#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a harness for unit testing the Station calibrator module."""
from __future__ import annotations

import unittest.mock

import pytest
import tango
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from tango.server import command

from ska_low_mccs_spshw.station_calibrator import MccsStationCalibrator


@pytest.fixture(name="calibration_solutions")
def calibration_solutions_fixture() -> dict[tuple[int, float], list[float]]:
    """
    Fixture that provides sample calibration solutions.

    :return: a sample calibration solution. The keys are tuples of the channel
        and the outside temperature, and the values are lists of calibration values
    """
    return {
        (23, 25.0): [0.5 * i for i in range(256)],
        (45, 25.0): [1.2 * (i % 2) for i in range(256)],
        (23, 30.0): [0.6 * i for i in range(256)],
        (45, 30.0): [1.4 * (i % 2) for i in range(256)],
        (23, 35.0): [0.7 * i for i in range(256)],
        (45, 35.0): [1.6 * (i % 2) for i in range(256)],
    }


@pytest.fixture(name="calibration_store_name", scope="session")
def calibration_store_name_fixture() -> str:
    """
    Return the name of the Calibration Store Tango device.

    :return: the name of the Calibration Store Tango device.
    """
    return "low-mccs/calibrationstore/001"


@pytest.fixture(name="mock_calibration_store")
def mock_calibration_store_fixture(
    calibration_solutions: dict[tuple[int, float], list[float]],
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsCalibrationStore device.

    :param calibration_solutions: sample calibration solutions to return from the
        calibration store, where the channel and temperature are the key

    :return: a mock MccsCalibrationStore device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    calibration_store = builder()
    calibration_store.GetSolution = lambda c, t: calibration_solutions[(c, t)]
    return calibration_store


@pytest.fixture(name="field_station_name", scope="session")
def field_station_name_fixture() -> str:
    """
    Return the name of the Field Station Tango device.

    :return: the name of the Field Station Tango device.
    """
    return "low-mccs/fieldstation/001"


@pytest.fixture(name="mock_field_station")
def mock_field_station_fixture() -> unittest.mock.Mock:
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
