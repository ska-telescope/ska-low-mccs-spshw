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
"""This module contains the tests for MccsSubrack."""
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
from ska_low_mccs.subrack import SubrackSimulator


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
        "device": "subrack_01",
        "proxy": MccsDeviceProxy,
    }


class TestMccsSubrack:
    """Test class for MccsSubrack tests."""

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subrack/01")

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

    def test_attributes(self, device_under_test):
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()

        assert (
            list(device_under_test.backplaneTemperatures)
            == SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURE
        )
        assert (
            list(device_under_test.boardTemperatures)
            == SubrackSimulator.DEFAULT_BOARD_TEMPERATURE
        )
        assert device_under_test.boardCurrent == SubrackSimulator.DEFAULT_BOARD_CURRENT
        assert (
            list(device_under_test.subrackFanSpeeds)
            == SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
        )
        assert (
            list(device_under_test.powerSupplyFanSpeeds)
            == SubrackSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEEDS
        )
        assert device_under_test.powerSupplyCurrents == pytest.approx(
            SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENT
        )
        assert device_under_test.powerSupplyVoltages == pytest.approx(
            SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE
        )

        assert (
            list(device_under_test.powerSupplyPowers)
            == SubrackSimulator.DEFAULT_POWER_SUPPLY_POWER
        )
        assert (
            list(device_under_test.tpmTemperatures)
            == [SubrackSimulator.DEFAULT_TPM_TEMPERATURE] * device_under_test.tpmCount
        )
        assert list(device_under_test.tpmCurrents) == pytest.approx(
            [SubrackSimulator.DEFAULT_TPM_CURRENT] * device_under_test.tpmCount
        )
        assert list(device_under_test.tpmPowers) == pytest.approx(
            [SubrackSimulator.DEFAULT_TPM_POWER] * device_under_test.tpmCount
        )
        assert list(device_under_test.tpmVoltages) == pytest.approx(
            [SubrackSimulator.DEFAULT_TPM_VOLTAGE] * device_under_test.tpmCount
        )

    def test_PowerOnTpm(self, device_under_test):
        """
        Test for PowerOnTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on successful"

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on is redundant"

    def test_PowerOffTpm(self, device_under_test):
        """
        Test for PowerOffTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off is redundant"

        _ = device_under_test.PowerOnTpm(1)

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off successful"
