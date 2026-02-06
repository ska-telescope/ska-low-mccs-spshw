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
from typing import Any, Generator

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


@scenario(
    "features/tile.feature",
    "Apply and read back staged calibration coefficients per antenna",
)
def test_apply_read_staged_cal_coeffs_antenna(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the tile device.

    In this test we use LoadCalibrationCoefficients which loads on a per-antenna basis

    :param stations_devices_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/tile.feature",
    "Apply and read back staged calibration coefficients per channel",
)
def test_apply_read_staged_cal_coeffs_channel(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests the tile device.

    In this test we use LoadCalibrationCoefficientsForChannels which loads on a
        per-channel basis

    :param stations_devices_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@scenario(
    "features/tile.feature",
    "Apply calibration, verify, switch banks, verify, revert",
)
def test_apply_switch_verify_cal_coeffs(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests calibration bank switching.

    This test stages calibration, verifies it, switches banks, and verifies live cal.

    :param stations_devices_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool, station_label: str) -> None:
    """
    Skip the test if not in real context.

    :param hw_context: whether or not the current test is againt HW.
    :param station_label: Station to test against.
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
def check_against_real_context(true_context: bool, station_label: str) -> None:
    """
    Skip the test if not in real context.

    :param true_context: whether or not the current context is real.
    :param station_label: Station to test against.
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

    # Make sure Station and all Tiles are ON by going through STANDBY
    station.standby()
    AttributeWaiter(timeout=300).wait_for_value(
        station, "state", tango.DevState.STANDBY
    )
    station.on()
    try:
        AttributeWaiter(timeout=300).wait_for_value(station, "state", tango.DevState.ON)
    except AssertionError:
        # Hardware can be in the ALARM state, we should still continue.
        assert station.state() in [tango.DevState.ON, tango.DevState.ALARM]
    for tile in station_tiles:
        AttributeWaiter(timeout=300).wait_for_value(
            tile, "tileProgrammingState", "Synchronised", lookahead=5
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
    tile_device.init()


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


@given("I stage calibration coefficients on the Tile per antenna")
@when("I stage calibration coefficients on the Tile per antenna")
def stage_calibration_coefficients_on_tile_per_antenna(
    tile_device: tango.DeviceProxy,
    calibration_coefficients: list[list[list[list[float]]]],
    nof_antennas: int,
    nof_channels: int,
) -> Generator:
    """
    Stage calibration coefficients on the Tile using per-antenna loading.

    :param tile_device: Tile under test.
    :param calibration_coefficients: A 4D list of
        calibration coefficients for a Tile. List of floats.
        channel * antenna * pol * (real, imag)
    :param nof_antennas: Number of antennas per tile.
    :param nof_channels: Number of channels.

    :yields: Control to the test.
    """
    # Store original cal.
    original_staged_cal: list[list[list[list[float]]]] = json.loads(
        tile_device.allStagedCal
    )
    for antenna in range(nof_antennas):
        # Only loads for one antenna at a time.
        # 8 values per channel for an antenna.
        # nof_channels * nof_pols * 2 values total plus antenna number prepended.
        # Extract all channels for this specific antenna
        cal_to_stage = [antenna] + np.array(
            [calibration_coefficients[ch][antenna] for ch in range(nof_channels)]
        ).ravel().tolist()
        tile_device.LoadCalibrationCoefficients(cal_to_stage)

    yield

    # Restore original cal
    for antenna in range(nof_antennas):
        cal_to_stage = [antenna] + np.array(
            [original_staged_cal[ch][antenna] for ch in range(nof_channels)]
        ).ravel().tolist()
        tile_device.LoadCalibrationCoefficients(cal_to_stage)

    try:
        assert np.array(original_staged_cal).ravel().tolist() == pytest.approx(
            np.array(json.loads(tile_device.allStagedCal)).ravel().tolist(), abs=0.001
        )
    except AssertionError:
        pytest.fail("Could not validate restoration of original staged calibration.")


@when("I stage calibration coefficients on the Tile per channel")
def stage_calibration_coefficients_on_tile_per_channel(
    tile_device: tango.DeviceProxy,
    calibration_coefficients: list[list[list[list[float]]]],
    nof_antennas: int,
    nof_channels: int,
) -> Generator:
    """
    Stage calibration coefficients on the Tile using per-channel loading.

    This uses LoadCalibrationCoefficientsForChannels which can load multiple
    channels at once, with all antennas for each channel.

    :param tile_device: Tile under test.
    :param calibration_coefficients: A 4D list of
        calibration coefficients for a Tile. List of floats.
        channel * antenna * pol * (real, imag)
    :param nof_antennas: Number of antennas per tile.
    :param nof_channels: Number of channels.

    :yields: Control to the test.
    """
    # Store original cal.
    original_staged_cal: list[list[list[list[float]]]] = json.loads(
        tile_device.allStagedCal
    )

    # Load all channels at once
    # Format: [first_channel, ch0_ant0_data, ch0_ant1_data, ..., ch0_ant15_data,
    #          ch1_ant0_data, ch1_ant1_data, ..., ch1_ant15_data, ...]
    # Where each antenna data is: pol0_real, pol0_imag, pol1_real, pol1_imag,
    #                              pol2_real, pol2_imag, pol3_real, pol3_imag (8 values)
    # Total per channel: 16 antennas * 8 values = 128 values
    # Total: 1 (start_channel) + 384 channels * 128 values = 49153 values

    cal_data = [0]  # Start with first_channel = 0
    for ch in range(nof_channels):
        # For each channel, interleave antenna data by value position
        # Command expects: [ant0_val0, ant0_val1, ..., ant0_val7,
        #                   ant1_val0, ant1_val1, ..., ant1_val7, ...]
        for antenna in range(nof_antennas):
            cal_data.extend(
                np.array(calibration_coefficients[ch][antenna]).ravel().tolist()
            )

    tile_device.LoadCalibrationCoefficientsForChannels(cal_data)

    yield

    # Restore original cal
    restore_data = [0]  # Start with first_channel = 0
    for ch in range(nof_channels):
        for antenna in range(nof_antennas):
            restore_data.extend(
                np.array(original_staged_cal[ch][antenna]).ravel().tolist()
            )

    tile_device.LoadCalibrationCoefficientsForChannels(restore_data)

    try:
        assert np.array(original_staged_cal).ravel().tolist() == pytest.approx(
            np.array(json.loads(tile_device.allStagedCal)).ravel().tolist(), abs=0.001
        )
    except AssertionError:
        pytest.fail("Could not validate restoration of original staged calibration.")


@when("I switch the active calibration bank", target_fixture="original_live_cal")
def switch_active_calibration_bank(
    tile_device: tango.DeviceProxy,
) -> Generator:
    """
    Switch staged and live calibration banks on the tile device.

    :param tile_device: Tile device under test.

    :yields: Control to the test.
    """
    original_staged_cal = np.array(json.loads(tile_device.allStagedCal))
    original_live_cal = np.array(json.loads(tile_device.allLiveCal))
    tile_device.ApplyCalibration("")
    time.sleep(5)  # We saw what looked like a partial bank swap.
    # Did we read it during the operation?
    new_live_cal = np.array(json.loads(tile_device.allLiveCal))
    new_staged_cal = np.array(json.loads(tile_device.allStagedCal))

    print(
        "Original Staged == Original Live (Expect False): "
        f"{original_staged_cal == pytest.approx(original_live_cal)}"
    )
    print(
        "Original Staged == New Live (Expect True): "
        f"{original_staged_cal == pytest.approx(new_live_cal)}"
    )
    print(
        "New Staged == New Live (Expect False): "
        f"{new_staged_cal == pytest.approx(new_live_cal)}"
    )
    print(
        "New Staged == Original Live (Expect True): "
        f"{new_staged_cal == pytest.approx(original_live_cal)}"
    )
    print(f"Original Staged[0]: {original_staged_cal[0]}")
    print(f"Original Live[0]: {original_live_cal[0]}")
    print(f"New Staged[0]: {new_staged_cal[0]}")
    print(f"New Live[0]: {new_live_cal[0]}")

    yield original_live_cal

    # Restore original live cal.
    tile_device.ApplyCalibration("")


@then("the staged calibration matches the original live calibration")
def compare_new_staged_with_original_live_calibration(
    tile_device: tango.DeviceProxy,
    original_live_cal: list[list[list[list[float]]]],
    nof_antennas: int,
    nof_channels: int,
    nof_pols: int,
) -> None:
    """
    Read back and compare live calibration on Tile.

    :param tile_device: Tile under test.
    :param original_live_cal: A list of
        calibration coefficients for a Tile.
    :param nof_antennas: Number of antennas per tile.
    :param nof_channels: Number of channels.
    :param nof_pols: Number of polarizations.
    """
    expected_length = nof_channels * nof_antennas * nof_pols * 2
    expected_cal_1d = np.array(original_live_cal).ravel().tolist()
    assert len(expected_cal_1d) == expected_length
    actual_cal_1d = np.array(json.loads(tile_device.allStagedCal)).ravel().tolist()
    assert len(actual_cal_1d) == expected_length

    assert actual_cal_1d == pytest.approx(expected_cal_1d, abs=0.001)


@then("the live calibration coefficients can be read back correctly from the Tile")
def read_and_compare_live_calibration(
    tile_device: tango.DeviceProxy,
    calibration_coefficients: list[list[list[list[float]]]],
    nof_antennas: int,
    nof_channels: int,
    nof_pols: int,
) -> None:
    """
    Read back and compare live calibration on Tile.

    :param tile_device: Tile under test.
    :param calibration_coefficients: A flattened list of
        calibration coefficients for a Tile.
    :param nof_antennas: Number of antennas per tile.
    :param nof_channels: Number of channels.
    :param nof_pols: Number of polarizations.
    """
    expected_length = nof_channels * nof_antennas * nof_pols * 2
    expected_cal_1d = np.array(calibration_coefficients).ravel().tolist()
    assert len(expected_cal_1d) == expected_length
    actual_cal_1d = np.array(json.loads(tile_device.allLiveCal)).ravel().tolist()
    assert len(actual_cal_1d) == expected_length

    assert actual_cal_1d == pytest.approx(expected_cal_1d, abs=0.001)


@given("the staged calibration coefficients can be read back correctly from the Tile")
@then("the staged calibration coefficients can be read back correctly from the Tile")
def read_and_compare_staged_calibration(
    tile_device: tango.DeviceProxy,
    calibration_coefficients: list[list[list[list[float]]]],
    nof_antennas: int,
    nof_channels: int,
    nof_pols: int,
) -> None:
    """
    Read back and compare staged calibration on Tile.

    :param tile_device: Tile under test.
    :param calibration_coefficients: A flattened list of
        calibration coefficients for a Tile.
    :param nof_antennas: Number of antennas per tile.
    :param nof_channels: Number of channels.
    :param nof_pols: Number of polarizations.
    """
    expected_length = nof_channels * nof_antennas * nof_pols * 2
    expected_cal_1d = np.array(calibration_coefficients).ravel().tolist()
    assert len(expected_cal_1d) == expected_length
    actual_cal_1d = np.array(json.loads(tile_device.allStagedCal)).ravel().tolist()
    assert len(actual_cal_1d) == expected_length

    assert actual_cal_1d == pytest.approx(expected_cal_1d, abs=0.001)


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
