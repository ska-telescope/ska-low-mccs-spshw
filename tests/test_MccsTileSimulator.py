#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTileSimulator project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
""" Test file for SKA MCCS Tile Simulator Device Server. """

#__all__ = ["tile_simulator", "main"]
# Imports
import pytest
import numpy as np
import sys
import os

# PyTango imports
from tango import DevFailed
from tango import DevState
# from tango.server import attribute, command, Device, DeviceMeta
# from tango.server import device_property

# Additional import
# from ska.mccs.tile_simulator import MccsTileSimulator
# from ska.mccs.group_device import MccsGroupDevice
# from ska.mccs.tpm_simulator import TpmSimulator
from ska.base.control_model import LoggingLevel

path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(path))

# Device test case
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsTileSimulator(object):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS Tile
    device server methods.
    """

    # -----------------
    # Device Properties
    # -----------------
#    TileIP = device_property(dtype=str, default_value="0.0.0.0")
#    TpmCpldPort = device_property(dtype=int, default_value=20000)
#    LmcIp = device_property(dtype=str, default_value="0.0.0.0")
#    DstPort = device_property(dtype=int, default_value=30000)

    # ---------------
    # General methods
    # ---------------

    # ----------
    # Device test cases, based upon Attributes methods defined in
    # tile_simulator.py
    # ----------
    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    def test_properties(self, tango_context):
        """Test the properties """
        assert tango_context.device.loggingLevel == LoggingLevel.INFO

    def test_State(self, tango_context):
        """Test for State"""
        assert tango_context.device.state() == DevState.ON

    #    def test_Status(self, tango_context):
    #        """Test for Status"""
    #        assert tango_context.device.status() == "This device is On"

    def test_PowerOn(self, tango_context):
        """Test for PowerOn"""
        assert tango_context.device.PowerOn() is None

    def test_PowerOff(self, tango_context):
        """Test for PowerOff"""
        assert tango_context.device.PowerOff() is None

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is None




    def test_is_connected(self, tango_context):
        """
        Test for Helper to disallow certain function
        calls on unconnected tiles
        """
        assert tango_context.device.is_connected is True

    def test_tileId(self, tango_context):
        """Test for the tileId attribute."""
        assert tango_context.device.tileID == -1

    def test_logicalTpmId(self, tango_context):
        """Test for the logicalTpmId attribute."""
        assert tango_context.device.logicalTpmId == -1

    def test_subarrayId(self, tango_context):
        """Test for the subarrayId attribute."""
        assert tango_context.device.subarrayId == -1

    def test_stationId(self, tango_context):
        """Test for the stationId attribute."""
        assert tango_context.device.stationId == -1

    def test_ipAddress(self, tango_context):
        """Test for the ipAddress attribute."""
        assert tango_context.device.ipAddress == ""

    def test_lmcIp(self, tango_context):
        """Test for the lmcIp attribute"""
        assert tango_context.device.lmcIp == ""

    def test_lmcPort(self, tango_context):
        """Test for the lmcPort attribute"""
        assert tango_context.device.lmcPort == 0

    def test_cspDestinationIp(self, tango_context):
        """Test for the cspDestinationIp attribute."""
        assert tango_context.device.cspDestinationIp == ""

    def test_cspDestinationMac(self, tango_context):
        """Test for the cspDestinationMac attribute."""
        assert tango_context.device.cspDestinationMac == ""

    def test_cspDestinationPort(self, tango_context):
        """Test for the cspDestinationPort attribute."""
        assert tango_context.device.cspDestinationPort == 0

    def test_firmwareName(self, tango_context):
        """Test for the firmwareName attribute."""
        assert tango_context.device.firmwareName == ""

    def test_firmwareVersion(self, tango_context):
        """Test for the firmwareVersion attribute."""
        assert tango_context.device.firmwareVersion == ""

    def test_voltage(self, tango_context):
        """Test for the voltage attribute."""
        assert tango_context.device.voltage == 0.0

    def test_current(self, tango_context):
        """Test for the current attribute."""
        assert tango_context.device.current == 0.0

    def test_isProgrammed(self, tango_context):
        """ Test that returns false to mimic that the board is not programmed"""
        assert tango_context.device.isProgrammed is False

    def test_board_temperature(self, tango_context):
        """Test for the board_temperature attribute."""
        assert tango_context.device.board_temperature == 0.0

    def test_fpga1_temperature(self, tango_context):
        """Test for the fpga1_temperature attribute."""
        assert tango_context.device.fpga1_temperature == 0.0

    def test_fpga2_temperature(self, tango_context):
        """Test for the fpga2_temperature attribute."""
        assert tango_context.device.fpga2_temperature == 0.0

    def test_fpga1_time(self, tango_context):
        """Test for the fpga1_time attribute."""
        assert tango_context.device.fpga1_time == 0.0

    def test_fpga2_time(self, tango_context):
        """Test the fpga2_time attribute."""
        assert tango_context.device.fpga2_time == 0.0

    def test_antennaIds(self, tango_context):
        """Test for the antennaIds attribute."""
        assert tango_context.device.antenna_ids == [0]

    def test_fortyGbDestinationIps(self, tango_context):
        """Test for the fortyGbDestinationIps attribute."""
        assert tango_context.device.forty_gb_destination_ips == [0]

    def test_fortyGbDestinationMacs(self, tango_context):
        """Test for the fortyGbDestinationMacs attribute."""
        assert tango_context.device.forty_gb_destination_macs == [0]

    def test_fortyGbDestinationPorts(self, tango_context):
        """Test for the fortyGbDestinationPorts attribute."""
        assert tango_context.device.forty_gb_destination_ports == [0]

    def test_adcPower(self, tango_context):
        # Test if board is not programmed, return None
        assert tango_context.device.adcPower is None

    # ------------------------------------------------------
    # Commands.
    # Tests for commands by calling the method by assertion.
    # ------------------------------------------------------

    def test_Initialise(self, tango_context):
        """Test for Initialise"""
        assert tango_context.device.Initialise() is None

    def test_Connect(self, tango_context):
        """Test for Connect"""
        assert tango_context.device.Connect(False) is None

    def test_Disconnect(self, tango_context):
        """ Test for Disconnect from the board"""
        assert tango_context.device.Disconnect() is None

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

#   def Get40GCoreConfiguration(self, argin):
#
#        """
#        Get 10g core configuration for core_id.
#        This is required to chain up TPMs to form a station
#
#        :return: the configuration as an array comprising:
#                 src_mac, src_ip, src_port, dest_mac, dest_ip, dest_port
#        :rtype: DevVarUlongArray
#        """
#        for item in self._forty_gb_core_list:
#            if argin == item["core_id"]:
#                return [
#                    item["src_mac"],
#                    item["src_ip"],
#                    item["src_port"],
#                    item["dst_mac"],
#                    item["dst_ip"],
#                    item["dst_port"],
#                ]
#        raise ValueError("Invalid core id specified")
#
#    @command(dtype_in="DevVarLongArray", doc_in="mode, payload_length, src_ip, lmc_mac")
#    @DebugIt()

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
