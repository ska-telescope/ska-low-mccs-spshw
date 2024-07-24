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
            "init_health_report",
            "final_monitoring_points",
            "final_health_state",
            "final_health_report",
        ],
        [
            (
                {},
                HealthState.OK,
                "Health is OK.",
                {},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {},
                HealthState.OK,
                "Health is OK.",
                {"voltages": {"AVDD3": 3.4}},
                HealthState.FAILED,
                "Intermediate health voltages is in FAILED HealthState. "
                'Cause: Monitoring point "/AVDD3": 3.4 not in range 2.37 - 2.6',
            ),
            (
                {"dsp": {"tile_beamf": False}},
                HealthState.FAILED,
                "Intermediate health dsp is in FAILED HealthState. "
                'Cause: Monitoring point "/tile_beamf": False =/= True',
                {"dsp": {"tile_beamf": True}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {"currents": {"FE0_mVA": 3.2}},
                HealthState.FAILED,
                "Intermediate health currents is in FAILED HealthState. "
                'Cause: Monitoring point "/FE0_mVA": 3.2 not in range 2.45 - 2.55',
                {"currents": {"FE0_mVA": 3.1}},
                HealthState.FAILED,
                "Intermediate health currents is in FAILED HealthState. "
                'Cause: Monitoring point "/FE0_mVA": 3.1 not in range 2.45 - 2.55',
            ),
            (
                {"temperatures": {"board": 25}},
                HealthState.OK,
                "Health is OK.",
                {"temperatures": {"board": 58}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {"alarms": {"temperature_alm": 0}},
                HealthState.OK,
                "Health is OK.",
                {"alarms": {"temperature_alm": 1}},
                HealthState.FAILED,
                "Intermediate health alarms is in FAILED HealthState. "
                'Cause: Monitoring point "/temperature_alm": 1 =/= 0',
            ),
            (
                {"adcs": {"sysref_counter": {"ADC7": False}}},
                HealthState.FAILED,
                "Intermediate health adcs is in FAILED HealthState. "
                'Cause: Monitoring point "/sysref_counter/ADC7": False =/= True',
                {"adcs": {"sysref_counter": {"ADC7": True}}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {"io": {"ddr_interface": {"reset_counter": {"FPGA1": 1}}}},
                HealthState.FAILED,
                "Intermediate health io is in FAILED HealthState. "
                'Cause: Monitoring point "/ddr_interface/reset_counter/FPGA1": 1 =/= 0',
                {"io": {"ddr_interface": {"reset_counter": {"FPGA1": 2}}}},
                HealthState.FAILED,
                "Intermediate health io is in FAILED HealthState. "
                'Cause: Monitoring point "/ddr_interface/reset_counter/FPGA1": 2 =/= 0',
            ),
            (
                {"voltages": {"VREF_2V5": None}},
                HealthState.OK,
                "Health is OK.",
                {"voltages": {"VREF_2V5": 2.5}},
                HealthState.FAILED,
                "Intermediate health voltages is in FAILED HealthState. "
                'Cause: Monitoring point "/VREF_2V5": 2.5 =/= None',
            ),
        ],
    )
    def test_health_changed_monitored_value(  # pylint: disable=too-many-arguments
        self: TestTileHealthModel,
        health_model: TileHealthModel,
        init_monitoring_points: dict[str, Any],
        init_health_state: HealthState,
        init_health_report: str,
        final_monitoring_points: dict[str, Any],
        final_health_state: HealthState,
        final_health_report: str,
    ) -> None:
        """
        Test the TileHealthModel for changing monitoring points.

        :param health_model: the HealthModel to test
        :param init_monitoring_points: the initial monitoring points,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param init_health_report: the initial expected health report
        :param final_monitoring_points: the new values of the monitoring points
        :param final_health_state: the final expected health state
        :param final_health_report: the initial final health report
        """
        # TODO: Fixed in ska-low-mccs-common > 0.7.2
        health_model._state[
            "tile_health_structure"
        ] = health_model._merge_dicts(  # type: ignore[assignment]
            TileData.get_tile_defaults(), init_monitoring_points
        )
        assert (init_health_state, init_health_report) == health_model.evaluate_health()
        health_model._state[
            "tile_health_structure"
        ] = health_model._merge_dicts(  # type: ignore[assignment]
            health_model._state["tile_health_structure"],  # type: ignore[arg-type]
            final_monitoring_points,
        )
        assert (
            final_health_state,
            final_health_report,
        ) == health_model.evaluate_health()

    @pytest.mark.parametrize(
        [
            "init_thresholds",
            "init_health_state",
            "init_health_report",
            "final_thresholds",
            "final_health_state",
            "final_health_report",
        ],
        [
            (
                {},
                HealthState.OK,
                "Health is OK.",
                {"voltages": {"MON_3V3": {"min": 1}}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {},
                HealthState.OK,
                "Health is OK.",
                {"temperatures": {"FPGA1": {"min": 150, "max": 250}}},
                HealthState.FAILED,
                "Intermediate health temperatures is in FAILED HealthState. "
                'Cause: Monitoring point "/FPGA1": 52.5 not in range 150 - 250',
            ),
            (
                {"timing": {"clocks": {"FPGA1": {"UDP": False}}}},
                HealthState.FAILED,
                "Intermediate health timing is in FAILED HealthState. "
                'Cause: Monitoring point "/clocks/FPGA1/UDP": True =/= False',
                {"timing": {"clocks": {"FPGA1": {"UDP": True}}}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {"io": {"f2f_interface": {"pll_status": (False, 2)}}},
                HealthState.FAILED,
                "Intermediate health io is in FAILED HealthState. "
                'Cause: Monitoring point "/f2f_interface/pll_status": '
                "(True, 0) =/= (False, 2)",
                {"io": {"f2f_interface": {"pll_status": (False, 4)}}},
                HealthState.FAILED,
                "Intermediate health io is in FAILED HealthState. "
                'Cause: Monitoring point "/f2f_interface/pll_status": '
                "(True, 0) =/= (False, 4)",
            ),
            (
                {"voltages": {"VIN": {"min": 10}}},
                HealthState.OK,
                "Health is OK.",
                {"voltages": {"VIN": {"min": 11}}},
                HealthState.OK,
                "Health is OK.",
            ),
            (
                {"adcs": {"sysref_timing_requirements": {"ADC12": True}}},
                HealthState.OK,
                "Health is OK.",
                {"adcs": {"sysref_timing_requirements": {"ADC12": False}}},
                HealthState.FAILED,
                "Intermediate health adcs is in FAILED HealthState. "
                'Cause: Monitoring point "/sysref_timing_requirements/ADC12": '
                "True =/= False",
            ),
            # TODO: MCCS-1979
            # (
            #     {"alarms": {"voltage_alm": 1}},
            #     HealthState.FAILED,
            #     "Intermediate health alarms is in FAILED HealthState. "
            #     'Cause: Monitoring point "/voltage_alm": 0 =/= 1',
            #     {"alarms": {"voltage_alm": 0}},
            #     HealthState.OK,
            #     "Health is OK.",
            # ),
            (
                {"dsp": {"station_beamf": {"ddr_parity_error_count": {"FPGA0": 2}}}},
                HealthState.FAILED,
                "Intermediate health dsp is in FAILED HealthState. "
                "Cause: Monitoring point "
                '"/station_beamf/ddr_parity_error_count/FPGA0": 0 =/= 2',
                {"dsp": {"station_beamf": {"ddr_parity_error_count": {"FPGA0": 1}}}},
                HealthState.FAILED,
                "Intermediate health dsp is in FAILED HealthState. "
                "Cause: Monitoring point "
                '"/station_beamf/ddr_parity_error_count/FPGA0": 0 =/= 1',
            ),
            (
                {"voltages": {"VREF_2V5": {"min": 2.4, "max": 2.6}}},
                HealthState.UNKNOWN,
                "Intermediate health voltages is in UNKNOWN HealthState. "
                "Cause: Monitoring point VREF_2V5 is None.",
                {"voltages": {"VREF_2V5": None}},
                HealthState.OK,
                "Health is OK.",
            ),
            # TODO: MCCS-1979
            # (
            #     {"alarms": {"voltage_alm": {"min": 0, "max": 1}}},
            #     HealthState.OK,
            #     "Health is OK.",
            #     {"alarms": {"voltage_alm": 1}},
            #     HealthState.FAILED,
            #     "Intermediate health alarms is in FAILED HealthState. "
            #     'Cause: Monitoring point "/voltage_alm": 0 =/= 1',
            # ),
        ],
    )
    def test_health_changed_thresholds(  # pylint: disable=too-many-arguments
        self: TestTileHealthModel,
        health_model: TileHealthModel,
        init_thresholds: dict[str, Any],
        init_health_state: HealthState,
        init_health_report: str,
        final_thresholds: dict[str, Any],
        final_health_state: HealthState,
        final_health_report: str,
    ) -> None:
        """
        Test the TileHealthModel for changing thresholds.

        :param health_model: the HealthModel to test
        :param init_thresholds: the initial thresholds,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param init_health_report: the initial expected health report
        :param final_thresholds: the new values of the thresholds
        :param final_health_state: the final expected health state
        :param final_health_report: the initial final health report
        """
        # TODO: Fixed in ska-low-mccs-common > 0.7.2
        health_model._state[
            "tile_health_structure"
        ] = TileData.get_tile_defaults()  # type: ignore[assignment]
        health_model.health_params = init_thresholds
        assert (init_health_state, init_health_report) == health_model.evaluate_health()
        health_model.health_params = final_thresholds
        assert (
            final_health_state,
            final_health_report,
        ) == health_model.evaluate_health()
