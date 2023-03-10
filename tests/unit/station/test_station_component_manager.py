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
from typing import Generator

import pytest
from ska_control_model import CommunicationStatus
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.station import SpsStationComponentManager


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    subrack_name: str,
    mock_subrack: unittest.mock.Mock,
    tile_name: str,
    mock_tile: unittest.mock.Mock,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of station component manager.

    The station component manager acts as a Tango client to the subrack
    and tile Tango device. In these unit tests, the subrack and tile
    Tango devices are mocked out, but since the station component
    manager uses tango to talk to them, we still need some semblance of
    a tango subsystem in place. Here, we assume that the station has
    only one subrack and one tile.

    :param subrack_name: the name of the subrack Tango device
    :param mock_subrack: a mock that has been configured with the
        required subrack behaviours.
    :param tile_name: the name of the subrack Tango device
    :param mock_tile: a mock that has been configured with the
        required tile behaviours.

    :yields: a tango context.
    """
    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_mock_device(subrack_name, mock_subrack)
    context_manager.add_mock_device(tile_name, mock_tile)
    with context_manager as context:
        yield context


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


@pytest.fixture(name="station_component_manager")
def station_component_manager_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
    tile_name: str,
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> SpsStationComponentManager:
    """
    Return a station component manager.

    :param tango_harness: a test harness for MCCS tango devices
    :param subrack_name: name of the subservient subrack Tango device
    :param tile_name: name of the subservient subrack Tango device
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group


    :return: a station component manager.
    """
    return SpsStationComponentManager(
        1,
        [subrack_name],
        [tile_name],
        "10.0.0.0",
        logger,
        1,
        callbacks["communication_status"],
        callbacks["component_state"],
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

    station_component_manager.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
