# -*- coding: utf-8 -*-
# pylint: skip-file
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import datetime
import json
import time
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenarios, then, when
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockCallable, MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType

scenarios("features/thin_slice.feature")


@pytest.fixture(scope="module")
def devices_to_load(tpm_number: int) -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :param tpm_number: the id of the tpm to load.
    :return: specification of the devices to be loaded.
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
def tile_device(tiles: dict[int, MccsDeviceProxy], tpm_number: int) -> MccsDeviceProxy:
    """
    Return the tile device.

    :param tiles: fixture for the list of tiles.
    :param tpm_number: the id of the tpm to use.
    :return: the tile device.
    """
    return tiles[tpm_number]


@pytest.fixture()
def subrack_device(subrack: MccsDeviceProxy) -> MccsDeviceProxy:
    """
    Return the subrack device.

    :param subrack: the subrack fixture to use.
    :return: the subrack device.
    """
    return subrack


@pytest.fixture()
def daq_device(daq: MccsDeviceProxy) -> MccsDeviceProxy:
    """
    Return the daq device.

    :param daq: the daq fixture to use.
    :return: the daq device.
    """
    return daq


@pytest.fixture()
def daq_processed_data_callback_fixture() -> MockCallable:
    """
    Return the callback to be called when the daq processes some data.

    :return: a mock object for the callback.
    """
    return MockCallable()


@pytest.fixture()
def daq_config_fixture() -> dict[str, Any]:
    """
    Return the configuration to be provided to the daq.

    :return: a dictionary containing the configuration.
    """
    return {
        "receiver_ports": [4660],
        "receiver_interface": "eth0",
        "receiver_ip": "10.0.10.2",
        "directory": ".",
    }


