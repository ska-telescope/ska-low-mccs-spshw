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
            "subrack_01",
            "tile_0001",
            "tile_0002",
            "tile_0003",
            "tile_0004",
        ],
    }


class TestSubrackTileIntegration:
    """
    Integration test cases for MCCS subsystem's power management.
    """

    def test_init(self, device_context):
        """
        Test that the MccsTile initialises to the DISABLE state when the
        subrack isn't powering the TPM.

        :todo: need to figure out how to test these devices initialising
            when the hardware is already supplying power to the TPM.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("tile_0001")
        subrack = device_context.get_device("subrack_01")

        assert tile.state() == DevState.DISABLE
        assert not subrack.IsTpmOn(1)

    def test_tile_on(self, device_context):
        """
        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("tile_0001")
        subrack = device_context.get_device("subrack_01")

        assert tile.state() == DevState.DISABLE
        assert not subrack.IsTpmOn(1)

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

    @pytest.mark.skip
    def test_tpm_on(self, device_context):
        """
        TODO: The is a placeholder for a test of functionality that
        hasn't been implemented yet.

        Subrack needs to have an attribute that exposes power to TPMs,
        and that attribute needs to publish change events. Then Tile
        needs to subscribe to those change events, and update its state
        when subrack turns off/on power to its TPM.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        tile = device_context.get_device("tile_0001")
        subrack = device_context.get_device("subrack_01")

        assert tile.state() == DevState.DISABLE
        assert not subrack.IsTpmOn(1)

        subrack.PowerOnTpm(1)
        time.sleep(0.1)  # to allow for event to be pushed
        assert tile.state() == DevState.STANDBY

        subrack.PowerOffTpm(1)
        time.sleep(0.1)  # to allow for event to be pushed
        assert tile.state() == DevState.DISABLE
