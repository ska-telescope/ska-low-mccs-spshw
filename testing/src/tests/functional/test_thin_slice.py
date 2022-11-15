# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import time
import datetime
import json

import pytest
import tango
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockCallable, MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

scenarios("features/thin_slice.feature")


@pytest.fixture(scope="module")
def devices_to_load(tpm_number) -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": f"tile_000{tpm_number}", "proxy": MccsDeviceProxy},
            {"name": "daq_01", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def tile_device(tiles, tpm_number):
    return tiles[tpm_number]


@pytest.fixture()
def subrack_device(subrack):
    return subrack


@pytest.fixture()
def daq_device(daq):
    return daq

@pytest.fixture()
def daq_start_callback():
    return MockCallable()


@pytest.fixture()
def daq_processed_data_callback():
    return MockCallable()

@pytest.fixture()
def daq_config():
    return {
        "nof_antennas": 16,
        "nof_channels": 512,
        "nof_beams": 1,
        "nof_polarisations": 2,
        "nof_tiles": 1,
        "nof_raw_samples": 32768,
        "raw_rms_threshold": -1,
        "nof_channel_samples": 1024,
        "nof_correlator_samples": 1835008,
        "nof_correlator_channels": 1,
        "continuous_period": 0,
        "nof_beam_samples": 42,
        "nof_beam_channels": 384,
        "nof_station_samples": 262144,
        "append_integrated": True,
        "sampling_time": 1.1325,
        "sampling_rate": (800e6 / 2.0) * (32.0 / 27.0) / 512.0,
        "oversampling_factor": 32.0 / 27.0,
        "receiver_ports": "4660",
        "receiver_interface": "eth0",
        "receiver_ip": "8080",
        "receiver_frame_size": 8500,
        "receiver_frames_per_block": 32,
        "receiver_nof_blocks": 256,
        "receiver_nof_threads": 1,
        "directory": ".",
        "logging": True,
        "write_to_disk": True,
        "station_config": None,
        "max_filesize": None,
        "acquisition_duration": -1,
        "acquisition_start_time": -1,
        "description": "This is a test configuration",
    }

@given("the subrack is online")
def turn_subrack_on(
    subrack_device,
    tpm_number,
    subrack_device_state_changed_callback,
    subrack_device_admin_mode_changed_callback,
    subrack_tpm_power_state_changed_callback,
    subrack_device_lrc_changed_callback,
):

    starting_admin_mode = subrack_device.adminMode
    subrack_device.add_change_event_callback(
        "adminMode",
        subrack_device_admin_mode_changed_callback,
    )
    subrack_device_admin_mode_changed_callback.assert_next_change_event(
        starting_admin_mode
    )

    starting_state = subrack_device.state()
    subrack_device.add_change_event_callback(
        "state",
        subrack_device_state_changed_callback,
    )
    subrack_device_state_changed_callback.assert_last_change_event(starting_state)

    starting_tpm_power_state = subrack_device.read_attribute(
        f"tpm{tpm_number}PowerState"
    )
    subrack_device.add_change_event_callback(
        f"tpm{tpm_number}PowerState",
        subrack_tpm_power_state_changed_callback,
    )
    subrack_tpm_power_state_changed_callback.assert_last_change_event(
        starting_tpm_power_state.value, starting_tpm_power_state.quality
    )

    # Subscribe to subrack's LRC result attribute
    subrack_device.add_change_event_callback(
        "longRunningCommandResult",
        subrack_device_lrc_changed_callback,
    )
    assert (
        "longRunningCommandResult".casefold()
        in subrack_device._change_event_subscription_ids
    )

    initial_lrc_result = ("", "")
    assert subrack_device.longRunningCommandResult == initial_lrc_result
    subrack_device_lrc_changed_callback.assert_next_change_event(initial_lrc_result)

    subrack_device.adminMode = AdminMode.ONLINE
    if starting_admin_mode == AdminMode.ONLINE:
        assert starting_state == tango.DevState.ON
    else:
        subrack_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

        if starting_state != tango.DevState.ON:
            [result_code], [unique_id] = subrack_device.On()

            subrack_device_state_changed_callback.assert_last_change_event(
                tango.DevState.ON
            )

            if starting_admin_mode != AdminMode.MAINTENANCE:
                subrack_device_lrc_changed_callback.assert_next_call(
                    "longrunningcommandresult",
                    (unique_id, '"On command has completed"'),
                    tango.AttrQuality.ATTR_VALID,
                )
    assert subrack_device.adminMode == AdminMode.ONLINE
    assert subrack_device.state() == tango.DevState.ON


@given("the TPM is off")
def given_tile_off(subrack_device, tile_device, tpm_number, tile_device_state_changed_callback, tile_device_lrc_changed_callback, subrack_device_lrc_changed_callback):
    tpm_power_state = subrack_device.read_attribute(
        f"tpm{tpm_number}PowerState"
    )
    if tpm_power_state != PowerState.OFF:
        turn_tile_off(tile_device, tpm_number, tile_device_state_changed_callback, tile_device_lrc_changed_callback, subrack_device_lrc_changed_callback)


@given("the TPM is on")
def given_tile_on(
    subrack_device,
    tile_device,
    tpm_number,
    subrack_device_state_changed_callback,
    subrack_device_admin_mode_changed_callback,
    subrack_tpm_power_state_changed_callback,
    subrack_device_lrc_changed_callback,
    tile_device_state_changed_callback,
    tile_device_admin_mode_changed_callback,
    tile_device_lrc_changed_callback
):
    if subrack_device.state() != tango.DevState.ON:
        turn_subrack_on(
            subrack_device,
            tpm_number,
            subrack_device_state_changed_callback,
            subrack_device_admin_mode_changed_callback,
            subrack_tpm_power_state_changed_callback,
            subrack_device_lrc_changed_callback,
        )
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")

    if tpm_power_state != PowerState.ON:
        turn_tile_on(
            subrack_device,
            tile_device,
            tpm_number,
            tile_device_state_changed_callback,
            tile_device_admin_mode_changed_callback,
            tile_device_lrc_changed_callback,
            subrack_device_lrc_changed_callback
        )


@when("the user tells the subrack to turn the TPM on")
def turn_tile_on(
    subrack_device,
    tile_device,
    tpm_number,
    tile_device_state_changed_callback,
    tile_device_admin_mode_changed_callback,
    tile_device_lrc_changed_callback,
    subrack_device_lrc_changed_callback
):
    starting_admin_mode = tile_device.adminMode
    tile_device.add_change_event_callback(
        "adminMode",
        tile_device_admin_mode_changed_callback,
    )
    tile_device_admin_mode_changed_callback.assert_next_change_event(
        starting_admin_mode
    )

    starting_state = tile_device.state()
    tile_device.add_change_event_callback(
        "state",
        tile_device_state_changed_callback,
    )
    tile_device_state_changed_callback.assert_next_change_event(starting_state)
    
    tile_device.add_change_event_callback(
        "longRunningCommandResult",
        tile_device_lrc_changed_callback,
    )
    assert (
        "longRunningCommandResult".casefold()
        in tile_device._change_event_subscription_ids
    )

    tile_device_lrc_changed_callback.assert_next_change_event(tile_device.longRunningCommandResult)

    tile_device.adminMode = AdminMode.ONLINE
    assert subrack_device.adminMode == AdminMode.ONLINE
    if starting_admin_mode != AdminMode.ONLINE:
        tile_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

    if starting_state != tango.DevState.ON:
        [result_code], [unique_id] = tile_device.On()
        tile_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        if starting_admin_mode != AdminMode.MAINTENANCE:
            args = tile_device_lrc_changed_callback.get_next_call()
            assert "_On" in args[0][1][0]
    assert tile_device.adminMode == AdminMode.ONLINE
    
    args = subrack_device_lrc_changed_callback.get_next_call()
    assert "_PowerOnTpm" in args[0][1][0]
    assert args[0][1][1] == f'"Subrack TPM {tpm_number} turn on tpm task has completed"'


@when("the user tells the subrack to turn the TPM off")
def turn_tile_off(tile_device, tpm_number, tile_device_state_changed_callback, tile_device_lrc_changed_callback, subrack_device_lrc_changed_callback):
    assert tile_device.adminMode == AdminMode.ONLINE
    [result_code], [unique_id] = tile_device.Off()
    tile_device_state_changed_callback.assert_last_change_event(
        tango.DevState.OFF
    )

    args = tile_device_lrc_changed_callback.get_next_call()
    assert "_Off" in args[0][1][0]

    args = subrack_device_lrc_changed_callback.get_next_call()
    assert "_PowerOffTpm" in args[0][1][0]
    assert args[0][1][1] == f'"Subrack TPM {tpm_number} turn off tpm task has completed"'


@then("the subrack reports that the TPM is on")
def subrack_assert_tpm_on(subrack_device, tpm_number):
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")

    assert tpm_power_state == PowerState.ON


@then("the TPM reports that it is on")
def tpm_assert_on(tile_device):#
    assert tile_device.state() == tango.DevState.ON


@then("the subrack reports that the TPM is off")
def subrack_assert_tpm_off(subrack_device, tpm_number):
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")
    assert tpm_power_state == PowerState.OFF


@then("the TPM reports that it is off")
def tpm_assert_off(tile_device):
    assert tile_device.state() == tango.DevState.OFF


@then("the TPM reports that it is initialised")
def tpm_assert_initialised(tile_device):
    maxTimeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Initialised" and count < maxTimeout:
        time.sleep(0.5)
        count += 1
    assert tile_device.tileProgrammingState == "Initialised"


@when("the user tells the TPM to start acquisition", target_fixture="tpm_acquisition_unique_id")
def start_acquisition(tile_device):
    ([return_code], [unique_id]) = tile_device.StartAcquisition(
        '{"StartTime":10, "Delay":20}'
    )
    assert return_code == ResultCode.QUEUED
    assert "_StartAcquisition" in unique_id
    return unique_id


@then("the TPM reports that it is acquiring data")
def tpm_assert_data_acquisition(tile_device, tile_device_lrc_changed_callback, tpm_acquisition_unique_id):

    t0 = datetime.datetime.strptime(tile_device.fpgaFrameTime,"%Y-%m-%dT%H:%M:%S.%fZ")
    time.sleep(1.0)
    t1 = datetime.datetime.strptime(tile_device.fpgaFrameTime,"%Y-%m-%dT%H:%M:%S.%fZ")
    timediff = datetime.datetime.timestamp(t1)-datetime.datetime.timestamp(t0)

    assert 0.9 < timediff and timediff < 1.1

    tile_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (tpm_acquisition_unique_id, '"Start acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@then("the TPM reports that it is synchronised")
def tpm_assert_synchronised(tile_device):
    maxTimeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Synchronised" and count < maxTimeout:
        time.sleep(0.5)
        count += 1
    assert tile_device.tileProgrammingState == "Synchronised"


@given("the DAQRX has not been started")
def daq_stopped(daq_device):
    stop_daq(daq_device)

@when("the user configures the DAQRX")
def configure_daq(daq_device, daq_config):
    daq_device.Configure(daq_config)


@then("the DAQRX reports that it has the provided configuration")
def daq_assert_configured(daq_device, daq_config):
    assert daq_device.configuration().items() == daq_config


@given("the DAQRX has been configured")
def given_daq_configured(daq_device, daq_config):
    configure_daq(daq_device, daq_config)


@when("the user starts the DAQRX", target_fixture="daq_start_unique_id")
def start_daq(daq_device, daq_start_callback, daq_processed_data_callback):
    #DaqModes.RAW_DATA is 0 hence the 0 here
    config = {
        "task_callback": daq_start_callback,
        "modes_to_start":[0],
        "callbacks": [daq_processed_data_callback]
    }
    ([return_code], [unique_id])  = daq_device.Start(
        json.dumps(config)
    )
    assert return_code == ResultCode.QUEUED
    assert "_Start" in unique_id
    return unique_id


@then("the DAQRX reports that it has been started")
def assert_daq_started(daq_device_lrc_changed_callback, daq_start_unique_id):
    daq_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (daq_start_unique_id, '"Start acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@given("the DAQRX has been started")
def given_daq_started(daq_device, daq_processed_data_callback):
    start_daq(daq_device, daq_processed_data_callback)


@when("the user stops the DAQRX", target_fixture="daq_stop_unique_id")
def stop_daq():
    ([return_code], [unique_id]) = daq_device.Stop()
    assert return_code == ResultCode.QUEUED
    assert "_Stop" in unique_id
    return unique_id


@then("the DAQRX reports that it has been stopped")
def assert_daq_stopped(daq_device_lrc_changed_callback, daq_stop_unique_id):
    daq_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (daq_stop_unique_id, '"Start acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@given("the TPM is synchronised")
def synchronise_tpm(subrack_device, tile_device, tpm_number, tile_device_state_changed_callback, tile_device_admin_mode_changed_callback, tile_device_lrc_changed_callback, subrack_device_lrc_changed_callback):
    if tile_device.state() != tango.DevState.ON:
        turn_tile_on(subrack_device, tile_device, tpm_number, tile_device_state_changed_callback, tile_device_admin_mode_changed_callback, tile_device_lrc_changed_callback, subrack_device_lrc_changed_callback)
    if tile_device.tileProgrammingState != "Synchronised":
        start_acquisition(tile_device)
    tpm_assert_synchronised(tile_device)


@when("the user tells the TPM to send data")
def tpm_send_data(tile_device):
    ([return_code], [unique_id]) = tile_device.SendRawData()
    assert return_code == ResultCode.QUEUED
    assert "_SendRawData" in unique_id


@then("the TPM does not report a fault")
def tpm_check_no_fault(tile_device, tile_device_device_state_changed_callback):
    assert tile_device.state() == tango.DevState.ON
    assert tile_device_device_state_changed_callback.assert_not_called()


@then("the DAQRX reports that it has received data from the TPM")
def assert_daq_received_data(daq_processed_data_callback):
    assert len(daq_processed_data_callback.get_whole_queue()) > 0
