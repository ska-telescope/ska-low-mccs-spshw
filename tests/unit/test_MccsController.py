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

import logging
import threading

import json
import pytest
import tango
from tango import DevState

from ska.base import DeviceStateModel
from ska.base.commands import CommandError, ResultCode
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs import (
    MccsController,
    ControllerPowerManager,
    ControllerResourceManager,
    release,
)
from ska.low.mccs.utils import call_with_json
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel

device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "controller",
}


class TestMccsController:
    """Test case for packet generation."""

    def test_State(self, device_under_test):
        """
        Test for State

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.State() == tango.DevState.OFF

    def test_Status(self, device_under_test):
        """
        Test for Status

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.Status() == "The device is in OFF state."

    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        vinfo = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [vinfo]

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, device_under_test):
        """
        Test for isCapabilityAchievable

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.isCapabilityAchievable([[0], [""]]) is not False

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(self, device_under_test):
        """
        Test for Reset

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        with pytest.raises(
            tango.DevFailed,
            match="Command Reset not allowed when the device is in OFF state",
        ):
            device_under_test.Reset()

    def test_On(self, device_under_test):
        """
        Test for On

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_Off(self, device_under_test):
        """
        Test for Off

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # Need to turn it on before we can turn it off
        device_under_test.On()
        [[result_code], [message]] = device_under_test.Off()
        assert result_code == ResultCode.OK
        assert message == "Off command completed OK"

    def test_StandbyLow(self, device_under_test):
        """
        Test for StandbyLow

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StandbyLow()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyLowCommand(), does nothing"

    def test_StandbyFull(self, device_under_test):
        """
        Test for StandbyFull

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StandbyFull()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyFullCommand(), does nothing"

    def test_Operate(self, device_under_test):
        """
        Test for Operate

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # assert device_under_test.Operate() == 0
        [[result_code], [message]] = device_under_test.Operate()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of OperateCommand(), does nothing"

    def test_Maintenance(self, device_under_test):
        """
        Test for Maintenance

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # assert device_under_test.Maintenance() is None
        [[result_code], [message]] = device_under_test.Maintenance()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of Maintenance(), does nothing"

    def test_Allocate(self, device_under_test):
        """
        Test the Allocate command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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

    def test_release(self, device_under_test):
        """
        Test Release command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        """
        Test for buildState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(self, device_under_test):
        """
        Test for versionId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    def test_healthState(self, device_under_test):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.healthState == HealthState.OK

    def test_controlMode(self, device_under_test):
        """
        Test for controlMode

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """
        Test for simulationMode

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(self, device_under_test):
        """
        Test for testMode

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.testMode == TestMode.NONE

    def test_commandProgress(self, device_under_test):
        """
        Test for commandProgress

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.commandProgress == 0

    def test_commandDelayExpected(self, device_under_test):
        """
        Test for commandDelayExpected

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.commandDelayExpected == 0

    def test_maxCapabilities(self, device_under_test):
        """
        Test for maxCapabilities

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.maxCapabilities is None

    def test_availableCapabilities(self, device_under_test):
        """
        Test for availableCapabilities

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.availableCapabilities is None


class TestControllerPowerManager:
    """
    This class contains tests of the ska.low.mccs.controller.ControllerPowerManager
    class
    """

    @pytest.fixture()
    def logger(self):
        """
        Fixture that returns a logger for the power manager under test
        (or its components) to use

        :return: a logger for the power manager under test to use
        :rtype: :py:class:`logging.Logger` or an object that implement
           its logging interface
        """
        return logging.getLogger()

    @pytest.fixture()
    def power_manager(self):
        """
        Fixture that returns a power manager with no hardware manager
        and no subservient devices

        :return: a power manager with no hardware manager and no
            subservient devices
        :rtype: :py:class:`ska.low.mccs.power.PowerManager`
        """
        return ControllerPowerManager([])

    @pytest.fixture()
    def state_model(self, logger):
        """
        Fixture that returns a state model for the command under test to
        use

        :param logger: a logger for the state model to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface

        :return: a state model for the command under test to use
        :rtype: :py:class:`ska.base.DeviceStateModel`
        """
        return DeviceStateModel(logger)

    def test_OnCommand(self, power_manager, state_model):
        """
        Test the working of the On command.

        Because the PowerManager and DeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the On
        command drives them correctly. The scope of this test is: check
        that the On command is not allowed to run the state model is
        not in the OFF state; check that such attempts fail with no
        side-effects; check that On() command IS allowed to run when
        the state model is in the OFF state; check that running the
        On() command succeeds, and that the result is the state model
        moves to state ON, and the power manager thinks it is on.

        :param power_manager: a power manager with no subservient
            devices
        :type power_manager: :py:class:`ska.low.mccs.power.PowerManager`
        :param state_model: the state model for the device
        :type state_model: :py:class:`ska.base.DeviceStateModel`
        """
        on_command = MccsController.OnCommand(power_manager, state_model)
        assert not power_manager.is_on()

        # in all states except OFF, the on command is not permitted,
        # should not be allowed, should fail, should have no side-effect
        # There's no need to check them all though, as that is done in
        # the lmcbaseclasses testing. Let's just double-check DISABLE
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.DISABLE
        )

        assert not on_command.is_allowed()
        with pytest.raises(CommandError):
            on_command()

        assert not power_manager.is_on()
        assert state_model.op_state == DevState.DISABLE

        # now push to OFF, the state in which the On command IS allowed
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.OFF
        )

        assert on_command.is_allowed()
        assert on_command() == (ResultCode.OK, "On command completed OK")
        assert power_manager.is_on()
        assert state_model.op_state == DevState.ON

    def test_OffCommand(self, power_manager, state_model):
        """
        Test the working of the Off command.

        Because the PowerManager and DeviceStateModel are thoroughly
        unit-tested elsewhere, here we just need to check that the Off
        command drives them correctly. The scope of this test is: check
        that the Off command is not allowed to run if the state model is
        not in the ON state; check that such attempts fail with no
        side-effects; check that Off() command IS allowed to run when
        the state model is in the ON state; check that running the
        Off() command succeeds, and that the result is the state model
        moves to state OFF, and the power manager thinks it is off.

        :param power_manager: a power manager with no subservient
            devices
        :type power_manager: :py:class:`ska.low.mccs.power.PowerManager`
        :param state_model: the state model for the device
        :type state_model: :py:class:`ska.base.DeviceStateModel`
        """
        off_command = MccsController.OffCommand(power_manager, state_model)
        power_manager.on()
        assert power_manager.is_on()

        # The Off command is allowed in states DISABLE, STANDBY and ON.
        # It is disallowed in states INIT and FAULT.

        # There's no need to check them all though, as that is done in
        # the lmcbaseclasses testing. Let's just check that the command
        # is disallowed from FAULT, and allowed from STANDBY

        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.FAULT
        )

        assert not off_command.is_allowed()
        with pytest.raises(CommandError):
            off_command()

        assert power_manager.is_on()
        assert state_model.op_state == DevState.FAULT

        # now push to STANDBY, a state in which the Off command IS
        # allowed
        state_model._straight_to_state(
            admin_mode=AdminMode.ONLINE, op_state=DevState.STANDBY
        )

        assert off_command.is_allowed()
        assert off_command() == (ResultCode.OK, "Off command completed OK")
        assert not power_manager.is_on()
        assert state_model.op_state == DevState.OFF


class TestControllerResourceManager:
    """
    This class contains tests of the ska.low.mccs.controller.ControllerResourceManager
    class.

    This class is already exercised through the Tango commands of Controller,
    but here we simulate some scenarios not covered.
    """

    @pytest.fixture()
    def resource_manager(self, device_under_test):
        """
        Fixture that returns a resource manager with 2 managed stations

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :return: a resource manager with 2 subservient station devices
        :rtype: :py:class:`ska.low.mccs.controller.ControllerResourceManager`
        """
        self.stations = ["low-mccs/station/001", "low-mccs/station/002"]

        # Event manager to take health events
        self.event_manager = EventManager(self.stations)
        self.health_model = HealthModel(
            None,
            self.stations,
            self.event_manager,
            device_under_test,
        )
        # HACK pending device pool management refactor
        self.health_monitor = self.health_model._health_monitor

        # Instantiate a resource manager for the Stations
        manager = ControllerResourceManager(
            self.health_monitor,
            "Test Manager",
            self.stations,
        )
        return manager

    def test_assign(self, resource_manager):
        """Test assignment operations of the ControllerResourceManager

        :param resource_manager: test fixture providing a manager object
        :type resource_manager: ControllerResourceManager
        """

        # Assign both stations
        resource_manager.assign(["low-mccs/station/001", "low-mccs/station/002"], 1)

        # They should both be recorded as assigned
        assigned = resource_manager.get_assigned_fqdns(1)
        assert "low-mccs/station/001" in assigned
        assert "low-mccs/station/002" in assigned

        # Drop station 2
        resource_manager.release(["low-mccs/station/002"])

        # It should now not be assigned
        assigned = resource_manager.get_assigned_fqdns(1)
        assert "low-mccs/station/002" not in assigned

        # Mock a health event so that station 2 is FAILED
        resource_manager._resources["low-mccs/station/002"]._health_changed(
            "healthState",
            HealthState.FAILED,
        )

        with pytest.raises(
            ValueError,
            match="low-mccs/station/002 does not pass health check for assignment",
        ):
            resource_manager.assign(["low-mccs/station/002"], 1)

        # Mock a health event so that station 2 is OK again
        resource_manager._resources["low-mccs/station/002"]._health_changed(
            "healthState",
            HealthState.OK,
        )

        # Assign it again
        resource_manager.assign(["low-mccs/station/002"], 1)

        # and check
        assigned = resource_manager.get_assigned_fqdns(1)
        assert "low-mccs/station/002" in assigned


class TestMccsController_InitCommand:
    """
    Contains the tests of :py:class:`~ska.low.mccs.MccsController`'s
    :py:class:`~ska.low.mccs.MccsController.InitCommand`.
    """

    class HangableInitCommand(MccsController.InitCommand):
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
            self._initialise_health_monitoring_called = False
            self._initialise_power_management_called = False

        def _initialise_health_monitoring(self, device, fqdns):
            """
            Initialise the health model for this device (overridden
            here to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device monitors health
            :type: list of str
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device, fqdns)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_power_management(self, device, fqdns):
            """
            Initialise power management for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device manages power
            :type: list of str
            """
            self._initialise_power_management_called = True
            super()._initialise_power_management(device, fqdns)

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
        assert init_command._initialise_health_monitoring_called
        assert not init_command._initialise_power_management_called
