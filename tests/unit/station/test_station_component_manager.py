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

from ska_low_mccs_spshw.station import SpsStationComponentManager
from tests.harness import SpsTangoTestHarness, get_subrack_name, get_tile_name


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    tile_id: int,
    mock_tile_device_proxy: unittest.mock.Mock,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    The station component manager acts as a Tango client to the subrack
    and tile Tango device. In these unit tests, the subrack and tile
    Tango devices are mocked out, but since the station component
    manager uses tango to talk to them, we still need some semblance of
    a tango subsystem in place. Here, we assume that the station has
    only one subrack and one tile.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy
        that has been configured with the required subrack behaviours.
    :param tile_id: ID of the tile Tango device to be mocked
    :param mock_tile_device_proxy: a mock tile device proxy
        that has been configured with the required subrack behaviours.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    harness.add_mock_tile_device(tile_id, mock_tile_device_proxy)
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
        "tile_health",
        "subrack_health",
        timeout=5.0,
    )


@pytest.fixture(name="station_component_manager")
def station_component_manager_fixture(
    test_context: None,
    subrack_id: int,
    tile_id: int,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> SpsStationComponentManager:
    """
    Return a station component manager.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param subrack_id: ID of the subservient subrack Tango device
    :param tile_id: ID of the subservient subrack Tango device
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group


    :return: a station component manager.
    """
    return SpsStationComponentManager(
        1,
        [get_subrack_name(subrack_id)],
        [get_tile_name(tile_id)],
        "10.0.0.0",
        logger,
        1,
        callbacks["communication_status"],
        callbacks["component_state"],
        callbacks["tile_health"],
        callbacks["subrack_health"],
    )


@pytest.mark.forked
def test_communication(
    station_component_manager: SpsStationComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test communication between the tile component manager and its tile.

    :param station_component_manager: the SPS station component manager
        under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert station_component_manager.communication_state == CommunicationStatus.DISABLED

    # takes the component out of DISABLED. Connects with subrack (NOT with TPM)
    station_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    callbacks["communication_status"].assert_not_called()

    station_component_manager.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)

    callbacks["communication_status"].assert_not_called()
