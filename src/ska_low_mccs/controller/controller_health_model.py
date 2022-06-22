# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a controller."""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from ska_tango_base.control_model import HealthState

from ska_low_mccs.health import HealthModel

__all__ = ["ControllerHealthModel"]


class ControllerHealthModel(HealthModel):
    """A health model for a controller."""

    def __init__(
        self: ControllerHealthModel,
        station_fqdns: Sequence[str],
        subrack_fqdns: Sequence[str],
        subarray_beam_fqdns: Sequence[str],
        station_beam_fqdns: Sequence[str],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param station_fqdns: the FQDNs of this controller's stations
        :param subrack_fqdns: the FQDNs of this controller's subracks
        :param subarray_beam_fqdns: the FQDNs of this controller's
            subarray beams
        :param station_beam_fqdns: the FQDNs of this controller's
            station beams
        :param component_state_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        """
        self._station_health: dict[str, Optional[HealthState]] = {
            station_fqdn: HealthState.UNKNOWN for station_fqdn in station_fqdns
        }
        self._subrack_health: dict[str, Optional[HealthState]] = {
            subrack_fqdn: HealthState.UNKNOWN for subrack_fqdn in subrack_fqdns
        }
        self._subarray_beam_health: dict[str, Optional[HealthState]] = {
            subarray_beam_fqdn: HealthState.UNKNOWN
            for subarray_beam_fqdn in subarray_beam_fqdns
        }
        self._station_beam_health: dict[str, Optional[HealthState]] = {
            station_beam_fqdn: HealthState.UNKNOWN
            for station_beam_fqdn in station_beam_fqdns
        }
        super().__init__(component_state_changed_callback)

    def station_health_changed(
        self: ControllerHealthModel,
        station_fqdn: str,
        station_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in station health.

        :param station_fqdn: the FQDN of the station whose health has
            changed
        :param station_health: the health state of the specified
            station, or None if the station's admin mode indicates that
            its health should not be rolled up.
        """
        if self._station_health.get(station_fqdn) != station_health:
            self._station_health[station_fqdn] = station_health
            self.update_health()

    def subrack_health_changed(
        self: ControllerHealthModel,
        subrack_fqdn: str,
        subrack_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in subrack health.

        :param subrack_fqdn: the FQDN of the subrack whose health has changed
        :param subrack_health: the health state of the specified subrack, or
            None if the subrack's admin mode indicates that its health
            should not be rolled up.
        """
        if self._subrack_health.get(subrack_fqdn) != subrack_health:
            self._subrack_health[subrack_fqdn] = subrack_health
            self.update_health()

    def subarray_beam_health_changed(
        self: ControllerHealthModel,
        subarray_beam_fqdn: str,
        subarray_beam_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in subarray beam health.

        :param subarray_beam_fqdn: the FQDN of the subarray beam whose
            health has changed
        :param subarray_beam_health: the health state of the specified
            subarray beam, or None if the subarray beam's admin mode
            indicates that its health should not be rolled up.
        """
        print(f"XXXX updating SubarrayBeam health {subarray_beam_fqdn}->{subarray_beam_health}")
        if self._subarray_beam_health.get(subarray_beam_fqdn) != subarray_beam_health:
            self._subarray_beam_health[subarray_beam_fqdn] = subarray_beam_health
            self.update_health()
        print(f"XXXX subarray beam healths: {self._subarray_beam_health}")

    def station_beam_health_changed(
        self: ControllerHealthModel,
        station_beam_fqdn: str,
        station_beam_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in station beam health.

        :param station_beam_fqdn: the FQDN of the station beam whose
            health has changed
        :param station_beam_health: the health state of the specified
            station beam, or None if the station beam's admin mode
            indicates that its health should not be rolled up.
        """
        if self._station_beam_health.get(station_beam_fqdn) != station_beam_health:
            self._station_beam_health[station_beam_fqdn] = station_beam_health
            self.update_health()

    def evaluate_health(
        self: ControllerHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the controller.

        The overall health is based on the fault and communication
        status of the controller overall, together with the health of the
        APIU, stations and subracks that it manages.

        This implementation simply sets the health of the controller to the
        health of its least healthy component.

        :return: an overall health of the controller
        """
        controller_health = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
        ]:
            if controller_health == health:
                print(f"XXX controller health is {health}")
                return health
            if health in self._station_health.values():
                print(f"XXX station health is {health}")
                return health
            if health in self._subrack_health.values():
                print(f"XXX subrack health is {health}")
                return health
            if health in self._subarray_beam_health.values():
                print(f"XXX subarray beam health is {health}")
                return health
            if health in self._station_beam_health.values():
                print(f"XXX station beam health is {health}")
                return health
        return HealthState.OK
