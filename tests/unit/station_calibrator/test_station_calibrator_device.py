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
import time
from typing import Iterator
from unittest.mock import Mock

import pytest
from ska_control_model import AdminMode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy

from ska_low_mccs_spshw import MccsStationCalibrator
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext

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


@pytest.fixture(name="test_context")
def test_context_fixture(
    patched_station_calibrator_device_class: MccsStationCalibrator,
    mock_field_station_device_proxy: Mock,
    mock_calibration_store_device_proxy: Mock,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Yield into a context in which Tango is running, with mock devices.

    :param patched_station_calibrator_device_class: a subclass of MccsStationCalibrator
        that has been patched with extra commands for use in testing
    :param mock_field_station_device_proxy: a mock field station proxy that has been
        configured with the required field station behaviours.
    :param mock_calibration_store_device_proxy: a mock calibration store proxy that has
        been configured with the required calibration store behaviours.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.set_station_calibrator_device(
        device_class=patched_station_calibrator_device_class,
    )
    harness.add_mock_field_station_device(mock_field_station_device_proxy)
    harness.add_mock_calibration_store_device(mock_calibration_store_device_proxy)
    with harness as context:
        yield context


@pytest.fixture(name="station_calibrator_device")
def station_calibrator_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the station calibrator Tango device under test.

    :param test_context: a Tango test context
        containing an SPS station and mock subservient devices.

    :yield: the station calibrator Tango device under test.
    """
    yield test_context.get_station_calibrator_device()


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

    # Give the calibrator a moment to set up the proxies
    time.sleep(0.1)

    for channel, temperature in calibration_solutions:
        argin = json.dumps({"frequency_channel": channel})
        station_calibrator_device.SetOutsideTemperature(temperature)
        result = station_calibrator_device.GetCalibration(argin)
        assert all(result == calibration_solutions[(channel, temperature)])
