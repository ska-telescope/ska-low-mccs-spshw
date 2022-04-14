# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsSubarray."""
from __future__ import annotations

import json
import time
import unittest
from typing import Callable, Type

import pytest
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ObsState,
    PowerState,
    SimulationMode,
    TestMode,
)
from ska_tango_base.executor import TaskStatus
from tango import DevState
from tango.server import command

from ska_low_mccs import MccsDeviceProxy, MccsSubarray, release
from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.testing.mock.mock_callable import MockCallable
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def patched_subarray_device_class() -> Type[MccsSubarray]:
    """
    Return a subarray device class, patched with extra methods for testing.

    :return: a patched subarray device class, patched with extra methods
        for testing
    """

    class PatchedSubarrayDevice(MccsSubarray):
        """
        MccsSubarray patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of obs state
        change events from subservient devices.
        """

        @command(dtype_in=int)
        def FakeSubservientDevicesObsState(
            self: PatchedSubarrayDevice, obs_state: ObsState
        ) -> None:
            obs_state = ObsState(obs_state)

            for fqdn in self.component_manager._device_obs_states:
                self.component_manager._device_obs_state_changed(fqdn, obs_state)

    return PatchedSubarrayDevice


@pytest.fixture()
def device_to_load(
    patched_subarray_device_class: type[MccsSubarray],
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_subarray_device_class: a class for a patched subarray
        device with extra methods for testing purposes.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "subarray_01",
        "proxy": MccsDeviceProxy,
        "patch": patched_subarray_device_class,
    }


