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
"""
This test module contains integration tests that exercise the power
management functionality of the SKA Low MCCS system between the subrack
and the TPM.
"""
import time

import pytest
from tango import DevState

from ska.low.mccs import MccsDeviceProxy


@pytest.fixture()
def devices_to_load():
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska.low.mccs",
        "devices": [
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
        ],
    }


class TestSubrackTileIntegration:
    """
    Integration test cases for MCCS subsystem's power management.
    """

    def test_tile_on(self, device_context):
        """
        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.test_context.MultiDeviceTestContext`
        """
        tile = device_context.get_device("tile_0001")
        subrack = device_context.get_device("subrack_01")

        assert subrack.state() == DevState.DISABLE
        assert tile.state() == DevState.DISABLE

        subrack.Off()
        assert subrack.state() == DevState.OFF
        subrack.On()
        assert subrack.state() == DevState.ON

        assert not subrack.isTpmOn(1)
        # TODO: For now we need to get this device to OFF (highest state
        # of device readiness) in order to turn the TPM on. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        tile.Off()
        assert tile.state() == DevState.OFF
        assert subrack.IsTpmOn(1)

        # TODO: For now we need to get this device to DISABLE (lowest
        # state of device readiness) in order to turn the TPM off. This
        # is a counterintuitive mess that will be fixed in SP-1501.
        tile.Disable()
        assert tile.state() == DevState.DISABLE
        assert not subrack.IsTpmOn(1)

        tile.Standby()
        assert tile.state() == DevState.STANDBY
        assert subrack.IsTpmOn(1)

    def test_tpm_on(self, device_context):
        """
        Test that wnen we tell the subrack drive to turn a given TPM on,
        the tile device recognises that its TPM has been powered, and
        changes state.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.test_context.MultiDeviceTestContext`
        """
        tile = device_context.get_device("tile_0001")
        subrack = device_context.get_device("subrack_01")

        subrack.Off()
        subrack.On()

        assert tile.state() == DevState.DISABLE
        assert not subrack.IsTpmOn(1)

        subrack.PowerOnTpm(1)

        # Wait long enough for the event to get through the events subsystem
        time.sleep(0.2)
        assert tile.state() == DevState.OFF

        subrack.PowerOffTpm(1)

        # Wait long enough for the event to get through the events subsystem
        time.sleep(0.2)
        assert tile.state() == DevState.DISABLE