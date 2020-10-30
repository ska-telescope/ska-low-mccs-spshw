########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains unit tests for the ska.low.mccs.events module
"""
from contextlib import nullcontext
import pytest
import tango
from ska.low.mccs.events import (
    EventSubscriptionHandler,
    DeviceEventManager,
    EventManager,
)


class TestEventSubscriptionHandler:
    """
    This class contains unit tests for the EventSubscriptionHandler
    class.
    """

    def test_subscribe(self, mock_device_proxies):
        """
        Test subscription: specifically, test that when an instance is
        initialised with a given fqdn and the name of an event, the
        device at that fqdn receives a subscribe_event call for that
        event.

        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        fqdn = "mock/mock/1"
        mock_device_proxy = tango.DeviceProxy(fqdn)

        event_name = "mock_event"

        _ = EventSubscriptionHandler(mock_device_proxy, event_name)

        # check that initialisation resulted in the device at the fqdn
        # receiving a subscription to the event
        mock_device_proxy.subscribe_event.assert_called_once()
        args, kwargs = mock_device_proxy.subscribe_event.call_args
        assert args[0] == event_name

    def test_event_pushing(self, mocker, mock_device_proxies):
        """
        Test that when an instance's push_event subscription callback
        method is called, it passes the event on by invoking its own
        registered callbacks

        :param mocker: fixture that wraps unittest.mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        fqdn = "mock/mock/1"
        event_name = "mock_event"
        event_value = "mock_value"
        event_quality = "mock_quality"
        callback_count = 2  # test should pass for any positive value

        mock_device_proxy = tango.DeviceProxy(fqdn)
        event_subscription_handler = EventSubscriptionHandler(
            mock_device_proxy, event_name
        )

        mock_callbacks = [mocker.Mock() for callback in range(callback_count)]
        for mock_callback in mock_callbacks:
            event_subscription_handler.register_callback(mock_callback)

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

    def test_unsubscribe(self, mocker, mock_device_proxies):
        """
        Test that when an instance is deleted, the device receives an
        unsubcribe_event call.

        This is a pretty weak test because tango event unsubscription is
        via an event id, which this class under test stores internally.
        So to check that the right event id is unsubscribed would
        require us making this a very implementation-dependent test. So
        we just that exactly one unsubscribe call is made, and leave it
        at that.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        fqdn = "mock/mock/1"
        event_name = "mock_event"
        mock_device_proxy = tango.DeviceProxy(fqdn)

        event_subscription_handler = EventSubscriptionHandler(
            mock_device_proxy, event_name
        )

        # Ideally we would `del event_subscription_handler` here, but `"del x`
        # isn't guaranteed to call `x.__del__`, so the best we can do is call
        # the private `_unsubscribe` method directly
        event_subscription_handler._unsubscribe()

        mock_device_proxy.unsubscribe_event.assert_called_once()


