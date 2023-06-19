# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the SpsStation tango device."""
from __future__ import annotations

import gc
import json
from typing import Generator

import pytest
from ska_control_model import AdminMode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy

from ska_low_mccs_spshw import MccsStationCalibrator

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "admin_mode",
        "command_result",
        "command_status",
        "health_state",
        "state",
        timeout=2.0,
    )


@pytest.fixture(name="station_calibrator_name", scope="session")
def station_calibrator_name_fixture() -> str:
    """
    Return the name of the Station Calibrator Tango device.

    :return: the name of the Station Calibrator Tango device.
    """
    return "low-mccs/stationcalibrator/001"


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(  # pylint: disable=too-many-arguments
    station_calibrator_name: str,
    patched_station_calibrator_device_class: type,
    field_station_name: str,
    mock_field_station: DeviceProxy,
    calibration_store_name: str,
    mock_calibration_store: DeviceProxy,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param station_calibrator_name: the name of the station calibrator Tango device
    :param patched_station_calibrator_device_class: a subclass of MccsStationCalibrator
        that has been patched with extra commands for use in testing
    :param field_station_name: the name of the field station Tango device
    :param mock_field_station: a mock field station proxy that has been configured
        with the required field station behaviours.
    :param calibration_store_name: the name of the calibration store Tango device
    :param mock_calibration_store: a mock calibration store proxy that has been
        configured with the required calibration store behaviours.

    :yields: a tango context.
    """
    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        station_calibrator_name,
        patched_station_calibrator_device_class,
        FieldStationFQDN=field_station_name,
        CalibrationStoreFQDN=calibration_store_name,
    )
    context_manager.add_mock_device(field_station_name, mock_field_station)
    context_manager.add_mock_device(calibration_store_name, mock_calibration_store)
    with context_manager as context:
        yield context


@pytest.fixture(name="station_calibrator_device")
def station_calibrator_device_fixture(
    tango_harness: TangoContextProtocol,
    station_calibrator_name: str,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param station_calibrator_name: name of the station calibrator Tango device.

    :yield: the station calibrator Tango device under test.
    """
    yield tango_harness.get_device(station_calibrator_name)


def test_GetCalibration(
    station_calibrator_device: MccsStationCalibrator,
    calibration_solutions: dict[tuple[int, float], list[float]],
) -> None:
    """
    Test of the GetCalibration command.

    :param station_calibrator_device: the station calibrator device under test
    :param calibration_solutions: the expected calibration solutions to be returned
        The key is the channel and the value is the calibration solution
    """
    station_calibrator_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    for channel, temperature in calibration_solutions:
        argin = json.dumps({"frequency_channel": channel})
        station_calibrator_device.SetOutsideTemperature(temperature)
        result = station_calibrator_device.GetCalibration(argin)
        assert all(result == calibration_solutions[(channel, temperature)])
