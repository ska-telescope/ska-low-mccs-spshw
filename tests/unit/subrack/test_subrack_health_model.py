# -*- coding: utf-8 -*
# pylint: disable=too-many-arguments
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsStation."""
from __future__ import annotations

from typing import Any, Optional

import pytest
from ska_control_model import AdminMode, HealthState, PowerState
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.subrack.subrack_health_model import SubrackHealthModel

NUMBER_OF_SUBRACK_STATE_MONITOR_POINTS = 12


class TestSubrackHealthModel:
    """A class for tests of the station health model."""

    @pytest.fixture(name="health_model")
    def health_model_fixture(self: TestSubrackHealthModel) -> SubrackHealthModel:
        """
        Fixture to return the station health model.

        :return: Health model to be used.
        """
        health_model = SubrackHealthModel(MockCallable())
        health_model.update_state(
            communicating=True, power=PowerState.ON, adminMode=AdminMode.ONLINE
        )

        return health_model

    @pytest.fixture(name="tpm_data")
    def tpm_data_fixture(
        self: TestSubrackHealthModel, tpm_count: int = 8
    ) -> dict[str, Any]:
        """
        Produce subrack data for 1-8 TPMs.

        :param tpm_count: Number of TPMs to generate data for. Default 8.

        :returns: A dictionary of TPM data.
        """
        tpm_count = min(tpm_count, 8)
        tpm_count = max(tpm_count, 1)
        data = {
            "board_temps": [50.0, 50.0],
            "backplane_temps": [50.0, 50.0],
            "subrack_fan_speeds": [60.0, 60.0],
            "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
            "power_supply_currents": [8.0, 8.0, 8.0, 8.0],
            "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
            "tpm_currents": [4.0] * tpm_count + [0.0] * (8 - tpm_count),
            "tpm_voltages": [5.0] * tpm_count + [0.0] * (8 - tpm_count),
            "tpm_power_states": [PowerState.UNKNOWN] * tpm_count,
            "tpm_present": [True] * tpm_count + [False] * (8 - tpm_count),
            "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
            "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
        }

        return data

    @pytest.mark.parametrize(
        ("data", "expected_final_health", "expected_final_report"),
        [
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                HealthState.OK,
                "Health is OK.",
                id="All devices healthy, expect OK",
            ),
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.UNKNOWN,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                HealthState.DEGRADED,
                "TPM 3 power state is UNKNOWN, ",
                id="One TPM UNKNOWN, expect DEGRADED",
            ),
            pytest.param(
                {
                    "board_temps": [],
                    "backplane_temps": [],
                    "subrack_fan_speeds": [],
                    "board_currents": [],
                    "tpm_currents": [],
                    "power_supply_currents": [],
                    "tpm_voltages": [],
                    "power_supply_voltages": [],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.UNKNOWN,
                    ],
                    "tpm_present": [],
                    "desired_fan_speeds": [
                        60.0,
                        60.0,
                        60.0,
                        60.0,
                    ],
                    "clock_reqs": [],
                },
                HealthState.OK,
                "Health is OK.",
                id="health state when no attributes updated.",
            ),
        ],
    )
    def test_subrack_evaluate_health(
        self: TestSubrackHealthModel,
        health_model: SubrackHealthModel,
        data: dict[str, Any],
        expected_final_health: HealthState,
        expected_final_report: str,
    ) -> None:
        """
        Tests for evaluating subrack health.

        :param health_model: Health model fixture.
        :param data: Health data values for health model.
        :param expected_final_health: Expected final health.
        :param expected_final_report: Expected final health report.
        """
        assert health_model.evaluate_health() == (
            HealthState.UNKNOWN,
            "Failed to read subrack state",
        )

        health_model.update_data(data)

        assert health_model.evaluate_health() == (
            expected_final_health,
            expected_final_report,
        )

    @pytest.mark.parametrize(
        ("init_data", "expected_state_init", "end_data", "expected_state_end"),
        [
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "old_tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "board_temps": [60.0, 40.0],
                    "backplane_temps": [60.0, 40.0],
                    "subrack_fan_speeds": [70.0, 50.0],
                    "board_currents": [3.0, 3.0, 3.0, 3.0, 3.0],
                    "tpm_currents": [3.0, 3.0, 3.0, 3.0, 3.0],
                    "power_supply_currents": [7.0, 7.0, 7.0, 7.0, 7.0],
                    "tpm_voltages": [4.0, 4.0, 4.0, 4.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "old_tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "board_temps": [60.0, 40.0],
                    "backplane_temps": [60.0, 40.0],
                    "subrack_fan_speeds": [70.0, 50.0],
                    "board_currents": [3.0, 3.0, 3.0, 3.0, 3.0],
                    "tpm_currents": [3.0, 3.0, 3.0, 3.0, 3.0],
                    "power_supply_currents": [7.0, 7.0, 7.0, 7.0, 7.0],
                    "tpm_voltages": [4.0, 4.0, 4.0, 4.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                id="Health data is updated succesfully",
            ),
        ],
    )
    def test_subrack_update_data(
        self: TestSubrackHealthModel,
        health_model: SubrackHealthModel,
        init_data: dict[str, Any],
        expected_state_init: dict,
        end_data: dict[str, Any],
        expected_state_end: dict,
    ) -> None:
        """
        Test that we can update the state of the health model.

        :param health_model: Health model fixture.
        :param init_data: Initial health data values for health model.
        :param expected_state_init: Expected init state.
        :param end_data: Final data for health model.
        :param expected_state_end: Expected final state.
        """
        health_model.update_data(init_data)
        assert health_model._state.get("subrack_state_points") == expected_state_init

        health_model.update_data(end_data)
        assert health_model._state.get("subrack_state_points") == expected_state_end

    @pytest.mark.parametrize(
        (
            "init_thresholds",
            "end_thresholds",
            "init_expected_health",
            "init_expected_report",
            "end_expected_health",
            "end_expected_report",
        ),
        [
            pytest.param(
                None,
                {
                    "failed_max_board_temp": 30.0,
                    "degraded_max_board_temp": 20.0,
                    "failed_min_board_temp": 10.0,
                },
                HealthState.OK,
                "Health is OK.",
                HealthState.FAILED,
                (
                    "Sensor 0 temp 50.0 greater than failed_max_board_temp 30.0. "
                    "Sensor 1 temp 50.0 greater than failed_max_board_temp 30.0. "
                ),
                id="Update thresholds so that now the device reports FAILED",
            ),
            pytest.param(
                None,
                {
                    "failed_max_board_temp": 70.0,
                    "degraded_max_board_temp": 40.0,
                    "failed_min_board_temp": 10.0,
                },
                HealthState.OK,
                "Health is OK.",
                HealthState.DEGRADED,
                (
                    "Sensor 0 temp 50.0 greater than degraded_max_board_temp 40.0. "
                    "Sensor 1 temp 50.0 greater than degraded_max_board_temp 40.0. "
                ),
                id="Update thresholds so that now the device reports DEGRADED",
            ),
            pytest.param(
                None,
                {"clock_presence": ["some_clock"]},
                HealthState.OK,
                "Health is OK.",
                HealthState.FAILED,
                "clock_reqs ['10MHz', '1PPS', '10_MHz_PLL_lock'] "
                "does not match thresholds ['some_clock']. ",
                id="""Update thresholds so that now the device requires clock
                  locks which it doesnt have, report FAILED""",
            ),
            pytest.param(
                {
                    "failed_max_board_temp": 30.0,
                    "degraded_max_board_temp": 20.0,
                    "failed_min_board_temp": 10.0,
                },
                {
                    "failed_max_board_temp": 70.0,
                    "degraded_max_board_temp": 60.0,
                    "failed_min_board_temp": 10.0,
                },
                HealthState.FAILED,
                (
                    "Sensor 0 temp 50.0 greater than failed_max_board_temp 30.0. "
                    "Sensor 1 temp 50.0 greater than failed_max_board_temp 30.0. "
                ),
                HealthState.OK,
                "Health is OK.",
                id="Thresholds start off FAILED, updated to OK",
            ),
        ],
    )
    def test_subrack_can_change_thresholds(
        self: TestSubrackHealthModel,
        health_model: SubrackHealthModel,
        init_thresholds: Optional[dict[str, float]],
        end_thresholds: dict[str, float],
        init_expected_health: HealthState,
        init_expected_report: str,
        end_expected_health: HealthState,
        end_expected_report: str,
    ) -> None:
        """
        Test subrack can change threshold values.

        :param health_model: Health model fixture.
        :param init_thresholds: Initial thresholds to set it to.
        :param end_thresholds: End thresholds to set it to.
        :param init_expected_health: Init expected health.
        :param init_expected_report: Init expected health report.
        :param end_expected_health: Final expected health.
        :param end_expected_report: Final expected health report.

        """
        assert health_model.evaluate_health() == (
            HealthState.UNKNOWN,
            "Failed to read subrack state",
        )

        data = {
            "board_temps": [50.0, 50.0],
            "backplane_temps": [50.0, 50.0],
            "subrack_fan_speeds": [60.0, 60.0],
            "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
            "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
            "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
            "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
            "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
            "tpm_power_states": [
                PowerState.ON,
                PowerState.ON,
                PowerState.ON,
                PowerState.ON,
            ],
            "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
            "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
            "tpm_present": [True, True, True, True],
        }
        if init_thresholds:
            health_model.health_params = init_thresholds

        health_model.update_data(data)
        assert health_model.evaluate_health() == (
            init_expected_health,
            init_expected_report,
        )

        health_model.health_params = end_thresholds
        assert health_model.evaluate_health() == (
            end_expected_health,
            end_expected_report,
        )

    @pytest.mark.parametrize(
        (
            "first_data",
            "expected_first_health_report",
            "second_data",
            "expected_final_health_report",
        ),
        [
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (HealthState.OK, "Health is OK."),
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.UNKNOWN,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (HealthState.DEGRADED, "TPM 0 power state is UNKNOWN, "),
                id="Transition from OK to DEGRADED",
            ),
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.UNKNOWN,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.UNKNOWN,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (
                    HealthState.DEGRADED,
                    "TPM 0 power state is UNKNOWN, TPM 3 power state is UNKNOWN, ",
                ),
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (HealthState.OK, "Health is OK."),
                id="Transition from DEGRADED to OK",
            ),
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.UNKNOWN,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (HealthState.DEGRADED, "TPM 2 power state is UNKNOWN, "),
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.UNKNOWN,
                        PowerState.UNKNOWN,
                        PowerState.UNKNOWN,
                        PowerState.UNKNOWN,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                (
                    HealthState.FAILED,
                    "TPM 0 power state is UNKNOWN, TPM 1 power state is UNKNOWN, "
                    "TPM 2 power state is UNKNOWN, TPM 3 power state is UNKNOWN, ",
                ),
                id="Transition from DEGRADED to FAILED",
            ),
        ],
    )
    def test_subrack_evaluate_tpm_power_transitions(
        self: TestSubrackHealthModel,
        health_model: SubrackHealthModel,
        first_data: dict[str, Any],
        expected_first_health_report: tuple[HealthState, str],
        second_data: dict[str, Any],
        expected_final_health_report: tuple[HealthState, str],
    ) -> None:
        """
        Tests for evaluating subrack health transition.

        :param health_model: Health model fixture.
        :param first_data: Health data values for health model.
        :param second_data: Health data values for health model.
        :param expected_first_health_report: Expected first health.
        :param expected_final_health_report: Expected final health report.
        """
        assert health_model.evaluate_health() == (
            HealthState.UNKNOWN,
            "Failed to read subrack state",
        )
        health_model.update_data(first_data)
        first_report = health_model.evaluate_health()
        assert first_report == expected_first_health_report

        health_model.update_data(second_data)
        assert health_model.evaluate_health() == expected_final_health_report

    @pytest.mark.parametrize(
        "counter",
        list(range(NUMBER_OF_SUBRACK_STATE_MONITOR_POINTS)),
    )
    @pytest.mark.parametrize(
        (
            "init_data",
            "expected_state_init",
            "poll_data",
            "poll_failed_data",
            "expected_state_end",
            "expected_state_end_failed_poll",
        ),
        [
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "old_tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "board_temps": [],
                    "backplane_temps": [],
                    "subrack_fan_speeds": [],
                    "board_currents": [],
                    "tpm_currents": [],
                    "power_supply_currents": [],
                    "tpm_voltages": [],
                    "power_supply_voltages": [],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": [],
                },
                {
                    "old_tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
                    "power_supply_currents": [8.0, 8.0, 8.0, 8.0, 8.0],
                    "tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [True, True, True, True],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": ["10MHz", "1PPS", "10_MHz_PLL_lock"],
                },
                {
                    "old_tpm_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_power_supply_voltages": [5.0, 5.0, 5.0, 5.0],
                    "old_tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "board_temps": [],
                    "backplane_temps": [],
                    "subrack_fan_speeds": [],
                    "board_currents": [],
                    "tpm_currents": [],
                    "power_supply_currents": [],
                    "tpm_voltages": [],
                    "power_supply_voltages": [],
                    "tpm_power_states": [
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                        PowerState.ON,
                    ],
                    "tpm_present": [],
                    "desired_fan_speeds": [60.0, 60.0, 60.0, 60.0],
                    "clock_reqs": [],
                },
                id="Test all attributes failing a poll.",
            ),
        ],
    )
    def test_update_from_failed_poll(
        self: TestSubrackHealthModel,
        health_model: SubrackHealthModel,
        counter: int,
        init_data: dict[str, Any],
        expected_state_init: dict[str, Any],
        poll_data: dict[str, Any],
        poll_failed_data: dict[str, Any],
        expected_state_end: dict[str, Any],
        expected_state_end_failed_poll: dict[str, Any],
    ) -> None:
        """
        Test that we can update the state of the health model.

        Using 2 dictionarys (one containing values from a happy request,
        the other containing the values when the attribute fails) we are
        able to iterate the failed monitoring point using a counter.

        :param counter: a counter used to iterate over failed attributes.
        :param health_model: Health model fixture.
        :param init_data: Initial health data values for health model.
        :param expected_state_init: Expected init state.
        :param poll_data: The data from a successfull poll.
        :param poll_failed_data: The data expected from a failed poll.
        :param expected_state_end: Expected final state when all attributes
            pass a poll.
        :param expected_state_end_failed_poll: Expected final state when
            all attributes fail a poll
        """
        if NUMBER_OF_SUBRACK_STATE_MONITOR_POINTS != len(poll_data):
            pytest.fail(
                "The counter key is larger than the number of checks"
                f"please set counter= {len(expected_state_end)}"
            )

        def _get_failed_monitoring_point_name(
            monitoring_points: dict[str, Any],
            counter: int,
        ) -> str:
            """
            Return the key of the monitoring point to fail.

            :param monitoring_points: a dictionary containing the monitoring points
            :param counter: a counter to select a key from the monitoring points
                at the enumerated position.

            :return: a string with the name of the
                monitoring point to fail a poll

            :raises KeyError: when no key found.
            """
            for i, key in enumerate(monitoring_points.keys()):
                if i == counter:
                    return key
            raise KeyError("No key found")

        def _swap_data_at_key(
            root_data: dict[str, Any], new_data: dict[str, Any], key: str
        ) -> None:
            """
            Modify data1 with data2 for a specific key.

            :param root_data: the dictionary with data to modify
            :param new_data: the dictionary with data to update root_data.
            :param key: the key to use
            """
            root_data[key] = new_data[key]

        health_model.update_data(init_data)
        assert health_model._state.get("subrack_state_points") == expected_state_init

        monitoring_point_to_fail = _get_failed_monitoring_point_name(poll_data, counter)
        _swap_data_at_key(poll_data, poll_failed_data, monitoring_point_to_fail)
        _swap_data_at_key(
            expected_state_end,
            expected_state_end_failed_poll,
            monitoring_point_to_fail,
        )
        health_model.update_data(poll_data)
        assert health_model._state.get("subrack_state_points") == expected_state_end
