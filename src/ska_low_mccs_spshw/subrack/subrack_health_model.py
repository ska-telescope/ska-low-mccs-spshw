#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a subrack."""
from __future__ import annotations

from typing import Any, Callable

from ska_control_model import HealthState
from ska_low_mccs_common.health import BaseHealthModel

__all__ = ["SubrackHealthModel"]


class SubrackHealthModel(BaseHealthModel):
    """A health model for a subrack."""

    def __init__(
        self: SubrackHealthModel,
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        tpm_voltages: list[float],
        power_supply_voltages: list[float],
        tpm_power_states: list[float],
        clock_reqs: set,
    ) -> None:
        """
        Initialise a new instance.

        :param component_state_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        :param station_fqdns: the FQDNs of this subrack's stations
        """
        super().__init__(component_state_changed_callback)

        self._board_temps = board_temps
        self._backplane_temps = backplane_temps
        self._subrack_fan_speeds = subrack_fan_speeds

        self._new_board_currents = board_currents
        self._new_tpm_currents = tpm_currents
        self._new_power_supply_currents = power_supply_currents

        self._old_tpm_voltages = tpm_voltages
        self._new_tpm_voltages = tpm_voltages
        self._old_power_supply_voltages = power_supply_voltages
        self._new_power_supply_voltages = power_supply_voltages

        self._old_tpm_power_states = tpm_power_states
        self._new_tpm_power_states = tpm_power_states

        self._desired_fan_speeds = []

        self._clock_reqs = clock_reqs

    def update_data(
        self: SubrackHealthModel,
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        tpm_voltages: list[float],
        power_supply_voltages: list[float],
        tpm_power_states: list[float],
        clock_reqs: set,
        desired_fan_speeds: list[float],
    ) -> None:
        self._board_temps = board_temps
        self._backplane_temps = backplane_temps
        self._subrack_fan_speeds = subrack_fan_speeds

        self._new_board_currents = board_currents
        self._new_tpm_currents = tpm_currents
        self._new_power_supply_currents = power_supply_currents

        self._old_tpm_voltages = self._new_tpm_voltages
        self._new_tpm_voltages = tpm_voltages
        self._old_power_supply_voltages = self._new_power_supply_voltages
        self._new_power_supply_voltages = power_supply_voltages

        self._old_tpm_power_states = self._new_tpm_power_states
        self._new_tpm_power_states = tpm_power_states

        self._clock_reqs = clock_reqs

        self._desired_fan_speeds = desired_fan_speeds

        self.evaluate_health()

    def evaluate_health(
        self: SubrackHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the subrack.

        The overall health is based on the fault and communication
        status of the subrack overall, together with the health of the
        tpms that it manages.

        This implementation simply sets the health of the subrack to the
        health of its least healthy component.

        :return: an overall health of the subrack
        """
        subrack_health = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]:
            if (
                self._health_rules.rules[health](
                    self._board_temps,
                    self._backplane_temps,
                    self._subrack_fan_speeds,
                    self._new_board_currents,
                    self._new_tpm_currents,
                    self._new_power_supply_currents,
                    self._old_tpm_voltages,
                    self._new_tpm_voltages,
                    self._old_power_supply_voltages,
                    self._new_power_supply_voltages,
                    self._old_tpm_power_states,
                    self._new_tpm_power_states,
                    self._clock_reqs,
                    self._desired_fan_speeds,
                )
                or subrack_health == health
            ):
                return health
        return HealthState.UNKNOWN
