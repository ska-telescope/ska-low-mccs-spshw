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

import pytest
from tango import DevState


class TestPowerManagementFromControllerToTile:
    """
    Integration test cases for MCCS subsystem's power management,
    focussing on the path from the controller to the Tile.
    """

    @pytest.fixture()
    def devices_to_load(self):
        """
        Fixture that specifies the devices to be loaded for testing.

        :return: specification of the devices to be loaded
        :rtype: dict
        """
        # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved,
        # we should merge this tile/subrack test with the antenna/APIU test below.
        return {
            "path": "charts/ska-low-mccs/data/configuration_without_antennas.json",
            "package": "ska.low.mccs",
            "devices": [
                "controller",
                "subarray_01",
                "subarray_02",
                "station_001",
                "station_002",
                "subrack_01",
                "tile_0001",
                "tile_0002",
                "tile_0003",
                "tile_0004",
            ],
        }

    def test_power_on_off(self, device_context):
        """
        Test that a MccsController device can enable an MccsSubarray
        device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        controller = device_context.get_device("controller")
        station_1 = device_context.get_device("station_001")
        station_2 = device_context.get_device("station_002")
        tile_1 = device_context.get_device("tile_0001")
        tile_2 = device_context.get_device("tile_0002")
        tile_3 = device_context.get_device("tile_0003")
        tile_4 = device_context.get_device("tile_0004")

        assert controller.State() == DevState.OFF
        assert station_1.State() == DevState.OFF
        assert station_2.State() == DevState.OFF
        assert tile_1.State() == DevState.DISABLE
        assert tile_2.State() == DevState.DISABLE
        assert tile_3.State() == DevState.DISABLE
        assert tile_4.State() == DevState.DISABLE

        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        controller.Startup()

        assert controller.State() == DevState.ON
        assert station_1.State() == DevState.ON
        assert station_2.State() == DevState.ON
        assert tile_1.State() == DevState.ON
        assert tile_2.State() == DevState.ON
        assert tile_3.State() == DevState.ON
        assert tile_4.State() == DevState.ON

        controller.Off()

        assert controller.State() == DevState.OFF
        assert station_1.State() == DevState.OFF
        assert station_2.State() == DevState.OFF
        assert tile_1.State() == DevState.OFF
        assert tile_2.State() == DevState.OFF
        assert tile_3.State() == DevState.OFF
        assert tile_4.State() == DevState.OFF


class TestPowerManagementFromControllerToAntenna:
    """
    Integration test cases for MCCS subsystem's power management.
    """

    @pytest.fixture()
    def devices_to_load(self):
        """
        Fixture that specifies the devices to be loaded for testing.

        :return: specification of the devices to be loaded
        :rtype: dict
        """
        # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved,
        # we should merge this antenna/APIU test with the tile/subrack test above.
        return {
            "path": "charts/ska-low-mccs/data/configuration_without_tiles.json",
            "package": "ska.low.mccs",
            "devices": [
                "controller",
                "subarray_01",
                "subarray_02",
                "station_001",
                "station_002",
                "apiu_001",
                "antenna_000001",
                "antenna_000002",
                "antenna_000003",
                "antenna_000004",
            ],
        }

    def test_power_on_off(self, device_context):
        """
        Test that a MccsController device can enable an MccsSubarray
        device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        controller = device_context.get_device("controller")
        station_1 = device_context.get_device("station_001")
        station_2 = device_context.get_device("station_002")
        antenna_1 = device_context.get_device("antenna_000001")
        antenna_2 = device_context.get_device("antenna_000002")
        antenna_3 = device_context.get_device("antenna_000003")
        antenna_4 = device_context.get_device("antenna_000004")

        assert controller.State() == DevState.OFF
        assert station_1.State() == DevState.OFF
        assert station_2.State() == DevState.OFF
        assert antenna_1.State() == DevState.OFF
        assert antenna_2.State() == DevState.OFF
        assert antenna_3.State() == DevState.OFF
        assert antenna_4.State() == DevState.OFF

        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        controller.Startup()

        assert controller.State() == DevState.ON
        assert station_1.State() == DevState.ON
        assert station_2.State() == DevState.ON
        assert antenna_1.State() == DevState.ON
        assert antenna_2.State() == DevState.ON
        assert antenna_3.State() == DevState.ON
        assert antenna_4.State() == DevState.ON

        controller.Off()

        assert controller.State() == DevState.OFF
        assert station_1.State() == DevState.OFF
        assert station_2.State() == DevState.OFF
        assert antenna_1.State() == DevState.OFF
        assert antenna_2.State() == DevState.OFF
        assert antenna_3.State() == DevState.OFF
        assert antenna_4.State() == DevState.OFF
