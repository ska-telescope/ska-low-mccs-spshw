# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Contains the tests for the MccsController Tango device_under_test prototype."""
from __future__ import annotations

import time
import unittest

import pytest
import tango
from ska_control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy, release
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs import MccsController
from ska_low_mccs.controller.controller_component_manager import (
    ControllerComponentManager,
)


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

    def test_InitDevice(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Initialisation.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST
        assert device_under_test.State() == tango.DevState.DISABLE
        assert device_under_test.adminMode == AdminMode.OFFLINE
        assert device_under_test.Status() == "The device is in DISABLE state."

    def test_adminMode(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: ControllerComponentManager,
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

        time.sleep(0.2)

        mock_component_manager.start_communicating.assert_called_once_with()

        assert device_under_test.adminMode == AdminMode.ONLINE
        assert device_under_test.state() == tango.DevState.OFF

    @pytest.mark.parametrize(
        ("device_command", "component_method"),
        [
            ("On", "on"),
            ("Off", "off"),
            ("Standby", "standby"),
        ],
    )
    def test_command(
        self: TestMccsController,
        device_under_test: MccsDeviceProxy,
        device_command: str,
        mock_component_manager: unittest.mock.Mock,
        component_method: str,
        unique_id: str,
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
        :param unique_id: a unique id used to check Tango layer functionality
        """
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.adminMode == AdminMode.ONLINE
        [[result_code], [uid]] = getattr(device_under_test, device_command)()
        if result_code == ResultCode.REJECTED:
            assert uid == f"Device is already in {device_command.upper()} state."
        else:
            assert result_code == ResultCode.QUEUED
            assert uid.split("_")[-1] == device_command
            method = getattr(mock_component_manager, component_method)
            method.assert_called_once()
            assert len(method.call_args[0]) == 1

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
        assert device_under_test.buildState == "MCCS build state: " + binfo

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
        subarray_beam_fqdns: list[str],
        station_beam_fqdns: list[str],
        station_fqdns: list[str],
        mock_component_manager: unittest.mock.Mock,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param subarray_beam_fqdns: list of subarraybeam fqdns to check the
            callbacks from
        :param station_beam_fqdns: list of stationbeam fqdns to check the
            callbacks from
        :param station_fqdns: list of station fqdns to check the callbacks
            from
        :param mock_component_manager: a mock component manager that has
            been patched into the device under test
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        # The device has subscribed to healthState change events on
        # its subsidiary devices, but hasn't heard from them (because in
        # unit testing these devices are mocked out), so its healthState
        # is UNKNOWN
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.adminMode == AdminMode.ONLINE
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

        mock_component_manager._component_state_changed_callback(
            {"health_state": HealthState.FAILED}, "low-mccs/subrack/01"
        )

        device_health_state_changed_callback.assert_next_change_event(
            HealthState.FAILED
        )
        assert device_under_test.healthState == HealthState.FAILED

        mock_component_manager._component_state_changed_callback(
            {"health_state": HealthState.OK}, "low-mccs/subrack/01"
        )

        for beam_fqdn in subarray_beam_fqdns + station_beam_fqdns + station_fqdns:
            mock_component_manager._component_state_changed_callback(
                {"health_state": HealthState.OK}, beam_fqdn
            )

        # time.sleep(0.2)
        # device_health_state_changed_callback.assert_next_change_event(HealthState.UNKNOWN)
        device_health_state_changed_callback.assert_last_change_event(HealthState.OK)
        assert device_under_test.healthState == HealthState.OK

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