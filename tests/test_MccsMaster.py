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
"""Contains the tests for the MccsMaster Tango tango_device prototype."""

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
@pytest.mark.usefixtures("tango_device", "initialize_device")
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
    }

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsMaster.numpy = MagicMock()

    def test_properties(self, tango_device):
        """ Test the properties """

    def test_State(self, tango_device):
        """Test for State"""
        assert tango_device.State() == tango.DevState.ON

    def test_Status(self, tango_device):
        """Test for Status"""
        assert tango_device.Status() == "The device is in ON state."

    def test_GetVersionInfo(self, tango_device):
        """Test for GetVersionInfo"""
        vinfo = release.get_release_info(tango_device.info().dev_class)
        assert tango_device.GetVersionInfo() == [vinfo]

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, tango_device):
        """Test for isCapabilityAchievable"""
        assert tango_device.isCapabilityAchievable([[0], [""]]) is not False

    def test_Reset(self, tango_device):
        """Test for Reset"""
        assert tango_device.Reset() is None

    def test_On(self, tango_device):
        """Test for On"""
        with pytest.raises(tango.DevFailed):
            assert tango_device.On()

    def test_Off(self, tango_device):
        """Test for Off"""
        assert tango_device.Off() is None

    def test_StandbyLow(self, tango_device):
        """Test for StandbyLow"""
        assert tango_device.StandbyLow() == 0

    def test_StandbyFull(self, tango_device):
        """Test for StandbyFull"""
        assert tango_device.StandbyFull() == 0

    def test_Operate(self, tango_device):
        """Test for Operate"""
        assert tango_device.Operate() == 0

    def test_Maintenance(self, tango_device):
        """Test for Maintenance"""
        assert tango_device.Maintenance() is None

    def test_buildState(self, tango_device):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert tango_device.buildState == binfo

    def test_versionId(self, tango_device):
        """Test for versionId"""
        assert tango_device.versionId == release.version

    def test_healthState(self, tango_device):
        """Test for healthState"""
        assert tango_device.healthState == HealthState.OK

    def test_adminMode(self, tango_device):
        """Test for adminMode"""
        assert tango_device.adminMode == AdminMode.ONLINE

    def test_controlMode(self, tango_device):
        """Test for controlMode"""
        assert tango_device.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, tango_device):
        """Test for simulationMode"""
        assert tango_device.simulationMode == SimulationMode.FALSE

    def test_testMode(self, tango_device):
        """Test for testMode"""
        assert tango_device.testMode == TestMode.NONE

    def test_commandProgress(self, tango_device):
        """Test for commandProgress"""
        assert tango_device.commandProgress == 0

    def test_commandDelayExpected(self, tango_device):
        """Test for commandDelayExpected"""
        assert tango_device.commandDelayExpected == 0

    def test_opState(self, tango_device):
        """Test for opState"""
        assert tango_device.opState == tango.DevState.UNKNOWN

    def test_maxCapabilities(self, tango_device):
        """Test for maxCapabilities"""
        assert tango_device.maxCapabilities is None

    def test_availableCapabilities(self, tango_device):
        """Test for availableCapabilities"""
        assert tango_device.availableCapabilities is None
