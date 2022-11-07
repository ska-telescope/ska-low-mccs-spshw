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
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            # {"name": "daq_01", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def tile_device(tiles):
    return tiles[1]


@pytest.fixture()
def subrack_device(subrack):
    return subrack


@pytest.fixture()
def daq_device(daq):
    return daq


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
def given_tile_off(subrack_device, tile_device):
    if tile_device.state() != tango.DevState.OFF:
        turn_tile_off(subrack_device, tile_device)


@given("the TPM is on")
def given_tile_on(subrack_device, tile_device):
    if subrack.state() != tango.DevState.ON:
        turn_subrack_on(
            subrack_device,
            tpm_number,
            subrack_device_state_changed_callback,
            subrack_device_admin_mode_changed_callback,
            subrack_tpm_power_state_changed_callback,
            subrack_device_lrc_changed_callback,
        )
    if tile_device.state() != tango.DevState.ON:
        turn_tile_on(subrack_device, tile_device)


@when("the user tells the subrack to turn the TPM on")
def turn_tile_on(
    tile_device,
    tile_device_state_changed_callback,
    tile_device_admin_mode_changed_callback,
    tile_device_lrc_changed_callback,
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
    tile_device_state_changed_callback.assert_next_change_event(
        starting_state
    )
    tile_device.add_change_event_callback(
        "longRunningCommandResult",
        tile_device_lrc_changed_callback,
    )
    assert (
        "longRunningCommandResult".casefold()
        in tile_device._change_event_subscription_ids
    )

    initial_lrc_result = ("", "")
    assert tile_device.longRunningCommandResult == initial_lrc_result
    tile_device_lrc_changed_callback.assert_next_change_event(initial_lrc_result)

    tile_device.adminMode = AdminMode.ONLINE
    if starting_admin_mode == AdminMode.ONLINE:
        assert starting_state == tango.DevState.ON
    else:
        tile_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

        if starting_state != tango.DevState.ON:
            [result_code], [unique_id] = tile_device.On()

            tile_device_state_changed_callback.assert_last_change_event(
                tango.DevState.ON
            )

        if starting_admin_mode != AdminMode.MAINTENANCE:
            tile_device_lrc_changed_callback.assert_next_call(
                "longrunningcommandresult",
                (unique_id, '"On command has completed"'),
                tango.AttrQuality.ATTR_VALID,
            )
    assert tile_device.adminMode == AdminMode.ONLINE
    assert tile_device.state() == tango.DevState.ON


@when("the user tells the subrack to turn the TPM off")
def turn_tile_off():
    pass


@then("the subrack reports that the TPM is on")
def subrack_assert_tpm_on(subrack_device_lrc_changed_callback,
tpm_number):
    args = subrack_device_lrc_changed_callback.get_next_call()
    assert "_PowerOnTpm" in args[0][1][0]
    assert (
        args[0][1][1]
        == f'"Subrack TPM {tpm_number} turn on tpm task has completed"'
    )


@then("the TPM reports that it is on")
def tpm_assert_on():
    pass


@then("the subrack reports that the TPM is off")
def subrack_assert_tpm_off():
    pass


@then("the TPM reports that it is off")
def tpm_assert_off():
    pass


@then("the TPM reports that it is initialised")
def tpm_assert_initialised(tile_device):
    maxTimeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Initialised" and count < maxTimeout:
        time.sleep(0.5)
        count+=1
    assert tile_device.tileProgrammingState == "Initialised"


@when("the user tells the TPM to start acquisition")
def start_acquisition(tile_device):
    ([return_code], [unique_id]) = tile_device.StartAcquisition(
        '{"StartTime":10, "Delay":20}'
    )
    assert return_code == ResultCode.QUEUED
    assert "_StartAcquisition" in unique_id



@then("the TPM reports that it has successfully completed the data acquisition")
def tpm_assert_completed_data_acquisition():
    lrc_result_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (unique_id, '"Start acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@then("the TPM reports that it is synchronised")
def tpm_assert_synchronised():
    maxTimeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Synchronised" and count < maxTimeout:
        time.sleep(0.5)
        count+=1
    assert tile_device.tileProgrammingState == "Synchronised"


@given("the DAQRX has not been started")
def daq_stopped():
    pass


@when("the user configures the DAQRX")
def configure_daq():
    daq_config = {
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

    daq_device.Configure(daq_config)


@then("the DAQRX reports that it has the provided configuration")
def daq_assert_configured(daq_config):
    assert daq_device.configuration().items() == daq_config



@given("the DAQRX has been configured")
def given_daq_configured():
    configure_daq()


@when("the user starts the DAQRX")
def start_daq():
    daq_start_callback = MockCallable()
    daq_device.Start(
        task_callback=daq_start_callback, callbacks=[processed_data_callback]
    )


@then("the DAQRX reports that it has been started")
def assert_daq_started(daq_start_callback):
    daq_start_callback.assert_next_call(status=TaskStatus.QUEUED)
    daq_start_callback.assert_next_call(status=TaskStatus.IN_PROGRESS)
    daq_start_callback.assert_next_call(status=TaskStatus.COMPLETED)

@given("the DAQRX has been started")
def given_daq_started():
    pass


@when("the user stops the DAQRX")
def stop_daq():
    pass


@then("the DAQRX reports that it has been stopped")
def assert_daq_stopped():
    pass


@given("the TPM is synchronised")
def synchronise_tpm():
    pass


@when("the user tells the TPM to send data")
def tpm_send_data():
    pass


@then("the TPM does not report a fault")
def tpm_check_no_fault():
    pass


@then("the DAQRX reports that it has received data from the TPM")
def assert_daq_received_data():
    pass
