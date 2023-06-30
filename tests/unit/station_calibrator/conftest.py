#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a harness for unit testing the Station calibrator module."""
from __future__ import annotations

import json
import unittest.mock

import pytest
import tango
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw.station_calibrator import MccsStationCalibrator


@pytest.fixture(name="mock_calibration_store_device_proxy")
def mock_calibration_store_device_proxy_fixture(
    calibration_solutions: dict[tuple[int, float], list[float]],
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsCalibrationStore device proxy.

    :param calibration_solutions: sample calibration solutions to return from the
        calibration store, where the channel and temperature are the key

    :return: a mock MccsCalibrationStore device proxy.
    """

    def _GetSolution(argin: str) -> list[float]:
        args = json.loads(argin)
        return calibration_solutions[(args["channel"], args["outside_temperature"])]

    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    calibration_store = builder()
    calibration_store.GetSolution = _GetSolution
    return calibration_store


@pytest.fixture(name="mock_field_station_device_proxy")
def mock_field_station_device_proxy_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock FieldStation device.

    :return: a mock FieldStation device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    return builder()


@pytest.fixture(name="patched_station_calibrator_device_class")
def patched_station_calibrator_device_class_fixture() -> type[MccsStationCalibrator]:
    """
    Return a station calibrator device class patched with extra methods for testing.

    :return: a station calibrator device class patched with extra methods for testing.
    """

    class PatchedStationCalibratorDevice(MccsStationCalibrator):
        """MccsStationCalibrator patched with extra commands for testing purposes."""

        @command(dtype_in="DevDouble", dtype_out="DevVoid")
        def SetOutsideTemperature(
            self: PatchedStationCalibratorDevice, argin: float
        ) -> None:
            """
            Mock a change in the outside temperature.

            :param argin: the outside temperature

            This would typically be polled from the field station.
            """
            self.component_manager._field_station_outside_temperature_changed(
                "outsideTemperature", argin, tango.AttrQuality.ATTR_VALID
            )

    return PatchedStationCalibratorDevice
