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
management functionality of the SKA Low MCCS system.
"""
from time import sleep

import pytest
from tango import DevState

from ska.low.mccs import MccsDeviceProxy


class TestPowerManagement:
    """
    Integration test cases for MCCS subsystem's power management,
    focussing on the path from the controller down to the tiles and
    antennas.
    """

    @pytest.fixture()
    def devices_to_load(self):
        """
        Fixture that specifies the devices to be loaded for testing.

        :return: specification of the devices to be loaded
        :rtype: dict
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration_without_beams.json",
            "package": "ska.low.mccs",
            "devices": [
                {"name": "controller", "proxy": MccsDeviceProxy},
                {"name": "station_001", "proxy": MccsDeviceProxy},
                {"name": "subrack_01", "proxy": MccsDeviceProxy},
                {"name": "tile_0001", "proxy": MccsDeviceProxy},
                {"name": "tile_0002", "proxy": MccsDeviceProxy},
                {"name": "tile_0003", "proxy": MccsDeviceProxy},
                {"name": "tile_0004", "proxy": MccsDeviceProxy},
                {"name": "apiu_001", "proxy": MccsDeviceProxy},
                {"name": "antenna_000001", "proxy": MccsDeviceProxy},
                {"name": "antenna_000002", "proxy": MccsDeviceProxy},
                {"name": "antenna_000003", "proxy": MccsDeviceProxy},
                {"name": "antenna_000004", "proxy": MccsDeviceProxy},
            ],
        }

    def test_power_on_off(self, device_context):
        """
        Test that a MccsController device can enable an MccsSubarray
        device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.test_context.MultiDeviceTestContext`
        """
        controller = device_context.get_device("controller")
        subrack = device_context.get_device("subrack_01")
        station = device_context.get_device("station_001")
        tile_1 = device_context.get_device("tile_0001")
        tile_2 = device_context.get_device("tile_0002")
        tile_3 = device_context.get_device("tile_0003")
        tile_4 = device_context.get_device("tile_0004")
        apiu = device_context.get_device("apiu_001")
        antenna_1 = device_context.get_device("antenna_000001")
        antenna_2 = device_context.get_device("antenna_000002")
        antenna_3 = device_context.get_device("antenna_000003")
        antenna_4 = device_context.get_device("antenna_000004")

        assert controller.State() == DevState.DISABLE
        assert subrack.State() == DevState.DISABLE
        assert station.State() == DevState.OFF
        assert tile_1.State() == DevState.DISABLE
        assert tile_2.State() == DevState.DISABLE
        assert tile_3.State() == DevState.DISABLE
        assert tile_4.State() == DevState.DISABLE
        assert apiu.State() == DevState.DISABLE
        assert antenna_1.State() == DevState.DISABLE
        assert antenna_2.State() == DevState.DISABLE
        assert antenna_3.State() == DevState.DISABLE
        assert antenna_4.State() == DevState.DISABLE

        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        controller.Startup()

        assert controller.State() == DevState.ON
        assert subrack.State() == DevState.ON
        assert subrack.IsTpmOn(1)
        assert subrack.IsTpmOn(2)
        assert subrack.IsTpmOn(3)
        assert subrack.IsTpmOn(4)
        assert station.State() == DevState.ON

        # The default testMode is TestMode.NONE, in which case certain
        # attributes are continually updated. By design, these
        # attributes sometimes go out of range, putting the device into
        # ALARM state.
        # Before testing, we set the testMode to TestMode.TEST, which
        # gives us static in-bounds values to test against. But if the
        # device was already in ALARM state by then, it can take a while
        # for the device to update its state from ALARM to ON.
        # TODO: Move this into conftest
        if any(
            tile.State() == DevState.ALARM for tile in [tile_1, tile_2, tile_3, tile_4]
        ):
            sleep(1.5)

        assert tile_1.State() == DevState.ON
        assert tile_2.State() == DevState.ON
        assert tile_3.State() == DevState.ON
        assert tile_4.State() == DevState.ON

        assert apiu.State() == DevState.ON
        assert apiu.IsAntennaOn(1)
        assert apiu.IsAntennaOn(2)
        assert apiu.IsAntennaOn(3)
        assert apiu.IsAntennaOn(4)
        assert antenna_1.State() == DevState.ON
        assert antenna_2.State() == DevState.ON
        assert antenna_3.State() == DevState.ON
        assert antenna_4.State() == DevState.ON

        controller.Off()

        assert controller.State() == DevState.OFF
        assert subrack.State() == DevState.OFF
        assert station.State() == DevState.OFF
        assert tile_1.State() == DevState.OFF
        assert tile_2.State() == DevState.OFF
        assert tile_3.State() == DevState.OFF
        assert tile_4.State() == DevState.OFF
        assert controller.State() == DevState.OFF
        assert station.State() == DevState.OFF
        assert apiu.State() == DevState.OFF
        assert antenna_1.State() == DevState.OFF
        assert antenna_2.State() == DevState.OFF
        assert antenna_3.State() == DevState.OFF
        assert antenna_4.State() == DevState.OFF