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
import ipaddress
import json
import time
import unittest.mock
from datetime import timezone
from typing import Any, Callable, Iterator
from unittest.mock import ANY, MagicMock, call, patch

import numpy as np
import pytest
from astropy.utils import iers
from ska_control_model import AdminMode, HealthState, ResultCode
from ska_low_mccs_common.testing.mock import MockCallable
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.station import SpsStation
from tests.harness import (
    SpsTangoTestHarness,
    SpsTangoTestHarnessContext,
    get_bandpass_daq_name,
    get_lmc_daq_name,
    get_subrack_name,
    get_tile_name,
)
from tests.test_tools import execute_lrc_to_completion

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
        "track_lrc_command",
        timeout=20.0,
    )


@pytest.fixture(name="sdn_first_interface", scope="session")
def sdn_first_interface_fixture() -> str:
    """
    Return the first interface of the block allocated to this station for science data.

    This is an IP address and netmask, in CIDR-style slash-notation.
    For example, "10.130.0.1/25" means "address 10.130.0.1 on network 10.130.0.0/25".

    :return: the SDN first interface
    """
    return "10.0.0.152/25"


@pytest.fixture(name="sdn_gateway", scope="session")
def sdn_gateway_fixture() -> str:
    """
    Return the IP address of the SDN gateway.

    :return: the SDN gateway IP
    """
    return "10.0.0.254"


@pytest.fixture(name="test_context")
def test_context_fixture(
    sdn_first_interface: str,
    sdn_gateway: str,
    mock_subrack_device_proxy: unittest.mock.Mock,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    mock_daq_device_proxy: unittest.mock.Mock,
    patched_sps_station_device_class: type[SpsStation],
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which an SPS station Tango device is running.

    :param sdn_first_interface: the first interface of the block
        allocated to this station for science data.
    :param sdn_gateway: the IP address of the SDN gateway
    :param mock_subrack_device_proxy: a mock return as a device proxy to
        the subrack device
    :param mock_tile_device_proxies: mocks to return as device proxies to the tiles
        devices
    :param mock_daq_device_proxy: a fixture returning a mocked MccsDaqReceiver
        for unittests.
    :param patched_sps_station_device_class: a subclass of SpsStation
        that has been patched with extra commands that mock system under
        control behaviours.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(1, mock_subrack_device_proxy)

    for i, mock_tile_device_proxy in enumerate(mock_tile_device_proxies):
        harness.add_mock_tile_device(i + 1, mock_tile_device_proxy)

    harness.set_sps_station_device(
        sdn_first_interface,
        sdn_gateway,
        subrack_ids=[1],
        tile_ids=range(1, len(mock_tile_device_proxies) + 1),
        lmc_daq_trl=get_lmc_daq_name(),
        bandpass_daq_trl=get_bandpass_daq_name(),
        device_class=patched_sps_station_device_class,
    )

    harness.add_mock_lmc_daq_device(mock_daq_device_proxy)
    harness.add_mock_bandpass_daq_device(mock_daq_device_proxy)

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


@pytest.fixture(name="on_station_device")
def on_station_device_fixture(
    test_context: SpsTangoTestHarnessContext,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> DeviceProxy:
    """
    Fixture that returns the SPS station Tango device under test.

    Makes sure the device is ONLINE and ON.

    :param test_context: a Tango test context
        containing an SPS station and mock subservient devices.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.

    :returns: the station Tango device under test.
    """
    sps_station = test_context.get_sps_station_device()
    sps_station.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    if sps_station.adminMode != AdminMode.ONLINE:
        sps_station.adminMode = AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.ON)

    return sps_station


@pytest.fixture(name="daq_device")
def daq_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the SPS station Tango device under test.

    :param test_context: a Tango test context
        containing an SPS station and mock subservient devices.

    :yield: the station Tango device under test.
    """
    yield test_context.get_daq_device()


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
        (off_command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "REJECTED")
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
    change_event_callbacks["command_status"].assert_not_called()


def test_On(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
    sdn_first_interface: str,
    sdn_gateway: str,
) -> None:
    """
    Test our ability to turn the SPS station device on.

    :param station_device: the SPS station Tango device under test.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param sdn_first_interface: CIDR-like specification of the first interface
        in the block allocated to this station for science data.
    :param sdn_gateway: IP address of the subnet gateway.
        An empty string signifiese that no gateway is defined.
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
    csp_ingest_port = 4660

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
        (off_command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (off_command_id, "REJECTED")
    )

    change_event_callbacks["state"].assert_not_called()

    # Make the station think it has received events from its subracks,
    # advising it that they are off.
    station_device.MockSubracksOff()

    change_event_callbacks["state"].assert_change_event(DevState.OFF)
    change_event_callbacks["state"].assert_not_called()
    assert station_device.state() == DevState.OFF

    # Now turn the station back on using the On command
    ([result_code], [on_command_id]) = station_device.On()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "IN_PROGRESS")
    )

    change_event_callbacks["state"].assert_not_called()

    # Make the station think it has received events from its subracks and then tiles,
    # advising it that they are on.
    station_device.MockSubracksOn()
    station_device.MockTilesOn()

    # Some commands require tile programming state to be Initialised or Synchronised
    for mock_tile_proxy in mock_tile_device_proxies:
        mock_tile_proxy.tileProgrammingState = "Initialised"

    # The mock takes a non-negligible amount of time to write attributes
    # Brief sleep needed to allow it to write the tileProgrammingState
    time.sleep(0.1)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    change_event_callbacks["state"].assert_not_called()
    assert station_device.state() == DevState.ON

    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "COMPLETED")
    )
    for i, tile in enumerate(mock_tile_device_proxies):
        last_tile = i == num_tiles - 1
        tile.Configure40GCore.assert_not_called()
        assert len(tile.ConfigureStationBeamformer.mock_calls) == 1
        assert json.loads(tile.ConfigureStationBeamformer.mock_calls[0].args[0]) == {
            "is_first": (i == 0),
            "is_last": (last_tile),
        }
        tile.SetLmcDownload.assert_last_call(
            json.dumps(
                {
                    "mode": "10G",
                    "payload_length": 8192,
                    "destination_ip": "10.244.170.166",
                    "destination_port": 4660,
                    "source_port": 61648,
                    "netmask_40g": str(
                        ipaddress.ip_interface(sdn_first_interface).netmask
                    ),
                    "gateway_40g": sdn_gateway,
                }
            )
        )
        tile.SetLmcIntegratedDownload.assert_last_call(
            json.dumps(
                {
                    "mode": "1G",
                    "channel_payload_length": 1024,
                    "beam_payload_length": 1024,
                    "destination_ip": "10.244.170.166",
                    "source_port": 61648,
                    "destination_port": 4660,
                    "netmask_40g": str(
                        ipaddress.ip_interface(sdn_first_interface).netmask
                    ),
                    "gateway_40g": sdn_gateway,
                }
            )
        )


