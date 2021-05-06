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

import json
import itertools
import threading

import pytest
from tango import AttrQuality, DevFailed, DevState, EventType

from ska_tango_base import DeviceStateModel
from ska_tango_base.control_model import HealthState, SimulationMode, TestMode
from ska_tango_base.commands import ResultCode
from ska_low_mccs import MccsDeviceProxy, MccsTile
from ska_low_mccs.hardware import PowerMode, SimulableHardwareFactory
from ska_low_mccs.tile import TileHardwareManager, TilePowerManager, StaticTpmSimulator

from testing.harness.mock import MockDeviceBuilder


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "tile_0001",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def initial_mocks(mock_factory, request):
    """
    Fixture that registers device proxy mocks prior to patching. The
    default fixture is overridden here to ensure that a mock subrack
    responds suitably to actions taken on it by the TilePowerManager.

    :param mock_factory: a factory for
        :py:class:`tango.DeviceProxy` mocks
    :type mock_factory: object
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`
    :return: a dictionary of mocks, keyed by FQDN
    :rtype: dict
    """
    kwargs = getattr(request, "param", {})
    state = kwargs.get("state", DevState.ON)
    is_on = kwargs.get("is_on", False)
    result_code = kwargs.get("result_code", ResultCode.OK)

    mock_subrack_factory = MockDeviceBuilder(mock_factory)
    mock_subrack_factory.set_state(state)
    mock_subrack_factory.add_command("IsTpmOn", is_on)
    mock_subrack_factory.add_result_command("PowerOffTpm", result_code)
    mock_subrack_factory.add_result_command("PowerOnTpm", result_code)

    return {"low-mccs/subrack/01": mock_subrack_factory()}


@pytest.fixture()
def mock_factory(mocker, request):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    kwargs = getattr(request, "param", {})
    is_on = kwargs.get("is_on", False)

    builder = MockDeviceBuilder()
    builder.add_attribute("areTpmsOn", [is_on, True, False, True])
    return builder


@pytest.fixture()
def device_under_test(tango_harness):
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/tile/0001")


