# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsSubrack."""
from __future__ import annotations

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
from ska_low_mccs.subrack import SubrackSimulator
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
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
    def device_under_test(
        self: TestMccsSubrack, tango_harness: TangoHarness
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subrack/01")

    def test_InitDevice(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.state() == DevState.DISABLE
        assert device_under_test.status() == "The device is in DISABLE state."
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.testMode == TestMode.TEST

    def test_healthState(
        self: TestMccsSubrack,
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
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()
        time.sleep(0.1)

        assert (
            list(device_under_test.backplaneTemperatures)
            == SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURES
        )
        assert (
            list(device_under_test.boardTemperatures)
            == SubrackSimulator.DEFAULT_BOARD_TEMPERATURES
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
            SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENTS
        )
        assert device_under_test.powerSupplyVoltages == pytest.approx(
            SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGES
        )

        assert (
            list(device_under_test.powerSupplyPowers)
            == SubrackSimulator.DEFAULT_POWER_SUPPLY_POWERS
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

    def test_PowerOnTpm(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for PowerOnTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on successful"
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on is redundant"

    def test_PowerOffTpm(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for PowerOffTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off is redundant"
        time.sleep(0.1)

        _ = device_under_test.PowerOnTpm(1)
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off successful"
