# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements infrastructure for event management in the MCCS subsystem."""
__all__ = ["EventManager"]

from functools import partial

from ska_low_mccs import MccsDeviceProxy


def _parse_spec(spec, allowed):
    """
    Helper function that implements parsing of a specification (of events or fqdns)
    against which to register a callback.

    :param spec: specification (of events or fqdns) against which to
        register a callback. This is either a list of items, or a single
        item, or None. If None, it means all allowed items
    :type spec: list(str), or str, or None
    :param allowed: specification of the full set of allowed items
        from which the specification specifies items
    :type allowed: list(str), or None

    :return: a list of items (events or fqdns)
    :rtype: list(str)

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


class EventManager:
    """
    Class EventManager is used to handle events from the tango subsystem.

    It supports and manages multiple event types from multiple devices.
    """

    def __init__(self, logger, fqdns=None, events=None):
        """
        Initialise a new EventManager object.

        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        :param fqdns: FQDNs of devices handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events from devices whose FQDN is not in this list
        :type fqdns: list, optional
        :param events: Names of events handled by this instance. If
            provided, this instance will reject attempts to subscribe
            to events not in this list
        :type events: list, optional
        """
        self._logger = logger

        self._allowed_fqdns = fqdns
        self._allowed_events = events
        self._handlers = {}

    def register_callback(self, callback, fqdn_spec=None, event_spec=None):
        """
        Register a callback for a particular event from a particularly device.

        :param callback: function handle of the form
            ``callback(fqdn, name, value, quality)``.
        :type callback: callable
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.
        :type fqdn_spec: str or list(str) or None
        :param event_spec: a specification of the event or events for
            which change events are subscribed. This may be the name of
            a single event, or a list of such names, or None, in which
            case the events provided at initialisation are used
        :type event_spec: str or list(str) or None

        :raises ValueError: if the FQDN and event are not in
            the lists of allowed FQDNs and allowed events respectively
        """
        try:
            fqdns = _parse_spec(fqdn_spec, self._allowed_fqdns)
        except ValueError as value_error:
            raise ValueError("Error parsing FQDN specification") from value_error

        try:
            events = _parse_spec(event_spec, self._allowed_events)
        except ValueError as value_error:
            raise ValueError("Error parsing event specification") from value_error

        for fqdn in fqdns:
            if fqdn not in self._handlers:
                self._handlers[fqdn] = MccsDeviceProxy(fqdn, self._logger)
            for event in events:
                self._handlers[fqdn].add_change_event_callback(
                    event, partial(callback, fqdn)
                )
