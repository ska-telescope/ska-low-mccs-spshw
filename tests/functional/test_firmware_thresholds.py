# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This file contains a test for setting of firmware thresholds."""
from __future__ import annotations

import json
import time
from typing import Any, Generator

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.test_tools import AttributeWaiter


@pytest.fixture(name="tile_device")
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


@pytest.fixture(name="initial_db_thresholds")
def initial_db_thresholds_fixture() -> dict[str, dict[str, Any]]:
    """
    Return a dictionary to set the db thresholds.

    :returns: a dictionary to set the db thresholds.
    """
    return {
        "temperatures": {"fpga1_alarm_threshold": 49.0},
        "voltages": {
            "MGT_AVCC_min_alarm_threshold": 1.0,
            "MGT_AVCC_max_alarm_threshold": 63.2,
        },
        "currents": {
            "FE0_mVA_min_alarm_threshold": 1.1,
            "FE0_mVA_max_alarm_threshold": 62.9,
        },
    }


@pytest.fixture(name="revert_db_thresholds")
def revert_db_thresholds_fixture() -> dict[str, dict[str, Any]]:
    """
    Return a dictionary to unset the db thresholds.

    :returns: a dictionary to unset the db thresholds.
    """
    return {
        "temperatures": {"fpga1_alarm_threshold": "Undefined"},
        "voltages": {
            "MGT_AVCC_min_alarm_threshold": "Undefined",
            "MGT_AVCC_max_alarm_threshold": "Undefined",
        },
        "currents": {
            "FE0_mVA_min_alarm_threshold": "Undefined",
            "FE0_mVA_max_alarm_threshold": "Undefined",
        },
    }


@pytest.fixture(name="device_threshold_updated")
def device_threshold_updated_fixture(
    tile_device: tango.DeviceProxy,
    initial_db_thresholds: dict[str, dict[str, Any]],
    revert_db_thresholds: dict[str, dict[str, Any]],
) -> Generator[None, None, None]:
    """
    Fixture to orchestrate the altering of thresholds in db.

    :param tile_device: the tile under test.
    :param initial_db_thresholds: the values initially populated
        in database
    :param revert_db_thresholds: the values to
        revert initial population

    :yields: To return cleanup
    """
    device_trl = tile_device.dev_name()
    db_connection = tango.Database()
    db_connection.put_device_attribute_property(device_trl, initial_db_thresholds)

    yield

    # Revert by ignoring in database
    db_connection.put_device_attribute_property(device_trl, revert_db_thresholds)

    # restart admin device, and wait to rediscover state
    tango.DeviceProxy(tile_device.adm_name()).restartserver()
    # Sleep to allow time for device to come up.
    time.sleep(6)
    AttributeWaiter(timeout=45).wait_for_value(
        tile_device,
        "tileProgrammingState",
        "Initialised",
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )


@scenario(
    "features/firmware_writes.feature", "Tile firmware thresholds checked after restart"
)
def test_device_reads_db_on_init() -> None:
    """Run a test scenario that tests the tile device."""


@scenario(
    "features/firmware_writes.feature",
    "Tile firmware thresholds checked after write",
)
def test_thresholds_checked_with_db_after_write() -> None:
    """Run a test scenario that tests the tile device."""


@scenario(
    "features/firmware_writes.feature",
    "Tile firmware thresholds unset in db",
)
def test_thresholds_unset_in_db() -> None:
    """Run a test scenario that tests the tile device."""


@scenario(
    "features/firmware_writes.feature",
    "Tile firmware thresholds written to match db",
)
def test_thresholds_written_to_match_db() -> None:
    """Run a test scenario that tests the tile device."""


@given("an SPS deployment against a real context")
def check_against_real_context(true_context: bool, station_label: str) -> None:
    """
    Skip the test if not in real context.

    :param true_context: whether or not the current context is real.
    :param station_label: Station to test against.
    """
    if not true_context:
        pytest.skip("This test requires real context.")
    if station_label == "stfc-ral-2":
        pytest.skip(
            "RAL hardware tests are passing inconsistently."
            "These tests will be skipped until proper cleanup is implemented."
        )


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
                f"Not all tiles came ON: {[tile.state() for tile in station_tiles]}"
            )
        time.sleep(1)
        iters += 1

    if station.state() != tango.DevState.ON:
        pytest.fail(f"SpsStation state {station.state()} != {tango.DevState.ON}")


@given("we reached into the database and altered a threshold")
def database_threshold_altered(
    device_threshold_updated: Generator[None, None, None]
) -> None:
    """
    Alter the database thresholds.

    :param device_threshold_updated: a fixture with setup teardown logic for
        altering thresholds.
    """
    # Note the device_threshold_updated
    # fixture contains the set up tear down logic here.
    print("Setting initial DB thresholds")


