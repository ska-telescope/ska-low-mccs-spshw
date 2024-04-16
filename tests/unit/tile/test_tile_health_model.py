# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the TileHealthModel."""
from __future__ import annotations

from typing import Any

import pytest
from ska_control_model import HealthState, PowerState
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.tile import TileData, TileHealthModel


class TestTileHealthModel:
    """A class for tests of the tile health model."""

    @pytest.fixture
    def health_model(self: TestTileHealthModel) -> TileHealthModel:
        """
        Fixture to return the tile health model.

        :return: Health model to be used.
        """
        health_model = TileHealthModel(MockCallable())
        health_model.update_state(communicating=True, power=PowerState.ON)

        return health_model

    @pytest.mark.parametrize(
        [
            "init_monitoring_points",
            "init_health_state",
            "final_monitoring_points",
            "final_health_state",
        ],
        [
            ({}, HealthState.OK, {}, HealthState.OK),
            ({}, HealthState.OK, {"voltages": {"AVDD3": 3.4}}, HealthState.FAILED),
            (
                {"dsp": {"tile_beamf": False}},
                HealthState.FAILED,
                {"dsp": {"tile_beamf": True}},
                HealthState.OK,
            ),
            (
                {"currents": {"FE0_mVA": 3.2}},
                HealthState.FAILED,
                {"currents": {"FE0_mVA": 3.1}},
                HealthState.FAILED,
            ),
            (
                {"temperatures": {"board": 25}},
                HealthState.OK,
                {"temperatures": {"board": 58}},
                HealthState.OK,
            ),
            (
                {"alarms": {"temperature_alm": 0}},
                HealthState.OK,
                {"alarms": {"temperature_alm": 1}},
                HealthState.FAILED,
            ),
            (
                {"adcs": {"sysref_counter": {"ADC7": False}}},
                HealthState.FAILED,
                {"adcs": {"sysref_counter": {"ADC7": True}}},
                HealthState.OK,
            ),
            (
                {"io": {"ddr_interface": {"reset_counter": {"FPGA1": 1}}}},
                HealthState.FAILED,
                {"io": {"ddr_interface": {"reset_counter": {"FPGA1": 2}}}},
                HealthState.FAILED,
            ),
        ],
    )
    def test_health_changed_monitored_value(  # pylint: disable=too-many-arguments
        self: TestTileHealthModel,
        health_model: TileHealthModel,
        init_monitoring_points: dict[str, Any],
        init_health_state: HealthState,
        final_monitoring_points: dict[str, Any],
        final_health_state: HealthState,
    ) -> None:
        """
        Test the TileHealthModel for changing monitoring points.

        :param health_model: the HealthModel to test
        :param init_monitoring_points: the initial monitoring points,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param final_monitoring_points: the new values of the monitoring points
        :param final_health_state: the final expected health state
        """
        # TODO: Fixed in ska-low-mccs-common > 0.7.2
        health_model._state[
            "tile_health_structure"
        ] = health_model._merge_dicts(  # type: ignore[assignment]
            TileData.get_tile_defaults(), init_monitoring_points
        )
        assert init_health_state == health_model.evaluate_health()
        health_model._state[
            "tile_health_structure"
        ] = health_model._merge_dicts(  # type: ignore[assignment]
            health_model._state["tile_health_structure"],  # type: ignore[arg-type]
            final_monitoring_points,
        )
        assert final_health_state == health_model.evaluate_health()

    @pytest.mark.parametrize(
        [
            "init_thresholds",
            "init_health_state",
            "final_thresholds",
            "final_health_state",
        ],
        [
            ({}, HealthState.OK, {"voltages": {"MON_3V3": {"min": 1}}}, HealthState.OK),
            (
                {},
                HealthState.OK,
                {"temperatures": {"FPGA1": {"min": 150, "max": 250}}},
                HealthState.FAILED,
            ),
            (
                {"timing": {"clocks": {"FPGA1": {"UDP": False}}}},
                HealthState.FAILED,
                {"timing": {"clocks": {"FPGA1": {"UDP": True}}}},
                HealthState.OK,
            ),
            (
                {"io": {"f2f_interface": {"pll_status": (False, 2)}}},
                HealthState.FAILED,
                {"io": {"f2f_interface": {"pll_status": (False, 4)}}},
                HealthState.FAILED,
            ),
            (
                {"voltages": {"VIN": {"min": 10}}},
                HealthState.OK,
                {"voltages": {"VIN": {"min": 11}}},
                HealthState.OK,
            ),
            (
                {"adcs": {"sysref_timing_requirements": {"ADC12": True}}},
                HealthState.OK,
                {"adcs": {"sysref_timing_requirements": {"ADC12": False}}},
                HealthState.FAILED,
            ),
            (
                {"alarms": {"voltage_alm": 1}},
                HealthState.FAILED,
                {"alarms": {"voltage_alm": 0}},
                HealthState.OK,
            ),
            (
                {"dsp": {"station_beamf": {"ddr_parity_error_count": {"FPGA0": 2}}}},
                HealthState.FAILED,
                {"dsp": {"station_beamf": {"ddr_parity_error_count": {"FPGA0": 1}}}},
                HealthState.FAILED,
            ),
        ],
    )
    def test_health_changed_thresholds(  # pylint: disable=too-many-arguments
        self: TestTileHealthModel,
        health_model: TileHealthModel,
        init_thresholds: dict[str, Any],
        init_health_state: HealthState,
        final_thresholds: dict[str, Any],
        final_health_state: HealthState,
    ) -> None:
        """
        Test the TileHealthModel for changing thresholds.

        :param health_model: the HealthModel to test
        :param init_thresholds: the initial thresholds,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param final_thresholds: the new values of the thresholds
        :param final_health_state: the final expected health state
        """
        # TODO: Fixed in ska-low-mccs-common > 0.7.2
        health_model._state[
            "tile_health_structure"
        ] = TileData.get_tile_defaults()  # type: ignore[assignment]
        health_model.health_params = init_thresholds
        assert init_health_state == health_model.evaluate_health()
        health_model.health_params = final_thresholds
        assert final_health_state == health_model.evaluate_health()
