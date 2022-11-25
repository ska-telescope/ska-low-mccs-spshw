# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsAPIU."""
from __future__ import annotations

import time

import pytest
from ska_control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs.apiu import ApiuSimulator


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "apiu_001",
        "proxy": MccsDeviceProxy,
    }


class TestMccsAPIU:
    """Test class for MccsAPIU tests."""

    @pytest.fixture()
    def device_under_test(
        self: TestMccsAPIU, tango_harness: TangoHarness
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/apiu/001")

    def test_InitDevice(self: TestMccsAPIU, device_under_test: MccsDeviceProxy) -> None:
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.adminMode == AdminMode.OFFLINE
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

    def test_healthState(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

    def test_attributes(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()
        time.sleep(0.1)

        assert device_under_test.temperature == ApiuSimulator.DEFAULT_TEMPERATURE
        assert device_under_test.humidity == ApiuSimulator.DEFAULT_HUMIDITY
        assert device_under_test.voltage == ApiuSimulator.DEFAULT_VOLTAGE
        assert device_under_test.current == ApiuSimulator.DEFAULT_CURRENT
        assert device_under_test.isAlive
        assert device_under_test.overCurrentThreshold == 0.0
        assert device_under_test.overVoltageThreshold == 0.0
        assert device_under_test.humidityThreshold == 0.0

        device_under_test.overCurrentThreshold = 22.0
        assert device_under_test.overCurrentThreshold == 22.0
        device_under_test.overVoltageThreshold = 6.0
        assert device_under_test.overVoltageThreshold == 6.0
        device_under_test.humidityThreshold = 60.0
        assert device_under_test.humidityThreshold == 60.0

    def test_PowerUp(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerUp.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerUp"

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerUp"

    def test_PowerDown(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerDown.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerDown"

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerDown"

    def test_PowerUpAntenna(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerUpAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()
        time.sleep(0.1)

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerUpAntenna"
        time.sleep(0.1)

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerUpAntenna"
        time.sleep(0.1)

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

    def test_PowerDownAntenna(
        self: TestMccsAPIU,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerDownAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()
        time.sleep(0.1)

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerDownAntenna"
        time.sleep(0.1)

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        _ = device_under_test.PowerUpAntenna(1)
        time.sleep(0.1)

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PowerDownAntenna"
        time.sleep(0.1)

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount
