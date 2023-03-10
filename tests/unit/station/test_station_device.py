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
from typing import Generator

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
    tile_name: str,
    mock_tile: DeviceProxy,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param station_name: the name of the subrack Tango device
    :param patched_station_device_class: a subclass of SpsStation that
        has been patched with extra commands for use in testing
    :param subrack_name: the name of the subrack Tango device
    :param mock_subrack: a mock subrack proxy that has been configured
        with the required subrack behaviours.
    :param tile_name: the name of the subrack Tango device
    :param mock_tile: a mock tile proxy that has been configured with
        the required tile behaviours.

    :yields: a tango context.
    """
    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        station_name,
        patched_station_device_class,
        StationId=0,
        TileFQDNs=[tile_name],
        SubrackFQDNs=[subrack_name],
        CabinetNetworkAddress="10.0.0.0",
    )
    context_manager.add_mock_device(subrack_name, mock_subrack)
    context_manager.add_mock_device(tile_name, mock_tile)
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
