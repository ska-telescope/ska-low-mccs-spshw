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
    ):
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
    ):
        for fan_speed in fan_speeds[0, 1]:
            if (
                abs(fan_speed - desired_fan_speeds[1])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
                or fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]
            ):
                return True
        for fan_speed in fan_speeds[2, 3]:
            if (
                abs(fan_speed - desired_fan_speeds[2])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
                or fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]
            ):
                return True
        return False

    def _check_voltage_drops(
        self: SubrackHealthRules,
        old_tpm_volts: list[float],
        tpm_volts: list[float],
        old_power_supply_volts: list[float],
        power_supply_volts: list[float],
        rule_str: str,
    ) -> bool:
        tpm_vol_drop = sum(old_tpm_volts - tpm_volts)
        power_sup_vol_drop = sum(old_power_supply_volts - power_supply_volts)

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
        total_current = sum(tpm_currents) + sum(board_currents)
        if (
            abs(sum(power_supply_currents) - total_current)
            > self._thresholds[f"{rule_str}max_current_diff"]
        ):
            return True

    def _check_powers(
        self: SubrackHealthRules,
        tpm_power_states: list[float],
        tpm_voltages: list[float],
        tpm_currents: list[float],
        rule_str: str,
    ) -> bool:
        for i, power_state in enumerate(tpm_power_states):
            if power_state == PowerState.ON:
                if tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_on"]:
                    return True
                if tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_on"]:
                    return True
            if power_state == PowerState.STANDBY:
                if tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_standby"]:
                    return True
                if tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_standby"]:
                    return True
            if power_state in [PowerState.OFF, PowerState.NO_SUPPLY]:
                if tpm_voltages[i] > 0:
                    return True
                if tpm_currents[i] > 0:
                    return True

    def unknown_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        old_tpm_voltages: list[float],
        tpm_voltages: list[float],
        old_power_supply_voltages: list[float],
        power_supply_voltages: list[float],
        old_tpm_power_states: list[float],
        tpm_power_states: list[float],
        clocks_reqs: set,
        desired_fan_speeds: list[float],
    ) -> bool:
        """
        Test whether UNKNOWN is valid for the subrack.

        :return: True if UNKNOWN is a valid state
        """
        for i, power_state in enumerate(tpm_power_states):
            if power_state == PowerState.UNKNOWN:
                return True

    def failed_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        old_tpm_voltages: list[float],
        tpm_voltages: list[float],
        old_power_supply_voltages: list[float],
        power_supply_voltages: list[float],
        old_tpm_power_states: list[float],
        tpm_power_states: list[float],
        clocks_reqs: set,
        desired_fan_speeds: list[float],
    ) -> bool:
        """
        Test whether FAILED is valid for the subrack.

        :return: True if FAILED is a valid state
        """
        fail_str = "failed_"

        if old_tpm_power_states != tpm_power_states and self._check_voltage_drops(
            old_tpm_voltages,
            tpm_voltages,
            old_power_supply_voltages,
            power_supply_voltages,
            fail_str,
        ):
            return True

        if self._check_powers(tpm_power_states, tpm_voltages, tpm_currents, fail_str):
            return True

        if self._check_basic_thresholds(board_temps, backplane_temps, fail_str):
            return True

        if self._check_fan_speeds(subrack_fan_speeds, desired_fan_speeds, fail_str):
            return True

        if self._check_current_diff(
            tpm_currents, board_currents, power_supply_currents, fail_str
        ):
            return True

        if not all(x in clocks_reqs for x in ["10MHz", "1PPS", "10_MHz_PLL_lock"]):
            return True

        return False

    def degraded_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        old_tpm_voltages: list[float],
        tpm_voltages: list[float],
        old_power_supply_voltages: list[float],
        power_supply_voltages: list[float],
        old_tpm_power_states: list[float],
        tpm_power_states: list[float],
        clocks_reqs: set,
        desired_fan_speeds: list[float],
    ) -> bool:
        """
        Test whether DEGRADED is valid for the subrack.

        :return: True if DEGRADED is a valid state
        """
        fail_str = "degraded_"

        if old_tpm_power_states != tpm_power_states and self._check_voltage_drops(
            old_tpm_voltages,
            tpm_voltages,
            old_power_supply_voltages,
            power_supply_voltages,
            fail_str,
        ):
            return True

        if self._check_powers(tpm_power_states, tpm_voltages, tpm_currents, fail_str):
            return True

        if self._check_basic_thresholds(board_temps, backplane_temps, fail_str):
            return True

        if self._check_fan_speeds(subrack_fan_speeds, desired_fan_speeds, fail_str):
            return True

        if self._check_current_diff(
            tpm_currents, board_currents, power_supply_currents, fail_str
        ):
            return True

        return False

    def healthy_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        board_temps: list[float],
        backplane_temps: list[float],
        subrack_fan_speeds: list[float],
        board_currents: list[float],
        tpm_currents: list[float],
        power_supply_currents: list[float],
        old_tpm_voltages: list[float],
        tpm_voltages: list[float],
        old_power_supply_voltages: list[float],
        power_supply_voltages: list[float],
        old_tpm_power_states: list[float],
        tpm_power_states: list[float],
        clocks_reqs: set,
        desired_fan_speeds: list[float],
    ) -> bool:
        """
        Test whether OK is valid for the subrack.

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
        return {
            "failed_max_board_temp": 0.0,
            "failed_min_board_temp": 0.0,
            "degraded_max_board_temp": 0.0,
            "degraded_min_board_temp": 0.0,
            "failed_max_backplane_temp": 0.0,
            "degraded_max_backplane_temp": 0.0,
            "failed_min_backplane_temp": 0.0,
            "degraded_min_backplane_temp": 0.0,
            "failed_fan_speed_diff": 0.0,
            "failed_min_fan_speed": 0.0,
            "degraded_fan_speed_diff": 0.0,
            "degraded_min_fan_speed": 0.0,
            "failed_voltage_drop": 0.0,
            "degraded_voltage_drop": 0.0,
            "failed_max_current_diff": 0.0,
            "degraded_max_current_diff": 0.0,
            "failed_tpm_voltage_on": 0.0,
            "degraded_tpm_voltage_on": 0.0,
            "failed_tpm_current_on": 0.0,
            "degraded_tpm_current_on": 0.0,
            "failed_tpm_voltage_standby": 0.0,
            "degraded_tpm_voltage_standby": 0.0,
            "failed_tpm_current_standby": 0.0,
            "degraded_tpm_current_standby": 0.0,
        }


# All these attributes are relevanto for health, but not in a simple way.
# DONE - Board and backplane temperature are simple: warning and fault thresholds.

# For fan speed, these should be a minimum RPM level, depending on the
# commanded percentage level (which in automatic mode depends on the number of TPM).
# Note that the commanded level is the same for fans 1&2 and 3&4, the actual RPM is independent for the 4 fans.

# Board current and voltage depends on whether the TPM has been turned on.

# Total (power supply) current should be the sum of the board currents,
# plus something depending on fan speeds, plus some margin from the backplane and management board (few 10W).
# When a TPM is turned on, the voltage drop across the power connector should be measured.
# This is the difference between the value measured by the subrack and that measured inside the TPM.
# If the drop is significant (0.1-0.2V?) this could cause the connector to burn, as we have ~8A flowing through.
# There should be some further parameters related to the clock: presence of 10MHz and 1PPS, 10 MHz PLL lock.
