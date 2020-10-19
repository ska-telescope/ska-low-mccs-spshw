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
__all__ = ["EventSubscriptionHandler", "DeviceEventManager", "EventManager"]

from functools import partial
import time

import tango
from tango import EventType


def _parse_spec(spec, allowed):
    """
    Helper function that implements parsing of a specification (of
    events or fqdns) against which to register a callback

    :param spec: specification (of events or fqdns) against which to
        register a callback. This is either a list of items, or a single
        item, or None. If None, it means all allowed items
    :type spec: list of str, or str, or None
    :param allowed: specification of the full set of allowed items
        from which the specification specifies items
    :type allowed: list of str, or None

    :return: a list of items (events or fqdns)
    :rtype: list of str

    :raises ValueError: if nothing was specified by the
        specification, or if an item was specified that is not in the
        list of allowed items
    """
    if spec is None:
        if allowed is None:
            raise ValueError("Nothing specified")
        return allowed

    if isinstance(spec, str):
        items = [spec]
    else:
        items = spec

    if allowed is not None:
        for item in items:
            if item not in allowed:
                raise ValueError(f"Unknown item {spec}")

    return items


class EventSubscriptionHandler:
    """
    This class handles subscription to change events on a single
    attribute from a single device. It allows registration of multiple
    callbacks.
    """

    def __init__(self, device_proxy, event_name):
        """
        Initialise a new EventSubscriptionHandler

        :param device_proxy: proxy to the device upon which the change
            event is subscribed
        :type device_proxy: :py:class:`tango.DeviceProxy`
        :param event_name: name of the event; that is, the name of the
            attribute for which change events are subscribed.
        :type event_name: str
        """
        self._device = device_proxy
        self._callbacks = []
        self._subscription_id = None

        self._subscribe(event_name)

    def _subscribe(self, event_name):
        """
        Subscribe to a change event

        :param event_name: name of the event; that is, the name of the
            attribute for which change events are subscribed.
        :type event_name: str
        """
        self._subscription_id = self._device.subscribe_event(
            event_name, EventType.CHANGE_EVENT, self, stateless=True
        )

    def register_callback(self, callback):
        """
        Register a callback for events handled by this handler

        :param callback: callable to be called when an event is received
            by this event handler. The callable will be called with
            three positional arguments: event name, value and quality.
        :type callback: callable
        """
        self._callbacks.append(callback)

    def push_event(self, event):
        """
        Callback called by the tango system when a subscribed event
        occurs. It in turn invokes all its own callbacks.

        :param event: an object encapsulating the event data.
        :type event: :py:class:`tango.EventData`
        """
        if event.attr_value is not None and event.attr_value.value is not None:
            for callback in self._callbacks:
                callback(
                    event.attr_value.name,
                    event.attr_value.value,
                    event.attr_value.quality,
                )

    def _unsubscribe(self):
        """
        Unsubscribe from the event
        """
        if self._subscription_id is not None:
            self._device.unsubscribe_event(self._subscription_id)
            self._subscription_id = None

    def __del__(self):
        """
        Cleanup before destruction
        """
        self._unsubscribe()


class DeviceEventManager:
    """
    Class DeviceEventManager is used to handle multiple events from a
    single device.
    """

    def __init__(self, fqdn, events=None):
        """
        Initialise a new DeviceEventManager object

        :param fqdn: the fully qualified device name of the device for
            which this DeviceEventManager will manage change events
        :type fqdn: str
        :param events: Names of events handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events not in this list
        :type events: list, optional
        :raises ConnectionError: if unable to create a DeviceProxy
            connection to the target device
        """
        # HACK: Synchronous implementation of connection retries, to be
        # fixed eventually by asyncio implementation
        self._device = None
        dev_failed = None
        sleeps = [0.1, 0.2, 0.5, 1]
        for sleep in sleeps:
            try:
                self._device = tango.DeviceProxy(fqdn)
            except tango.DevFailed as _dev_failed:
                dev_failed = _dev_failed
                time.sleep(sleep)
                continue
            else:
                break
        else:
            raise ConnectionError(f"Could not connect to device {fqdn}") from dev_failed

        self._allowed_events = events
        self._handlers = {}

    def register_callback(self, callback, event_spec=None):
        """
        Register a callback for an event (or events) handled by this
        handler

        :param callback: callable to be called when an event is received
            by this event handler. The callable will be called with
            three positional arguments: event name, value and quality.
        :type callback: callable
        :param event_spec: a specification of the event or events for
            which change events are subscribed. This may be the name of
            a single event, or a list of such names, or None, in which
            case the events provided at initialisation are used
        :type event_spec: str or list of str or None

        :raises ValueError: if the event is not in the list
            of allowed events
        """
        try:
            events = _parse_spec(event_spec, self._allowed_events)
        except ValueError as value_error:
            raise ValueError("Error parsing event specification") from value_error

        for event in events:
            if event not in self._handlers:
                self._handlers[event] = EventSubscriptionHandler(self._device, event)
            self._handlers[event].register_callback(callback)


class EventManager:
    """
    Class EventManager is used to handle events from the tango subsystem.
    It supports and manages multiple event types from multiple devices.
    """

    def __init__(self, fqdns=None, events=None):
        """
        Initialise a new EventManager object

        :param fqdns: FQDNs of devices handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events from devices whose FQDN is not in this list
        :type fqdns: list, optional
        :param events: Names of events handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events not in this list
        :type events: list, optional
        """
        self._allowed_fqdns = fqdns
        self._allowed_events = events
        self._handlers = {}

    def register_callback(self, callback, fqdn_spec=None, event_spec=None):
        """
        Register a callback for a particular event from a particularly
        device

        :param callback: callable to be called with args (fqdn, name,
            value, quality) whenever the event is received
        :type callback: callable
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.
        :type fqdn_spec: str, or list of str, or None
        :param event_spec: a specification of the event or events for
            which change events are subscribed. This may be the name of
            a single event, or a list of such names, or None, in which
            case the events provided at initialisation are used
        :type event_spec: str, or list of str, or None

        :raises ValueError: if the FQDN and event are not in
            the lists of allowed FQDNs and allowed events respectively
        """
        try:
            fqdns = _parse_spec(fqdn_spec, self._allowed_fqdns)
        except ValueError as value_error:
            raise ValueError("Error parsing FQDN specification") from value_error

        for fqdn in fqdns:
            if fqdn not in self._handlers:
                self._handlers[fqdn] = DeviceEventManager(fqdn, self._allowed_events)
            self._handlers[fqdn].register_callback(
                partial(callback, fqdn), event_spec=event_spec
            )
