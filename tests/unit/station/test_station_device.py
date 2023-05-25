# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the SpsStation tango device."""
from __future__ import annotations

import gc
import json
import time
from typing import Any, Callable, Generator
from unittest.mock import PropertyMock

import pytest
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.station import SpsStation

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "admin_mode",
        "command_result",
        "command_status",
        "health_state",
        "state",
        timeout=2.0,
    )


@pytest.fixture(name="station_name", scope="session")
def station_name_fixture() -> str:
    """
    Return the name of the SPS station Tango device.

    :return: the name of the SPS station Tango device.
    """
    return "low-mccs/sps_station/001"


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(  # pylint: disable=too-many-arguments
    station_name: str,
    patched_station_device_class: type[SpsStation],
    subrack_name: str,
    mock_subrack: DeviceProxy,
    tile_names: list[str],
    mock_tiles: list[DeviceProxy],
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param station_name: the name of the subrack Tango device
    :param patched_station_device_class: a subclass of SpsStation that
        has been patched with extra commands for use in testing
    :param subrack_name: the name of the subrack Tango device
    :param mock_subrack: a mock subrack proxy that has been configured
        with the required subrack behaviours.
    :param tile_names: the names of the tile Tango devices
    :param mock_tiles: mock tile proxies that have been configured with
        the required tile behaviours.

    :yields: a tango context.
    """
    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        station_name,
        patched_station_device_class,
        StationId=0,
        TileFQDNs=tile_names,
        SubrackFQDNs=[subrack_name],
        CabinetNetworkAddress="10.0.0.0",
    )
    context_manager.add_mock_device(subrack_name, mock_subrack)
    for i, name in enumerate(tile_names):
        context_manager.add_mock_device(name, mock_tiles[i])
    with context_manager as context:
        yield context


@pytest.fixture(name="station_device")
def station_device_fixture(
    tango_harness: TangoContextProtocol,
    station_name: str,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param station_name: name of the station Tango device.

    :yield: the station Tango device under test.
    """
    yield tango_harness.get_device(station_name)


def test_off(
    station_device: SpsStation,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to turn the SPS station device off.

    :param station_device: the SPS station Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    # First let's check the initial state
    assert station_device.adminMode == AdminMode.OFFLINE

    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    change_event_callbacks["state"].assert_not_called()

    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()

    # TODO: Check that we get an updated value for our subscribed attribute

    # It's on, so let's turn it off.
    station_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(None)

    station_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    ([result_code], [off_command_id]) = station_device.Off()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "IN_PROGRESS")
    )

    change_event_callbacks["state"].assert_not_called()

    # Make the station think it has received events from its subracks,
    # advising it that they are off.
    station_device.MockSubracksOff()

    change_event_callbacks["state"].assert_change_event(DevState.OFF)
    change_event_callbacks["state"].assert_not_called()
    assert station_device.state() == DevState.OFF

    # TODO: SpsStation.Off() implementation is currently fire-and-forget.
    # No command result is ever issued.
    #
    # change_event_callbacks["command_result"].assert_change_event(
    #     (
    #         off_command_id,
    #         json.dumps([int(ResultCode.OK), "Command completed"]),
    #     ),
    # )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED")
    )


@pytest.mark.parametrize(
    ("expected_init_params", "new_params"),
    [
        pytest.param(
            {
                "subrack_degraded": 0.05,
                "subrack_failed": 0.2,
                "tile_degraded": 0.05,
                "tile_failed": 0.2,
            },
            {
                "subrack_degraded": 0.1,
                "subrack_failed": 0.3,
                "tile_degraded": 0.07,
                "tile_failed": 0.2,
            },
            id="Check correct initial values, write new and "
            "verify new values have been written",
        )
    ],
)
def test_healthParams(
    station_device: SpsStation,
    expected_init_params: dict[str, float],
    new_params: dict[str, float],
) -> None:
    """
    Test for healthParams attributes.

    :param station_device: the SPS station Tango device under test.
    :param expected_init_params: the initial values which the health model is
        expected to have initially
    :param new_params: the new health rule params to pass to the health model
    """
    assert station_device.healthModelParams == json.dumps(expected_init_params)
    new_params_json = json.dumps(new_params)
    station_device.healthModelParams = new_params_json  # type: ignore[assignment]
    assert station_device.healthModelParams == new_params_json


@pytest.mark.parametrize(
    (
        "command",
        "command_args",
        "tile_command",
        "tile_command_args",
        "tile_command_args_json_dict",
    ),
    [
        pytest.param(
            "StartAcquisition",
            json.dumps({"start_time": "20230101T12:34:55.000Z", "delay": 0}),
            "StartAcquisition",
            json.dumps({"start_time": "20230101T12:34:55.000Z", "delay": 0}),
            True,
        ),
        pytest.param(
            "ConfigureTestGenerator",
            json.dumps({"tone_frequency": 1000, "tone_amplitude": 1}),
            "ConfigureTestGenerator",
            json.dumps({"tone_frequency": 1000, "tone_amplitude": 1}),
            False,
        ),
        pytest.param(
            "StopDataTransmission",
            None,
            "StopDataTransmission",
            None,
            False,
        ),
        pytest.param(
            "SendDataSamples",
            json.dumps(
                {
                    "data_type": "raw",
                }
            ),
            "SendDataSamples",
            json.dumps(
                {
                    "data_type": "raw",
                }
            ),
            True,
        ),
        pytest.param(
            "StopIntegratedData",
            None,
            "StopIntegratedData",
            None,
            False,
        ),
        pytest.param(
            "ConfigureIntegratedBeamData",
            "{}",
            "ConfigureIntegratedBeamData",
            json.dumps(
                {"integration_time": 0.5, "first_channel": 0, "last_channel": 191}
            ),
            False,
        ),
        pytest.param(
            "ConfigureIntegratedChannelData",
            "{}",
            "ConfigureIntegratedChannelData",
            json.dumps(
                {"integration_time": 0.5, "first_channel": 0, "last_channel": 511}
            ),
            True,
        ),
        pytest.param(
            "StopBeamformer",
            None,
            "StopBeamformer",
            None,
            False,
        ),
        pytest.param(
            "StartBeamformer",
            "{}",
            "StartBeamformer",
            json.dumps(
                {
                    "start_time": None,
                    "duration": -1,
                    "subarray_beam_id": -1,
                    "scan_id": 0,
                }
            ),
            True,
        ),
        pytest.param(
            "ApplyPointingDelays",
            "20230101T12:34:55.000Z",
            "ApplyPointingDelays",
            "20230101T12:34:55.000Z",
            False,
        ),
        pytest.param(
            "LoadPointingDelays",
            [1] + [0] * 512,
            "LoadPointingDelays",
            [1] + [0] * 32,
            False,
        ),
        pytest.param(
            "ApplyCalibration",
            "20230101T12:34:55.000Z",
            "ApplyCalibration",
            "20230101T12:34:55.000Z",
            False,
        ),
        pytest.param(
            "SetBeamformerRegions",
            [4, 24, 0, 0, 0, 3, 1, 101, 26, 40, 1, 0, 24, 4, 2, 102],
            "SetBeamformerRegions",
            [
                4,
                8,
                0,
                0,
                0,
                3,
                1,
                101,
                12,
                8,
                0,
                0,
                8,
                3,
                1,
                101,
                20,
                8,
                0,
                0,
                16,
                3,
                1,
                101,
                26,
                8,
                1,
                0,
                24,
                4,
                2,
                102,
                34,
                8,
                1,
                0,
                32,
                4,
                2,
                102,
                42,
                8,
                1,
                0,
                40,
                4,
                2,
                102,
                50,
                8,
                1,
                0,
                48,
                4,
                2,
                102,
                58,
                8,
                1,
                0,
                56,
                4,
                2,
                102,
            ],
            False,
        ),
        pytest.param(
            "SetLmcIntegratedDownload",
            json.dumps({"destination_ip": "127.0.0.1"}),
            "SetLmcIntegratedDownload",
            json.dumps(
                {
                    "mode": "10G",
                    "channel_payload_length": 1024,
                    "beam_payload_length": 1024,
                    "destination_ip": "127.0.0.1",
                    "source_port": 0xF0D0,
                    "destination_port": 4660,
                }
            ),
            True,
        ),
        pytest.param(
            "SetLmcDownload",
            json.dumps({"destination_ip": "127.0.0.1"}),
            "SetLmcDownload",
            json.dumps(
                {
                    "mode": "40G",
                    "payload_length": 1024,
                    "destination_ip": "127.0.0.1",
                    "destination_port": 4660,
                    "source_port": 0xF0D0,
                }
            ),
            True,
        ),
    ],
)
def test_station_tile_commands(
    station_device: SpsStation,
    command: str,
    command_args: Any,
    mock_tiles: DeviceProxy,
    tile_command: str,
    tile_command_args: Any,
    tile_command_args_json_dict: bool,
):
    """
    Tests of station commands calling the corresponding command on Tile.

    :param station_device: The station device to use
    :param command: The command to call on the station
    :param command_args: The arguments to call the command with
    :param mock_tile: The mock for the tile to verify commands being called
    :param tile_command: The expected command to be called on the tile
    :param tile_command_args: The expected arguments for the command on the tile
    :param tile_command_args_json_dict: True if the arguments for the tile command are
        a JSON dictionary. This prompts the test to load the dictionary as a python
        dictionary so it can be safely compared with the input, as the two JSON strings
        cannot be directly compared, since Python dictionaries are not ordered. The
        expected arguments parameter should be a json dictionary.
    """
    station_device.adminMode = AdminMode.ONLINE

    # Some commands require tile programming state to be Initialised or Synchronised
    mock_tiles[0].tileProgrammingState = "Synchronised"

    # The mock takes a non-negligible amount of time to write attributes
    # Brief sleep needed to allow it to write the tileProgrammingState
    time.sleep(0.1)

    if command_args is None:
        getattr(station_device, command)()
    else:
        getattr(station_device, command)(command_args)
    tile_command_mock = getattr(mock_tiles[0], tile_command)

    # Wait for LRCs to execute
    timeout = 10
    time_waited = 0
    while not tile_command_mock.called:
        time.sleep(1)
        time_waited += 1
        if time_waited >= timeout:
            assert False, f"Command {tile_command} not called on tile"

    tile_command_mock.assert_called_once()
    if tile_command_args is None:
        assert len(tile_command_mock.call_args[0]) == 0
    elif tile_command_args_json_dict:
        assert json.loads(tile_command_args) == json.loads(
            tile_command_mock.call_args[0][0]
        )
    else:
        assert tile_command_args == tile_command_mock.call_args[0][0]


def test_isCalibrated(station_device: SpsStation) -> None:
    """
    Test of the isCalibrated attribute.

    :param station_device: The station device to use
    """
    assert not station_device.isCalibrated


def test_isConfigured(station_device: SpsStation) -> None:
    """
    Test of the isConfigured attribute.

    :param station_device: The station device to use
    """
    assert not station_device.isConfigured


@pytest.mark.parametrize(
    ("attribute", "data", "tile_data"),
    [
        pytest.param("channeliserRounding", lambda _: [3] * 512, lambda _: [3] * 512),
        pytest.param(
            "cspRounding",
            lambda _: [4] * 384,
            lambda _: [4] * 384,
        ),
        pytest.param(
            "staticTimeDelays",
            lambda num_tiles: list(range(32 * num_tiles)),
            lambda i: [(i * 32) + q for q in range(32)],
        ),
        pytest.param(
            "preaduLevels",
            lambda num_tiles: list(range(32 * num_tiles)),
            lambda i: [(i * 32) + q for q in range(32)],
        ),
        pytest.param(
            "ppsDelays",
            lambda num_tiles: list(range(num_tiles)),
            lambda i: [i],
        ),
    ],
)
def test_rw_attributes(
    station_device: SpsStation,
    mock_tiles: list[DeviceProxy],
    num_tiles: int,
    attribute: str,
    data: Callable[[int], list[float]],
    tile_data: Callable[[int], list[float]],
) -> None:
    """
    Test of the read-write attributes.

    These are:
        staticTimeDelays
        channeliserRounding
        cspRounding
        preaduLevels
        ppsDelays

    :param station_device: The station device to use
    :param mock_tiles: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.adminMode = AdminMode.ONLINE
    rounding_mocks = [PropertyMock() for _ in range(num_tiles)]
    for i, tile in enumerate(mock_tiles):
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.1)
    for i in range(num_tiles):
        setattr(type(mock_tiles[i]), attribute, rounding_mocks[i])
    setattr(station_device, attribute, data(num_tiles))
    for i in range(num_tiles):
        assert all(rounding_mocks[i].call_args[0][0] == tile_data(i))
    assert all(getattr(station_device, attribute) == data(num_tiles))
