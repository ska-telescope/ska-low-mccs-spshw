#########################################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTile project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################################
"""Contain the tests for the SKA MCCS Tile Device Server."""

# Path
import sys
import os

path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(path))

# Imports
import pytest
from mock import MagicMock

from PyTango import DevState
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    LoggingLevel,
    SimulationMode,
    TestMode,
)


# Device test case
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsTile(object):
    """Test case for MCCS tile."""

    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    def test_properties(self, tango_context):
        """ Test the properties """
        assert tango_context.device.loggingLevel == 4
        assert tango_context.device.SKALevel == 4

    def test_InitialState(self, tango_context):
        """Test for Initial State"""
        assert tango_context.device.state() == DevState.ON
        assert tango_context.device.adminMode == AdminMode.ONLINE
        assert tango_context.device.healthState == HealthState.OK
        assert tango_context.device.controlMode == ControlMode.REMOTE
        assert tango_context.device.status() == "The device is in ON state."
        assert tango_context.device.simulationMode == False
        assert tango_context.device.testMode == None

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        info = [
            ", ".join(("MccsTile", release.NAME, release.VERSION, release.DESCRIPTION))
        ]
        assert tango_context.device.GetVersionInfo() == info

    def test_buildState(self, tango_context):
        """Test for buildState"""
        info = ", ".join((release.NAME, release.VERSION, release.DESCRIPTION))
        assert tango_context.device.buildState == info

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == release.VERSION

    def test_isProgrammed(self, tango_context):
        """Test for isProgrammed"""
        assert tango_context.device.isProgrammed == False

    #
    # The following are POGO generated tests and presented as is
    #
    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() == None

    def test_Initialise(self, tango_context):
        """Test for Initialise"""
        assert tango_context.device.Initialise() == None

    def test_Connect(self, tango_context):
        """Test for Connect"""
        assert tango_context.device.Connect(False) == None

    def test_Disconnect(self, tango_context):
        """Test for Disconnect"""
        assert tango_context.device.Disconnect() == None

    def test_DownloadFirmware(self, tango_context):
        """Test for DownloadFirmware"""
        assert tango_context.device.DownloadFirmware("") == None

    def test_ProgramCPLD(self, tango_context):
        """Test for ProgramCPLD"""
        assert tango_context.device.ProgramCPLD("") == None

    def test_WaitPPSEvent(self, tango_context):
        """Test for WaitPPSEvent"""
        assert tango_context.device.WaitPPSEvent() == None

    def test_GetRegisterList(self, tango_context):
        """Test for GetRegisterList"""
        assert tango_context.device.GetRegisterList() == 0

    def test_ReadRegister(self, tango_context):
        """Test for ReadRegister"""
        assert tango_context.device.ReadRegister([0]) == [0]

    def test_WriteRegister(self, tango_context):
        """Test for WriteRegister"""
        assert tango_context.device.WriteRegister([0]) == None

    def test_ReadAddress(self, tango_context):
        """Test for ReadAddress"""
        assert tango_context.device.ReadAddress([0]) == [0]

    def test_WriteAddress(self, tango_context):
        """Test for WriteAddress"""
        assert tango_context.device.WriteAddress([0]) == None

    def test_Configure40GCore(self, tango_context):
        """Test for Configure40GCore"""
        assert tango_context.device.Configure40GCore([0]) == None

    def test_Get40GCoreConfiguration(self, tango_context):
        """Test for Get40GCoreConfiguration"""
        assert tango_context.device.Get40GCoreConfiguration(0) == [0]

    def test_SetLMCDownload(self, tango_context):
        """Test for SetLMCDownload"""
        assert tango_context.device.SetLMCDownload([0]) == None

    def test_SetChanneliserTruncation(self, tango_context):
        """Test for SetChanneliserTruncation"""
        assert tango_context.device.SetChanneliserTruncation([0]) == None

    def test_SetBeamFormerRegions(self, tango_context):
        """Test for SetBeamFormerRegions"""
        assert tango_context.device.SetBeamFormerRegions([0]) == None

    def test_ConfigureStationBeamformer(self, tango_context):
        """Test for ConfigureStationBeamformer"""
        assert tango_context.device.ConfigureStationBeamformer([0]) == None

    def test_LoadCalibrationCoefficients(self, tango_context):
        """Test for LoadCalibrationCoefficients"""
        assert tango_context.device.LoadCalibrationCoefficients("", "") == None

    def test_LoadBeamAngle(self, tango_context):
        """Test for LoadBeamAngle"""
        assert tango_context.device.LoadBeamAngle([0.0]) == None

    def test_LoadAntennaTapering(self, tango_context):
        """Test for LoadAntennaTapering"""
        assert tango_context.device.LoadAntennaTapering([0.0]) == None

    def test_SwitchCalibrationBank(self, tango_context):
        """Test for SwitchCalibrationBank"""
        assert tango_context.device.SwitchCalibrationBank(0.0) == None

    def test_SetPointingDelay(self, tango_context):
        """Test for SetPointingDelay"""
        assert tango_context.device.SetPointingDelay([0]) == None

    def test_LoadPointingDelay(self, tango_context):
        """Test for LoadPointingDelay"""
        assert tango_context.device.LoadPointingDelay(0.0) == None

    def test_StartBeamformer(self, tango_context):
        """Test for StartBeamformer"""
        assert tango_context.device.StartBeamformer(0.0) == None

    def test_StopBeamformer(self, tango_context):
        """Test for StopBeamformer"""
        assert tango_context.device.StopBeamformer() == None

    def test_ConfigureIntegratedChannelData(self, tango_context):
        """Test for ConfigureIntegratedChannelData"""
        assert tango_context.device.ConfigureIntegratedChannelData(0.0) == None

    def test_ConfigureIntegratedBeamData(self, tango_context):
        """Test for ConfigureIntegratedBeamData"""
        assert tango_context.device.ConfigureIntegratedBeamData(0.0) == None

    def test_SendRawData(self, tango_context):
        """Test for SendRawData"""
        assert tango_context.device.SendRawData() == None

    def test_SendChannelisedData(self, tango_context):
        """Test for SendChannelisedData"""
        assert tango_context.device.SendChannelisedData(0) == None

    def test_SendChannelisedDataContinuous(self, tango_context):
        """Test for SendChannelisedDataContinuous"""
        assert tango_context.device.SendChannelisedDataContinuous(0) == None

    def test_SendBeamData(self, tango_context):
        """Test for SendBeamData"""
        assert tango_context.device.SendBeamData() == None

    def test_StopDataTransmission(self, tango_context):
        """Test for StopDataTransmission"""
        assert tango_context.device.StopDataTransmission() == None

    def test_tileId(self, tango_context):
        """Test for tileId"""
        assert tango_context.device.tileId == 0

    def test_logicalTpmId(self, tango_context):
        """Test for logicalTpmId"""
        assert tango_context.device.logicalTpmId == 0

    def test_subarrayId(self, tango_context):
        """Test for subarrayId"""
        assert tango_context.device.subarrayId == 0

    def test_ipAddress(self, tango_context):
        """Test for ipAddress"""
        assert tango_context.device.ipAddress == ""

    def test_lmcIp(self, tango_context):
        """Test for lmcIp"""
        assert tango_context.device.lmcIp == ""

    def test_lmcPort(self, tango_context):
        """Test for lmcPort"""
        assert tango_context.device.lmcPort == 0

    def test_cspDestinationIp(self, tango_context):
        """Test for cspDestinationIp"""
        assert tango_context.device.cspDestinationIp == ""

    def test_cspDestinationMac(self, tango_context):
        """Test for cspDestinationMac"""
        assert tango_context.device.cspDestinationMac == ""

    def test_cspDestinationPort(self, tango_context):
        """Test for cspDestinationPort"""
        assert tango_context.device.cspDestinationPort == 0

    def test_firmwareName(self, tango_context):
        """Test for firmwareName"""
        assert tango_context.device.firmwareName == ""

    def test_firmwareVersion(self, tango_context):
        """Test for firmwareVersion"""
        assert tango_context.device.firmwareVersion == ""

    def test_voltage(self, tango_context):
        """Test for voltage"""
        assert tango_context.device.voltage == 0.0

    def test_current(self, tango_context):
        """Test for current"""
        assert tango_context.device.current == 0.0

    def test_board_temperature(self, tango_context):
        """Test for board_temperature"""
        assert tango_context.device.board_temperature == 0.0

    def test_fpga1_temperature(self, tango_context):
        """Test for fpga1_temperature"""
        assert tango_context.device.fpga1_temperature == 0.0

    def test_fpga2_temperature(self, tango_context):
        """Test for fpga2_temperature"""
        assert tango_context.device.fpga2_temperature == 0.0

    def test_stationId(self, tango_context):
        """Test for stationId"""
        assert tango_context.device.stationId == 0

    def test_fpga1_time(self, tango_context):
        """Test for fpga1_time"""
        assert tango_context.device.fpga1_time == 0.0

    def test_fpga2_time(self, tango_context):
        """Test for fpga2_time"""
        assert tango_context.device.fpga2_time == 0.0

    def test_loggingTargets(self, tango_context):
        """Test for loggingTargets"""
        assert tango_context.device.loggingTargets == ("",)

    def test_antennaIds(self, tango_context):
        """Test for antennaIds"""
        assert tango_context.device.antennaIds == (0,)

    def test_fortyGbDestinationIps(self, tango_context):
        """Test for fortyGbDestinationIps"""
        assert tango_context.device.fortyGbDestinationIps == ("",)

    def test_fortyGbDestinationMacs(self, tango_context):
        """Test for fortyGbDestinationMacs"""
        assert tango_context.device.fortyGbDestinationMacs == ("",)

    def test_fortyGbDestinationPorts(self, tango_context):
        """Test for fortyGbDestinationPorts"""
        assert tango_context.device.fortyGbDestinationPorts == (0,)

    def test_adcPower(self, tango_context):
        """Test for adcPower"""
        assert tango_context.device.adcPower == (0.0,)
