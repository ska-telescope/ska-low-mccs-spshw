# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

from typing import Callable

import pytest
import tango
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "tests/data/configuration.json",
        "package": "ska_low_mccs_spshw",
        "devices": [
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
        ],
    }


class TestSubrackTileIntegration:
    """Integration test cases for interactions between subrack and tile."""

    def test_subrack_tile_integration(
        self: TestSubrackTileIntegration,
        tango_harness: TangoHarness,
        subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
        subrack_device_state_changed_callback: MockChangeEventCallback,
        tile_device_admin_mode_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback_factory: Callable[[str], MockChangeEventCallback],
        tile_device_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test the integration of tile within subrack.

        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param tango_harness: a test harness for tango devices
        :param subrack_device_admin_mode_changed_callback: a callback
            that we can use to subscribe to admin mode changes on the
            subrack device
        :param subrack_device_state_changed_callback: a callback that we
            can use to subscribe to state changes on the subrack device.
        :param tile_device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param lrc_result_changed_callback_factory: a factory to create
            callbacks to be used to subscribe to device LRC result changes
        :param tile_device_state_changed_callback: a callback that we
            can use to subscribe to state changes on the tile device.
        """
        tile_device = tango_harness.get_device("low-mccs/tile/0001")
        subrack_device = tango_harness.get_device("low-mccs/subrack/01")
        tpm_id = 1

        tile_lrc_result_changed_callback = lrc_result_changed_callback_factory()
        subrack_lrc_result_changed_callback = lrc_result_changed_callback_factory()

        tile_device.add_change_event_callback(
            "adminMode",
            tile_device_admin_mode_changed_callback,
        )
        tile_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.OFFLINE
        )

        tile_device.add_change_event_callback(
            "state",
            tile_device_state_changed_callback,
        )
        tile_device_state_changed_callback.assert_next_change_event(
            tango.DevState.DISABLE
        )

        subrack_device.add_change_event_callback(
            "adminMode",
            subrack_device_admin_mode_changed_callback,
        )
        subrack_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.OFFLINE
        )

        subrack_device.add_change_event_callback(
            "state",
            subrack_device_state_changed_callback,
        )
        subrack_device_state_changed_callback.assert_last_change_event(
            tango.DevState.DISABLE
        )

        assert subrack_device.tpm1PowerState == PowerState.UNKNOWN

        # Subscribe to subrack's LRC result attribute
        subrack_device.add_change_event_callback(
            "longRunningCommandResult",
            subrack_lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in subrack_device._change_event_subscription_ids
        )
        initial_lrc_result = ("", "")
        assert subrack_device.longRunningCommandResult == initial_lrc_result
        subrack_lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        # Subscribe to tile's LRC result attribute
        tile_device.add_change_event_callback(
            "longRunningCommandResult",
            tile_lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in tile_device._change_event_subscription_ids
        )
        assert tile_device.longRunningCommandResult == initial_lrc_result
        tile_lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        tile_device.adminMode = AdminMode.ONLINE

        tile_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

        # Before the tile device tries to connect with its TPM, it need to find out from
        # its subrack whether the TPM is event turned on. So it subscribes to change
        # events on the state of its subrack Tango device. The subrack device advises it
        # that it is OFFLINE. Therefore tile remains in UNKNOWN state.
        tile_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )
        assert tile_device.state() == tango.DevState.UNKNOWN

        subrack_device.adminMode = AdminMode.ONLINE
        subrack_device_admin_mode_changed_callback.assert_last_change_event(
            AdminMode.ONLINE
        )

        # The subrack device tries to establish a connection to its upstream power
        # supply device. Until this connection is established, it is in UNKNOWN state.
        subrack_device_state_changed_callback.assert_next_change_event(
            tango.DevState.UNKNOWN
        )

        # The subrack device connects to its upstream power supply device and finds that
        # the subrack is turned off, so it transitions to OFF state
        subrack_device_state_changed_callback.assert_last_change_event(
            tango.DevState.OFF
        )
        assert subrack_device.tpm1PowerState == PowerState.NO_SUPPLY

        # The tile device receives a change event. Since the event indicates that the
        # subrack hardware is OFF, the tile has established that its TPM is not powered,
        # so it transitions to OFF state.
        tile_device_state_changed_callback.assert_next_change_event(tango.DevState.OFF)
        assert tile_device.state() == tango.DevState.OFF

        [result_code], [unique_id] = subrack_device.On()
        # The subrack device tells the upstream power supply to power the subrack on.
        # Once the upstream power supply has powered the subrack on, the subrack device
        # tries to establish a connection to the subrack. Until that connection is
        # established, it is in UNKNOWN state.

        # TODO: Subrack is going straight to ON and not transitioning through UNKNOWN
        # subrack_device_state_changed_callback.assert_next_change_event(
        #     tango.DevState.UNKNOWN
        # )

        # Once the subrack device is connected to its subrack, it transitions to ON
        # state.
        subrack_device_state_changed_callback.assert_last_change_event(
            tango.DevState.ON
        )
        assert subrack_device.tpm1PowerState == PowerState.OFF

        subrack_lrc_result_changed_callback.assert_next_call(
            "longrunningcommandresult",
            (unique_id, '"On command has completed"'),
            tango.AttrQuality.ATTR_VALID,
        )

        # The tile device is notified that its subrack is on. It now has communication
        # with its TPM. The first thing it does is subscribe to change events on the
        # power mode of its TPM. It is informed that the TPM is turned off, so it
        # remains in OFF state
        tile_device_state_changed_callback.assert_not_called()
        assert tile_device.state() == tango.DevState.OFF

        # Power on TPM using Tile On

        [result_code], [unique_id] = tile_device.On()

        # The tile device tells the subrack device to tell its subrack to power on its
        # TPM. This is done. The subrack device detects that the TPM is now on.

        tile_device_state_changed_callback.assert_last_change_event(tango.DevState.ON)
        assert tile_device.state() == tango.DevState.ON
        assert subrack_device.tpm1PowerState == PowerState.ON
        tile_lrc_result_changed_callback.assert_next_call(
            "longrunningcommandresult",
            (unique_id, '"Tile on completed"'),
            tango.AttrQuality.ATTR_VALID,
        )
        # TurnOnTpm isn't directly called here so we have to get at it a bit
        # differently.
        args = subrack_lrc_result_changed_callback.get_next_call()
        assert "_PowerOnTpm" in args[0][1][0]
        assert args[0][1][1] == f'"Subrack TPM {tpm_id} turn on tpm task has completed"'

        # Power off TPM using Tile

        [result_code], [unique_id] = tile_device.Off()

        # The tile device tells the subrack device to tell its subrack to power off its
        # TPM. This is done. The subrack device detects that the TPM is now off.

        tile_device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)
        assert tile_device.state() == tango.DevState.OFF
        assert subrack_device.tpm1PowerState == PowerState.OFF

        tile_lrc_result_changed_callback.assert_next_call(
            "longrunningcommandresult",
            (unique_id, '"Tile off completed"'),
            tango.AttrQuality.ATTR_VALID,
        )
        # TurnOffTpm isn't directly called here so we have to get at it a bit
        # differently.
        args = subrack_lrc_result_changed_callback.get_next_call()
        assert "_PowerOffTpm" in args[0][1][0]
        assert (
            args[0][1][1] == f'"Subrack TPM {tpm_id} turn off tpm task has completed"'
        )

        # Power on TPM using subrack

        [[result_code], [unique_id]] = subrack_device.PowerOnTpm(tpm_id)
        assert result_code == ResultCode.QUEUED
        assert "_PowerOnTpm" in unique_id

        subrack_lrc_result_changed_callback.assert_next_call(
            "longrunningcommandresult",
            (unique_id, f'"Subrack TPM {tpm_id} turn on tpm task has completed"'),
            tango.AttrQuality.ATTR_VALID,
        )
        # A third party has told the subrack device to turn the TPM on. The subrack
        # device tells the subrack to turn the TPM on. The subrack device detects that
        # the TPM is on.
        tile_device_state_changed_callback.assert_last_change_event(tango.DevState.ON)
        assert tile_device.state() == tango.DevState.ON
        assert subrack_device.tpm1PowerState == PowerState.ON

        # Power off TPM using subrack

        [[result_code], [unique_id]] = subrack_device.PowerOffTpm(tpm_id)
        assert result_code == ResultCode.QUEUED
        assert "_PowerOffTpm" in unique_id

        subrack_lrc_result_changed_callback.assert_next_call(
            "longrunningcommandresult",
            (unique_id, f'"Subrack TPM {tpm_id} turn off tpm task has completed"'),
            tango.AttrQuality.ATTR_VALID,
        )

        # A third party has told the subrack device to turn the TPM off. The subrack
        # device tells the subrack to turn the TPM off. The subrack device detects that
        # the TPM is off.
        assert subrack_device.tpm1PowerState == PowerState.OFF

        tile_device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)
        assert tile_device.state() == tango.DevState.OFF
