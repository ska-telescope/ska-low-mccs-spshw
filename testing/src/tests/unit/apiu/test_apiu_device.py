# type: ignore
###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""This module contains the tests for MccsAPIU."""
import time

import pytest
from tango import DevState

from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.apiu import ApiuSimulator


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
        "device": "apiu_001",
        "proxy": MccsDeviceProxy,
    }


class TestMccsAPIU:
    """Test class for MccsAPIU tests."""

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/apiu/001")

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.state() == DevState.DISABLE
        assert device_under_test.status() == "The device is in DISABLE state."
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.testMode == TestMode.TEST

    def test_healthState(self, device_under_test, device_health_state_changed_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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

    def test_attributes(self, device_under_test, device_admin_mode_changed_callback):
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
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

    def test_PowerUp(self, device_under_test, device_admin_mode_changed_callback):
        """
        Test for PowerUp.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up successful"

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up is redundant"

    def test_PowerDown(self, device_under_test, device_admin_mode_changed_callback):
        """
        Test for PowerDown.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down is redundant"

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down successful"

    def test_PowerUpAntenna(
        self, device_under_test, device_admin_mode_changed_callback
    ):
        """
        Test for PowerUpAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-up successful"

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-up is redundant"

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

    def test_PowerDownAntenna(
        self, device_under_test, device_admin_mode_changed_callback
    ):
        """
        Test for PowerDownAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.On()

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-down is redundant"

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        _ = device_under_test.PowerUpAntenna(1)

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-down successful"

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount
