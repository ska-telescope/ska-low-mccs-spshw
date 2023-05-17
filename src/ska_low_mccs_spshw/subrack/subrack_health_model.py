#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a subrack."""
from __future__ import annotations

from typing import Any, Optional

from ska_control_model import HealthState
from ska_low_mccs_common.health import BaseHealthModel, HealthChangedCallbackProtocol

from .subrack_health_rules import SubrackHealthRules

__all__ = ["SubrackHealthModel"]


class SubrackHealthModel(BaseHealthModel):
    """A health model for a subrack."""

    def __init__(
        self: SubrackHealthModel,
        component_state_changed_callback: HealthChangedCallbackProtocol,
        thresholds: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param component_state_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        :param thresholds: Thresholds for the subrack device.
        """
        self._health_rules = SubrackHealthRules(thresholds)
        super().__init__(component_state_changed_callback)

    def update_state(self: BaseHealthModel, **kwargs: Any) -> None:
        """
        Update this health model with state relevant to evaluating health.

        :param kwargs: updated state
        """
        # linting
        if "new_tpm_voltages" in self._state:
            self._state["old_tpm_voltages"] = self._state["tpm_voltages"]

        # linting
        if "new_power_supply_voltages" in self._state:
            self._state["old_power_supply_voltages"] = self._state[
                "new_power_supply_voltages"
            ]
        # linting
        if "new_tpm_power_states" in self._state:
            self._state["old_tpm_power_states"] = self._state["tpm_power_states"]

        super().update_state(**kwargs)

    # def update_data(
    #     self: SubrackHealthModel,
    #     board_temps: list[float],
    #     backplane_temps: list[float],
    #     subrack_fan_speeds: list[float],
    #     board_currents: list[float],
    #     tpm_currents: list[float],
    #     power_supply_currents: list[float],
    #     tpm_voltages: list[float],
    #     power_supply_voltages: list[float],
    #     tpm_power_states: list[float],
    #     clock_reqs: set,
    #     desired_fan_speeds: list[float],
    # ) -> None:
    #     """
    #     Update the state of the subrack device.

    #     :param board_temps: The board temperatures.
    #     :param backplane_temps: Backplane temperatures.
    #     :param subrack_fan_speeds: Subrack fan speeds
    #     :param board_currents: Currents drawn by all of the boards.
    #     :param tpm_currents: Currents drawn by all of the TPMs.
    #     :param power_supply_currents: Currents drawn by all of the power supplys.
    #     :param tpm_voltages: Voltage used by all TPMs.
    #     :param power_supply_voltages: Voltage used by all power supplies.
    #     :param tpm_power_states: If all the TPMs are on, off or some other state.
    #     :param clock_reqs: Set containing clock requirements.
    #     :param desired_fan_speeds: What the user wants the fan speeds to be.
    #     """
    #     self._state.board_temps = board_temps
    #     self._state.backplane_temps = backplane_temps
    #     self._state.subrack_fan_speeds = subrack_fan_speeds

    #     self._state.new_board_currents = board_currents
    #     self._state.new_tpm_currents = tpm_currents
    #     self._state.new_power_supply_currents = power_supply_currents

    #     # linting
    #     if "new_tpm_voltages" in self._state:
    #         self._state.old_tpm_voltages = self._state.new_tpm_voltages
    #     self._state.new_tpm_voltages = tpm_voltages

    #     # linting
    #     if "new_power_supply_voltages" in self._state:
    #         self._state.old_power_supply_voltages = (
    #             self._state.new_power_supply_voltages
    #         )
    #     self._state.new_power_supply_voltages = power_supply_voltages

    #     # linting
    #     if "new_tpm_power_states" in self._state:
    #         self._state.old_tpm_power_states = self._state.new_tpm_power_states
    #     self._state.new_tpm_power_states = tpm_power_states

    #     self._state.clock_reqs = clock_reqs

    #     self._state.desired_fan_speeds = desired_fan_speeds

    #     self.evaluate_health()

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
            if self._health_rules.rules[health](self._state, subrack_health):
                return health
        return HealthState.UNKNOWN
