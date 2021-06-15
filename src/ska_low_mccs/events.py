# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements infrastructure for event management in the MCCS subsystem."""

from __future__ import annotations  # allow forward references in type hints

__all__ = ["EventSubscriptionHandler", "DeviceEventManager", "EventManager"]

from functools import partial
import warnings
import logging
import backoff
from typing import Callable, Union

from tango import (
    DevFailed,
    EventData,
    EventType,
    DeviceProxy,
    DeviceAttribute,
)  # type: ignore[attr-defined]

from ska_low_mccs.device_proxy import MccsDeviceProxy


def _parse_spec(
    spec: Union[list[str], str] = None, allowed: list[str] = None
) -> list[str]:
    """
    Helper function that implements parsing of a specification (of events or fqdns)
    against which to register a callback.

    :param spec: specification (of events or fqdns) against which to
        register a callback. This is either a list of items, or a single
        item, or None. If None, it means all allowed items
    :param allowed: specification of the full set of allowed items
        from which the specification specifies items

    :return: a list of items (events or fqdns)

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
    This class handles subscription to change events on a single attribute from a single
    device.

    It allows registration of multiple callbacks.
    """

    def __init__(
        self: EventSubscriptionHandler,
        device_proxy: DeviceProxy,
        event_name: str,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new EventSubscriptionHandler.

        :param device_proxy: proxy to the device upon which the change
            event is subscribed
        :param event_name: name of the event; that is, the name of the
            attribute for which change events are subscribed.
        :param logger: the logger to be used by the object under test
        """
        self._logger = logger

        self._device = device_proxy
        self._event_name = event_name
        self._event_value = None
        self._event_quality = None
        self._subscription_id = None
        self._callbacks: list[Callable] = []

        self._subscribe()

    @backoff.on_exception(backoff.expo, DevFailed, factor=1, max_time=120)
    def _subscribe(self: EventSubscriptionHandler) -> None:
        """
        Subscribe to a change event.

        Even though we already have a DeviceProxy to the device that we
        want to subscribe to, it is still possible that the device is
        not ready, in which case subscription will fail and a
        :py:class:`tango.DevFailed` exception will be raised. Here, we
        attempt subscription in a backoff-retry, and only raise the
        exception one our retries are exhausted. (The alternative option
        of subscribing with "stateless=True" could not be made to work.)
        """
        self._subscription_id = self._device.subscribe_event(
            self._event_name, EventType.CHANGE_EVENT, self
        )

    def _read(self: EventSubscriptionHandler) -> object:
        """
        Manually read an attribute. Used when we receive an event with empty attribute
        data.

        :return: the attribute value
        """
        return self._device.read_attribute(self._event_name)

    def _process_event(
        self: EventSubscriptionHandler, event: EventData
    ) -> DeviceAttribute:
        """
        Extract the attribute value from a received event; or, if the event failed to
        carry an attribute value, read the attribute value directly.

        :param event: the received event

        :return: the attribute value data
        """
        if event.attr_value is None:
            warning_message = (
                "Received change event with empty value. Falling back to manual "
                f"attribute read. Event.err is {event.err}. Event.errors is\n"
                f"{event.errors}."
            )
            warnings.warn(UserWarning(warning_message))
            self._logger.warn(warning_message)
            return self._read()
        else:
            return event.attr_value

    def _call(
        self: EventSubscriptionHandler,
        callback: Callable,
        attribute_data: DeviceAttribute,
    ) -> None:
        """
        Call the callback with unpacked attribute data.

        :param callback: function handle for the callback
        :param attribute_data: the attribute data to be unpacked and
            used to call the callback
        """
        callback(attribute_data.name, attribute_data.value, attribute_data.quality)

    def register_callback(self: EventSubscriptionHandler, callback: Callable) -> None:
        """
        Register a callback for events handled by this handler.

        :param callback: function handle of the form
            ``callback(name, value, quality)``.
        """
        self._callbacks.append(callback)
        self._call(callback, self._read())

    def push_event(self: EventSubscriptionHandler, event: EventData) -> None:
        """
        Callback called by the tango system when a subscribed event occurs. It in turn
        invokes all its own callbacks.

        :param event: an object encapsulating the event data.
        """
        attribute_data = self._process_event(event)
        for callback in self._callbacks:
            self._call(callback, attribute_data)

    def _unsubscribe(self: EventSubscriptionHandler) -> None:
        """Unsubscribe from the event."""
        if self._subscription_id is not None:
            self._device.unsubscribe_event(self._subscription_id)
            self._subscription_id = None

    def __del__(self: EventSubscriptionHandler) -> None:
        """Cleanup before destruction."""
        self._unsubscribe()


class DeviceEventManager:
    """This class is used to handle multiple events from a single device."""

    def __init__(
        self: DeviceEventManager,
        fqdn: str,
        logger: logging.Logger,
        events: list[str] = None,
    ) -> None:
        """
        Initialise a new DeviceEventManager object.

        :param fqdn: the fully qualified device name of the device for
            which this DeviceEventManager will manage change events
        :param logger: the logger to be used by the object under test
        :param events: Names of events handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events not in this list
        """
        self._logger = logger

        self._allowed_events = events
        self._handlers: dict[str, EventSubscriptionHandler] = {}

        self._fqdn = fqdn
        self._device = MccsDeviceProxy(fqdn, logger)

    def register_callback(
        self: DeviceEventManager,
        callback: Callable,
        event_spec: Union[list[str], str] = None,
    ) -> None:
        """
        Register a callback for an event (or events) handled by this handler.

        :param callback: function handle of the form
            ``callback(name, value, quality)``.
        :param event_spec: a specification of the event or events for
            which change events are subscribed. This may be the name of
            a single event, or a list of such names, or None, in which
            case the events provided at initialisation are used

        :raises ValueError: if the event is not in the list
            of allowed events
        """
        try:
            events = _parse_spec(event_spec, self._allowed_events)
        except ValueError as value_error:
            raise ValueError("Error parsing event specification") from value_error

        for event in events:
            if event not in self._handlers:
                self._handlers[event] = self._create_event_subscription_handler(event)
            self._handlers[event].register_callback(callback)

    def _create_event_subscription_handler(
        self: DeviceEventManager, event: str
    ) -> EventSubscriptionHandler:
        """
        Create a new event subscription handler for a given event.

        :param event: the event for which change events are subscribed.

        :return: an event subscription handler for the device
        """
        return EventSubscriptionHandler(self._device, event, self._logger)


class EventManager:
    """
    Class EventManager is used to handle events from the tango subsystem.

    It supports and manages multiple event types from multiple devices.
    """

    def __init__(
        self: EventManager,
        logger: logging.Logger,
        fqdns: list[str] = None,
        events: list[str] = None,
    ) -> None:
        """
        Initialise a new EventManager object.

        :param logger: the logger to be used by the object under test
        :param fqdns: FQDNs of devices handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events from devices whose FQDN is not in this list
        :param events: Names of events handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events not in this list
        """
        self._logger = logger

        self._allowed_fqdns = fqdns
        self._allowed_events = events
        self._handlers: dict[str, DeviceEventManager] = {}

    def register_callback(
        self: EventManager,
        callback: Callable,
        fqdn_spec: Union[list[str], str] = None,
        event_spec: Union[list[str], str] = None,
    ) -> None:
        """
        Register a callback for a particular event from a particularly device.

        :param callback: function handle of the form
            ``callback(fqdn, name, value, quality)``.
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.
        :param event_spec: a specification of the event or events for
            which change events are subscribed. This may be the name of
            a single event, or a list of such names, or None, in which
            case the events provided at initialisation are used

        :raises ValueError: if the FQDN and event are not in
            the lists of allowed FQDNs and allowed events respectively
        """
        try:
            fqdns = _parse_spec(fqdn_spec, self._allowed_fqdns)
        except ValueError as value_error:
            raise ValueError("Error parsing FQDN specification") from value_error

        for fqdn in fqdns:
            if fqdn not in self._handlers:
                self._handlers[fqdn] = self._create_device_event_manager(fqdn)
            self._handlers[fqdn].register_callback(
                partial(callback, fqdn), event_spec=event_spec
            )

    def _create_device_event_manager(
        self: EventManager, fqdn: str
    ) -> DeviceEventManager:
        """
        Create a new device event manager for a given FQDN.

        :param fqdn: FQDN of the device for which we are creating a
            device event manager

        :return: a device event manager for the device at a given FQDN
        """
        return DeviceEventManager(fqdn, self._logger, self._allowed_events)
