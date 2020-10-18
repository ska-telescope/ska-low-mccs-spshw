#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsTile.
"""

import logging
import itertools
import json
import threading

import pytest
from tango import AttrQuality, DevFailed, EventType

from ska.base import DeviceStateModel
from ska.base.control_model import HealthState, SimulationMode
from ska.base.commands import ResultCode
from ska.low.mccs.hardware import SimulableHardwareFactory
from ska.low.mccs.tile import MccsTile
from ska.low.mccs.tile_hardware import TileHardwareManager
from ska.low.mccs.tpm_simulator import TpmSimulator


device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "tile_0001",
}


class TestMccsTile(object):
    """
    Test class for MccsTile tests.

    The Tile device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS Tile
    device server methods.
    """

    # def test_postinit(self, device_under_test):
    #     # check that initialisation leaves us in a state where turning
    #     # the device on doesn't put it into ALARM state
    #     device_under_test.On()
    #     assert device_under_test.state() == DevState.ON
    #     time.sleep(1.1)
    #     assert device_under_test.state() == DevState.ON

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
        mock_callback = mocker.Mock()
        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

    def test_logicalTileId(self, device_under_test):
        """
        Test for the logicalTpmId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalTileId == 0
        device_under_test.logicalTileId = 7
        assert device_under_test.logicalTileId == 7

    def test_subarrayId(self, device_under_test):
        """
        Test for the subarrayId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.subarrayId == 0
        device_under_test.subarrayId = 3
        assert device_under_test.subarrayId == 3

    def test_stationId(self, device_under_test):
        """
        Test for the stationId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.stationId == 0
        device_under_test.stationId = 5
        assert device_under_test.stationId == 5

    def test_cspDestinationIp(self, device_under_test):
        """
        Test for the cspDestinationIp attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.cspDestinationIp == ""
        device_under_test.cspDestinationIp = "10.0.23.56"
        assert device_under_test.cspDestinationIp == "10.0.23.56"

    def test_cspDestinationMac(self, device_under_test):
        """
        Test for the cspDestinationMac attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.cspDestinationMac == ""
        device_under_test.cspDestinationMac = "10:fe:fa:06:0b:99"
        assert device_under_test.cspDestinationMac == "10:fe:fa:06:0b:99"

    def test_cspDestinationPort(self, device_under_test):
        """
        Test for the cspDestinationPort attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.cspDestinationPort == 0
        device_under_test.cspDestinationPort = 4567
        assert device_under_test.cspDestinationPort == 4567

    def test_voltage(self, device_under_test):
        """
        Test for the voltage attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.voltage == TpmSimulator.VOLTAGE

    def test_current(self, device_under_test):
        """
        Test for the current attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        device_under_test.current == TpmSimulator.CURRENT

    def test_board_temperature(self, device_under_test):
        """
        Test for the board_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.board_temperature == TpmSimulator.BOARD_TEMPERATURE

    def test_fpga1_temperature(self, device_under_test):
        """
        Test for the fpga1_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.fpga1_temperature == TpmSimulator.FPGA1_TEMPERATURE

    def test_fpga2_temperature(self, device_under_test):
        """
        Test for the fpga2_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.fpga2_temperature == TpmSimulator.FPGA2_TEMPERATURE

    def test_fpga1_time(self, device_under_test):
        """
        Test for the fpga1_time attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.fpga1_time == TpmSimulator.FPGA1_TIME

    def test_fpga2_time(self, device_under_test):
        """
        Test for the fpga2_time attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.fpga2_time == TpmSimulator.FPGA2_TIME

    def test_antennaIds(self, device_under_test):
        """
        Test for the antennaIds attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert tuple(device_under_test.antennaIds) == tuple()
        new_ids = tuple(range(8))
        device_under_test.antennaIds = new_ids
        assert tuple(device_under_test.antennaIds) == new_ids

    def test_adcPower(self, device_under_test):
        """
        Test for the adcPowerattribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        expected = tuple(float(i) for i in range(32))
        assert device_under_test.adcPower == pytest.approx(expected)

    def test_currentTileBeamformerFrame(self, device_under_test):
        """
        Test for the currentTileBeamformerFrame attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert (
            device_under_test.currentTileBeamformerFrame
            == TpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME
        )

    def test_phaseTerminalCount(self, device_under_test):
        """
        Test for the phaseTerminalCount attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.PhaseTerminalCount == TpmSimulator.PHASE_TERMINAL_COUNT
        device_under_test.PhaseTerminalCount = 45
        assert device_under_test.PhaseTerminalCount == 45

    def test_ppsDelay(self, device_under_test):
        """
        Test for the ppsDelay attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.ppsDelay == 12


class TestMccsTileCommands:
    """
    Tests of MccsTile device commands
    """

    @pytest.mark.parametrize(
        ("device_command", "arg"),
        (
            (
                "SetLmcDownload",
                json.dumps({"Mode": "1G", "PayloadLength": 4, "DstIP": "10.0.1.23"}),
            ),
            ("SetBeamFormerRegions", (1, 8, 5)),
            (
                "ConfigureStationBeamformer",
                json.dumps(
                    {"StartChannel": 2, "NumTiles": 4, "IsFirst": True, "IsLast": False}
                ),
            ),
            ("LoadBeamAngle", tuple(float(i) for i in range(16))),
            ("LoadAntennaTapering", tuple(float(i) for i in range(16))),
            ("SetPointingDelay", [3] * 33),
            ("ConfigureIntegratedChannelData", 6.284),
            ("ConfigureIntegratedBeamData", 3.142),
            ("SendRawData", json.dumps({"Sync": True, "Period": 5, "Seconds": 6.7})),
            (
                "SendChannelisedData",
                json.dumps(
                    {"NSamples": 4, "FirstChannel": 7, "LastChannel": 234, "Period": 5}
                ),
            ),
            (
                "SendChannelisedDataContinuous",
                json.dumps({"ChannelID": 2, "NSamples": 4, "WaitSeconds": 3.5}),
            ),
            ("SendBeamData", json.dumps({"Period": 10, "Timeout": 4, "Seconds": 0.5})),
            ("StartAcquisition", json.dumps({"StartTime": 5})),
            ("CheckPendingDataRequests", None),
            ("SetTimeDelays", tuple(float(i) for i in range(32))),
            (
                "SetLmcIntegratedDownload",
                json.dumps(
                    {
                        "Mode": "1G",
                        "ChannelPayloadLength": 4,
                        "BeamPayloadLength": 6,
                        "DstIP": "10.0.1.23",
                    }
                ),
            ),
            (
                "SendRawDataSynchronised",
                json.dumps({"Period": 10, "Timeout": 4, "Seconds": 0.5}),
            ),
            (
                "SendChannelisedDataNarrowband",
                json.dumps(
                    {
                        "Frequency": 4000,
                        "RoundBits": 256,
                        "NSamples": 48,
                        "WaitSeconds": 10,
                        "Seconds": 0.5,
                    }
                ),
            ),
            (
                "CalculateDelay",
                json.dumps(
                    {"CurrentDelay": 5.0, "CurrentTC": 2, "RefLo": 3.0, "RefHi": 78.0}
                ),
            ),
        ),
    )
    def test_command_not_implemeented(self, device_under_test, device_command, arg):
        """
        A very weak test for commands that are not implemented yet.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_command: the name of the device command under test
        :type device_command: str
        :param arg: argument to the command (optional)
        :type arg: any
        """
        device_under_test.On()

        args = [] if arg is None else [arg]
        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = getattr(device_under_test, device_command)(*args)

    @pytest.mark.parametrize(
        ("device_command", "arg", "tpm_command"),
        (
            ("Initialise", None, "initialise"),
            ("ProgramCPLD", "test_bitload_cpld", "cpld_flash_write"),
            ("SwitchCalibrationBank", 19, "switch_calibration_bank"),
            ("LoadPointingDelay", 0.5, "load_pointing_delay"),
            ("StopDataTransmission", None, "stop_data_transmission"),
            (
                "ComputeCalibrationCoefficients",
                None,
                "compute_calibration_coefficients",
            ),
            ("SetCspRounding", 6.284, "set_csp_rounding"),
            ("TweakTransceivers", None, "tweak_transceivers"),
            ("PostSynchronisation", None, "post_synchronisation"),
            ("SyncFpgas", None, "sync_fpgas"),
        ),
    )
    def test_command_passthrough(
        self, device_under_test, mocker, device_command, arg, tpm_command
    ):
        """
        Test of commands that return OK and have a simple pass-through
        implementation, such that calling the command on the device
        causes a corresponding command to be called on the TPM
        simulator.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param device_command: the name of the device command under test
        :type device_command: str
        :param arg: argument to the command (optional)
        :type arg: any
        :param tpm_command: the name of the tpm command that is expected
            to be called as a result of the device command being called
        :type tpm_command: str
        """
        device_under_test.On()

        # First test that the calling the command on the device results
        # in a NotImplementedError
        args = [] if arg is None else [arg]
        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = getattr(device_under_test, device_command)(*args)

        # Now check that calling the command object results in the
        # correct TPM simulator command being called.
        logger = logging.getLogger()
        state_model = DeviceStateModel(logger)

        mock_tpm_simulator = mocker.Mock()
        hardware_factory = SimulableHardwareFactory(True, _simulator=mock_tpm_simulator)
        hardware_manager = TileHardwareManager(
            SimulationMode.TRUE, logger, _factory=hardware_factory
        )

        command_class = getattr(MccsTile, f"{device_command}Command")
        command_object = command_class(hardware_manager, state_model, logger)

        # doesn't raise NotImplementedError because the tpm simulator is
        # mocked out
        command_object(*args)
        assert getattr(mock_tpm_simulator, tpm_command).called_once_with(*args)

    def test_On(self, device_under_test):
        """Test for On

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_GetFirmwareAvailable(self, device_under_test):
        """
        Test for
        * GetFirmwareAvailable command
        * firmwareName attribute
        * firmwareVersion attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        firmware_available_str = device_under_test.GetFirmwareAvailable()
        firmware_available = json.loads(firmware_available_str)
        assert firmware_available == TpmSimulator.FIRMWARE_AVAILABLE

        firmware_name = device_under_test.firmwareName
        assert firmware_name == TpmSimulator.FIRMWARE_NAME

        major = firmware_available[firmware_name]["major"]
        minor = firmware_available[firmware_name]["minor"]
        assert device_under_test.firmwareVersion == f"{major}.{minor}"

    def test_DownloadFirmware(self, device_under_test):
        """
        Test for DownloadFirmware.
        Also functions as the test for the isProgrammed property

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        assert not device_under_test.isProgrammed
        bitfile = "test_bitload_firmware"
        device_under_test.DownloadFirmware(bitfile)
        assert device_under_test.isProgrammed

    def test_GetRegisterList(self, device_under_test):
        """
        Test for GetRegisterList

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        assert device_under_test.GetRegisterList() == list(
            TpmSimulator.REGISTER_MAP[0].keys()
        )

    def test_ReadRegister(self, device_under_test):
        """
        Test for ReadRegister

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        num_values = 4
        arg = {
            "RegisterName": "test-reg1",
            "NbRead": num_values,
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)
        values = device_under_test.ReadRegister(json_arg)
        assert (values == [0 for i in range(num_values)]).all()

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed, match=f"{exclude_key} is a mandatory parameter"
            ):
                _ = device_under_test.ReadRegister(bad_json_arg)

    def test_WriteRegister(self, device_under_test):
        """
        Test for WriteRegister

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        arg = {
            "RegisterName": "test-reg1",
            "Values": [0, 1, 2, 3],
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)

        [[result_code], [message]] = device_under_test.WriteRegister(json_arg)
        assert result_code == ResultCode.OK
        assert message == "WriteRegister command completed OK"

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed, match=f"{exclude_key} is a mandatory parameter"
            ):
                _ = device_under_test.WriteRegister(bad_json_arg)

    def test_ReadAddress(self, device_under_test):
        """
        Test for ReadAddress

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        address = 0xF
        nvalues = 10
        expected = (0,) * nvalues
        assert tuple(device_under_test.ReadAddress([address, nvalues])) == expected

        with pytest.raises(DevFailed):
            _ = device_under_test.ReadAddress([address])

    def WriteAddress(self, device_under_test):
        """
        Test for WriteAddress

        This is a very weak test but the
        :py:class:`~ska.low.mccs.tile_hardware.TileHardwareManager`'s
        :py:meth:`~ska.low.mccs.tile_hardware.TileHardwareManager.write_address`
        method is well tested.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        [[result_code], [message]] = device_under_test.WriteAddress([20, 1, 2, 3])
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_Configure40GCore(self, device_under_test):
        """
        Test for
        * Configure40GCore command
        * fortyGDestinationIps attribute
        * fortyGDestinationMacs attribute
        * fortyGDestinationPorts attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()

        config_1 = {
            "CoreID": 1,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstMac": "10:fe:ed:08:0b:59",
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        device_under_test.Configure40GCore(json.dumps(config_1))
        config_2 = {
            "CoreID": 2,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4001,
            "DstMac": "10:fe:ed:08:0b:57",
            "DstIP": "10.0.98.4",
            "DstPort": 5001,
        }
        device_under_test.Configure40GCore(json.dumps(config_2))

        assert tuple(device_under_test.fortyGbDestinationIps) == (
            "10.0.98.3",
            "10.0.98.4",
        )
        assert tuple(device_under_test.fortyGbDestinationMacs) == (
            "10:fe:ed:08:0b:59",
            "10:fe:ed:08:0b:57",
        )
        assert tuple(device_under_test.fortyGbDestinationPorts) == (5000, 5001)

        result_str = device_under_test.Get40GCoreConfiguration(1)
        result = json.loads(result_str)
        assert result == config_1.pop("CoreID")

        with pytest.raises(DevFailed, match="Invalid core id specified"):
            _ = device_under_test.Get40GCoreConfiguration(3)

    @pytest.mark.parametrize("channels", (2, 3))
    @pytest.mark.parametrize("frequencies", (1, 2, 3))
    def test_SetChanneliserTruncation(self, device_under_test, channels, frequencies):
        """
        Test for SetChanneliserTruncation

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param channels: number of channels to set
        :type channels: int
        :param frequencies: number of frequencies to set
        """
        device_under_test.On()

        array = [channels] + [frequencies] + [1.0] * (channels * frequencies)

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = device_under_test.SetChanneliserTruncation(array)
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = device_under_test.SetChanneliserTruncation(array[:-1])
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = device_under_test.SetChanneliserTruncation(array + [1.0])

    def test_LoadCalibrationCoefficients(self, device_under_test):
        """
        Test for LoadCalibrationCoefficients

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.On()
        antenna = 2
        complex_coeffs = [
            [complex(3.4, 1.2), complex(2.3, 4.1), complex(4.6, 8.2), complex(6.8, 2.4)]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coeffs))
        out = [[v.real, v.imag] for v in inp]
        coeffs = [antenna] + list(itertools.chain.from_iterable(out))

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = device_under_test.LoadCalibrationCoefficients(coeffs)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCoefficients(coeffs[0:8])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCoefficients(coeffs[0:16])

    @pytest.mark.parametrize("start_time", (None, 0))
    @pytest.mark.parametrize("duration", (None, -1))
    def test_start_and_stop_beamformer(self, device_under_test, start_time, duration):
        """
        Test for
        * StartBeamformer command
        * StopBeamformer command
        * isBeamformerRunning attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param start_time: time to state the beamformer
        :type start_time: int or None
        :param duration: duration of time that the beamformer should run
        :type duration: int or None
        """
        device_under_test.On()
        assert not device_under_test.isBeamformerRunning
        args = {"StartTime": start_time, "Duration": duration}
        device_under_test.StartBeamformer(json.dumps(args))
        assert device_under_test.isBeamformerRunning
        device_under_test.StopBeamformer()
        assert not device_under_test.isBeamformerRunning


class TestMccsTile_InitCommand:
    """
    Contains the tests of :py:class:`~ska.low.mccs.MccsTile`'s
    :py:class:`~ska.low.mccs.MccsTile.InitCommand`.
    """

    class HangableInitCommand(MccsTile.InitCommand):
        """
        A subclass of InitCommand with the following properties that
        support testing:

        * A lock that, if acquired prior to calling the command, causes
          the command to hang until the lock is released
        * Call trace attributes that record which methods were called
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new HangableInitCommand instance

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_hardware_management_called = False
            self._initialise_health_monitoring_called = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device (overwridden here to inject a call trace
            attribute).

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            self._initialise_hardware_management_called = True
            super()._initialise_hardware_management(device)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device (overridden
            here to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device)

    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        mock_device = mocker.MagicMock()
        mock_state_model = mocker.Mock()

        init_command = self.HangableInitCommand(mock_device, mock_state_model)

        with init_command._hang_lock:
            init_command()
            # we got the hang lock first, so the initialisation thread
            # will hang in health initialisation until we release it
            init_command.interrupt()

        init_command._thread.join()

        # now that we've released the hang lock, the thread can exit
        # its _initialise_hardware_management, but before it enters its
        # _initialise_health_monitoring, it will detect that it has been
        # interrupted, and return
        assert init_command._initialise_hardware_management_called
        assert not init_command._initialise_health_monitoring_called
