########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains unit tests for the ska_low_mccs.events module.
"""
from contextlib import nullcontext
import pytest
from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.events import (
    EventSubscriptionHandler,
    DeviceEventManager,
    EventManager,
)

from testing.harness.tango_harness import TangoHarness


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    This is a slightly lazy hack to allow us to test event subscription
    against mocking. We want our tango harness to be up and running for
    this to work, but the Tango test contexts require at least one
    device to be running. So we stand up a single device, which we won't
    actually be using in any way.

    TODO: Find a way to stand up a Tango test harness that is 100% mock
    devices, and thus doesn't use a Tango test context at all.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/extra.json",
        "package": "ska_low_mccs",
        "device": "device",
        "proxy": MccsDeviceProxy,
    }


class TestEventSubscriptionHandler:
    """
    This class contains unit tests for the EventSubscriptionHandler
    class.
    """

    def test_subscribe(self, tango_harness: TangoHarness, logger):
        """
        Test subscription: specifically, test that when an instance is
        initialised with a given fqdn and the name of an event, the
        device at that fqdn receives a subscribe_event call for that
        event.

        :param tango_harness: a test harness for tango devices
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        mock_device_proxy = tango_harness.get_device("mock/mock/1")
        event_name = "mock_event"

        _ = EventSubscriptionHandler(mock_device_proxy, event_name, logger)

        # check that initialisation resulted in the device at the fqdn
        # receiving a subscription to the event
        mock_device_proxy.subscribe_event.assert_called_once()
        args, kwargs = mock_device_proxy.subscribe_event.call_args
        assert args[0] == event_name

    def test_event_pushing(self, tango_harness: TangoHarness, mocker, logger):
        """
        Test that when an instance's push_event subscription callback
        method is called, it passes the event on by invoking its own
        registered callbacks.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.mock
        :type mocker: :py:class:`pytest_mock.mocker`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        event_name = "mock_event"
        event_value = "mock_value"
        event_quality = "mock_quality"
        callback_count = 2  # test should pass for any positive value

        mock_device_proxy = tango_harness.get_device("mock/mock/1")
        event_subscription_handler = EventSubscriptionHandler(
            mock_device_proxy, event_name, logger
        )

        mock_callbacks = [mocker.Mock() for callback in range(callback_count)]
        for mock_callback in mock_callbacks:
            event_subscription_handler.register_callback(mock_callback)
            mock_callback.assert_called_once()
            mock_callback.reset_mock()

        # set up the mock_event we are going to push
        mock_event = mocker.Mock()
        mock_event.attr_value.name = event_name
        mock_event.attr_value.value = event_value
        mock_event.attr_value.quality = event_quality

        # push the event (we are pretending to be the device here)
        event_subscription_handler.push_event(mock_event)

        # check that the mock callback was called as expected
        for mock_callback in mock_callbacks:
            mock_callback.assert_called_once_with(
                event_name, event_value, event_quality
            )

    def test_unsubscribe(self, tango_harness: TangoHarness, logger):
        """
        Test that when an instance is deleted, the device receives an
        unsubcribe_event call.

        This is a pretty weak test because tango event unsubscription is
        via an event id, which this class under test stores internally.
        So to check that the right event id is unsubscribed would
        require us making this a very implementation-dependent test. So
        we just that exactly one unsubscribe call is made, and leave it
        at that.

        :param tango_harness: a test harness for tango devices
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        event_name = "mock_event"
        mock_device_proxy = tango_harness.get_device("mock/mock/1")

        event_subscription_handler = EventSubscriptionHandler(
            mock_device_proxy, event_name, logger
        )

        # Ideally we would `del event_subscription_handler` here, but `"del x`
        # isn't guaranteed to call `x.__del__`, so the best we can do is call
        # the private `_unsubscribe` method directly
        event_subscription_handler._unsubscribe()

        mock_device_proxy.unsubscribe_event.assert_called_once()


