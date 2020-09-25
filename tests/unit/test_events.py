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
from collections import defaultdict
import pytest
import tango
from ska.low.mccs.events import EventManager


@pytest.fixture
def mock_device_proxies(mocker):
    """
    Fixture that patches :class:`tango.DeviceProxy` to always return the
    same mock for each fqdn

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: unittest.Mock wrapper
    :yield: a dictionary (but don't access it directly, access it
        through :class:`tango.DeviceProxy` calls)
    """
    device_proxy_mocks = defaultdict(mocker.Mock)
    mocker.patch("tango.DeviceProxy", side_effect=lambda fqdn: device_proxy_mocks[fqdn])
    yield device_proxy_mocks


class TestEventManager:
    """
    This class contains unit tests for the ska.low.mccs.events.EventManager class
    """

    def test_init(self, mocker, mock_device_proxies):
        """
        Check eventManager initialisation: specifically, test that when
        an EventManager is initialised with a given fqdn and list of
        events, the device at that fqdn receives a subscribeEvent call
        for each event on the list.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: unittest.Mock wrapper
        :param mock_device_proxies: fixture that patches
            :class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :class:`tango.DeviceProxy` calls)
        """
        # set up the event manager args
        fqdn = "foo/bah/1"
        event_names = ["fooChange", "bahChange"]
        mock_callback = mocker.Mock()
        mock_device_proxy = tango.DeviceProxy(fqdn)

        # initialise the event manager
        _ = EventManager(fqdn, mock_callback, event_names)

        # check that event manager initialisation resulted in the device
        # at the fqdn receiving subscriptions to each event
        assert event_names == [
            call[0][0] for call in mock_device_proxy.subscribe_event.call_args_list
        ]

    def test_event_pushing(self, mocker, mock_device_proxies):
        """
        Test that when an eventManager's push_event callback method is
        called, the eventManager passes the event on by invoking its own
        callback

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: fixture
        :param mock_device_proxies: fixture that patches
            :class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :class:`tango.DeviceProxy` calls)
        """

        # set up our event_manager with some events and a mock callback
        fqdn = "foo/bah/1"
        event_names = ["fooChange", "bahChange"]
        mock_callback = mocker.Mock()
        event_manager = EventManager(fqdn, mock_callback, event_names)

        # set up the mock_event we are going to push
        (event_name, event_value, event_quality) = ("fooChange", "value", "quality")
        mock_event = mocker.Mock()
        mock_event.attr_value.name = event_name
        mock_event.attr_value.value = event_value
        mock_event.attr_value.quality = event_quality

        # push the event (we are pretending to be the device here)
        event_manager.push_event(mock_event)

        # check that the mock callback with called as expected
        mock_callback.assert_called_once_with(
            fqdn, event_name, event_value, event_quality
        )

    @pytest.mark.parametrize("trigger", ["unsubscribe", "delete"])
    def test_unsubscribe(self, trigger, mocker, mock_device_proxies):
        """
        Test that when an event manager is deleted or told to
        unsubscribe from all of its events, the device receives the
        right number of unsubcribeEvent calls.

        This is a pretty weak test because tango event unsubscription is
        via eventId, which the eventManager stores internally. So to
        check that the right eventIds are unsubscribed would require us
        making this a very implementation-dependent test. So we just
        check that the right number of unsubscribe calls are made, and
        leave it at that.

        :param trigger: the action that should trigger the unsubscribe:
            either "unsubscribe" for an explicit call to the unsubscribe
            method, or "delete" for deletion of the event_manager
            object.
        :type trigger: str
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: unittest.Mock wrapper
        :param mock_device_proxies: fixture that patches
            :class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :class:`tango.DeviceProxy` calls)
        """
        # set up the event manager args
        fqdn = "foo/bah/1"
        event_names = ["fooChange", "bahChange"]
        mock_callback = mocker.Mock()
        mock_device_proxy = tango.DeviceProxy(fqdn)

        # initialise the event manager
        event_manager = EventManager(fqdn, mock_callback, event_names)

        # now unsubscribe / delete
        if trigger == "unsubscribe":
            event_manager.unsubscribe()
        elif trigger == "delete":
            del event_manager

        # check that the device received an unsubscribe_event call for
        # each event name
        mock_device_proxy.unsubscribe_event.call_count == len(event_names)
