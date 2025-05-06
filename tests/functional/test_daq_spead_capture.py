# -*- coding: utf-8 -*-
# pylint: skip-file
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the bdd test steps of the daq status reporting."""
from __future__ import annotations

import json
import os
from typing import Callable

import pytest
import tango
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import (
    expect_attribute,
    poll_until_consumers_stopped,
    poll_until_state_change,
)
from tests.harness import get_lmc_daq_name, get_subrack_name, get_tile_name

from ..test_tools import retry_communication

scenarios("./features/daq_spead_capture.feature")


@given(
    parsers.cfparse("this test is running against station {expected_station}."),
    target_fixture="station_name",
)
def station_context_fixture(
    expected_station: str,
    available_stations: list[str],
) -> str:
    """
    Return the name of the station under test.

    :param available_stations: a list of available stations in the
        context expected_station test is running.
    :param expected_station: the name of the station to test against.

    :return: the name of the station under test
    """
    if expected_station not in available_stations:
        pytest.skip(
            f"This test is designed for station {expected_station}. "
            f"This is not one of the {available_stations=}."
        )
    return expected_station


@given("the DAQ is available", target_fixture="daq_device")
def daq_device_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the DAQ device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    return tango.DeviceProxy(get_lmc_daq_name(station_name))


@given("the Tile is available", target_fixture="tile_device")
def tile_device_fixture(station_name: str) -> str:
    """
    Return a ``tango.DeviceProxy`` to the Tile device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the Tile device under test.
    """
    return tango.DeviceProxy(get_tile_name(10, station_name))


@given("the Subrack is available", target_fixture="subrack_device")
def subrack_device_fixture(station_name: str, subrack_id: int) -> str:
    """
    Return a ``tango.DeviceProxy`` to the subrack device under test.

    :param station_name: the name of the station under test.
    :param subrack_id: the id of the subrack used in this test.

    :return: a ``tango.DeviceProxy`` to the subrack device under test.
    """
    return tango.DeviceProxy(get_subrack_name(subrack_id, station_name))


@given(parsers.parse("DAQ is ready to receive {data_type} data type."))
def daq_ready_to_receive_beam(
    daq_device: tango.DeviceProxy,
    data_type: str,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Configure the Daq device for select data type.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param data_type: The data type to configure DAQ with
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    # Set initial state.
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)

    # Configure DAQ
    configuration = {
        "directory": "/product/test_eb_id/ska-low-mccs/test_scan_id/",
        "nof_tiles": 1,
        "append_integrated": False,
    }
    daq_device.Configure(json.dumps(configuration))
    daq_device.Start(json.dumps({"modes_to_start": data_type}))

    daq_device.subscribe_event(
        "dataReceivedResult",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["data_received_callback"],
    )
    change_event_callbacks["data_received_callback"].assert_change_event(Anything)


@given("MccsTile is routed to daq")
def tile_ready_to_send_to_daq(
    daq_device: tango.DeviceProxy,
    tile_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Configure the Daq device for select data type.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param tile_device: A 'tango.DeviceProxy' to the Tile device.
    :param subrack_device: A 'tango.DeviceProxy' to the Subrack device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    if subrack_device.state() != tango.DevState.ON:
        subrack_device.adminMode = 0
        poll_until_state_change(subrack_device, tango.DevState.ON, 5)

    if tile_device.state() != tango.DevState.ON:
        if tile_device.AdminMode != AdminMode.ONLINE:
            tile_device.subscribe_event(
                "adminMode",
                tango.EventType.CHANGE_EVENT,
                change_event_callbacks["tile_adminMode"],
            )
            change_event_callbacks["tile_adminMode"].assert_change_event(Anything)
            tile_device.adminMode = 0
            change_event_callbacks["tile_adminMode"].assert_change_event(
                AdminMode.ONLINE
            )

        tile_device.on()
        poll_until_state_change(tile_device, tango.DevState.ON, 100)

    if tile_device.tileProgrammingState not in ["Initialised", "Synchronised"]:
        assert expect_attribute(
            tile_device, "tileProgrammingState", "Initialised", timeout=240.0
        )

    # Start the ADCs and SDP processing chain.
    if tile_device.tileProgrammingState != "Synchronised":
        tile_device.startacquisition("{}")
        assert expect_attribute(tile_device, "tileProgrammingState", "Synchronised")

    assert tile_device.tileProgrammingState == "Synchronised"

    daq_status = json.loads(daq_device.DaqStatus())

    tpm_lmc_config = {
        "mode": "1G",
        "destination_ip": daq_status["Receiver IP"][0],
        "destination_port": int(daq_status["Receiver Ports"][0]),
    }
    tile_device.SetLmcDownload(json.dumps(tpm_lmc_config))


@given("the DAQ has no consumers running")
def daq_device_has_no_running_consumers(
    daq_device: tango.DeviceProxy,
) -> None:
    """
    Assert that daq receiver has no running consumers.

    :param daq_device: The daq_device fixture to use.
    """
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)

    status = json.loads(daq_device.DaqStatus())
    if status["Running Consumers"] != []:
        daq_device.Stop()  # Stops *all* consumers.
        poll_until_consumers_stopped(daq_device)


@when("MccsTile sends channel data type", target_fixture="initial_hdf5_count")
def send_simulated_data(
    tile_device: tango.DeviceProxy,
    get_hdf5_count: Callable,
) -> int:
    """
    Start sending simulated data.

    :param tile_device: A 'tango.DeviceProxy' to the Tile device.
    :param get_hdf5_count: A callable to return the number of hdf5 files
        in a directory.

    :return: the initial number of hdf5 files in directory.
    """
    initial_count = get_hdf5_count()
    tile_device.SendDataSamples(json.dumps({"data_type": "channel"}))
    return initial_count


@then(parsers.cfparse("Daq receives data {daq_modes_of_interest}"))
def check_capture(
    change_event_callbacks: MockTangoEventCallbackGroup,
    get_hdf5_count: Callable,
    initial_hdf5_count: int,
    station_name: str,
) -> None:
    """
    Confirm Daq has received the correct data.

    :param station_name: the name of the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param initial_hdf5_count: the initial number of hdf5 files in directory.
    :param get_hdf5_count: A callable to return the number of hdf5 files
        in a directory.
    """
    try:
        change_event_callbacks["data_received_callback"].assert_change_event(
            ("integrated_channel", Anything)
        )
    except AssertionError:
        if station_name == "stfc-ral-software":
            pytest.xfail(
                reason=(
                    "There is a discrepancy between the simulator and hardware."
                    " the hardware sends burst_channel."
                )
            )
        pytest.fail("No integrated data received.")
    final_hdf5_count = get_hdf5_count()
    assert final_hdf5_count - initial_hdf5_count >= 1


@pytest.fixture(name="get_hdf5_count", scope="session")
def get_hdf5_count_fixture(get_hdf5_files: Callable) -> Callable:
    """
    Return a function to count number of .hdf5 files in a given directory.

    :param get_hdf5_files: the a callable to retreive hdf5 files.

    :return: A function to count .hdf5 files in directory.
    """

    def _hdf5_count() -> int:
        return len(get_hdf5_files())

    return _hdf5_count


@pytest.fixture(name="get_hdf5_files", scope="session")
def get_hdf5_fixture(hdf5_directory: str) -> Callable:
    """
    Return a function to get .hdf5 files in a given directory.

    :param hdf5_directory: the hdf5 destination file.

    :return: A function return .hdf5 files in directory.
    """

    def _hdf5_files() -> list[str]:
        return [f for f in os.listdir(hdf5_directory) if f.endswith(".hdf5")]

    return _hdf5_files


@pytest.fixture(name="hdf5_directory", scope="session")
def hdf5_directory_fixture() -> str:
    """
    Return the path to the test-data directory.

    :return: the name of target hdf5 directory.
    """
    return "/test-data/test_eb_id/ska-low-mccs/test_scan_id"
