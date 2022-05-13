# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsSubrack."""
from __future__ import annotations

import pytest
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_tango_base.executor import TaskStatus
from tango import DevState

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
        assert device_under_test.adminMode == AdminMode.OFFLINE
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

    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_attributes(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        # Subscribe to subrack's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )
        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        device_under_test.adminMode = AdminMode.ONLINE
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)
        assert device_under_test.adminMode == AdminMode.ONLINE

        ([result_code], [unique_id]) = device_under_test.On()
        assert result_code == ResultCode.QUEUED
        assert "_On" in unique_id

        message = '"On command has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

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

    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_PowerOnTpm(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerOnTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        # Subscribe to subrack's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )
        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        device_under_test.adminMode = AdminMode.ONLINE
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        ([result_code], [unique_id]) = device_under_test.On()
        assert result_code == ResultCode.QUEUED
        assert "_On" in unique_id
        message = '"On command has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

        tpm_id = 1
        ([result_code], [unique_id]) = device_under_test.PowerOnTpm(tpm_id)
        assert result_code == ResultCode.QUEUED
        assert "_PowerOnTpm" in unique_id
        message = f'"Subrack TPM {tpm_id} turn on tpm task has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

        # Issue redundant power on TPM command
        # ([result_code], [unique_id]) = device_under_test.PowerOnTpm(tpm_id)
        # assert result_code == ResultCode.QUEUED
        # assert "_PowerOnTpm" in unique_id
        # message =f'"Subrack TPM {tpm_id} power-on is redundant"'
        # lrc_result = (
        #     unique_id,
        #     message,
        #     )
        # lrc_result_changed_callback.assert_last_change_event(lrc_result)

    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_PowerOffTpm(
        self: TestMccsSubrack,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PowerOffTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        # Subscribe to subrack's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )
        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        device_under_test.adminMode = AdminMode.ONLINE
        ([result_code], [unique_id]) = device_under_test.On()
        assert result_code == ResultCode.QUEUED
        assert "_On" in unique_id

        message = '"On command has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

        tpm_id = 1
        # [[result_code], [unique_id]] = device_under_test.PowerOffTpm(tpm_id)
        # assert result_code == ResultCode.QUEUED
        # assert "_PowerOffTpm" in unique_id
        # lrc_result_changed_callback.assert_last_change_event(
        #     unique_id=unique_id,
        #     expected_message=f"Subrack TPM {tpm_id} power-off is redundant",
        # )

        ([result_code], [unique_id]) = device_under_test.PowerOnTpm(tpm_id)
        assert result_code == ResultCode.QUEUED
        assert "_PowerOnTpm" in unique_id
        message = f'"Subrack TPM {tpm_id} turn on tpm task has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

        ([result_code], [unique_id]) = device_under_test.PowerOffTpm(tpm_id)
        assert result_code == ResultCode.QUEUED
        assert "_PowerOffTpm" in unique_id
        message = f'"Subrack TPM {tpm_id} turn off tpm task has completed"'
        lrc_result = (
            unique_id,
            message,
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)
