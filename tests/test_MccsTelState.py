#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTelState project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsTelState.
"""
import tango
import pytest
from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.base.control_model import LoggingLevel
from ska.low.mccs import MccsTelState, release

device_info = {
    "class": MccsTelState,
    "properties": {"SkaLevel": "4", "LoggingLevelDefault": "4"},
}

# Device test case
class TestMccsTelState(object):
    """Test case for packet generation."""

    # properties = {
    #    "TelStateConfigFile": "",
    #    "SkaLevel": "4",
    #    "GroupDefinitions": "",
    #    "LoggingLevelDefault": "4",
    #    "LoggingTargetsDefault": "",
    # }

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsTelState.numpy = MagicMock()

    @pytest.mark.skip(reason="Not implemented")
    def test_properties(self, device_under_test):
        # Test the properties
        pass

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        """
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

    def test_State(self, device_under_test):
        """Test for State"""
        assert device_under_test.State() == tango.DevState.OFF

    def test_Status(self, device_under_test):
        """Test for Status"""
        assert device_under_test.Status() == "The device is in OFF state."

    def test_GetVersionInfo(self, device_under_test):
        info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [info]

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(self, device_under_test):
        """Test for Reset"""

        with pytest.raises(Exception):
            device_under_test.Reset()

    def test_buildState(self, device_under_test):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version

    def test_loggingLevel(self, device_under_test):
        """Test for loggingLevel"""
        assert device_under_test.loggingLevel == LoggingLevel.INFO

    def test_healthState(self, device_under_test):
        """Test for healthState"""
        assert device_under_test.healthState == HealthState.OK

    def test_controlMode(self, device_under_test):
        """Test for controlMode"""
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """Test for simulationMode"""
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(self, device_under_test):
        """Test for testMode"""
        assert device_under_test.testMode == TestMode.NONE

    @pytest.mark.skip(reason="Not implemented")
    def test_elementsStates(self, device_under_test):
        """Test for elementsStates"""
        assert device_under_test.elementsStates == ""

    @pytest.mark.skip(reason="Not implemented")
    def test_observationsStates(self, device_under_test):
        """Test for observationsStates"""
        assert device_under_test.observationsStates == ""

    @pytest.mark.skip(reason="Not implemented")
    def test_algorithms(self, device_under_test):
        """Test for algorithms"""
        assert device_under_test.algorithms == ""

    @pytest.mark.skip(reason="Not implemented")
    def test_algorithmsVersion(self, device_under_test):
        """Test for algorithmsVersion"""
        assert device_under_test.algorithmsVersion == ""

    def test_loggingTargets(self, device_under_test):
        """Test for loggingTargets"""
        assert device_under_test.loggingTargets == ("tango::logger",)
