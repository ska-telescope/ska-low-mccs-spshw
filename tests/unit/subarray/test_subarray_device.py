# type: ignore
# -*- coding: utf-8 -*
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
from ska_control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ObsState,
    PowerState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy, release
from ska_low_mccs_common.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness
from tango import DevState
from tango.server import command

from ska_low_mccs import MccsSubarray
from ska_low_mccs.subarray.subarray_component_manager import SubarrayComponentManager


@pytest.fixture()
def patched_subarray_device_class(
    mock_subarray_component_manager: SubarrayComponentManager,
    station_on_fqdn: str,
    subarray_beam_on_fqdn: str,
) -> Type[MccsSubarray]:
    """
    Return a subarray device class, patched with extra methods for testing.

    :param mock_subarray_component_manager: A fixture that provides a partially
        mocked component manager which has access to the
        component_state_changed_callback.
    :param station_on_fqdn: The FQDN of a mock station that is powered on.
    :param subarray_beam_on_fqdn: The FQDN of a mock subarray beam that is powered on.

    :return: a patched subarray device class, patched with extra methods
        for testing
    """

    class PatchedSubarrayDevice(MccsSubarray):
        """
        MccsSubarray patched with extra commands for testing purposes.

        The extra commands allow us to mock the receipt of obs state
        change events from subservient devices, turn on DeviceProxies,
        set the initial obsState and examine the health model.
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
            self: PatchedSubarrayDevice,
        ) -> None:
            for fqdn, proxy in self.component_manager._stations.items():
                if fqdn == station_on_fqdn:
                    proxy.power_state = PowerState.ON

            for fqdn, proxy in self.component_manager._subarray_beams.items():
                if fqdn == subarray_beam_on_fqdn:
                    proxy.power_state = PowerState.ON

        @command(dtype_in=str)
        def set_obs_state(
            self: PatchedSubarrayDevice,
            obs_state_name: str,
        ) -> None:
            """
            Set the obsState of this device.

            A method to set the obsState for testing purposes.

            :param obs_state_name: The name of the obsState to directly transition to.
            """
            self.obs_state_model._straight_to_state(obs_state_name)

        @command(dtype_in=str, dtype_out=int)
        def examine_health_model(
            self: PatchedSubarrayDevice,
            fqdn: str,
        ) -> HealthState:
            """
            Return the health state of a subservient device.

            Returns the health state of the device at the given FQDN.
            :param fqdn: The FQDN of a device whose health state we want.
            :return: The HealthState of the device at the specified FQDN.
            """
            device_type = fqdn.split("/")[1]
            if device_type == "beam":
                return self._health_model._station_beam_healths[fqdn]
            elif device_type == "station":
                return self._health_model._station_healths[fqdn]
            elif device_type == "subarraybeam":
                return self._health_model._subarray_beam_healths[fqdn]

        def create_component_manager(
            self: PatchedSubarrayDevice,
        ) -> SubarrayComponentManager:
            """
            Return a partially mocked component manager instead of the usual one.

            :return: a mock component manager
            """
            mock_subarray_component_manager._communication_state_changed_callback = (
                self._component_communication_state_changed
            )
            mock_subarray_component_manager._component_state_changed_callback = (
                self._component_state_changed_callback
            )

            return mock_subarray_component_manager

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

    @pytest.mark.skip(
        "GetVersionInfo is no longer a long running command and merely returns"
        " a string. Should this test be removed?"
    )
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
        # To please the linter and to show this test is skipped explicitly
        # in test reports.
        pass

    #     # TODO: Is this test pointless now? GetVersionInfo isn't a LRC anymore
    #     # Subscribe to controller's LRC result attribute
    #     device_under_test.add_change_event_callback(
    #         "longRunningCommandResult",
    #         lrc_result_changed_callback,
    #     )
    #     assert (
    #         "longRunningCommandResult".casefold()
    #         in device_under_test._change_event_subscription_ids
    #     )
    #     initial_lrc_result = ("", "")
    #     assert device_under_test.longRunningCommandResult == initial_lrc_result
    #     lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

    #     # GetVersionInfo appears to have changed. Maybe missing a cmd obj
    #     version_info = device_under_test.GetVersionInfo()
    #     # assert result_code == TaskStatus.QUEUED
    #     # assert "GetVersionInfo" in unique_id

    #     vinfo = release.get_release_info(device_under_test.info().dev_class)
    #     lrc_result = (
    #         unique_id,
    #         str(ResultCode.OK.value),
    #         str([vinfo]),
    #     )
    #     lrc_result_changed_callback.assert_last_change_event(lrc_result)

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

    @pytest.mark.skip(
        reason="covered by ticket MCCS-1138, skipped to allow other work to progress"
    )
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
        :param device_state_changed_callback: A mock callback to be called when
            the device's state is changed.
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_under_test.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE
        device_state_changed_callback.assert_next_change_event(DevState.DISABLE)
        assert device_under_test.state() == DevState.DISABLE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        time.sleep(0.1)

        device_state_changed_callback.assert_last_change_event(DevState.ON)
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
        assert "AssignResources" in str(response).rsplit("_", maxsplit=1)[-1].rstrip(
            "']"
        )

        assert device_under_test.state() == DevState.ON

        initial_lrc_result = ("", "")
        assert device_under_test.longRunningCommandResult == initial_lrc_result
        lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

        time.sleep(0.5)  # Needs time to actually resource or
        # we release before we've finished assigning.
        interface = "https://schema.skao.int/ska-low-mccs-assignedresources/1.0"
        assert device_under_test.assignedResources == json.dumps(
            {
                "interface": interface,
                "subarray_beam_ids": [subarray_beam_on_fqdn.split("/")[-1].lstrip("0")],
                "station_ids": [[station_on_fqdn.split("/")[-1].lstrip("0")]],
                "channel_blocks": channel_blocks,
            }
        )
        assert device_under_test.obsState == ObsState.IDLE
        ([result_code], [unique_id]) = device_under_test.ReleaseAllResources()
        import pdb

        pdb.set_trace()
        assert result_code == ResultCode.QUEUED
        assert "ReleaseAllResources" in unique_id
        time.sleep(0.5)

        lrc_result = (
            unique_id,
            '"ReleaseAllResources has completed."',
        )

        lrc_result_changed_callback.assert_last_change_event(lrc_result)
        interface = "https://schema.skao.int/ska-low-mccs-assignedresources/1.0"
        assert device_under_test.assignedResources == json.dumps(
            {
                "interface": interface,
                "subarray_beam_ids": [],
                "station_ids": [],
                "channel_blocks": [],
            }
        )
        assert device_under_test.obsState == ObsState.EMPTY

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

        # Need to force station and subarray beam proxies into PowerState.ON for
        # configure to complete.
        device_under_test.TurnOnProxies()

        ([result_code], _) = device_under_test.Configure(
            json.dumps(
                {
                    "stations": [{"station_id": station_on_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
                }
            )
        )
        # The below assertion will often fail as the obsState transitions
        # through CONFIGURING to READY faster than we can check.
        # assert device_under_test.obsState == ObsState.CONFIGURING

        assert result_code == ResultCode.QUEUED

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

        # Seems to be a bit of an adminMode wobble here.
        # The first event to come through is another OFFLINE (possibly just a dupe
        # of the first) but is followed by ONLINE so assertion has been changed from
        # `assert_next_change_event` to `assert_last_change_event`
        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        segment_spec: list[int] = []
        result_code, response = device_under_test.sendTransientBuffer(segment_spec)

        assert result_code == ResultCode.QUEUED
        assert "SendTransientBuffer" in str(response).rsplit("_", maxsplit=1)[
            -1
        ].rstrip("']")

    @pytest.mark.parametrize("target_power_state", list(PowerState))
    def test_component_state_changed_callback_power_state(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,  # pylint: disable=unused-argument
        mock_subarray_component_manager: SubarrayComponentManager,
        target_power_state: PowerState,
    ) -> None:
        """
        Test `component_state_changed properly` handles power updates.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param target_power_state: The PowerState that the device should end up in.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "power_state"
        # Call the callback with the {key, value} pair
        state_change = {key: target_power_state}
        mock_subarray_component_manager.component_state_changed_callback(state_change)

        # Check that the power state has changed.
        final_power_state = mock_subarray_component_manager.power_state
        assert final_power_state == target_power_state

    @pytest.mark.parametrize("target_health_state", list(HealthState))
    def test_component_state_changed_callback_health_state(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,  # pylint: disable=unused-argument
        mock_subarray_component_manager: SubarrayComponentManager,
        target_health_state: HealthState,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test `component_state_changed` properly handles health updates.

        Here we only test that the change event is pushed and that we receive it.
        HealthState.UNKNOWN is omitted due to it being the initial state.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param target_health_state: The HealthState that the device should end up in.
        :param device_health_state_changed_callback: A mock callback to be called when
            the device's health state changes.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        key = "health_state"
        state_change = {key: target_health_state}

        # Initial state is UNKNOWN so skip that one.
        if target_health_state != HealthState.UNKNOWN:
            mock_subarray_component_manager._component_state_changed_callback(
                state_change
            )
            device_health_state_changed_callback.assert_next_change_event(
                target_health_state
            )

    @pytest.mark.parametrize("configured_changed", [True, False])
    def test_component_state_changed_callback_configured_changed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        configured_changed: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles configured_changed updates.

        Test that the obs state model is properly updated when the component is
        configured or unconfigured.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param configured_changed: Whether the component is configured.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "configured_changed"
        state_change = {key: configured_changed}
        # set initial obsState
        if configured_changed:
            # TODO: Figure out a better test for these transitional state changes.
            # obsState change: CONFIGURING_IDLE -> CONFIGURING_READY
            initial_obs_state_name = "CONFIGURING_IDLE"
            initial_obs_state = ObsState.CONFIGURING
            final_obs_state = ObsState.CONFIGURING  # This is not a great test...
        else:
            # obsState change: READY -> IDLE
            initial_obs_state_name = "READY"
            initial_obs_state = ObsState.READY
            final_obs_state = ObsState.IDLE
        device_under_test.set_obs_state(initial_obs_state_name)

        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("scanning_changed", [True, False])
    def test_component_state_changed_callback_scanning_changed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        scanning_changed: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles scanning_changed updates.

        Test that the obs state model is properly updated when the component starts
        or stops scanning.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param scanning_changed: Whether the subarray is scanning.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "scanning_changed"
        state_change = {key: scanning_changed}
        # set initial obsState
        if scanning_changed:
            # obsState change: READY -> SCANNING
            initial_obs_state_name = "READY"
            initial_obs_state = ObsState.READY
            final_obs_state = ObsState.SCANNING
        else:
            # obsState change: SCANNING -> READY
            initial_obs_state_name = "SCANNING"
            initial_obs_state = ObsState.SCANNING
            final_obs_state = ObsState.READY
        device_under_test.set_obs_state(initial_obs_state_name)

        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("resourcing", [True, False])
    def test_component_state_changed_callback_assign_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        resourcing: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles assign_completed updates.

        Test that the obs state model is properly updated when resource assignment
        completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param resourcing: Whether the subarray is resourcing or emptying.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "assign_completed"
        state_change = {key: None}
        # Set initial obsState.
        if resourcing:
            # obsState change: RESOURCING_IDLE -> IDLE
            initial_obs_state_name = "RESOURCING_IDLE"
            initial_obs_state = ObsState.RESOURCING
            final_obs_state = ObsState.IDLE
        else:
            # obsState change: RESOURCING_EMPTY -> EMPTY
            initial_obs_state_name = "RESOURCING_EMPTY"
            initial_obs_state = ObsState.RESOURCING
            final_obs_state = ObsState.EMPTY

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("to_empty", [True, False])
    def test_component_state_changed_callback_release_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        to_empty: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles release_completed updates.

        Test that the obs state model is properly updated when resource release
        completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param to_empty: Whether the subarray is transitioning to EMPTY or not.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "release_completed"
        state_change = {key: None}
        # Set initial obsState.
        if to_empty:
            # obsState change: RESOURCING_EMPTY -> EMPTY
            initial_obs_state_name = "RESOURCING_EMPTY"
            initial_obs_state = ObsState.RESOURCING
            final_obs_state = ObsState.EMPTY
        else:
            # obsState change: RESOURCING_IDLE -> IDLE
            initial_obs_state_name = "RESOURCING_IDLE"
            initial_obs_state = ObsState.RESOURCING
            final_obs_state = ObsState.IDLE

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("to_ready", [True, False])
    def test_component_state_changed_callback_configure_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        to_ready: bool,
    ) -> None:
        """
        Test `component_state_changed` properly handles configure_completed updates.

        Test that the obs state model is properly updated when configuring completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param to_ready: Whether the subarray is transitioning to READY or not.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "configure_completed"
        state_change = {key: None}
        # Set initial obsState.
        if to_ready:
            # obsState change: CONFIGURING_READY -> READY
            initial_obs_state_name = "CONFIGURING_READY"
            initial_obs_state = ObsState.CONFIGURING
            final_obs_state = ObsState.READY
        else:
            # obsState change: CONFIGURING_IDLE -> IDLE
            initial_obs_state_name = "CONFIGURING_IDLE"
            initial_obs_state = ObsState.CONFIGURING
            final_obs_state = ObsState.IDLE

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    def test_component_state_changed_callback_abort_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
    ) -> None:
        """
        Test `component_state_changed` properly handles abort_completed updates.

        Test that the obs state model is properly updated when abort completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "abort_completed"
        state_change = {key: None}
        # Set initial obsState.
        # obsState change: ABORTING -> ABORTED
        initial_obs_state_name = "ABORTING"
        initial_obs_state = ObsState.ABORTING
        final_obs_state = ObsState.ABORTED

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    def test_component_state_changed_callback_obs_reset_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
    ) -> None:
        """
        Test `component_state_changed` properly handles obsreset_completed updates.

        Test that the obs state model is properly updated when obsreset completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "obsreset_completed"
        state_change = {key: None}
        # Set initial obsState.
        # obsState change: RESETTING -> IDLE
        initial_obs_state_name = "RESETTING"
        initial_obs_state = ObsState.RESETTING
        final_obs_state = ObsState.IDLE

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    def test_component_state_changed_callback_restart_completed(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
    ) -> None:
        """
        Test `component_state_changed` properly handles restart_completed updates.

        Test that the obs state model is properly updated when restart completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "restart_completed"
        state_change = {key: None}
        # Set initial obsState.
        # obsState change: RESTARTING -> EMPTY
        initial_obs_state_name = "RESTARTING"
        initial_obs_state = ObsState.RESTARTING
        final_obs_state = ObsState.EMPTY

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("initial_obs_state", list(ObsState))
    def test_component_state_changed_callback_obsfault(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,
        mock_subarray_component_manager: SubarrayComponentManager,
        initial_obs_state: ObsState,
    ) -> None:
        """
        Test `component_state_changed` properly handles restart_completed updates.

        Test that the obs state model is properly updated when restart completes.

        :param mock_subarray_component_manager: A fixture that provides a partially
            mocked component manager which has access to the
            component_state_changed_callback.
        :param initial_obs_state: The obsState that the subarray should start
            the test in.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        key = "obsfault"
        state_change = {key: None}
        # Set initial obsState.
        # obsState change: * -> FAULT
        initial_obs_state_name = initial_obs_state.name
        # Handle special cases of RESOURCING and CONFIGURING with their
        # transitional states.
        special_cases = ["RESOURCING", "CONFIGURING"]
        if initial_obs_state_name in special_cases:
            initial_obs_state_name = initial_obs_state_name + "_IDLE"

        final_obs_state = ObsState.FAULT

        device_under_test.set_obs_state(initial_obs_state_name)
        time.sleep(0.1)
        assert device_under_test.obsState == initial_obs_state

        mock_subarray_component_manager._component_state_changed_callback(state_change)
        time.sleep(0.1)
        assert device_under_test.obsState == final_obs_state

    @pytest.mark.parametrize("target_health_state", list(HealthState))
    @pytest.mark.parametrize(
        "fqdn", ["station_on_fqdn", "subarray_beam_on_fqdn", "station_beam_on_fqdn"]
    )
    def test_component_state_changed_callback_subservient_device_health_state(
        self: TestMccsSubarray,
        device_under_test: MccsDeviceProxy,  # pylint: disable=unused-argument
        mock_subarray_component_manager: SubarrayComponentManager,
        target_health_state: HealthState,
        fqdn: str,
        request: pytest.FixtureRequest,
    ) -> None:
        """
        Test `component_state_changed` properly handles health updates.

        Here we test that by calling `component_state_changed_callback` with
        the fqdn of a device and a new healthState the record of it's health
        state in the health model is properly updated.

        :param mock_subarray_component_manager: A fixture that provides a partiall
            mocked component manager which has access to the
            component_state_changed_callback.
        :param target_health_state: The HealthState that the device should end up in.
        :param fqdn: The fqdn of a subservient device.
        :param request: A PyTest object giving access to the requesting test.
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        # Get the fixture from the parametrized fixture that's not a fixture.
        # (But is really.)
        fqdn = request.getfixturevalue(fqdn)

        key = "health_state"
        state_change = {key: target_health_state}

        mock_subarray_component_manager._component_state_changed_callback(
            state_change, fqdn=fqdn
        )
        dev_final_health_state = device_under_test.examine_health_model(fqdn)
        assert dev_final_health_state == target_health_state
