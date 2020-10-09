###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsController project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contains the tests for the MccsController Tango device_under_test prototype."""

import json
import logging
import pytest
import tango

from ska.base import SKABaseDeviceStateModel
from ska.base.commands import CommandError, ResultCode
from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.low.mccs import MccsController, ControllerPowerManager, release
from ska.low.mccs.utils import call_with_json

device_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "controller",
}


class TestMccsController:
    """Test case for packet generation."""

    def test_State(self, device_under_test):
        """Test for State"""
        assert device_under_test.State() == tango.DevState.OFF

    def test_Status(self, device_under_test):
        """Test for Status"""
        assert device_under_test.Status() == "The device is in OFF state."

    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        vinfo = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [vinfo]

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, device_under_test):
        """Test for isCapabilityAchievable"""
        assert device_under_test.isCapabilityAchievable([[0], [""]]) is not False

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(self, device_under_test):
        """Test for Reset"""

        with pytest.raises(Exception):
            device_under_test.Reset()

    def test_On(self, device_under_test):
        """Test for On"""
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_Off(self, device_under_test):
        """Test for Off"""
        # Need to turn it on before we can turn it off
        device_under_test.On()
        [[result_code], [message]] = device_under_test.Off()
        assert result_code == ResultCode.OK
        assert message == "Off command completed OK"

    def test_StandbyLow(self, device_under_test):
        """Test for StandbyLow"""
        [[result_code], [message]] = device_under_test.StandbyLow()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyLowCommand(), does nothing"

    def test_StandbyFull(self, device_under_test):
        """Test for StandbyFull"""
        [[result_code], [message]] = device_under_test.StandbyFull()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyFullCommand(), does nothing"

    def test_Operate(self, device_under_test):
        """Test for Operate"""
        # assert device_under_test.Operate() == 0
        [[result_code], [message]] = device_under_test.Operate()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of OperateCommand(), does nothing"

    def test_Maintenance(self, device_under_test):
        """Test for Maintenance"""
        # assert device_under_test.Maintenance() is None
        [[result_code], [message]] = device_under_test.Maintenance()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of Maintenance(), does nothing"

    def test_Allocate(self, device_under_test):
        """
        Test the Allocate command.
        """
        controller = device_under_test  # for readability
        mock_subarray_1 = tango.DeviceProxy("low-mccs/subarray/01")
        mock_subarray_2 = tango.DeviceProxy("low-mccs/subarray/02")
        mock_station_1 = tango.DeviceProxy("low-mccs/station/001")
        mock_station_2 = tango.DeviceProxy("low-mccs/station/002")

        # Subarrays and stations are mock devices so we have to manually
        # set any relevant initial state
        mock_station_1.subarrayId = 0
        mock_station_2.subarrayId = 0

        controller.On()

        mock_subarray_1.On.side_effect = (
            (ResultCode.OK, "On command completed successfully"),
        )
        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )

        # allocate station_1 to subarray_1
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=1, station_ids=[1]
        )
        assert result_code == ResultCode.OK

        # check that the mock subarray_1 was told to assign that resource
        mock_subarray_1.On.assert_called_once_with()
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low-mccs/station/001"]})
        )
        mock_subarray_2.On.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=2, station_ids=[1]
        )
        assert result_code == ResultCode.FAILED

        # check no side-effects
        mock_subarray_1.On.assert_not_called()
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.On.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray
        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )

        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=1, station_ids=[1, 2]
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.On.assert_not_called()
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low-mccs/station/002"]})
        )
        mock_subarray_2.On.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 1

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        mock_subarray_1.ReleaseResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )

        # allocating station 2 to subarray 1 should succeed, because
        # it only requires resource release
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=1, station_ids=[2]
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.On.assert_not_called()
        mock_subarray_1.ReleaseResources.assert_called_once_with(
            json.dumps({"stations": ["low-mccs/station/001"]})
        )
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.On.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 1

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        mock_subarray_1.ReleaseAllResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )
        mock_subarray_1.Off.side_effect = ((ResultCode.OK, "Subarray switched off"),)

        (result_code, message) = call_with_json(
            controller.Release, subarray_id=1, release_all=True
        )
        assert result_code == ResultCode.OK

        mock_subarray_1.On.assert_not_called()
        mock_subarray_1.Off.assert_called_once_with()
        mock_subarray_1.ReleaseAllResources.assert_called_once_with()
        mock_subarray_2.AssignResources.assert_not_called()
        mock_subarray_2.On.assert_not_called()
        mock_subarray_2.Off.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()

        # check
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

        # now that subarray 1 has been disabled, its resources should
        # have been released so we should be able to allocate them to
        # subarray 2

        mock_subarray_2.On.side_effect = (
            (ResultCode.OK, "On command completed successfully"),
        )
        mock_subarray_2.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        (result_code, message) = call_with_json(
            controller.Allocate, subarray_id=2, station_ids=[1, 2]
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.On.assert_not_called()
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.On.assert_called_once_with()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low-mccs/station/001", "low-mccs/station/002"]})
        )
        assert mock_station_1.subarrayId == 2
        assert mock_station_2.subarrayId == 2

    def test_Release(self, device_under_test):
        """
        Test Release command.
        """
        controller = device_under_test  # for readability
        mock_subarray_1 = tango.DeviceProxy("low-mccs/subarray/01")
        mock_subarray_2 = tango.DeviceProxy("low-mccs/subarray/02")
        mock_station_1 = tango.DeviceProxy("low-mccs/station/001")
        mock_station_2 = tango.DeviceProxy("low-mccs/station/002")

        controller.On()

        # allocate stations 1 to subarray 1
        mock_subarray_1.On.side_effect = ((ResultCode.OK, "Subarray is on"),)
        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        call_with_json(controller.Allocate, subarray_id=1, station_ids=[1])
        mock_subarray_1.On.assert_called_once_with()
        # check state
        assert mock_station_1.subarrayId == 1

        # allocate station 2 to subarray 2
        mock_subarray_2.On.side_effect = ((ResultCode.OK, "Subarray is on"),)
        mock_subarray_2.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        call_with_json(controller.Allocate, subarray_id=2, station_ids=[2])
        mock_subarray_2.On.assert_called_once_with()
        # check state
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 2

        # release all resources from subarray_2
        mock_subarray_2.ReleaseAllResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )
        mock_subarray_2.Off.side_effect = ((ResultCode.OK, "Subarray switched off"),)

        # release all resources from subarray_2
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_1.Off.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_called_once_with()
        mock_subarray_2.Off.assert_called_once_with()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # releasing all resources of unresourced subarray_2 should fail
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.FAILED

        # check no side-effect to failed release
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_1.Off.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_not_called()
        mock_subarray_2.Off.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # release resources of subarray_1
        mock_subarray_1.ReleaseAllResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )
        mock_subarray_1.Off.side_effect = ((ResultCode.OK, "Subarray switched off"),)

        # release all resources from subarray_1
        (result_code, message) = call_with_json(
            controller.Release, subarray_id=1, release_all=True
        )
        assert result_code == ResultCode.OK

        # check all released
        mock_subarray_1.Off.assert_called_once_with()
        mock_subarray_1.ReleaseAllResources.assert_called_once_with()
        mock_subarray_2.Off.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

    def test_buildState(self, device_under_test):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version

    def test_healthState(self, device_under_test):
        """Test for healthState"""
        assert device_under_test.healthState == HealthState.OK

    def test_controlMode(self, device_under_test):
        """Test for controlMode"""
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """Test for simulationMode"""
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(self, device_under_test):
        """Test for testMode"""
        assert device_under_test.testMode == TestMode.NONE

    def test_commandProgress(self, device_under_test):
        """Test for commandProgress"""
        assert device_under_test.commandProgress == 0

    def test_commandDelayExpected(self, device_under_test):
        """Test for commandDelayExpected"""
        assert device_under_test.commandDelayExpected == 0

    def test_maxCapabilities(self, device_under_test):
        """Test for maxCapabilities"""
        assert device_under_test.maxCapabilities is None

    def test_availableCapabilities(self, device_under_test):
        """Test for availableCapabilities"""
        assert device_under_test.availableCapabilities is None


