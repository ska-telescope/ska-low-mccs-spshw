# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import gc
from typing import Generator

import pytest
import tango
from ska_control_model import AdminMode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    station_name: str,
    subrack_name: str,
    subrack_address: tuple[str, int],
    tile_name: str,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param station_name: the name of the station Tango device
    :param subrack_name: the name of the subrack Tango device
    :param subrack_address: the host and port of the subrack
    :param tile_name: the name of the tile Tango device

    :yields: a tango context.
    """
    subrack_ip, subrack_port = subrack_address

    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        station_name,
        "ska_low_mccs_spshw.SpsStation",
        StationId=0,
        TileFQDNs=[tile_name],
        SubrackFQDNs=[subrack_name],
        CabinetNetworkAddress="10.0.0.0",
    )
    context_manager.add_device(
        subrack_name,
        "ska_low_mccs_spshw.MccsSubrack",
        SubrackIp=subrack_ip,
        SubrackPort=subrack_port,
        UpdateRate=1.0,
        LoggingLevelDefault=5,
    )
    context_manager.add_device(
        tile_name,
        "ska_low_mccs_spshw.MccsTile",
        TileId=1,
        SubrackFQDN=subrack_name,
        SubrackBay=1,
        AntennasPerTile=2,
        SimulationConfig=1,
        TestConfig=1,
        TpmIp="10.0.10.201",
        TpmCpldPort=10000,
        TpmVersion="tpm_v1_6",
        LoggingLevelDefault=5,
    )
    with context_manager as context:
        yield context


@pytest.fixture(name="station_device")
def station_device_fixture(
    tango_harness: TangoContextProtocol,
    station_name: str,
) -> tango.DeviceProxy:
    """
    Return the station Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param station_name: name of the station Tango device.

    :return: the station Tango device under test.
    """
    return tango_harness.get_device(station_name)


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> tango.DeviceProxy:
    """
    Return the subrack Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    tango_harness: TangoContextProtocol,
    tile_name: str,
) -> tango.DeviceProxy:
    """
    Return the tile Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param tile_name: name of the tile Tango device.

    :return: the tile Tango device under test.
    """
    return tango_harness.get_device(tile_name)


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "station_state",
        "subrack_state",
        "tile_state",
        timeout=2.0,
    )


def test_station(
    station_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
    tile_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test SPS station integration with subservient subrack and tile.

    :param station_device: the station Tango device under test.
    :param subrack_device: the subrack Tango device under test.
    :param tile_device: the tile Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    assert station_device.adminMode == AdminMode.OFFLINE
    assert subrack_device.adminMode == AdminMode.OFFLINE
    assert tile_device.adminMode == AdminMode.OFFLINE

    # Since the devices are in adminMode OFFLINE,
    # they are not even trying to monitor and control their components,
    # so they each report state as DISABLE.
    station_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["station_state"],
    )
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.DISABLE)
    subrack_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_state"],
    )
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.DISABLE)
    tile_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_state"],
    )
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)

    station_device.adminMode = AdminMode.ONLINE

    change_event_callbacks["station_state"].assert_change_event(tango.DevState.UNKNOWN)

    # Station stays in UNKNOWN state
    # because subrack and tile devices are still OFFLINE
    change_event_callbacks["station_state"].assert_not_called()

    tile_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)

    # Tile and station both stay in UNKNOWN state
    # because subrack is still OFFLINE
    change_event_callbacks["tile_state"].assert_not_called()
    change_event_callbacks["station_state"].assert_not_called()

    subrack_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.UNKNOWN)
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.ON)

    # Now that subrack is ONLINE, it reports itself ON, and the TPM to be OFF,
    # so MccsTile reports itself OFF
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

    # When the subracks are on but the tiles are off,
    # the station is in STANDBY.
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.STANDBY)
    change_event_callbacks["station_state"].assert_not_called()

    tile_device.On()

    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.ON)
