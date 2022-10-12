# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the station beam component manager."""
from __future__ import annotations

import json
import time
import unittest.mock

import pytest
import tango
from ska_control_model import CommunicationStatus, ObsState, PowerState, TaskStatus
from ska_low_mccs_common.testing.mock import MockCallable, MockCallableDeque

from ska_low_mccs.subarray import SubarrayComponentManager


class TestSubarrayComponentManager:
    """Class for testing the subarray component manager."""

    def test_communication(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        communication_state_changed_callback: MockCallable,
        station_on_fqdn: str,
        subarray_beam_on_fqdn: str,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
    ) -> None:
        """
        Test the component manager's communication with its assigned devices.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes

        :param station_on_fqdn: the FQDN of a mock station that is
            powered on.
        :param subarray_beam_on_fqdn: the FQDN of a mock subarray beam
            that is powered on
        :param station_beam_on_fqdn: the FQDN of a mock station beam
            that is powered on
        :param channel_blocks: a mock list of channel blocks
        """
        subarray_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

        resource_spec = {
            "stations": [station_on_fqdn],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }

        result_code, response = subarray_component_manager.assign(resource_spec)
        assert result_code == TaskStatus.QUEUED
        assert response == "Task queued"

        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

        subarray_component_manager.stop_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            subarray_component_manager.communication_state
            == CommunicationStatus.DISABLED
        )

        subarray_component_manager.start_communicating()
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_state_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )

    def test_assign_and_release(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        station_off_fqdn: str,
        station_on_fqdn: str,
        subarray_beam_off_fqdn: str,
        subarray_beam_on_fqdn: str,
        station_beam_off_fqdn: str,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test the component manager's handling of configuration.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param station_off_fqdn: the FQDN of a station that is powered
            off.
        :param station_on_fqdn: the FQDN of a station that is powered
            on.
        :param subarray_beam_off_fqdn: the FQDN of a subarray beam that is powered
            off.
        :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is powered
            on.
        :param station_beam_off_fqdn: the FQDN of a station beam that is powered
            off.
        :param station_beam_on_fqdn: the FQDN of a station beam that is powered
            on.
        :param channel_blocks: a list of channel blocks.
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        subarray_component_manager.start_communicating()
        component_state_changed_callback.assert_next_call(
            {"power_state": PowerState.ON}
        )

        assert subarray_component_manager.assigned_resources_dict == {
            "stations": list(),
            "subarray_beams": list(),
            "station_beams": list(),
            "channel_blocks": list(),
        }

        # Assignment from empty
        resource_spec = {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }
        result_code, response = subarray_component_manager.assign(resource_spec)
        assert result_code == TaskStatus.QUEUED
        assert response == "Task queued"
        time.sleep(0.1)
        component_state_changed_callback.assert_in_deque(
            {
                "resources_changed": [
                    {"low-mccs/station/001"},
                    {"low-mccs/subarraybeam/02"},
                    {"low-mccs/beam/02"},
                ]
            }
        )

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_off_fqdn, PowerState.OFF
        )

        component_state_changed_callback.assert_in_deque({"assign_completed": None})

        assert subarray_component_manager.assigned_resources_dict == {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }

        # Further assign
        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        result_code, response = subarray_component_manager.assign(resource_spec)
        assert result_code == TaskStatus.QUEUED
        assert response == "Task queued"

        time.sleep(0.1)
        component_state_changed_callback.assert_in_deque(
            {
                "resources_changed": [
                    {"low-mccs/station/002", "low-mccs/station/001"},
                    {"low-mccs/subarraybeam/03", "low-mccs/subarraybeam/02"},
                    {"low-mccs/beam/02", "low-mccs/beam/03"},
                ]
            }
        )

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        subarray_component_manager._station_power_state_changed(
            station_off_fqdn, PowerState.ON
        )
        time.sleep(0.1)
        component_state_changed_callback.assert_in_deque({"assign_completed": None})

        assert subarray_component_manager.assigned_resources_dict == {
            "stations": [[station_off_fqdn], [station_on_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn, subarray_beam_on_fqdn],
            "station_beams": [station_beam_off_fqdn, station_beam_on_fqdn],
            "channel_blocks": channel_blocks + channel_blocks,
        }

        # Release all
        result_code, response = subarray_component_manager.release_all()
        assert result_code == TaskStatus.QUEUED
        assert response == "Task queued"

        time.sleep(0.1)
        component_state_changed_callback.assert_in_deque(
            {"resources_changed": [set(), set(), set()]}
        )
        component_state_changed_callback.assert_in_deque({"release_completed": None})

        assert subarray_component_manager.assigned_resources_dict == {
            "stations": list(),
            "subarray_beams": list(),
            "station_beams": list(),
            "channel_blocks": list(),
        }

    def test_release(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        station_off_fqdn: str,
        component_state_changed_callback: MockCallable,
    ) -> None:
        """
        Test the component manager's handling of the release command.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param station_off_fqdn: the FQDN of a station that is powered
            off.
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        subarray_component_manager.start_communicating()
        component_state_changed_callback.assert_next_call(
            {"power_state": PowerState.ON}
        )

        release_json = json.dumps({"station_beams": [station_off_fqdn]})
        with pytest.raises(
            NotImplementedError,
            match="MCCS Subarray cannot partially release resources.",
        ):
            # Following line changed to execute ._release rather than .release
            # as .release just queues the ._release command and ._release
            # is where the exception is supposed to be raised.
            subarray_component_manager._release(release_json)

    def test_configure(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        station_off_id: int,
        station_off_fqdn: str,
        mock_station_off: unittest.mock.Mock,
        station_on_id: int,
        station_on_fqdn: str,
        mock_station_on: unittest.mock.Mock,
        subarray_beam_off_id: int,
        subarray_beam_off_fqdn: str,
        mock_subarray_beam_off: unittest.mock.Mock,
        subarray_beam_on_id: int,
        subarray_beam_on_fqdn: str,
        mock_subarray_beam_on: unittest.mock.Mock,
        station_beam_on_fqdn: str,
        station_beam_off_fqdn: str,
        channel_blocks: list[int],
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test the component manager's handling of configuration.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param station_off_id: the id number of a station that is
            powered off.
        :param station_off_fqdn: the FQDN of a station that is powered
            off.
        :param mock_station_off: a mock station that is powered off.
        :param station_on_id: the id number of a station that is
            powered on.
        :param station_on_fqdn: the FQDN of a station that is powered
            on.
        :param mock_station_on: a mock station that is powered on.
        :param subarray_beam_off_id: the id number of a subarray beam that is
            powered off.
        :param subarray_beam_off_fqdn: the FQDN of a subarray beam that is powered
            off.
        :param mock_subarray_beam_off: a mock subarray beam that is powered off.
        :param subarray_beam_on_id: the id number of a subarray beam that is
            powered on.
        :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is powered
            on.
        :param mock_subarray_beam_on: a mock subarray beam that is powered on.
        :param station_beam_on_fqdn: the FQDN of a station beam that is powered
            on.
        :param station_beam_off_fqdn: the FQDN of a station beam that is powered
            off.
        :param channel_blocks: a list of channel blocks.
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        # The sleeps littering this test are to allow the code time to execute the queued commands
        # and make the calls to the callback so we can make the assertions.
        # Without them the callbacks end up having not been called (yet!) by the time we get to them.
        subarray_component_manager.start_communicating()

        assert (
            subarray_component_manager.communication_state
            == CommunicationStatus.ESTABLISHED
        )
        expected_arguments = {"power_state": PowerState.ON}
        time.sleep(0.1)
        component_state_changed_callback.assert_next_call_with_keys(expected_arguments)
        # There are a few (unavoidable) nasty hacks like the following line
        # scattered around as a result of the changes to the callbacks during the update to v0.13.
        subarray_component_manager.power_state = PowerState.ON

        # can't configure when resources are OFF
        resource_spec = {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)

        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_off_fqdn, PowerState.ON
        )

        expected_arguments = [
            {"assign_completed": None},
            {
                "resources_changed": [
                    {"low-mccs/station/001"},
                    {"low-mccs/subarraybeam/02"},
                    {"low-mccs/beam/02"},
                ]
            },
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_next_calls_with_keys(expected_arguments)

        with pytest.raises(ConnectionError, match="Component is not turned on."):
            subarray_component_manager._configure(
                {
                    "stations": [{"station_id": station_off_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_off_id}],
                }
            )

        task_status, response = subarray_component_manager.release_all()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # Check that component_state_changed_callback has been called with the arguments expected.
        expected_arguments = [
            {"resources_changed": [set(), set(), set()]},
            {"release_completed": None},
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )

        expected_arguments = [
            {"assign_completed": None},
            {
                "resources_changed": [
                    {"low-mccs/station/002"},
                    {"low-mccs/subarraybeam/02"},
                    {"low-mccs/beam/02"},
                ]
            },
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        for fqdn, proxy in subarray_component_manager._stations.items():
            if fqdn == station_on_fqdn:
                proxy.power_state = PowerState.ON

        with pytest.raises(ConnectionError, match="Component is not turned on."):
            subarray_component_manager._configure(
                {
                    "stations": [{"station_id": station_on_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_off_id}],
                }
            )

        time.sleep(0.1)
        mock_station_on.Configure.assert_next_call(
            json.dumps({"station_id": station_on_id})
        )
        mock_subarray_beam_off.Configure.assert_not_called()

        task_status, response = subarray_component_manager.release_all()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        expected_arguments = [
            {"release_completed": None},
            {"resources_changed": [set(), set(), set()]},
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        resource_spec = {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )

        # Check that component_state_changed_callback has been called with the arguments expected.
        expected_arguments = [
            {"assign_completed": None},
            {
                "resources_changed": [
                    {"low-mccs/station/001"},
                    {"low-mccs/subarraybeam/03"},
                    {"low-mccs/beam/03"},
                ]
            },
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        with pytest.raises(ConnectionError, match="Component is not turned on."):
            subarray_component_manager._configure(
                {
                    "stations": [{"station_id": station_off_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
                }
            )
        mock_station_off.Configure.assert_not_called()
        mock_station_on.Configure.assert_not_called()
        mock_subarray_beam_on.Configure.assert_not_called()
        mock_subarray_beam_off.Configure.assert_not_called()

        task_status, response = subarray_component_manager.release_all()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        expected_arguments = [
            {"release_completed": None},
            {"resources_changed": [set(), set(), set()]},
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        # CAN configure when resources are ON
        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )

        expected_arguments = [
            {"assign_completed": None},
            {
                "resources_changed": [
                    {"low-mccs/station/002"},
                    {"low-mccs/subarraybeam/03"},
                    {"low-mccs/beam/03"},
                ]
            },
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        # Hacky solution to set the power states of the proxies so configure finishes.
        for fqdn, proxy in subarray_component_manager._stations.items():
            if fqdn == station_on_fqdn:
                proxy.power_state = PowerState.ON

        for fqdn, proxy in subarray_component_manager._subarray_beams.items():
            if fqdn == subarray_beam_on_fqdn:
                proxy.power_state = PowerState.ON

        task_status, response = subarray_component_manager.configure(
            {
                "stations": [{"station_id": station_on_id}],
                "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
            }
        )
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        mock_station_off.Configure.assert_not_called()
        mock_station_on.Configure.assert_next_call(
            json.dumps({"station_id": station_on_id})
        )
        mock_subarray_beam_off.Configure.assert_not_called()
        mock_subarray_beam_on.Configure.assert_next_call(
            json.dumps({"subarray_beam_id": subarray_beam_on_id})
        )

        subarray_component_manager._stations[station_on_fqdn]._obs_state_changed(
            "obsState", ObsState.READY, tango.AttrQuality.ATTR_VALID
        )
        # TODO: Reinstate these obsstate assertions once the callback can handle it. (They're there but we haven't formally checked.)
        # component_state_changed_callback.assert_next_call(
        #     {"obsstate_changed": ObsState.READY}, fqdn="low-mccs/station/002"
        # )

        subarray_component_manager._subarray_beams[
            subarray_beam_on_fqdn
        ]._obs_state_changed("obsState", ObsState.READY, tango.AttrQuality.ATTR_VALID)
        # component_state_changed_callback.assert_next_call(
        #     {"obsstate_changed": ObsState.READY}, fqdn="low-mccs/subarraybeam/03"
        # )

        expected_arguments = [
            {"configured_changed": True},
            {"configure_completed": None},
        ]
        time.sleep(0.1)
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        # deconfigure
        task_status, response = subarray_component_manager.deconfigure()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        mock_station_off.Configure.assert_not_called()
        mock_station_on.Configure.assert_next_call(json.dumps({}))
        mock_subarray_beam_off.Configure.assert_not_called()
        mock_subarray_beam_on.Configure.assert_next_call(json.dumps({}))

        expected_arguments = {"configured_changed": False}
        time.sleep(0.1)
        component_state_changed_callback.assert_in_deque(expected_arguments)

    def test_scan(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        station_on_id: int,
        station_on_fqdn: str,
        subarray_beam_on_id: int,
        subarray_beam_on_fqdn: str,
        mock_subarray_beam_on: unittest.mock.Mock,
        station_beam_on_id: int,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
        scan_id: int,
        start_time: float,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test the component manager's handling of configuration.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param station_on_id: the id number of a station that is
            powered on.
        :param station_on_fqdn: the FQDN of a station that is powered
            on.
        :param subarray_beam_on_id: the id number of a subarray beam that is
            powered on.
        :param subarray_beam_on_fqdn: the FQDN of a subarray beam that is powered
            on.
        :param mock_subarray_beam_on: a mock subarray beam that is powered on.
        :param station_beam_on_id: the id number of a station beam that is
            powered on.
        :param station_beam_on_fqdn: the FQDN of a station beam that is powered
            on.
        :param channel_blocks: a list of channel blocks.
        :param scan_id: a scan id for use in testing
        :param start_time: a scan start time for use in testing
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        subarray_component_manager.start_communicating()
        component_state_changed_callback.assert_next_call(
            {"power_state": PowerState.ON}
        )
        # The following is a hacky solution but appears to be the only one available.
        # The issue is that the component_state_changed_callback is responsible for actually changing the power state
        # but the mock we're using can't do it so the best we can do is to assert that the call comes through which
        # would have done this and then do it manually ourselves for the test.
        subarray_component_manager.power_state = PowerState.ON
        assert subarray_component_manager.power_state == PowerState.ON

        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        # Hacky solution to set the power states of the proxies so configure finishes.
        for fqdn, proxy in subarray_component_manager._stations.items():
            if fqdn == station_on_fqdn:
                proxy.power_state = PowerState.ON

        for fqdn, proxy in subarray_component_manager._subarray_beams.items():
            if fqdn == subarray_beam_on_fqdn:
                proxy.power_state = PowerState.ON

        for fqdn, proxy in subarray_component_manager._station_beams.items():
            if fqdn == station_beam_on_fqdn:
                proxy.power_state = PowerState.ON

        expected_arguments = [
            {"assign_completed": None},
            {
                "resources_changed": [
                    {"low-mccs/station/002"},
                    {"low-mccs/subarraybeam/03"},
                    {"low-mccs/beam/03"},
                ]
            },
        ]
        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        time.sleep(0.1)
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )
        component_state_changed_callback.assert_next_calls_with_keys(expected_arguments)

        for fqdn, proxy in subarray_component_manager._stations.items():
            if fqdn == station_on_fqdn:
                proxy.power_state = PowerState.ON

        for fqdn, proxy in subarray_component_manager._subarray_beams.items():
            if fqdn == subarray_beam_on_fqdn:
                proxy.power_state = PowerState.ON

        for fqdn, proxy in subarray_component_manager._station_beams.items():
            if fqdn == station_beam_on_fqdn:
                proxy.power_state = PowerState.ON

        task_status, response = subarray_component_manager.configure(
            {
                "stations": [{"station_id": station_on_id}],
                "subarray_beams": [{"subarray_beam_id": subarray_beam_on_id}],
                "station_beams": [{"station_beam_id": station_beam_on_id}],
            }
        )
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        assert subarray_component_manager.scan_id is None
        task_status, response = subarray_component_manager.scan(scan_id, start_time)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        time.sleep(0.1)
        assert subarray_component_manager.scan_id == scan_id

        mock_subarray_beam_on.Scan.assert_next_call(
            json.dumps({"scan_id": scan_id, "start_time": start_time})
        )
        time.sleep(0.1)
        component_state_changed_callback.assert_next_call_with_keys(
            {"scanning_changed": True}
        )

        task_status, response = subarray_component_manager.end_scan()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        time.sleep(0.1)
        component_state_changed_callback.assert_next_call_with_keys(
            {"scanning_changed": False}
        )
