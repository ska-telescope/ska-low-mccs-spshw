# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains a test for the station syncronisation.

Depending on your exact deployment the individual tests may or may not be run.
This test just checks that anything which can run passes.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode, HealthState
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.test_tools import AttributeWaiter, TpmStatus

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@scenario("features/station.feature", "Synchronising time stamping")
def test_tile(stations_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that tests the station device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/station_health.feature",
    "Station health is failed when Tiles are not synchronized",
)
def test_health_failed(stations_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that tests the station device health.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool) -> None:
    """
    Skip the test if not against HW.

    :param hw_context: whether or not the current context is against real HW.
    """
    if not hw_context:
        pytest.skip("This test requires real HW.")


@given("the SpsStation is ON")
def check_spsstation_state(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    stations_devices_exported: list[tango.DeviceProxy],
    station_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ONLINE AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    """
    station.subscribe_event(
        "adminmode",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_adminmode"],
    )
    change_event_callbacks.assert_change_event(
        "device_adminmode", Anything, consume_nonmatches=True
    )
    station.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )
    change_event_callbacks.assert_change_event("device_state", Anything)
    initial_mode = station.adminmode
    if initial_mode != AdminMode.ONLINE:
        station.adminmode = AdminMode.ONLINE
        change_event_callbacks["device_adminmode"].assert_change_event(AdminMode.ONLINE)
        if initial_mode == AdminMode.OFFLINE:
            change_event_callbacks["device_state"].assert_change_event(
                tango.DevState.UNKNOWN
            )

    device_bar_station = [
        dev for dev in stations_devices_exported if dev.dev_name() != station.dev_name()
    ]

    for device in device_bar_station:
        if device.adminmode != AdminMode.ONLINE:
            device.adminmode = AdminMode.ONLINE

    if initial_mode == AdminMode.OFFLINE:
        change_event_callbacks["device_state"].assert_change_event(Anything)

    time.sleep(5)

    if any(
        device.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for device in stations_devices_exported
    ):
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
        for tile in station_tiles
    ):
        if iters >= 60:
            pytest.fail(
                f"Not all tiles came ON: {[tile.state() for tile in station_tiles]}"
            )
        time.sleep(1)
        iters += 1

    if station.state() != tango.DevState.ON:
        pytest.fail(f"SpsStation state {station.state()} != {tango.DevState.ON}")


@when("the station is initialised")
def station_not_synched(station: tango.DeviceProxy) -> None:
    """
    Verify that a device is in the desired state.

    :param station: station device under test.
    """
    station.Initialise()


@when("the station is ordered to synchronise")
def sync_station(station: tango.DeviceProxy) -> None:
    """
    Sync the station.

    :param station: station device under test.
    """
    start_time = datetime.strftime(
        datetime.fromtimestamp(int(time.time()) + 2), RFC_FORMAT
    )
    station.StartAcquisition(json.dumps({"start_time": start_time}))


@then("the station becomes synchronised")
def station_is_synced(station: tango.DeviceProxy) -> None:
    """
    Check the station are synced.

    :param station: station device under test.
    """
    deadline = time.time() + 120  # seconds
    print("Waiting for all remaining unprogrammed tiles Synchronise")
    while time.time() < deadline:
        time.sleep(2)

        if all(status == "Synchronised" for status in station.tileProgrammingState):
            break
    else:
        pytest.fail("Timeout in waiting for tiles to Synchronise")


@when(
    parsers.cfparse(
        "Device Tile {tile_id:Number} is restarted", extra_types={"Number": int}
    )
)
def restart_device(exported_tiles: list[tango.DeviceProxy], tile_id: int) -> None:
    """
    Check the station are synced.

    :param exported_tiles: the tiles
    :param tile_id: the name of the device to restart
    """
    tile_device = exported_tiles[tile_id - 1]
    tile_device.init()


@then(
    parsers.cfparse(
        "Tile {tile_id:Number} is not in {programming_state:string} state",
        extra_types={"Number": int, "string": str},
    )
)
def check_tile_sync_state(
    exported_tiles: list[tango.DeviceProxy],
    tile_id: int,
    programming_state: str,
) -> None:
    """
    Verify that a tile is in a desired syncronized state.

    :param exported_tiles: the tiles
    :param tile_id: the name of the device to restart
    :param programming_state: the seried Sync state
    """
    tile_device = exported_tiles[tile_id - 1]
    sync_state = TpmStatus.SYNCHRONISED
    AttributeWaiter(timeout=15).wait_for_value(
        tile_device,
        "tileProgrammingState",
        sync_state,
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )


@then(
    parsers.cfparse(
        "SpsStation is in {health_state:string} state",
        extra_types={"Number": int, "string": str},
    )
)
def check_station_health_state(
    station: tango.DeviceProxy,
    health_state: str,
) -> None:
    """
    Verify that a tile is in a desired syncronized state.

    :param station: the tiles
    :param health_state: the seried Sync state
    """
    health_state_value = HealthState.FAILED
    AttributeWaiter(timeout=15).wait_for_value(
        station,
        "healthState",
        health_state_value,
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )
