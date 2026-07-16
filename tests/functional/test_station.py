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
import threading
import random
import time
from collections.abc import Iterator
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
STRESS_TEST_PHASE_DURATION = 120.0  # seconds
NOF_CHANNEL_GROUPS = 48


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@pytest.fixture(name="tile_inheriting")
def tile_inheriting_fixture(station_tiles: list[tango.DeviceProxy]) -> Iterator[None]:
    """
    Temporarily enable ``inheritmodes`` for all station tiles.

    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.

    :yields: facilitate teardown
    """
    initial_inherit = [tile.inheritmodes for tile in station_tiles]

    for tile in station_tiles:
        tile.inheritmodes = True

    time.sleep(1)

    yield

    for tile, initial_mode in zip(station_tiles, initial_inherit):
        tile.inheritmodes = initial_mode


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
    "Stress testing the interface does not cause lock contention (SKB-1440 regression)",
)
def test_lock_contention_not_observed(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that stress tests the SpsStation/Tile interface.

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
def ensure_spsstation_state_on(
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
    ensure_spsstation_state_on(
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
    [result_code], [_] = station.On()
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


@pytest.fixture(name="stress_test_failures")
def stress_test_failures_fixture() -> list[str]:
    """
    Fixture to store failures observed while stress testing the interface.

    :returns: an empty list to append failure descriptions to.
    """
    return []


def _poll_all_tile_attributes(
    station_tiles: list[tango.DeviceProxy],
    excluded_tile_attributes: list[str],
    failures: list[str],
    stop_event: threading.Event,
) -> None:
    """
    Continuously poll every attribute on every tile until told to stop.

    This is used as a background stressor for the TPM hardware lock while
    other operations are driven against the station, per SKB-1440.

    :param station_tiles: List of TPM DeviceProxies.
    :param excluded_tile_attributes: Attribute names to skip, as they are
        known to fail for reasons unrelated to hardware lock contention.
    :param failures: a list to append failure descriptions to.
    :param stop_event: an event used to signal the loop to stop.
    """
    tile_exclusions = {}
    for i, tile in enumerate(station_tiles):
        exclusions = set(excluded_tile_attributes)
        if i != len(station_tiles) - 1:
            # These are documented by the API as do not use unless final tile.
            exclusions.update(
                {
                    "fpga0_station_beamformer_flagged_count",
                    "fpga1_station_beamformer_flagged_count",
                }
            )
        tile_exclusions[tile.dev_name()] = exclusions

    while not stop_event.is_set():
        for tile in station_tiles:
            exclusions = tile_exclusions[tile.dev_name()]
            try:
                attribute_names = tile.get_attribute_list()
            except tango.DevFailed as error:
                failures.append(
                    f"get_attribute_list failed on {tile.dev_name()}: {error}"
                )
                continue
            for attr in attribute_names:
                if attr in exclusions:
                    continue
                try:
                    getattr(tile, attr)
                except tango.DevFailed as error:
                    failures.append(f"Failed to read {tile.dev_name()}.{attr}: {error}")


def _wait_for_preadu_levels(station: tango.DeviceProxy, timeout: float = 60.0) -> Any:
    """
    Wait for the SpsStation preaduLevels attribute to populate.

    :param station: station device under test.
    :param timeout: the maximum time to wait, in seconds.

    :raises TimeoutError: if preaduLevels does not populate in time.

    :return: the populated preaduLevels values.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        levels = station.preaduLevels
        if levels is not None and len(levels) > 0:
            return levels
        time.sleep(1)
    raise TimeoutError("Timed out waiting for preaduLevels to populate on SpsStation")


def _stress_initialise_and_preadu_levels(
    station: tango.DeviceProxy,
    failures: list[str],
    duration: float = STRESS_TEST_PHASE_DURATION,
) -> None:
    """
    Repeatedly Initialise the station and read/write preaduLevels.

    :param station: station device under test.
    :param failures: a list to append failure descriptions to.
    :param duration: how long to run this phase for, in seconds.
    """
    deadline = time.time() + duration
    while time.time() < deadline:
        try:
            [result_code], [command_id] = station.Initialise()
            if result_code != ResultCode.QUEUED:
                failures.append(f"Initialise not queued, got {result_code}")
                continue
            wait_for_lrc_result(
                device=station,
                uid=command_id,
                expected_result=ResultCode.OK,
                timeout=60,
            )
        except (tango.DevFailed, TimeoutError, ValueError) as error:
            failures.append(f"Initialise failed: {error}")
            continue

        try:
            original_levels = list(_wait_for_preadu_levels(station))
        except TimeoutError as error:
            failures.append(str(error))
            continue

        raised_levels = [level + 1 for level in original_levels]
        try:
            station.preaduLevels = raised_levels
            station.preaduLevels = original_levels
        except tango.DevFailed as error:
            failures.append(f"preaduLevels write failed: {error}")


def _stress_beamformer_running_for_channels(
    station: tango.DeviceProxy,
    failures: list[str],
    duration: float = STRESS_TEST_PHASE_DURATION,
) -> None:
    """
    Repeatedly call BeamformerRunningForChannels for every channel group.

    :param station: station device under test.
    :param failures: a list to append failure descriptions to.
    :param duration: how long to run this phase for, in seconds.
    """
    deadline = time.time() + duration
    while time.time() < deadline:
        for channel_group in range(NOF_CHANNEL_GROUPS):
            try:
                station.command_inout(
                    "BeamformerRunningForChannels",
                    json.dumps({"channel_groups": [channel_group]}),
                )
            except tango.DevFailed as error:
                failures.append(
                    "BeamformerRunningForChannels failed for channel group "
                    f"{channel_group}: {error}"
                )
            if time.time() >= deadline:
                break


@when("we stress test the interface")
def stress_test_interface(
    station: tango.DeviceProxy,
    station_tiles: list[tango.DeviceProxy],
    excluded_tile_attributes: list[str],
    stress_test_failures: list[str],
) -> None:
    """
    Stress test the SpsStation/Tile interface to check for lock contention.

    A background thread continuously polls every attribute on every tile
    while, concurrently, the station is repeatedly Initialised and its
    preaduLevels are read and written, followed by repeated
    BeamformerRunningForChannels queries. This reproduces the conditions of
    SKB-1440, where prolonged holding of the TPM hardware lock by one
    operation starved out others.

    :param station: station device under test.
    :param station_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    :param excluded_tile_attributes: A list of attributes to not poll.
    :param stress_test_failures: a list to record failure descriptions in.
    """
    assert station_tiles, "No station tiles were discovered"

    stop_polling = threading.Event()
    poll_thread = threading.Thread(
        target=_poll_all_tile_attributes,
        args=(
            station_tiles,
            excluded_tile_attributes,
            stress_test_failures,
            stop_polling,
        ),
        daemon=True,
    )
    poll_thread.start()

    try:
        _stress_initialise_and_preadu_levels(station, stress_test_failures)
        _stress_beamformer_running_for_channels(station, stress_test_failures)
    finally:
        stop_polling.set()
        poll_thread.join(timeout=30)


@then("we do not get any failures")
def check_no_failures(stress_test_failures: list[str]) -> None:
    """
    Assert that no failures were observed during the stress test.

    :param stress_test_failures: a list of failure descriptions collected
        during the stress test.
    """
    assert not stress_test_failures, (
        f"{len(stress_test_failures)} failure(s) observed during stress test:\n"
        + "\n".join(stress_test_failures)
    )


@when("we trigger skb-1402")
def trigger_skb_1402(
    station: tango.DeviceProxy,
    tile_inheriting: Any,
    change_event_callbacks: MockTangoEventCallbackGroup,
    command_info: dict[str, Any],
) -> None:
    """
    Call Tango Init, then Standby as soon as the station re-enters UNKNOWN.

    This reproduces the SKB-1402 race: Init tears down and rebuilds the
    station's communication with its TPMs, cycling the device state through
    UNKNOWN -> DISABLE -> INIT -> DISABLE -> UNKNOWN. Commanding Standby
    the moment we re-enter UNKNOWN used to hang if a TPM read was in flight
    when the TPM lost power.

    :param station: station device under test.
    :param tile_inheriting: fixture to ensure tiles are inheriting.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param command_info: a dict in which to store command IDs.
    """
    state_callback = MockTangoEventCallbackGroup(
        "state",
        timeout=15,
    )
    station.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        state_callback["state"],
    )
    state_callback.assert_change_event("state", tango.DevState.ON)

    station.Init()

    # Command can be invoked as soon as we restart and enter UNKNOWN.
    for expected_state in [
        tango.DevState.UNKNOWN,
        tango.DevState.DISABLE,
        tango.DevState.INIT,
        tango.DevState.DISABLE,
        tango.DevState.UNKNOWN,
    ]:
        state_callback.assert_change_event("state", expected_state)

    for i in range(10):
        try:
            time.sleep(random.randrange(1, 10) / 50)
            [result_code], [command_id] = station.Standby()
            break
        except tango.DevFailed:
            time.sleep(0.1)

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
    assert station_tiles, "No station tiles were discovered"
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
