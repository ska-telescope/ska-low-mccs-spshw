# -*- coding: utf-8 -*-
#
# This file is part of the ska.low.mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for event management in the MCCS
subsystem.

"""
__all__ = ["EventManager"]

import tango
from tango import EventType


class EventManager:
    """
    Class EventManager is used to handle events from the tango subsystem.
    """

    def __init__(
        self, fqdn, update_callback=None, event_names=["state", "healthState"]
    ):
        """
        Initialise a new EventManager object

        :param fqdn: the fully qualified device name of the device publishing events
        :type fqdn: string
        :param update_callback: a callback to update the devices health state
        :type update_callback: function
        """
        self._eventIds = []
        self._fqdn = fqdn
        self.callback = update_callback
        # Always subscribe to state change, it's pushed by the base classes
        # stateless=True is needed to deal with device not running or device restart
        try:
            self._deviceProxy = tango.DeviceProxy(fqdn)
            self._event_names = event_names
            for event_name in self._event_names:
                id = self._deviceProxy.subscribe_event(
                    event_name, EventType.CHANGE_EVENT, self, stateless=True
                )
                self._eventIds.append(id)
        except Exception as df:
            print(f"device probably not started for {fqdn}", df)

    def unsubscribe(self):
        """
        Unsubscribe all events
        """
        for eventId in self._eventIds:
            self._deviceProxy.unsubscribe_event(eventId)

    def push_event(self, ev):
        """
        A consumer callback used to inform the device of events from the subscribed
        publishers

        :param ev: an object encapsulating the event data.
        """
        if ev.attr_value is not None and ev.attr_value.value is not None:
            if self.callback is not None:
                self.callback(
                    self._fqdn,
                    ev.attr_value.name,
                    ev.attr_value.value,
                    ev.attr_value.quality,
                )
