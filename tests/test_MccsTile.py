#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTile project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
""" Test file for SKA MCCS Tile Device Server. """

# Imports
import io
import json
import time
import pytest
import itertools
import numpy as np
from contextlib import redirect_stdout

# PyTango imports
from tango import DevState, DevFailed


class TestMccsTile(object):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS Tile
    device server methods.
    """

    def test_State(self, tango_device):
        """Test for State"""
        assert tango_device.state() == DevState.OFF
        tango_device.Connect(True)
        assert tango_device.state() == DevState.ON

    def test_tileId(self, tango_device):
        """Test for the tileId attribute."""
        assert tango_device.tileID == 0
        tango_device.tileID = 9
        assert tango_device.tileID == 9

    def test_logicalTileId(self, tango_device):
        """Test for the logicalTpmId attribute."""
        assert tango_device.logicalTileId == 0
        tango_device.logicalTileId = 7
        assert tango_device.logicalTileId == 7

    def test_subarrayId(self, tango_device):
        """Test for the subarrayId attribute."""
        assert tango_device.subarrayId == 0
        tango_device.subarrayId = 3
        assert tango_device.subarrayId == 3

    def test_stationId(self, tango_device):
        """Test for the stationId attribute."""
        assert tango_device.stationId == 0
        tango_device.stationId = 5
        assert tango_device.stationId == 5

    def test_ipAddress(self, tango_device):
        """Test for the ipAddress attribute."""
        assert tango_device.ipAddress == "0.0.0.0"
        tango_device.ipAddress = "10.0.23.99"
        assert tango_device.ipAddress == "10.0.23.99"

    def test_lmcIp(self, tango_device):
        """Test for the lmcIp attribute"""
        assert tango_device.lmcIp == "0.0.0.0"
        tango_device.lmcIp = "10.0.23.50"
        assert tango_device.lmcIp == "10.0.23.50"

    def test_lmcPort(self, tango_device):
        """Test for the lmcPort attribute"""
        assert tango_device.lmcPort == 30000
        tango_device.lmcPort = 40000
        assert tango_device.lmcPort == 40000

    def test_cspDestinationIp(self, tango_device):
        """Test for the cspDestinationIp attribute."""
        assert tango_device.cspDestinationIp == ""
        tango_device.cspDestinationIp = "10.0.23.56"
        assert tango_device.cspDestinationIp == "10.0.23.56"

    def test_cspDestinationMac(self, tango_device):
        """Test for the cspDestinationMac attribute."""
        assert tango_device.cspDestinationMac == ""
        tango_device.cspDestinationMac = "10:fe:fa:06:0b:99"
        assert tango_device.cspDestinationMac == "10:fe:fa:06:0b:99"

    def test_cspDestinationPort(self, tango_device):
        """Test for the cspDestinationPort attribute."""
        assert tango_device.cspDestinationPort == 0
        tango_device.cspDestinationPort = 4567
        assert tango_device.cspDestinationPort == 4567

    def test_firmwareName(self, tango_device):
        """Test for the firmwareName attribute."""
        assert tango_device.firmwareName == ""
        tango_device.firmwareName = "test_firmware"
        assert tango_device.firmwareName == "test_firmware"

    def test_firmwareVersion(self, tango_device):
        """Test for the firmwareVersion attribute."""
        assert tango_device.firmwareVersion == ""
        tango_device.firmwareVersion = "01-beta"
        assert tango_device.firmwareVersion == "01-beta"

    def test_voltage(self, tango_device):
        """Test for the voltage attribute."""
        tango_device.Connect(True)
        assert tango_device.voltage == 10.5

    def test_current(self, tango_device):
        """Test for the current attribute."""
        tango_device.Connect(True)
        tango_device.current == 0.4

    def test_isProgrammed(self, tango_device):
        """Test for isProgrammed"""
        tango_device.Connect(True)
        assert tango_device.isProgrammed is True

    def test_board_temperature(self, tango_device):
        """Test for the board_temperature attribute."""
        tango_device.Connect(True)
        assert tango_device.board_temperature == 40.0

    def test_fpga1_temperature(self, tango_device):
        """Test for the fpga1_temperature attribute."""
        tango_device.Connect(True)
        assert tango_device.fpga1_temperature == 38.0

    def test_fpga2_temperature(self, tango_device):
        """Test for the fpga2_temperature attribute."""
        tango_device.Connect(True)
        assert tango_device.fpga2_temperature == 37.5

    def test_fpga1_time(self, tango_device):
        """Test for the fpga1_time attribute."""
        tango_device.Connect(True)
        assert tango_device.fpga1_time == 0
        sec = int(time.time())
        tango_device.fpga1_time = sec
        assert tango_device.fpga1_time == sec

    def test_fpga2_time(self, tango_device):
        """Test the fpga2_time attribute."""
        tango_device.Connect(True)
        assert tango_device.fpga2_time == 0
        tango_device.fpga2_time = 1535
        assert tango_device.fpga2_time == 1535

    def test_antennaIds(self, tango_device):
        """Test for the antennaIds attribute."""
        assert (tango_device.AntennaIds == []).all()
        new_ids = [i for i in range(8)]
        tango_device.AntennaIds = new_ids
        assert (tango_device.AntennaIds == new_ids).all()

    def test_fortyGbDestinationIps(self, tango_device):
        """Test for fortyGbDestinationIps"""
        tango_device.Connect(True)
        dict1 = {
            "CoreID": 1,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:59",
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict1)
        tango_device.Configure40GCore(jstr)
        dict2 = {
            "CoreID": 2,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:57",
            "DstIP": "10.0.98.4",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict2)
        tango_device.Configure40GCore(jstr)
        assert tango_device.fortyGbDestinationIps == ("10.0.98.3", "10.0.98.4")

    def test_fortyGbDestinationMacs(self, tango_device):
        """Test for fortyGbDestinationMacs"""
        tango_device.Connect(True)
        dict1 = {
            "CoreID": 1,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:59",
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict1)
        tango_device.Configure40GCore(jstr)
        dict2 = {
            "CoreID": 2,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:57",
            "DstIP": "10.0.98.4",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict2)
        tango_device.Configure40GCore(jstr)
        assert tango_device.fortyGbDestinationMacs == (
            "10:fe:ed:08:0b:59",
            "10:fe:ed:08:0b:57",
        )

    def test_fortyGbDestinationPorts(self, tango_device):
        """Test for fortyGbDestinationPorts"""
        tango_device.Connect(True)
        dict1 = {
            "CoreID": 1,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:59",
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict1)
        tango_device.Configure40GCore(jstr)
        dict2 = {
            "CoreID": 2,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:57",
            "DstIP": "10.0.98.4",
            "DstPort": 5001,
        }
        jstr = json.dumps(dict2)
        tango_device.Configure40GCore(jstr)
        assert (tango_device.fortyGbDestinationPorts == (5000, 5001)).all()

    def test_adcPower(self, tango_device):
        """ Test if board is not programmed, return None"""
        tango_device.Connect(True)
        expected = [float(i) for i in range(32)]
        assert (tango_device.adcPower == expected).all()

    def test_currentTileBeamformerFrame(self, tango_device):
        tango_device.Connect(True)
        assert tango_device.CurrentTileBeamformerFrame == 23

    def test_checkPendingDataRequests(self, tango_device):
        tango_device.Connect(True)
        assert tango_device.CheckPendingDataRequests is False

    def test_isBeamformerRunning(self, tango_device):
        tango_device.Connect(True)
        assert tango_device.isBeamformerRunning is False
        tango_device.StartBeamformer("{}")
        assert tango_device.isBeamformerRunning is True

    def test_phaseTerminalCount(self, tango_device):
        tango_device.Connect(True)
        assert tango_device.PhaseTerminalCount == 0
        tango_device.PhaseTerminalCount = 45
        assert tango_device.PhaseTerminalCount == 45

    def test_ppsDelay(self, tango_device):
        tango_device.Connect(True)
        assert tango_device.ppsDelay == 12

    # ------------------------------------------------------
    # Commands.
    # Tests for commands by calling the method by assertion.
    # ------------------------------------------------------

    def test_Initialise(self, tango_device):
        """Test for Initialise"""
        tango_device.Connect(False)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.Initialise()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: initialise"

    def test_Connect(self, tango_device):
        """Test for Connect"""
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.Connect(False)
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: connect"

    def test_Disconnect(self, tango_device):
        """ Test for Disconnect from the board"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.disconnect()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: disconnect"

    def test_GetFirmwareList(self, tango_device):
        """ Test for GetFirmwareList """
        tango_device.Connect(True)
        firmware_str = tango_device.GetFirmwareList()
        firmware_list = json.loads(firmware_str)
        assert firmware_list == {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
        }

    def test_DownloadFirmware(self, tango_device):
        """Test for DownloadFirmware"""
        tango_device.Connect(False)
        bitfile = "test_bitload_firmware"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.DownloadFirmware(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_ProgramCPLD(self, tango_device):
        """Test for ProgramCPLD"""
        tango_device.Connect(True)
        bitfile = "test_bitload_cpld"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ProgramCPLD(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_WaitPPSEvent(self, tango_device):
        """Test for WaitPPSEvent"""
        tango_device.Connect(True)
        tango_device.fpga1_time = int(time.time())
        assert tango_device.WaitPPSEvent() is None

    def test_GetRegisterList(self, tango_device):
        """Test for GetRegisterList"""
        tango_device.Connect(True)
        assert tango_device.GetRegisterList() == [
            "test-reg1",
            "test-reg2",
            "test-reg3",
            "test-reg4",
        ]

    def test_ReadAndWriteRegister(self, tango_device):
        """Test for ReadRegister & WriteRegister"""
        tango_device.Connect(True)
        nb_read = 4
        offset = 1
        device = 0
        dict = {
            "RegisterName": "test-reg1",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = tango_device.ReadRegister(jstr)
        assert (values == [0 for i in range(nb_read)]).all()
        values = [i for i in range(9)]
        offset = 2
        dict1 = {
            "RegisterName": "test-reg1",
            "Values": values,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict1)
        tango_device.WriteRegister(jstr)
        jstr = json.dumps(dict)
        values = tango_device.ReadRegister(jstr)
        assert (values == [0, 0, 1, 2]).all()
        dict2 = dict.copy()
        dict2.pop("RegisterName")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("NbRead")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Offset")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Device")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_device.ReadRegister(jstr)
        device = 1
        dict = {
            "RegisterName": "test-reg1",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = tango_device.ReadRegister(jstr)
        assert (values == [0 for i in range(nb_read)]).all()
        dict = {
            "RegisterName": "test-reg5",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = tango_device.ReadRegister(jstr)
        assert len(values) == 0

        dict3 = dict1.copy()
        dict3.pop("RegisterName")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Values")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Offset")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Device")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_device.WriteRegister(jstr)

    def test_ReadAndWriteAddress(self, tango_device):
        """Test for ReadAddress and WriteAddress"""
        tango_device.Connect(True)
        address = 0xf
        nvalues = 10
        expected = [0 for i in range(nvalues)]
        assert (tango_device.ReadAddress([address, nvalues]) == expected).all()
        values = [val for val in range(nvalues)]
        values.insert(0, address)
        tango_device.WriteAddress(values)
        assert (
            tango_device.ReadAddress([address, nvalues]) == values[1:]
        ).all()
        with pytest.raises(DevFailed):
            tango_device.ReadAddress([address])
        with pytest.raises(DevFailed):
            tango_device.WriteAddress([address])

    def test_Configure40GCore(self, tango_device):
        """Test for Configure40GCore"""
        tango_device.Connect(True)
        dict1 = {
            "CoreID": 1,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:59",
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict1)
        tango_device.Configure40GCore(jstr)
        dict2 = {
            "CoreID": 2,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:57",
            "DstIP": "10.0.98.4",
            "DstPort": 5000,
        }
        jstr = json.dumps(dict2)
        tango_device.Configure40GCore(jstr)
        output = tango_device.Get40GCoreConfiguration(1)
        result = json.loads(output)
        assert result == dict1.pop("CoreID")
        with pytest.raises(DevFailed):
            output = tango_device.Get40GCoreConfiguration(3)

        dict = dict2.copy()
        dict.pop("CoreID")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.Configure40GCore(jstr)

    def test_SetLmcDownload(self, tango_device):
        """Test for SetLMCDownload"""
        tango_device.Connect(True)
        expected = {
            "Mode": "1G",
            "PayloadLength": 4,
            "DstIP": "10.0.1.23",
            "SrcPort": 0xF0D0,
            "DstPort": 4660,
            "LmcMac": None,
        }
        dict = {"Mode": "1G", "PayloadLength": 4, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetLmcDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"PayloadLength": 4, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.SetLmcDownload(jstr)

    def test_SetChanneliserTruncation(self, tango_device):
        """Test for SetChanneliserTruncation"""
        tango_device.Connect(True)
        trunc = [
            [0, 1, 2, 3, 4, 5],
            [6, 7, 8, 9, 10, 11],
            [12, 13, 14, 15, 16, 17],
            [18, 19, 20, 21, 22, 23],
        ]
        arr = np.array(trunc).ravel()
        n = len(trunc)
        m = len(arr) // n
        argin = np.concatenate([np.array((n, m)), arr])
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetChanneliserTruncation(argin)
        out = ss.getvalue().strip()
        result = []
        for x in out[1:-1].split(" "):
            if x != "":
                result.append(int(x))
        assert (result == arr).all()
        argin = [2, 2]
        with pytest.raises(DevFailed):
            tango_device.SetChanneliserTruncation(argin)

    def test_SetBeamFormerRegions(self, tango_device):
        """Test for SetBeamFormerRegions"""
        tango_device.Connect(True)
        regions = [[5, 16, 1], [25, 32, 2], [45, 48, 3]]
        input = list(itertools.chain.from_iterable(regions))
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetBeamformerRegions(input)
        out = ss.getvalue().strip()
        result = [int(x) for x in out[1:-1].split(",")]
        assert input == result
        input = [3, 8]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [i for i in range(49)]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [5, 15, 1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [5, 16, -1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48, 8]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)
        input = [5, 160, 1, 25, 160, 2, 45, 72, 3]
        with pytest.raises(DevFailed):
            tango_device.SetBeamformerRegions(input)

    def test_ConfigureStationBeamformer(self, tango_device):
        """Test for ConfigureStationBeamformer"""
        tango_device.Connect(True)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ConfigureStationBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == dict
        dict = {"NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.ConfigureStationBeamformer(jstr)

    def test_LoadCalibrationCoefficients(self, tango_device):
        """Test for LoadCalibrationCoefficients"""
        tango_device.Connect(True)
        antenna = 2
        complex_coeffs = [
            [complex(3.4, 1.2), complex(2.3, 4.1), complex(4.6, 8.2), complex(6.8, 2.4)]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coeffs))
        out = [[v.real, v.imag] for v in inp]
        coeffs = list(itertools.chain.from_iterable(out))
        coeffs.insert(0, float(antenna))
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.LoadCalibrationCoefficients(coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == coeffs
        with pytest.raises(DevFailed):
            tango_device.LoadCalibrationCoefficients(coeffs[0:8])
        with pytest.raises(DevFailed):
            tango_device.LoadCalibrationCoefficients(coeffs[0:16])

    def test_LoadBeamAngle(self, tango_device):
        """Test for LoadBeamAngle"""
        tango_device.Connect(True)
        angle_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.LoadBeamAngle(angle_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == angle_coeffs

    def test_LoadAntennaTapering(self, tango_device):
        """Test for LoadAntennaTapering"""
        tango_device.Connect(True)
        tapering_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.LoadAntennaTapering(tapering_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == tapering_coeffs
        with pytest.raises(DevFailed):
            tango_device.LoadAntennaTapering(tapering_coeffs[:12])

    def test_SwitchCalibrationBank(self, tango_device):
        """Test for SwitchCalibrationBank"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SwitchCalibrationBank(19)
        result = ss.getvalue().strip()
        assert result == "19"

    def test_SetPointingDelay(self, tango_device):
        """Test for SetPointingDelay"""
        delays = [3]
        for i in range(32):
            delays.append(float(i))
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetPointingDelay(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays
        with pytest.raises(DevFailed):
            tango_device.SetPointingDelay(delays[:32])
        delays[0] = 8
        with pytest.raises(DevFailed):
            tango_device.SetPointingDelay(delays)

    def test_LoadPointingDelay(self, tango_device):
        """Test for LoadPointingDelay"""
        tango_device.Connect(True)
        delay = 11
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.LoadPointingDelay(delay)
        result = ss.getvalue().strip()
        assert int(result) == delay

    def test_StartBeamformer(self, tango_device):
        """Test for StartBeamformer"""
        tango_device.Connect(True)
        expected = {"StartTime": 0, "Duration": 5}
        dict = {"Duration": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.StartBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopBeamformer(self, tango_device):
        """Test for StopBeamformer"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.StopBeamformer()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_beamformer"

    def test_ConfigureIntegratedChannelData(self, tango_device):
        """Test for ConfigureIntegratedChannelData"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ConfigureIntegratedChannelData(6.284)
        result = ss.getvalue().strip()
        assert result == "6.284"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ConfigureIntegratedChannelData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_ConfigureIntegratedBeamData(self, tango_device):
        """Test for ConfigureIntegratedBeamData"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ConfigureIntegratedBeamData(3.142)
        result = ss.getvalue().strip()
        assert result == "3.142"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ConfigureIntegratedBeamData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_SendRawData(self, tango_device):
        """Test for SendRawData"""
        tango_device.Connect(True)
        expected = {
            "Sync": True,
            "Period": 5,
            "Timeout": 0,
            "Timestamp": None,
            "Seconds": 6.7,
        }
        dict = {"Sync": True, "Period": 5, "Seconds": 6.7}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendRawData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedData(self, tango_device):
        """Test for SendChannelisedData"""
        tango_device.Connect(True)
        expected = {
            "NSamples": 4,
            "FirstChannel": 7,
            "LastChannel": 234,
            "Period": 5,
            "Timeout": 0,
            "Timestamp": None,
            "Seconds": 0.2,
        }
        dict = {"NSamples": 4, "FirstChannel": 7, "LastChannel": 234, "Period": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendChannelisedData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataContinuous(self, tango_device):
        """Test for SendChannelisedDataContinuous"""
        tango_device.Connect(True)
        expected = {
            "ChannelID": 2,
            "NSamples": 4,
            "WaitSeconds": 3.5,
            "Timeout": 0,
            "Timestamp": None,
            "Seconds": 0.2,
        }
        dict = {"ChannelID": 2, "NSamples": 4, "WaitSeconds": 3.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendChannelisedDataContinuous(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"NSamples": 4, "WaitSeconds": 3.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.SendChannelisedDataContinuous(jstr)

    def test_SendBeamData(self, tango_device):
        """Test for SendBeamData"""
        tango_device.Connect(True)
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendBeamData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopDataTransmission(self, tango_device):
        """Test for StopDataTransmission"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.StopDataTransmission()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_data_transmission"

    def test_ComputeCalibrationCoefficients(self, tango_device):
        """Test for ComputeCalibrationCoefficients"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.ComputeCalibrationCoefficients()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: compute_calibration_coefficients"

    def test_StartAcquisition(self, tango_device):
        """ Test for StartAcquisition"""
        tango_device.Connect(True)
        expected = {"StartTime": 5, "Delay": 2}
        dict = {"StartTime": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.StartAcquisition(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SetTimeDelays(self, tango_device):
        """Test for SetTimeDelays"""
        delays = []
        for i in range(32):
            delays.append(float(i))
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetTimeDelays(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays

    def test_SetCspRounding(self, tango_device):
        """ Test for SetCspRounding"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetCspRounding(6.284)
        result = ss.getvalue().strip()
        assert result == "6.284"

    def test_SetLmcIntegratedDownload(self, tango_device):
        """ Test for SetLmcIntegratedDownload """
        tango_device.Connect(True)
        expected = {
            "Mode": "1G",
            "ChannelPayloadLength": 4,
            "BeamPayloadLength": 6,
            "DstIP": "10.0.1.23",
            "SrcPort": 0xF0D0,
            "DstPort": 4660,
            "LmcMac": None,
        }
        dict = {
            "Mode": "1G",
            "ChannelPayloadLength": 4,
            "BeamPayloadLength": 6,
            "DstIP": "10.0.1.23",
        }
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SetLmcIntegratedDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"ChannelPayloadLength": 4, "BeamPayloadLength": 6, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.SetLmcIntegratedDownload(jstr)

    def test_SendRawDataSynchronised(self, tango_device):
        """ Test for SendRawDataSynchronised """
        tango_device.Connect(True)
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendRawDataSynchronised(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataNarrowband(self, tango_device):
        """ Test for SendChannelisedDataNarrowband"""
        tango_device.Connect(True)
        expected = {
            "Frequency": 4000,
            "RoundBits": 256,
            "NSamples": 48,
            "WaitSeconds": 10,
            "Timeout": 0,
            "Timestamp": None,
            "Seconds": 0.5,
        }
        dict = {
            "Frequency": 4000,
            "RoundBits": 256,
            "NSamples": 48,
            "WaitSeconds": 10,
            "Seconds": 0.5,
        }
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SendChannelisedDataNarrowband(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"RoundBits": 256, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.SendChannelisedDataNarrowband(jstr)
        dict = {"Frequency": 4000, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.SendChannelisedDataNarrowband(jstr)

    def test_TweakTransceivers(self, tango_device):
        """ Test for TweakTransceivers"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.TweakTransceivers()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: tweak_transceivers"

    def test_PostSynchronisation(self, tango_device):
        """ Test for PostSynchronisation"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.PostSynchronisation()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: post_synchronisation"

    def test_SyncFpgas(self, tango_device):
        """ Test for SyncFpgas"""
        tango_device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.SyncFpgas()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: sync_fpgas"

    def test_CalculateDelay(self, tango_device):
        """ Test for CalculateDelay"""
        tango_device.Connect(True)
        dict = expected = {
            "CurrentDelay": 5.0,
            "CurrentTC": 2,
            "RefLo": 3.0,
            "RefHi": 78.0,
        }
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_device.CalculateDelay(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"CurrentTC": 2, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.CalculateDelay(jstr)
        dict = expected = {"CurrentDelay": 5.0, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefLo": 3.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_device.CalculateDelay(jstr)