def test_Abort_On(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test the process of Aborting a turn on command.

    :param station_device: the SPS station Tango device under test.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
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

    # Turn station on, make sure it works
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

    # Turn station to Standby state
    ([result_code], [standby_command_id]) = station_device.Standby()
    assert result_code == ResultCode.QUEUED

    change_event_callbacks["command_status"].assert_change_event(
        (standby_command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (standby_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (standby_command_id, "IN_PROGRESS")
    )

    change_event_callbacks["state"].assert_not_called()

    station_device.MockTilesOff()

    change_event_callbacks["state"].assert_change_event(DevState.STANDBY)
    change_event_callbacks["state"].assert_not_called()

    assert station_device.state() == DevState.STANDBY

    change_event_callbacks["command_status"].assert_change_event(
        (standby_command_id, "COMPLETED")
    )

    # Turn a tile off, the on command won't be able to finish until it times out
    mock_tile_device_proxies[0].adminMode = AdminMode.OFFLINE

    ([on_result_code], [on_command_id]) = station_device.On()

    assert on_result_code == ResultCode.QUEUED
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "QUEUED")
    )
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "IN_PROGRESS")
    )

    # Abort the command
    ([abort_result_code], [abort_command_id]) = station_device.AbortCommands()
    change_event_callbacks["command_status"].assert_change_event(
        (on_command_id, "ABORTED")
    )


