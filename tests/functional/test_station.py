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
from typing import Any, Callable, Generator

import numpy as np
import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import verify_bandpass_state
from tests.harness import DEFAULT_STATION_LABEL, get_bandpass_daq_name
from tests.test_tools import wait_for_lrc_result

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
        "daq_xPolBandpass",
        "daq_yPolBandpass",
        "data_received_callback",
        "tile_adminMode",
        "device_state",
        "device_adminmode",
        "tile_programming_state",
        "tile_0_state",
        "tile_1_state",
        "tile_2_state",
        "tile_3_state",
        "tile_4_state",
        "tile_5_state",
        "tile_6_state",
        "tile_7_state",
        "tile_0_programming_state",
        "tile_1_programming_state",
        "tile_2_programming_state",
        "tile_3_programming_state",
        "tile_4_programming_state",
        "tile_5_programming_state",
        "tile_6_programming_state",
        "tile_7_programming_state",
        timeout=300.0,
    )


@scenario("features/station.feature", "Synchronising time stamping")
def test_station_syncs_and_bandpasses_start(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the station device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/station.feature",
    "TPMs transition directly from OFF to ON to Synchronised",
)
def test_station_on_strict(stations_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that tests the station device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/station.feature",
    "TPMs transition from OFF to ON to Synchronised (workaround allowed)",
)
def test_station_on_workaround(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the station device.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/station.feature",
    "Standby commanded during Init takes all TPMs to Off (SKB-1402 regression)",
)
def test_standby_during_init(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
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


@given("the station and its tiles are synchronised")
def check_station_and_tiles_synchronised(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    stations_devices_exported: list[tango.DeviceProxy],
    station_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON and all its tiles are Synchronised.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    """
    check_spsstation_state(
        station, change_event_callbacks, stations_devices_exported, station_tiles
    )

    if any(status != "Synchronised" for status in station.tileProgrammingState):
        station.Initialise()

    station_is_synced(station)


@given(parsers.parse("the SpsStation OnWorkaroundFlag is set to {flag}"))
def check_spsstation_on_workaround_flag_param(
    station: tango.DeviceProxy, flag: str
) -> Generator:
    """
    Parametrised step to set the SpsStation OnWorkaroundFlag.

    :param station: a proxy to the station under test.
    :param flag: Boolean value to set OnWorkaroundFlag.

    :yields: Control to the test then cleans up afterwards.
    """
    initial_workaround_flag = station.OnWorkaround
    flag_bool = flag.lower() == "true"
    if station.OnWorkaround != flag_bool:
        station.OnWorkaround = flag_bool

    yield

    station.OnWorkaround = initial_workaround_flag


@when("the SpsStation is turned ON")
def turn_station_on(station: tango.DeviceProxy) -> None:
    """
    Turn station on.

    :param station: station device under test.
    """
    ([result_code], [_]) = station.On()
    assert result_code == ResultCode.QUEUED


@when("the station is initialised")
def station_not_synched(
    station: tango.DeviceProxy,
    bandpass_daq_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Verify that a device is in the desired state.

    Subscribe to bandpass attributes before Initialise so we can
    detect updates emitted during station bring-up.

    :param station: station device under test.
    :param bandpass_daq_device: a proxy to the bandpass DAQ device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    bandpass_daq_device.subscribe_event(
        "xPolBandpass",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["daq_xPolBandpass"],
    )
    bandpass_daq_device.subscribe_event(
        "yPolBandpass",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["daq_yPolBandpass"],
    )
    # Consume initial subscription snapshots so subsequent assertions
    # are about updates that happen during/after initialise.
    change_event_callbacks["daq_xPolBandpass"].assert_change_event(
        Anything, consume_nonmatches=True
    )
    change_event_callbacks["daq_yPolBandpass"].assert_change_event(
        Anything, consume_nonmatches=True
    )

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
def all_tpms_directly_transition_to_synchronised_state(
    station_tiles: list[tango.DeviceProxy],
    station: tango.DeviceProxy,
    wait_for_lrcs_to_finish: Callable,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Assert all TPMs transition to Synchronised.

    We expect the state transitions to happen exactly once.

    :param station_tiles: List of TPM DeviceProxies.
    :param station: Station under test.
    :param wait_for_lrcs_to_finish: A callable to wait for long running commands to
        finish.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    for i, tile in enumerate(station_tiles):
        tile.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks[f"tile_{i}_state"],
        )
        tile.subscribe_event(
            "tileprogrammingstate",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks[f"tile_{i}_programming_state"],
        )
    wait_for_lrcs_to_finish(
        [station], timeout=300
    )  # Explicitly wait for Station.On to complete. ~ 2min
    for i, tile in enumerate(station_tiles):
        # Expect OFF -> ON but we might miss some events.
        # So long as the Tile is ON and doesn't go OFF again that's ok.
        try:
            change_event_callbacks[f"tile_{i}_state"].assert_change_event(
                tango.DevState.ON
            )
        except AssertionError:
            assert tile.state() == tango.DevState.ON

        # Expect NotProgrammed -> Programmed -> Initialised -> Synchronised
        # If these appear strictly in order then we know the TPM didn't powercycle.
        for tile_programming_state in [
            "Off",
            "NotProgrammed",
            "Programmed",
            "Initialised",
            "Synchronised",
        ]:
            change_event_callbacks[f"tile_{i}_programming_state"].assert_change_event(
                tile_programming_state
            )
    for tile in station_tiles:
        assert tile.state() == tango.DevState.ON
        assert tile.tileProgrammingState == "Synchronised"


@then("all TPMs eventually transition to Synchronised state")
def all_tpms_eventually_transition_to_synchronised_state(
    station_tiles: list[tango.DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check all TPMs reach Synchronised state.

    We expect the state transitions to happen at least once.

    :param station_tiles: List of TPM DeviceProxies.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    for tile in station_tiles:
        tile.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["device_state"],
        )
        tile.subscribe_event(
            "tileprogrammingstate",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        # Expect OFF -> ON eventually.
        change_event_callbacks["device_state"].assert_change_event(
            tango.DevState.ON, consume_nonmatches=True, lookahead=50
        )
        # Expect to get to Synchronised eventually.
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Synchronised", lookahead=50, consume_nonmatches=True
        )
    # All tiles must still end up ON and Synchronised.
    for tile in station_tiles:
        assert tile.state() == tango.DevState.ON
        assert tile.tileProgrammingState == "Synchronised"


@pytest.fixture(name="bandpass_daq_device")
def bandpass_daq_device_fixture(
    station_label: str | None,
) -> tango.DeviceProxy:
    """
    Return a proxy to the bandpass DAQ receiver device.

    :param station_label: the label of the station under test.

    :returns: a ``tango.DeviceProxy`` to the bandpass DAQ device.
    """
    return tango.DeviceProxy(
        get_bandpass_daq_name(station_label or DEFAULT_STATION_LABEL)
    )


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


@then("the bandpass daq is receiving bandpasses")
def bandpass_daq_receiving(
    bandpass_daq_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the bandpass DAQ has an active bandpass monitor and is receiving data.

    :param bandpass_daq_device: a proxy to the bandpass DAQ device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    verify_bandpass_state(bandpass_daq_device, True)

    change_event_callbacks["daq_xPolBandpass"].assert_change_event(
        Anything, consume_nonmatches=True
    )
    change_event_callbacks["daq_yPolBandpass"].assert_change_event(
        Anything, consume_nonmatches=True
    )

    assert np.count_nonzero(bandpass_daq_device.xPolBandpass) > 0
    assert np.count_nonzero(bandpass_daq_device.yPolBandpass) > 0


@when("the SpsStation is instructed to Init, then to Standby as soon as possible")
def init_then_standby_on_unknown(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    command_info: dict[str, Any],
) -> None:
    """
    Call Tango Init, then Standby as soon as the station re-enters UNKNOWN.

    This reproduces the SKB-1402 race: Init tears down and rebuilds the
    station's communication with its TPMs, cycling the device state through
    UNKNOWN -> DISABLED -> INIT -> DISABLED -> UNKNOWN. Commanding Standby
    the moment we re-enter UNKNOWN used to hang if a TPM read was in flight
    when the TPM lost power.

    :param station: station device under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param command_info: a dict in which to store command IDs.
    """
    station.Init()

    for expected_state in [
        tango.DevState.UNKNOWN,
        tango.DevState.DISABLED,
        tango.DevState.INIT,
        tango.DevState.DISABLED,
        tango.DevState.UNKNOWN,
    ]:
        change_event_callbacks["device_state"].assert_change_event(expected_state)

    ([result_code], [command_id]) = station.Standby()
    assert result_code == ResultCode.QUEUED
    command_info["Standby"] = command_id


@then("the Standby command completed successfully")
def standby_command_completed_successfully(
    station: tango.DeviceProxy, command_info: dict[str, Any]
) -> None:
    """
    Check the Standby command completed with ResultCode.OK.

    :param station: station device under test.
    :param command_info: a dict containing command IDs.
    """
    wait_for_lrc_result(
        device=station,
        uid=command_info["Standby"],
        expected_result=ResultCode.OK,
        timeout=300,
    )


@then("all TPMs transition to Off state")
def all_tpms_transition_to_off(station_tiles: list[tango.DeviceProxy]) -> None:
    """
    Check all TPMs reach OFF state.

    :param station_tiles: List of TPM DeviceProxies.
    """
    deadline = time.time() + 300
    while time.time() < deadline:
        if all(tile.state() == tango.DevState.OFF for tile in station_tiles):
            break
        time.sleep(2)
    else:
        pytest.fail(
            "Not all tiles transitioned to OFF: "
            f"""{[(tile.dev_name(), tile.state()) for tile in station_tiles]}"""
        )
