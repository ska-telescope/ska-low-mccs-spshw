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
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, ObsState, PowerState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.subarray import SubarrayComponentManager
from ska_low_mccs.testing.mock import MockCallable


class TestSubarrayComponentManager:
    """Class for testing the subarray component manager."""

    def test_communication(
        self: TestSubarrayComponentManager,
        subarray_component_manager: SubarrayComponentManager,
        communication_status_changed_callback: MockCallable,
        station_on_fqdn: str,
        subarray_beam_on_fqdn: str,
        station_beam_on_fqdn: str,
        channel_blocks: list[int],
    ) -> None:
        """
        Test the component manager's communication with its assigned devices.

        :param subarray_component_manager: the subarray component
            manager under test.
        :param communication_status_changed_callback: callback to be
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
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_status
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

        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        subarray_component_manager.stop_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.DISABLED
        )
        assert (
            subarray_component_manager.communication_status
            == CommunicationStatus.DISABLED
        )

        subarray_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            subarray_component_manager.communication_status
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
        component_state_changed_callback: MockCallable,
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
        :param assign_completed_callback: callback to be called when the
            component completes a resource assignment.
        :param release_completed_callback: callback to be called when
            the component completes a resource release.
        :param resources_changed_callback: callback to be called when this
            subarray's resources change
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        # TODO: There's a race condition in this test somewhere. It will sporadically fail when callbacks are called in a different order.
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

        component_state_changed_callback.assert_next_call(
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
        subarray_component_manager._station_power_state_changed(
            station_off_fqdn, PowerState.OFF
        )

        component_state_changed_callback.assert_next_call({"assign_completed": None})

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

        component_state_changed_callback.assert_next_call(
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

        component_state_changed_callback.assert_next_call({"assign_completed": None})

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

        component_state_changed_callback.assert_next_call(
            {"resources_changed": [set(), set(), set()]}
        )
        component_state_changed_callback.assert_next_call({"release_completed": None})

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
        component_state_changed_callback: MockCallable,
        communication_status_changed_callback: MockCallable,
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
        :param assign_completed_callback: callback to be called when the
            component completes a resource assignment.
        :param configure_completed_callback: callback to be called when
            the component completes a configuration.
        :param configured_changed_callback: callback to be called when
            whether the subarray is configured changes
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        subarray_component_manager.start_communicating()

        print(f"1 subarray comms: {subarray_component_manager.communication_status}")
        assert (
            subarray_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )
        print(f"2 subarray comms: {subarray_component_manager.communication_status}")
        component_state_changed_callback.assert_next_call(
            {"power_state": PowerState.ON}
        )
        print(f"3 subarray comms: {subarray_component_manager.communication_status}")

        # can't configure when resources are OFF
        resource_spec = {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }
        print(f"4 subarray comms: {subarray_component_manager.communication_status}")
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        component_state_changed_callback.assert_next_call(
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
        subarray_component_manager._station_power_state_changed(
            station_off_fqdn, PowerState.ON
        )
        component_state_changed_callback.assert_next_call({"assign_completed": None})
        print(f"5 subarray comms: {subarray_component_manager.communication_status}")

        # tmp=0
        # print("Waiting for proxies to connect.")
        # for station in subarray_component_manager._stations.values():
        #     while station.communication_status != CommunicationStatus.ESTABLISHED:
        #         time.sleep(1)
        #         print(f"{station._fqdn} comms status: {station.communication_status}")
        #         tmp=tmp+1
        #         if tmp>20:
        #             break
        # print("Finished waiting for proxies to connect")
        with pytest.raises(
            ConnectionError, match="Communication with component is not established."
        ):
            subarray_component_manager._configure(
                {
                    "stations": [{"station_id": station_off_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_off_id}],
                }
            )
        
        task_status, response = subarray_component_manager.release_all()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        time.sleep(0.1)
        component_state_changed_callback.assert_next_call(
            {"resources_changed": [set(), set(), set()]}
        )
        component_state_changed_callback.assert_next_call({"release_completed": None})
        print(f"6 subarray comms: {subarray_component_manager.communication_status}")
        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_off_fqdn],
            "station_beams": [station_beam_off_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        component_state_changed_callback.assert_next_call(
            {
                "resources_changed": [
                    {"low-mccs/station/002"},
                    {"low-mccs/subarraybeam/02"},
                    {"low-mccs/beam/02"},
                ]
            }
        )
        print(f"7 subarray comms: {subarray_component_manager.communication_status}")
        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )
        component_state_changed_callback.assert_next_call({"assign_completed": None})

        assert subarray_component_manager._stations[station_on_fqdn].communication_state == CommunicationStatus.ESTABLISHED
        with pytest.raises(
            ConnectionError, match="Communication with component is not established."
        ):
            subarray_component_manager._configure(
                {
                    "stations": [{"station_id": station_on_id}],
                    "subarray_beams": [{"subarray_beam_id": subarray_beam_off_id}],
                }
            )

        mock_station_on.Configure.assert_next_call(
            json.dumps({"station_id": station_on_id})
        )
        mock_subarray_beam_off.Configure.assert_not_called()

        task_status, response = subarray_component_manager.release_all()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        component_state_changed_callback.assert_next_call(
            {"resources_changed": [set(), set(), set()]}
        )
        component_state_changed_callback.assert_next_call({"release_completed": None})

        resource_spec = {
            "stations": [[station_off_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        component_state_changed_callback.assert_next_call(
            {
                "resources_changed": [
                    {"low-mccs/station/001"},
                    {"low-mccs/subarraybeam/03"},
                    {"low-mccs/beam/03"},
                ]
            }
        )

        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )
        component_state_changed_callback.assert_next_call({"assign_completed": None})

        with pytest.raises(
            ConnectionError, match="Communication with component is not established."
        ):
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
        component_state_changed_callback.assert_next_call(
            {"resources_changed": [set(), set(), set()]}
        )
        component_state_changed_callback.assert_next_call({"release_completed": None})

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

        component_state_changed_callback.assert_next_call(
            {
                "resources_changed": [
                    {"low-mccs/station/002"},
                    {"low-mccs/subarraybeam/03"},
                    {"low-mccs/beam/03"},
                ]
            }
        )
        # subarray connects to stations, subscribes to change events on power mode,
        # doesn't consider resource assignment to be complete until it has received an
        # event from each one. So let's fake that.
        subarray_component_manager._station_power_state_changed(
            station_on_fqdn, PowerState.ON
        )
        component_state_changed_callback.assert_next_call({"assign_completed": None})

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

        component_state_changed_callback.assert_next_call({"configured_changed": True})
        # configured_changed_callback.assert_next_call(True)
        # configure_completed_callback.assert_not_called()

        subarray_component_manager._stations[station_on_fqdn]._obs_state_changed(
            "obsState", ObsState.READY, tango.AttrQuality.ATTR_VALID
        )
        component_state_changed_callback.assert_next_call(
            {"obsstate_changed": ObsState.READY}, fqdn="low-mccs/station/002"
        )

        subarray_component_manager._subarray_beams[
            subarray_beam_on_fqdn
        ]._obs_state_changed("obsState", ObsState.READY, tango.AttrQuality.ATTR_VALID)
        component_state_changed_callback.assert_next_call(
            {"obsstate_changed": ObsState.READY}, fqdn="low-mccs/subarraybeam/03"
        )

        component_state_changed_callback.assert_next_call({"configure_completed": None})

        # deconfigure
        task_status, response = subarray_component_manager.deconfigure()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

        mock_station_off.Configure.assert_not_called()
        mock_station_on.Configure.assert_next_call(json.dumps({}))
        mock_subarray_beam_off.Configure.assert_not_called()
        mock_subarray_beam_on.Configure.assert_next_call(json.dumps({}))
        component_state_changed_callback.assert_next_call({"configured_changed": False})

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
        scanning_changed_callback: MockCallable,
        component_state_changed_callback: MockCallable,
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
        :param scanning_changed_callback: callback to be called when whether
            the subarray is scanning changes
        :param component_state_changed_callback: Callback to call when the component's state changes.
        """
        subarray_component_manager.start_communicating()
        # assert subarray_component_manager.power_state == PowerState.ON
        component_state_changed_callback.assert_next_call(
            {"power_state": PowerState.ON}
        )

        resource_spec = {
            "stations": [[station_on_fqdn]],
            "subarray_beams": [subarray_beam_on_fqdn],
            "station_beams": [station_beam_on_fqdn],
            "channel_blocks": channel_blocks,
        }
        task_status, response = subarray_component_manager.assign(resource_spec)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"

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
        time.sleep(0.2)
        assert subarray_component_manager.scan_id == scan_id

        mock_subarray_beam_on.Scan.assert_next_call(
            json.dumps({"scan_id": scan_id, "start_time": start_time})
        )
        component_state_changed_callback.assert_next_call({"scanning_changed": True})
        # scanning_changed_callback.assert_next_call(True)

        task_status, response = subarray_component_manager.end_scan()
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        component_state_changed_callback.assert_next_call({"scanning_changed": False})
        # scanning_changed_callback.assert_next_call(False)