class TestDeviceEventManager:
    """
    This class contains unit tests for the DeviceEventManager class.
    """

    @pytest.mark.parametrize(
        ("allowed_events", "event_spec", "raise_context"),
        [
            (None, None, pytest.raises(ValueError)),
            (None, "event_1", nullcontext()),
            (None, ["event_1", "event_2"], nullcontext()),
            (["event_1", "event_2"], None, nullcontext()),
            (["event_1", "event_2"], "event_1", nullcontext()),
            (["event_1", "event_2"], "unknown_event", pytest.raises(ValueError)),
            (["event_1", "event_2"], ["event_1", "event_2"], nullcontext()),
            (
                ["event_1", "event_2"],
                ["event_1", "unknown_event"],
                pytest.raises(ValueError),
            ),
        ],
    )
    def test_event_spec(
        self,
        allowed_events,
        event_spec,
        raise_context,
        tango_harness: TangoHarness,
        mock_callback,
        logger,
    ):
        """
        Check the various supported value types for event_spec argument,
        including its interaction with the list of allowed events.

        :param allowed_events: list of allowed events to pass during
            initialisation of the instance under test
        :type allowed_events: list(str) or None
        :param event_spec: specification of the event or events to try
            to subscribe to
        :type event_spec: str or list(str) or None
        :param raise_context: a context indicating whether this test
            should raise a Value error or not
        :type raise_context: :py:class:`contextmanager`
        :param tango_harness: a test harness for tango devices
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        device_event_manager = DeviceEventManager("mock/mock/1", logger, allowed_events)

        with raise_context:
            device_event_manager.register_callback(mock_callback, event_spec=event_spec)

    def test_subscription(self, tango_harness: TangoHarness, mocker, logger):
        """
        Test subscription: specifically, test that when a a client
        subscribes to a specified event from a DeviceEventManager, the
        device managed by that DeviceEventManager receives a
        subscribe_event call for the specified event.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: :py:class:`pytest_mock.mocker`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        fqdn = "mock/mock/1"
        device_event_manager = DeviceEventManager(fqdn, logger)

        event_count = 2  # test should pass for any positive number
        callbacks = [mocker.Mock() for i in range(event_count)]

        mock_device_proxy = tango_harness.get_device("mock/mock/1")

        for i in range(event_count):
            event_name = f"mock_event_{i}"
            device_event_manager.register_callback(callbacks[i], event_spec=event_name)

            # check that initialisation resulted in the device at the fqdn
            # receiving a subscription to the event
            mock_device_proxy.subscribe_event.assert_called_once()
            args, kwargs = mock_device_proxy.subscribe_event.call_args
            assert args[0] == event_name

            mock_device_proxy.reset_mock()

    def test_event_pushing(self, tango_harness: TangoHarness, mocker, logger):
        """
        Test that when a EventSubscriptionHandler's push_event callback
        method is called, this DeviceEventMonitor receives the event and
        passes it down the change by invoking its own registered
        callbacks.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: :py:class:`pytest_mock.mocker`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """

        event_count = 2  # test should pass for any positive number
        fqdn = "mock/mock/1"

        device_event_manager = DeviceEventManager(fqdn, logger)

        mock_callbacks = [mocker.Mock() for i in range(event_count)]
        for i in range(event_count):
            event_name = f"mock_event_{i}"
            device_event_manager.register_callback(
                mock_callbacks[i], event_spec=event_name
            )
            mock_callbacks[i].assert_called_once()
            mock_callbacks[i].reset_mock()

        for i in range(event_count):
            event_name = f"mock_event_{i}"
            event_value = f"mock_value_{i}"
            event_quality = f"mock_quality_{i}"

            mock_event = mocker.Mock()
            mock_event.attr_value.name = event_name
            mock_event.attr_value.value = event_value
            mock_event.attr_value.quality = event_quality

            # push the event (this is quite implementation-dependent
            # because we are pretending to be the tango device)
            device_event_manager._handlers[event_name].push_event(mock_event)

            # check that the mock callback was called as expected
            mock_callbacks[i].assert_called_once_with(
                event_name, event_value, event_quality
            )


class TestEventManager:
    """
    This class contains unit tests for the EventManager class.
    """

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
        Check the various supported value types for fqdn_spec argument,
        including its interaction with the list of allowed fqdn.

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
        Test subscription: specifically, test that when a a client uses
        an EventManager to subscribe to a specified event from a
        specified device, the device receives a subscribe_event call for
        the specified event.

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
        Test that when an device pushes an event, the event moves down
        the tree and eventually causes the EventManager instance to call
        its own callbacks.

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
                event_manager._handlers[fqdn]._handlers[event].push_event(mock_event)

                # check that the mock callback was called as expected
                mock_callbacks[(fqdn, event)].assert_called_once_with(
                    fqdn, event, event_value, event_quality
                )
