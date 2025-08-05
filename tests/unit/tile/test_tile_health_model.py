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
        health_model = TileHealthModel(MockCallable(), "v1.6.7a", "0.5.0", True)
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
                'Cause: Monitoring point "/FE0_mVA": 3.2 not in range 2.37 - 2.62',
                {"currents": {"FE0_mVA": 3.1}},
                HealthState.FAILED,
                "Intermediate health currents is in FAILED HealthState. "
                'Cause: Monitoring point "/FE0_mVA": 3.1 not in range 2.37 - 2.62',
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
            "bios_version",
            "hw_version",
            "init_monitoring_points",
            "init_health_state",
            "init_health_report",
            "final_monitoring_points",
            "final_health_state",
            "final_health_report",
        ],
        [
            (
                "0.5.0",
                "v1.6.7a",
                {
                    "temperatures": {
                        "ADC0": float("NaN"),
                        "ADC1": float("NaN"),
                        "ADC2": float("NaN"),
                        "ADC3": float("NaN"),
                        "ADC4": float("NaN"),
                        "ADC5": float("NaN"),
                        "ADC6": float("NaN"),
                        "ADC7": float("NaN"),
                        "ADC8": float("NaN"),
                        "ADC9": float("NaN"),
                        "ADC10": float("NaN"),
                        "ADC11": float("NaN"),
                        "ADC12": float("NaN"),
                        "ADC13": float("NaN"),
                        "ADC14": float("NaN"),
                        "ADC15": float("NaN"),
                    }
                },
                HealthState.OK,
                "Health is OK.",
                {"temperatures": {"ADC0": 22.0}},
                HealthState.FAILED,  # This is determined by the hw and bios versions.
                "Intermediate health temperatures is in FAILED HealthState. "
                'Cause: Monitoring point "/ADC0": 22.0 =/= nan',
            ),
            (
                "0.5.0",
                "v2.0.5b",
                {
                    "temperatures": {
                        "ADC0": float("NaN"),
                        "ADC1": float("NaN"),
                        "ADC2": float("NaN"),
                        "ADC3": float("NaN"),
                        "ADC4": float("NaN"),
                        "ADC5": float("NaN"),
                        "ADC6": float("NaN"),
                        "ADC7": float("NaN"),
                        "ADC8": float("NaN"),
                        "ADC9": float("NaN"),
                        "ADC10": float("NaN"),
                        "ADC11": float("NaN"),
                        "ADC12": float("NaN"),
                        "ADC13": float("NaN"),
                        "ADC14": float("NaN"),
                        "ADC15": float("NaN"),
                    }
                },
                HealthState.FAILED,
                "Intermediate health temperatures is in FAILED HealthState. "
                'Cause: Monitoring point "/ADC0": nan not in range 10 - 90 | '
                'Monitoring point "/ADC1": nan not in range 10 - 90 | '
                'Monitoring point "/ADC2": nan not in range 10 - 90 | '
                'Monitoring point "/ADC3": nan not in range 10 - 90 | '
                'Monitoring point "/ADC4": nan not in range 10 - 90 | '
                'Monitoring point "/ADC5": nan not in range 10 - 90 | '
                'Monitoring point "/ADC6": nan not in range 10 - 90 | '
                'Monitoring point "/ADC7": nan not in range 10 - 90 | '
                'Monitoring point "/ADC8": nan not in range 10 - 90 | '
                'Monitoring point "/ADC9": nan not in range 10 - 90 | '
                'Monitoring point "/ADC10": nan not in range 10 - 90 | '
                'Monitoring point "/ADC11": nan not in range 10 - 90 | '
                'Monitoring point "/ADC12": nan not in range 10 - 90 | '
                'Monitoring point "/ADC13": nan not in range 10 - 90 | '
                'Monitoring point "/ADC14": nan not in range 10 - 90 | '
                'Monitoring point "/ADC15": nan not in range 10 - 90',
                {
                    "temperatures": {
                        "ADC0": 22.0,
                        "ADC1": 22.0,
                        "ADC2": 22.0,
                        "ADC3": 22.0,
                        "ADC4": 22.0,
                        "ADC5": 22.0,
                        "ADC6": 22.0,
                        "ADC7": 22.0,
                        "ADC8": 22.0,
                        "ADC9": 22.0,
                        "ADC10": 22.0,
                        "ADC11": 22.0,
                        "ADC12": 22.0,
                        "ADC13": 22.0,
                        "ADC14": 22.0,
                        "ADC15": 22.0,
                    }
                },
                HealthState.OK,
                "Health is OK.",
            ),
        ],
    )
    def test_health_with_hardware_configuration(  # pylint: disable=too-many-arguments
        self: TestTileHealthModel,
        bios_version: str,
        hw_version: str,
        init_monitoring_points: dict[str, Any],
        init_health_state: HealthState,
        init_health_report: str,
        final_monitoring_points: dict[str, Any],
        final_health_state: HealthState,
        final_health_report: str,
    ) -> None:
        """
        Test the TileHealthModel for for different hardware.

        :param bios_version: the bios version of the TPM.
        :param hw_version: the hardware version of the TPM.
        :param init_monitoring_points: the initial monitoring points,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param init_health_report: the initial expected health report
        :param final_monitoring_points: the new values of the monitoring points
        :param final_health_state: the final expected health state
        :param final_health_report: the initial final health report
        """
        health_model = TileHealthModel(MockCallable(), hw_version, bios_version, True)
        health_model.update_state(communicating=True, power=PowerState.ON)
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
                {"pps_drift": 5},
                HealthState.DEGRADED,
                "Intermediate health derived is in DEGRADED HealthState. "
                'Cause: Monitoring point "/pps_drift": 5 over soft limit: 4',
            ),
            (
                {},
                HealthState.OK,
                "Health is OK.",
                {"pps_drift": 15},
                HealthState.FAILED,
                "Intermediate health derived is in FAILED HealthState. "
                'Cause: Monitoring point "/pps_drift": 15 over hard limit: 10',
            ),
        ],
    )
    def test_derived_health_changed_value(  # pylint: disable=too-many-arguments
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
        Test the TileHealthModel for changing derived monitoring points.

        :param health_model: the HealthModel to test
        :param init_monitoring_points: the initial monitoring points,
            using the defaults where not provided
        :param init_health_state: the initial expected health state
        :param init_health_report: the initial expected health report
        :param final_monitoring_points: the new values of the monitoring points
        :param final_health_state: the final expected health state
        :param final_health_report: the initial final health report
        """
        health_model._state["tile_health_structure"] = TileData.get_tile_defaults()
        health_model._state.update(
            derived=health_model._merge_dicts(  # type: ignore[assignment]
                health_model._state["derived"],  # type: ignore[arg-type]
                init_monitoring_points,
            )
        )

        assert (init_health_state, init_health_report) == health_model.evaluate_health()
        health_model._state.update(
            derived=health_model._merge_dicts(  # type: ignore[assignment]
                health_model._state["derived"],  # type: ignore[arg-type]
                final_monitoring_points,
            )
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
        health_model._state["tile_health_structure"] = (  # type: ignore[assignment]
            TileData.get_tile_defaults()
        )
        health_model.health_params = init_thresholds
        assert (init_health_state, init_health_report) == health_model.evaluate_health()
        health_model.health_params = final_thresholds
        assert (
            final_health_state,
            final_health_report,
        ) == health_model.evaluate_health()