class TestTilePowerManager:
    """
    Test class for
    :py:class:`ska_low_mccs.tile.tile_device.TilePowerManager`.
    """

    @pytest.fixture()
    def power_manager(self, logger, mock_callback):
        """
        Returns the power manager under test.

        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param mock_callback: a mock for use as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`

        :return: the power manager under test
        :rtype: :py:class:`ska_low_mccs.tile.tile_device.TilePowerManager`
        """
        return TilePowerManager("low-mccs/subrack/01", 1, logger, mock_callback)

    @pytest.mark.parametrize(
        ("initial_mocks", "mock_factory", "expected_power_mode"),
        [
            # ({"state": A, "is_on": B}, {"is_on": C}, D) means
            # If subrack.state() returns A
            # If subrack.IsTpmOn() returns B,
            # And change event subscription on subrack.areTpmsOn returns a C event
            # Then the power mode should end up D.
            (
                {"state": DevState.DISABLE, "is_on": False},
                {"is_on": False},
                PowerMode.OFF,
            ),
            ({"state": DevState.OFF, "is_on": False}, {"is_on": False}, PowerMode.OFF),
            ({"state": DevState.ON, "is_on": False}, {"is_on": False}, PowerMode.OFF),
            ({"state": DevState.ON, "is_on": True}, {"is_on": True}, PowerMode.ON),
        ],
        ids=("DISABLED", "OFF", "TPM off", "TPM on"),
        indirect=["initial_mocks", "mock_factory"],
    )
    def test_init(
        self,
        device_under_test,
        power_manager,
        mock_callback,
        initial_mocks,
        expected_power_mode,
        mock_factory,
    ):
        """
        Test that the power manager initialises into the right state,
        depending on whether the subrack says the TPM is off or on.

        :param device_under_test: a :py:class:`tango.DeviceProxy` to the
            device under test, within a
            :py:class:tango.test_context.DeviceTestContext`tile.
            (The device is not actually under test here, but we need
            this to ensure that the TANGO subsystem gets stood up.)
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param power_manager: the power_manager under test
        :type power_manager: :py:class:`ska_low_mccs.tile.tile_device.TilePowerManager`
        :param mock_callback: a mock for use as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        :param initial_mocks: a dictionary of mock devices, keyed by
            device FQDN, set up before device initialisation. This is
            only used indirectly here, but included so that we can
            indirectly parametrize it.
        :type initial_mocks: dict<str, :py:class:`pytest_mock.mocker.Mock`>
        :param expected_power_mode: the expected post-init power mode,
            given the indirect parametrisation of the subrack mock
            fixture.
        :param mock_factory: a factory for
            :py:class:`tango.DeviceProxy` mocks
        :type mock_factory: object
        """
        assert power_manager.power_mode == PowerMode.UNKNOWN
        power_manager.connect()
        assert power_manager.power_mode == expected_power_mode
        mock_callback.assert_called_once_with(expected_power_mode)

    @pytest.mark.parametrize(
        ("initial_mocks", "expected_return", "expected_power_mode"),
        [
            # ({"is_on": A, "result_code": B}, C, D) means
            # If subrack.IsTpmOn() returns A,
            # And subrack.PowerOnTPM() returns B
            # Then power_manager.on() should return C,
            # And the power mode should end up as D
            ({"is_on": False, "result_code": ResultCode.OK}, True, PowerMode.ON),
            ({"is_on": False, "result_code": ResultCode.FAILED}, False, PowerMode.OFF),
            ({"is_on": True, "result_code": ResultCode.OK}, None, PowerMode.ON),
            ({"is_on": True, "result_code": ResultCode.FAILED}, None, PowerMode.ON),
        ],
        ids=("OFF-OK", "OFF-FAILED", "ON-OK", "ON-FAILED"),
        indirect=["initial_mocks"],
    )
    def test_on(
        self,
        device_under_test,
        power_manager,
        initial_mocks,
        expected_return,
        expected_power_mode,
        mock_callback,
    ):
        """
        Test that turning on this TilePowerManager results in the right
        return code and state for each possible subrack state.

        :param device_under_test: a :py:class:`tango.DeviceProxy` to the
            device under test, within a
            :py:class:tango.test_context.DeviceTestContext`tile.
            (The device is not actually under test here, but we need
            this to ensure that the TANGO subsystem gets stood up.)
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param power_manager: the power_manager under test
        :type power_manager: :py:class:`ska_low_mccs.tile.tile_device.TilePowerManager`
        :param initial_mocks: a dictionary of mock devices, keyed by
            device FQDN, set up before device initialisation. This is
            only used indirectly here, but included so that we can
            indirectly parametrize it.
        :type initial_mocks: dict<str, :py:class:`pytest_mock.mocker.Mock`>
        :param expected_return: the expected return value for the call
        :type expected_return: bool
        :param expected_power_mode: the expected power mode of this
            TilePowerManager after the method has been executed.
        :type expected_power_mode:
            :py:class:`ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        :param mock_callback: a mock for use as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        power_manager.connect()
        assert power_manager.on() == expected_return
        assert power_manager.power_mode == expected_power_mode

    @pytest.mark.parametrize(
        ("initial_mocks", "expected_return", "expected_power_mode"),
        [
            # ({"is_on": A, "result_code": B}, C, D) means
            # If subrack.IsTpmOn() returns A,
            # And subrack.PowerOffTPM() returns B
            # Then power_manager.off() should return C,
            # And the power mode should end up as D
            ({"is_on": False, "result_code": ResultCode.OK}, None, PowerMode.OFF),
            ({"is_on": False, "result_code": ResultCode.FAILED}, None, PowerMode.OFF),
            ({"is_on": True, "result_code": ResultCode.OK}, True, PowerMode.OFF),
            ({"is_on": True, "result_code": ResultCode.FAILED}, False, PowerMode.ON),
        ],
        ids=("OFF-OK", "OFF-FAILED", "ON-OK", "ON-FAILED"),
        indirect=["initial_mocks"],
    )
    def test_off(
        self,
        device_under_test,
        power_manager,
        initial_mocks,
        expected_return,
        expected_power_mode,
    ):
        """
        Test that turning on this TilePowerManager results in the right
        return code and state for each possible subrack state.

        :param device_under_test: a :py:class:`tango.DeviceProxy` to the
            device under test, within a
            :py:class:tango.test_context.DeviceTestContext`tile.
            (The device is not actually under test here, but we need
            this to ensure that the TANGO subsystem gets stood up.)
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param power_manager: the power_manager under test
        :type power_manager: :py:class:`ska_low_mccs.tile.tile_device.TilePowerManager`
        :param initial_mocks: a dictionary of mock devices, keyed by
            device FQDN, set up before device initialisation. This is
            only used indirectly here, but included so that we can
            indirectly parametrize it.
        :type initial_mocks: dict<str, :py:class:`pytest_mock.mocker.Mock`>
        :param expected_return: the expected return value for the call
        :type expected_return: bool
        :param expected_power_mode: the expected power mode of this
            TilePowerManager after the method has been executed.
        :type expected_power_mode:
            :py:class:`ska_low_mccs.hardware.power_mode_hardware.PowerMode`
        """
        power_manager.connect()
        assert power_manager.off() == expected_return
        assert power_manager.power_mode == expected_power_mode


class TestMccsTile:
    """
    Test class for MccsTile tests.

    The Tile device represents the TANGO interface to a Tile (TPM) unit.
    Tests conducted herein aim to exercise the currently defined MCCS
    Tile device server methods.
    """

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        assert device_under_test.healthState == HealthState.UNKNOWN

        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.UNKNOWN
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

    def test_voltage(self, device_under_test, dummy_json_args):
        """
        Test for the voltage attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert device_under_test.voltage == StaticTpmSimulator.VOLTAGE

    def test_current(self, device_under_test, dummy_json_args):
        """
        Test for the current attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        device_under_test.current == StaticTpmSimulator.CURRENT

    def test_board_temperature(self, device_under_test, dummy_json_args):
        """
        Test for the board_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert (
            device_under_test.board_temperature == StaticTpmSimulator.BOARD_TEMPERATURE
        )

    def test_fpga1_temperature(self, device_under_test, dummy_json_args):
        """
        Test for the fpga1_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert (
            device_under_test.fpga1_temperature == StaticTpmSimulator.FPGA1_TEMPERATURE
        )

    def test_fpga2_temperature(self, device_under_test, dummy_json_args):
        """
        Test for the fpga2_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert (
            device_under_test.fpga2_temperature == StaticTpmSimulator.FPGA2_TEMPERATURE
        )

    def test_fpga1_time(self, device_under_test, dummy_json_args):
        """
        Test for the fpga1_time attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert device_under_test.fpga1_time == StaticTpmSimulator.FPGA1_TIME

    def test_fpga2_time(self, device_under_test, dummy_json_args):
        """
        Test for the fpga2_time attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert device_under_test.fpga2_time == StaticTpmSimulator.FPGA2_TIME

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

    def test_adcPower(self, device_under_test, dummy_json_args):
        """
        Test for the adcPowerattribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        expected = tuple(float(i) for i in range(32))
        assert device_under_test.adcPower == pytest.approx(expected)

    def test_currentTileBeamformerFrame(self, device_under_test, dummy_json_args):
        """
        Test for the currentTileBeamformerFrame attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert (
            device_under_test.currentTileBeamformerFrame
            == StaticTpmSimulator.CURRENT_TILE_BEAMFORMER_FRAME
        )

    def test_phaseTerminalCount(self, device_under_test, dummy_json_args):
        """
        Test for the phaseTerminalCount attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert (
            device_under_test.PhaseTerminalCount
            == StaticTpmSimulator.PHASE_TERMINAL_COUNT
        )
        device_under_test.PhaseTerminalCount = 45
        assert device_under_test.PhaseTerminalCount == 45

    def test_ppsDelay(self, device_under_test, dummy_json_args):
        """
        Test for the ppsDelay attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert device_under_test.ppsDelay == 12


class TestMccsTileCommands:
    """
    Tests of MccsTile device commands.
    """

    @pytest.mark.parametrize(
        ("device_command", "arg"),
        (
            (
                "SetLmcDownload",
                json.dumps({"Mode": "1G", "PayloadLength": 4, "DstIP": "10.0.1.23"}),
            ),
            ("SetBeamFormerRegions", (2, 8, 5, 0)),
            (
                "ConfigureStationBeamformer",
                json.dumps(
                    {"StartChannel": 2, "NumTiles": 4, "IsFirst": True, "IsLast": False}
                ),
            ),
            ("LoadBeamAngle", tuple(float(i) for i in range(16))),
            ("LoadAntennaTapering", tuple(float(i) for i in range(17))),
            ("SetPointingDelay", [3] * 5),  # 2 * antennas_per_tile + 1
            ("ConfigureIntegratedChannelData", 6.284),
            ("ConfigureIntegratedBeamData", 3.142),
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
                    {"CurrentDelay": 5.0, "CurrentTC": 2, "RefLo": 3.0, "RefHi": 78.0}
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
        ),
    )
    def test_command_not_implemented(
        self, device_under_test, device_command, arg, dummy_json_args
    ):
        """
        A very weak test for commands that are not implemented yet.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_command: the name of the device command under test
        :type device_command: str
        :param arg: argument to the command (optional)
        :type arg: str
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        args = [] if arg is None else [arg]
        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = getattr(device_under_test, device_command)(*args)

    @pytest.mark.parametrize(
        ("device_command", "arg", "tpm_command"),
        (
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
        self,
        device_under_test,
        mocker,
        device_command,
        arg,
        tpm_command,
        logger,
        dummy_json_args,
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
        :type mocker: :py:class:`pytest_mock.mocker`
        :param device_command: the name of the device command under test
        :type device_command: str
        :param arg: argument to the command (optional)
        :type arg: str
        :param tpm_command: the name of the tpm command that is expected
            to be called as a result of the device command being called
        :type tpm_command: str
        :param logger: a object that implements the standard logging
            interface of :py:class:`logging.Logger`
        :type logger: :py:class:`logging.Logger`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        # First test that the calling the command on the device results
        # in a NotImplementedError
        args = [] if arg is None else [arg]
        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = getattr(device_under_test, device_command)(*args)

        # Now check that calling the command object results in the
        # correct TPM simulator command being called.
        state_model = DeviceStateModel(logger)

        mock_tpm_simulator = mocker.Mock()
        hardware_factory = SimulableHardwareFactory(
            True, _static_simulator=mock_tpm_simulator
        )
        hardware_manager = TileHardwareManager(
            SimulationMode.TRUE,
            TestMode.TEST,
            logger,
            "0.0.0.0",
            10000,
            _factory=hardware_factory,
        )

        command_class = getattr(MccsTile, f"{device_command}Command")
        command_object = command_class(hardware_manager, state_model, logger)

        # doesn't raise NotImplementedError because the tpm simulator is
        # mocked out
        command_object(*args)
        assert getattr(mock_tpm_simulator, tpm_command).called_once_with(*args)

    def test_Initialise(self, device_under_test):
        """
        Test for Initialise.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.Initialise()
        assert result_code == ResultCode.OK
        assert message == MccsTile.InitialiseCommand.SUCCEEDED_MESSAGE

    def test_On(self, device_under_test, dummy_json_args):
        """
        Test for On.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        [result_code], [_, message_uid] = device_under_test.On(dummy_json_args)
        assert result_code == ResultCode.QUEUED
        assert ":On" in message_uid

    def test_GetFirmwareAvailable(self, device_under_test, dummy_json_args):
        """
        Test for:

        * GetFirmwareAvailable command
        * firmwareName attribute
        * firmwareVersion attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        firmware_available_str = device_under_test.GetFirmwareAvailable()
        firmware_available = json.loads(firmware_available_str)
        assert firmware_available == StaticTpmSimulator.FIRMWARE_AVAILABLE

        firmware_name = device_under_test.firmwareName
        assert firmware_name == StaticTpmSimulator.FIRMWARE_NAME

        major = firmware_available[firmware_name]["major"]
        minor = firmware_available[firmware_name]["minor"]
        assert device_under_test.firmwareVersion == f"{major}.{minor}"

    def test_DownloadFirmware(self, device_under_test):
        """
        Test for DownloadFirmware. Also functions as the test for the
        isProgrammed and the firmwareName properties.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Standby()

        assert not device_under_test.isProgrammed
        bitfile = "testing/data/Vivado_test_firmware_bitfile.bit"
        [[result_code], [message]] = device_under_test.DownloadFirmware(bitfile)
        assert result_code == ResultCode.OK
        assert message == MccsTile.DownloadFirmwareCommand.SUCCEEDED_MESSAGE
        assert device_under_test.isProgrammed
        assert device_under_test.firmwareName == bitfile

    def test_MissingDownloadFirmwareFile(self, device_under_test):
        """
        Test for a missing firmware download. Also functions as the test
        for the isProgrammed and the firmwareName properties.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Standby()

        assert not device_under_test.isProgrammed
        invalid_bitfile_path = "this/folder/and/file/doesnt/exist.bit"
        existing_firmware_name = device_under_test.firmwareName
        [[result_code], [message]] = device_under_test.DownloadFirmware(
            invalid_bitfile_path
        )
        assert result_code == ResultCode.FAILED
        assert message != MccsTile.DownloadFirmwareCommand.SUCCEEDED_MESSAGE
        assert not device_under_test.isProgrammed
        assert device_under_test.firmwareName == existing_firmware_name

    def test_GetRegisterList(self, device_under_test, dummy_json_args):
        """
        Test for GetRegisterList.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert device_under_test.GetRegisterList() == list(
            StaticTpmSimulator.REGISTER_MAP[0].keys()
        )

    def test_ReadRegister(self, device_under_test, dummy_json_args):
        """
        Test for ReadRegister.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        num_values = 4
        arg = {
            "RegisterName": "test-reg1",
            "NbRead": num_values,
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)
        values = device_under_test.ReadRegister(json_arg)
        assert list(values) == [0] * num_values

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed, match=f"{exclude_key} is a mandatory parameter"
            ):
                _ = device_under_test.ReadRegister(bad_json_arg)

    def test_WriteRegister(self, device_under_test, dummy_json_args):
        """
        Test for WriteRegister.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        arg = {
            "RegisterName": "test-reg1",
            "Values": [0, 1, 2, 3],
            "Offset": 1,
            "Device": 1,
        }
        json_arg = json.dumps(arg)

        [[result_code], [message]] = device_under_test.WriteRegister(json_arg)
        assert result_code == ResultCode.OK
        assert message == MccsTile.WriteRegisterCommand.SUCCEEDED_MESSAGE

        for exclude_key in arg.keys():
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed, match=f"{exclude_key} is a mandatory parameter"
            ):
                _ = device_under_test.WriteRegister(bad_json_arg)

    def test_ReadAddress(self, device_under_test, dummy_json_args):
        """
        Test for ReadAddress.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        address = 0xF
        nvalues = 10
        expected = (0,) * nvalues
        assert tuple(device_under_test.ReadAddress([address, nvalues])) == expected

        with pytest.raises(DevFailed):
            _ = device_under_test.ReadAddress([address])

    def test_WriteAddress(self, device_under_test, dummy_json_args):
        """
        Test for WriteAddress.

        This is a very weak test but the
        :py:class:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager`'s
        :py:meth:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager.write_address`
        method is well tested.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        [[result_code], [message]] = device_under_test.WriteAddress([20, 1, 2, 3])
        assert result_code == ResultCode.OK
        assert message == MccsTile.WriteAddressCommand.SUCCEEDED_MESSAGE

    def test_Configure40GCore(self, device_under_test, dummy_json_args):
        """
        Test for.

        * Configure40GCore command
        * fortyGDestinationIps attribute
        * fortyGDestinationMacs attribute
        * fortyGDestinationPorts attribute

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

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
    def test_SetChanneliserTruncation(
        self, device_under_test, channels, frequencies, dummy_json_args
    ):
        """
        Test for SetChanneliserTruncation.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param channels: number of channels to set
        :type channels: int
        :param frequencies: number of frequencies to set
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        array = [channels] + [frequencies] + [1.0] * (channels * frequencies)

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = device_under_test.SetChanneliserTruncation(array)
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = device_under_test.SetChanneliserTruncation(array[:-1])
        with pytest.raises(DevFailed, match="ValueError: cannot reshape array"):
            _ = device_under_test.SetChanneliserTruncation(array + [1.0])

    def test_LoadCalibrationCoefficients(self, device_under_test, dummy_json_args):
        """
        Test for LoadCalibrationCoefficients.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        antenna = 2
        complex_coefficients = [
            [complex(3.4, 1.2), complex(2.3, 4.1), complex(4.6, 8.2), complex(6.8, 2.4)]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coefficients))
        out = [[v.real, v.imag] for v in inp]
        coefficients = [antenna] + list(itertools.chain.from_iterable(out))

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = device_under_test.LoadCalibrationCoefficients(coefficients)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCoefficients(coefficients[0:8])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCoefficients(coefficients[0:16])

    def test_LoadCalibrationCurve(self, device_under_test, dummy_json_args):
        """
        Test for LoadCalibrationCurve.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        antenna = 2
        beam = 0
        complex_coefficients = [
            [complex(3.4, 1.2), complex(2.3, 4.1), complex(4.6, 8.2), complex(6.8, 2.4)]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coefficients))
        out = [[v.real, v.imag] for v in inp]
        coefficients = [antenna] + [beam] + list(itertools.chain.from_iterable(out))

        with pytest.raises(DevFailed, match="NotImplementedError"):
            _ = device_under_test.LoadCalibrationCurve(coefficients)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCurve(coefficients[0:9])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = device_under_test.LoadCalibrationCurve(coefficients[0:17])

    @pytest.mark.parametrize("start_time", (None, 0))
    @pytest.mark.parametrize("duration", (None, -1))
    def test_start_and_stop_beamformer(
        self, device_under_test, start_time, duration, dummy_json_args
    ):
        """
        Test for.

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
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """
        # TODO: For now we need to get this to OFF (highest state of
        # device readiness) before we can turn this ON. This is a
        # counterintuitive mess that will be fixed in SP-1501.
        device_under_test.Off()
        device_under_test.On(dummy_json_args)
        assert not device_under_test.isBeamformerRunning
        args = {"StartTime": start_time, "Duration": duration}
        device_under_test.StartBeamformer(json.dumps(args))
        assert device_under_test.isBeamformerRunning
        device_under_test.StopBeamformer()
        assert not device_under_test.isBeamformerRunning


class TestInitCommand:
    """
    Contains the tests of :py:class:`~ska_low_mccs.tile.tile_device.MccsTile`'s
    :py:class:`~ska_low_mccs.tile.tile_device.MccsTile.InitCommand`.
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
            Create a new HangableInitCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_hardware_management_called = False
            self._initialise_health_monitoring_called = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device (overridden here to inject a call trace
            attribute).

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_hardware_management_called = True
            super()._initialise_hardware_management(device)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device)

    @pytest.mark.skip(
        reason="This is taking forever to run; need to investigate"
        # TODO: investigate this.
    )
    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: :py:class:`pytest_mock.mocker`
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
