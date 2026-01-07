# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the bandpass monitor functionality."""
from __future__ import annotations

import json
import time
from typing import Any, Generator

import numpy as np
import pytest
import tango
from pytest_bdd import given, scenarios, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import (
    poll_until_consumers_running,
    poll_until_consumers_stopped,
    poll_until_state_change,
    verify_bandpass_state,
)
from tests.harness import get_lmc_daq_name, get_subrack_name, get_tile_name
from tests.test_tools import retry_communication

scenarios("./features/bandpass_monitor.feature")


@given(
    "we have a target station",
    target_fixture="station_name",
)
def station_name_fixture(
    station: tango.DeviceProxy | None,
    station_label: str | None,
    true_context: bool,
) -> str:
    """
    Return an available station to test against.

    :param station: the station we are testing against.
    :param station_label: a fixture returning the station label passed
        in from the environment.
    :param true_context: whether to test against an existing Tango deployment

    :return: the station to test against.
    """
    if not true_context:
        pytest.skip("This needs to be run in a true-context")
    try:
        if station is None:
            pytest.skip("No station to test against.")
        station.ping()
    except tango.DevFailed as e:
        pytest.fail(f"Target station is not reachable {e}")
    return station_label or "real-daq-1"


@pytest.fixture(name="daq_config")
def daq_config_fixture() -> dict[str, Any]:
    """
    Get the config to configure the daq with.

    :return: the config to configure the DAQ with.
    """
    return {
        "directory": "/product/test_eb_id/ska-low-mccs/test_scan_id/",
        "nof_tiles": 1,
        "append_integrated": False,
    }


@given("the DAQ is available", target_fixture="daq_device")
def daq_device_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the DAQ device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    daq_device = tango.DeviceProxy(get_lmc_daq_name(station_name))
    if daq_device.adminMode != AdminMode.ONLINE:
        daq_device.adminMode = AdminMode.ONLINE
    poll_until_state_change(daq_device, tango.DevState.ON)
    return daq_device


@given("a bandpass DAQ device", target_fixture="bandpass_daq_device")
def daq_device_off_fixture(station_name: str) -> tango.DeviceProxy:
    """
    Return a ``tango.DeviceProxy`` to the DAQ device under test.

    :param station_name: the name of the station under test.

    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    return tango.DeviceProxy(get_lmc_daq_name(station_name + "-bandpass"))


@when("the bandpass DAQ is set ONLINE", target_fixture="bandpass_daq_device")
def set_daq_device_online_fixture(
    bandpass_daq_device: tango.DeviceProxy,
) -> tango.DeviceProxy:
    """
    Set the daq device online.

    :param bandpass_daq_device: A 'tango.DeviceProxy' to the OFFLINE Daq device.
    :return: a ``tango.DeviceProxy`` to the DAQ device under test.
    """
    if not bandpass_daq_device.adminMode == AdminMode.OFFLINE:
        bandpass_daq_device.adminMode = AdminMode.OFFLINE
    bandpass_daq_device.adminMode = AdminMode.ONLINE
    poll_until_state_change(bandpass_daq_device, tango.DevState.ON)
    return bandpass_daq_device


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


@given("the Tile is routed to the DAQ")
def tile_ready_to_send_to_daq(
    daq_device: tango.DeviceProxy,
    synchronised_tile_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
) -> None:
    """
    Configure the Daq device for select data type.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param synchronised_tile_device: A 'tango.DeviceProxy' to the Tile device
        in Synchronised state.
    :param subrack_device: A 'tango.DeviceProxy' to the Subrack device.
    """
    if subrack_device.state() != tango.DevState.ON:
        subrack_device.adminMode = AdminMode.ONLINE
        poll_until_state_change(subrack_device, tango.DevState.ON, 5)
    daq_status = json.loads(daq_device.DaqStatus())

    tpm_lmc_config = {
        "mode": "1G",
        "destination_ip": daq_status["Receiver IP"][0],
        "destination_port": daq_status["Receiver Ports"][0],
    }
    synchronised_tile_device.SetLmcDownload(json.dumps(tpm_lmc_config))


@given("no consumers are running")
def daq_device_has_no_running_consumers(
    daq_device: tango.DeviceProxy,
) -> None:
    """
    Assert that daq receiver has no running consumers.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)

    status = json.loads(daq_device.DaqStatus())
    if status["Running Consumers"] != []:
        daq_device.Stop()  # Stops *all* consumers.
        poll_until_consumers_stopped(daq_device)


