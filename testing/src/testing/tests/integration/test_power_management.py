# type: ignore
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
"""This module contains integration tests of MCCS power management functionality."""
from time import sleep

import pytest
import pytest_mock
from tango import DevState

from ska_low_mccs import MccsDeviceProxy

from testing.harness.tango_harness import TangoHarness
from testing.harness import HelperClass


class TestPowerManagement(HelperClass):
    """
    Integration test cases for MCCS subsystem's power management.

    These tests focus on the path from the controller down to the tiles
    and antennas.
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
            "package": "ska_low_mccs",
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

    def test_power_on_off(
        self, tango_harness: TangoHarness, mocker: pytest_mock.mocker
    ):
        """
        Test that a MccsController device can enable an MccsSubarray device.

        :param tango_harness: a test harness for tango devices
        :param mocker: fixture that wraps unittest.Mock
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subrack = tango_harness.get_device("low-mccs/subrack/01")
        station = tango_harness.get_device("low-mccs/station/001")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        tile_4 = tango_harness.get_device("low-mccs/tile/0004")
        apiu = tango_harness.get_device("low-mccs/apiu/001")
        antenna_1 = tango_harness.get_device("low-mccs/antenna/000001")
        antenna_2 = tango_harness.get_device("low-mccs/antenna/000002")
        antenna_3 = tango_harness.get_device("low-mccs/antenna/000003")
        antenna_4 = tango_harness.get_device("low-mccs/antenna/000004")

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
        sleep(0.5)  # Allow time for Startup to complete
        dev_states = {
            controller: DevState.ON,
            subrack: DevState.ON,
            station: DevState.ON,
            tile_1: DevState.ON,
            tile_2: DevState.ON,
            tile_3: DevState.ON,
            tile_4: DevState.ON,
        }
        self.check_states_of_devices(dev_states)

        assert subrack.IsTpmOn(1)
        assert subrack.IsTpmOn(2)
        assert subrack.IsTpmOn(3)
        assert subrack.IsTpmOn(4)

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

        dev_states = {
            tile_1: DevState.ON,
            tile_2: DevState.ON,
            tile_3: DevState.ON,
            tile_4: DevState.ON,
            apiu: DevState.ON,
            antenna_1: DevState.ON,
            antenna_2: DevState.ON,
            antenna_3: DevState.ON,
            antenna_4: DevState.ON,
        }
        self.check_states_of_devices(dev_states)

        assert apiu.IsAntennaOn(1)
        assert apiu.IsAntennaOn(2)
        assert apiu.IsAntennaOn(3)
        assert apiu.IsAntennaOn(4)

        controller.Off()
        sleep(0.5)  # Allow time for Off to complete

        dev_states = {
            controller: DevState.OFF,
            subrack: DevState.OFF,
            station: DevState.OFF,
            tile_1: DevState.OFF,
            tile_2: DevState.OFF,
            tile_3: DevState.OFF,
            tile_4: DevState.OFF,
            apiu: DevState.OFF,
            antenna_1: DevState.OFF,
            antenna_2: DevState.OFF,
            antenna_3: DevState.OFF,
            antenna_4: DevState.OFF,
        }
        self.check_states_of_devices(dev_states)
