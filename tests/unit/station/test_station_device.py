# -*- coding: utf-8 -*
# pylint: disable=too-many-arguments, too-many-lines
# pylint: disable=too-many-locals, too-many-statements
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the SpsStation tango device."""
from __future__ import annotations

import datetime
import gc
import json
import time
import unittest.mock
from typing import Any, Callable, Iterator

import numpy as np
import pytest
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.mocks import MockFieldStation
from ska_low_mccs_spshw.station import SpsStation
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext

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
        "outsideTemperature",
        timeout=2.0,
    )


@pytest.fixture(name="cabinet_network_address", scope="session")
def cabinet_network_address_fixture() -> str:
    """
    Return the station cabinet network address.

    :return: the station cabinet network address
    """
    return "10.0.0.0"


@pytest.fixture(name="test_context")
def test_context_fixture(
    cabinet_network_address: str,
    mock_subrack_device_proxy: unittest.mock.Mock,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    patched_sps_station_device_class: type[SpsStation],
    daq_trl: str,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which an SPS station Tango device is running.

    :param cabinet_network_address: the network address of the SPS
        cabinet
    :param mock_subrack_device_proxy: a mock return as a device proxy to
        the subrack device
    :param mock_tile_device_proxies: mocks to return as device proxies to the tiles
        devices
    :param patched_sps_station_device_class: a subclass of SpsStation
        that has been patched with extra commands that mock system under
        control behaviours.
    :param daq_trl: a Tango Resource Locator of a DAQ instance.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(1, mock_subrack_device_proxy)

    for i, mock_tile_device_proxy in enumerate(mock_tile_device_proxies):
        harness.add_mock_tile_device(i + 1, mock_tile_device_proxy)

    harness.set_sps_station_device(
        cabinet_network_address,
        subrack_ids=[1],
        tile_ids=range(1, len(mock_tile_device_proxies) + 1),
        daq_trl=daq_trl,
        device_class=patched_sps_station_device_class,
    )
    harness.add_field_station_device(
        device_class=MockFieldStation,
    )

    with harness as context:
        yield context


@pytest.fixture(name="station_device")
def station_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the SPS station Tango device under test.

    :param test_context: a Tango test context
        containing an SPS station and mock subservient devices.

    :yield: the station Tango device under test.
    """
    yield test_context.get_sps_station_device()


@pytest.fixture(name="field_station_device")
def field_station_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the field station Tango device under test.

    :param test_context: a Tango test context
        containing an SPS station and mock subservient devices.

    :yield: the station Tango device under test.
    """
    yield test_context.get_field_station_device()


def test_mock_field_station(
    field_station_device: DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test basic functionality of the mock field station.

    :param field_station_device: the Field station Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    assert (
        field_station_device.outsideTemperature
        == MockFieldStation.INITIAL_MOCKED_OUTSIDE_TEMPERATURE
    )

    field_station_device.subscribe_event(
        "outsideTemperature",
        EventType.CHANGE_EVENT,
        change_event_callbacks["outsideTemperature"],
    )
    change_event_callbacks["outsideTemperature"].assert_change_event(
        MockFieldStation.INITIAL_MOCKED_OUTSIDE_TEMPERATURE
    )

    mocked_outside_temperature = 37.2

    field_station_device.MockOutsideTemperatureChange(mocked_outside_temperature)

    change_event_callbacks["outsideTemperature"].assert_change_event(
        mocked_outside_temperature
    )


def test_Off(
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

    change_event_callbacks["command_status"].assert_change_event(())

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


def test_On(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test our ability to turn the SPS station device on.

    :param station_device: the SPS station Tango device under test.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    counter = 0
    sync_time = None

    def getter(*args: Any) -> list:
        nonlocal counter, sync_time
        if counter < 2:
            counter += 1
            sync_time = datetime.datetime.now()
        return [sync_time]

    for tile in mock_tile_device_proxies:
        pm = unittest.mock.PropertyMock()
        pm.__get__ = getter  # type: ignore[assignment]
        type(tile).fpgasUnixTime = pm

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

    csp_ingest_address = "123.234.123.234"
    csp_ingest_port = 1234

    station_device.SetCspIngest(
        json.dumps(
            {
                "destination_ip": csp_ingest_address,
                "destination_port": csp_ingest_port,
                "source_port": 0,
            }
        )
    )

    # It's already on, so let's turn it off before we turn it on again.
    station_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(())

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

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED")
    )

    # Now turn the station back on using the On command
    ([result_code], [on_command_id]) = station_device.On()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED", on_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED", on_command_id, "IN_PROGRESS")
    )

    change_event_callbacks["state"].assert_not_called()

    # Make the station think it has received events from its subracks and then tiles,
    # advising it that they are on.
    station_device.MockSubracksOn()
    station_device.MockTilesOn()

    change_event_callbacks["state"].assert_change_event(DevState.STANDBY)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()
    assert station_device.state() == DevState.ON

    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "COMPLETED", on_command_id, "COMPLETED")
    )
    for i, tile in enumerate(mock_tile_device_proxies):
        last_tile = i == num_tiles - 1
        if last_tile:
            num_configures = 4
        else:
            num_configures = 2
        assert len(tile.Configure40GCore.mock_calls) == num_configures
        assert json.loads(
            tile.Configure40GCore.mock_calls[0 if not last_tile else 2].args[0]
        ) == {
            "core_id": 0,
            "arp_table_entry": 0,
            "source_ip": f"10.0.0.{str(152 + (2 * i))}",
            "source_mac": 107752307294360 + (2 * i),
            "source_port": 61648,
            "destination_ip": f"10.0.0.{str(154 + (2 * i))}"
            if i != num_tiles - 1
            else csp_ingest_address,
            "destination_port": 4660 if not last_tile else csp_ingest_port,
        }
        assert json.loads(
            tile.Configure40GCore.mock_calls[1 if not last_tile else 3].args[0]
        ) == {
            "core_id": 1,
            "arp_table_entry": 0,
            "source_ip": f"10.0.0.{str(153 + (2 * i))}",
            "source_mac": 107752307294361 + (2 * i),
            "source_port": 61648,
            "destination_ip": f"10.0.0.{str(155 + (2 * i))}"
            if i != num_tiles - 1
            else csp_ingest_address,
            "destination_port": 4660 if not last_tile else csp_ingest_port,
        }
        assert len(tile.ConfigureStationBeamformer.mock_calls) == 1
        assert json.loads(tile.ConfigureStationBeamformer.mock_calls[0].args[0]) == {
            "is_first": (i == 0),
            "is_last": (last_tile),
        }
        assert len(tile.SetLmcDownload.mock_calls) == 2
        assert json.loads(tile.SetLmcDownload.mock_calls[0].args[0]) == {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": 4660,
            "source_port": 61648,
        }
        assert json.loads(tile.SetLmcDownload.mock_calls[1].args[0]) == {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": 4660,
            "source_port": 61648,
        }
        assert len(tile.SetLmcIntegratedDownload.mock_calls) == 1
        assert json.loads(tile.SetLmcIntegratedDownload.mock_calls[0].args[0]) == {
            "mode": "10G",
            "destination_ip": "0.0.0.0",
            "beam_payload_length": 8192,
            "channel_payload_length": 8192,
        }


def test_Initialise(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test of the Initialise command.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    counter = 0
    sync_time = None

    def getter(*args: Any) -> list:
        nonlocal counter, sync_time
        if counter < 2:
            counter += 1
            sync_time = datetime.datetime.now()
        return [sync_time]

    for tile in mock_tile_device_proxies:
        pm = unittest.mock.PropertyMock()
        pm.__get__ = getter  # type: ignore[assignment]
        type(tile).fpgasUnixTime = pm

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

    csp_ingest_address = "123.234.123.234"
    csp_ingest_port = 1234

    station_device.SetCspIngest(
        json.dumps(
            {
                "destination_ip": csp_ingest_address,
                "destination_port": csp_ingest_port,
                "source_port": 0,
            }
        )
    )

    station_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(())
    station_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    ([result_code], [command_id]) = station_device.Initialise()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event((command_id, "QUEUED"))
    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "IN_PROGRESS")
    )
    time.sleep(12)
    for tile in mock_tile_device_proxies:
        tile.tileProgrammingState = "Initialised"
    time.sleep(4)
    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "COMPLETED")
    )

    for i, tile in enumerate(mock_tile_device_proxies):
        last_tile = i == num_tiles - 1
        if last_tile:
            num_configures = 4
        else:
            num_configures = 2
        assert len(tile.Configure40GCore.mock_calls) == num_configures
        assert json.loads(
            tile.Configure40GCore.mock_calls[0 if not last_tile else 2].args[0]
        ) == {
            "core_id": 0,
            "arp_table_entry": 0,
            "source_ip": f"10.0.0.{str(152 + (2 * i))}",
            "source_mac": 107752307294360 + (2 * i),
            "source_port": 61648,
            "destination_ip": f"10.0.0.{str(154 + (2 * i))}"
            if i != num_tiles - 1
            else csp_ingest_address,
            "destination_port": 4660 if not last_tile else csp_ingest_port,
        }
        assert json.loads(
            tile.Configure40GCore.mock_calls[1 if not last_tile else 3].args[0]
        ) == {
            "core_id": 1,
            "arp_table_entry": 0,
            "source_ip": f"10.0.0.{str(153 + (2 * i))}",
            "source_mac": 107752307294361 + (2 * i),
            "source_port": 61648,
            "destination_ip": f"10.0.0.{str(155 + (2 * i))}"
            if i != num_tiles - 1
            else csp_ingest_address,
            "destination_port": 4660 if not last_tile else csp_ingest_port,
        }
        assert len(tile.ConfigureStationBeamformer.mock_calls) == 1
        assert json.loads(tile.ConfigureStationBeamformer.mock_calls[0].args[0]) == {
            "is_first": (i == 0),
            "is_last": (last_tile),
        }
        assert len(tile.SetLmcDownload.mock_calls) == 2
        assert json.loads(tile.SetLmcDownload.mock_calls[0].args[0]) == {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": 4660,
            "source_port": 61648,
        }
        assert json.loads(tile.SetLmcDownload.mock_calls[1].args[0]) == {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": 4660,
            "source_port": 61648,
        }
        assert len(tile.SetLmcIntegratedDownload.mock_calls) == 1
        assert json.loads(tile.SetLmcIntegratedDownload.mock_calls[0].args[0]) == {
            "mode": "10G",
            "destination_ip": "0.0.0.0",
            "beam_payload_length": 8192,
            "channel_payload_length": 8192,
        }


def test_Standby(
    station_device: SpsStation,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test of the Standby command.

    :param station_device: The station device to use
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
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
    station_device.subscribe_event(
        "longRunningCommandStatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_status"],
    )

    change_event_callbacks["command_status"].assert_change_event(())
    station_device.subscribe_event(
        "longRunningCommandResult",
        EventType.CHANGE_EVENT,
        change_event_callbacks["command_result"],
    )
    change_event_callbacks["command_result"].assert_change_event(("", ""))

    ([result_code], [command_id]) = station_device.Standby()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event((command_id, "QUEUED"))
    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "IN_PROGRESS")
    )
    change_event_callbacks["state"].assert_not_called()

    # Make the station think it has received events from its tiles,
    # advising it that they are off.
    station_device.MockTilesOff()

    change_event_callbacks["state"].assert_change_event(DevState.STANDBY)
    change_event_callbacks["state"].assert_not_called()
    assert station_device.state() == DevState.STANDBY

    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "COMPLETED")
    )


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
            "SetBeamFormerTable",
            [4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102],
            "SetBeamformerRegions",
            [4, 8, 0, 0, 0, 3, 1, 101, 26, 8, 1, 0, 24, 4, 2, 102],
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
        pytest.param(
            "LoadCalibrationCoefficients",
            [2, 3.4, 1.2, 2.3, 4.1, 4.6, 8.2, 6.8, 2.4],
            "LoadCalibrationCoefficients",
            np.array([2, 3.4, 1.2, 2.3, 4.1, 4.6, 8.2, 6.8, 2.4]),
            False,
        ),
    ],
)
def test_station_tile_commands(
    station_device: SpsStation,
    command: str,
    command_args: Any,
    mock_tile_device_proxies: DeviceProxy,
    tile_command: str,
    tile_command_args: Any,
    tile_command_args_json_dict: bool,
) -> None:
    """
    Tests of station commands calling the corresponding command on Tile.

    :param station_device: The station device to use
    :param command: The command to call on the station
    :param command_args: The arguments to call the command with
    :param mock_tile_device_proxies: The mock for the tiles to verify
        commands being called
    :param tile_command: The expected command to be called on the tile
    :param tile_command_args: The expected arguments for the command on the tile
    :param tile_command_args_json_dict:
        True if the arguments for the tile command are a JSON dictionary.
        This prompts the test to load the dictionary as a python dictionary
        so it can be safely compared with the input,
        as the two JSON strings cannot be directly compared,
        since Python dictionaries are not ordered.
        The expected arguments parameter should be a json dictionary.
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]

    # Some commands require tile programming state to be Initialised or Synchronised
    mock_tile_device_proxies[0].tileProgrammingState = "Synchronised"

    # The mock takes a non-negligible amount of time to write attributes
    # Brief sleep needed to allow it to write the tileProgrammingState
    time.sleep(0.1)

    if command_args is None:
        getattr(station_device, command)()
    else:
        getattr(station_device, command)(command_args)
    tile_command_mock = getattr(mock_tile_device_proxies[0], tile_command)

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
    elif isinstance(tile_command_args, np.ndarray):
        assert np.all(tile_command_args == tile_command_mock.call_args[0][0])
    else:
        assert tile_command_args == tile_command_mock.call_args[0][0]


def test_SetCspIngest(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test of the SetCspIngest command.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    station_device.MockSubracksOn()
    station_device.MockTilesOn()
    station_device.SetCspIngest(
        json.dumps(
            {
                "destination_ip": "123.123.234.234",
                "destination_port": 1234,
                "source_port": 2345,
            }
        )
    )
    assert station_device.cspIngestAddress == "123.123.234.234"
    assert station_device.cspIngestPort == 1234
    assert station_device.cspSourcePort == 2345
    for i, tile in enumerate(mock_tile_device_proxies):
        if i != num_tiles - 1:
            tile.Configure40GCore.assert_not_called()
        else:
            assert len(tile.Configure40GCore.mock_calls) == 2
            assert json.loads(tile.Configure40GCore.mock_calls[0].args[0]) == {
                "core_id": 0,
                "arp_table_entry": 0,
                "source_ip": f"10.0.0.{str(152 + (2 * i))}",
                "source_mac": 107752307294360 + (2 * i),
                "source_port": 61648,
                "destination_ip": "123.123.234.234",
                "destination_port": 1234,
            }
            assert json.loads(tile.Configure40GCore.mock_calls[1].args[0]) == {
                "core_id": 1,
                "arp_table_entry": 0,
                "source_ip": f"10.0.0.{str(153 + (2 * i))}",
                "source_mac": 107752307294361 + (2 * i),
                "source_port": 61648,
                "destination_ip": "123.123.234.234",
                "destination_port": 1234,
            }


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
    :param expected_init_params: the initial values which the health
        model is expected to have initially
    :param new_params: the new health rule params to pass to the health model
    """
    assert station_device.healthModelParams == json.dumps(expected_init_params)
    new_params_json = json.dumps(new_params)
    station_device.healthModelParams = new_params_json  # type: ignore[assignment]
    assert station_device.healthModelParams == new_params_json


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


def test_fortyGbNetworkAddress(
    station_device: SpsStation, cabinet_network_address: str
) -> None:
    """
    Test of the fortyGbNetworkAddress attribute.

    :param station_device: The station device to use
    :param cabinet_network_address: the station network cabinet address
    """
    assert station_device.fortyGbNetworkAddress == cabinet_network_address


@pytest.mark.parametrize(
    ("attribute", "data", "tile_data"),
    [
        pytest.param("channeliserRounding", lambda _: [3] * 512, lambda _: [3] * 512),
        pytest.param(
            "ppsDelays",
            lambda num_tiles: list(range(num_tiles)),
            lambda i: [i],
        ),
    ],
)
def test_rw_attributes(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
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
        preaduLevels
        ppsDelays

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param attribute: the attribute on the station to use
    :param data: the data to set to the station attribute, as a function of the number
        of tiles
    :param tile_data: the expected value for the attribute to take on the tile, as a
        function of the tile number in the list of tile mocks.
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    rounding_mocks = [unittest.mock.PropertyMock() for _ in range(num_tiles)]
    for i, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.1)
    for i in range(num_tiles):
        setattr(type(mock_tile_device_proxies[i]), attribute, rounding_mocks[i])
    setattr(station_device, attribute, data(num_tiles))
    time.sleep(0.1)
    for i in range(num_tiles):
        assert all(rounding_mocks[i].call_args[0][0] == tile_data(i))
    assert all(getattr(station_device, attribute) == data(num_tiles))


def test_cspRounding(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test for the cspRounding attribute.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    rounding_mocks = [unittest.mock.PropertyMock() for _ in range(num_tiles)]
    for _, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.1)
    for i in range(num_tiles):
        setattr(type(mock_tile_device_proxies[i]), "cspRounding", rounding_mocks[i])
    time.sleep(0.1)
    station_device.cspRounding = [4] * 384  # type: ignore[assignment]
    for i, mock in enumerate(rounding_mocks):
        if i == num_tiles - 1:
            assert all(mock.call_args[0][0] == [4] * 384)
        else:
            mock.assert_not_called()
    assert all(station_device.cspRounding == [4] * 384)  # type: ignore[arg-type]


def test_beamformerTable(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test the beamformerTable attribute.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    for _, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.1)
    station_device.SetBeamFormerTable([4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102])
    assert np.all(
        station_device.beamformerTable
        == np.array([4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102])
    )


@pytest.mark.parametrize(
    [
        "attribute_name",
        "tile_attribute_name",
        "init_tile_attribute_values",
        "init_expected_value",
        "final_tile_attribute_values",
        "final_expected_value",
    ],
    [
        pytest.param(
            "isProgrammed",
            "tileProgrammingState",
            lambda i: "Unconnected" if i % 2 == 0 else "Off",
            lambda _: False,
            lambda i: "Synchronised" if i % 2 == 0 else "Programmed",
            lambda _: True,
        ),
        pytest.param(
            "testGeneratorActive",
            "testGeneratorActive",
            lambda _: False,
            lambda _: False,
            lambda i: i == 0,
            lambda _: True,
        ),
        pytest.param(
            "isBeamformerRunning",
            "isBeamformerRunning",
            lambda i: i % 2 == 0,
            lambda _: False,
            lambda _: True,
            lambda _: True,
        ),
        pytest.param(
            "tileProgrammingState",
            "tileProgrammingState",
            lambda i: "Unconnected" if i % 2 == 0 else "Off",
            lambda n: ["Unconnected", "Off"] * int(n / 2)
            + ([] if n % 2 == 0 else ["Unconnected"]),
            lambda i: "Synchronised" if i % 2 == 0 else "Programmed",
            lambda n: ["Synchronised", "Programmed"] * int(n / 2)
            + ([] if n % 2 == 0 else ["Synchronised"]),
        ),
        pytest.param(
            "boardTemperaturesSummary",
            "boardTemperature",
            lambda i: i,
            lambda n: [0, (n - 1) / 2, n - 1],
            lambda i: 2 * i,
            lambda n: [0, (2 * (n - 1)) / 2, 2 * (n - 1)],
        ),
        pytest.param(
            "fpgaTemperaturesSummary",
            "fpgaTemperature",
            lambda i: 2 * i,
            lambda n: [0, (2 * (n - 1)) / 2, 2 * (n - 1)],
            lambda i: i,
            lambda n: [0, (n - 1) / 2, n - 1],
        ),
        pytest.param(
            "ppsDelaySummary",
            "ppsDelay",
            lambda i: i,
            lambda n: [0, (n - 1) / 2, n - 1],
            lambda i: 2 * i,
            lambda n: [0, (2 * (n - 1)) / 2, 2 * (n - 1)],
        ),
        pytest.param(
            "sysrefPresentSummary",
            "sysrefPresent",
            lambda i: not i % 2 == 0,
            lambda _: False,
            lambda _: True,
            lambda _: True,
        ),
        pytest.param(
            "pllLockedSummary",
            "pllLocked",
            lambda i: i % 2 == 0,
            lambda _: False,
            lambda _: True,
            lambda _: True,
        ),
        pytest.param(
            "ppsPresentSummary",
            "ppsPresent",
            lambda i: not i % 2 == 0,
            lambda _: False,
            lambda _: True,
            lambda _: True,
        ),
        pytest.param(
            "clockPresentSummary",
            "clockPresent",
            lambda i: i % 2 == 0,
            lambda _: False,
            lambda _: True,
            lambda _: True,
        ),
        pytest.param(
            "fortyGbNetworkErrors",
            "fortyGbNetworkErrors",
            lambda _: 0,
            lambda n: [0] * 2 * n,
            lambda _: 1,
            lambda n: [0] * 2 * n,
        ),
    ],
)
def test_station_tile_attributes(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    attribute_name: str,
    tile_attribute_name: str,
    init_tile_attribute_values: Callable[[int], Any],
    init_expected_value: Callable[[int], Any],
    final_tile_attribute_values: Callable[[int], Any],
    final_expected_value: Callable[[int], Any],
) -> None:
    """
    Test of attributes which aggregate tile attributes.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param attribute_name: the attribute to access on the station
    :param tile_attribute_name: the attribute on the tile that is accessed
    :param init_tile_attribute_values: the initial value that the tile attributes
        should take. This is a callable that takes in the number of the tile in the
        list of tiles and returns the value, so that different tiles can take different
        values.
    :param init_expected_value: the initial expected value of the station attribute, as
        a function of the number of tiles in the station.
    :param final_tile_attribute_values: the final value that the tile attributes
        should take.
    :param final_expected_value: the final expected value of the station attribute, as
        a function of the number of tiles in the station.
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    for i, tile in enumerate(mock_tile_device_proxies):
        if tile_attribute_name == "fpgaTemperature":
            setattr(tile, "fpga1Temperature", init_tile_attribute_values(i))
            setattr(tile, "fpga2Temperature", init_tile_attribute_values(i))
        else:
            setattr(tile, tile_attribute_name, init_tile_attribute_values(i))
    time.sleep(0.1)
    assert getattr(station_device, attribute_name) == pytest.approx(
        init_expected_value(num_tiles)
    )
    for i, tile in enumerate(mock_tile_device_proxies):
        if tile_attribute_name == "fpgaTemperature":
            setattr(tile, "fpga1Temperature", final_tile_attribute_values(i))
            setattr(tile, "fpga2Temperature", final_tile_attribute_values(i))
        else:
            setattr(tile, tile_attribute_name, final_tile_attribute_values(i))
    time.sleep(0.1)
    assert getattr(station_device, attribute_name) == pytest.approx(
        final_expected_value(num_tiles)
    )


def test_stations_daq_trl(station_device: SpsStation, daq_trl: str) -> None:
    """
    Test that SPSStation properly stores its DAQ TRL.

    Tests that SPSStation initialises its DAQ TRL properly and is
        able to change its value.

    :param station_device: The station device to use.
    :param daq_trl: The DAQ TRL in use.
    """
    assert station_device.daqTRL == daq_trl

    station_device.daqTRL = "NEW_DAQ_TRL"  # type: ignore[method-assign]

    assert station_device.daqTRL == "NEW_DAQ_TRL"
