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


# Device test case
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsTile(object):
    """
    The Tile Device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS Tile
    device server methods.
    """

    def test_State(self, tango_context):
        """Test for State"""
        assert tango_context.device.state() == DevState.OFF
        tango_context.device.Connect(True)
        assert tango_context.device.state() == DevState.ON

    def test_tileId(self, tango_context):
        """Test for the tileId attribute."""
        assert tango_context.device.tileID == -1
        tango_context.device.tileID = 9
        assert tango_context.device.tileID == 9

    def test_logicalTpmId(self, tango_context):
        """Test for the logicalTpmId attribute."""
        assert tango_context.device.logicalTpmId == -1
        tango_context.device.logicalTpmId = 7
        assert tango_context.device.logicalTpmId == 7

    def test_subarrayId(self, tango_context):
        """Test for the subarrayId attribute."""
        assert tango_context.device.subarrayId == -1
        tango_context.device.subarrayId = 3
        assert tango_context.device.subarrayId == 3

    def test_stationId(self, tango_context):
        """Test for the stationId attribute."""
        assert tango_context.device.stationId == -1
        tango_context.device.stationId = 5
        assert tango_context.device.stationId == 5

    def test_ipAddress(self, tango_context):
        """Test for the ipAddress attribute."""
        assert tango_context.device.ipAddress == "0.0.0.0"
        tango_context.device.ipAddress = "10.0.23.99"
        assert tango_context.device.ipAddress == "10.0.23.99"

    def test_lmcIp(self, tango_context):
        """Test for the lmcIp attribute"""
        assert tango_context.device.lmcIp == "0.0.0.0"
        tango_context.device.lmcIp = "10.0.23.50"
        assert tango_context.device.lmcIp == "10.0.23.50"

    def test_lmcPort(self, tango_context):
        """Test for the lmcPort attribute"""
        assert tango_context.device.lmcPort == 30000
        tango_context.device.lmcPort = 40000
        assert tango_context.device.lmcPort == 40000

    def test_cspDestinationIp(self, tango_context):
        """Test for the cspDestinationIp attribute."""
        assert tango_context.device.cspDestinationIp == ""
        tango_context.device.cspDestinationIp = "10.0.23.56"
        assert tango_context.device.cspDestinationIp == "10.0.23.56"

    def test_cspDestinationMac(self, tango_context):
        """Test for the cspDestinationMac attribute."""
        assert tango_context.device.cspDestinationMac == ""
        tango_context.device.cspDestinationMac = "10:fe:fa:06:0b:99"
        assert tango_context.device.cspDestinationMac == "10:fe:fa:06:0b:99"

    def test_cspDestinationPort(self, tango_context):
        """Test for the cspDestinationPort attribute."""
        assert tango_context.device.cspDestinationPort == 0
        tango_context.device.cspDestinationPort = 4567
        assert tango_context.device.cspDestinationPort == 4567

    def test_firmwareName(self, tango_context):
        """Test for the firmwareName attribute."""
        assert tango_context.device.firmwareName == ""
        tango_context.device.firmwareName = "test_firmware"
        assert tango_context.device.firmwareName == "test_firmware"

    def test_firmwareVersion(self, tango_context):
        """Test for the firmwareVersion attribute."""
        assert tango_context.device.firmwareVersion == ""
        tango_context.device.firmwareVersion = "01-beta"
        assert tango_context.device.firmwareVersion == "01-beta"

    def test_voltage(self, tango_context):
        """Test for the voltage attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.voltage == 10.5

    def test_current(self, tango_context):
        """Test for the current attribute."""
        tango_context.device.Connect(True)
        tango_context.device.current == 0.4

    def test_isProgrammed(self, tango_context):
        """Test for isProgrammed"""
        tango_context.device.Connect(True)
        assert tango_context.device.isProgrammed is True

    def test_board_temperature(self, tango_context):
        """Test for the board_temperature attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.board_temperature == 40.0

    def test_fpga1_temperature(self, tango_context):
        """Test for the fpga1_temperature attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.fpga1_temperature == 38.0

    def test_fpga2_temperature(self, tango_context):
        """Test for the fpga2_temperature attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.fpga2_temperature == 37.5

    def test_fpga1_time(self, tango_context):
        """Test for the fpga1_time attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.fpga1_time == 0
        sec = int(time.time())
        tango_context.device.fpga1_time = sec
        assert tango_context.device.fpga1_time == sec

    def test_fpga2_time(self, tango_context):
        """Test the fpga2_time attribute."""
        tango_context.device.Connect(True)
        assert tango_context.device.fpga2_time == 0
        tango_context.device.fpga2_time = 1535
        assert tango_context.device.fpga2_time == 1535

    def test_antennaIds(self, tango_context):
        """Test for the antennaIds attribute."""
        assert (tango_context.device.AntennaIds == []).all()
        new_ids = [i for i in range(8)]
        tango_context.device.AntennaIds = new_ids
        assert (tango_context.device.AntennaIds == new_ids).all()

    def test_fortyGbDestinationIps(self, tango_context):
        """Test for fortyGbDestinationIps"""
        tango_context.device.Connect(True)
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
        tango_context.device.Configure40GCore(jstr)
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
        tango_context.device.Configure40GCore(jstr)
        assert tango_context.device.fortyGbDestinationIps == ("10.0.98.3", "10.0.98.4")

    def test_fortyGbDestinationMacs(self, tango_context):
        """Test for fortyGbDestinationMacs"""
        tango_context.device.Connect(True)
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
        tango_context.device.Configure40GCore(jstr)
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
        tango_context.device.Configure40GCore(jstr)
        assert tango_context.device.fortyGbDestinationMacs == (
            "10:fe:ed:08:0b:59",
            "10:fe:ed:08:0b:57",
        )

    def test_fortyGbDestinationPorts(self, tango_context):
        """Test for fortyGbDestinationPorts"""
        tango_context.device.Connect(True)
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
        tango_context.device.Configure40GCore(jstr)
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
        tango_context.device.Configure40GCore(jstr)
        assert (tango_context.device.fortyGbDestinationPorts == (5000, 5001)).all()

    def test_adcPower(self, tango_context):
        """ Test if board is not programmed, return None"""
        tango_context.device.Connect(True)
        expected = [float(i) for i in range(32)]
        assert (tango_context.device.adcPower == expected).all()

    def test_currentTileBeamformerFrame(self, tango_context):
        tango_context.device.Connect(True)
        assert tango_context.device.CurrentTileBeamformerFrame == 23

    def test_checkPendingDataRequests(self, tango_context):
        tango_context.device.Connect(True)
        assert tango_context.device.CheckPendingDataRequests is False

    def test_isBeamformerRunning(self, tango_context):
        tango_context.device.Connect(True)
        assert tango_context.device.isBeamformerRunning is False
        tango_context.device.StartBeamformer("{}")
        assert tango_context.device.isBeamformerRunning is True

    def test_phaseTerminalCount(self, tango_context):
        tango_context.device.Connect(True)
        assert tango_context.device.PhaseTerminalCount == 0
        tango_context.device.PhaseTerminalCount = 45
        assert tango_context.device.PhaseTerminalCount == 45

    def test_ppsDelay(self, tango_context):
        tango_context.device.Connect(True)
        assert tango_context.device.ppsDelay == 12

    # ------------------------------------------------------
    # Commands.
    # Tests for commands by calling the method by assertion.
    # ------------------------------------------------------

    def test_Initialise(self, tango_context):
        """Test for Initialise"""
        tango_context.device.Connect(False)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.Initialise()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: initialise"

    def test_Connect(self, tango_context):
        """Test for Connect"""
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.Connect(False)
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: connect"

    def test_Disconnect(self, tango_context):
        """ Test for Disconnect from the board"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.disconnect()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: disconnect"

    def test_GetFirmwareList(self, tango_context):
        """ Test for GetFirmwareList """
        tango_context.device.Connect(True)
        firmware_str = tango_context.device.GetFirmwareList()
        firmware_list = json.loads(firmware_str)
        assert firmware_list == {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
        }

    def test_DownloadFirmware(self, tango_context):
        """Test for DownloadFirmware"""
        tango_context.device.Connect(False)
        bitfile = "test_bitload_firmware"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.DownloadFirmware(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_ProgramCPLD(self, tango_context):
        """Test for ProgramCPLD"""
        tango_context.device.Connect(True)
        bitfile = "test_bitload_cpld"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ProgramCPLD(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_WaitPPSEvent(self, tango_context):
        """Test for WaitPPSEvent"""
        tango_context.device.Connect(True)
        tango_context.device.fpga1_time = int(time.time())
        assert tango_context.device.WaitPPSEvent() is None

    def test_GetRegisterList(self, tango_context):
        """Test for GetRegisterList"""
        tango_context.device.Connect(True)
        assert tango_context.device.GetRegisterList() == [
            "test-reg1",
            "test-reg2",
            "test-reg3",
            "test-reg4",
        ]

    def test_ReadAndWriteRegister(self, tango_context):
        """Test for ReadRegister & WriteRegister"""
        tango_context.device.Connect(True)
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
        values = tango_context.device.ReadRegister(jstr)
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
        tango_context.device.WriteRegister(jstr)
        jstr = json.dumps(dict)
        values = tango_context.device.ReadRegister(jstr)
        assert (values == [0, 0, 1, 2]).all()
        dict2 = dict.copy()
        dict2.pop("RegisterName")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_context.device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("NbRead")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_context.device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Offset")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_context.device.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Device")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            tango_context.device.ReadRegister(jstr)
        device = 1
        dict = {
            "RegisterName": "test-reg1",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = tango_context.device.ReadRegister(jstr)
        assert (values == [0 for i in range(nb_read)]).all()
        dict = {
            "RegisterName": "test-reg5",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = tango_context.device.ReadRegister(jstr)
        assert len(values) == 0

        dict3 = dict1.copy()
        dict3.pop("RegisterName")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_context.device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Values")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_context.device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Offset")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_context.device.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Device")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            tango_context.device.WriteRegister(jstr)

    def test_ReadAndWriteAddress(self, tango_context):
        """Test for ReadAddress and WriteAddress"""
        tango_context.device.Connect(True)
        address = 0xf
        nvalues = 10
        expected = [0 for i in range(nvalues)]
        assert (tango_context.device.ReadAddress([address, nvalues]) == expected).all()
        values = [val for val in range(nvalues)]
        values.insert(0, address)
        tango_context.device.WriteAddress(values)
        assert (
            tango_context.device.ReadAddress([address, nvalues]) == values[1:]
        ).all()
        with pytest.raises(DevFailed):
            tango_context.device.ReadAddress([address])
        with pytest.raises(DevFailed):
            tango_context.device.WriteAddress([address])

    def test_Configure40GCore(self, tango_context):
        """Test for Configure40GCore"""
        tango_context.device.Connect(True)
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
        tango_context.device.Configure40GCore(jstr)
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
        tango_context.device.Configure40GCore(jstr)
        output = tango_context.device.Get40GCoreConfiguration(1)
        result = json.loads(output)
        assert result == dict1.pop("CoreID")
        with pytest.raises(DevFailed):
            output = tango_context.device.Get40GCoreConfiguration(3)

        dict = dict2.copy()
        dict.pop("CoreID")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.Configure40GCore(jstr)

    def test_SetLmcDownload(self, tango_context):
        """Test for SetLMCDownload"""
        tango_context.device.Connect(True)
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
            tango_context.device.SetLmcDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"PayloadLength": 4, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.SetLmcDownload(jstr)

    def test_SetChanneliserTruncation(self, tango_context):
        """Test for SetChanneliserTruncation"""
        tango_context.device.Connect(True)
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
            tango_context.device.SetChanneliserTruncation(argin)
        out = ss.getvalue().strip()
        result = []
        for x in out[1:-1].split(" "):
            if x != "":
                result.append(int(x))
        assert (result == arr).all()
        argin = [2, 2]
        with pytest.raises(DevFailed):
            tango_context.device.SetChanneliserTruncation(argin)

    def test_SetBeamFormerRegions(self, tango_context):
        """Test for SetBeamFormerRegions"""
        tango_context.device.Connect(True)
        regions = [[5, 16, 1], [25, 32, 2], [45, 48, 3]]
        input = list(itertools.chain.from_iterable(regions))
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SetBeamformerRegions(input)
        out = ss.getvalue().strip()
        result = [int(x) for x in out[1:-1].split(",")]
        assert input == result
        input = [3, 8]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [i for i in range(49)]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [5, 15, 1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [5, 16, -1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48, 8]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)
        input = [5, 160, 1, 25, 160, 2, 45, 72, 3]
        with pytest.raises(DevFailed):
            tango_context.device.SetBeamformerRegions(input)

    def test_ConfigureStationBeamformer(self, tango_context):
        """Test for ConfigureStationBeamformer"""
        tango_context.device.Connect(True)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ConfigureStationBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == dict
        dict = {"NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.ConfigureStationBeamformer(jstr)

    def test_LoadCalibrationCoefficients(self, tango_context):
        """Test for LoadCalibrationCoefficients"""
        tango_context.device.Connect(True)
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
            tango_context.device.LoadCalibrationCoefficients(coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == coeffs
        with pytest.raises(DevFailed):
            tango_context.device.LoadCalibrationCoefficients(coeffs[0:8])
        with pytest.raises(DevFailed):
            tango_context.device.LoadCalibrationCoefficients(coeffs[0:16])

    def test_LoadBeamAngle(self, tango_context):
        """Test for LoadBeamAngle"""
        tango_context.device.Connect(True)
        angle_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.LoadBeamAngle(angle_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == angle_coeffs

    def test_LoadAntennaTapering(self, tango_context):
        """Test for LoadAntennaTapering"""
        tango_context.device.Connect(True)
        tapering_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.LoadAntennaTapering(tapering_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == tapering_coeffs
        with pytest.raises(DevFailed):
            tango_context.device.LoadAntennaTapering(tapering_coeffs[:12])

    def test_SwitchCalibrationBank(self, tango_context):
        """Test for SwitchCalibrationBank"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SwitchCalibrationBank(19)
        result = ss.getvalue().strip()
        assert result == "19"

    def test_SetPointingDelay(self, tango_context):
        """Test for SetPointingDelay"""
        delays = [3]
        for i in range(32):
            delays.append(float(i))
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SetPointingDelay(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays
        with pytest.raises(DevFailed):
            tango_context.device.SetPointingDelay(delays[:32])
        delays[0] = 8
        with pytest.raises(DevFailed):
            tango_context.device.SetPointingDelay(delays)

    def test_LoadPointingDelay(self, tango_context):
        """Test for LoadPointingDelay"""
        tango_context.device.Connect(True)
        delay = 11
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.LoadPointingDelay(delay)
        result = ss.getvalue().strip()
        assert int(result) == delay

    def test_StartBeamformer(self, tango_context):
        """Test for StartBeamformer"""
        tango_context.device.Connect(True)
        expected = {"StartTime": 0, "Duration": 5}
        dict = {"Duration": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.StartBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopBeamformer(self, tango_context):
        """Test for StopBeamformer"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.StopBeamformer()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_beamformer"

    def test_ConfigureIntegratedChannelData(self, tango_context):
        """Test for ConfigureIntegratedChannelData"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ConfigureIntegratedChannelData(6.284)
        result = ss.getvalue().strip()
        assert result == "6.284"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ConfigureIntegratedChannelData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_ConfigureIntegratedBeamData(self, tango_context):
        """Test for ConfigureIntegratedBeamData"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ConfigureIntegratedBeamData(3.142)
        result = ss.getvalue().strip()
        assert result == "3.142"
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ConfigureIntegratedBeamData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_SendRawData(self, tango_context):
        """Test for SendRawData"""
        tango_context.device.Connect(True)
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
            tango_context.device.SendRawData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedData(self, tango_context):
        """Test for SendChannelisedData"""
        tango_context.device.Connect(True)
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
            tango_context.device.SendChannelisedData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataContinuous(self, tango_context):
        """Test for SendChannelisedDataContinuous"""
        tango_context.device.Connect(True)
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
            tango_context.device.SendChannelisedDataContinuous(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"NSamples": 4, "WaitSeconds": 3.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.SendChannelisedDataContinuous(jstr)

    def test_SendBeamData(self, tango_context):
        """Test for SendBeamData"""
        tango_context.device.Connect(True)
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SendBeamData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopDataTransmission(self, tango_context):
        """Test for StopDataTransmission"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.StopDataTransmission()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_data_transmission"

    def test_ComputeCalibrationCoefficients(self, tango_context):
        """Test for ComputeCalibrationCoefficients"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.ComputeCalibrationCoefficients()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: compute_calibration_coefficients"

    def test_StartAcquisition(self, tango_context):
        """ Test for StartAcquisition"""
        tango_context.device.Connect(True)
        expected = {"StartTime": 5, "Delay": 2}
        dict = {"StartTime": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.StartAcquisition(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SetTimeDelays(self, tango_context):
        """Test for SetTimeDelays"""
        delays = []
        for i in range(32):
            delays.append(float(i))
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SetTimeDelays(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays

    def test_SetCspRounding(self, tango_context):
        """ Test for SetCspRounding"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SetCspRounding(6.284)
        result = ss.getvalue().strip()
        assert result == "6.284"

    def test_SetLmcIntegratedDownload(self, tango_context):
        """ Test for SetLmcIntegratedDownload """
        tango_context.device.Connect(True)
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
            tango_context.device.SetLmcIntegratedDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"ChannelPayloadLength": 4, "BeamPayloadLength": 6, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.SetLmcIntegratedDownload(jstr)

    def test_SendRawDataSynchronised(self, tango_context):
        """ Test for SendRawDataSynchronised """
        tango_context.device.Connect(True)
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SendRawDataSynchronised(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataNarrowband(self, tango_context):
        """ Test for SendChannelisedDataNarrowband"""
        tango_context.device.Connect(True)
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
            tango_context.device.SendChannelisedDataNarrowband(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"RoundBits": 256, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.SendChannelisedDataNarrowband(jstr)
        dict = {"Frequency": 4000, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.SendChannelisedDataNarrowband(jstr)

    def test_TweakTransceivers(self, tango_context):
        """ Test for TweakTransceivers"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.TweakTransceivers()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: tweak_transceivers"

    def test_PostSynchronisation(self, tango_context):
        """ Test for PostSynchronisation"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.PostSynchronisation()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: post_synchronisation"

    def test_SyncFpgas(self, tango_context):
        """ Test for SyncFpgas"""
        tango_context.device.Connect(True)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.SyncFpgas()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: sync_fpgas"

    def test_CalculateDelay(self, tango_context):
        """ Test for CalculateDelay"""
        tango_context.device.Connect(True)
        dict = expected = {
            "CurrentDelay": 5.0,
            "CurrentTC": 2,
            "RefLo": 3.0,
            "RefHi": 78.0,
        }
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            tango_context.device.CalculateDelay(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"CurrentTC": 2, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.CalculateDelay(jstr)
        dict = expected = {"CurrentDelay": 5.0, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefLo": 3.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            tango_context.device.CalculateDelay(jstr)
