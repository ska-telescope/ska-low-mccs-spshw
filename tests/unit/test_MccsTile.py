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
"""
This module contains the tests for MccsTile.
"""

import io
import json
import time
import pytest
import itertools
import numpy as np
from contextlib import redirect_stdout
from tango import DevSource
from tango import DevFailed

from ska.base.control_model import TestMode
from ska.base.commands import ResultCode

device_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "tile1",
}


@pytest.mark.mock_device_proxy
class TestMccsTile(object):
    """
    Test class for MccsTile tests.

    The Tile device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS Tile
    device server methods.
    """

    def test_tileId(self, device_under_test):
        """
        Test for the tileId attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.tileID == 1
        device_under_test.tileID = 9
        assert device_under_test.tileID == 9

    def test_logicalTileId(self, device_under_test):
        """
        Test for the logicalTpmId attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.logicalTileId == 0
        device_under_test.logicalTileId = 7
        assert device_under_test.logicalTileId == 7

    def test_subarrayId(self, device_under_test):
        """
        Test for the subarrayId attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.subarrayId == 0
        device_under_test.subarrayId = 3
        assert device_under_test.subarrayId == 3

    def test_stationId(self, device_under_test):
        """
        Test for the stationId attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.stationId == 0
        device_under_test.stationId = 5
        assert device_under_test.stationId == 5

    def test_ipAddress(self, device_under_test):
        """
        Test for the ipAddress attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.ipAddress == "0.0.0.0"
        device_under_test.ipAddress = "10.0.23.99"
        assert device_under_test.ipAddress == "10.0.23.99"

    def test_lmcIp(self, device_under_test):
        """
        Test for the lmcIp attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.lmcIp == "0.0.0.0"
        device_under_test.lmcIp = "10.0.23.50"
        assert device_under_test.lmcIp == "10.0.23.50"

    def test_lmcPort(self, device_under_test):
        """
        Test for the lmcPort attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.lmcPort == 30000
        device_under_test.lmcPort = 40000
        assert device_under_test.lmcPort == 40000

    def test_cspDestinationIp(self, device_under_test):
        """
        Test for the cspDestinationIp attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.cspDestinationIp == ""
        device_under_test.cspDestinationIp = "10.0.23.56"
        assert device_under_test.cspDestinationIp == "10.0.23.56"

    def test_cspDestinationMac(self, device_under_test):
        """
        Test for the cspDestinationMac attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.cspDestinationMac == ""
        device_under_test.cspDestinationMac = "10:fe:fa:06:0b:99"
        assert device_under_test.cspDestinationMac == "10:fe:fa:06:0b:99"

    def test_cspDestinationPort(self, device_under_test):
        """
        Test for the cspDestinationPort attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.cspDestinationPort == 0
        device_under_test.cspDestinationPort = 4567
        assert device_under_test.cspDestinationPort == 4567

    def test_firmwareName(self, device_under_test):
        """
        Test for the firmwareName attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.firmwareName == ""
        device_under_test.firmwareName = "test_firmware"
        assert device_under_test.firmwareName == "test_firmware"

    def test_firmwareVersion(self, device_under_test):
        """
        Test for the firmwareVersion attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert device_under_test.firmwareVersion == ""
        device_under_test.firmwareVersion = "01-beta"
        assert device_under_test.firmwareVersion == "01-beta"

    @pytest.mark.mock_device_proxy
    def test_voltage(self, device_under_test):
        """
        Test for the voltage attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        device_under_test.set_source(DevSource.DEV)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.voltage == 4.7

    @pytest.mark.mock_device_proxy
    def test_current(self, device_under_test):
        """
        Test for the current attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        device_under_test.set_source(DevSource.DEV)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        device_under_test.current == 0.4

    def test_isProgrammed(self, device_under_test):
        """
        Test for the isProgrammed attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.Connect(True)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.isProgrammed is True

    @pytest.mark.mock_device_proxy
    def test_board_temperature(self, device_under_test):
        """
        Test for the board_temperature attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        device_under_test.set_source(DevSource.DEV)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.board_temperature == 36.0

    @pytest.mark.mock_device_proxy
    def test_fpga1_temperature(self, device_under_test):
        """
        Test for the fpga1_temperature attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        device_under_test.set_source(DevSource.DEV)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.fpga1_temperature == 38.0

    @pytest.mark.mock_device_proxy
    def test_fpga2_temperature(self, device_under_test):
        """
        Test for the fpga2_temperature attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        device_under_test.set_source(DevSource.DEV)
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.fpga2_temperature == 37.5

    def test_fpga1_time(self, device_under_test):
        """
        Test for the fpga1_time attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.fpga1_time == 0
        sec = int(time.time())
        device_under_test.fpga1_time = sec
        assert device_under_test.fpga1_time == sec

    def test_fpga2_time(self, device_under_test):
        """
        Test for the fpga2_time attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.fpga2_time == 0
        device_under_test.fpga2_time = 1535
        assert device_under_test.fpga2_time == 1535

    def test_antennaIds(self, device_under_test):
        """
        Test for the antennaIds attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        assert (device_under_test.AntennaIds == []).all()
        new_ids = [i for i in range(8)]
        device_under_test.AntennaIds = new_ids
        assert (device_under_test.AntennaIds == new_ids).all()

    def test_fortyGbDestinationIps(self, device_under_test):
        """
        Test for the fortyGbDestinationIps attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
        device_under_test.Configure40GCore(jstr)
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
        device_under_test.Configure40GCore(jstr)
        assert device_under_test.fortyGbDestinationIps == ("10.0.98.3", "10.0.98.4")

    def test_fortyGbDestinationMacs(self, device_under_test):
        """
        Test for the fortyGbDestinationMacs attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
        device_under_test.Configure40GCore(jstr)
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
        device_under_test.Configure40GCore(jstr)
        assert device_under_test.fortyGbDestinationMacs == (
            "10:fe:ed:08:0b:59",
            "10:fe:ed:08:0b:57",
        )

    def test_fortyGbDestinationPorts(self, device_under_test):
        """
        Test for the fortyGbDestinationPorts attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
        device_under_test.Configure40GCore(jstr)
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
        device_under_test.Configure40GCore(jstr)
        assert (device_under_test.fortyGbDestinationPorts == (5000, 5001)).all()

    def test_adcPower(self, device_under_test):
        """
        Test for the adcPowerattribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        device_under_test.testMode = TestMode.TEST
        [[result_code], [message]] = device_under_test.Connect(False)
        assert result_code == ResultCode.OK
        expected = [float(i) for i in range(32)]
        assert (device_under_test.adcPower == expected).all()

    def test_currentTileBeamformerFrame(self, device_under_test):
        """
        Test for the currentTileBeamformerFrame attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.CurrentTileBeamformerFrame == 23

    def test_checkPendingDataRequests(self, device_under_test):
        """
        Test for the checkPendingDataRequests attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.CheckPendingDataRequests is False

    def test_isBeamformerRunning(self, device_under_test):
        """
        Test for the isBeamformerRunning attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.isBeamformerRunning is False
        device_under_test.StartBeamformer("{}")
        assert device_under_test.isBeamformerRunning is True

    def test_phaseTerminalCount(self, device_under_test):
        """
        Test for the phaseTerminalCount attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.PhaseTerminalCount == 0
        device_under_test.PhaseTerminalCount = 45
        assert device_under_test.PhaseTerminalCount == 45

    def test_ppsDelay(self, device_under_test):
        """
        Test for the ppsDelay attribute.

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.ppsDelay == 12

    # ------------------------------------------------------
    # Commands.
    # Tests for commands by calling the method by assertion.
    # ------------------------------------------------------

    def test_Initialise(self, device_under_test):
        """
        Test for Initialise

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(False)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.Initialise()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: initialise"

    def test_On(self, device_under_test):
        """Test for On

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_Connect(self, device_under_test):
        """
        Test for Connect

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        ss = io.StringIO()
        with redirect_stdout(ss):
            [[result_code], [message]] = device_under_test.Connect(False)
            assert result_code == ResultCode.OK
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: connect"

    def test_Disconnect(self, device_under_test):
        """
        Test for Disconnect from the board

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(False)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.disconnect()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: disconnect"

    def test_GetFirmwareList(self, device_under_test):
        """
        Test for GetFirmwareList

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        firmware_str = device_under_test.GetFirmwareList()
        firmware_list = json.loads(firmware_str)
        assert firmware_list == {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
        }

    def test_DownloadFirmware(self, device_under_test):
        """
        Test for DownloadFirmware

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(False)
        assert result_code == ResultCode.OK
        bitfile = "test_bitload_firmware"
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.DownloadFirmware(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_ProgramCPLD(self, device_under_test):
        """
        Test for ProgramCPLD

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        bitfile = "test_bitload_cpld"
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ProgramCPLD(bitfile)
        result = ss.getvalue().strip()
        assert result == bitfile

    def test_WaitPPSEvent(self, device_under_test):
        """
        Test for WaitPPSEvent

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        device_under_test.fpga1_time = int(time.time())
        (result, info) = device_under_test.WaitPPSEvent()
        assert result == ResultCode.OK

    def test_GetRegisterList(self, device_under_test):
        """
        Test for GetRegisterList

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        assert device_under_test.GetRegisterList() == [
            "test-reg1",
            "test-reg2",
            "test-reg3",
            "test-reg4",
        ]

    def test_ReadAndWriteRegister(self, device_under_test):
        """
        Test for ReadRegister & WriteRegister

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
        values = device_under_test.ReadRegister(jstr)
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
        device_under_test.WriteRegister(jstr)
        jstr = json.dumps(dict)
        values = device_under_test.ReadRegister(jstr)
        assert (values == [0, 0, 1, 2]).all()
        dict2 = dict.copy()
        dict2.pop("RegisterName")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            device_under_test.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("NbRead")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            device_under_test.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Offset")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            device_under_test.ReadRegister(jstr)
        dict2 = dict.copy()
        dict2.pop("Device")
        jstr = json.dumps(dict2)
        with pytest.raises(DevFailed):
            device_under_test.ReadRegister(jstr)
        device = 1
        dict = {
            "RegisterName": "test-reg1",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = device_under_test.ReadRegister(jstr)
        assert (values == [0 for i in range(nb_read)]).all()
        dict = {
            "RegisterName": "test-reg5",
            "NbRead": nb_read,
            "Offset": offset,
            "Device": device,
        }
        jstr = json.dumps(dict)
        values = device_under_test.ReadRegister(jstr)
        assert len(values) == 0

        dict3 = dict1.copy()
        dict3.pop("RegisterName")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            device_under_test.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Values")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            device_under_test.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Offset")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            device_under_test.WriteRegister(jstr)
        dict3 = dict1.copy()
        dict3.pop("Device")
        jstr = json.dumps(dict3)
        with pytest.raises(DevFailed):
            device_under_test.WriteRegister(jstr)

    def test_ReadAndWriteAddress(self, device_under_test):
        """
        Test for ReadAddress and WriteAddress

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        address = 0xF
        nvalues = 10
        expected = [0 for i in range(nvalues)]
        assert (device_under_test.ReadAddress([address, nvalues]) == expected).all()
        values = [val for val in range(nvalues)]
        values.insert(0, address)
        device_under_test.WriteAddress(values)
        assert (device_under_test.ReadAddress([address, nvalues]) == values[1:]).all()
        with pytest.raises(DevFailed):
            device_under_test.ReadAddress([address])
        with pytest.raises(DevFailed):
            device_under_test.WriteAddress([address])

    def test_Configure40GCore(self, device_under_test):
        """
        Test for Configure40GCore

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
        device_under_test.Configure40GCore(jstr)
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
        device_under_test.Configure40GCore(jstr)
        output = device_under_test.Get40GCoreConfiguration(1)
        result = json.loads(output)
        assert result == dict1.pop("CoreID")
        with pytest.raises(DevFailed):
            output = device_under_test.Get40GCoreConfiguration(3)

        dict = dict2.copy()
        dict.pop("CoreID")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("SrcPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstMac")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstIP")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)
        dict = dict2.copy()
        dict.pop("DstPort")
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.Configure40GCore(jstr)

    def test_SetLmcDownload(self, device_under_test):
        """
        Test for SetLMCDownload

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SetLmcDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"PayloadLength": 4, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.SetLmcDownload(jstr)

    def test_SetChanneliserTruncation(self, device_under_test):
        """
        Test for SetChanneliserTruncation

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SetChanneliserTruncation(argin)
        out = ss.getvalue().strip()
        result = []
        for x in out[1:-1].split(" "):
            if x != "":
                result.append(int(x))
        assert (result == arr).all()
        argin = [2, 2]
        with pytest.raises(DevFailed):
            device_under_test.SetChanneliserTruncation(argin)

    def test_SetBeamFormerRegions(self, device_under_test):
        """
        Test for SetBeamFormerRegions

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        regions = [[5, 16, 1], [25, 32, 2], [45, 48, 3]]
        input = list(itertools.chain.from_iterable(regions))
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SetBeamformerRegions(input)
        out = ss.getvalue().strip()
        result = [int(x) for x in out[1:-1].split(",")]
        assert input == result
        input = [3, 8]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [i for i in range(49)]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [5, 15, 1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [5, 16, -1, 25, 32, 2, 45, 48, 3]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [5, 16, 1, 25, 32, 2, 45, 48, 8]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)
        input = [5, 160, 1, 25, 160, 2, 45, 72, 3]
        with pytest.raises(DevFailed):
            device_under_test.SetBeamformerRegions(input)

    def test_ConfigureStationBeamformer(self, device_under_test):
        """
        Test for ConfigureStationBeamformer

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ConfigureStationBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == dict
        dict = {"NumTiles": 4, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "IsFirst": True, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsLast": False}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.ConfigureStationBeamformer(jstr)
        dict = {"StartChannel": 2, "NumTiles": 4, "IsFirst": True}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.ConfigureStationBeamformer(jstr)

    def test_LoadCalibrationCoefficients(self, device_under_test):
        """
        Test for LoadCalibrationCoefficients

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.LoadCalibrationCoefficients(coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == coeffs
        with pytest.raises(DevFailed):
            device_under_test.LoadCalibrationCoefficients(coeffs[0:8])
        with pytest.raises(DevFailed):
            device_under_test.LoadCalibrationCoefficients(coeffs[0:16])

    def test_LoadBeamAngle(self, device_under_test):
        """
        Test for LoadBeamAngle

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        angle_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.LoadBeamAngle(angle_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == angle_coeffs

    def test_LoadAntennaTapering(self, device_under_test):
        """
        Test for LoadAntennaTapering

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        tapering_coeffs = [float(i) for i in range(16)]
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.LoadAntennaTapering(tapering_coeffs)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == tapering_coeffs
        with pytest.raises(DevFailed):
            device_under_test.LoadAntennaTapering(tapering_coeffs[:12])

    def test_SwitchCalibrationBank(self, device_under_test):
        """
        Test for SwitchCalibrationBank

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SwitchCalibrationBank(19)
        result = ss.getvalue().strip()
        assert result == "19"

    def test_SetPointingDelay(self, device_under_test):
        """
        Test for SetPointingDelay

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        delays = [3]
        for i in range(32):
            delays.append(float(i))
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SetPointingDelay(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays
        with pytest.raises(DevFailed):
            device_under_test.SetPointingDelay(delays[:32])
        delays[0] = 8
        with pytest.raises(DevFailed):
            device_under_test.SetPointingDelay(delays)

    def test_LoadPointingDelay(self, device_under_test):
        """
        Test for LoadPointingDelay

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        delay = 11
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.LoadPointingDelay(delay)
        result = ss.getvalue().strip()
        assert int(result) == delay

    def test_StartBeamformer(self, device_under_test):
        """
        Test for StartBeamformer

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        expected = {"StartTime": 0, "Duration": 5}
        dict = {"Duration": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.StartBeamformer(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopBeamformer(self, device_under_test):
        """
        Test for StopBeamformer

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.StopBeamformer()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_beamformer"

    def test_ConfigureIntegratedChannelData(self, device_under_test):
        """
        Test for ConfigureIntegratedChannelData

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ConfigureIntegratedChannelData(6.284)
        result = ss.getvalue().strip()
        assert result == "6.284"
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ConfigureIntegratedChannelData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_ConfigureIntegratedBeamData(self, device_under_test):
        """
        Test for ConfigureIntegratedBeamData

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ConfigureIntegratedBeamData(3.142)
        result = ss.getvalue().strip()
        assert result == "3.142"
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ConfigureIntegratedBeamData(0.0)
        result = ss.getvalue().strip()
        assert result == "0.5"

    def test_SendRawData(self, device_under_test):
        """
        Test for SendRawData

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SendRawData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedData(self, device_under_test):
        """
        Test for SendChannelisedData

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SendChannelisedData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataContinuous(self, device_under_test):
        """
        Test for SendChannelisedDataContinuous

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SendChannelisedDataContinuous(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"NSamples": 4, "WaitSeconds": 3.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.SendChannelisedDataContinuous(jstr)

    def test_SendBeamData(self, device_under_test):
        """
        Test for SendBeamData

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SendBeamData(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_StopDataTransmission(self, device_under_test):
        """
        Test for StopDataTransmission

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.StopDataTransmission()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: stop_data_transmission"

    def test_ComputeCalibrationCoefficients(self, device_under_test):
        """
        Test for ComputeCalibrationCoefficients

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.ComputeCalibrationCoefficients()
        result = ss.getvalue().strip()
        assert result == "TpmSimulator: compute_calibration_coefficients"

    def test_StartAcquisition(self, device_under_test):
        """
        Test for StartAcquisition

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        expected = {"StartTime": 5, "Delay": 2}
        dict = {"StartTime": 5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.StartAcquisition(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SetTimeDelays(self, device_under_test):
        """
        Test for SetTimeDelays

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        delays = []
        for i in range(32):
            delays.append(float(i))
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SetTimeDelays(delays)
        out = ss.getvalue().strip()
        result = [float(x) for x in out[1:-1].split(",")]
        assert result == delays

    def test_SetCspRounding(self, device_under_test):
        """
        Test for SetCspRounding

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        [[result_code], [message]] = device_under_test.SetCspRounding(6.284)
        assert result_code == ResultCode.OK
        assert message == "SetCspRounding command succeeded"

    def test_SetLmcIntegratedDownload(self, device_under_test):
        """
        Test for SetLmcIntegratedDownload

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SetLmcIntegratedDownload(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"ChannelPayloadLength": 4, "BeamPayloadLength": 6, "DstIP": "10.0.1.23"}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.SetLmcIntegratedDownload(jstr)

    def test_SendRawDataSynchronised(self, device_under_test):
        """
        Test for SendRawDataSynchronised

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        expected = {"Period": 10, "Timeout": 4, "Timestamp": None, "Seconds": 0.5}
        dict = {"Period": 10, "Timeout": 4, "Seconds": 0.5}
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.SendRawDataSynchronised(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected

    def test_SendChannelisedDataNarrowband(self, device_under_test):
        """
        Test for SendChannelisedDataNarrowband

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
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
            device_under_test.SendChannelisedDataNarrowband(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"RoundBits": 256, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.SendChannelisedDataNarrowband(jstr)
        dict = {"Frequency": 4000, "NSamples": 48, "WaitSeconds": 10, "Seconds": 0.5}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.SendChannelisedDataNarrowband(jstr)

    def test_TweakTransceivers(self, device_under_test):
        """
        Test for TweakTransceivers

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        [[result_code], [message]] = device_under_test.TweakTransceivers()
        assert result_code == ResultCode.OK
        assert message == "TweakTransceivers command succeeded"

    def test_PostSynchronisation(self, device_under_test):
        """
        Test for PostSynchronisation

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        [[result_code], [message]] = device_under_test.PostSynchronisation()
        assert result_code == ResultCode.OK
        assert message == "PostSynchronisation command succeeded"

    def test_SyncFpgas(self, device_under_test):
        """
        Test for SyncFpgas

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(False)
        assert result_code == ResultCode.OK
        [[result_code], [message]] = device_under_test.SyncFpgas()
        assert result_code == ResultCode.OK
        assert message == "SyncFpgas command succeeded"

    def test_CalculateDelay(self, device_under_test):
        """
        Test for CalculateDelay

        :param device_under_test: a DeviceProxy under a DeviceTestContext
        :type device_under_test: DeviceProxy
        """
        [[result_code], [message]] = device_under_test.Connect(True)
        assert result_code == ResultCode.OK
        dict = expected = {
            "CurrentDelay": 5.0,
            "CurrentTC": 2,
            "RefLo": 3.0,
            "RefHi": 78.0,
        }
        jstr = json.dumps(dict)
        ss = io.StringIO()
        with redirect_stdout(ss):
            device_under_test.CalculateDelay(jstr)
        result = json.loads(ss.getvalue())
        assert result == expected
        dict = {"CurrentTC": 2, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.CalculateDelay(jstr)
        dict = expected = {"CurrentDelay": 5.0, "RefLo": 3.0, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefHi": 78.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.CalculateDelay(jstr)
        dict = {"CurrentDelay": 5.0, "CurrentTC": 2, "RefLo": 3.0}
        jstr = json.dumps(dict)
        with pytest.raises(DevFailed):
            device_under_test.CalculateDelay(jstr)