def test_Initialise(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
    sdn_first_interface: str,
    sdn_gateway: str,
) -> None:
    """
    Test of the Initialise command.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param sdn_first_interface: CIDR-like specification of the first interface
        in the block allocated to this station for science data.
    :param sdn_gateway: IP address of the subnet gateway.
        An empty string signifiese that no gateway is defined.
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
    csp_ingest_port = 4660

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

    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "STAGING")
    )
    change_event_callbacks["command_status"].assert_change_event((command_id, "QUEUED"))
    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "IN_PROGRESS")
    )
    time.sleep(12)
    for tile in mock_tile_device_proxies:
        tile.tileProgrammingState = "Synchronised"
    time.sleep(4)
    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "COMPLETED")
    )

    # get total number of leap seconds
    iers_table = iers.LeapSeconds.auto_open()
    total_leap_seconds = max(iers_table["tai_utc"])

    current_time = datetime.datetime.now()
    midnight = current_time.replace(
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone.utc,
    )
    # The expected global reference time will be the last midnight in tai.
    # To get this, take the current time, change hours/min/s to midnight, transform
    # it to a posix value (number of seconds) then subtract the leap seconds.
    expected_grt = int(np.floor(midnight.timestamp())) - int(total_leap_seconds)

    for i, tile in enumerate(mock_tile_device_proxies):
        last_tile = i == num_tiles - 1
        tile.Configure40GCore.assert_not_called()
        assert len(tile.ConfigureStationBeamformer.mock_calls) == 1
        assert json.loads(tile.ConfigureStationBeamformer.mock_calls[0].args[0]) == {
            "is_first": (i == 0),
            "is_last": (last_tile),
        }

        assert tile.globalReferenceTime == station_device.globalReferenceTime
        dt = datetime.datetime.strptime(
            tile.globalReferenceTime, "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        # Transform to Posix timestamp to match the expected_grt
        ts = dt.replace(tzinfo=timezone.utc).timestamp()
        assert int(np.ceil(ts)) == expected_grt

        tile.SetLmcDownload.assert_last_call(
            json.dumps(
                {
                    "mode": "10G",
                    "payload_length": 8192,
                    "destination_ip": "10.244.170.166",
                    "destination_port": 4660,
                    "source_port": 61648,
                    "netmask_40g": str(
                        ipaddress.ip_interface(sdn_first_interface).netmask
                    ),
                    "gateway_40g": sdn_gateway,
                }
            )
        )
        tile.SetLmcIntegratedDownload.assert_last_call(
            json.dumps(
                {
                    "mode": "1G",
                    "channel_payload_length": 1024,
                    "beam_payload_length": 1024,
                    "destination_ip": "10.244.170.166",
                    "source_port": 61648,
                    "destination_port": 4660,
                    "netmask_40g": str(
                        ipaddress.ip_interface(sdn_first_interface).netmask
                    ),
                    "gateway_40g": sdn_gateway,
                }
            )
        )


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

    change_event_callbacks["command_status"].assert_change_event(
        (command_id, "STAGING")
    )
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
    ),
    [
        pytest.param(
            "StartAcquisition",
            json.dumps({"start_time": "20230101T12:34:55.000Z", "delay": 0}),
            "StartAcquisition",
            json.dumps({"start_time": "20230101T12:34:55.000Z", "delay": 0}),
        ),
        pytest.param(
            "ConfigureTestGenerator",
            json.dumps({"tone_frequency": 1000, "tone_amplitude": 1}),
            "ConfigureTestGenerator",
            json.dumps({"tone_frequency": 1000, "tone_amplitude": 1}),
        ),
        pytest.param(
            "StopDataTransmission",
            None,
            "StopDataTransmission",
            None,
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
        ),
        pytest.param(
            "StopIntegratedData",
            None,
            "StopIntegratedData",
            None,
        ),
        pytest.param(
            "ConfigureIntegratedBeamData",
            "{}",
            "ConfigureIntegratedBeamData",
            json.dumps(
                {"integration_time": 0.5, "first_channel": 0, "last_channel": 191}
            ),
        ),
        pytest.param(
            "ConfigureIntegratedChannelData",
            "{}",
            "ConfigureIntegratedChannelData",
            json.dumps(
                {"integration_time": 0.5, "first_channel": 0, "last_channel": 511}
            ),
        ),
        pytest.param(
            "BeamformerRunningForChannels",
            "{}",
            "BeamformerRunningForChannels",
            json.dumps({"channel_groups": None}),
        ),
        pytest.param(
            "BeamformerRunningForChannels",
            json.dumps({"channel_groups": [1, 2, 4, 5]}),
            "BeamformerRunningForChannels",
            json.dumps({"channel_groups": [1, 2, 4, 5]}),
        ),
        pytest.param(
            "ApplyPointingDelays",
            "20230101T12:34:55.000Z",
            "ApplyPointingDelays",
            "20230101T12:34:55.000Z",
        ),
        pytest.param(
            "ApplyCalibration",
            "20230101T12:34:55.000Z",
            "ApplyCalibration",
            "20230101T12:34:55.000Z",
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
        ),
        pytest.param(
            "SetBeamFormerTable",
            [4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102],
            "SetBeamformerRegions",
            [4, 8, 0, 0, 0, 3, 1, 101, 26, 8, 1, 0, 24, 4, 2, 102],
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
                    "netmask_40g": "255.255.255.128",  # /25
                    "gateway_40g": "10.0.0.254",
                }
            ),
        ),
        pytest.param(
            "SetLmcDownload",
            json.dumps({"destination_ip": "127.0.0.1"}),
            "SetLmcDownload",
            json.dumps(
                {
                    "mode": "10G",
                    "payload_length": 8192,
                    "destination_ip": "127.0.0.1",
                    "destination_port": 4660,
                    "source_port": 0xF0D0,
                    "netmask_40g": "255.255.255.128",  # /25
                    "gateway_40g": "10.0.0.254",
                }
            ),
        ),
        pytest.param(
            "LoadCalibrationCoefficients",
            [2.0, 3.4, 1.2, 2.3, 4.1, 4.6, 8.2, 6.8, 2.4],
            "LoadCalibrationCoefficients",
            [2.0, 3.4, 1.2, 2.3, 4.1, 4.6, 8.2, 6.8, 2.4],
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
) -> None:
    """
    Tests of station commands calling the corresponding command on Tile.

    :param station_device: The station device to use
    :param command: The command to call on the station
    :param command_args: The arguments to call the command with
    :param mock_tile_device_proxies: The mock for the tiles to verify
        commands being called
    :param tile_command: The expected command to be called on the tile
    :param tile_command_args: The expected arguments for the command on the tile.
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]

    # Some commands require tile programming state to be Initialised or Synchronised
    for mock_tile_proxy in mock_tile_device_proxies:
        mock_tile_proxy.tileProgrammingState = "Synchronised"

    # The mock takes a non-negligible amount of time to write attributes
    # Brief sleep needed to allow it to write the tileProgrammingState
    time.sleep(0.2)

    if command_args is None:
        getattr(station_device, command)()
    else:
        getattr(station_device, command)(command_args)
    tile_command_mock: MockCallable = getattr(mock_tile_device_proxies[0], tile_command)

    if tile_command_args is None:
        tile_command_mock.assert_next_call()
    else:
        tile_command_mock.assert_next_call(tile_command_args)


