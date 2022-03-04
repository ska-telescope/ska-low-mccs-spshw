# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of the device_component_manager module."""
from __future__ import annotations

import logging
import time
import unittest.mock

import pytest
import tango
from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs.component import CommunicationStatus, DeviceComponentManager
from ska_low_mccs.testing import TangoHarness
from ska_low_mccs.testing.mock import MockCallable, MockChangeEventCallback


@pytest.fixture()
def component_manager(
    tango_harness: TangoHarness,
    fqdn: str,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_power_mode_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    health_changed_callback: MockCallable,
) -> DeviceComponentManager:
    """
    Return a device component manager for testing.

    :param tango_harness: a test harness for MCCS tango devices
    :param fqdn: the FQDN of the device to be managed by this component
        manager.
    :param logger: a logger for the component manager to use.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param health_changed_callback: callback to be called when the
        health state of the device changes. The value it is called
        with will normally be a HealthState, but may be None if the
        admin mode of the device indicates that the device's health
        should not be included in upstream health rollup.

    :return: a device component manager for testing.
    """
    return DeviceComponentManager(
        fqdn,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        health_changed_callback,
    )


class TestDeviceComponentManager:
    """Tests of the DeviceComponentManager class."""

    def test_communication(
        self: TestDeviceComponentManager,
        component_manager: DeviceComponentManager,
        communication_status_changed_callback: MockCallable,
    ) -> None:
        """
        Test the component manager's communication with the device.

        :param component_manager: the component manager under test
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        assert component_manager.communication_status == CommunicationStatus.DISABLED
        component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert component_manager.communication_status == CommunicationStatus.ESTABLISHED

        component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert component_manager.communication_status == CommunicationStatus.DISABLED

    @pytest.mark.parametrize(
        ("component_manager_command", "device_command"),
        [
            ("on", "On"),
            ("standby", "Standby"),
            ("off", "Off"),
            ("reset", "Reset"),
        ],
    )
    def test_command(
        self: TestDeviceComponentManager,
        component_manager: DeviceComponentManager,
        mock_proxy: unittest.mock.Mock,
        component_manager_command: str,
        device_command: str,
    ) -> None:
        """
        Test command execution.

        :param component_manager: the component manager under test
        :param mock_proxy: a mock proxy to the component device
        :param component_manager_command: the name of the command to the
            component manager
        :param device_command: the name of the command that is expected
            to be called on the device.
        """
        with pytest.raises(
            ConnectionError,
            match="Communication with component is not established",
        ):
            getattr(component_manager, component_manager_command)()
        getattr(mock_proxy, device_command).assert_not_called()

        component_manager.start_communicating()
        time.sleep(0.1)

        getattr(component_manager, component_manager_command)()
        mock_command = getattr(mock_proxy, device_command)
        mock_command.assert_next_call()

    def test_health(
        self: TestDeviceComponentManager,
        component_manager: DeviceComponentManager,
        health_changed_callback: MockCallable,
    ) -> None:
        """
        Test the component managers handling of health.

        :param component_manager: the component manager under test
        :param health_changed_callback: callback to be called when the
            health status of the device changes
        """
        assert component_manager.health is None

        component_manager._device_admin_mode_changed(
            "adminMode", AdminMode.ONLINE, tango.AttrQuality.ATTR_VALID
        )
        assert component_manager.health == HealthState.UNKNOWN
        health_changed_callback.assert_next_call(HealthState.UNKNOWN)

        component_manager._device_health_state_changed(
            "healthState", HealthState.DEGRADED, tango.AttrQuality.ATTR_VALID
        )
        assert component_manager.health == HealthState.DEGRADED
        health_changed_callback.assert_next_call(HealthState.DEGRADED)

        component_manager._device_admin_mode_changed(
            "adminMode", AdminMode.RESERVED, tango.AttrQuality.ATTR_VALID
        )
        assert component_manager.health is None
        health_changed_callback.assert_next_call(None)

        component_manager._device_admin_mode_changed(
            "adminMode", AdminMode.ONLINE, tango.AttrQuality.ATTR_VALID
        )
        assert component_manager.health == HealthState.DEGRADED
        health_changed_callback.assert_next_call(HealthState.DEGRADED)
