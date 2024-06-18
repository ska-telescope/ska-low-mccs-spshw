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

from typing import Any, Optional

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
    ) -> tuple[bool, str]:
        """
        Check the thresholds of values that are simple boundaries.

        :param board_temps: The temperatures of the boards.
        :param backplane_temps: The temperatures of the backplane sensors.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached, along with a text report.
        """
        has_failed = False
        report = ""
        for sensor_no, temp in enumerate(board_temps):
            if temp > self._thresholds[f"{rule_str}max_board_temp"]:
                has_failed = True
                report += (
                    f"Sensor {sensor_no} temp {temp} greater than {rule_str}"
                    f"max_board_temp {self._thresholds[f'{rule_str}max_board_temp']}. "
                )
            if temp < self._thresholds[f"{rule_str}min_board_temp"]:
                has_failed = True
                report += (
                    f"Sensor {sensor_no} temp {temp} less than {rule_str}"
                    f"min_board_temp {self._thresholds[f'{rule_str}min_board_temp']}. "
                )
        for sensor_no, temp in enumerate(backplane_temps):
            if temp > self._thresholds[f"{rule_str}max_backplane_temp"]:
                has_failed = True
                report += (
                    f"Sensor {sensor_no} temp {temp} greater than {rule_str}"
                    "max_backplane_temp "
                    f"{self._thresholds[f'{rule_str}max_backplane_temp']}. "
                )
            if temp < self._thresholds[f"{rule_str}min_backplane_temp"]:
                has_failed = True
                report += (
                    f"Sensor {sensor_no} temp {temp} less than {rule_str}"
                    "min_backplane_temp "
                    f"{self._thresholds[f'{rule_str}min_backplane_temp']}. "
                )
        return has_failed, report

    def _check_fan_speeds(
        self: SubrackHealthRules,
        fan_speeds: list[float],
        desired_fan_speeds: Optional[list[float]],
        rule_str: str,
    ) -> tuple[bool, str]:
        """
        Check the fan speeds.

        :param fan_speeds: The speeds of the fans.
        :param desired_fan_speeds: The desired speeds of the fans, None if not set yet.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached, along with a text report.
        """
        has_failed = False
        report = ""

        for fan_speed in fan_speeds[0:2]:
            if (
                desired_fan_speeds is not None
                and abs(fan_speed - desired_fan_speeds[1])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
            ):
                has_failed = True
                report += (
                    f"Speed diff {fan_speed} - {desired_fan_speeds[1]} = "
                    f"{abs(fan_speed - desired_fan_speeds[1])} not within threshold "
                    f"{self._thresholds[f'{rule_str}fan_speed_diff']}. "
                )
            if fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]:
                has_failed = True
                report += (
                    f"Fan speed {fan_speed} is below {rule_str}min_fan_speed "
                    f"{self._thresholds[f'{rule_str}min_fan_speed']}. "
                )

        for fan_speed in fan_speeds[2:4]:
            if (
                desired_fan_speeds is not None
                and abs(fan_speed - desired_fan_speeds[2])
                > self._thresholds[f"{rule_str}fan_speed_diff"]
            ):
                has_failed = True
                report += (
                    f"Speed diff abs({fan_speed} - {desired_fan_speeds[2]}) = "
                    f"{abs(fan_speed - desired_fan_speeds[2])} not within threshold "
                    f"{self._thresholds[f'{rule_str}fan_speed_diff']}. "
                )
            if fan_speed < self._thresholds[f"{rule_str}min_fan_speed"]:
                has_failed = True
                report += (
                    f"Fan speed {fan_speed} is below {rule_str}min_fan_speed "
                    f"{self._thresholds[f'{rule_str}min_fan_speed']}. "
                )
        return has_failed, report

    # pylint: disable=too-many-arguments
    def _check_voltage_drops(
        self: SubrackHealthRules,
        old_tpm_volts: list[float],
        tpm_volts: list[float],
        old_power_supply_volts: list[float],
        power_supply_volts: list[float],
        rule_str: str,
    ) -> tuple[bool, str]:
        """
        Check the drop in voltage across the tpms.

        :param old_tpm_volts: The old voltages of the tpms.
        :param tpm_volts: The new voltages of the tpms.
        :param old_power_supply_volts: The old voltages of the power supplies.
        :param power_supply_volts: The voltages of the power supplies.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached, along with a text report.
        """
        if (
            len(old_tpm_volts) == 0
            or len(tpm_volts) == 0
            or old_tpm_volts is None
            or tpm_volts is None
        ):
            return (
                False,
                f"One of {old_tpm_volts}, {tpm_volts} is empty. ",
            )
        tpm_vol_drop = sum(np.subtract(old_tpm_volts, tpm_volts))

        power_sup_vol_drop = sum(
            np.subtract(old_power_supply_volts, power_supply_volts)
        )

        if (tpm_vol_drop - power_sup_vol_drop) > self._thresholds[
            f"{rule_str}voltage_drop"
        ]:
            return (
                True,
                f"Voltage drop {tpm_vol_drop} - {power_sup_vol_drop} = "
                f"{tpm_vol_drop - power_sup_vol_drop} is above threshold "
                f"{self._thresholds[f'{rule_str}voltage_drop']}. ",
            )
        return False, ""

    def _check_current_diff(
        self: SubrackHealthRules,
        tpm_currents: list[float],
        board_currents: list[float],
        power_supply_currents: list[float],
        rule_str: str,
    ) -> tuple[bool, str]:
        """
        Check the difference in current across all devices in the subrack.

        This makes sure that all the currents are adding up to give
        rougly the same value and we're not losing power somewhere.

        :param tpm_currents: The currents of the tpms.
        :param board_currents: The currents of the boards.
        :param power_supply_currents: The currents of the power supplies.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached, along with a text report.
        """
        total_current = sum(tpm_currents) + sum(board_currents)
        if (
            abs(sum(power_supply_currents) - total_current)
            > self._thresholds[f"{rule_str}max_current_diff"]
        ):
            return (
                True,
                f"For power supply currents {power_supply_currents}, the sum "
                f"{sum(power_supply_currents)} differ from the total current "
                f"{total_current} by more than "
                f"{self._thresholds[f'{rule_str}max_current_diff']}. ",
            )
        return False, ""

    def _check_powers(
        self: SubrackHealthRules,
        tpm_power_states: list[float],
        tpm_voltages: list[float],
        tpm_currents: list[float],
        tpm_present: list[bool],
        rule_str: str,
    ) -> tuple[bool, str]:
        """
        Check the voltages and currents for tpms are within thresholds.

        :param tpm_power_states: List of the power states of the tpms.
        :param tpm_voltages: The voltages of the tpms.
        :param tpm_currents: The currents of the tpms.
        :param tpm_present: List of whether a tpm is present.
        :param rule_str: The type of error threshold to be checking against.

        :return: True if any of the thresholds are breached, along with a text report.
        """
        has_failed = False
        report = ""
        if (
            len(tpm_voltages) == 0
            or len(tpm_currents) == 0
            or len(tpm_power_states) == 0
        ):
            return (
                False,
                f"One of {tpm_voltages}, {tpm_currents}, {tpm_power_states} is empty. ",
            )
        for i, power_state in enumerate(tpm_power_states):
            if tpm_voltages[i] is None or tpm_currents[i] is None or not tpm_present[i]:
                continue  # may happen
            if power_state == PowerState.ON and (
                tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_on"]
            ):
                has_failed = True
                report += (
                    f"TPM {i} ON voltage too high {tpm_voltages[i]} > "
                    f"{self._thresholds[f'{rule_str}tpm_voltage_on']}. "
                )
            if power_state == PowerState.ON and (
                tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_on"]
            ):
                has_failed = True
                report += (
                    f"TPM {i} ON current too high {tpm_currents[i]} > "
                    f"{self._thresholds[f'{rule_str}tpm_current_on']}. "
                )
            if power_state == PowerState.STANDBY and (
                tpm_voltages[i] > self._thresholds[f"{rule_str}tpm_voltage_standby"]
            ):
                has_failed = True
                report += (
                    f"TPM {i} STANDBY voltage too high {tpm_voltages[i]} > "
                    f"{self._thresholds[f'{rule_str}tpm_voltage_standby']}. "
                )
            if power_state == PowerState.STANDBY and (
                tpm_currents[i] > self._thresholds[f"{rule_str}tpm_current_standby"]
            ):
                has_failed = True
                report += (
                    f"TPM {i} STANDBY current too high {tpm_currents[i]} > "
                    f"{self._thresholds[f'{rule_str}tpm_current_standby']}. "
                )
            if power_state in [PowerState.OFF, PowerState.NO_SUPPLY] and (
                tpm_voltages[i] > 0 or tpm_currents[i] > 0
            ):
                has_failed = True
                report += (
                    f"TPM {i} PowerState is {power_state} but voltage is "
                    f"{tpm_voltages[i]} and current {tpm_currents[i]}. "
                )
        return has_failed, report

    def unknown_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether UNKNOWN is valid for the subrack.

        :param state_dict: The current state of the subrack.

        :return: True if UNKNOWN is a valid state, along with a text report.
        """
        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return True, "Failed to read subrack state"

        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        for i, power_state in enumerate(state["tpm_power_states"]):
            if power_state == PowerState.UNKNOWN:
                return True, f"TPM {i} power state is UNKNOWN"
        return False, ""

    # pylint: disable=too-many-locals
    def failed_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether FAILED is valid for the subrack.

        :param state_dict: The current state of the subrack.

        :return: True if FAILED is a valid state, along with a text report.
        """
        fail_str = "failed_"
        has_failed = False
        report = ""

        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return False, ""
        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        voltage_failed, voltage_report = self._check_voltage_drops(
            state["old_tpm_voltages"],
            state["tpm_voltages"],
            state["old_power_supply_voltages"],
            state["power_supply_voltages"],
            fail_str,
        )

        if (
            voltage_failed
            and state["old_tpm_power_states"] != state["tpm_power_states"]
        ):
            has_failed = True
            report += voltage_report
        power_failed, power_report = self._check_powers(
            state["tpm_power_states"],
            state["tpm_voltages"],
            state["tpm_currents"],
            state["tpm_present"],
            fail_str,
        )

        if power_failed:
            has_failed = True
            report += power_report
        basic_thresholds_failed, basic_report = self._check_basic_thresholds(
            state["board_temps"], state["backplane_temps"], fail_str
        )
        if basic_thresholds_failed:
            has_failed = True
            report += basic_report
        fan_failed, fan_report = self._check_fan_speeds(
            state["subrack_fan_speeds"], state["desired_fan_speeds"], fail_str
        )

        if fan_failed:
            has_failed = True
            report += fan_report
        current_failed, current_report = self._check_current_diff(
            state["tpm_currents"],
            state["board_currents"],
            state["power_supply_currents"],
            fail_str,
        )

        if current_failed:
            has_failed = True
            report += current_report
        if not all(
            x in state["clock_reqs"]
            for x in self._thresholds["clock_presence"]  # type: ignore
        ):
            has_failed = True
            report += (
                f"clock_reqs {state['clock_reqs']} does not match thresholds "
                f"{self._thresholds['clock_presence']}. "
            )

        return has_failed, report

    # pylint: disable=too-many-locals
    def degraded_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether DEGRADED is valid for the subrack.

        :param state_dict: The current state of the subrack.

        :return: True if DEGRADED is a valid state, along with a text report.
        """
        fail_str = "degraded_"
        has_degraded = False
        report = ""

        if (
            state_dict.get("subrack_state_points") == {}
            or state_dict.get("subrack_state_points") is None
        ):
            return has_degraded, report
        state = state_dict.get("subrack_state_points")
        assert isinstance(state, dict)

        voltage_degraded, voltage_report = self._check_voltage_drops(
            state["old_tpm_voltages"],
            state["tpm_voltages"],
            state["old_power_supply_voltages"],
            state["power_supply_voltages"],
            fail_str,
        )
        if (
            voltage_degraded
            and state["old_tpm_power_states"] != state["tpm_power_states"]
        ):
            has_degraded = True
            report += voltage_report
        power_degraded, power_report = self._check_powers(
            state["tpm_power_states"],
            state["tpm_voltages"],
            state["tpm_currents"],
            state["tpm_present"],
            fail_str,
        )
        if power_degraded:
            has_degraded = True
            report += power_report
        basic_degraded, basic_report = self._check_basic_thresholds(
            state["board_temps"], state["backplane_temps"], fail_str
        )
        if basic_degraded:
            has_degraded = True
            report += basic_report
        fan_degraded, fan_report = self._check_fan_speeds(
            state["subrack_fan_speeds"], state["desired_fan_speeds"], fail_str
        )
        if fan_degraded:
            has_degraded = True
            report += fan_report
        current_degraded, current_report = self._check_current_diff(
            state["tpm_currents"],
            state["board_currents"],
            state["power_supply_currents"],
            fail_str,
        )
        if current_degraded:
            has_degraded = True
            report += current_report

        return has_degraded, report

    def healthy_rule(  # type: ignore[override]
        self: SubrackHealthRules,
        state_dict: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether OK is valid for the subrack.

        :param state_dict: The current state of the subrack.

        :return: True if OK is a valid state, along with a text report.
        """
        # Not sure what I should be measuring against here...
        return True, "Health is OK"

    @property
    def default_thresholds(self: HealthRules) -> dict[str, Any]:
        """
        Get the default thresholds for this device.

        :return: the default thresholds
        """
        # Not certain on these values just yet, so these are placeholders
        # for now, will need to get input from stakeholders on actual values
        # TODO NEED to get these actual values from somewhere
        return {
            "failed_max_board_temp": 70.0,
            "degraded_max_board_temp": 60.0,
            "failed_min_board_temp": 10.0,
            "degraded_min_board_temp": 20.0,
            "failed_max_backplane_temp": 70.0,
            "degraded_max_backplane_temp": 60.0,
            "failed_min_backplane_temp": 10.0,
            "degraded_min_backplane_temp": 15.0,
            "failed_fan_speed_diff": 10.0,
            "degraded_fan_speed_diff": 5.0,
            "failed_min_fan_speed": 20.0,
            "degraded_min_fan_speed": 30.0,
            "failed_voltage_drop": 5.0,
            "degraded_voltage_drop": 3.0,
            "failed_max_current_diff": 12.0,
            "degraded_max_current_diff": 10.0,
            "failed_tpm_voltage_on": 13.0,
            "degraded_tpm_voltage_on": 12.5,
            "failed_tpm_current_on": 9.0,
            "degraded_tpm_current_on": 8.0,
            "failed_tpm_voltage_standby": 5.0,
            "degraded_tpm_voltage_standby": 4.0,
            "failed_tpm_current_standby": 4.0,
            "degraded_tpm_current_standby": 3.0,
            "clock_presence": [],
        }