class TestControllerPowerManager:
    """
    This class contains tests of the ska.low.mccs.controller.ControllerPowerManager
    class
    """

    @pytest.fixture
    def logger(self):
        """
        Fixture that returns a logger for the power manager under test
        (or its components) to use
        """
        return logging.getLogger()

    @pytest.fixture
    def power_manager(self):
        """
        Fixture that returns a power manager with no hardware manager
        and no subservient devices
        """
        return ControllerPowerManager([])

    @pytest.fixture
    def state_model(self, logger):
        """
        Fixture that returns a state model for the power manager under
        test to use

        :param logger: a logger for the state model to use
        """
        return SKABaseDeviceStateModel(logger)

    def test_OnCommand(self, power_manager, state_model, logger):
        """
        Test the working of the On command.

        Because the PowerManager and SKABaseDeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the On
        command drives them correctly. The scope of this test is: check
        that the On command is not allowed to run the state model is
        not in the OFF state; check that such attempts fail with no
        side-effects; check that On() command IS allowed to run when
        the state model is in the OFF state; check that running the
        On() command succeeds, and that the result is the state model
        moves to state ON, and the power manager thinks it is on.
        """
        on_command = MccsController.OnCommand(power_manager, state_model, logger)
        assert not power_manager.is_on()

        all_states = {
            "UNINITIALISED",
            "FAULT_ENABLED",
            "FAULT_DISABLED",
            "INIT_ENABLED",
            "INIT_DISABLED",
            "DISABLED",
            "OFF",
            "ON",
        }

        # in all states except OFF, the on command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        for state in all_states - {"OFF"}:
            state_model._straight_to_state(state)

            assert not on_command.is_allowed()
            with pytest.raises(CommandError):
                on_command()

            assert not power_manager.is_on()
            assert state_model._state == state

        # now push to OFF, the state in which the On command IS allowed
        state_model._straight_to_state("OFF")
        assert on_command.is_allowed()
        assert on_command() == (ResultCode.OK, "On command completed OK")
        assert power_manager.is_on()
        assert state_model._state == "ON"

    def test_OffCommand(self, power_manager, state_model):
        """
        Test the working of the Off command.

        Because the PowerManager and BaseDeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the Off
        command drives them correctly. The scope of this test is: check
        that the Off command is not allowed to run if the state model is
        not in the ON state; check that such attempts fail with no
        side-effects; check that Off() command IS allowed to run when
        the state model is in the ON state; check that running the
        Off() command succeeds, and that the result is the state model
        moves to state OFF, and the power manager thinks it is off.
        """
        off_command = MccsController.OffCommand(power_manager, state_model)
        power_manager.on()
        assert power_manager.is_on()

        all_states = {
            "UNINITIALISED",
            "FAULT_ENABLED",
            "FAULT_DISABLED",
            "INIT_ENABLED",
            "INIT_DISABLED",
            "DISABLED",
            "OFF",
            "ON",
        }

        # in all states except ON, the off command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        for state in all_states - {"ON"}:
            state_model._straight_to_state(state)

            assert not off_command.is_allowed()
            with pytest.raises(CommandError):
                off_command()

            assert power_manager.is_on()
            assert state_model._state == state

        # now push to ON, the state in which the Off command IS allowed
        state_model._straight_to_state("ON")
        assert off_command.is_allowed()
        assert off_command() == (ResultCode.OK, "Off command completed OK")
        assert not power_manager.is_on()
        assert state_model._state == "OFF"