@when("the Tile TANGO device is restarted")
def tile_is_restarted(tile_device: tango.DeviceProxy) -> None:
    """
    Restart the device.

    :param tile_device: tile device under test.
    """
    tango.DeviceProxy(tile_device.adm_name()).restartserver()
    time.sleep(6)


@given("we have resynced with db")
def tile_is_resynced_with_db(tile_device: tango.DeviceProxy) -> None:
    """
    Resynced the device with the db.

    :param tile_device: tile device under test.
    """
    if tile_device.adminMode != AdminMode.ENGINEERING:
        tile_device.adminMode = AdminMode.ENGINEERING
    tile_device.UpdateThresholdCache()


@when("we write the thresholds for a different group")
def thresholds_written_for_different_attribute(tile_device: tango.DeviceProxy) -> None:
    """
    Write the threshold values in firmware.

    :param tile_device: the tile under test
    """
    assert tile_device.state() == tango.DevState.FAULT
    if tile_device.adminMode != AdminMode.ENGINEERING:
        tile_device.adminMode = AdminMode.ENGINEERING
    tile_device.FirmwareVoltageThresholds = json.dumps(
        {"MON_3V3_min_alarm_threshold": 0.0, "MON_3V3_max_alarm_threshold": 65.535}
    )


@when("we write the thresholds to ignore that group")
def write_thresholds_to_ignore_initial_values_set_in_db(
    tile_device: tango.DeviceProxy,
) -> None:
    """
    Write threshold to Undefined.

    :param tile_device: the tile under test

    """
    if tile_device.adminMode != AdminMode.ENGINEERING:
        tile_device.adminMode = AdminMode.ENGINEERING

    # Set the voltages to Undefined
    tile_device.FirmwareVoltageThresholds = json.dumps(
        {
            "MGT_AVCC_min_alarm_threshold": "Undefined",
            "MGT_AVCC_max_alarm_threshold": "Undefined",
        }
    )
    # Set the currents to Undefined
    tile_device.FirmwareCurrentThresholds = json.dumps(
        {
            "FE0_mVA_min_alarm_threshold": "Undefined",
            "FE0_mVA_max_alarm_threshold": "Undefined",
        }
    )
    # Set the temperatures to Undefined
    tile_device.FirmwareTemperatureThresholds = json.dumps(
        {"fpga1_alarm_threshold": "Undefined"}
    )


@when("we write the thresholds to match")
def write_thresholds_to_match(
    tile_device: tango.DeviceProxy,
) -> None:
    """
    Write threshold to match the database.

    :param tile_device: the tile under test

    """
    if tile_device.adminMode != AdminMode.ENGINEERING:
        tile_device.adminMode = AdminMode.ENGINEERING

    # Set the voltages to Undefined
    tile_device.FirmwareVoltageThresholds = json.dumps(
        {
            "MGT_AVCC_min_alarm_threshold": 1.0,
            "MGT_AVCC_max_alarm_threshold": 63.2,
        }
    )
    # Set the currents to Undefined
    tile_device.FirmwareCurrentThresholds = json.dumps(
        {
            "FE0_mVA_min_alarm_threshold": 1.1,
            "FE0_mVA_max_alarm_threshold": 62.9,
        }
    )
    # Set the temperatures to Undefined
    tile_device.FirmwareTemperatureThresholds = json.dumps(
        {"fpga1_alarm_threshold": 49.0}
    )


@then("the Tile reports it has configuration mismatch")
def check_for_configuration_missmatch(
    tile_device: tango.DeviceProxy, change_event_callbacks: MockTangoEventCallbackGroup
) -> None:
    """
    Check for configuration missmatch.

    :param tile_device: the tile under test
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    AttributeWaiter(timeout=45).wait_for_value(
        tile_device,
        "tileProgrammingState",
        "Initialised",
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )
    assert tile_device.state() == tango.DevState.FAULT

    sub_id = tile_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )

    change_event_callbacks["device_state"].assert_change_event(tango.DevState.FAULT)
    change_event_callbacks["device_state"].assert_not_called()

    tile_device.unsubscribe_event(sub_id)


@then("the Tile reports it has no configuration mismatch")
def tile_reports_on(
    tile_device: tango.DeviceProxy, change_event_callbacks: MockTangoEventCallbackGroup
) -> None:
    """
    Check that the tile is ON.

    :param tile_device: the tile under test
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    AttributeWaiter(timeout=45).wait_for_value(
        tile_device,
        "tileProgrammingState",
        "Initialised",
        lookahead=2,  # UNKNOWN first hence lookahead == 2
    )
    assert tile_device.state() == tango.DevState.ON
    sub_id = tile_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )

    change_event_callbacks["device_state"].assert_change_event(tango.DevState.ON)
    change_event_callbacks["device_state"].assert_not_called()

    tile_device.unsubscribe_event(sub_id)
