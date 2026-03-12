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
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "pdu_state",
        "subrack_state",
        "subrack_fan_mode",
        "subrack_fan_speeds",
        "subrack_fan_speeds_percent",
        "subrack_tpm_power_state",
        "subrack_tpm_present",
        "daq_state",
        "daq_long_running_command_status",
        "daq_long_running_command_result",
        "daq_xPolBandpass",
        "daq_yPolBandpass",
        "data_received_callback",
        "tile_adminMode",
        "device_state",
        "device_adminmode",
        "tile_programming_state",
        timeout=300.0,
    )


@scenario("features/station.feature", "Synchronising time stamping")
def test_tile(stations_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that tests the station device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool, station_label: str) -> None:
    """
    Skip the test if not against HW.

    :param hw_context: whether or not the current context is against real HW.
    :param station_label: Station to test against.
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
                "Not all tiles came ON: "
                f"""{[
                    (tile.dev_name(), tile.state(), tile.tileprogrammingstate)
                    for tile in station_tiles
                ]}"""
            )

        time.sleep(1)
        iters += 1

    if station.state() != tango.DevState.ON:
        pytest.fail(f"SpsStation state {station.state()} != {tango.DevState.ON}")


@given("the SpsStation is STANDBY")
def check_spsstation_state_standby(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    stations_devices_exported: list[tango.DeviceProxy],
    station_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is STANDBY, and all devices are in ONLINE AdminMode.

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

    if station.state() != tango.DevState.STANDBY:
        state_callback = MockTangoEventCallbackGroup("state", timeout=300)
        station.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            state_callback["state"],
        )
        state_callback.assert_change_event("state", Anything, consume_nonmatches=True)
        station.Standby()
        state_callback.assert_change_event(
            "state", tango.DevState.STANDBY, consume_nonmatches=True, lookahead=3
        )

    iters = 0
    while any(tile.state() not in [tango.DevState.OFF] for tile in station_tiles):
        if iters >= 60:
            pytest.fail(
                "Not all tiles came OFF: "
                f"""{[
                    (tile.dev_name(), tile.state(), tile.tileprogrammingstate)
                    for tile in station_tiles
                ]}"""
            )

        time.sleep(1)
        iters += 1

    if station.state() != tango.DevState.STANDBY:
        pytest.fail(f"SpsStation state {station.state()} != {tango.DevState.STANDBY}")


@when("the SpsStation is turned ON")
def turn_station_on(station: tango.DeviceProxy) -> None:
    """
    Turn station on.

    :param station: station device under test.
    """
    station.On()


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


@then("all TPMs directly transition to Synchronised state")
def all_tpms_transition_to_synchronised_state(
    station_tiles: list[tango.DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Assert all TPMs transition to Synchronised.

    :param station_tiles: List of TPM DeviceProxies.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    for tile in station_tiles:
        # Sub to state change event.
        tile.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["device_state"],
        )
        # Expect OFF -> ON
        for state in [tango.DevState.UNKNOWN, tango.DevState.OFF, tango.DevState.ON]:
            change_event_callbacks["device_state"].assert_change_event(state)
        # Sub to tileprogrammingstate change event
        tile.subscribe_event(
            "tileprogrammingstate",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        # Expect Unprogrammed -> Programmed -> Initialised -> Synchronised
        for tile_programming_state in [
            "Unprogrammed",
            "Programmed",
            "Initialised",
            "Synchronised",
        ]:
            change_event_callbacks["tile_programming_state"].assert_change_event(
                tile_programming_state
            )
    for tile in station_tiles:
        assert tile.state() == tango.DevState.ON
        assert tile.tileProgrammingState == "Synchronised"
        # If state goes backwards in this chain then fail.
    change_event_callbacks.assert_not_called()


@then("all TPMs eventually transition to Synchronised state")
def all_tpms_eventually_transition_to_synchronised_state(
    station_tiles: list[tango.DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check all TPMs reach Synchronised state.

    :param station_tiles: List of TPM DeviceProxies.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    for tile in station_tiles:
        # Sub to state change event.
        tile.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["device_state"],
        )
        # Expect OFF -> ON
        change_event_callbacks["device_state"].assert_change_event(
            tango.DevState.ON, consume_nonmatches=True, lookahead=30
        )
        # Sub to tileprogrammingstate change event
        tile.subscribe_event(
            "tileprogrammingstate",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        # Expect Unprogrammed -> Programmed -> Initialised -> Synchronised
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Synchronised"
        )
    for tile in station_tiles:
        assert tile.state() == tango.DevState.ON
        assert tile.tileProgrammingState == "Synchronised"


@then("the station becomes synchronised")
def station_is_synced(station: tango.DeviceProxy) -> None:
    """
    Check the station are synced.

    :param station: station device under test.
    """
    deadline = time.time() + 300  # seconds
    print("Waiting for all remaining unprogrammed tiles Synchronise")
    while time.time() < deadline:
        time.sleep(2)

        if all(status == "Synchronised" for status in station.tileProgrammingState):
            break
    else:
        pytest.fail("Timeout in waiting for tiles to Synchronise")
