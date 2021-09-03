########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains unit tests for the ska_low_mccs.device_proxy module."""
from __future__ import annotations  # allow forward references in type hints

import logging

import pytest_mock

from ska_low_mccs import MccsDeviceProxy

from ska_low_mccs.testing.tango_harness import TangoHarness


class TestMccsDeviceProxy:
    """This class contains unit tests for the MccsDeviceProxy class."""

    def test_subscription(
        self: TestMccsDeviceProxy,
        tango_harness: TangoHarness,
        mocker: pytest_mock.MockerFixture,
        logger: logging.Logger,
    ) -> None:
        """
        Test change event subscription.

        Specifically, test that when a client registered a change event
        callback on an MccsDeviceProxy, this results in the underlying
        device receiving a subscribe_event call for the specified event.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :param logger: the logger to be used by the object under test
        """
        fqdn = "mock/mock/1"
        mccs_device_proxy = MccsDeviceProxy(fqdn, logger)

        event_count = 2  # test should pass for any positive number
        callbacks = [mocker.Mock() for i in range(event_count)]

        mock_device_proxy = tango_harness.get_device("mock/mock/1")

        for i in range(event_count):
            event_name = f"mock_event_{i}"
            mccs_device_proxy.add_change_event_callback(event_name, callbacks[i])

            # check that initialisation resulted in the device at the fqdn
            # receiving a subscription to the event
            mock_device_proxy.subscribe_event.assert_called_once()
            args, kwargs = mock_device_proxy.subscribe_event.call_args
            assert args[0] == event_name

            mock_device_proxy.reset_mock()

    def test_event_pushing(
        self: TestMccsDeviceProxy,
        tango_harness: TangoHarness,
        mocker: pytest_mock.MockerFixture,
        logger: logging.Logger,
    ) -> None:
        """
        Test that events result in callbacks being called.

        Specifically, test that when an MccsDeviceProxy's
        ``_change_event_received`` callback method is called with an
        change event for a particular attribute, all callbacks
        registered with the MccsDeviceProxy for that attribute are
        called, and callbacks registered for other attributes are not
        called.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        :param logger: the logger to be used by the object under test
        """
        event_count = 3  # test should pass for any positive number
        fqdn = "mock/mock/1"

        device_proxy = MccsDeviceProxy(fqdn, logger)

        mock_callbacks = [mocker.Mock() for i in range(event_count)]
        for i in range(event_count):
            event_name = f"mock_event_{i+1}"
            device_proxy.add_change_event_callback(event_name, mock_callbacks[i])

            for j in range(event_count):
                if i == j:
                    mock_callbacks[j].assert_called_once()
                    mock_callbacks[j].reset_mock()
                else:
                    mock_callbacks[j].assert_not_called()

        for i in range(event_count):
            event_name = f"mock_event_{i+1}"
            event_value = f"mock_value_{i+1}"
            event_quality = f"mock_quality_{i+1}"

            mock_event = mocker.Mock()
            mock_event.err = False
            mock_event.attr_value.name = event_name
            mock_event.attr_value.value = event_value
            mock_event.attr_value.quality = event_quality

            # push the event (this is quite implementation-dependent
            # because we are pretending to be the tango device)
            device_proxy._change_event_received(mock_event)

            # check that the mock callback was called as expected, and
            # that other mock callbacks were not called.
            for j in range(event_count):
                if i == j:
                    mock_callbacks[j].assert_called_once_with(
                        event_name, event_value, event_quality
                    )
                    mock_callbacks[j].reset_mock()
                else:
                    mock_callbacks[j].assert_not_called()
