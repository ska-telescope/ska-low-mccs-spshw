###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import time

import pytest
from tango import DevState

from ska_tango_base.control_model import AdminMode

from ska_low_mccs import MccsDeviceProxy

from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DevicesToLoadType, TangoHarness


@pytest.fixture()
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
            # TODO: commented out as they are not used at present and to
            # help diagnose the intermittent test failure.
            # {"name": "tile_0002", "proxy": MccsDeviceProxy},
            # {"name": "tile_0003", "proxy": MccsDeviceProxy},
            # {"name": "tile_0004", "proxy": MccsDeviceProxy},
        ],
    }


class TestSubrackTileIntegration:
    """Integration test cases for interactions between subrack and tile."""

    def test_subrack_tile_integration(
        self: TestSubrackTileIntegration,
        tango_harness: TangoHarness,
        subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
        tile_device_admin_mode_changed_callback: MockChangeEventCallback,
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
        :param tile_device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device = tango_harness.get_device("low-mccs/tile/0001")
        subrack_device = tango_harness.get_device("low-mccs/subrack/01")

        tile_device.add_change_event_callback(
            "adminMode",
            tile_device_admin_mode_changed_callback,
        )
        tile_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.OFFLINE
        )

        assert subrack_device.state() == DevState.DISABLE
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        tile_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.ONLINE
        )

        # Before the tile device tries to connect with its TPM, it need to find out from
        # its subrack whether the TPM is event turned on. So it subscribes to change
        # events on the state of its subrack Tango device. The subrack device advises it
        # that it is OFFLINE. Therefore tile remains in UNKNOWN state.
        assert tile_device.state() == DevState.UNKNOWN

        subrack_device.add_change_event_callback(
            "adminMode",
            subrack_device_admin_mode_changed_callback,
        )
        subrack_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.OFFLINE
        )

        subrack_device.adminMode = AdminMode.ONLINE
        subrack_device_admin_mode_changed_callback.assert_next_change_event(
            AdminMode.ONLINE
        )

        # The subrack device connects to its subrack and finds that the
        # subrack is turned off, so it transitions to OFF state
        assert subrack_device.state() == DevState.OFF

        time.sleep(0.1)
        # The tile device receives a change event. Since the event indicates that the
        # subrack hardware is OFF, the tile has established that its TPM is not powered,
        # so it transitions to OFF state.
        assert tile_device.state() == DevState.OFF

        subrack_device.On()
        # The subrack device tells the subrack to power on. Once the subrack has powered
        # on, the subrack device detects that change of state, and transitions to ON
        # state.
        time.sleep(0.1)
        assert subrack_device.state() == DevState.ON
        assert not subrack_device.isTpmOn(1)

        time.sleep(0.1)
        # The tile device is notified that its subrack is on. It now has communication
        # with its TPM. The first thing it does is subscribe to change events on the
        # power mode of its TPM. It is informed that the TPM is turned off, so it
        # transitions to OFF
        assert tile_device.state() == DevState.OFF

        tile_device.On()
        # The tile device tells the subrack device to tell its subrack to power on its
        # TPM. This is done. The subrack device detects that the TPM is now on.
        time.sleep(0.1)
        assert subrack_device.IsTpmOn(1)

        time.sleep(0.1)
        # It fires a change event, which is received by the tile device.
        assert tile_device.state() == DevState.ON

        subrack_device.PowerOffTpm(1)
        # A third party has told the subrack device to turn the TPM off. The subrack
        # device tells the subrack to turn the TPM off. The subrack device detects that
        # the TPM is off.
        assert not subrack_device.IsTpmOn(1)

        time.sleep(0.1)
        # It fires a change event, which is received by the tile device.
        assert tile_device.state() == DevState.OFF
