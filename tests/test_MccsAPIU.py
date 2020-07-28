###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsStationBeam project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsAPIU.
"""
import pytest
import tango
from tango import DevSource
from ska.base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs import MccsAPIU, release

device_info = {
    "class": MccsAPIU,
    "properties": {"SkaLevel": "4","LoggingLevelDefault": 4,},
}

class TestMccsAPIU:
    """
    Test class for MccsAPIU tests
    """

    @pytest.mark.skip(reason="Not implemented.")
    def test_properties(self, device_under_test):
        """
        Test the properties. Not implemented.
        """
        pass

    # general methods
    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        """
        assert device_under_test.state() == tango.DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

        # These start-up defaults might change
        assert device_under_test.voltage == 0.0
        assert device_under_test.current == 0.0
        assert device_under_test.temperature == 0.0
        assert device_under_test.humidity == 0.0
        assert device_under_test.isAlive == True
        assert device_under_test.overCurrentThreshold == 0.0
        assert device_under_test.overVoltageThreshold == 0.0
        assert device_under_test.humidityThreshold == 0.0
        assert device_under_test._logicalAntennaId == []

    # overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version