class TestDeviceEventManager:
    """
    This class contains unit tests for the DeviceEventManager class
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
        self, allowed_events, event_spec, raise_context, mocker, mock_device_proxies
    ):
        """
        Check the various supported value types for event_spec argument,
        including its interaction with the list of allowed events.

        :param allowed_events: list of allowed events to pass during
            initialisation of the instance under test
        :type allowed_events: list of str or None
        :param event_spec: specification of the event or events to try
            to subscribe to
        :type event_spec: str, or list of str, or None
        :param raise_context: a context indicating whether this test
            should raise a Value error or not
        :type raise_context: context
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        device_event_manager = DeviceEventManager("mock/mock/1", allowed_events)

        with raise_context:
            device_event_manager.register_callback(mocker.Mock(), event_spec=event_spec)

    def test_subscription(self, mocker, mock_device_proxies):
        """
        Test subscription: specifically, test that when a
        a client subscribes to a specified event from a
        DeviceEventManager, the device managed by that DeviceEventManager
        receives a subscribe_event call for the specified event.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        fqdn = "mock/mock/1"
        device_event_manager = DeviceEventManager(fqdn)

        event_count = 2  # test should pass for any positive number
        callbacks = [mocker.Mock() for i in range(event_count)]

        mock_device_proxy = tango.DeviceProxy(fqdn)

        for i in range(event_count):
            event_name = f"mock_event_{i}"
            device_event_manager.register_callback(callbacks[i], event_spec=event_name)

            # check that initialisation resulted in the device at the fqdn
            # receiving a subscription to the event
            mock_device_proxy.subscribe_event.assert_called_once()
            args, kwargs = mock_device_proxy.subscribe_event.call_args
            assert args[0] == event_name

            mock_device_proxy.reset_mock()

    def test_event_pushing(self, mocker, mock_device_proxies):
        """
        Test that when a EventSubscriptionHandler's push_event
        callback method is called, this DeviceEventMonitor receives the
        event and passes it down the change by invoking its own
        registered callbacks

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """

        event_count = 2  # test should pass for any positive number
        fqdn = "mock/mock/1"

        device_event_manager = DeviceEventManager(fqdn)

        mock_callbacks = [mocker.Mock() for i in range(event_count)]
        for i in range(event_count):
            event_name = f"mock_event_{i}"
            device_event_manager.register_callback(
                mock_callbacks[i], event_spec=event_name
            )

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
    This class contains unit tests for the EventManager class
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
        self, allowed_fqdns, fqdn_spec, raise_context, mocker, mock_device_proxies
    ):
        """
        Check the various supported value types for fqdn_spec argument,
        including its interaction with the list of allowed fqdn.

        :param allowed_fqdns: list of FQDNs to pass during
            initialisation of the instance under test
        :type allowed_fqdns: list of str or None
        :param fqdn_spec: specification of the fqdn/s of device/s to
            attempt event subscription against
        :type fqdn_spec: str, or list of str, or None
        :param raise_context: a context indicating whether this test
            should raise a Value error or not
        :type raise_context: context
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        event_manager = EventManager(fqdns=allowed_fqdns)

        with raise_context:
            event_manager.register_callback(
                mocker.Mock(), fqdn_spec=fqdn_spec, event_spec="mock"
            )

    def test_subscribe(self, mocker, mock_device_proxies):
        """
        Test subscription: specifically, test that when a
        a client uses an EventManager to subscribe to a specified event
        from a specified device, the device receives a subscribe_event
        call for the specified event.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        device_count = 2  # test should pass for any positive number
        event_count = 2  # test should pass for any positive number

        event_manager = EventManager()

        fqdns = [f"mock/mock/{i}" for i in range(device_count)]
        events = [f"mock_event_{i}" for i in range(event_count)]

        for fqdn in fqdns:
            mock_device_proxy = tango.DeviceProxy(fqdn)

            for event in events:
                mock_callback = mocker.Mock()

                event_manager.register_callback(
                    mock_callback, fqdn_spec=fqdn, event_spec=event
                )

                mock_device_proxy.subscribe_event.assert_called_once()
                args, kwargs = mock_device_proxy.subscribe_event.call_args
                assert args[0] == event

                mock_device_proxy.reset_mock()

    def test_event_pushing(self, mocker, mock_device_proxies):
        """
        Test that when an device pushes an event, the event moves down
        the tree and eventually causes the EventManager instance to
        call its own callbacks

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        """
        device_count = 2  # test should pass for any positive number
        event_count = 2  # test should pass for any positive number

        fqdns = [f"mock/mock/{i}" for i in range(device_count)]
        events = [f"mock_event_{i}" for i in range(event_count)]
        mock_callbacks = {}

        event_manager = EventManager()
        for fqdn in fqdns:
            for event in events:
                mock_callbacks[(fqdn, event)] = mocker.Mock()
                event_manager.register_callback(
                    mock_callbacks[(fqdn, event)], fqdn_spec=fqdn, event_spec=event
                )

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
