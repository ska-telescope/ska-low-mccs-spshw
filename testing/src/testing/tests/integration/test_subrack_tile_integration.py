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

from ska_low_mccs import MccsDeviceProxy

from testing.harness.tango_harness import TangoHarness
from testing.harness import HelperClass


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
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
        ],
    }


class TestSubrackTileIntegration(HelperClass):
    """
    Integration test cases for MCCS subsystem's power management.
    """

    def test_tile_on(self, tango_harness: TangoHarness, empty_json_dict: str):
        """
        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param tango_harness: a test harness for tango devices
        :param empty_json_dict: an empty json encoded dictionary
        """
        tile = tango_harness.get_device("low-mccs/tile/0001")
        subrack = tango_harness.get_device("low-mccs/subrack/01")

        assert subrack.state() == DevState.DISABLE
        assert tile.state() == DevState.DISABLE

        self.start_up_device(subrack)

        assert not subrack.isTpmOn(1)
        # TODO: For now we need to get this device to OFF (highest state
        # of device readiness) in order to turn the TPM on. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        tile.Off(empty_json_dict)
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

    def test_tpm_on(self, tango_harness: TangoHarness):
        """
        Test that wnen we tell the subrack drive to turn a given TPM on,
        the tile device recognises that its TPM has been powered, and
        changes state.

        :param tango_harness: a test harness for tango devices
        """
        tile = tango_harness.get_device("low-mccs/tile/0001")
        subrack = tango_harness.get_device("low-mccs/subrack/01")

        self.start_up_device(subrack)

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
