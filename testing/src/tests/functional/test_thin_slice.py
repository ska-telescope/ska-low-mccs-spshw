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
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockCallable, MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness

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
            #{"name": "daq_01", "proxy": MccsDeviceProxy},
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
def turn_subrack_on(subrack_device, tpm_number, subrack_device_state_changed_callback, subrack_device_admin_mode_changed_callback, subrack_tpm_power_state_changed_callback, subrack_device_lrc_changed_callback):
    
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
    subrack_device_state_changed_callback.assert_last_change_event(
        starting_state
    )

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
def given_tile_off(tile_device):
    turn_tile_off()

@given("the TPM is on")
def given_tile_on():
    turn_tile_on()

@when("the user tells the subrack to turn the TPM on")
def turn_tile_on():
    pass

@when("the user tells the subrack to turn the TPM off")
def turn_tile_off():
    pass

@then("the subrack reports that the TPM is on")
def subrack_assert_tpm_on():
    pass

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
def tpm_assert_initialised():
    pass

@when("the user tells the TPM to start acquisition")
def start_acquisition():
    pass

@then("the TPM reports that it has successfully completed the data acquisition")
def tpm_assert_completed_data_acquisition():
    pass

@then("the TPM reports that it is synchronised")
def tpm_assert_synchronised():
    pass

@given("the DAQRX has not been started")
def daq_stopped():
    pass

@when("the user configures the DAQRX")
def configure_daq():
    pass

@then("the DAQRX reports that it has the provided configuration")
def daq_assert_configured():
    pass

@given("the DAQRX has been configured")
def given_daq_configured():
    configure_daq()

@when("the user starts the DAQRX")
def start_daq():
    pass

@then("the DAQRX reports that it has been started")
def assert_daq_started():
    pass

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

@then("the DAQRX reports that it has received data from the TPM")
def assert_daq_received_data():
    pass