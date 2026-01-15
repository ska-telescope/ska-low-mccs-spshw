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

import json
import time
from typing import Any

import numpy as np
import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.test_tools import AttributeWaiter, TileWrapper, TpmStatus


@pytest.fixture(name="first_tile")
def first_tile_fixture(station_tiles: list[tango.DeviceProxy]) -> tango.DeviceProxy:
    """
    Fixture containing a proxy to the tile under test.

    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.

    :returns: a proxy to the tile under test.
    """
    return station_tiles[0]


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@scenario("features/tile.feature", "Flagged packets is ok")
def test_tile(stations_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that tests the tile device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario("features/tile.feature", "Tile synchronised state recovered after dev_init")
def test_tile_synchronised_recover(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the tile device.

    :param stations_devices_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario("features/tile.feature", "Tile initialised state recovered after dev_init")
def test_tile_initialised_recover(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the tile device.

    :param stations_devices_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool) -> None:
    """
    Skip the test if not in real context.

    :param hw_context: whether or not the current test is againt HW.
    """
    if not hw_context:
        pytest.skip(
            "This test requires real HW. "
            "We require that a bounce of the Pod "
            "Does not wipe the state of the device_under_test. "
            "Since the simulator is constructed in init_device its "
            "state is reset after a init_device."
        )


@given("an SPS deployment against a real context")
def check_against_real_context(true_context: bool) -> None:
    """
    Skip the test if not in real context.

    :param true_context: whether or not the current context is real.
    """
    if not true_context:
        pytest.skip("This test requires real context.")


@given("the SpsStation and tiles are ON")
def check_spsstation_state(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    stations_devices_exported: list[tango.DeviceProxy],
    station_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ENGINEERING AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param stations_devices_exported: Fixture containing the tango.DeviceProxy
        root for all sps devices.
    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    """
    sub_id1 = station.subscribe_event(
        "adminMode",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_adminmode"],
    )
    change_event_callbacks["device_adminmode"].assert_change_event(Anything)
    sub_id2 = station.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )
    change_event_callbacks["device_state"].assert_change_event(Anything)

    initial_mode = station.adminMode
    if initial_mode != AdminMode.ONLINE:
        station.adminMode = AdminMode.ONLINE
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

    station.unsubscribe_event(sub_id1)
    station.unsubscribe_event(sub_id2)

    # Sleep time to discover state.
    time.sleep(5)

    # TODO: An On from SpsStation level when ON will mean that
    # Any TPMs that are OFF will remain OFF due to ON being defined as
    # any TPM ON and the base class rejecting calls to ON if device is ON.
    # Therefore we are individually calling MccsTile.On() here.
    _initial_station_state = station.state()
    for tile in station_tiles:
        if tile.state() not in [tango.DevState.ON, tango.DevState.ALARM]:
            tile.on()
            AttributeWaiter(timeout=60).wait_for_value(
                tile,
                "state",
                tango.DevState.ON,
            )
    if (
        _initial_station_state != tango.DevState.ON
        and station.state() != tango.DevState.ON
    ):
        AttributeWaiter(timeout=60).wait_for_value(
            station, "state", tango.DevState.ON, lookahead=3
        )

    iters = 0
    while any(
        tile.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in station_tiles
    ):
        if iters >= 60:
            pytest.fail(
                "Not all tiles came ON: "
                f"""{[
                    (
                        tile.dev_name(),
                        tile.state(),
                        tile.tileprogrammingstate,
                        tile.lrcexecuting,
                        tile.lrcfinished
                    )
                    for tile in station_tiles
                ]}"""
            )
        time.sleep(1)
        iters += 1

    if station.state() != tango.DevState.ON:
        pytest.fail(f"SpsStation state {station.state()} != {tango.DevState.ON}")


@given("the Tile dropped packets is 0")
def tile_dropped_packets_is_0(first_tile: tango.DeviceProxy) -> None:
    """
    Verify that a device is in the desired state.

    :param first_tile: tile device under test.
    """
    try:
        assert first_tile.data_router_discarded_packets == json.dumps(
            {"FPGA0": [0, 0], "FPGA1": [0, 0]}
        )
    except Exception:  # pylint: disable=broad-except
        # Allow time to in case of first read.
        time.sleep(10)
        assert first_tile.data_router_discarded_packets == json.dumps(
            {"FPGA0": [0, 0], "FPGA1": [0, 0]}
        )


@given("the Tile is in a defined synchronised state", target_fixture="defined_state")
def tile_has_defined_synchronised_state(
    tile_device: tango.DeviceProxy,
) -> dict[str, Any]:
    """
    Verify that a device is in the desired state.

    :param tile_device: tile device under test.

    :returns: a fixture with the defined_state
    """
    defined_state = {
        "logical_tile_id": 2,
        "station_id": 2,
        "static_time_delays": np.array([5] * 32),
        # "csp_rounding": np.array([4] * 384), # THORN-207
        "channeliser_rounding": np.array([4] * 512),
    }
    tw = TileWrapper(tile_device)
    tw.set_state(programming_state=TpmStatus.SYNCHRONISED, **defined_state)
    return defined_state


@given("the Tile is available", target_fixture="tile_device")
def tile_device_fixture(
    station_tiles: list[tango.DeviceProxy],
) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the Tile device under test.

    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.

    :return: a ``tango.DeviceProxy`` to the Tile device under test.
    """
    station_tiles[-1].ping()
    return station_tiles[-1]


@given("the Tile is in a defined initialised state", target_fixture="defined_state")
def tile_has_defined_initialised_state(
    tile_device: tango.DeviceProxy,
) -> dict[str, Any]:
    """
    Verify that a device is in the desired state.

    :param tile_device: tile device under test.

    :returns: a fixture with the defined_state
    """
    defined_state = {
        "logical_tile_id": 2,
        "station_id": 2,
        "static_time_delays": np.array([6.25] * 32),
        # "csp_rounding": np.array([4] * 384),
        "channeliser_rounding": np.array([3] * 512),
    }
    tw = TileWrapper(tile_device)
    tw.set_state(
        programming_state=TpmStatus.INITIALISED,
        **defined_state,
    )
    return defined_state


@when("the Tile TANGO device is restarted")
def tile_is_restarted(tile_device: tango.DeviceProxy) -> None:
    """
    Restart the device.

    :param tile_device: tile device under test.
    """
    tile_device.set_timeout_millis(10000)
    tile_device.init()
    tile_device.set_timeout_millis(3000)


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


@then(parsers.cfparse("the Tile comes up in the defined {programming_state} state"))
def tile_is_in_state(
    tile_device: tango.DeviceProxy,
    defined_state: dict[str, Any],
    programming_state: str,
) -> None:
    """
    Assert that the tile comes up in the correct state.

    :param tile_device: tile device under test.
    :param defined_state: A fixture containing the defined state.
    :param programming_state: the programmingstate to check against.
    """
    AttributeWaiter(timeout=15).wait_for_value(
        tile_device,
        "tileProgrammingState",
        programming_state,
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )
    # There is an edge case here. When we are discovering state,
    # the configuration attributes will be read on the next poll.0
    # When driving the state the configuration will be read before
    # we arrive at state.
    time.sleep(5)
    tw = TileWrapper(tile_device)
    for item, val in defined_state.items():
        attr = getattr(tw, item)
        if isinstance(attr, np.ndarray):
            assert np.array_equal(attr, val), f"{item} does not match {val}"
        else:
            assert getattr(tw, item) == val, f"{item} does not match {val}"


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
