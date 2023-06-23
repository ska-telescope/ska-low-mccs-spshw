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

    def update_data(self: BaseHealthModel, new_states: dict) -> None:
        """
        Update this health model with state relevant to evaluating health.

        :param new_states: New states of the data points.
        """
        if "subrack_state_points" not in self._state:
            self._state["subrack_state_points"] = {}  # type: ignore

        assert isinstance(self._state["subrack_state_points"], dict)

        state_points = self._state.get("subrack_state_points", {})
        # set the old_value to the previous value if exists otherwise have it match new
        if state_points.get("tpm_voltages"):
            self._state["subrack_state_points"]["old_tpm_voltages"] = state_points.get(
                "tpm_voltages"
            )
        else:
            self._state["subrack_state_points"]["old_tpm_voltages"] = new_states.get(
                "tpm_voltages"
            )

        # set the old_value to the previous value if exists otherwise have it match new
        if state_points.get("power_supply_voltages"):
            self._state["subrack_state_points"][
                "old_power_supply_voltages"
            ] = state_points.get("power_supply_voltages")
        else:
            self._state["subrack_state_points"][
                "old_power_supply_voltages"
            ] = new_states.get("power_supply_voltages")

        # set the old_value to the previous value if exists otherwise have it match new
        if state_points.get("tpm_power_states"):
            self._state["subrack_state_points"][
                "old_tpm_power_states"
            ] = state_points.get("tpm_power_states")
        else:
            self._state["subrack_state_points"][
                "old_tpm_power_states"
            ] = new_states.get("tpm_power_states")

        self._state["subrack_state_points"] = (
            self._state["subrack_state_points"] | new_states
        )

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
