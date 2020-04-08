###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTile project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contain the tests for the SKA MCCS Tile Device Server."""

# Imports
import pytest
import numpy as np
from tango import DevState, DevFailed

# from ska.mccs import release
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
        assert tango_context.device.loggingLevel == LoggingLevel.INFO

    def test_InitialState(self, tango_context):
        """Test for Initial State"""
        assert tango_context.device.state() == DevState.ON
        assert tango_context.device.adminMode == AdminMode.ONLINE
        assert tango_context.device.healthState == HealthState.OK
        assert tango_context.device.controlMode == ControlMode.REMOTE
        assert tango_context.device.status() == "The device is in ON state."
        assert tango_context.device.simulationMode == SimulationMode.FALSE
        assert tango_context.device.testMode == TestMode.NONE

    def test_isProgrammed(self, tango_context):
        """Test for isProgrammed"""
        assert tango_context.device.isProgrammed is False

    def test_Initialise(self, tango_context):
        """Test for Initialise"""
        assert tango_context.device.Initialise() is None

    def test_Connect(self, tango_context):
        """Test for Connect"""
        assert tango_context.device.Connect(False) is None

    def test_Disconnect(self, tango_context):
        """Test for Disconnect"""
        assert tango_context.device.Disconnect() is None

    def test_GetFirmwareList(self, tango_context):
        """Test for GetFirmwareList"""
        assert tango_context.device.GetFirmwareList() == []

    def test_DownloadFirmware(self, tango_context):
        """Test for DownloadFirmware"""
        assert tango_context.device.DownloadFirmware("") is None

    def test_ProgramCPLD(self, tango_context):
        """Test for ProgramCPLD"""
        assert tango_context.device.ProgramCPLD("") is None

    def test_WaitPPSEvent(self, tango_context):
        """Test for WaitPPSEvent"""
        assert tango_context.device.WaitPPSEvent() is None

    def test_GetRegisterList(self, tango_context):
        """Test for GetRegisterList"""
        assert tango_context.device.GetRegisterList() == []

    def test_ReadRegister(self, tango_context):
        """Test for ReadRegister"""
        with pytest.raises(DevFailed):
            tango_context.device.ReadRegister([1, 2, 3])

    def test_WriteRegister(self, tango_context):
        """Test for WriteRegister"""
        assert tango_context.device.WriteRegister([0]) is None

    def test_ReadAddress(self, tango_context):
        """Test for ReadAddress"""
        assert tango_context.device.ReadAddress([0]) == [0]

    def test_WriteAddress(self, tango_context):
        """Test for WriteAddress"""
        assert tango_context.device.WriteAddress([0]) is None

    def test_Configure40GCore(self, tango_context):
        """Test for Configure40GCore
        1. Check for insufficient values
        2. Check correct number of values entered
        3. Check retrieving the values
        4. Check for invalid core id
        """
        good_values = [10, 20, 30, 40, 50, 60, 70]
        bad_values = [10, 20, 30, 40, 50, 60]
        expected = np.array([20, 30, 40, 50, 60, 70], dtype=np.uint32)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(bad_values)
        assert tango_context.device.Configure40GCore(good_values) is None
        result = tango_context.device.Get40GCoreConfiguration(10)
        assert (result == expected).all()
        with pytest.raises(DevFailed):
            tango_context.device.Get40GCoreConfiguration(1)

    def test_SetLMCDownload(self, tango_context):
        """Test for SetLMCDownload"""
        assert tango_context.device.SetLMCDownload([0]) is None

    def test_SetChanneliserTruncation(self, tango_context):
        """Test for SetChanneliserTruncation"""
        assert tango_context.device.SetChanneliserTruncation([0]) is None

    def test_SetBeamFormerRegions(self, tango_context):
        """Test for SetBeamFormerRegions"""
        assert tango_context.device.SetBeamFormerRegions([0]) is None

    def test_ConfigureStationBeamformer(self, tango_context):
        """Test for ConfigureStationBeamformer"""
        assert tango_context.device.ConfigureStationBeamformer([0]) is None

    def test_LoadCalibrationCoefficients(self, tango_context):
        """Test for LoadCalibrationCoefficients"""
        assert tango_context.device.LoadCalibrationCoefficients([0.0]) is None

    def test_LoadBeamAngle(self, tango_context):
        """Test for LoadBeamAngle"""
        assert tango_context.device.LoadBeamAngle([0.0]) is None

    def test_LoadAntennaTapering(self, tango_context):
        """Test for LoadAntennaTapering"""
        assert tango_context.device.LoadAntennaTapering([0.0]) is None

    def test_SwitchCalibrationBank(self, tango_context):
        """Test for SwitchCalibrationBank"""
        assert tango_context.device.SwitchCalibrationBank(0.0) is None

    def test_SetPointingDelay(self, tango_context):
        """Test for SetPointingDelay"""
        assert tango_context.device.SetPointingDelay([0]) is None

    def test_LoadPointingDelay(self, tango_context):
        """Test for LoadPointingDelay"""
        assert tango_context.device.LoadPointingDelay(0.0) is None

    def test_StartBeamformer(self, tango_context):
        """Test for StartBeamformer"""
        assert tango_context.device.StartBeamformer(0.0) is None

    def test_StopBeamformer(self, tango_context):
        """Test for StopBeamformer"""
        assert tango_context.device.StopBeamformer() is None

    def test_ConfigureIntegratedChannelData(self, tango_context):
        """Test for ConfigureIntegratedChannelData"""
        assert tango_context.device.ConfigureIntegratedChannelData(0.0) is None

    def test_ConfigureIntegratedBeamData(self, tango_context):
        """Test for ConfigureIntegratedBeamData"""
        assert tango_context.device.ConfigureIntegratedBeamData(0.0) is None

    def test_SendRawData(self, tango_context):
        """Test for SendRawData"""
        assert tango_context.device.SendRawData() is None

    def test_SendChannelisedData(self, tango_context):
        """Test for SendChannelisedData"""
        assert tango_context.device.SendChannelisedData(0) is None

    def test_SendChannelisedDataContinuous(self, tango_context):
        """Test for SendChannelisedDataContinuous"""
        assert tango_context.device.SendChannelisedDataContinuous(0) is None

    def test_SendBeamData(self, tango_context):
        """Test for SendBeamData"""
        assert tango_context.device.SendBeamData() is None

    def test_StopDataTransmission(self, tango_context):
        """Test for StopDataTransmission"""
        assert tango_context.device.StopDataTransmission() is None

    def test_tileId(self, tango_context):
        """Test for tileId"""
        assert tango_context.device.tileId == -1

    def test_logicalTpmId(self, tango_context):
        """Test for logicalTpmId"""
        assert tango_context.device.logicalTpmId == -1

    def test_subarrayId(self, tango_context):
        """Test for subarrayId"""
        assert tango_context.device.subarrayId == -1

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
        assert tango_context.device.stationId == -1

    def test_fpga1_time(self, tango_context):
        """Test for fpga1_time"""
        assert tango_context.device.fpga1_time == 0.0

    def test_fpga2_time(self, tango_context):
        """Test for fpga2_time"""
        assert tango_context.device.fpga2_time == 0.0

    def test_antennaIds(self, tango_context):
        """Test for antennaIds"""
        assert tango_context.device.antennaIds is None

    def test_fortyGbDestinationIps(self, tango_context):
        """Test for fortyGbDestinationIps"""
        assert tango_context.device.fortyGbDestinationIps is None

    def test_fortyGbDestinationMacs(self, tango_context):
        """Test for fortyGbDestinationMacs"""
        assert tango_context.device.fortyGbDestinationMacs is None

    def test_fortyGbDestinationPorts(self, tango_context):
        """Test for fortyGbDestinationPorts"""
        assert tango_context.device.fortyGbDestinationPorts is None

    def test_adcPower(self, tango_context):
        """Test for adcPower"""
        assert tango_context.device.adcPower is None