@given("the bandpass monitor is not running")
def monitor_not_running(daq_device: tango.DeviceProxy) -> None:
    """
    Ensure that the bandpass monitor is not running.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    if json.loads(daq_device.DaqStatus())["Bandpass Monitor"]:
        daq_device.StopBandpassMonitor()
        daq_monitor_stopped(daq_device)


@given("the DAQ is configured")
def daq_configure(
    daq_device: tango.DeviceProxy,
    daq_config: dict[str, Any],
) -> None:
    """
    Configure the Daq device.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param daq_config: the config to configure the DAQ with.
    """
    # Set initial state.
    if daq_device.state() != tango.DevState.ON:
        retry_communication(daq_device)
        poll_until_state_change(daq_device, tango.DevState.ON, 5)

    # Configure DAQ
    daq_device.Configure(json.dumps(daq_config))


@given("the DAQ is started with the integrated channel data consumer")
def daq_integrated_channel_running(
    daq_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Start the Daq device with integrated channel data.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    daq_device.Start(json.dumps({"modes_to_start": "INTEGRATED_CHANNEL_DATA"}))

    daq_device.subscribe_event(
        "dataReceivedResult",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["data_received_callback"],
    )
    change_event_callbacks["data_received_callback"].assert_change_event(Anything)
    time_elapsed = 0
    timeout = 10
    while time_elapsed < timeout:
        consumers = json.loads(daq_device.DaqStatus())["Running Consumers"]
        if consumers != [] and ["INTEGRATED_CHANNEL_DATA", 5] in consumers:
            break
        time.sleep(1)
        time_elapsed += 1
    assert ["INTEGRATED_CHANNEL_DATA", 5] in consumers


@then("the bandpass DAQ is started with the integrated channel data consumer")
def check_daq_integrated_channel_running(
    bandpass_daq_device: tango.DeviceProxy,
) -> None:
    """
    Check the Daq device has integrated channel data consumer running.

    :param bandpass_daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    poll_until_consumers_running(
        bandpass_daq_device,
        ["DaqModes.INTEGRATED_CHANNEL_DATA".rsplit(".", maxsplit=1)[-1]],
    )


@then("the bandpass DAQ has the bandpass monitor running")
def bandpass_daq_bandpass_monitor_running(
    bandpass_daq_device: tango.DeviceProxy,
) -> None:
    """
    Check the bandpass monitor is running.

    :param bandpass_daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    verify_bandpass_state(bandpass_daq_device, True)


@given("the bandpass monitor is running")
def daq_bandpass_monitor_running(
    daq_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Generator:
    """
    Start the bandpass monitor.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.

    :yields: To return cleanup
    """
    daq_device.subscribe_event(
        "xPolBandpass",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["daq_xPolBandpass"],
    )
    daq_device.subscribe_event(
        "yPolBandpass",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["daq_yPolBandpass"],
    )
    change_event_callbacks["daq_xPolBandpass"].assert_change_event(Anything)
    change_event_callbacks["daq_yPolBandpass"].assert_change_event(Anything)
    start_bandpass_result = daq_device.StartBandpassMonitor()

    if start_bandpass_result[0][0] == ResultCode.REJECTED:
        # Allow a rejection if already running.
        assert start_bandpass_result[1][0] == "Bandpass monitor already started."
    else:
        sub_id = daq_device.subscribe_event(
            "longRunningCommandResult",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["daq_long_running_command_result"],
        )
        change_event_callbacks["daq_long_running_command_result"].assert_change_event(
            (
                start_bandpass_result[1][0],
                json.dumps([ResultCode.OK, "Bandpass monitor active"]),
            ),
            lookahead=12,
            consume_nonmatches=True,
        )
        daq_device.unsubscribe_event(sub_id)

    verify_bandpass_state(daq_device, True)

    yield

    # Cleanup: Turn off bandpass monitor here if it's still on.
    if json.loads(daq_device.DaqStatus())["Bandpass Monitor"] is True:
        daq_device.StopBandpassMonitor()
        verify_bandpass_state(daq_device, False)


@when("the DAQ is commanded to stop monitoring bandpasses")
@then("the DAQ is commanded to stop monitoring bandpasses")
def daq_stop_bandpass_monitor(daq_device: tango.DeviceProxy) -> None:
    """
    Stop monitoring for bandpasses.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    result = daq_device.StopBandpassMonitor()
    assert result[1][0] == "Bandpass monitor stopping."


