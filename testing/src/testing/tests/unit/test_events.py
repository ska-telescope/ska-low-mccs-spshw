# type: ignore
########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains unit tests for the ska_low_mccs.events module."""
from contextlib import nullcontext
import pytest
from ska_low_mccs.events import EventManager

from testing.harness.tango_harness import TangoHarness


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing. In this case we mock all
    devices, so there is no need to stand up any.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return None


class TestEventManager:
    """This class contains unit tests for the EventManager class."""

    @pytest.mark.parametrize(
        ("allowed_fqdns", "fqdn_spec", "raise_context"),
        [
            (None, None, pytest.raises(ValueError)),
            (None, "mock/mock/1", nullcontext()),
            (None, ["mock/mock/1", "mock/mock/2"], nullcontext()),
            (["known/mock/1", "known/mock/2"], None, nullcontext()),
            (["known/mock/1", "known/mock/2"], "known/mock/1", nullcontext()),
            (
                ["known/mock/1", "known/mock/2"],
                ["known/mock/1", "known/mock/2"],
                nullcontext(),
            ),
            (
                ["known/mock/1", "known/mock/2"],
                "unknown/mock/1",
                pytest.raises(ValueError),
            ),
            (
                ["known/mock/1", "known/mock/2"],
                ["known/mock/1", "unknown/mock/1"],
                pytest.raises(ValueError),
            ),
        ],
    )
    def test_fqdns_spec(
        self,
        allowed_fqdns,
        fqdn_spec,
        raise_context,
        tango_harness: TangoHarness,
        mocker,
        logger,
    ):
        """
        Check the various supported value types for fqdn_spec argument, including its
        interaction with the list of allowed fqdn.

        :param allowed_fqdns: list of FQDNs to pass during
            initialisation of the instance under test
        :type allowed_fqdns: list(str) or None
        :param fqdn_spec: specification of the fqdn/s of device/s to
            attempt event subscription against
        :type fqdn_spec: str or list(str) or None
        :param raise_context: a context indicating whether this test
            should raise a Value error or not
        :type raise_context: :py:class:`contextmanager`
        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: :py:class:`pytest_mock.mocker`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        event_manager = EventManager(logger, fqdns=allowed_fqdns)

        with raise_context:
            event_manager.register_callback(
                mocker.Mock(), fqdn_spec=fqdn_spec, event_spec="mock"
            )

    def test_subscribe(self, tango_harness: TangoHarness, mock_callback, logger):
        """
        Test subscription: specifically, test that when a a client uses an EventManager
        to subscribe to a specified event from a specified device, the device receives a
        subscribe_event call for the specified event.

        :param tango_harness: a test harness for tango devices
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        device_count = 2  # test should pass for any positive number
        event_count = 2  # test should pass for any positive number

        event_manager = EventManager(logger)

        fqdns = [f"mock/mock/{i}" for i in range(1, device_count + 1)]
        events = [f"mock_event_{i}" for i in range(1, event_count + 1)]

        for fqdn in fqdns:
            mock_device_proxy = tango_harness.get_device(fqdn)

            for event in events:
                mock_callback.reset_mock()

                event_manager.register_callback(
                    mock_callback, fqdn_spec=fqdn, event_spec=event
                )

                mock_device_proxy.subscribe_event.assert_called_once()
                args, kwargs = mock_device_proxy.subscribe_event.call_args
                assert args[0] == event

                mock_device_proxy.reset_mock()

    def test_event_pushing(self, tango_harness: TangoHarness, mocker, logger):
        """
        Test that when an device pushes an event, the event moves down the tree and
        eventually causes the EventManager instance to call its own callbacks.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: :py:class:`pytest_mock.mocker`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        device_count = 2  # test should pass for any positive number
        event_count = 2  # test should pass for any positive number

        fqdns = [f"mock/mock/{i}" for i in range(1, device_count + 1)]
        events = [f"mock_event_{i}" for i in range(1, event_count + 1)]
        mock_callbacks = {}

        event_manager = EventManager(logger)
        for fqdn in fqdns:
            for event in events:
                mock_callbacks[(fqdn, event)] = mocker.Mock()
                event_manager.register_callback(
                    mock_callbacks[(fqdn, event)], fqdn_spec=fqdn, event_spec=event
                )
                mock_callbacks[(fqdn, event)].assert_called_once()
                mock_callbacks[(fqdn, event)].reset_mock()

        for fqdn in fqdns:
            for event in events:
                event_value = f"mock_value_for_{event}"
                event_quality = f"mock_quality_for_{event}"

                mock_event = mocker.Mock()
                mock_event.attr_value.name = event
                mock_event.attr_value.value = event_value
                mock_event.attr_value.quality = event_quality

                # push the event (this is quite implementation-dependent
                # because we are pretending to be the tango device)
                event_manager._handlers[fqdn]._change_event_received(mock_event)

                # check that the mock callback was called as expected
                mock_callbacks[(fqdn, event)].assert_called_once_with(
                    fqdn, event, event_value, event_quality
                )
