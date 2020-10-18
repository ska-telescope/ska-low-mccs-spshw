########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.demo module
"""
from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.demo import ConnectionFailableTile


device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "tile_0001",
    "patch": ConnectionFailableTile,
}


class TestConnectionFailableTile:
    """
    This class contains the tests for the ConnectionFailableTile device
    class.
    """

    def test_health(self, device_under_test):
        """
        Test that device health changes to failed when we simulate
        connection failure

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.healthState == HealthState.OK

        device_under_test.SimulateConnectionFailure(True)
        assert device_under_test.healthState == HealthState.FAILED

        device_under_test.SimulateConnectionFailure(False)
        assert device_under_test.healthState == HealthState.OK
