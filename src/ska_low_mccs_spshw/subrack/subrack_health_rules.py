#  -*- coding: utf-8 -*
# pylint: disable=arguments-differ
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A file to store health transition rules for subrack."""
from __future__ import annotations

from typing import Any

import numpy as np
from ska_control_model import HealthState, PowerState
from ska_low_mccs_common.health import HealthRules

DEGRADED_STATES = frozenset({HealthState.DEGRADED, HealthState.FAILED, None})


class SubrackHealthRules(HealthRules):
    """A class to handle transition rules for subrack."""

    def _check_basic_thresholds(
        self: SubrackHealthRules,
        board_temps: list[float],
        backplane_temps: list[float],
        rule_str: str,
    ) -> bool:
        """
        Check the thresholds of values that are simple boundaries.

        :param board_temps: The temperatures of the boards.
        :param backplane_temps: The temperatures of the backplane sensors.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached.
        """
        for temp in board_temps:
            if (
                temp > self._thresholds[f"{rule_str}max_board_temp"]
                or temp < self._thresholds[f"{rule_str}min_board_temp"]
            ):
                return True
        for temp in backplane_temps:
            if (
                temp > self._thresholds[f"{rule_str}max_backplane_temp"]
                or temp < self._thresholds[f"{rule_str}min_backplane_temp"]
            ):
                return True

        return False

    def _check_fan_speeds(
        self: SubrackHealthRules,
        fan_speeds: list[float],
        desired_fan_speeds: list[float],
        rule_str: str,
    ) -> bool:
        """
        Check the fan speeds.

        :param fan_speeds: The speeds of the fans.
        :param desired_fan_speeds: The desired speeds of the fans.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached.
        """
        for fan_speed in fan_speeds[0:2]:
            if (
                abs(fan_speed - desired_fan_speeds[1])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
                or fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]
            ):
                return True
        for fan_speed in fan_speeds[2:4]:
            if (
                abs(fan_speed - desired_fan_speeds[2])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
                or fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]
            ):
                return True
        return False

    # pylint: disable=too-many-arguments
    def _check_voltage_drops(
        self: SubrackHealthRules,
        old_tpm_volts: list[float],
        tpm_volts: list[float],
        old_power_supply_volts: list[float],
        power_supply_volts: list[float],
        rule_str: str,
    ) -> bool:
        """
        Check the drop in voltage across the tpms.

        :param old_tpm_volts: The old voltages of the tpms.
        :param tpm_volts: The new voltages of the tpms.
        :param old_power_supply_volts: The old voltages of the power supplies.
        :param power_supply_volts: The voltages of the power supplies.
        :param rule_str: The type of error threshold to be checking against.
        :return: True if any of the thresholds are breached.
        """
        tpm_vol_drop = sum(np.subtract(old_tpm_volts, tpm_volts))

        power_sup_vol_drop = sum(
            np.subtract(old_power_supply_volts, power_supply_volts)
        )

        return (tpm_vol_drop - power_sup_vol_drop) > self._thresholds[
            f"{rule_str}voltage_drop"
        ]

    def _check_current_diff(
        self: SubrackHealthRules,
        tpm_currents: list[float],
        board_currents: list[float],
        power_supply_currents: list[float],
        rule_str: str,
    ) -> bool:
        """
        Check the difference in current across all devices in the subrack.

        This makes sure that all the currents are adding up to give
        rougly the same value and we're not losing power somewhere.

        :param tpm_currents: The currents of the tpms.
        :param board_currents: The currents of the boards.
        :param power_supply_currents: The currents of the power supplies.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached.
        """
        total_current = sum(tpm_currents) + sum(board_currents)
        if (
            abs(sum(power_supply_currents) - total_current)
            > self._thresholds[f"{rule_str}max_current_diff"]
        ):
            return True
        return False

    def _check_powers(
        self: SubrackHealthRules,
        tpm_power_states: list[float],
        tpm_voltages: list[float],
        tpm_currents: list[float],
        rule_str: str,
    ) -> bool:
        """
        Check the voltages and currents for tpms are within thresholds.

        :param tpm_power_states: List of the power states of the tpms.
        :param tpm_voltages: The voltages of the tpms.
        :param tpm_currents: The currents of the tpms.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached.
        """
        if (
            len(tpm_voltages) == 0
            or len(tpm_currents) == 0
            or len(tpm_power_states) == 0
        ):
            return False
        for i, power_state in enumerate(tpm_power_states):
            if power_state == PowerState.ON and (
                tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_on"]
                or tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_on"]
            ):
                return True
            if power_state == PowerState.STANDBY and (
                tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_standby"]
                or tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_standby"]
            ):
                return True
            if power_state in [PowerState.OFF, PowerState.NO_SUPPLY] and (
                tpm_voltages[i] > 0 or tpm_currents[i] > 0
            ):
                return True
        return False

    def unknown_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
        subrack_health: HealthState,
    ) -> bool:
        """
        Test whether UNKNOWN is valid for the subrack.

        :param state_dict: The current state of the subrack.
        :param subrack_health: The health state of the subrack.

        :return: True if UNKNOWN is a valid state
        """
        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return True

        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        if subrack_health == HealthState.UNKNOWN:
            return True
        for i, power_state in enumerate(state["tpm_power_states"]):
            if power_state == PowerState.UNKNOWN:
                return True
        return False

    # pylint: disable=too-many-boolean-expressions
    def failed_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
        subrack_health: HealthState,
    ) -> bool:
        """
        Test whether FAILED is valid for the subrack.

        :param state_dict: The current state of the subrack.
        :param subrack_health: The health state of the subrack.

        :return: True if FAILED is a valid state
        """
        fail_str = "failed_"

        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return False
        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        if (
            subrack_health == HealthState.FAILED
            or (
                state["old_tpm_power_states"] != state["tpm_power_states"]
                and self._check_voltage_drops(
                    state["old_tpm_voltages"],
                    state["tpm_voltages"],
                    state["old_power_supply_voltages"],
                    state["power_supply_voltages"],
                    fail_str,
                )
            )
            or self._check_powers(
                state["tpm_power_states"],
                state["tpm_voltages"],
                state["tpm_currents"],
                fail_str,
            )
            or self._check_basic_thresholds(
                state["board_temps"], state["backplane_temps"], fail_str
            )
            or self._check_fan_speeds(
                state["subrack_fan_speeds"], state["desired_fan_speeds"], fail_str
            )
            or self._check_current_diff(
                state["tpm_currents"],
                state["board_currents"],
                state["power_supply_currents"],
                fail_str,
            )
        ):
            return True

        if not all(
            x in state["clock_reqs"] for x in ["10MHz", "1PPS", "10_MHz_PLL_lock"]
        ):
            return True

        return False

    # pylint: disable=too-many-boolean-expressions
    def degraded_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
        subrack_health: HealthState,
    ) -> bool:
        """
        Test whether DEGRADED is valid for the subrack.

        :param state_dict: The current state of the subrack.
        :param subrack_health: The health state of the subrack.

        :return: True if DEGRADED is a valid state
        """
        fail_str = "degraded_"

        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return False
        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        if (
            subrack_health == HealthState.DEGRADED
            or (
                state["old_tpm_power_states"] != state["tpm_power_states"]
                and self._check_voltage_drops(
                    state["old_tpm_voltages"],
                    state["tpm_voltages"],
                    state["old_power_supply_voltages"],
                    state["power_supply_voltages"],
                    fail_str,
                )
            )
            or self._check_powers(
                state["tpm_power_states"],
                state["tpm_voltages"],
                state["tpm_currents"],
                fail_str,
            )
            or self._check_basic_thresholds(
                state["board_temps"], state["backplane_temps"], fail_str
            )
            or self._check_fan_speeds(
                state["subrack_fan_speeds"], state["desired_fan_speeds"], fail_str
            )
            or self._check_current_diff(
                state["tpm_currents"],
                state["board_currents"],
                state["power_supply_currents"],
                fail_str,
            )
        ):
            return True

        return False

    def healthy_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
        subrack_health: HealthState,
    ) -> bool:
        """
        Test whether OK is valid for the subrack.

        :param state_dict: The current state of the subrack.
        :param subrack_health: The health state of the subrack.

        :return: True if OK is a valid state
        """
        # Not sure what I should be measuring against here...
        return True

    @property
    def default_thresholds(self: HealthRules) -> dict[str, float]:
        """
        Get the default thresholds for this device.

        :return: the default thresholds
        """
        # no idea where to get these values from lol
        # TODO NEED to get these actual values from somewhere
        return {
            "failed_max_board_temp": 70.0,
            "degraded_max_board_temp": 60.0,
            "failed_min_board_temp": 10.0,
            "degraded_min_board_temp": 20.0,
            "failed_max_backplane_temp": 70.0,
            "degraded_max_backplane_temp": 60.0,
            "failed_min_backplane_temp": 10.0,
            "degraded_min_backplane_temp": 20.0,
            "failed_fan_speed_diff": 10.0,
            "degraded_fan_speed_diff": 5.0,
            "failed_min_fan_speed": 20.0,
            "degraded_min_fan_speed": 30.0,
            "failed_voltage_drop": 5.0,
            "degraded_voltage_drop": 3.0,
            "failed_max_current_diff": 2.0,
            "degraded_max_current_diff": 1.0,
            "failed_tpm_voltage_on": 8.0,
            "degraded_tpm_voltage_on": 6.0,
            "failed_tpm_current_on": 6.0,
            "degraded_tpm_current_on": 5.0,
            "failed_tpm_voltage_standby": 5.0,
            "degraded_tpm_voltage_standby": 4.0,
            "failed_tpm_current_standby": 4.0,
            "degraded_tpm_current_standby": 3.0,
        }
