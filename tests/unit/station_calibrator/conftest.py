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


@pytest.fixture(name="calibration_solutions")
def calibration_solutions_fixture() -> dict[int, list[float]]:
    """
    Fixture that provides sample calibration solutions.

    :return: a sample calibration solution.
    """
    return {
        23: [0.5 * i for i in range(256)],
        45: [1.2 * (i % 2) for i in range(256)],
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
    calibration_solutions: dict[int, list[float]],
) -> unittest.mock.Mock:
    """
    Fixture that provides a mock MccsCalibrationStore device.

    :param calibration_solutions: sample calibration solutions to return from the
        calibration store, where the channel is the key

    :return: a mock MccsCalibrationStore device.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    calibration_store = builder()
    calibration_store.GetSolution = lambda c, _: calibration_solutions[c]
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
