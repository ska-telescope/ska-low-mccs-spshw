# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsTile."""
from __future__ import annotations

import itertools
import json
import time
import unittest
from typing import Any, Optional

import pytest
from ska_control_model import AdminMode, HealthState, ResultCode, TestMode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness
from tango import DevFailed, DevState

from ska_low_mccs import MccsTile
from ska_low_mccs.tile import StaticTpmSimulator


@pytest.fixture()
def device_to_load(
    patched_tile_device_class: type[MccsTile],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_tile_device_class: a device class for the tile device
        under test, patched with extra methods for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "tile_0001",
        "patch": patched_tile_device_class,
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def tile_device(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the tile device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the tile device under test
    """
    return tango_harness.get_device("low-mccs/tile/0001")


class TestMccsTile:
    """
    Test class for MccsTile tests.

    The Tile device represents the TANGO interface to a Tile (TPM) unit.
    """

    def test_healthState(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        mock_tile_component_manager: unittest.mock.Mock,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        :param mock_tile_component_manager: A mock component manager.
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert tile_device.healthState == HealthState.UNKNOWN

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        mock_tile_component_manager.component_state_changed_callback(
            {"health_state": HealthState.OK}
        )
        device_health_state_changed_callback.assert_next_change_event(HealthState.OK)
        assert tile_device.healthState == HealthState.OK

    @pytest.mark.parametrize(
        ("attribute", "initial_value", "write_value"),
        [
            ("logicalTileId", 0, 7),
            ("stationId", 0, 5),
            ("voltage", 4.7, None),
            ("boardTemperature", StaticTpmSimulator.BOARD_TEMPERATURE, None),
            ("current", StaticTpmSimulator.CURRENT, None),
            ("fpga1Temperature", StaticTpmSimulator.FPGA1_TEMPERATURE, None),
            ("fpga2Temperature", StaticTpmSimulator.FPGA2_TEMPERATURE, None),
            ("fpgasUnixTime", pytest.approx(StaticTpmSimulator.FPGAS_TIME), None),
            (
                "currentTileBeamformerFrame",
                StaticTpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
                None,
            ),
            (
                "phaseTerminalCount",
                StaticTpmSimulator.PHASE_TERMINAL_COUNT,
                45,
            ),
            (
                "adcPower",
                pytest.approx(tuple(float(i) for i in range(32))),
                None,
            ),
            ("ppsDelay", 12, None),
        ],
    )
    def test_component_attribute(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_state_changed_callback: MockChangeEventCallback,
        attribute: str,
        initial_value: Any,
        write_value: Any,
    ) -> None:
        """
        Test device attributes that map through to the component.

        Thus require the component to be connected and turned on before
        a read / write can be effected.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param attribute: name of the attribute under test
        :param initial_value: expected initial value of the attribute
        :param write_value: value to be written as part of the test.
        """
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = getattr(tile_device, attribute)

        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_last_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
        time.sleep(0.1)
        device_state_changed_callback.assert_next_change_event(DevState.OFF)

        tile_device.MockTpmOn()
        time.sleep(0.1)
        device_state_changed_callback.assert_last_change_event(DevState.ON)

        assert getattr(tile_device, attribute) == initial_value

        if write_value is not None:
            tile_device.write_attribute(attribute, write_value)
            assert getattr(tile_device, attribute) == write_value

    def test_cspDestinationIp(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for the cspDestinationIp attribute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert tile_device.cspDestinationIp == ""
        tile_device.cspDestinationIp = "10.0.23.56"
        assert tile_device.cspDestinationIp == "10.0.23.56"

    def test_cspDestinationMac(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for the cspDestinationMac attribute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert tile_device.cspDestinationMac == ""
        tile_device.cspDestinationMac = "10:fe:fa:06:0b:99"
        assert tile_device.cspDestinationMac == "10:fe:fa:06:0b:99"

    def test_cspDestinationPort(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for the cspDestinationPort attribute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert tile_device.cspDestinationPort == 0
        tile_device.cspDestinationPort = 4567
        assert tile_device.cspDestinationPort == 4567

    def test_antennaIds(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for the antennaIds attribute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert tuple(tile_device.antennaIds) == tuple()
        new_ids = tuple(range(8))
        tile_device.antennaIds = new_ids
        assert tuple(tile_device.antennaIds) == new_ids


class TestMccsTileCommands:
    """Tests of MccsTile device commands."""

    @pytest.mark.parametrize(
        ("device_command", "arg"),
        [
            (
                "SetLmcDownload",
                json.dumps({"Mode": "1G", "PayloadLength": 4, "DstIP": "10.0.1.23"}),
            ),
            ("SetBeamFormerRegions", (2, 8, 5, 0, 0, 1, 1, 101)),
            (
                "ConfigureStationBeamformer",
                json.dumps(
                    {
                        "StartChannel": 2,
                        "NumTiles": 4,
                        "IsFirst": True,
                        "IsLast": False,
                    }
                ),
            ),
            ("LoadBeamAngle", tuple(float(i) for i in range(16))),
            ("LoadAntennaTapering", tuple(float(i) for i in range(17))),
            ("SetPointingDelay", [3] * 5),  # 2 * antennas_per_tile + 1
            (
                "ConfigureIntegratedChannelData",
                json.dumps(
                    {
                        "Integration Time": 6.284,
                        "First channel": 0,
                        "Last Channel": 511,
                    }
                ),
            ),
            (
                "ConfigureIntegratedBeamData",
                json.dumps(
                    {
                        "Integration Time": 3.142,
                        "First channel": 0,
                        "Last Channel": 191,
                    }
                ),
            ),
            ("SendRawData", json.dumps({"Sync": True, "Seconds": 6.7})),
            (
                "SendChannelisedData",
                json.dumps({"NSamples": 4, "FirstChannel": 7, "LastChannel": 234}),
            ),
            (
                "SendChannelisedDataContinuous",
                json.dumps({"ChannelID": 2, "NSamples": 4, "WaitSeconds": 3.5}),
            ),
            ("SendBeamData", json.dumps({"Seconds": 0.5})),
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
                json.dumps({"Seconds": 0.5}),
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
                    {
                        "CurrentDelay": 5.0,
                        "CurrentTC": 2,
                        "RefLo": 3.0,
                        "RefHi": 78.0,
                    }
                ),
            ),
            (
                "ConfigureTestGenerator",
                json.dumps(
                    {
                        "ToneFrequency": 150e6,
                        "ToneAmplitude": 0.1,
                        "NoiseAmplitude": 0.9,
                        "PulseFrequency": 7,
                        "SetTime": 0,
                    }
                ),
            ),
            ("SwitchCalibrationBank", 19),
            ("LoadPointingDelay", 1),
            ("StopDataTransmission", None),
            ("StopIntegratedData", None),
            ("ComputeCalibrationCoefficients", None),
            ("SetCspRounding", 6.284),
            ("TweakTransceivers", None),
        ],
    )
    def test_command_not_implemented(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_command: str,
        arg: Any,
    ) -> None:
        """
        A very weak test for commands that are not implemented yet.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_command: the name of the device command under test
        :param arg: argument to the command (optional)
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        args = [] if arg is None else [arg]
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = getattr(tile_device, device_command)(*args)

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        tile_device.MockTpmOff()
        time.sleep(0.1)

        tile_device.MockTpmOn()
        time.sleep(0.1)

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = getattr(tile_device, device_command)(*args)

    def test_StartAcquisition(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_state_changed_callback: MockChangeEventCallback,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for StartAcquisition.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        """
        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
        time.sleep(0.2)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.StartAcquisition(json.dumps({"StartTime": 5}))

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)

        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.StartAcquisition(
            json.dumps({"StartTime": 5})
        )
        assert result_code == ResultCode.QUEUED
        assert "StartAcquisition" in message.split("_")[-1]

    def test_ProgramCPLD(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_state_changed_callback: MockChangeEventCallback,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PostSynchronisation.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        """
        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
        time.sleep(0.2)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.ProgramCPLD("test_bitload_cpld")

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)

        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.ProgramCPLD("test_bitload_cpld")
        assert result_code == ResultCode.QUEUED
        assert "ProgramCPLD" in message.split("_")[-1]

    def test_PostSynchronisation(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_state_changed_callback: MockChangeEventCallback,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PostSynchronisation.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        """
        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
        time.sleep(0.2)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.PostSynchronisation()

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)

        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.PostSynchronisation()
        assert result_code == ResultCode.QUEUED
        assert "PostSynchronisation" in message.split("_")[-1]

    def test_SyncFpgas(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_state_changed_callback: MockChangeEventCallback,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PostSynchronisation.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        """
        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE
        time.sleep(0.2)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.SyncFpgas()

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)

        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.SyncFpgas()
        assert result_code == ResultCode.QUEUED
        assert "SyncFpgas" in message.split("_")[-1]

    # def test_On(
    #     self: TestMccsTileCommands,
    #     tile_device: MccsDeviceProxy,
    #     device_state_changed_callback: MockChangeEventCallback,
    #     device_admin_mode_changed_callback: MockChangeEventCallback,
    #     mock_subrack_device_proxy: MccsDeviceProxy,
    #     subrack_tpm_id: int,
    # ) -> None:
    #     """
    #     Test for On.

    #     :param tile_device: fixture that provides a
    #         :py:class:`tango.DeviceProxy` to the device under test, in a
    #         :py:class:`tango.test_context.DeviceTestContext`.
    #     :param device_admin_mode_changed_callback: a callback that
    #         we can use to subscribe to admin mode changes on the tile
    #         device
    #     :param mock_subrack_device_proxy: a proxy to this subrack device
    #         for the subrack of the TPM under test.
    #     :param subrack_tpm_id: the position of the TPM in its subrack
    #     """
    #     tile_device.add_change_event_callback(
    #         "adminMode",
    #         device_admin_mode_changed_callback,
    #     )
    #     tile_device.add_change_event_callback(
    #         "state",
    #         device_state_changed_callback,
    #     )
    #     device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
    #     assert tile_device.adminMode == AdminMode.OFFLINE

    #     # device_state_changed_callback.assert_last_change_event(DevState.DISABLE)
    #     # assert tile_device.state() == DevState.DISABLE
    #     with pytest.raises(
    #         DevFailed,
    #         match="Command On not allowed when the device is in DISABLE state",
    #     ):
    #         _ = tile_device.On()

    #     tile_device.adminMode = AdminMode.ONLINE
    #     device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
    #     assert tile_device.adminMode == AdminMode.ONLINE

    #     time.sleep(0.2)
    #     tile_device.MockTpmOff()
    #     time.sleep(0.2)

    #     tile_device.MockTpmOn()
    #     time.sleep(0.2)

    #     [[result_code], [message]] = tile_device.On()
    #     assert result_code == ResultCode.QUEUED
    #     assert "_OnCommand" in message.split("_")[-1]

    #     mock_subrack_device_proxy.PowerOnTpm.assert_next_call(subrack_tpm_id)
    #     # At this point the subrack should turn the TPM on, then fire a change event.
    #     # so let's fake that.
    #     tile_device.MockTpmOn()
    #     assert tile_device.state() == DevState.ON

    def test_Initialise(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for Initialise.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.Initialise()

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.Initialise()

        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.Initialise()
        assert result_code == ResultCode.QUEUED
        assert "Initialise" in message.split("_")[-1]

    def test_GetFirmwareAvailable(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test if firmware available.

        Test for:
        * GetFirmwareAvailable command
        * firmwareName attribute
        * firmwareVersion attribute

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        """
        tile_device.testMode = TestMode.TEST
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        tile_device.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_last_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        # At this point, the component should be unconnected, as not turned on
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = tile_device.GetFirmwareAvailable()

        time.sleep(0.1)
        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()
        # device_state_changed_callback.assert_last_change_event(DevState.ON)

        firmware_available_str = tile_device.GetFirmwareAvailable()
        firmware_available = json.loads(firmware_available_str)
        assert firmware_available == StaticTpmSimulator.FIRMWARE_AVAILABLE

        firmware_name = tile_device.firmwareName
        assert firmware_name == StaticTpmSimulator.FIRMWARE_NAME

        major = firmware_available[firmware_name]["major"]
        minor = firmware_available[firmware_name]["minor"]
        assert tile_device.firmwareVersion == f"{major}.{minor}"

    def test_DownloadFirmware(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for DownloadFirmware.

        Also functions as the test for the isProgrammed and
        the firmwareName properties.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        bitfile = "tests/data/Vivado_test_firmware_bitfile.bit"
        [[result_code], [message]] = tile_device.DownloadFirmware(bitfile)
        assert result_code == ResultCode.QUEUED
        assert "DownloadFirmware" in message.split("_")[-1]
        time.sleep(0.1)
        assert tile_device.isProgrammed
        assert tile_device.firmwareName == bitfile

    def test_MissingDownloadFirmwareFile(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for a missing firmware download.

        Also functions as the test for the
        isProgrammed and the firmwareName properties.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        invalid_bitfile_path = "this/folder/and/file/doesnt/exist.bit"
        existing_firmware_name = tile_device.firmwareName
        [[result_code], [message]] = tile_device.DownloadFirmware(invalid_bitfile_path)
        assert result_code == ResultCode.FAILED
        assert "DownloadFirmware" not in message.split("_")[-1]
        assert tile_device.firmwareName == existing_firmware_name

    def test_GetRegisterList(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for GetRegisterList.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        assert tile_device.GetRegisterList() == list(
            StaticTpmSimulator.REGISTER_MAP[0].keys()
        )

    def test_ReadRegister(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for ReadRegister.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        num_values = 4
        arg = {
            "RegisterName": "test-reg1",
            "NbRead": num_values,
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)
        values = tile_device.ReadRegister(json_arg)
        assert list(values) == [0] * num_values

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed,
                match=f"{exclude_key} is a mandatory parameter",
            ):
                _ = tile_device.ReadRegister(bad_json_arg)

    def test_WriteRegister(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for WriteRegister.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        arg = {
            "RegisterName": "test-reg1",
            "Values": [0, 1, 2, 3],
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)
        [[result_code], [message]] = tile_device.WriteRegister(json_arg)
        assert result_code == ResultCode.OK
        assert "WriteRegister" in message.split("_")[-1]

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed,
                match=f"{exclude_key} is a mandatory parameter",
            ):
                _ = tile_device.WriteRegister(bad_json_arg)

    def test_ReadAddress(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for ReadAddress.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        address = 0xF
        nvalues = 10
        expected = (0,) * nvalues
        assert tuple(tile_device.ReadAddress([address, nvalues])) == expected

        with pytest.raises(DevFailed):
            _ = tile_device.ReadAddress([address])

    def test_WriteAddress(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for WriteAddress.

        This is a very weak test but the
        :py:class:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager`'s
        :py:meth:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager.write_address`
        method is well tested.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        [[result_code], [message]] = tile_device.WriteAddress([20, 1, 2, 3])
        assert result_code == ResultCode.OK
        assert "WriteAddress" in message.split("_")[-1]

    def test_Configure40GCore(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for.

        * Configure40GCore command
        * fortyGBDestinationIps attribute
        * fortyGBDestinationPorts attribute

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        time.sleep(0.1)  # Just a settle time require so become ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        config_1 = {
            "CoreID": 1,
            "ArpTableEntry": 0,
            "SrcMac": "10:fe:ed:08:0a:58",
            "SrcIP": "10.0.99.3",
            "SrcPort": 4000,
            "DstIP": "10.0.98.3",
            "DstPort": 5000,
        }
        tile_device.Configure40GCore(json.dumps(config_1))

        config_2 = {
            "CoreID": 2,
            "ArpTableEntry": 1,
            "SrcMac": "10:fe:ed:08:0a:56",
            "SrcIP": "10.0.99.4",
            "SrcPort": 4001,
            "DstIP": "10.0.98.4",
            "DstPort": 5001,
        }
        tile_device.Configure40GCore(json.dumps(config_2))

        assert tuple(tile_device.fortyGbDestinationIps) == (
            "10.0.98.3",
            "10.0.98.4",
        )
        assert tuple(tile_device.fortyGbDestinationPorts) == (5000, 5001)

        arg = {
            "CoreID": 1,
            "ArpTableEntry": 0,
        }
        json_arg = json.dumps(arg)
        result_str = tile_device.Get40GCoreConfiguration(json_arg)
        result = json.loads(result_str)
        assert result["CoreID"] == config_1.pop("CoreID")

        arg = {
            "CoreID": 3,
            "ArpTableEntry": 0,
        }
        json_arg = json.dumps(arg)
        with pytest.raises(
            DevFailed, match="Invalid core id or arp table id specified"
        ):
            _ = tile_device.Get40GCoreConfiguration(json_arg)

    @pytest.mark.parametrize("channels", (2, 3))
    @pytest.mark.parametrize("frequencies", (1, 2, 3))
    def test_SetChanneliserTruncation(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        channels: int,
        frequencies: int,
    ) -> None:
        """
        Test for SetChanneliserTruncation.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param channels: number of channels to set
        :param frequencies: number of frequencies to set
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        array: list[int] = [channels] + [frequencies] + [1] * (channels * frequencies)

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = tile_device.SetChanneliserTruncation(array)
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = tile_device.SetChanneliserTruncation(array[:-1])
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = tile_device.SetChanneliserTruncation(array + [1])

    def test_LoadCalibrationCoefficients(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for LoadCalibrationCoefficients.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        antenna = float(2)
        complex_coefficients = [
            [
                complex(3.4, 1.2),
                complex(2.3, 4.1),
                complex(4.6, 8.2),
                complex(6.8, 2.4),
            ]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coefficients))
        out = [[v.real, v.imag] for v in inp]
        coefficients = [antenna] + list(itertools.chain.from_iterable(out))

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = tile_device.LoadCalibrationCoefficients(coefficients)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = tile_device.LoadCalibrationCoefficients(coefficients[0:8])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = tile_device.LoadCalibrationCoefficients(coefficients[0:16])

    def test_LoadCalibrationCurve(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for LoadCalibrationCurve.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        antenna = 2
        beam = 0
        complex_coefficients = [
            [
                complex(3.4, 1.2),
                complex(2.3, 4.1),
                complex(4.6, 8.2),
                complex(6.8, 2.4),
            ]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coefficients))
        out = [[v.real, v.imag] for v in inp]
        coefficients: list[float] = (
            [float(antenna)] + [float(beam)] + list(itertools.chain.from_iterable(out))
        )

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = tile_device.LoadCalibrationCurve(coefficients)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = tile_device.LoadCalibrationCurve(coefficients[0:9])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = tile_device.LoadCalibrationCurve(coefficients[0:17])

    @pytest.mark.parametrize("start_time", (None, 0))
    @pytest.mark.parametrize("duration", (None, -1))
    def test_start_and_stop_beamformer(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        start_time: Optional[int],
        duration: Optional[int],
    ) -> None:
        """
        Test for.

        * StartBeamformer command
        * StopBeamformer command
        * isBeamformerRunning attribute

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param start_time: time to state the beamformer
        :param duration: duration of time that the beamformer should run
        """
        tile_device.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert tile_device.adminMode == AdminMode.ONLINE

        time.sleep(0.1)

        tile_device.MockTpmOff()
        time.sleep(0.1)
        tile_device.MockTpmOn()

        assert not tile_device.isBeamformerRunning
        args = {"StartTime": start_time, "Duration": duration}
        tile_device.StartBeamformer(json.dumps(args))
        assert tile_device.isBeamformerRunning
        tile_device.StopBeamformer()
        assert not tile_device.isBeamformerRunning