@then("the DAQ reports that it is stopping monitoring bandpasses")
def daq_monitor_stopped(
    daq_device: tango.DeviceProxy,
) -> None:
    """
    Confirm that the bandpass monitor process has stopped.

    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    """
    verify_bandpass_state(daq_device, False)


@when(
    "the Tile is commanded to send integrated channel data",
    target_fixture="initial_hdf5_count",
)
def tile_send_data(
    tile_device: tango.DeviceProxy,
) -> None:
    """
    Command the tile to start sending data.

    :param tile_device: A 'tango.DeviceProxy' to the Tile device.
    """
    # tile_device.SendDataSamples(json.dumps({"data_type": "channel", "n_samples": 16}))
    tile_device.ConfigureIntegratedChannelData(json.dumps({}))


@then("the DAQ reports that it has received integrated channel data")
def daq_received_data(
    change_event_callbacks: MockTangoEventCallbackGroup,
    tile_device: tango.DeviceProxy,
    station_name: str,
) -> None:
    """
    Confirm Daq has received data.

    :param station_name: the name of the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param tile_device: A 'tango.DeviceProxy' to the Tile device.
    """
    try:
        change_event_callbacks["data_received_callback"].assert_change_event(
            ("integrated_channel", Anything)
        )
    except AssertionError:
        # if station_name == "stfc-ral-2":
        #     pytest.xfail(
        #         "There seems to be a discrepency between the simulator and hardware."
        #         "When testing against hardware the datatype collected is burst_chan"
        #     )
        print("Change event queue content for data_received_callback:")
        while not change_event_callbacks[
            "data_received_callback"
        ]._callable._call_queue.empty():
            print(
                change_event_callbacks[
                    "data_received_callback"
                ]._callable._call_queue.get()
            )
        pytest.fail("No integrated_channel data was received")
    # Stop the data transmission, else it will continue forever.
    tile_device.StopIntegratedData()


@then("the DAQ saves bandpass data to its relevant attributes")
def daq_bandpasses_saved(
    daq_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    station_name: str,
) -> None:
    """
    Confirm the DAQ has stored bandpass data to its attributes.

    :param station_name: the name of the station under test.
    :param daq_device: A 'tango.DeviceProxy' to the Daq device.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    try:
        change_event_callbacks["daq_xPolBandpass"].assert_change_event(Anything)
        assert np.count_nonzero(daq_device.xPolBandpass) > 0
        change_event_callbacks["daq_yPolBandpass"].assert_change_event(Anything)
        assert np.count_nonzero(daq_device.yPolBandpass) > 0
    except AssertionError:
        # if station_name == "stfc-ral-2":
        #     pytest.xfail(
        #         "There is an issue with this stage at RAL."
        #         "Caught exception: list index out of range. "
        #         "Tile 1 out of bounds! Max tile number: 1"
        #         f"Failed with message {e}"
        #     )
        print("Change event queue content for daq_xPolBandpass:")
        while not change_event_callbacks[
            "daq_xPolBandpass"
        ]._callable._call_queue.empty():
            print(
                change_event_callbacks["daq_xPolBandpass"]._callable._call_queue.get()
            )
        pytest.fail("Bandpass callbacks got no update")
