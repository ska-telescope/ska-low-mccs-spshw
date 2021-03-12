###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA-Low-MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
Contains the tests for the MccsController Tango device_under_test
prototype.
"""

import json
import threading

import pytest
import tango
from tango import AttrQuality
from tango.server import command

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs import MccsController, MccsDeviceProxy, MccsSubarray, release
from ska.low.mccs.controller import ControllerResourceManager
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel
from ska.low.mccs.utils import call_with_json

from tests.mocks import MockDeviceBuilder, MockSubarrayBuilder


class ControllerWithFailableDevices(MccsController):
    """
    An extension of the MccsController device with additional commands
    that we can use to tell the device to simulate the receipt of events
    from subservient devices.
    """

    @command(dtype_in="DevString")
    def simulateHealthStateChange(self, argin):
        """
        Makes this controller think that a device that it manages has
        had a change of healthState.

        :param argin: JSON-encode dict with "fqdn" and "health" values
        :type argin: str
        """
        kwargs = json.loads(argin)
        fqdn = kwargs.get("fqdn")
        assert fqdn is not None
        health = kwargs.get("health_state")
        assert health is not None

        self.health_model._health_monitor._device_health_monitors[
            fqdn
        ]._health_state_changed(fqdn, "healthState", health, AttrQuality.ATTR_VALID)

    @command(dtype_in="DevString")
    def simulateAdminModeChange(self, argin):
        """
        Makes this controller think that a device that it manages has
        had a change of adminMode.

        :param argin: JSON-encode dict with "fqdn" and "adminMode" values
        :type argin: str
        """
        kwargs = json.loads(argin)
        fqdn = kwargs.get("fqdn")
        assert fqdn is not None
        admin_mode = kwargs.get("admin_mode")
        assert admin_mode is not None

        self.health_model._health_monitor._device_health_monitors[
            fqdn
        ]._admin_mode_changed(fqdn, "adminMode", admin_mode, AttrQuality.ATTR_VALID)


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska.low.mccs",
        "device": "controller",
        "proxy": MccsDeviceProxy,
        "patch": ControllerWithFailableDevices,
    }


@pytest.fixture()
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("healthState", HealthState.UNKNOWN)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    builder.add_result_command("Off", ResultCode.OK)
    builder.add_result_command("On", ResultCode.OK)
    builder.add_result_command("Standby", ResultCode.OK)
    return builder


class TestMccsController:
    """
    Tests of the MccsController device.
    """

    def test_State(self, device_under_test):
        """
        Test for State.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.State() == tango.DevState.DISABLE

    def test_Status(self, device_under_test):
        """
        Test for Status.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.Status() == "The device is in DISABLE state."

    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo.

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
        Test for isCapabilityAchievable.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.isCapabilityAchievable([[0], [""]]) is not False

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(self, device_under_test):
        """
        Test for Reset.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        with pytest.raises(
            tango.DevFailed,
            match="Command Reset not allowed when the device is in DISABLE state",
        ):
            device_under_test.Reset()

    def test_On(self, device_under_test, mock_event_callback):
        """
        Test for On (including end of command event testing).

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_event_callback: fixture that provides a mock
            instance with callback support methods
        :type mock_event_callback: :py:class:`pytest_mock.mocker.Mock`
        """
        device_under_test.Off()

        # Test that subscription yields an event as expected
        _ = device_under_test.subscribe_event(
            "commandResult", tango.EventType.CHANGE_EVENT, mock_event_callback
        )
        mock_event_callback.check_event_data(name="commandResult", result=None)

        # Call the On() command on the Controller device
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == MccsController.OnCommand.SUCCEEDED_MESSAGE
        mock_event_callback.check_command_result(
            name="commandResult", result=result_code
        )

    def test_Off(self, device_under_test, mock_event_callback):
        """
        Test for Off (including end of command event testing).

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_event_callback: fixture that provides a mock
            instance with callback support methods
        :type mock_event_callback: :py:class:`pytest_mock.mocker.Mock`
        """
        controller = device_under_test  # for readability
        # Need to turn it on before we can turn it off
        controller.Off()
        controller.On()

        # Test that subscription yields an event as expected
        _ = controller.subscribe_event(
            "commandResult", tango.EventType.CHANGE_EVENT, mock_event_callback
        )
        mock_event_callback.check_event_data(name="commandResult", result=None)

        # Call the Off() command on the Controller device
        [[result_code], [message]] = controller.Off()
        assert result_code == ResultCode.OK
        assert message == MccsController.OffCommand.SUCCEEDED_MESSAGE
        mock_event_callback.check_command_result(
            name="commandResult", result=result_code
        )

    def test_StandbyLow(self, device_under_test):
        """
        Test for StandbyLow.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StandbyLow()
        assert result_code == ResultCode.OK
        assert message == MccsController.StandbyLowCommand.SUCCEEDED_MESSAGE

    def test_StandbyFull(self, device_under_test):
        """
        Test for StandbyFull.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StandbyFull()
        assert result_code == ResultCode.OK
        assert message == MccsController.StandbyFullCommand.SUCCEEDED_MESSAGE

    def test_Operate(self, device_under_test):
        """
        Test for Operate.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()

        # assert device_under_test.Operate() == 0
        [[result_code], [message]] = device_under_test.Operate()
        assert result_code == ResultCode.OK
        assert message == MccsController.OperateCommand.SUCCEEDED_MESSAGE

    def test_Maintenance(self, device_under_test):
        """
        Test for Maintenance.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # assert device_under_test.Maintenance() is None
        [[result_code], [message]] = device_under_test.Maintenance()
        assert result_code == ResultCode.OK
        assert message == MccsController.MaintenanceCommand.SUCCEEDED_MESSAGE

    class TestAllocateRelease:
        """
        Class containing fixtures and tests of the MccsController's
        :py:meth:`~ska.low.mccs.controller.controller_device.MccsController.Allocate`
        and
        :py:meth:`~ska.low.mccs.controller.controller_device.MccsController.Release`
        commands.
        """

        @pytest.fixture()
        def initial_mocks(self, mock_factory):
            """
            Fixture that registers device proxy mocks prior to patching.
            The default fixture is overridden here to ensure that mock
            subarrays and stations respond suitably to actions taken on
            them by the controller as part of the controller's
            :py:meth:`~ska.low.mccs.controller.controller_device.MccsController.Allocate`
            and
            :py:meth:`~ska.low.mccs.controller.controller_device.MccsController.Release`
            commands.

            :param mock_factory: a factory for
                :py:class:`tango.DeviceProxy` mocks
            :type mock_factory: object
            :return: a dictionary of mocks, keyed by FQDN
            :rtype: dict
            """
            mock_subarray_factory = MockSubarrayBuilder(mock_factory)

            mock_station_factory = MockDeviceBuilder(mock_factory)
            mock_station_factory.add_attribute("subarrayId", 0)

            return {
                "low-mccs/subarray/01": mock_subarray_factory(),
                "low-mccs/subarray/02": mock_subarray_factory(),
                "low-mccs/station/001": mock_station_factory(),
                "low-mccs/station/002": mock_station_factory(),
            }

        def test_Allocate(self, device_under_test, mock_event_callback, logger):
            """
            Test the Allocate command (including end of command event
            testing).

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test,
                in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param mock_event_callback: fixture that provides a mock
                instance with callback support methods
            :type mock_event_callback:
                :py:class:`pytest_mock.mocker.Mock`
            :param logger: the logger to be used by the object under test
            :type logger: :py:class:`logging.Logger`
            """
            controller = device_under_test  # for readability
            mock_subarray_1 = MccsDeviceProxy("low-mccs/subarray/01", logger)
            mock_subarray_2 = MccsDeviceProxy("low-mccs/subarray/02", logger)
            mock_station_1 = MccsDeviceProxy("low-mccs/station/001", logger)
            mock_station_2 = MccsDeviceProxy("low-mccs/station/002", logger)

            controller.Off()
            controller.On()

            call_with_json(
                device_under_test.simulateAdminModeChange,
                fqdn="low-mccs/station/001",
                admin_mode=AdminMode.ONLINE,
            )
            call_with_json(
                device_under_test.simulateHealthStateChange,
                fqdn="low-mccs/station/001",
                health_state=HealthState.OK,
            )
            call_with_json(
                device_under_test.simulateAdminModeChange,
                fqdn="low-mccs/station/002",
                admin_mode=AdminMode.ONLINE,
            )
            call_with_json(
                device_under_test.simulateHealthStateChange,
                fqdn="low-mccs/station/002",
                health_state=HealthState.OK,
            )

            # Test that subscription yields an event as expected
            _ = device_under_test.subscribe_event(
                "commandResult", tango.EventType.CHANGE_EVENT, mock_event_callback
            )
            mock_event_callback.check_event_data(name="commandResult", result=None)

            # Make the call to allocate
            ((result_code,), (_,)) = call_with_json(
                controller.Allocate,
                subarray_id=1,
                station_ids=[1],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(name="commandResult", result=None)

            # check that the mock subarray_1 was told to assign that resource
            mock_subarray_1.On.assert_called_once_with()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_called_once_with(
                json.dumps(
                    {
                        "stations": ["low-mccs/station/001"],
                        "subarray_beams": ["low-mccs/subarraybeam/01"],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                    }
                )
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
            ((result_code,), (_,)) = call_with_json(
                controller.Allocate,
                subarray_id=2,
                station_ids=[1],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.FAILED
            mock_event_callback.check_command_result(name="commandResult", result=None)

            # check no side-effects
            mock_subarray_1.On.assert_not_called()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_not_called()
            mock_subarray_2.On.assert_not_called()
            mock_subarray_2.ReleaseResources.assert_not_called()
            mock_subarray_2.AssignResources.assert_not_called()
            assert mock_station_1.subarrayId == 1
            assert mock_station_2.subarrayId == 0

            mock_subarray_1.reset_mock()
            mock_subarray_2.reset_mock()

            # allocating stations 1 and 2 to subarray 1 should succeed,
            # because the already allocated station is allocated to the same
            # subarray
            mock_subarray_1.AssignResources.side_effect = (
                (ResultCode.OK, MccsSubarray.AssignResourcesCommand.SUCCEEDED_MESSAGE),
            )

            ((result_code,), (_,)) = call_with_json(
                controller.Allocate,
                subarray_id=1,
                station_ids=[1, 2],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(name="commandResult", result=None)

            # check
            mock_subarray_1.On.assert_not_called()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_called_once_with(
                json.dumps(
                    {
                        "stations": ["low-mccs/station/002"],
                        "subarray_beams": ["low-mccs/subarraybeam/01"],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                    }
                )
            )
            mock_subarray_2.On.assert_not_called()
            mock_subarray_2.ReleaseResources.assert_not_called()
            mock_subarray_2.AssignResources.assert_not_called()
            assert mock_station_1.subarrayId == 1
            assert mock_station_2.subarrayId == 1

            mock_subarray_1.reset_mock()
            mock_subarray_2.reset_mock()

            # allocating station 2 to subarray 1 should succeed, because
            # it only requires resource release
            ((result_code,), (_,)) = call_with_json(
                controller.Allocate,
                subarray_id=1,
                station_ids=[2],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
            )

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

            ((result_code,), (_,)) = call_with_json(
                controller.Release, subarray_id=1, release_all=True
            )
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
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
            mock_subarray_1.reset_mock()
            mock_subarray_2.reset_mock()

            ((result_code,), (_,)) = call_with_json(
                controller.Allocate,
                subarray_id=2,
                station_ids=[1, 2],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
            )

            # check
            mock_subarray_1.On.assert_not_called()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_not_called()
            mock_subarray_2.On.assert_called_once_with()
            mock_subarray_2.ReleaseResources.assert_not_called()
            mock_subarray_2.AssignResources.assert_called_once_with(
                json.dumps(
                    {
                        "stations": ["low-mccs/station/001", "low-mccs/station/002"],
                        "subarray_beams": ["low-mccs/subarraybeam/01"],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                    }
                )
            )
            assert mock_station_1.subarrayId == 2
            assert mock_station_2.subarrayId == 2

        def test_Release(self, device_under_test, mock_event_callback, logger):
            """
            Test Release command.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param mock_event_callback: fixture that provides a mock instance
                with callback support methods
            :type mock_event_callback:
                :py:class:`pytest_mock.mocker.Mock`
            :param logger: the logger to be used by the object under
                test
            :type logger: :py:class:`logging.Logger`
            """
            controller = device_under_test  # for readability
            mock_subarray_1 = MccsDeviceProxy("low-mccs/subarray/01", logger)
            mock_subarray_2 = MccsDeviceProxy("low-mccs/subarray/02", logger)
            mock_station_1 = MccsDeviceProxy("low-mccs/station/001", logger)
            mock_station_2 = MccsDeviceProxy("low-mccs/station/002", logger)

            controller.Off()
            controller.On()

            call_with_json(
                device_under_test.simulateAdminModeChange,
                fqdn="low-mccs/station/001",
                admin_mode=AdminMode.ONLINE,
            )
            call_with_json(
                device_under_test.simulateHealthStateChange,
                fqdn="low-mccs/station/001",
                health_state=HealthState.OK,
            )
            call_with_json(
                device_under_test.simulateAdminModeChange,
                fqdn="low-mccs/station/002",
                admin_mode=AdminMode.ONLINE,
            )
            call_with_json(
                device_under_test.simulateHealthStateChange,
                fqdn="low-mccs/station/002",
                health_state=HealthState.OK,
            )

            call_with_json(
                controller.Allocate,
                subarray_id=1,
                station_ids=[1],
                subarray_beam_ids=[1],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            mock_subarray_1.On.assert_called_once_with()
            # check state
            assert mock_station_1.subarrayId == 1

            # allocate station 2 to subarray 2
            call_with_json(
                controller.Allocate,
                subarray_id=2,
                station_ids=[2],
                subarray_beam_ids=[2],
                channels=[[0, 8, 1, 1], [8, 8, 2, 1]],
            )
            mock_subarray_2.On.assert_called_once_with()
            # check state
            assert mock_station_1.subarrayId == 1
            assert mock_station_2.subarrayId == 2

            # Test that subscription yields an event as expected
            _ = device_under_test.subscribe_event(
                "commandResult", tango.EventType.CHANGE_EVENT, mock_event_callback
            )
            mock_event_callback.check_event_data(name="commandResult", result=None)

            # release all resources from subarray_2
            ((result_code,), (_,)) = call_with_json(
                controller.Release, subarray_id=2, release_all=True
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
            )

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
            ((result_code,), (_,)) = call_with_json(
                controller.Release, subarray_id=2, release_all=True
            )
            assert result_code == ResultCode.FAILED
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
            )

            # check no side-effect to failed release
            mock_subarray_1.ReleaseAllResources.assert_not_called()
            mock_subarray_1.Off.assert_not_called()
            mock_subarray_2.ReleaseAllResources.assert_not_called()
            mock_subarray_2.Off.assert_not_called()
            assert mock_station_1.subarrayId == 1
            assert mock_station_2.subarrayId == 0

            mock_subarray_1.reset_mock()
            mock_subarray_2.reset_mock()

            # release all resources from subarray_1
            ((result_code,), (_,)) = call_with_json(
                controller.Release, subarray_id=1, release_all=True
            )
            assert result_code == ResultCode.OK
            mock_event_callback.check_command_result(
                name="commandResult", result=result_code
            )

            # check all released
            mock_subarray_1.Off.assert_called_once_with()
            mock_subarray_1.ReleaseAllResources.assert_called_once_with()
            mock_subarray_2.Off.assert_not_called()
            mock_subarray_2.ReleaseAllResources.assert_not_called()
            assert mock_station_1.subarrayId == 0
            assert mock_station_2.subarrayId == 0

    def test_buildState(self, device_under_test):
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(self, device_under_test):
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    def test_healthState(self, device_under_test, mock_event_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_event_callback: fixture that provides a mock instance
            with callback support methods
        :type mock_event_callback: :py:class:`pytest_mock.mocker.Mock`
        """

        # The device has subscribed to healthState change events on
        # its subsidiary devices, but hasn't heard from them (because in
        # unit testing these devices are mocked out), so its healthState
        # is UNKNOWN
        assert device_under_test.healthState == HealthState.UNKNOWN

        # Test that subscription yields an event as expected
        _ = device_under_test.subscribe_event(
            "healthState", tango.EventType.CHANGE_EVENT, mock_event_callback
        )
        mock_event_callback.check_event_data(
            name="healthState", result=device_under_test.healthState
        )

        call_with_json(
            device_under_test.simulateAdminModeChange,
            fqdn="low-mccs/subrack/01",
            admin_mode=AdminMode.ONLINE,
        )
        call_with_json(
            device_under_test.simulateAdminModeChange,
            fqdn="low-mccs/station/001",
            admin_mode=AdminMode.ONLINE,
        )
        call_with_json(
            device_under_test.simulateAdminModeChange,
            fqdn="low-mccs/station/002",
            admin_mode=AdminMode.ONLINE,
        )

        call_with_json(
            device_under_test.simulateHealthStateChange,
            fqdn="low-mccs/subrack/01",
            health_state=HealthState.FAILED,
        )
        assert device_under_test.healthState == HealthState.UNKNOWN
        mock_event_callback.assert_not_called()

        call_with_json(
            device_under_test.simulateHealthStateChange,
            fqdn="low-mccs/station/001",
            health_state=HealthState.FAILED,
        )
        assert device_under_test.healthState == HealthState.UNKNOWN
        mock_event_callback.assert_not_called()

        call_with_json(
            device_under_test.simulateHealthStateChange,
            fqdn="low-mccs/station/002",
            health_state=HealthState.FAILED,
        )
        assert device_under_test.healthState == HealthState.FAILED
        mock_event_callback.check_event_data(
            name="healthState", result=device_under_test.healthState
        )

    def test_controlMode(self, device_under_test):
        """
        Test for controlMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """
        Test for simulationMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(self, device_under_test):
        """
        Test for testMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.testMode == TestMode.TEST

    def test_commandProgress(self, device_under_test):
        """
        Test for commandProgress.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.commandProgress == 0

    def test_commandDelayExpected(self, device_under_test):
        """
        Test for commandDelayExpected.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.commandDelayExpected == 0

    def test_maxCapabilities(self, device_under_test):
        """
        Test for maxCapabilities.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.maxCapabilities is None

    def test_availableCapabilities(self, device_under_test):
        """
        Test for availableCapabilities.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.availableCapabilities is None


class TestControllerResourceManager:
    """
    This class contains tests of the
    :py:class:`~ska.low.mccs.controller.controller_device.ControllerResourceManager`
    class.

    This class is already exercised through the Tango commands of
    Controller, but here we simulate some scenarios not covered.

    """

    @pytest.fixture()
    def resource_manager(self, device_under_test, logger):
        """
        Fixture that returns a resource manager with 2 managed stations.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`

        :return: a resource manager with 2 subservient station devices
        :rtype:
            :py:class:`ska.low.mccs.controller.controller_device.ControllerResourceManager`
        """
        self.stations = ["low-mccs/station/001", "low-mccs/station/002"]

        # Event manager to take health events
        self.event_manager = EventManager(logger, self.stations)
        self.health_model = HealthModel(None, self.stations, self.event_manager)
        # HACK pending device pool management refactor
        self.health_monitor = self.health_model._health_monitor

        # Instantiate a resource manager for the Stations
        manager = ControllerResourceManager(
            self.health_monitor, "Test Manager", self.stations, logger
        )
        return manager

    def test_assign(self, resource_manager):
        """
        Test assignment operations of the ControllerResourceManager.

        :param resource_manager: test fixture providing a manager object
        :type resource_manager:
            :py:class:`~ska.low.mccs.controller.controller_device.ControllerResourceManager`
        """
        stations = ("low-mccs/station/001", "low-mccs/station/002")
        # Assign both stations
        with pytest.raises(
            ValueError, match="does not pass health check for assignment"
        ):
            resource_manager.assign(stations, 1)

        for station in stations:
            resource_manager._resources[station]._health_changed(
                station, HealthState.OK
            )

        resource_manager.assign(stations, 1)

        # They should both be recorded as assigned
        assert stations == tuple(resource_manager.get_assigned_fqdns(1))

        # Drop station 2
        resource_manager.release(["low-mccs/station/002"])

        # It should now not be assigned
        assigned = resource_manager.get_assigned_fqdns(1)
        assert "low-mccs/station/002" not in assigned

        # Mock a health event so that station 2 is FAILED
        resource_manager._resources["low-mccs/station/002"]._health_changed(
            "low-mccs/station/002", HealthState.FAILED
        )

        with pytest.raises(
            ValueError,
            match="low-mccs/station/002 does not pass health check for assignment",
        ):
            resource_manager.assign(["low-mccs/station/002"], 1)

        # Mock a health event so that station 2 is OK again
        resource_manager._resources["low-mccs/station/002"]._health_changed(
            "low-mccs/station/002", HealthState.OK
        )

        # Assign it again
        resource_manager.assign(["low-mccs/station/002"], 1)

        # and check
        assigned = resource_manager.get_assigned_fqdns(1)
        assert "low-mccs/station/002" in assigned


class TestInitCommand:
    """
    Contains the tests of
    :py:class:`~ska.low.mccs.controller.controller_device.MccsController`'s
    :py:class:`~ska.low.mccs.controller.controller_device.MccsController.InitCommand`.
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

        def _initialise_device_pool(self, device):
            """
            Initialise the device pool for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            self._initialise_device_pool_called = True
            super()._initialise_device_pool(device)

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
        assert init_command._initialise_device_pool_called
        assert not init_command._initialise_health_monitoring_called
