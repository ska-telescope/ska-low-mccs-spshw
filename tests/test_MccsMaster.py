#########################################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################################
"""Contais the tests for the MccsMaster Tango device prototype."""

# from mock import MagicMock
import pytest
from tango import DevState
from ska.base.control_model import AdminMode, ControlMode, HealthState, SimulationMode, TestMode

# pylint: disable=invalid-name,too-many-public-methods
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsMaster:
    """Test case for packet generation."""

    properties = {
        'SkaLevel': '4',
        'CentralLoggingTarget': '',
        'ElementLoggingTarget': '',
        'StorageLoggingTarget': 'localhost',
        'GroupDefinitions': '',
        'NrSubarrays': '16',
        'CapabilityTypes': '',
        'MaxCapabilities': '',
        'MccsSubarrays': '',
        'LoggingLevelDefault': '4',
        'LoggingTargetsDefault': '',
        'MccsStations': '',
        'MccsStationBeams': '',
        'MccsTiles': '',
        'MccsAntennas': '',
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
        assert tango_context.device.State() == DevState.UNKNOWN

    def test_Status(self, tango_context):
        """Test for Status"""
        assert tango_context.device.Status() == "The device is in UNKNOWN state."

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        assert tango_context.device.GetVersionInfo() == [""]

    def test_isCapabilityAchievable(self, tango_context):
        """Test for isCapabilityAchievable"""
        assert tango_context.device.isCapabilityAchievable(
            [[0], [""]]) is not False

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is not None

    def test_On(self, tango_context):
        """Test for On"""
        assert tango_context.device.On() is not None

    def test_Off(self, tango_context):
        """Test for Off"""
        assert tango_context.device.Off() is not None

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
        assert tango_context.device.EnableSubarray(0) is not None

    def test_DisableSubarray(self, tango_context):
        """Test for DisableSubarray"""
        assert tango_context.device.DisableSubarray(0) is not None

    def test_Allocate(self, tango_context):
        """Test for Allocate"""
        assert tango_context.device.Allocate("") is not None

    def test_Release(self, tango_context):
        """Test for Release"""
        assert tango_context.device.Release(0) is not None

    def test_Maintenance(self, tango_context):
        """Test for Maintenance"""
        assert tango_context.device.Maintenance() is not None

    def test_elementLoggerAddress(self, tango_context):
        """Test for elementLoggerAddress"""
        assert tango_context.device.elementLoggerAddress == ''

    def test_elementAlarmAddress(self, tango_context):
        """Test for elementAlarmAddress"""
        assert tango_context.device.elementAlarmAddress == ''

    def test_elementTelStateAddress(self, tango_context):
        """Test for elementTelStateAddress"""
        assert tango_context.device.elementTelStateAddress == ''

    def test_elementDatabaseAddress(self, tango_context):
        """Test for elementDatabaseAddress"""
        assert tango_context.device.elementDatabaseAddress == ''

    def test_buildState(self, tango_context):
        """Test for buildState"""
        assert tango_context.device.buildState == ''

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == ''

    def test_centralLoggingLevel(self, tango_context):
        """Test for centralLoggingLevel"""
        assert tango_context.device.centralLoggingLevel == 0

    def test_elementLoggingLevel(self, tango_context):
        """Test for elementLoggingLevel"""
        assert tango_context.device.elementLoggingLevel == 0

    def test_storageLoggingLevel(self, tango_context):
        """Test for storageLoggingLevel"""
        assert tango_context.device.storageLoggingLevel == 0

    def test_healthState(self, tango_context):
        """Test for healthState"""
        assert tango_context.device.healthState == HealthState

    def test_adminMode(self, tango_context):
        """Test for adminMode"""
        assert tango_context.device.adminMode == AdminMode

    def test_controlMode(self, tango_context):
        """Test for controlMode"""
        assert tango_context.device.controlMode == ControlMode

    def test_simulationMode(self, tango_context):
        """Test for simulationMode"""
        assert tango_context.device.simulationMode == SimulationMode

    def test_testMode(self, tango_context):
        """Test for testMode"""
        assert tango_context.device.testMode == TestMode

    def test_commandProgress(self, tango_context):
        """Test for commandProgress"""
        assert tango_context.device.commandProgress == 0

    def test_loggingLevel(self, tango_context):
        """Test for loggingLevel"""
        assert tango_context.device.loggingLevel == 0

    def test_commandDelayExpected(self, tango_context):
        """Test for commandDelayExpected"""
        assert tango_context.device.commandDelayExpected == 0

    def test_opState(self, tango_context):
        """Test for opState"""
        assert tango_context.device.opState == DevState.UNKNOWN

    def test_maxCapabilities(self, tango_context):
        """Test for maxCapabilities"""
        assert tango_context.device.maxCapabilities == ('',)

    def test_availableCapabilities(self, tango_context):
        """Test for availableCapabilities"""
        assert tango_context.device.availableCapabilities == ('',)

    def test_subarrayFQDNs(self, tango_context):
        """Test for subarrayFQDNs"""
        assert tango_context.device.subarrayFQDNs == ('',)

    def test_loggingTargets(self, tango_context):
        """Test for loggingTargets"""
        assert tango_context.device.loggingTargets == ('',)

    def test_stationBeamFQDNs(self, tango_context):
        """Test for stationBeamFQDNs"""
        assert tango_context.device.stationBeamFQDNs == ('',)

    def test_stationFQDNs(self, tango_context):
        """Test for stationFQDNs"""
        assert tango_context.device.stationFQDNs == ('',)

    def test_tileFQDNs(self, tango_context):
        """Test for tileFQDNs"""
        assert tango_context.device.tileFQDNs == ('',)
