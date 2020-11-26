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

from conftest import confirm_initialised


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
            "controller",
            "subarray_01",
            "subarray_02",
            "station_001",
            "station_002",
            "tile_0001",
            "tile_0002",
            "tile_0003",
            "tile_0004",
            "apiu_001",
            # "antenna_000001",  # workaround for MCCS-244
            # "antenna_000002",
            # "antenna_000003",
            # "antenna_000004",
        ],
    }


class TestPowerManagement:
    """
    Integration test cases for MCCS subsystem's power management.
    """

    def test_power_on_off(self, device_context):
        """
        Test that a MccsController device can enable an MccsSubarray
        device.

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        controller = device_context.get_device("low-mccs/control/control")
        station_1 = device_context.get_device("low-mccs/station/001")
        station_2 = device_context.get_device("low-mccs/station/002")
        tile_1 = device_context.get_device("low-mccs/tile/0001")
        tile_2 = device_context.get_device("low-mccs/tile/0002")
        tile_3 = device_context.get_device("low-mccs/tile/0003")
        tile_4 = device_context.get_device("low-mccs/tile/0004")

        confirm_initialised(
            [controller, station_1, station_2, tile_1, tile_2, tile_3, tile_4]
        )

        assert controller.State() == DevState.OFF
        assert station_1.State() == DevState.OFF
        assert station_2.State() == DevState.OFF
        assert tile_1.State() == DevState.OFF
        assert tile_2.State() == DevState.OFF
        assert tile_3.State() == DevState.OFF
        assert tile_4.State() == DevState.OFF

        controller.On()

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
