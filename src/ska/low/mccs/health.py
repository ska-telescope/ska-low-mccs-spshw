# -*- coding: utf-8 -*-
#
# This file is part of the ska.low.mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for health management in the MCCS
subsystem.

"""
__all__ = ["HealthMonitor"]

from tango import DevState
from tango import AttrQuality

from ska.base.control_model import HealthState


class HealthMonitor:
    """
    HealthMonitor is the health monitor for the MCCS prototype.
    """

    def __init__(self, fqdns, rollup_callback, event_names=None):
        """
        Initialise a new HealthMonitor object
        """
        self._healthstate_table = {}
        self._rollup_callback = rollup_callback
        self._event_names = event_names
        self._initialise_table(fqdns)

    def _initialise_table(self, fqdns):
        # Initialise a table of State and Health with FQDN keys
        print("initialise default table")
        for fqdn in fqdns:
            self._healthstate_table.update(
                {fqdn: {"State": DevState.UNKNOWN, "healthstate": HealthState.OK}}
            )

    def update_health_table(self, fqdn, event, value, quality):
        """
        Callback routine for Event Manager push events

        :param fqdn: fully qualified device name
        :type fqdn: str
        :param event: event name
        :type event: str
        :param value: the value of the attribute event name
        :type value: object
        :param quality: the quality of the event
        :type quality: AttrQuality enum (defined in tango)
        """
        event_dict = self._healthstate_table[fqdn]
        if event == "State":
            event_dict[event] = value
        elif event == "healthstate":
            event_dict[event] = HealthState(value)

        print(self._healthstate_table)
        if self._rollup_callback is not None:
            self._rollup_callback(self._healthstate_table)


class LocalHealthMonitor(HealthMonitor):
    """
    LocalHealthMonitor is the health monitor specifically for ascertaining the
    health state of the current device by aggregating the quality of its attributes.
    """

    def __init__(self, fqdns, rollup_callback, event_names):
        super().__init__(fqdns, rollup_callback, event_names)

    def _initialise_table(self, fqdns):
        """
        Internal routine to initialise the healthstate table

        :param fqdns: a list of fully qualified device names
        :type fqdns: list of str
        """
        print("initialise hardware healthstate table")
        for fqdn in fqdns:
            event_dict = {}
            for name in self._event_names:
                event_dict.update({name: HealthState.OK})
            self._healthstate_table.update({fqdn: event_dict})
        print(self._healthstate_table)

    def update_health_table(self, fqdn, event, value, quality):
        """
        Callback routine for Event Manager push events which converts
        attribute quality into health state according to:
        ATTR_ALARM    -> HealthState.FAILED
        ATTR_WARNING  -> HealthState.DEGRADED
        ATTR_VALID    -> HealthState.OK
        ATTR_CHANGING -> HealthState.UNKNOWN
        ATTR_INVALID  -> HealthState.UNKNOWN

        :param fqdn: fully qualified device name
        :type fqdn: str
        :param event: event name
        :type event: str
        :param value: the value of the attribute event name
        :type value: object
        :param quality: the quality of the event
        :type quality: AttrQuality enum (defined in tango)
        """
        event_dict = self._healthstate_table[fqdn]
        if quality == AttrQuality.ATTR_ALARM:
            event_dict[event] = HealthState.FAILED
        elif quality == AttrQuality.ATTR_WARNING:
            event_dict[event] = HealthState.DEGRADED
        elif quality == AttrQuality.ATTR_VALID:
            event_dict[event] = HealthState.OK
        else:
            event_dict[event] = HealthState.UNKNOWN

        self._rollup_callback(self._healthstate_table)


class RollupPolicy:
    def __init__(self, update_healthstate_callback):
        self._update_healthstate_callback = update_healthstate_callback

    def rollup_health(self, healthstate_table):
        """
        Rollup the health states of an element and its constituent sub-elements
        and push the resultant health state to the enclosing element.
        """
        health_state = HealthState.OK
        for fqdn, event_dict in healthstate_table.items():
            for event, health in event_dict.items():
                if event == "State" and (
                    health == DevState.FAULT or health == DevState.ALARM
                ):
                    health_state = HealthState.FAILED
                elif event == "State":
                    health_state = HealthState.OK
                elif health == HealthState.FAILED:
                    health_state = HealthState.FAILED
                    break
                elif health == HealthState.DEGRADED:
                    health_state = HealthState.DEGRADED
                elif health == HealthState.UNKNOWN and health != HealthState.DEGRADED:
                    health_state = HealthState.UNKNOWN
            if health_state == HealthState.FAILED:
                break
        self._update_healthstate_callback(health_state)
