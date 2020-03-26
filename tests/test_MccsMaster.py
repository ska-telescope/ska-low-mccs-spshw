###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contains the tests for the MccsMaster Tango device prototype."""

# from mock import MagicMock
import pytest
import tango
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.mccs import release

# pylint: disable=invalid-name
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsMaster:
    """Test case for packet generation."""

    properties = {
        "SkaLevel": "4",
        "CentralLoggingTarget": "",
        "ElementLoggingTarget": "",
        "StorageLoggingTarget": "localhost",
        "GroupDefinitions": "",
        "NrSubarrays": "16",
        "CapabilityTypes": "",
        "MaxCapabilities": "",
        "MccsSubarrays": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
        "MccsStations": "",
        "MccsStationBeams": "",
        "MccsTiles": "",
        "MccsAntennas": "",
    }

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsMaster.numpy = MagicMock()

    def test_properties(self, tango_context):
        """ Test the properties """

    def test_State(self, tango_context):
        """Test for State"""
        assert tango_context.device.State() == tango.DevState.ON

    def test_Status(self, tango_context):
        """Test for Status"""
        assert tango_context.device.Status() == "The device is in ON state."

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        vinfo = release.get_release_info("MccsMaster")
        assert tango_context.device.GetVersionInfo() == vinfo

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, tango_context):
        """Test for isCapabilityAchievable"""
        assert (
            tango_context.device.isCapabilityAchievable([[0], [""]])
            is not False  # force wrap
        )  # force wrap

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is None

    def test_On(self, tango_context):
        """Test for On"""
        with pytest.raises(tango.DevFailed):
            assert tango_context.device.On()

    def test_Off(self, tango_context):
        """Test for Off"""
        assert tango_context.device.Off() is None

    def test_StandbyLow(self, tango_context):
        """Test for StandbyLow"""
        assert tango_context.device.StandbyLow() == 0

    def test_StandbyFull(self, tango_context):
        """Test for StandbyFull"""
        assert tango_context.device.StandbyFull() == 0

    def test_Operate(self, tango_context):
        """Test for Operate"""
        assert tango_context.device.Operate() == 0

    def test_EnableSubarray(self, tango_context):
        """Test for EnableSubarray"""
        assert tango_context.device.EnableSubarray(0) is None

    def test_DisableSubarray(self, tango_context):
        """Test for DisableSubarray"""
        assert tango_context.device.DisableSubarray(0) is None

    def test_Allocate(self, tango_context):
        """Test for Allocate"""
        assert tango_context.device.Allocate("") is None

    def test_Release(self, tango_context):
        """Test for Release"""
        assert tango_context.device.Release(0) is None

    def test_Maintenance(self, tango_context):
        """Test for Maintenance"""
        assert tango_context.device.Maintenance() is None

    def test_buildState(self, tango_context):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert tango_context.device.buildState == binfo

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == release.version

    def test_healthState(self, tango_context):
        """Test for healthState"""
        assert tango_context.device.healthState == HealthState.OK

    def test_adminMode(self, tango_context):
        """Test for adminMode"""
        assert tango_context.device.adminMode == AdminMode.ONLINE

    def test_controlMode(self, tango_context):
        """Test for controlMode"""
        assert tango_context.device.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, tango_context):
        """Test for simulationMode"""
        assert tango_context.device.simulationMode == SimulationMode.FALSE

    def test_testMode(self, tango_context):
        """Test for testMode"""
        assert tango_context.device.testMode == TestMode.NONE

    def test_commandProgress(self, tango_context):
        """Test for commandProgress"""
        assert tango_context.device.commandProgress == 0

    def test_commandDelayExpected(self, tango_context):
        """Test for commandDelayExpected"""
        assert tango_context.device.commandDelayExpected == 0

    def test_opState(self, tango_context):
        """Test for opState"""
        assert tango_context.device.opState == tango.DevState.UNKNOWN

    def test_maxCapabilities(self, tango_context):
        """Test for maxCapabilities"""
        assert tango_context.device.maxCapabilities is None

    def test_availableCapabilities(self, tango_context):
        """Test for availableCapabilities"""
        assert tango_context.device.availableCapabilities is None
