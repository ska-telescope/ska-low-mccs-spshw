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
import json
import pytest
from tango import DevState

from ska_low_mccs import MccsDeviceProxy

from testing.harness.tango_harness import TangoHarness


@pytest.fixture()
def devices_to_load():
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            # THESE ARE THE SYSTEM UNDER TEST
            {"name": "apiu_001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000002", "proxy": MccsDeviceProxy},
            {"name": "antenna_000003", "proxy": MccsDeviceProxy},
            {"name": "antenna_000004", "proxy": MccsDeviceProxy},
            # THESE ARE NOT UNDER TEST BUT ARE NEEDED BY THE ABOVE
            # (An antenna needs its tile which needs its subrack...)
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
        ],
    }


class TestApiuAntennaIntegration:
    """
    Integration test cases for MCCS subsystem's power management.
    """

    def test_antenna_on(self, tango_harness: TangoHarness):
        """
        Test that:

        * when MccsAntenna is turned on, the APIU supplies power to the
          TPM
        * when MccsAntenna is turned off, the APIU denies power to the
          TPM

        :param tango_harness: a test harness for tango devices
        """
        antenna = tango_harness.get_device("low-mccs/antenna/000001")
        apiu = tango_harness.get_device("low-mccs/apiu/001")

        assert apiu.state() == DevState.DISABLE
        assert antenna.state() == DevState.DISABLE

        apiu.Off()
        assert apiu.state() == DevState.OFF
        args = {"dummy": "args"}
        dummy_json_args = json.dumps(args)
        apiu.On(dummy_json_args)
        assert apiu.state() == DevState.ON

        assert not apiu.isAntennaOn(1)
        # TODO: For now we need to get this device to OFF (highest state
        # of device readiness) in order to turn the antenna on. This is
        # a counterintuitive mess that will be fixed in SP-1501.
        antenna.Off()
        assert antenna.state() == DevState.OFF
        assert apiu.IsAntennaOn(1)

        # TODO: For now we need to get this device to DISABLE (lowest
        # state of device readiness) in order to turn the antenna off.
        # This is a counterintuitive mess that will be fixed in SP-1501.
        antenna.Disable()
        assert antenna.state() == DevState.DISABLE
        assert not apiu.IsAntennaOn(1)

    def test_apiu_antenna_on(self, tango_harness: TangoHarness):
        """
        Test that wnen we tell the APIU drive to turn a given antenna
        on, the antenna device recognises that its hardware has been
        powered, and changes state.

        :param tango_harness: a test harness for tango devices
        """
        antenna = tango_harness.get_device("low-mccs/antenna/000001")
        apiu = tango_harness.get_device("low-mccs/apiu/001")

        apiu.Off()
        args = {"dummy": "args"}
        dummy_json_args = json.dumps(args)
        apiu.On(dummy_json_args)

        assert antenna.state() == DevState.DISABLE
        assert not apiu.IsAntennaOn(1)

        apiu.PowerUpAntenna(1)

        # Wait long enough for the event to get through the events subsystem
        time.sleep(0.2)
        assert antenna.state() == DevState.OFF

        apiu.PowerDownAntenna(1)

        # Wait long enough for the event to get through the events subsystem
        time.sleep(0.2)
        assert antenna.state() == DevState.DISABLE