@patch("ska_low_mccs_spshw.station.station_component_manager.MccsCompositeCommandProxy")
@patch("ska_low_mccs_spshw.station.station_component_manager.MccsCommandProxy")
@pytest.mark.parametrize(
    (
        "command",
        "command_args",
        "tile_command",
        "tile_command_args",
    ),
    [
        pytest.param(
            "StopBeamformer",
            None,
            "StopBeamformer",
            json.dumps(
                {
                    "channel_groups": None,
                }
            ),
        ),
        pytest.param(
            "StopBeamformerForChannels",
            "{}",
            "StopBeamformer",
            json.dumps(
                {
                    "channel_groups": None,
                }
            ),
        ),
        pytest.param(
            "StopBeamformerForChannels",
            json.dumps({"channel_groups": [1, 2, 4, 5]}),
            "StopBeamformer",
            json.dumps({"channel_groups": [1, 2, 4, 5]}),
        ),
        pytest.param(
            "StartBeamformer",
            "{}",
            "StartBeamformer",
            json.dumps(
                {
                    "start_time": None,
                    "duration": -1,
                    "scan_id": 0,
                }
            ),
        ),
        pytest.param(
            "StartBeamformer",
            json.dumps({"channel_groups": [1, 2, 4, 5]}),
            "StartBeamformer",
            json.dumps(
                {
                    "start_time": None,
                    "duration": -1,
                    "scan_id": 0,
                    "channel_groups": [1, 2, 4, 5],
                }
            ),
        ),
    ],
)
def test_station_tile_commands_lrc(
    mock_command_cls: unittest.mock.Mock,
    mock_composite_cls: unittest.mock.Mock,
    station_device: SpsStation,
    command: str,
    command_args: Any,
    mock_tile_device_proxies: DeviceProxy,
    tile_command: str,
    tile_command_args: Any,
) -> None:
    """
    Tests of station commands calling the corresponding command on Tile.

    :param mock_command_cls: a patched MccsCommandProxy
        class for to assert against.
    :param mock_composite_cls: a patched MccsCompositeCommandProxy
        class for to assert against.
    :param station_device: The station device to use
    :param command: The command to call on the station
    :param command_args: The arguments to call the command with
    :param mock_tile_device_proxies: The mock for the tiles to verify
        commands being called
    :param tile_command: The expected command to be called on the tile
    :param tile_command_args: The expected arguments for the command on the tile.
    """
    # Mock composite command
    mock_composite = MagicMock()
    mock_composite_cls.return_value = mock_composite
    mock_composite.__iadd__.return_value = mock_composite

    # Mock result of calling the composite command
    mock_composite.return_value = (ResultCode.OK, "Success")

    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]

    # Some commands require tile programming state to be Initialised or Synchronised
    for mock_tile_proxy in mock_tile_device_proxies:
        mock_tile_proxy.tileProgrammingState = "Synchronised"

    # The mock takes a non-negligible amount of time to write attributes
    # Brief sleep needed to allow it to write the tileProgrammingState
    time.sleep(0.2)

    if command_args is None:
        getattr(station_device, command)()
    else:
        getattr(station_device, command)(command_args)

    time.sleep(0.2)
    assert len(mock_tile_device_proxies) == 4
    mock_command_cls.assert_has_calls(
        [
            call(
                device_name=get_tile_name(1, "ci-1"),
                command_name=tile_command,
                logger=ANY,
                default_args=ANY,
            ),
            call(
                device_name=get_tile_name(2, "ci-1"),
                command_name=tile_command,
                logger=ANY,
                default_args=ANY,
            ),
            call(
                device_name=get_tile_name(3, "ci-1"),
                command_name=tile_command,
                logger=ANY,
                default_args=ANY,
            ),
            call(
                device_name=get_tile_name(4, "ci-1"),
                command_name=tile_command,
                logger=ANY,
                default_args=ANY,
            ),
        ]
    )


