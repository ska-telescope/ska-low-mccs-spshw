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
"""Contains the tests for the MccsController Tango device_under_test prototype."""
from __future__ import annotations

import unittest

import pytest
import tango

from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_tango_base.commands import ResultCode
from ska_low_mccs import MccsController, MccsDeviceProxy, release
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load(
    patched_controller_device_class: type[MccsController],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_controller_device_class: a controller device class
        that has been patched with a mock component manager

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "controller",
        "proxy": MccsDeviceProxy,
        "patch": patched_controller_device_class,
    }


@pytest.fixture()
def device_under_test(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/control/control")


class TestMccsController:
    """Tests of the MccsController device."""

    def test_State(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for State.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.State() == tango.DevState.DISABLE

    def test_Status(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Status.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.Status() == "The device is in DISABLE state."

    def test_GetVersionInfo(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        # Subscribe to controller's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )
        initial_lrc_result = ("", "", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(
            initial_lrc_result
        )

        vinfo = release.get_release_info(device_under_test.info().dev_class)

        # Message queue length is non-zero so command is queued
        ([result_code], [unique_id]) = device_under_test.GetVersionInfo()
        assert result_code == ResultCode.QUEUED
        assert "GetVersionInfo" in unique_id

        return
        lrc_result = (
            unique_id,
            str(ResultCode.OK.value),
            "Controller On command completed OK",
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

        assert device_under_test.GetVersionInfo() == [vinfo]

    def test_adminMode(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
    ) -> None:
        """
        Test adminMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: a mock component manager that has
            been patched into the device under test
        """
        assert device_under_test.adminMode == AdminMode.OFFLINE
        assert device_under_test.state() == tango.DevState.DISABLE

        device_under_test.adminMode = AdminMode.ONLINE
        mock_component_manager.start_communicating.assert_called_once_with()

        assert device_under_test.adminMode == AdminMode.ONLINE
        assert device_under_test.state() == tango.DevState.OFF

    @pytest.mark.parametrize(
        ("device_command", "component_method"),
        [
            ("Off", "off"),
            ("Standby", "standby"),
            ("On", "on"),
        ],
    )
    def test_command(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        device_command: str,
        mock_component_manager: unittest.mock.Mock,
        component_method: str,
    ) -> None:
        """
        Test that device commands are passed through to the component manager.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_command: name of the device command
        :param mock_component_manager: a mock component manager that has
            been patched into the device under test
        :param component_method: name of the component method that
            implements the device command
        """
        device_under_test.adminMode = AdminMode.ONLINE
        getattr(device_under_test, device_command)()
        getattr(mock_component_manager, component_method).assert_called_once_with()

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Reset.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            tango.DevFailed,
            match="Command Reset not allowed when the device is in DISABLE state",
        ):
            device_under_test.Reset()

    def test_buildState(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.versionId == release.version

    def test_healthState(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: a mock component manager that has
            been patched into the device under test
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        # The device has subscribed to healthState change events on
        # its subsidiary devices, but hasn't heard from them (because in
        # unit testing these devices are mocked out), so its healthState
        # is UNKNOWN
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

        mock_component_manager._subrack_health_changed_callback(
            "low-mccs/subrack/01",
            HealthState.FAILED,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.FAILED
        )
        assert device_under_test.healthState == HealthState.FAILED

        mock_component_manager._subrack_health_changed_callback(
            "low-mccs/subrack/01",
            HealthState.OK,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

    def test_controlMode(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for controlMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for simulationMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for testMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.testMode == TestMode.TEST

    def test_maxCapabilities(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for maxCapabilities.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.maxCapabilities is None

    def test_availableCapabilities(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for availableCapabilities.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.availableCapabilities is None