@given("the subrack is online")
def turn_subrack_on(
    subrack_device: MccsDeviceProxy,
    tpm_number: int,
    subrack_device_state_changed_callback: MockChangeEventCallback,
    subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
    subrack_tpm_power_state_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the subrack on if necessary.

    Also sets up the necessary callbacks for the subrack.

    :param subrack_device: the subrack fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param subrack_device_state_changed_callback: a callback that we can use
        to subscribe to state changes on the subrack device.
    :param subrack_device_admin_mode_changed_callback: a callback that we can
        use to subscribe to admin mode changes on the subrack device.
    :param subrack_tpm_power_state_changed_callback: a callback that we can
        use to subscribe to tpm power state changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    """
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
def given_tile_off(
    subrack_device: MccsDeviceProxy,
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the tile device off if necessary.

    :param subrack_device: the subrack fixture to use.
    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    """
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")
    if tpm_power_state != PowerState.OFF:
        turn_tile_off(
            tile_device,
            tpm_number,
            tile_device_state_changed_callback,
            tile_device_lrc_changed_callback,
            subrack_device_lrc_changed_callback,
        )


@given("the TPM is on")
def given_tile_on(
    subrack_device: MccsDeviceProxy,
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    subrack_device_state_changed_callback: MockChangeEventCallback,
    subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
    subrack_tpm_power_state_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_admin_mode_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the tile (and subrack) on if necessary.

    :param subrack_device: the subrack fixture to use.
    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param subrack_device_state_changed_callback: a callback that we can use
        to subscribe to state changes on the subrack device.
    :param subrack_device_admin_mode_changed_callback: a callback that we can
        use to subscribe to admin mode changes on the subrack device.
    :param subrack_tpm_power_state_changed_callback: a callback that we can
        use to subscribe to tpm power state changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_admin_mode_changed_callback: a callback that we can use
        to subscribe to admin mode changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    """
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
            subrack_device_lrc_changed_callback,
        )


@when("the user tells the subrack to turn the TPM on")
def turn_tile_on(
    subrack_device: MccsDeviceProxy,
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_admin_mode_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the tile on.

    Also sets up any necessary callbacks

    :param subrack_device: the subrack fixture to use.
    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_admin_mode_changed_callback: a callback that we can use
        to subscribe to admin mode changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    """
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

    tile_device_lrc_changed_callback.assert_next_change_event(
        tile_device.longRunningCommandResult
    )

    tile_device.adminMode = AdminMode.ONLINE
    assert subrack_device.adminMode == AdminMode.ONLINE
    if starting_admin_mode != AdminMode.ONLINE:
        tile_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

    if starting_state != tango.DevState.ON:
        [result_code], [unique_id] = tile_device.On()
        tile_device_state_changed_callback.assert_last_change_event(tango.DevState.ON)
        if starting_admin_mode != AdminMode.MAINTENANCE:
            tile_device_lrc_changed_callback.assert_next_call(
                "longrunningcommandresult",
                (unique_id, '"On command has completed"'),
                tango.AttrQuality.ATTR_VALID,
            )
    assert tile_device.adminMode == AdminMode.ONLINE

    args = subrack_device_lrc_changed_callback.get_next_call()
    assert "_PowerOnTpm" in args[0][1][0]
    assert args[0][1][1] == (
        f'"Subrack TPM {tpm_number} turn on tpm task has' ' completed"'
    )


@when("the user tells the subrack to turn the TPM off")
def turn_tile_off(
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the tile off.

    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    """
    assert tile_device.adminMode == AdminMode.ONLINE
    [result_code], [unique_id] = tile_device.Off()
    tile_device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)

    args = tile_device_lrc_changed_callback.get_next_call()
    assert "_Off" in args[0][1][0]

    args = subrack_device_lrc_changed_callback.get_next_call()
    assert "_PowerOffTpm" in args[0][1][0]
    assert args[0][1][1] == (
        f'"Subrack TPM {tpm_number} turn off tpm task has' ' completed"'
    )


@then("the subrack reports that the TPM is on")
def subrack_assert_tpm_on(subrack_device: MccsDeviceProxy, tpm_number: int) -> None:
    """
    Verify that the subrack returns the ON power state for the TPM.

    :param subrack_device: the subrack fixture to use.
    :param tpm_number: the id of the tpm to use.
    """
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")

    assert tpm_power_state == PowerState.ON


@then("the TPM reports that it is on")
def tpm_assert_on(tile_device: MccsDeviceProxy) -> None:
    """
    Verify that the tile has the ON state.

    :param tile_device: the tile fixture to use.
    """
    assert tile_device.state() == tango.DevState.ON


@then("the subrack reports that the TPM is off")
def subrack_assert_tpm_off(subrack_device: MccsDeviceProxy, tpm_number: int) -> None:
    """
    Verify that the subrack returns the ON power state for the TPM.

    :param subrack_device: the subrack fixture to use.
    :param tpm_number: the id of the tpm to use.
    """
    tpm_power_state = getattr(subrack_device, f"tpm{tpm_number}PowerState")
    assert tpm_power_state == PowerState.OFF


@then("the TPM reports that it is off")
def tpm_assert_off(tile_device: MccsDeviceProxy) -> None:
    """
    Verify that the tile has the ON state.

    :param tile_device: the tile fixture to use.
    """
    assert tile_device.state() == tango.DevState.OFF


@then("the TPM reports that it is initialised")
def tpm_assert_initialised(tile_device: MccsDeviceProxy) -> None:
    """
    Verify that the tile enters the initialised programming state.

    :param tile_device: the tile fixture to use.
    """
    max_timeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Initialised" and count < max_timeout:
        time.sleep(0.5)
        count += 1
    assert tile_device.tileProgrammingState == "Initialised"


@given("the TPM reports that it is initialised")
def initialise_tpm(
    subrack_device: MccsDeviceProxy,
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    subrack_device_state_changed_callback: MockChangeEventCallback,
    subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
    subrack_tpm_power_state_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_admin_mode_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn the tile on and verify it is initialised.

    :param subrack_device: the subrack fixture to use.
    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param subrack_device_state_changed_callback: a callback that we can use
        to subscribe to state changes on the subrack device.
    :param subrack_device_admin_mode_changed_callback: a callback that we can
        use to subscribe to admin mode changes on the subrack device.
    :param subrack_tpm_power_state_changed_callback: a callback that we can
        use to subscribe to tpm power state changes on the subrack device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_admin_mode_changed_callback: a callback that we can use
        to subscribe to admin mode changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the tile device.
    """
    given_tile_on(
        subrack_device,
        tile_device,
        tpm_number,
        subrack_device_state_changed_callback,
        subrack_device_admin_mode_changed_callback,
        subrack_tpm_power_state_changed_callback,
        subrack_device_lrc_changed_callback,
        tile_device_state_changed_callback,
        tile_device_admin_mode_changed_callback,
        tile_device_lrc_changed_callback,
    )

    tpm_assert_initialised(tile_device)


@when(
    "the user tells the TPM to start acquisition",
    target_fixture="tpm_acquisition_unique_id",
)
def start_acquisition(tile_device: MccsDeviceProxy) -> str:
    """
    Start data acquisition on the tile.

    :param tile_device: the tile fixture to use.
    :return: the command unique id
    """
    ([return_code], [unique_id]) = tile_device.StartAcquisition(
        '{"StartTime":10, "Delay":20}'
    )
    assert return_code == ResultCode.QUEUED
    assert "_StartAcquisition" in unique_id
    return unique_id


@then("the TPM reports that it is acquiring data")
def tpm_assert_data_acquisition(
    tile_device: MccsDeviceProxy,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
    tpm_acquisition_unique_id: str,
) -> None:
    """
    Verify that the tile has started acquiring data.

    :param tile_device: the tile fixture to use.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param tpm_acquisition_unique_id: the unique id of the StartAcquisition
        command given
    """
    t0 = datetime.datetime.strptime(tile_device.fpgaFrameTime, "%Y-%m-%dT%H:%M:%S.%fZ")
    time.sleep(1.0)
    t1 = datetime.datetime.strptime(tile_device.fpgaFrameTime, "%Y-%m-%dT%H:%M:%S.%fZ")
    timediff = datetime.datetime.timestamp(t1) - datetime.datetime.timestamp(t0)

    assert 0.9 < timediff < 1.1

    tile_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (tpm_acquisition_unique_id, '"Start acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@then("the TPM reports that it is synchronised")
def tpm_assert_synchronised(tile_device: MccsDeviceProxy) -> None:
    """
    Verify that the tile enters the synchronised programming state.

    :param tile_device: the tile fixture to use.
    """
    max_timeout = 10
    count = 0
    while tile_device.tileProgrammingState != "Synchronised" and count < max_timeout:
        time.sleep(0.5)
        count += 1
    assert tile_device.tileProgrammingState == "Synchronised"


@given("the DAQRX has not been started")
def daq_stopped(daq_device: MccsDeviceProxy) -> None:
    """
    Turn off the daq.

    :param daq_device: the daq fixture to use.
    """
    stop_daq(daq_device)


@when("the user configures the DAQRX")
def configure_daq(daq_device: MccsDeviceProxy, daq_config: dict[str, Any]) -> None:
    """
    Configure the daq device with the desired configuration.

    :param daq_device: the daq fixture to use.
    :param daq_config: the daq configuration to use.
    """
    daq_device.Configure(daq_config)


@then("the DAQRX reports that it has the provided configuration")
def daq_assert_configured(
    daq_device: MccsDeviceProxy, daq_config: dict[str, Any]
) -> None:
    """
    Verify that the daq has the desired configuration.

    :param daq_device: the daq fixture to use.
    :param daq_config: the desired configuration.
    """
    assert daq_device.configuration().items() == daq_config


@given("the DAQRX has been configured")
def given_daq_configured(
    daq_device: MccsDeviceProxy, daq_config: dict[str, Any]
) -> None:
    """
    Configure the daq device with the desired configuration.

    :param daq_device: the daq fixture to use.
    :param daq_config: the daq configuration to use.
    """
    configure_daq(daq_device, daq_config)


@when("the user starts the DAQRX", target_fixture="daq_start_unique_id")
def start_daq(
    daq_device: MccsDeviceProxy,
    daq_processed_data_callback: MockChangeEventCallback,
    daq_device_lrc_changed_callback: MockChangeEventCallback,
) -> str:
    """
    Start the daq with the desired processing mode and callback.

    Also subscribes to the long running command result changed event

    :param daq_device: the daq fixture to use.
    :param daq_processed_data_callback: a callback to provide the daq to
        verify that it has processed data.
    :param daq_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the daq device.
    :return: the unique id of the Start command.
    """
    # Subscribe to daq's LRC result attribute
    daq_device.add_change_event_callback(
        "longRunningCommandResult",
        daq_device_lrc_changed_callback,
    )
    assert (
        "longRunningCommandResult".casefold()
        in daq_device._change_event_subscription_ids
    )

    # DaqModes.RAW_DATA is 0 hence the 0 here
    config = {
        "modes_to_start": [0],
        "callbacks": [daq_processed_data_callback],
    }
    ([return_code], [unique_id]) = daq_device.Start(json.dumps(config))
    assert return_code == ResultCode.QUEUED
    assert "_Start" in unique_id
    return unique_id


@then("the DAQRX reports that it has been started")
def assert_daq_started(
    daq_device_lrc_changed_callback: MockChangeEventCallback, daq_start_unique_id: str
) -> None:
    """
    Verify that the daq has been started.

    :param daq_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the daq device.
    :param daq_start_unique_id: the unique id of the Start command called.
    """
    daq_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (daq_start_unique_id, '"Start has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@given("the DAQRX has been started")
def given_daq_started(
    daq_device: MccsDeviceProxy,
    daq_processed_data_callback: MockCallable,
    daq_device_lrc_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Start the daq.

    :param daq_device: the daq fixture to use.
    :param daq_processed_data_callback: a callback to provide the daq to
        verify that it has processed data.
    :param daq_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the daq device.
    """
    start_daq(daq_device, daq_processed_data_callback, daq_device_lrc_changed_callback)


@when("the user stops the DAQRX", target_fixture="daq_stop_unique_id")
def stop_daq(daq_device: MccsDeviceProxy) -> str:
    """
    Stop the daq.

    :param daq_device: the daq fixture to use.
    :return: the unique id of the Stop command called.
    """
    ([return_code], [unique_id]) = daq_device.Stop()
    assert return_code == ResultCode.QUEUED
    assert "_Stop" in unique_id
    return unique_id


@then("the DAQRX reports that it has been stopped")
def assert_daq_stopped(
    daq_device_lrc_changed_callback: MockChangeEventCallback, daq_stop_unique_id: str
) -> None:
    """
    Verify the daq has been stopped.

    :param daq_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the daq device.
    :param daq_stop_unique_id: the unique id of the Stop command called.
    """
    daq_device_lrc_changed_callback.assert_next_call(
        "longrunningcommandresult",
        (daq_stop_unique_id, '"Stop acquisition has completed"'),
        tango.AttrQuality.ATTR_VALID,
    )


@given("the TPM reports that it is synchronised")
def synchronise_tpm(
    subrack_device: MccsDeviceProxy,
    tile_device: MccsDeviceProxy,
    tpm_number: int,
    tile_device_state_changed_callback: MockChangeEventCallback,
    tile_device_admin_mode_changed_callback: MockChangeEventCallback,
    tile_device_lrc_changed_callback: MockChangeEventCallback,
    subrack_device_lrc_changed_callback: MockChangeEventCallback,
    subrack_device_state_changed_callback: MockChangeEventCallback,
    subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
    subrack_tpm_power_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Turn on the tile and start acquisition.

    :param subrack_device: the subrack fixture to use.
    :param tile_device: the tile fixture to use.
    :param tpm_number: the id of the tpm to use.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    :param tile_device_admin_mode_changed_callback: a callback that we can use
        to subscribe to admin mode changes on the tile device.
    :param tile_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the tile device.
    :param subrack_device_lrc_changed_callback: a callback that we can use to
        subscribe to long running command result changes on the subrack device.
    :param subrack_device_state_changed_callback: a callback that we can use
        to subscribe to state changes on the subrack device.
    :param subrack_device_admin_mode_changed_callback: a callback that we can
        use to subscribe to admin mode changes on the subrack device.
    :param subrack_tpm_power_state_changed_callback: a callback that we can
        use to subscribe to tpm power state changes on the subrack device.
    """
    given_tile_on(
        subrack_device,
        tile_device,
        tpm_number,
        subrack_device_state_changed_callback,
        subrack_device_admin_mode_changed_callback,
        subrack_tpm_power_state_changed_callback,
        subrack_device_lrc_changed_callback,
        tile_device_state_changed_callback,
        tile_device_admin_mode_changed_callback,
        tile_device_lrc_changed_callback,
    )
    if tile_device.tileProgrammingState != "Synchronised":
        start_acquisition(tile_device)
    tpm_assert_synchronised(tile_device)


@when("the user tells the TPM to send data")
def tpm_send_data(tile_device: MccsDeviceProxy) -> None:
    """
    Tell the tile to send data.

    :param tile_device: the tile fixture to use.
    """
    ([return_code], [unique_id]) = tile_device.SendRawData()
    assert return_code == ResultCode.QUEUED
    assert "_SendRawData" in unique_id


@then("the TPM does not report a fault")
def tpm_check_no_fault(
    tile_device: MccsDeviceProxy,
    tile_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Verify that the tile hasn't encountered a fault.

    :param tile_device: the tile fixture to use.
    :param tile_device_state_changed_callback: a callback that we can use to
        subscribe to state changes on the tile device.
    """
    assert tile_device.state() == tango.DevState.ON
    tile_device_state_changed_callback.assert_not_called()


@then("the DAQRX reports that it has received data from the TPM")
def assert_daq_received_data(daq_processed_data_callback: MockCallable) -> None:
    """
    Verify that the daq has received data from the TPM.

    :param daq_processed_data_callback: a callback to verify that the daq has
        processed data.
    """
    assert len(daq_processed_data_callback.get_whole_queue()) > 0