def test_SetCspIngest(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
    sdn_first_interface: str,
    sdn_gateway: str,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test of the SetCspIngest command.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    :param sdn_first_interface: CIDR-like specification of the first interface
        in the block allocated to this station for science data.
    :param sdn_gateway: IP address of the subnet gateway.
        An empty string signifiese that no gateway is defined.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    # We have the initial mocked state to be ON.
    change_event_callbacks["state"].assert_change_event(DevState.ON)
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
        tile.Configure40GCore.assert_not_called()


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
    station_device: SpsStation, sdn_first_interface: str
) -> None:
    """
    Test of the fortyGbNetworkAddress attribute.

    :param station_device: The station device to use
    :param sdn_first_interface: the first interface in the block
        assigned to this station for science data
    """
    first_interface = ipaddress.ip_interface(sdn_first_interface)
    assert station_device.fortyGbNetworkAddress == str(first_interface.ip)


def test_write_read_channeliser_rounding(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test we can set and read channeliserRounding.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    for i, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"

    channeliser_rounding_to_set = np.array([5] * 512)
    execute_lrc_to_completion(
        station_device,
        "SetChanneliserRounding",
        channeliser_rounding_to_set,
    )

    # Calculate expected channeliser rounding of all tiles after write
    zero_results = np.zeros((12, 512))
    channeliser_rounding_to_check: np.ndarray = np.concatenate(
        (np.array([channeliser_rounding_to_set] * 4), zero_results)
    )
    assert np.array_equal(
        station_device.channeliserRounding, channeliser_rounding_to_check
    )


def test_setting_cspRounding(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
    num_tiles: int,
) -> None:
    """
    Test for the cspRounding attribute.

    :param station_device: The station device to use
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)

    # Set the last tile with a different cspRounding.
    mock_tile_device_proxies[-1].cspRounding = [6] * 384

    assert all(station_device.cspRounding == [6] * 384)

    rounding_mocks = [unittest.mock.PropertyMock() for _ in range(num_tiles)]
    for _, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"
    for i in range(num_tiles):
        setattr(type(mock_tile_device_proxies[i]), "cspRounding", rounding_mocks[i])
    station_device.cspRounding = np.array([4] * 384)  # type: ignore[assignment]
    for i, mock in enumerate(rounding_mocks):
        if i == num_tiles - 1:
            assert all(mock.call_args[0][0] == [4] * 384)
        else:
            mock.assert_not_called()


def test_beamformerTable(
    station_device: SpsStation,
    mock_tile_device_proxies: list[unittest.mock.Mock],
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
    for _, tile in enumerate(mock_tile_device_proxies):
        tile.SetBeamformerRegions.assert_last_call(
            [4, 8, 0, 0, 0, 3, 1, 101, 26, 8, 1, 0, 24, 4, 2, 102]
        )
    assert not np.all(
        station_device.beamformerTable[0:14]
        == np.array([4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102])
    )
    station_device.MockBeamformerTableChange(
        json.dumps(
            {
                "tile_id": len(mock_tile_device_proxies) - 1,
                "value": [4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102]
                + [0] * 46 * 7,
            }
        )
    )
    assert np.all(
        station_device.beamformerTable[0:14]
        == np.array([4, 0, 0, 0, 3, 1, 101, 26, 1, 0, 24, 4, 2, 102])
    )


def test_beamformerRegions(
    station_device: SpsStation,
    mock_tile_device_proxies: list[DeviceProxy],
    num_tiles: int,
) -> None:
    """
    Test the beamformerRegions attribute.

    :param station_device: The station device to use
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param num_tiles: the number of mock tiles
    """
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    for _, tile in enumerate(mock_tile_device_proxies):
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.5)
    station_device.SetBeamFormerRegions(
        [64, 16, 1, 1, 8, 1, 1, 101, 128, 64, 1, 1, 72, 1, 1, 102]
    )
    assert np.all(
        station_device.beamformerRegions[0:16]
        == np.array([64, 16, 1, 1, 8, 1, 1, 101, 128, 64, 1, 1, 72, 1, 1, 102])
    ), station_device.beamformerRegions


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
    change_event_callbacks: MockTangoEventCallbackGroup,
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
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    sub_id = station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    station_device.unsubscribe_event(sub_id)

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


def test_stations_daq_trl(station_device: SpsStation) -> None:
    """
    Test that SPSStation properly stores its DAQ TRL.

    Tests that SPSStation initialises its DAQ TRL properly and is
        able to change its value.

    :param station_device: The station device to use.
    """
    assert station_device.LMCdaqTRL == get_lmc_daq_name()

    station_device.LMCdaqTRL = "NEW_DAQ_TRL"  # type: ignore[method-assign]

    assert station_device.LMCdaqTRL == "NEW_DAQ_TRL"


def test_AcquireDataForCalibration(
    station_device: SpsStation,
    daq_device: DeviceProxy,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    mock_daq_device_proxy: unittest.mock.Mock,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test the AcquireDaqtaForCalibration command.

    :param station_device: The station device to use.
    :param daq_device: the DAQ device proxy that would receive the data
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param mock_daq_device_proxy: A fixture returning a mocked MccsDaqReceiver device.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    first_channel = 106
    last_channel = 106

    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    daq_device.adminMode = 0

    for tile in mock_tile_device_proxies:
        tile.tileProgrammingState = "Synchronised"
    time.sleep(0.1)

    def _mocked_daq_status_callable_started() -> str:
        return json.dumps(
            {
                "Running Consumers": [["CORRELATOR_DATA", 8]],
                "Receiver Interface": "eth0",
                "Receiver Ports": [4660],
                "Receiver IP": ["10.244.170.166"],
                "Bandpass Monitor": False,
                "Daq Health": ["OK", 0],
            }
        )

    mock_daq_device_proxy.configure_mock(DaqStatus=_mocked_daq_status_callable_started)
    start_time = datetime.datetime.strftime(
        datetime.datetime.fromtimestamp(time.time() + 5), "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    [_], [command_id] = station_device.AcquireDataForCalibration(
        json.dumps(
            {
                "start_time": start_time,
                "first_channel": first_channel,
                "last_channel": last_channel,
            }
        )
    )
    tile_command_mock: MockCallable = getattr(
        mock_tile_device_proxies[0], "SendDataSamples"
    )

    tile_command_mock.assert_next_call(
        json.dumps(
            {
                "start_time": start_time,
                "data_type": "channel",
                "first_channel": first_channel,
                "last_channel": last_channel,
                "n_samples": 1835008,
            }
        )
    )
    assert (
        json.loads(daq_device.DaqStatus())["Running Consumers"][0][0]
        == "CORRELATOR_DATA"
    )
    station_device.MockCalibrationDataReceived()

    def _mocked_daq_status_callable_stopped() -> str:
        return json.dumps(
            {
                "Running Consumers": [],
                "Receiver Interface": "eth0",
                "Receiver Ports": [4660],
                "Receiver IP": ["10.244.170.166"],
                "Bandpass Monitor": False,
                "Daq Health": ["OK", 0],
            }
        )

    mock_daq_device_proxy.configure_mock(DaqStatus=_mocked_daq_status_callable_stopped)

    timeout = 20
    current_time = 0
    while current_time < timeout:
        try:
            assert (
                station_device.CheckLongRunningCommandStatus(command_id) == "COMPLETED"
            )
            break
        except AssertionError:
            time.sleep(1)
            current_time += 1
    assert station_device.CheckLongRunningCommandStatus(command_id) == "COMPLETED"


def test_health(
    station_device: SpsStation,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    mock_subrack_device_proxy: unittest.mock.Mock,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test station health rollup.

    :param station_device: The station device to use.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param mock_subrack_device_proxy: mock subrack proxy that has been configured with
        the required behaviours.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    # 1 Station, 1 Mock Subrack, 4 Mock Tiles.
    tile_trls = [get_tile_name(i + 1) for i in range(4)]
    subrack_trls = [get_subrack_name(1)]
    devices = subrack_trls + tile_trls

    station_device.subscribe_event(
        "healthState",
        EventType.CHANGE_EVENT,
        change_event_callbacks["health_state"],
    )
    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)

    change_event_callbacks["health_state"].assert_change_event(HealthState.UNKNOWN)

    # Set all device healths to OK. Station should be OK.
    for device in devices:
        station_device.MockSubdeviceHealth(
            json.dumps({"device": device, "health": HealthState.OK})
        )

    for tile_id in range(len(tile_trls)):
        station_device.MockTileProgrammingStateChange(
            json.dumps(
                {
                    "tile_id": tile_id,
                    "value": "Synchronised",
                }
            )
        )

    # needs looksahead > 5 because each tile change updates the state
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=6, consume_nonmatches=True
    )
    assert station_device.healthState == HealthState.OK

    # Set device health to trigger each degraded/failure.

    # --- 2 Degraded Tiles = Degraded ---
    for i in range(2):
        station_device.MockSubdeviceHealth(
            json.dumps({"device": tile_trls[i], "health": HealthState.DEGRADED})
        )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.DEGRADED, lookahead=1
    )
    assert station_device.healthState == HealthState.DEGRADED
    # Reset Tile health.
    for i in range(2):
        station_device.MockSubdeviceHealth(
            json.dumps({"device": tile_trls[i], "health": HealthState.OK})
        )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=1
    )
    assert station_device.healthState == HealthState.OK

    # --- 1 Failed Tile = Failed ---
    station_device.MockSubdeviceHealth(
        json.dumps({"device": tile_trls[3], "health": HealthState.FAILED})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.FAILED, lookahead=3
    )
    assert station_device.healthState == HealthState.FAILED
    # Reset Tile health.
    station_device.MockSubdeviceHealth(
        json.dumps({"device": tile_trls[3], "health": HealthState.OK})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=3
    )
    assert station_device.healthState == HealthState.OK

    # --- 1 Subrack Degraded = Degraded ---
    station_device.MockSubdeviceHealth(
        json.dumps({"device": subrack_trls[0], "health": HealthState.DEGRADED})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.DEGRADED, lookahead=1
    )
    assert station_device.healthState == HealthState.DEGRADED
    # Reset Subrack health.
    station_device.MockSubdeviceHealth(
        json.dumps({"device": subrack_trls[0], "health": HealthState.OK})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=1
    )
    assert station_device.healthState == HealthState.OK

    # --- 1 Subrack Failed = Failed ---
    station_device.MockSubdeviceHealth(
        json.dumps({"device": subrack_trls[0], "health": HealthState.FAILED})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.FAILED, lookahead=3
    )
    assert station_device.healthState == HealthState.FAILED
    # Reset Subrack health.
    station_device.MockSubdeviceHealth(
        json.dumps({"device": subrack_trls[0], "health": HealthState.OK})
    )
    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=3
    )
    assert station_device.healthState == HealthState.OK


def test_programing_state_health_rollup(
    station_device: SpsStation,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test station health rollup.

    :param station_device: The station device to use.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    station_device.subscribe_event(
        "healthState",
        EventType.CHANGE_EVENT,
        change_event_callbacks["health_state"],
    )
    station_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    station_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.ON)

    change_event_callbacks["health_state"].assert_change_event(HealthState.UNKNOWN)

    tile_trls = [get_tile_name(i + 1) for i in range(4)]
    subrack_trls = [get_subrack_name(1)]
    devices = subrack_trls + tile_trls

    # Set all device healths to OK. Station should be OK.
    for device in devices:
        station_device.MockSubdeviceHealth(
            json.dumps({"device": device, "health": HealthState.OK})
        )

    # needs looksahead >= 5 because each tile change updates the state
    for tile_id in range(len(tile_trls)):
        station_device.MockTileProgrammingStateChange(
            json.dumps(
                {
                    "tile_id": tile_id,
                    "value": "Synchronised",
                }
            )
        )

    change_event_callbacks["health_state"].assert_change_event(
        HealthState.OK, lookahead=5, consume_nonmatches=True
    )
    assert station_device.healthState == HealthState.OK

    station_device.MockTileProgrammingStateChange(
        json.dumps(
            {
                "tile_id": 1,
                "value": "Unknown",
            }
        )
    )

    change_event_callbacks["health_state"].assert_change_event(HealthState.DEGRADED)

    station_device.MockTileProgrammingStateChange(
        json.dumps(
            {
                "tile_id": 1,
                "value": "Synchronised",
            }
        )
    )
    change_event_callbacks["health_state"].assert_change_event(HealthState.OK)
    assert station_device.healthState == HealthState.OK


@pytest.mark.parametrize(
    ("expected_init_params", "new_params"),
    [
        pytest.param(
            {
                "subrack_degraded": 0.05,
                "subrack_failed": 0.2,
                "tile_degraded": 0.05,
                "tile_failed": 0.2,
                "pps_delta_degraded": 4,
                "pps_delta_failed": 9,
                "subracks": [1, 1, 1],  # Expect these to be overwritten
                "tiles": [1, 1, 2],  # Expect these to be overwritten
            },
            {
                "subrack_degraded": 0.1,
                "subrack_failed": 0.3,
                "tile_degraded": 0.07,
                "tile_failed": 0.2,
                "pps_delta_degraded": 6,
                "pps_delta_failed": 10,
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


def test_csp_set_reset(
    on_station_device: SpsStation,
    mock_tile_device_proxies: list[unittest.mock.Mock],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test the SetCspIngest and ResetCspIngest commands.

    :param on_station_device: The station device to use.
    :param mock_tile_device_proxies: mock tile proxies that have been configured with
        the required tile behaviours.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    assert on_station_device.state() == DevState.ON
    initial_csp_config = on_station_device.cspIngestConfig

    csp_ingest_config = json.dumps(
        {
            "destination_ip": "123.234.345.456",
            "source_port": 1234,
            "destination_port": 2345,
        }
    )
    rc, _ = on_station_device.SetCspIngest(csp_ingest_config)
    assert rc == ResultCode.OK
    assert csp_ingest_config == on_station_device.cspIngestConfig

    rc, _ = on_station_device.ResetCspIngest()
    assert rc == ResultCode.OK
    assert initial_csp_config == on_station_device.cspIngestConfig
