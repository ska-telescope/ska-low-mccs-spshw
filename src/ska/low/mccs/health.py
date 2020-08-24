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

import threading

from tango import DevState
from tango import AttrQuality

from ska.base.control_model import HealthState


class HealthMonitor:
    """
    HealthMonitor is the health monitor for the MCCS prototype.
    """

    def __init__(self, device, fqdns):
        """
        Initialise a new HealthMonitor object
        """
        self._health_state_table = {}
        self._device = device
        self._lock = threading.Lock()
        self._initialise_table(fqdns)

    def _initialise_table(self, fqdns):
        # Initialise a table of State and Health with FQDN keys
        print("initialise default table")
        for fqdn in fqdns:
            self._health_state_table.update(
                {fqdn: {"state": DevState.UNKNOWN, "healthstate": HealthState.OK}}
            )

    def update_health_table(self, fqdn, event, value, quality):
        """
        Callback routine for Event Manager push events
        """
        event_dict = self._health_state_table[fqdn]
        if event == "state":
            event_dict[event] = value
        elif event == "healthstate":
            event_dict[event] = HealthState(value)

        self.rollup_health()

    def rollup_health(self):
        """
        Rollup the health states of an element and its constituent sub-elements
        and push the resultant health state to the enclosing element.
        """
        health_state = HealthState.OK
        for fqdn, event_dict in self._health_state_table.items():
            for event, health in event_dict.items():
                if event == "state" and (
                    health == DevState.FAULT or health == DevState.ALARM
                ):
                    health_state = HealthState.FAILED
                elif event == "state":
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

        print(self._health_state_table)
        self._device.push_change_event("healthState", health_state)
        with self._lock:
            self._device._health_state = health_state
        print("health state=", health_state)


class TileHealthMonitor(HealthMonitor):
    """
    TileHealthMonitor is the health monitor specifically for the tile hardware.
    """

    def __init__(self, device, fqdns):
        super().__init__(device, fqdns)

    def _initialise_table(self, fqdns):
        print("initialise tile table")
        for fqdn in fqdns:
            self._health_state_table.update(
                {
                    fqdn: {
                        "current": HealthState.OK,
                        "voltage": HealthState.OK,
                        "board_temperature": HealthState.OK,
                        "fpga1_temperature": HealthState.OK,
                        "fpga2_temperature": HealthState.OK,
                    }
                }
            )

    def update_health_table(self, fqdn, event, value, quality):
        """
        Callback routine for Event Manager push events which converts
        attribute quality into health state.
        """
        print("tile update health table")
        event_dict = self._health_state_table[fqdn]
        if quality == AttrQuality.ATTR_ALARM:
            event_dict[event] = HealthState.FAILED
        elif quality == AttrQuality.ATTR_WARNING:
            event_dict[event] = HealthState.DEGRADED
        elif quality == AttrQuality.ATTR_VALID:
            event_dict[event] = HealthState.OK
        else:
            event_dict[event] = HealthState.UNKNOWN

        self.rollup_health()