@pytest.fixture()
def mock_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a mock factory for device proxy mocks.

    This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :return: a factory for device proxy mocks
    """
    builder = MockDeviceBuilder()
    builder.add_attribute("healthState", HealthState.UNKNOWN)
    builder.add_attribute("adminMode", AdminMode.ONLINE)
    return builder


class TestMccsSubarray:
    """Test class for MccsSubarray tests."""

    @pytest.fixture()
    def device_under_test(
        self: TestMccsSubarray, tango_harness: TangoHarness
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/subarray/01")

    def test_InitDevice(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Initial state.

        :todo: Test for different memorized values of adminMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

        # The following reads might not be allowed in this state once
        # properly implemented
        assert device_under_test.scanId == -1
        assert device_under_test.stationFQDNs is None
        # No activationTime attr?
        # assert device_under_test.activationTime == 0

    def test_healthState(
        self: TestMccsSubarray,
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

    def test_GetVersionInfo(
        self: TestMccsSubarray,
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
        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        # GetVersionInfo appears to have changed. Maybe missing a cmd obj
        ([result_code], [unique_id]) = device_under_test.GetVersionInfo()
        assert result_code == TaskStatus.QUEUED
        assert "GetVersionInfo" in unique_id

        vinfo = release.get_release_info(device_under_test.info().dev_class)
        lrc_result = (
            unique_id,
            str(ResultCode.OK.value),
            str([vinfo]),
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)

    def test_buildState(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    def test_versionId(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.versionId == release.version

    def test_scanId(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for scanID attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.scanId == -1

    def test_stationFQDNs(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for stationFQDNs attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.stationFQDNs is None

    def test_assignResources(
        self: TestMccsSubarray,
        lrc_result_changed_callback: MockChangeEventCallback,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        station_on_fqdn: str,
        subarray_beam_on_fqdn: str,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
        component_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test for assignResources.

        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param station_on_fqdn: the FQDN of a station that is powered
            on.
        :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is powered
            on.
        :param station_beam_on_fqdn: the FQDN of a station beam that is powered
            on.
        :param channel_blocks: a list of channel blocks.
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        assert device_under_test.state() == DevState.DISABLE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        assert device_under_test.state() == DevState.ON
        assert device_under_test.obsState == ObsState.EMPTY
        time.sleep(0.1)

        ([result_code], _) = device_under_test.AssignResources(
            json.dumps(
                {
                    "stations": [[station_on_fqdn]],
                    "subarray_beams": [subarray_beam_on_fqdn],
                    "station_beams": [station_beam_on_fqdn],
                    "channel_blocks": channel_blocks,
                }
            )
        )
        assert result_code == ResultCode.OK
        time.sleep(0.1)
        assert device_under_test.assignedResources == json.dumps(
            {
                "interface": "https://schema.skao.int/ska-low-mccs-assignedresources/1.0",
                "subarray_beam_ids": [subarray_beam_on_fqdn.split("/")[-1].lstrip("0")],
                "station_ids": [[station_on_fqdn.split("/")[-1].lstrip("0")]],
                "channel_blocks": channel_blocks,
            }
        )

        assert device_under_test.state() == DevState.ON

        # Subscribe to controller's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )
        time.sleep(0.1)  # allow event system time to run
        initial_lrc_result = ("", "", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)
        ([result_code], [unique_id]) = device_under_test.ReleaseAllResources()
        assert result_code == ResultCode.QUEUED
        assert "ReleaseAllResourcesCommand" in unique_id

        lrc_result = (
            unique_id,
            str(ResultCode.OK.value),
            "ReleaseAllResources command completed OK",
        )
        lrc_result_changed_callback.assert_last_change_event(lrc_result)
        assert device_under_test.assignedResources == json.dumps(
            {
                "interface": "https://schema.skao.int/ska-low-mccs-assignedresources/1.0",
                "subarray_beam_ids": [],
                "station_ids": [],
                "channel_blocks": [],
            }
        )

    def test_configure(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        station_on_id: int,
        station_on_fqdn: str,
        subarray_beam_on_id: int,
        subarray_beam_on_fqdn: str,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
    ) -> None:
        """
        Test for configure command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param station_on_id: the id number of a station that is
            powered on.
        :param station_on_fqdn: the FQDN of a station that is powered
            on.
        :param subarray_beam_on_id: the id number of a subarray beam that is
            powered on.
        :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is powered
            on.
        :param station_beam_on_fqdn: the FQDN of a station beam that is
            powered on.
        :param channel_blocks: a list of channel blocks.
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

        assert device_under_test.state() == DevState.ON
        assert device_under_test.obsState == ObsState.EMPTY
        time.sleep(0.1)

        ([result_code], _) = device_under_test.AssignResources(
            json.dumps(
                {
                    "stations": [[station_on_fqdn]],
                    "subarray_beams": [subarray_beam_on_fqdn],
                    "station_beams": [station_beam_on_fqdn],
                    "channel_blocks": channel_blocks,
                }
            )
        )
        assert result_code == ResultCode.OK
        time.sleep(0.1)
        assert device_under_test.obsState == ObsState.IDLE

        ([result_code], _) = device_under_test.Configure(
            json.dumps(
                {
                    "stations": [{"station_id": station_on_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
                }
            )
        )
        assert result_code == ResultCode.QUEUED
        time.sleep(0.1)
        assert device_under_test.obsState == ObsState.CONFIGURING

        device_under_test.FakeSubservientDevicesObsState(ObsState.READY)

        time.sleep(0.1)
        assert device_under_test.obsState == ObsState.READY

    def test_sendTransientBuffer(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for sendTransientBuffer.

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
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        segment_spec: list[int] = []
        returned = device_under_test.sendTransientBuffer(segment_spec)
        assert returned == [
            [ResultCode.OK],
            [MccsSubarray.SendTransientBufferCommand.RESULT_MESSAGES[ResultCode.OK]],
        ]

    def test_component_state_changed_callback(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test component_state_changed_callback properly extracts values from state
        changes it deals with and raises an error for any that it doesn't for single
        state changes and multiple state changes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        health_state_val = HealthState.OK
        station_health_state_val = HealthState.OK
        station_beam_health_state_val = HealthState.OK
        subarray_beam_health_state_val = HealthState.OK
        health_states = [
            HealthState.DEGRADED,
            HealthState.FAILED,
            HealthState.OK,
            HealthState.UNKNOWN,
        ]
        scanning_changed_val = True
        resources_changed_val = [
            {"low-mccs/station/001"},
            {"low-mccs/subarraybeam/02"},
            {"low-mccs/beam/02"},
        ]
        configured_changed_val = True
        obs_state_val = 1
        station_power_state_val = PowerState.UNKNOWN
        power_state_val = PowerState.UNKNOWN
        state_changes = [
            {"health_state": health_state_val},
            {"station_health_state": station_health_state_val},
            {"station_beam_health_state": station_beam_health_state_val},
            {"subarray_beam_health_state": subarray_beam_health_state_val},
            {"resources_changed": resources_changed_val},
            {"configured_changed": configured_changed_val},
            {"scanning_changed": scanning_changed_val},
            {"assign_completed": None},
            {"release_completed": None},
            {"configure_completed": None},
            {"abort_completed": None},
            {"obsreset_completed": None},
            {"restart_completed": None},
            {"obsfault": None},
            {"obsstate_changed": obs_state_val},
            {"station_power_state": station_power_state_val},
            {"power_state": power_state_val},
        ]
