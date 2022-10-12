# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for station beams."""
from __future__ import annotations

from typing import Any, Callable, Optional

from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthModel

__all__ = ["StationBeamHealthModel"]


class StationBeamHealthModel(HealthModel):
    """A health model for station beams."""

    def __init__(
        self: StationBeamHealthModel,
        health_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: a callback to be called when the
            health of the station beam (as evaluated by this model)
            changes
        """
        self._beam_health = HealthState.UNKNOWN
        self._station_health: Optional[HealthState] = HealthState.UNKNOWN
        self._station_fault: bool = False

        super().__init__(health_changed_callback)

    def evaluate_health(
        self: StationBeamHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the station beam.

        The overall health is based on the whether the beam is locked or
        not.

        :return: an overall health of the station beam
        """
        super_health = super().evaluate_health()

        station_fault_health = (
            HealthState.FAILED if self._station_fault else HealthState.OK
        )

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
        ]:
            if super_health == health:
                return health
            if self._beam_health == health:
                return health
            if self._station_health == health:
                return health
            if station_fault_health == health:
                return health

        return HealthState.OK

    def is_beam_locked_changed(
        self: StationBeamHealthModel, is_beam_locked: bool
    ) -> None:
        """
        Handle a change in whether the station beam is locked.

        This is a callback hook that is called when whether asubarray
        beam is locked changes.

        :param is_beam_locked: whether the station beam is locked
        """
        self._beam_health = HealthState.OK if is_beam_locked else HealthState.DEGRADED
        self.update_health()

    def station_health_changed(
        self: StationBeamHealthModel, station_health: Optional[HealthState]
    ) -> None:
        """
        Handle a change in the health of the station device that this beam controls.

        This is a callback hook that is called when whether a station
        beam detects that the health of its station has changed. This
        could occur because the station's health changes, or because the
        beam changes station.

        :param station_health: the health of the station that is
            controlled by this beam
        """
        self._station_health = station_health
        self.update_health()

    def station_fault_changed(
        self: StationBeamHealthModel,
        station_fault: bool,
    ) -> None:
        """
        Handle a change in the fault state of the station beam's station device.

        This is a callback hook that is called when whether a station
        beam detects that the fault state of its station has changed.
        This could occur because the station's health changes, or
        because the beam changes station.

        :param station_fault: the fault state of the station that is
            controlled by this beam.
        """
        self._station_fault = station_fault
        self.update_health()
