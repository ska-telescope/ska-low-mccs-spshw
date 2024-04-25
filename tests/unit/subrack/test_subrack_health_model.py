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
from ska_control_model import HealthState, PowerState
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.subrack.subrack_health_model import SubrackHealthModel


class TestSubrackHealthModel:
    """A class for tests of the station health model."""

    @pytest.fixture
    def health_model(self: TestSubrackHealthModel) -> SubrackHealthModel:
        """
        Fixture to return the station health model.

        :return: Health model to be used.
        """
        health_model = SubrackHealthModel(MockCallable())
        health_model.update_state(communicating=True, power=PowerState.ON)

        return health_model

    @pytest.mark.parametrize(
        ("data", "expected_final_health", "expected_final_report"),
        [
            pytest.param(
                {
                    "board_temps": [50.0, 50.0],
                    "backplane_temps": [50.0, 50.0],
                    "subrack_fan_speeds": [60.0, 60.0],
                    "board_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
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
                    "board_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
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
                    "board_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
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
                "50.0 greater than failed_max_board_temp 30.0",
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
                "50.0 greater than degraded_max_board_temp 40.0",
                id="Update thresholds so that now the device reports DEGRADED",
            ),
            pytest.param(
                None,
                {"clock_presence": ["some_clock"]},
                HealthState.OK,
                "Health is OK.",
                HealthState.FAILED,
                "clock_reqs ['10MHz', '1PPS', '10_MHz_PLL_lock'] "
                "does not match thresholds ['some_clock']",
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
                "50.0 greater than failed_max_board_temp 30.0",
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
            "board_currents": [4.0, 4.0, 4.0, 4.0, 4.0],
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
