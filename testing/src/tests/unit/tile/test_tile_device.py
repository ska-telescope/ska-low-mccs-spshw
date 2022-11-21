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

# import numpy as np
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
            ("fpga1Temperature", StaticTpmSimulator.FPGA1_TEMPERATURE, None),
            ("fpga2Temperature", StaticTpmSimulator.FPGA2_TEMPERATURE, None),
            ("fpgasUnixTime", pytest.approx(StaticTpmSimulator.FPGAS_TIME), None),
            (
                "currentTileBeamformerFrame",
                StaticTpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
                None,
            ),
            ("currentFrame", 0, None),
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
            # TODO Tests fail as np.ndarray is returned.
            # (
            #   "channeliserRounding",
            #   pytest.approx(StaticTpmSimulator.CHANNELISER_TRUNCATION),
            #   [2] * 512,
            # ),
            # ("preaduLevels", pytest.approx(StaticTpmSimulator.PREADU_LEVELS), [5]*32),
            # ("staticDelays", StaticTpmSimulator.STATIC_DELAYS, [12.]*32),
            # ("cspRounding", StaticTpmSimulator.CSP_ROUNDING, [3]*384),
            # ("arpTable", StaticTpmSimulator.ARP_TABLE, None),
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
                json.dumps(
                    {"mode": "1G", "payload_length": 4, "destination_ip": "10.0.1.23"}
                ),
            ),
            (
                "LoadPointingDelays",
                [3] + [1e-6, 2e-8] * 16,
            ),  # 2 * antennas_per_tile + 1
            (
                "ConfigureIntegratedChannelData",
                json.dumps(
                    {
                        "integration_time": 6.284,
                        "first_channel": 0,
                        "last_channel": 511,
                    }
                ),
            ),
            (
                "ConfigureIntegratedBeamData",
                json.dumps(
                    {
                        "integration_time": 3.142,
                        "first_channel": 0,
                        "last_channel": 191,
                    }
                ),
            ),
            (
                "SetLmcIntegratedDownload",
                json.dumps(
                    {
                        "mode": "1G",
                        "channel_payload_length": 4,
                        "beam_payload_length": 6,
                        "destination_ip": "10.0.1.23",
                    }
                ),
            ),
            ("ApplyCalibration", ""),
            ("ApplyPointingDelays", ""),
            ("StopIntegratedData", None),
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

        bitfile = "testing/data/Vivado_test_firmware_bitfile.bit"
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
            StaticTpmSimulator.REGISTER_MAP.keys()
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
        values = tile_device.ReadRegister("test-reg1")
        assert list(values) == [0] * num_values

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
            "register_name": "test-reg1",
            "values": [0, 1, 2, 3],
        }
        json_arg = json.dumps(arg)
        [[result_code], [message]] = tile_device.WriteRegister(json_arg)
        assert result_code == ResultCode.OK
        assert "WriteRegister" in message.split("_")[-1]

        for exclude_key in ["register_name", "values"]:
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

        expected = (0,)
        assert tile_device.ReadAddress([address]) == expected

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
            "core_id": 0,
            "arp_table_entry": 0,
            "source_mac": "10:fe:ed:08:0a:58",
            "source_ip": "10.0.99.3",
            "source_port": 4000,
            "destination_ip": "10.0.98.3",
            "destination_port": 5000,
        }
        tile_device.Configure40GCore(json.dumps(config_1))

        config_2 = {
            "core_id": 1,
            "arp_table_entry": 1,
            "source_mac": "10:fe:ed:08:0a:56",
            "source_ip": "10.0.99.4",
            "source_port": 4001,
            "destination_ip": "10.0.98.4",
            "destination_port": 5001,
        }
        tile_device.Configure40GCore(json.dumps(config_2))

        assert tuple(tile_device.fortyGbDestinationIps) == (
            "10.0.98.3",
            "10.0.98.4",
        )
        assert tuple(tile_device.fortyGbDestinationPorts) == (5000, 5001)

        arg = {
            "core_id": 0,
            "arp_table_entry": 0,
        }
        json_arg = json.dumps(arg)
        result_str = tile_device.Get40GCoreConfiguration(json_arg)
        result = json.loads(result_str)
        assert result["core_id"] == config_1.pop("core_id")

        arg = {
            "core_id": 3,
            "arp_table_entry": 0,
        }
        json_arg = json.dumps(arg)
        with pytest.raises(
            DevFailed, match="Invalid core id or arp table id specified"
        ):
            _ = tile_device.Get40GCoreConfiguration(json_arg)

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

    @pytest.mark.parametrize("start_time", (None,))
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
        args = {"start_time": start_time, "duration": duration}
        tile_device.StartBeamformer(json.dumps(args))
        assert tile_device.isBeamformerRunning
        tile_device.StopBeamformer()
        assert not tile_device.isBeamformerRunning

    def test_configure_beamformer(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for.

        ConfigureStationBeamformer
        SetBeamFormerRegions
        beamformerTable attribute

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

        tile_device.ConfigureStationBeamformer(
            json.dumps(
                {
                    "start_channel": 2,
                    "n_channels": 8,
                    "is_first": True,
                    "is_last": False,
                }
            )
        )
        table = list(tile_device.beamformerTable)
        expected = [2, 0, 0, 0, 0, 0, 0] + [0, 0, 0, 0, 0, 0, 0] * 47
        assert table == expected

        tile_device.SetBeamFormerRegions([2, 8, 5, 3, 8, 1, 1, 101])
        table = list(tile_device.beamformerTable)
        expected = [2, 5, 3, 8, 1, 1, 101] + [0, 0, 0, 0, 0, 0, 0] * 47
        assert table == expected

    def test_send_data_samples(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for various flavors of SendDataSamples.

        Also tests:
        CheckPendingDataRequests
        StopDataTransmission

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

        args = [
            {"data_type": "raw", "sync": True, "seconds": 6.7},
            {
                "data_type": "channel",
                "n_samples": 4,
                "first_channel": 7,
                "last_channel": 234,
            },
            {"data_type": "beam", "seconds": 0.5},
            {
                "data_type": "narrowband",
                "frequency": 150e6,
                "round_bits": 6,
                "n_samples": 128,
                "seconds": 0.5,
            },
        ]
        for arg in args:
            time.sleep(0.1)
            json_arg = json.dumps(arg)
            [[result_code], [message]] = tile_device.SendDataSamples(json_arg)
            assert result_code == ResultCode.OK

        assert not tile_device.pendingDataRequests
        json_arg = json.dumps(
            {"data_type": "channel_continuous", "channel_id": 2, "n_samples": 4}
        )
        [[result_code], [message]] = tile_device.SendDataSamples(json_arg)
        assert result_code == ResultCode.OK
        time.sleep(0.1)
        assert tile_device.pendingDataRequests
        tile_device.StopDataTransmission()
        time.sleep(0.1)
        assert not tile_device.pendingDataRequests
