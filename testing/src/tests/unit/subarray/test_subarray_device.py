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
import pytest, pytest_mock
from typing import Callable, Type, Any, Optional

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
from ska_tango_base.control_model import CommunicationStatus, PowerState
from tango import DevState
from tango.server import command

from ska_low_mccs import MccsDeviceProxy, MccsSubarray, release
from ska_low_mccs.subarray.subarray_component_manager import SubarrayComponentManager
from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.testing.mock.mock_callable import MockCallable, MockCallableDeque
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness

#from testing.src.tests.unit.controller.conftest import component_state_changed_callback
#from testing.src.tests.unit.subarray.conftest import subarray_beam_on_fqdn


@pytest.fixture()
def patched_subarray_device_class(mock_subarray_component_manager: SubarrayComponentManager, station_on_fqdn: str, subarray_beam_on_fqdn: str,) -> Type[MccsSubarray]:
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

        @command(dtype_in=None)
        def TurnOnProxies(
            self:PatchedSubarrayDevice,
        ) -> None:
            for fqdn,proxy in self.component_manager._stations.items():
                if fqdn == station_on_fqdn:
                    proxy.power_state = PowerState.ON

            for fqdn,proxy in self.component_manager._subarray_beams.items():
                if fqdn == subarray_beam_on_fqdn:
                    proxy.power_state = PowerState.ON

        @command(dtype_in="DevString")
        def component_state_changed_proxy(
            self: PatchedSubarrayDevice,
            state_change_json: str,
        ) -> None:
            """This method is just a passthrough to test the callback."""
            state_change = json.loads(state_change_json)
            print(f"Calling callback with state change: {state_change}")
            self._component_state_changed_callback(state_change)

        def create_component_manager(
            self: PatchedSubarrayDevice,
        ) -> unittest.mock.Mock:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            mock_subarray_component_manager._communication_state_changed_callback = (
                self._component_communication_state_changed
            )
            #mock_subarray_component_manager = pytest_mock.mocker.Mock()
            #mock_subarray_component_manager = super().create_component_manager()
            mock_subarray_component_manager._component_state_changed_callback = (
                self._component_state_changed_callback
            )

            return mock_subarray_component_manager

    return PatchedSubarrayDevice

@pytest.fixture()
def device_state_changed_callback(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for device admin mode change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the
        device via a change event subscription, so that it gets called
        when the device admin mode changes.
    """
    return mock_change_event_callback_factory("state")

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


    @pytest.mark.skip("GetVersionInfo is no longer a long running command and merely returns a string. Should this test be removed?")
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
        # TODO: Is this test pointless now? GetVersionInfo isn't a LRC anymore
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
        version_info = device_under_test.GetVersionInfo()
        print(version_info)
        #assert result_code == TaskStatus.QUEUED
        #assert "GetVersionInfo" in unique_id

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
        device_state_changed_callback: MockChangeEventCallback,
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
        device_under_test.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )
        device_state_changed_callback.assert_next_change_event(DevState.UNKNOWN)
        device_state_changed_callback.assert_next_change_event(DevState.INIT)

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE
        time.sleep(0.1)

        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert device_under_test.state() == DevState.DISABLE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        time.sleep(0.1)

        # TODO: Not getting DevState.ON coming through for some reason.
        device_state_changed_callback.assert_next_change_event(DevState.ON)
        assert device_under_test.state() == DevState.ON
        assert device_under_test.obsState == ObsState.EMPTY

        # Subscribe to controller's LRC result attribute
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        assert (
            "longRunningCommandResult".casefold()
            in device_under_test._change_event_subscription_ids
        )

        result_code, response = device_under_test.AssignResources(
            json.dumps(
                {
                    "stations": [[station_on_fqdn]],
                    "subarray_beams": [subarray_beam_on_fqdn],
                    "station_beams": [station_beam_on_fqdn],
                    "channel_blocks": channel_blocks,
                }
            )
        )
        assert result_code == ResultCode.QUEUED
        assert "AssignResources" in str(response).rsplit("_", maxsplit=1)[-1].rstrip("']")

        assert device_under_test.state() == DevState.ON

        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        time.sleep(0.1) # Needs time to actually resource or
        # we release before we've finished assigning.
        assert device_under_test.assignedResources == json.dumps(
            {
                "interface": "https://schema.skao.int/ska-low-mccs-assignedresources/1.0",
                "subarray_beam_ids": [subarray_beam_on_fqdn.split("/")[-1].lstrip("0")],
                "station_ids": [[station_on_fqdn.split("/")[-1].lstrip("0")]],
                "channel_blocks": channel_blocks,
            }
        )

        ([result_code], [unique_id]) = device_under_test.ReleaseAllResources()
        assert result_code == ResultCode.QUEUED
        assert "ReleaseAllResources" in unique_id

        lrc_result = (
            unique_id,
            '"ReleaseAllResources has completed."',
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
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
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

        assert result_code == ResultCode.QUEUED
        time.sleep(0.1)
        assert device_under_test.obsState == ObsState.IDLE

        # Need to force station and subarray beam proxies into PowerState.ON for configure to complete.
        device_under_test.TurnOnProxies()

        ([result_code], _) = device_under_test.Configure(
            json.dumps(
                {
                    "stations": [{"station_id": station_on_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
                }
            )
        )
        # Using device_obs_state variable to capture obsState value at this point.
        # If we don't do this then it transitions to obsState.READY by the time we make the assertion for CONFIGURING.
        device_obs_state = device_under_test.obsState
        assert result_code == ResultCode.QUEUED

        # This test sometimes fails at this point as the obsState has gone all the way to READY faster than we can check.
        # TODO: Add a mock callback and make assertions on the change events for ObsState.
        assert device_obs_state == ObsState.CONFIGURING
        time.sleep(0.1)
        device_under_test.FakeSubservientDevicesObsState(ObsState.READY)
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

        # Seems to be a bit of an adminMode wobble here.
        # The first event to come through is another OFFLINE (possibly just a dupe of the first) but is followed by ONLINE so assertion has been changed from `assert_next_call` to `assert_last_call`
        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        segment_spec: list[int] = []
        result_code, response = device_under_test.sendTransientBuffer(segment_spec)

        assert result_code == ResultCode.QUEUED
        assert "SendTransientBuffer" in str(response).rsplit("_", maxsplit=1)[-1].rstrip("']")


    # This will input all possible PowerState values for this test.
    @pytest.mark.parametrize("target_power_state", list(PowerState))
    def test_component_state_changed_callback_power_state(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy, #pylint: disable=unused-argument
        mock_subarray_component_manager: SubarrayComponentManager,
        target_power_state: PowerState,
    ) -> None:
        """
        Test component_state_changed_callback properly extracts values from state
        changes it deals with and raises an error for any that it doesn't for single
        state changes and multiple state changes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        #print(f"Testing powerState = {value}")

        key = "power_state"
        initial_power_state = mock_subarray_component_manager.power_state
        # Check the initial power state. If it's the same as the target power state then quickly switch it to a different one.
        if initial_power_state == target_power_state:
            new_initial_power_state = PowerState((initial_power_state+1)%len(list(PowerState)))
            mock_subarray_component_manager.power_state = new_initial_power_state
            assert mock_subarray_component_manager.power_state == new_initial_power_state
        
        # Call the callback with the {key, value} pair
        state_change = {key: target_power_state}
        mock_subarray_component_manager.component_state_changed_callback(state_change)

        # Check that the power state has changed.
        final_power_state = mock_subarray_component_manager.power_state
        assert final_power_state == target_power_state
        
        # Deliberately fail the test so we get the traceback and stdout log in terminal.
        assert False
        
