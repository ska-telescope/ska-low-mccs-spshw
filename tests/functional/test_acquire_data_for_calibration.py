# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the bdd test steps for AcquireDataForCalibration.

These tests exercise the ``SpsStation.AcquireDataForCalibration`` command
end-to-end against real hardware. We do not care about the contents of the
correlator files produced, only that the acquisition machinery
(station -> tiles -> DAQ correlator) yields one correlator file per requested
channel.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import pytest
import tango
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import poll_until_state_change
from tests.harness import get_lmc_daq_name, get_sps_station_name
from tests.test_tools import (
    AttributeWaiter,
    get_lrc_finished,
    retry_communication,
    wait_for_lrc_result,
)

scenarios("./features/acquire_data_for_calibration.feature")

# The acquisition is a long running command that has to configure the station,
# start the DAQ correlator, send channelised data from every tile and wait for
# a correlator file per channel. Give it plenty of headroom on real hardware.
ACQUIRE_TIMEOUT = 180


@given(
    parsers.cfparse("this test is running against station {expected_station}."),
    target_fixture="station_name",
)
def station_context_fixture(
    expected_station: str,
    available_stations: list[str],
    true_context: bool,
) -> str:
    """
    Return the name of the station under test.

    :param expected_station: the name of the station to test against.
    :param available_stations: a list of available stations in the context
        the test is running.
    :param true_context: whether to test against an existing Tango deployment.

    :return: the name of the station under test.
    """
    if not true_context:
        pytest.skip("This needs to be run in a true-context")
    if expected_station not in available_stations:
        pytest.skip(
            f"This test is designed for station {expected_station}. "
            f"This is not one of the {available_stations=}."
        )
    return expected_station


@pytest.fixture(name="station")
def station_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the SpsStation under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the SpsStation under test.
    """
    return tango.DeviceProxy(get_sps_station_name(station_name))


@given("the DAQ is available", target_fixture="daq_device")
def daq_device_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the DAQ device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    daq_device = tango.DeviceProxy(get_lmc_daq_name(station_name))
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)
    return daq_device


@given("the SpsStation is synchronised")
def station_is_synchronised(
    station: tango.DeviceProxy,
    station_tiles: list[tango.DeviceProxy],
    wait_for_lrcs_to_finish: Callable,
) -> None:
    """
    Ensure the SpsStation is ON with all tiles synchronised.

    ``AcquireDataForCalibration`` is rejected unless every tile is
    ``Synchronised``, so drive the station there before acquiring.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param station_tiles: the Tile devices belonging to the station under test.
    :param wait_for_lrcs_to_finish: callable that waits for LRCs on devices.
    """
    if station.adminMode not in [AdminMode.ONLINE, AdminMode.ENGINEERING]:
        station.adminMode = AdminMode.ONLINE
        AttributeWaiter(timeout=300).wait_for_value(
            station, "state", tango.DevState.ON, lookahead=5
        )
    wait_for_lrcs_to_finish(station_tiles + [station], timeout=300)

    if not all(status == "Synchronised" for status in station.tileProgrammingState):
        # Cycle STANDBY -> ON to (re)synchronise the tiles.
        station.standby()
        AttributeWaiter(timeout=300).wait_for_value(
            station, "state", tango.DevState.STANDBY
        )
        station.on()
        try:
            AttributeWaiter(timeout=300).wait_for_value(
                station, "state", tango.DevState.ON
            )
        except AssertionError:
            # Hardware can settle in ALARM, that is fine for this test.
            assert station.state() in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in station_tiles:
            AttributeWaiter(timeout=300).wait_for_value(
                tile, "tileProgrammingState", "Synchronised", lookahead=10
            )

    if not all(status == "Synchronised" for status in station.tileProgrammingState):
        pytest.fail(f"Not all tiles are Synchronised: {station.tileProgrammingState}")


@when(
    parsers.parse(
        "I acquire calibration data for channels {first_channel:d} to {last_channel:d}"
    ),
    target_fixture="acquisition",
)
def acquire_data_for_calibration(
    station: tango.DeviceProxy,
    daq_device: tango.DeviceProxy,
    first_channel: int,
    last_channel: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> dict[str, Any]:
    """
    Command the station to acquire calibration data for a range of channels.

    Subscribes to the DAQ ``dataReceivedResult`` attribute before issuing the
    command so that the correlator file events emitted during acquisition are
    captured for the assertion step.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param daq_device: A 'tango.DeviceProxy' to the DAQ device.
    :param first_channel: the first channel to acquire data for.
    :param last_channel: the last channel to acquire data for.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.

    :return: details of the submitted acquisition, for the assertion step.
    """
    daq_device.subscribe_event(
        "dataReceivedResult",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["data_received_callback"],
    )
    # Consume the initial (subscription) event.
    change_event_callbacks["data_received_callback"].assert_change_event(Anything)

    [result_code], [command_id] = station.AcquireDataForCalibration(
        json.dumps({"first_channel": first_channel, "last_channel": last_channel})
    )
    assert ResultCode(result_code) == ResultCode.QUEUED
    return {
        "command_id": command_id,
        "requested_channels": list(range(first_channel, last_channel + 1)),
    }


@then("the requested number of correlator files are produced")
def check_requested_correlator_files_produced(
    station: tango.DeviceProxy,
    acquisition: dict[str, Any],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Confirm a correlator file was produced for every requested channel.

    Two independent signals are checked:

    * the DAQ emits one ``("tc_correlator", ...)`` ``dataReceivedResult`` event per
      correlator file it writes, and
    * the command reports which requested channels failed to yield a correlator
      file via the ``dropped_channels`` field of its result.

    :param station: A 'tango.DeviceProxy' to the SpsStation device.
    :param acquisition: details of the submitted acquisition.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    command_id = acquisition["command_id"]
    requested_channels = acquisition["requested_channels"]

    # Waits for the LRC queue to drain and asserts it completed with OK.
    wait_for_lrc_result(station, command_id, ResultCode.OK, ACQUIRE_TIMEOUT)

    # One dataReceivedResult "correlator" event should have been pushed by the
    # DAQ for each requested channel's correlator file.
    data_received = change_event_callbacks["data_received_callback"]
    for _ in requested_channels:
        data_received.assert_change_event(
            ("tc_correlator", Anything), consume_nonmatches=True
        )

    # Cross-check against the command's own accounting: no requested channel
    # should have been dropped, i.e. every requested correlator file was made.
    finished = get_lrc_finished(station, command_id)
    _, payload = finished["result"]
    dropped_channels = payload["dropped_channels"]
    received_count = len(requested_channels) - len(dropped_channels)
    assert received_count == len(requested_channels), (
        f"Expected {len(requested_channels)} correlator files, "
        f"got {received_count}. Dropped channels: {dropped_channels}"
    )
