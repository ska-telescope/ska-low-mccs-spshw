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
        """
        Initialise a table of State and Health with FQDN keys

        :param fqdns: Fully qualified device names of the monitored Tango devices
        :type fqdns: list of str
        """
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

        if self._rollup_callback is not None:
            self._rollup_callback(self._healthstate_table)

    def get_healthstate_table(self):
        """
        Get the health table

        :return: the health table
        """
        return self._healthstate_table


class LocalHealthMonitor(HealthMonitor):
    """
    LocalHealthMonitor is the health monitor specifically for ascertaining the
    health state of the current device by aggregating the quality of its attributes.
    """

    def __init__(self, fqdns, rollup_callback, event_names):
        """
        Initialise a new LocalHealthMonitor object. Should be used
        to obtain the healthstate of devices whose attributes constitute
        the healthstate.

        :param fqdns: a list of fully qualified device names
        :type fqdns: list of str
        :param rollup_callback: a function to aggregate healthstate
        :type rollup_callback: function
        :param event_names: attribute names generating events used that
                            constitute the device healthstate
        :type event_names: list of str

        """
        super().__init__(fqdns, rollup_callback, event_names)

    def _initialise_table(self, fqdns):
        """
        Internal routine to initialise the healthstate table

        :param fqdns: a list of fully qualified device names
        :type fqdns: list of str
        """
        for fqdn in fqdns:
            event_dict = {}
            for name in self._event_names:
                event_dict.update({name: HealthState.OK})
            self._healthstate_table.update({fqdn: event_dict})

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
        event_dict[event] = self.quality_to_healthstate(quality)

        if self._rollup_callback is not None:
            self._rollup_callback(self._healthstate_table)

    def quality_to_healthstate(self, quality):
        """
        Helper function to translate attribute quality to healthstate.

        :param quality: attribute quality
        :type quality: AttrQuality

        :return: HealthState
        """
        quality_healthstate_map = {
            AttrQuality.ATTR_ALARM: HealthState.FAILED,
            AttrQuality.ATTR_WARNING: HealthState.DEGRADED,
            AttrQuality.ATTR_VALID: HealthState.OK,
            AttrQuality.ATTR_CHANGING: HealthState.UNKNOWN,
            AttrQuality.ATTR_INVALID: HealthState.UNKNOWN,
        }
        return quality_healthstate_map[quality]


class HealthRollupPolicy:
    """
    HealthRollupPolicy is a class to aggregate different device healthstates.
    """

    def __init__(self, update_healthstate_callback):
        """
        Initialise the health rollup policy.

        :param update_healthstate_callback: a callback used to set the
            healthstate attribute of the device
        :type update_healthstate_callback: function
        """
        self._update_healthstate_callback = update_healthstate_callback

    def rollup_health(self, healthstate_table):
        """
        Rollup the health states of an element and its constituent sub-elements
        and push the resultant health state to the enclosing element.

        :param healthstate_table: a table containing healthstates to be aggregated.
        :type healthstate_table: dict
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
        if self._update_healthstate_callback is not None:
            self._update_healthstate_callback(health_state)
        return health_state
