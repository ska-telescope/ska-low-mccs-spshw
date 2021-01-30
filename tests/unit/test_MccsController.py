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
import logging
import threading
import time

import pytest
import tango
from tango import AttrQuality, DevState
from tango.server import command

from ska.base import DeviceStateModel
from ska.base.commands import CommandError, ResultCode
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs.controller import (
    MccsController,
    ControllerPowerManager,
    ControllerResourceManager,
)
from ska.low.mccs import release
from ska.low.mccs.utils import call_with_json
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel


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
        args = json.loads(argin)
        fqdn = args["fqdn"]
        health = args["health_state"]

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
        args = json.loads(argin)
        fqdn = args["fqdn"]
        admin_mode = args["admin_mode"]

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
    :type mocker: wrapper for :py:mod:`unittest.mock`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an
        instance)
    """
    _values = {"healthState": HealthState.UNKNOWN, "adminMode": AdminMode.ONLINE}

    def _mock_attribute(name, *args, **kwargs):
        """
        Returns a mock of a :py:class:`tango.DeviceAttribute` instance,
        for a given attribute name.

        :param name: name of the attribute
        :type name: str
        :param args: positional args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type args: list
        :param kwargs: named args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type kwargs: dict

        :return: a basic mock for a :py:class:`tango.DeviceAttribute`
            instance, with name, value and quality values
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.name = name
        mock.value = _values.get(name, "MockValue")
        mock.quality = "MockQuality"
        return mock

    def _mock_device():
        """
        Returns a mock for a :py:class:`tango.DeviceProxy` instance,
        with its :py:meth:`tango.DeviceProxy.read_attribute` method
        mocked to return :py:class:`tango.DeviceAttribute` mocks.

        :return: a basic mock for a :py:class:`tango.DeviceProxy`
            instance,
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.read_attribute.side_effect = _mock_attribute
        return mock

    return _mock_device


class TestMccsController:
    """
    Tests of the MccsController device.
    """

    @staticmethod
    def _callback_event_data_check(mock_callback, name, result):
        """
        :param mock_callback: fixture that provides a mock callback object
            that records registered callbacks from the DUT
        :type mock_callback: :py:class:`tango.DeviceProxy`
        :param name: name of the registered event
        :type name: str
        :param result: return code from the completed command
            If set to None, value and quaility checks are bypassed
        :type result: :py:class:`~ska.base.commands.ResultCode`
        """
        # push_change_event isn't synchronous, because it has to go
        # through the 0MQ event system. So we have to sleep long enough
        # for the event to arrive
        time.sleep(0.2)

        mock_callback.assert_called_once()
        event_data = mock_callback.call_args[0][0].attr_value

        assert event_data.name.lower() == name.lower()
        if result is not None:
            assert event_data.value == result
            assert event_data.quality == tango.AttrQuality.ATTR_VALID
        mock_callback.reset_mock()

    @staticmethod
    def _callback_commandResult_check(mock_callback, name, result):
        """
        Special callback check routine for commandResult.
        There should always be two entries for commandResult; the first
        should reset commandResult to ResultCode.UNKNOWN, the second
        should match the expected result passed into this routine.

        :param mock_callback: fixture that provides a mock callback object
            that records registered callbacks from the DUT
        :type mock_callback: :py:class:`tango.DeviceProxy`
        :param name: name of the registered event
        :type name: str
        :param result: return code from the completed command
            If set to None, value and quaility checks are bypassed
        :type result: :py:class:`~ska.base.commands.ResultCode`
        """
        # push_change_event isn't synchronous, because it has to go
        # through the 0MQ event system. So we have to sleep long enough
        # for the event to arrive
        time.sleep(0.2)

        mock_callback.assert_called()
        assert len(mock_callback.mock_calls) == 2  # exactly two calls

        first_event_data = mock_callback.mock_calls[0][1][0].attr_value
        second_event_data = mock_callback.mock_calls[1][1][0].attr_value
        assert first_event_data.name.lower() == name.lower()
        assert second_event_data.name.lower() == name.lower()
        assert first_event_data.value == ResultCode.UNKNOWN
        assert first_event_data.quality == tango.AttrQuality.ATTR_VALID
        if result is not None:
            assert second_event_data.value == result
            assert second_event_data.quality == tango.AttrQuality.ATTR_VALID
        mock_callback.reset_mock()

    def test_State(self, device_under_test):
        """
        Test for State.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.State() == tango.DevState.OFF

    def test_Status(self, device_under_test):
        """
        Test for Status.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.Status() == "The device is in OFF state."

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
            match="Command Reset not allowed when the device is in OFF state",
        ):
            device_under_test.Reset()

    def test_On(self, device_under_test, mocker):
        """
        Test for On (including end of command event testing).

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        # Test that subscription yields an event as expected
        mock_callback = mocker.Mock()
        _ = device_under_test.subscribe_event(
            "commandResult", tango.EventType.CHANGE_EVENT, mock_callback
        )
        TestMccsController._callback_event_data_check(
            mock_callback=mock_callback, name="commandResult", result=None
        )

        # Call the On() command on the Controller device
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"
        TestMccsController._callback_commandResult_check(
            mock_callback=mock_callback, name="commandResult", result=result_code
        )

    def test_Off(self, device_under_test, mocker):
        """
        Test for Off (including end of command event testing).

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        controller = device_under_test  # for readability
        # Need to turn it on before we can turn it off
        controller.On()

        # Test that subscription yields an event as expected
        mock_callback = mocker.Mock()
        _ = controller.subscribe_event(
            "commandResult", tango.EventType.CHANGE_EVENT, mock_callback
        )
        TestMccsController._callback_event_data_check(
            mock_callback=mock_callback, name="commandResult", result=None
        )

        # Call the Off() command on the Controller device
        [[result_code], [message]] = controller.Off()
        assert result_code == ResultCode.OK
        assert message == "Off command completed OK"
        TestMccsController._callback_commandResult_check(
            mock_callback=mock_callback, name="commandResult", result=result_code
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
        assert message == "Stub implementation of StandbyLowCommand(), does nothing"

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
        assert message == "Stub implementation of StandbyFullCommand(), does nothing"

    def test_Operate(self, device_under_test):
        """
        Test for Operate.

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
        Test for Maintenance.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # assert device_under_test.Maintenance() is None
        [[result_code], [message]] = device_under_test.Maintenance()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of Maintenance(), does nothing"

    class TestAllocateRelease:
        """
        Class containing fixtures and tests of the MccsController's
        :py:meth:`~ska.low.mccs.MccsController.Allocate` and
        :py:meth:`~ska.low.mccs.MccsController.Release` commands
        """

        @pytest.fixture()
        def initial_mocks(self, mock_factory):
            """
            Fixture that registers device proxy mocks prior to patching.
            The default fixture is overridden here to ensure that mock
            subarrays and stations respond suitably to actions taken on
            them by the controller as part of the controller's
            :py:meth:`~ska.low.mccs.MccsController.Allocate` and
            :py:meth:`~ska.low.mccs.MccsController.Release` commands

            :param mock_factory: a factory for
                :py:class:`tango.DeviceProxy` mocks
            :type mock_factory: object
            :return: a dictionary of mocks, keyed by FQDN
            :rtype: dict
            """

            def _subarray_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.MccsSubarray`
                device. The returned mock will respond suitably to
                actions taken on it by the controller as part of the
                controller's
                :py:meth:`~ska.low.mccs.MccsController.Allocate` and
                :py:meth:`~ska.low.mccs.MccsController.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.MccsSubarray` device.
                :rtype: :py:class:`unittest.Mock`
                """
                mock = mock_factory()
                mock.On.return_value = (
                    ResultCode.OK,
                    "On command completed successfully",
                )
                mock.AssignResources.return_value = (
                    ResultCode.OK,
                    "Resources assigned",
                )
                mock.ReleaseResources.return_value = (
                    ResultCode.OK,
                    "Resources released",
                )
                mock.ReleaseAllResources.return_value = (
                    ResultCode.OK,
                    "Resources released",
                )
                mock.Off.return_value = (ResultCode.OK, "Subarray switched off")
                return mock

            def _station_mock():
                """
                Sets up a mock for a :py:class:`tango.DeviceProxy` that
                connects to an :py:class:`~ska.low.mccs.MccsStation`
                device. The returned mock will respond suitably to
                actions taken on it by the controller as part of the
                controller's
                :py:meth:`~ska.low.mccs.MccsController.Allocate` and
                :py:meth:`~ska.low.mccs.MccsController.Release`
                commands.

                :return: a mock for a :py:class:`tango.DeviceProxy` that
                    connects to an
                    :py:class:`~ska.low.mccs.MccsStation` device.
                :rtype: :py:class:`unittest.Mock`
                """
                mock = mock_factory()
                mock.subarrayId = 0
                return mock

            return {
                "low-mccs/subarray/01": _subarray_mock(),
                "low-mccs/subarray/02": _subarray_mock(),
                "low-mccs/station/001": _station_mock(),
                "low-mccs/station/002": _station_mock(),
            }

        def test_Allocate(self, device_under_test, mocker):
            """
            Test the Allocate command (including end of command event
            testing).

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param mocker: fixture that wraps unittest.Mock
            :type mocker: wrapper for :py:mod:`unittest.mock`
            """
            controller = device_under_test  # for readability
            mock_subarray_1 = tango.DeviceProxy("low-mccs/subarray/01")
            mock_subarray_2 = tango.DeviceProxy("low-mccs/subarray/02")
            mock_station_1 = tango.DeviceProxy("low-mccs/station/001")
            mock_station_2 = tango.DeviceProxy("low-mccs/station/002")

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
            mock_callback = mocker.Mock()
            _ = device_under_test.subscribe_event(
                "commandResult", tango.EventType.CHANGE_EVENT, mock_callback
            )
            TestMccsController._callback_event_data_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )

            # Make the call to allocate
            ((result_code,), (_,)) = call_with_json(
                controller.Allocate, subarray_id=1, station_ids=[1]
            )
            assert result_code == ResultCode.OK
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )

            # check that the mock subarray_1 was told to assign that resource
            mock_subarray_1.On.assert_called_once_with()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_called_once_with(
                json.dumps({"stations": ["low-mccs/station/001"], "station_beams": []})
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
                controller.Allocate, subarray_id=2, station_ids=[1]
            )
            assert result_code == ResultCode.FAILED
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )

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

            ((result_code,), (_,)) = call_with_json(
                controller.Allocate, subarray_id=1, station_ids=[1, 2]
            )
            assert result_code == ResultCode.OK
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )

            # check
            mock_subarray_1.On.assert_not_called()
            mock_subarray_1.ReleaseResources.assert_not_called()
            mock_subarray_1.AssignResources.assert_called_once_with(
                json.dumps({"stations": ["low-mccs/station/002"], "station_beams": []})
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
                controller.Allocate, subarray_id=1, station_ids=[2]
            )
            assert result_code == ResultCode.OK
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=result_code
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
            time.sleep(0.2)  # RCL???
            mock_callback.reset_mock()
            ((result_code,), (_,)) = call_with_json(
                controller.Allocate, subarray_id=2, station_ids=[1, 2]
            )
            assert result_code == ResultCode.OK
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=result_code
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
                        "station_beams": [],
                    }
                )
            )
            assert mock_station_1.subarrayId == 2
            assert mock_station_2.subarrayId == 2

        def test_Release(self, device_under_test, mocker):
            """
            Test Release command.

            :param device_under_test: fixture that provides a
                :py:class:`tango.DeviceProxy` to the device under test, in a
                :py:class:`tango.test_context.DeviceTestContext`.
            :type device_under_test: :py:class:`tango.DeviceProxy`
            :param mocker: fixture that wraps unittest.Mock
            :type mocker: wrapper for :py:mod:`unittest.mock`
            """
            controller = device_under_test  # for readability
            mock_subarray_1 = tango.DeviceProxy("low-mccs/subarray/01")
            mock_subarray_2 = tango.DeviceProxy("low-mccs/subarray/02")
            mock_station_1 = tango.DeviceProxy("low-mccs/station/001")
            mock_station_2 = tango.DeviceProxy("low-mccs/station/002")

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

            call_with_json(controller.Allocate, subarray_id=1, station_ids=[1])
            mock_subarray_1.On.assert_called_once_with()
            # check state
            assert mock_station_1.subarrayId == 1

            # allocate station 2 to subarray 2
            call_with_json(controller.Allocate, subarray_id=2, station_ids=[2])
            mock_subarray_2.On.assert_called_once_with()
            # check state
            assert mock_station_1.subarrayId == 1
            assert mock_station_2.subarrayId == 2

            # Test that subscription yields an event as expected
            mock_callback = mocker.Mock()
            _ = device_under_test.subscribe_event(
                "commandResult", tango.EventType.CHANGE_EVENT, mock_callback
            )
            TestMccsController._callback_event_data_check(
                mock_callback=mock_callback, name="commandResult", result=None
            )

            # release all resources from subarray_2
            ((result_code,), (_,)) = call_with_json(
                controller.Release, subarray_id=2, release_all=True
            )
            assert result_code == ResultCode.OK
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=result_code
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
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=result_code
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
            TestMccsController._callback_commandResult_check(
                mock_callback=mock_callback, name="commandResult", result=result_code
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

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """

        # The device has subscribed to healthState change events on
        # its subsidiary, but hasn't heard from them (because in unit
        # testing these devices are mocked out), so its healthState is
        # UNKNOWN
        assert device_under_test.healthState == HealthState.UNKNOWN

        # Test that subscription yields an event as expected
        mock_callback = mocker.Mock()
        _ = device_under_test.subscribe_event(
            "healthState", tango.EventType.CHANGE_EVENT, mock_callback
        )
        TestMccsController._callback_event_data_check(
            mock_callback=mock_callback,
            name="healthState",
            result=device_under_test.healthState,
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
            fqdn="low-mccs/station/001",
            health_state=HealthState.FAILED,
        )
        assert device_under_test.healthState == HealthState.UNKNOWN
        mock_callback.assert_not_called()

        call_with_json(
            device_under_test.simulateHealthStateChange,
            fqdn="low-mccs/station/002",
            health_state=HealthState.FAILED,
        )
        assert device_under_test.healthState == HealthState.FAILED
        TestMccsController._callback_event_data_check(
            mock_callback=mock_callback,
            name="healthState",
            result=device_under_test.healthState,
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
        assert device_under_test.testMode == TestMode.NONE

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


class TestControllerPowerManager:
    """
    This class contains tests of the `:py:class:~ska.low.mccs.controller
    .controller_device.ControllerPowerManager` class.
    """

    @pytest.fixture()
    def logger(self):
        """
        Fixture that returns a logger for the power manager under test
        (or its components) to use.

        :return: a logger for the power manager under test to use
        :rtype: :py:class:`logging.Logger` or an object that implement
           its logging interface
        """
        return logging.getLogger()

    @pytest.fixture()
    def power_manager(self):
        """
        Fixture that returns a power manager with no hardware manager
        and no subservient devices.

        :return: a power manager with no hardware manager and no
            subservient devices
        :rtype: :py:class:`ska.low.mccs.power.PowerManager`
        """
        return ControllerPowerManager([])

    @pytest.fixture()
    def state_model(self, logger):
        """
        Fixture that returns a state model for the command under test to
        use.

        :param logger: a logger for the state model to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface

        :return: a state model for the command under test to use
        :rtype: :py:class:`~ska.base.DeviceStateModel`
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
        :type state_model: :py:class:`~ska.base.DeviceStateModel`
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
        :type state_model: :py:class:`~ska.base.DeviceStateModel`
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
    This class contains tests of the `:py:class:~ska.low.mccs.controller
    .controller_device.ControllerResourceManager` class.

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
            self.health_monitor, "Test Manager", self.stations
        )
        return manager

    def test_assign(self, resource_manager):
        """
        Test assignment operations of the ControllerResourceManager.

        :param resource_manager: test fixture providing a manager object
        :type resource_manager: ControllerResourceManager
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
            Create a new HangableInitCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska.base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_health_monitoring_called = False
            self._initialise_power_management_called = False

        def _initialise_health_monitoring(self, device, fqdns):
            """
            Initialise the health model for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device monitors health
            :type: list(str)
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
            :type: list(str)
            """
            self._initialise_power_management_called = True
            super()._initialise_power_management(device, fqdns)

    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely.

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
