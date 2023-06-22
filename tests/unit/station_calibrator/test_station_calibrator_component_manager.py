#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Iterator

import pytest
from ska_control_model import CommunicationStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.station_calibrator import StationCalibratorComponentManager
from tests.harness import (
    SpsTangoTestHarness,
    get_calibration_store_name,
    get_field_station_name,
)


@pytest.fixture(name="test_context")
def test_context_fixture(
    mock_field_station_device_proxy: unittest.mock.Mock,
    mock_calibration_store_device_proxy: unittest.mock.Mock,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    The field station and calibration store devices which the station calibrator
    component manager interacts with are mocked out here

    :param mock_field_station_device_proxy: a mock field station device proxy
        that has been configured with the required field station behaviours.
    :param mock_calibration_store_device_proxy: a mock calibration store device proxy
        that has been configured with the required calibration store behaviours.

    :yields: into a context in which Tango is running
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_field_station_device(mock_field_station_device_proxy)
    harness.add_mock_calibration_store_device(mock_calibration_store_device_proxy)
    with harness:
        yield


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        timeout=5.0,
    )


@pytest.fixture(name="station_calibrator_component_manager")
def station_calibrator_component_manager_fixture(
    test_context: None,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> StationCalibratorComponentManager:
    """
    Return a station calibrator component manager.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group


    :return: a station calibrator component manager.
    """
    return StationCalibratorComponentManager(
        logger,
        get_field_station_name(),
        get_calibration_store_name(),
        callbacks["communication_status"],
        callbacks["component_state"],
    )


@pytest.mark.forked
def test_communication(
    station_calibrator_component_manager: StationCalibratorComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test communication for the station calibrator component manager.

    :param station_calibrator_component_manager: the station calibrator component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert (
        station_calibrator_component_manager.communication_state
        == CommunicationStatus.DISABLED
    )

    # takes the component out of DISABLED
    station_calibrator_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    station_calibrator_component_manager.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
