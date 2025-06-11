# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains a test for the tile dropped packets test.

Depending on your exact deployment the individual tests may or may not be run.
This test just checks that anything which can run passes.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_sps_station_name


@pytest.fixture(name="station")
def station_fixture(available_stations: list[str]) -> tango.DeviceProxy:
    """
    Fixture containing a proxy to the station under test.

    :param available_stations: the names of the stations we are testing against.

    :returns: a proxy to the station under test.
    """
    return tango.DeviceProxy(get_sps_station_name(available_stations[-1]))


@pytest.fixture(name="first_tile")
def first_tile_fixture(exported_tiles: list[tango.DeviceProxy]) -> tango.DeviceProxy:
    """
    Fixture containing a proxy to the tile under test.

    :param exported_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.

    :returns: a proxy to the tile under test.
    """
    return exported_tiles[0]


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@scenario("features/tile.feature", "Flagged packets is ok")
def test_tile(sps_devices_trl_exported: list[str]) -> None:
    """
    Run a test scenario that tests the tile device.

    :param sps_devices_trl_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in [tango.DeviceProxy(trl) for trl in sps_devices_trl_exported]:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool) -> None:
    """
    Skip the test if not against HW.

    :param hw_context: whether or not the current context is against real HW.
    """
    if not hw_context:
        pytest.skip("This test requires real HW.")


@given("the SpsStation and tiles are ON")
def check_spsstation_state(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    sps_devices_trl_exported: list[str],
    exported_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ENGINEERING AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param sps_devices_trl_exported: Fixture containing the trl
        root for all sps devices.
    :param exported_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    """
    station.subscribe_event(
        "adminmode",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_adminmode"],
    )
    change_event_callbacks.assert_change_event("device_adminmode", Anything)
    station.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )
    change_event_callbacks.assert_change_event("device_state", Anything)
    initial_mode = station.adminmode
    if station.adminmode != initial_mode:
        station.adminmode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event("device_adminmode", AdminMode.ONLINE)
        if initial_mode == AdminMode.OFFLINE:
            change_event_callbacks.assert_change_event(
                "device_state", tango.DevState.UNKNOWN
            )
            change_event_callbacks.assert_change_event("device_state", Anything)

    for device in [tango.DeviceProxy(trl) for trl in sps_devices_trl_exported]:
        if device.adminmode != AdminMode.ONLINE:
            device.adminmode = AdminMode.ONLINE

    if station.state() != tango.DevState.ON:
        state_callback = MockTangoEventCallbackGroup("state", timeout=300)
        station.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            state_callback["state"],
        )
        state_callback.assert_change_event("state", Anything, consume_nonmatches=True)
        station.on()
        state_callback.assert_change_event(
            "state", tango.DevState.ON, consume_nonmatches=True, lookahead=3
        )

    iters = 0
    while any(
        tile.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in exported_tiles
    ):
        if iters >= 60:
            pytest.fail(
                f"Not all tiles came ON: {[tile.state() for tile in exported_tiles]}"
            )
        time.sleep(1)
        iters += 1

    assert station.state() == tango.DevState.ON


@given("the Tile dropped packets is 0")
def tile_dropped_packets_is_0(tile_device: tango.DeviceProxy) -> None:
    """
    Verify that a device is in the desired state.

    :param tile_device: tile device under test.
    """
    assert (
        tile_device.data_router_discarded_packets
        == '{"FPGA0": [0, 0], "FPGA1": [0, 0]}'
    )


@when("the Tile data acquisition is started")
def tile_start_data_acq(
    first_tile: tango.DeviceProxy,
) -> None:
    """
    Start data acquisition.

    :param first_tile: tile device under test.
    """
    first_tile.startacquisition("{}")
    timeout = 0
    while timeout < 60:
        if first_tile.tileprogrammingstate == "Synchronised":
            break
        time.sleep(1)
        timeout = timeout + 1
    assert timeout <= 60, "Tiles didn't synchronise"


@then("the Tile dropped packets is 0 after 30 seconds")
def tile_dropped_packets_stays_0(
    first_tile: tango.DeviceProxy,
) -> None:
    """
    Assert that the number of dropped packets is 0.

    :param first_tile: tile device under test.
    """
    timeout = 0
    time.sleep(5)
    while timeout < 30:
        if (
            first_tile.data_router_discarded_packets
            == '{"FPGA0": [0, 0], "FPGA1": [0, 0]}'
        ):
            break
        time.sleep(1)
        timeout = timeout + 1
    assert (
        first_tile.data_router_discarded_packets == '{"FPGA0": [0, 0], "FPGA1": [0, 0]}'
    )
