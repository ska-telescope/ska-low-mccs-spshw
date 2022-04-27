# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for subarrays."""
from __future__ import annotations

import functools
import json
import logging
import threading
from typing import Any, Callable, Optional, Sequence

import ska_tango_base.subarray
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, ObsState, PowerState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.component import (
    MccsComponentManager,
    ObsDeviceComponentManager,
    check_communicating,
    check_on,
)

__all__ = ["SubarrayComponentManager"]


class _StationProxy(ObsDeviceComponentManager):
    """A subarray's proxy to its stations."""

    @check_communicating
    @check_on
    def configure(self: _StationProxy, configuration: dict) -> tuple[TaskStatus, str]:
        """
        Configure the station.

        :param configuration: the configuration to be applied to this
            station

        :return: A task status and response message.
        """
        print("In station proxy configure.")
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        (result_code, unique_id) = self._proxy.Configure(configuration_str)
        return (result_code, unique_id)


class _SubarrayBeamProxy(ObsDeviceComponentManager):
    """A subarray's proxy to its subarray beams."""

    @check_communicating
    @check_on
    def configure(
        self: _SubarrayBeamProxy, configuration: dict
    ) -> tuple[TaskStatus, str]:
        """
        Configure the subarray beam.

        :param configuration: the configuration to be applied to this
            subarray beam

        :return: A task status and response message.
        """
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        (result_code, unique_id) = self._proxy.Configure(configuration_str)
        return (result_code, unique_id)

    @check_communicating
    @check_on
    def scan(
        self: _SubarrayBeamProxy, scan_id: int, start_time: float
    ) -> tuple[TaskStatus, str]:
        """
        Start the subarray beam scanning.

        :param scan_id: the id of the scan
        :param start_time: the start time of the scan

        :return: A task status and response message.
        """
        assert self._proxy is not None
        scan_arg = json.dumps({"scan_id": scan_id, "start_time": start_time})
        ([result_code], unique_id) = self._proxy.Scan(scan_arg)
        return (result_code, unique_id)


class _StationBeamProxy(ObsDeviceComponentManager):
    """A subarray's proxy to its station beams."""

    @check_communicating
    @check_on
    def configure(
        self: _StationBeamProxy, configuration: dict
    ) -> tuple[TaskStatus, str]:
        """
        Configure the station beam.

        :param configuration: the configuration to be applied to this
            station beam

        :return: A task status and response message.
        """
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        ([result_code], unique_id) = self._proxy.Configure(configuration_str)
        return (result_code, unique_id)


class SubarrayComponentManager(
    MccsComponentManager,
    ska_tango_base.subarray.SubarrayComponentManager,
):
    """A component manager for a subarray."""

    def __init__(
        self: SubarrayComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        :param max_workers: Maximum number of workers in the worker pool. Defaults to None.
        """
        # Not used *yet*. Below self._callbacks to be removed eventually.
        self._component_state_changed_callback = component_state_changed_callback

        self._assign_completed_callback = component_state_changed_callback
        self._release_completed_callback = component_state_changed_callback
        self._configure_completed_callback = component_state_changed_callback
        self._abort_completed_callback = component_state_changed_callback
        self._obsreset_completed_callback = component_state_changed_callback
        self._restart_completed_callback = component_state_changed_callback
        self._resources_changed_callback = component_state_changed_callback
        self._configured_changed_callback = component_state_changed_callback
        self._scanning_changed_callback = component_state_changed_callback
        self._obs_fault_callback = component_state_changed_callback
        self._station_health_changed_callback = component_state_changed_callback
        self._subarray_beam_health_changed_callback = component_state_changed_callback
        self._station_beam_health_changed_callback = component_state_changed_callback

        self._device_communication_statuses: dict[str, CommunicationStatus] = {}
        self._station_power_modes: dict[str, Optional[PowerState]] = {}
        self._device_obs_states: dict[str, Optional[ObsState]] = {}
        self._is_assigning = False
        self._configuring_resources: set[str] = set()
        self._station_groups: list[list[str]] = list()
        self._stations: dict[str, _StationProxy] = dict()
        self._subarray_beams: dict[str, _SubarrayBeamProxy] = dict()
        self._station_beams: dict[str, _StationBeamProxy] = dict()
        self._channel_blocks: list[int] = list()
        self._max_workers = max_workers

        self._scan_id: Optional[int] = None

        super().__init__(
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: SubarrayComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()
        if self._stations or self._subarray_beams:
            for station_proxy in self._stations.values():
                station_proxy.start_communicating()
            for subarray_beam_proxy in self._subarray_beams.values():
                subarray_beam_proxy.start_communicating()
            for station_beam_proxy in self._station_beams.values():
                station_beam_proxy.start_communicating()
        else:
            self.update_communication_status(CommunicationStatus.ESTABLISHED)
            with self._power_state_lock:
                self._component_state_changed_callback(state_change={"power_state": PowerState.ON})

    def stop_communicating(self: SubarrayComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for fqdn in self._stations:
            self._stations[fqdn].stop_communicating()

        for fqdn in self._subarray_beams:
            self._subarray_beams[fqdn].stop_communicating()

        for fqdn in self._station_beams:
            self._station_beams[fqdn].stop_communicating()

    @property
    def scan_id(self: SubarrayComponentManager) -> Optional[int]:
        """
        Return the scan id, or None if a scan is not current.

        :return: the scan id, or None if a scan is not current.
        """
        return self._scan_id

    @property
    def station_fqdns(self: SubarrayComponentManager) -> set[str]:
        """
        Return the set of FQDNs of stations assigned to this subarray.

        :return: the set of FQDNs of stations assigned to this subarray.
        """
        return set(self._stations.keys())

    @check_communicating
    def assign(
        self: SubarrayComponentManager,
        resource_spec: dict,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `AssignResources` slow command.

        This method returns immediately after it is submitted for execution.

        :param resource_spec: resource specification; for example

            .. code-block:: python

                {
                    "subarray_beams": ["low-mccs/subarraybeam/01"],
                    "stations": [["low-mccs/station/001", "low-mccs/station/002"]],
                    "station_beams": ["low-mccs/beam/01","low-mccs/beam/02"]
                    "channel_blocks": [3]
                }
        :param task_callback: Update task state, defaults to None
        :return: a result code and response message.
        """
        return self.submit_task(
            self._assign,
            args=[resource_spec],
            task_callback=task_callback,
        )

    @check_communicating
    def _assign(  # type: ignore[override]
        self: SubarrayComponentManager,
        resource_spec: dict,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> ResultCode:
        """
        Assign resources to this subarray.

        This is just for communication and health roll-up, resource management is done by controller.

        :param resource_spec: resource specification; for example

            .. code-block:: python

                {
                    "subarray_beams": ["low-mccs/subarraybeam/01"],
                    "stations": [["low-mccs/station/001", "low-mccs/station/002"]],
                    "station_beams": ["low-mccs/beam/01","low-mccs/beam/02"]
                    "channel_blocks": [3]
                }
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        station_fqdns: list[list[str]] = resource_spec.get("stations", [])
        subarray_beam_fqdns: list[str] = resource_spec.get("subarray_beams", [])
        station_beam_fqdns: list[str] = resource_spec.get("station_beams", [])
        channel_blocks: list[int] = resource_spec.get("channel_blocks", [])

        station_fqdn_set = self._flatten_new_station_groups(station_fqdns)
        self._channel_blocks = self._channel_blocks + channel_blocks

        station_fqdns_to_add = sorted(station_fqdn_set) - self._stations.keys()
        subarray_beam_fqdns_to_add = subarray_beam_fqdns - self._subarray_beams.keys()
        station_beam_fqdns_to_add = station_beam_fqdns - self._station_beams.keys()
        fqdns_to_add = station_fqdns_to_add.union(
            subarray_beam_fqdns_to_add, station_beam_fqdns_to_add
        )

        if fqdns_to_add:
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
            for fqdn in fqdns_to_add:
                self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED
                self._device_obs_states[fqdn] = ObsState.IDLE
            self._evaluate_communication_status()

            for fqdn in station_fqdns_to_add:
                self._stations[fqdn] = _StationProxy(
                    fqdn,
                    self.logger,
                    self._max_workers,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    functools.partial(
                        self._component_state_changed_callback, fqdn=fqdn
                    ),
                )
            for fqdn in subarray_beam_fqdns_to_add:
                self._subarray_beams[fqdn] = _SubarrayBeamProxy(
                    fqdn,
                    self.logger,
                    self._max_workers,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    functools.partial(
                        self._component_state_changed_callback, fqdn=fqdn
                    ),
                )
            for fqdn in station_beam_fqdns_to_add:
                self._station_beams[fqdn] = _StationBeamProxy(
                    fqdn,
                    self.logger,
                    self._max_workers,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    functools.partial(
                        self._component_state_changed_callback, fqdn=fqdn
                    ),
                )
            self._resources_changed_callback(
                {
                    "resources_changed": [
                        set(self._stations.keys()),
                        set(self._subarray_beams.keys()),
                        set(self._station_beams.keys()),
                    ]
                }
            )

            self._is_assigning = True
            for fqdn in station_fqdns_to_add:
                self._stations[fqdn].start_communicating()
            for fqdn in subarray_beam_fqdns_to_add:
                self._subarray_beams[fqdn].start_communicating()
            for fqdn in station_beam_fqdns_to_add:
                self._station_beams[fqdn].start_communicating()

        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED, result="AssignResources has completed."
            )

        return ResultCode.OK

    def _flatten_new_station_groups(
        self: SubarrayComponentManager,
        station_fqdns: list[list[str]],
    ) -> set:
        """
        Add station groups to this subarray component manager's _station_groups.

        This is for housekeeping to store the station heirarchy for the assigned_resources_dict attribute.
        A flattened (1-D) array is returned for adding new fqdns to the component manager's Station Proxies.

        :param station_fqdns: list of lists of stations

        :return: a (1-D) set of station fqdns
        """
        station_fqdn_set = set()
        for station_group in station_fqdns:
            for station_fqdn in station_group:
                station_fqdn_set.add(station_fqdn)
            self._station_groups.append(station_group)

        return station_fqdn_set

    @property  # type: ignore[misc]
    @check_communicating
    def assigned_resources(
        self: SubarrayComponentManager,
    ) -> set:
        """
        Return this subarray's resources.

        :return: this subarray's resources.
        """
        return (
            set(self._stations) | set(self._subarray_beams) | set(self._station_beams)
        )

    @property  # type: ignore[misc]
    @check_communicating
    def assigned_resources_dict(
        self: SubarrayComponentManager,
    ) -> dict[str, Sequence[Any]]:
        """
        Return a dictionary of resource types and fqdns.

        :return: this subarray's resources.
        """
        return {
            "stations": self._station_groups,
            "subarray_beams": sorted(self._subarray_beams.keys()),
            "station_beams": sorted(self._station_beams.keys()),
            "channel_blocks": self._channel_blocks,
        }

    @check_communicating
    def release(  # type: ignore[override]
        self: SubarrayComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `release` slow command.

        :param argin: list of resource fqdns to release.
        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._release,
            args=[argin],
            task_callback=task_callback,
        )

    @check_communicating
    def _release(  # type: ignore[override]
        self: SubarrayComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Release resources from this subarray.

        :param argin: list of resource fqdns to release.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises NotImplementedError: because MCCS Subarray cannot perform a
            partial release of resources.
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="Not Implemented: MCCS Subarray cannot partially release resources.",
            )
        raise NotImplementedError("MCCS Subarray cannot partially release resources.")

    @check_communicating
    def release_all(
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `ReleaseAllResources` slow command.

        Release all resources from this subarray.
        :param task_callback: Update task state, defaults to None

        :return: a result code
        """
        return self.submit_task(
            self._release_all,
            args=[],
            task_callback=task_callback,
        )

    @check_communicating
    def _release_all(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> ResultCode:
        """
        Release all resources from this subarray.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        if self._stations or self._subarray_beams or self._station_beams:
            self._stations.clear()
            self._station_groups.clear()
            self._subarray_beams.clear()
            self._station_beams.clear()
            self._channel_blocks.clear()
            self._device_communication_statuses.clear()
            self._device_obs_states.clear()

            self._resources_changed_callback(
                {
                    "resources_changed": [
                        set(self._stations.keys()),
                        set(self._subarray_beams.keys()),
                        set(self._station_beams.keys()),
                    ]
                }
            )
            self._evaluate_communication_status()
        self._release_completed_callback({"release_completed": None})

        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED, result="ReleaseAllResources has completed."
            )
        return ResultCode.OK

    @check_communicating
    def configure(  # type: ignore[override]
        self: SubarrayComponentManager,
        configuration: dict[str, Any],
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `configure` slow command.

        :param configuration: the configurations to be applied
        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._configure,
            args=[configuration],
            task_callback=task_callback,
        )

    @check_communicating
    def _configure(  # type: ignore[override]
        self: SubarrayComponentManager,
        configuration: dict[str, Any],
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> ResultCode:
        """
        Configure the resources for a scan.

        :param configuration: the configurations to be applied
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        print("In _configure")
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        stations = configuration["stations"]
        station_configuration = {station["station_id"]: station for station in stations}
        subarray_beams = configuration["subarray_beams"]
        subarray_beam_configuration = {
            subarray_beam["subarray_beam_id"]: subarray_beam
            for subarray_beam in subarray_beams
        }
        print("Before station config")
        result_code = self._configure_stations(station_configuration)
        print("After station config")
        print(result_code)
        if result_code != ResultCode.FAILED:
            result_code = self._configure_subarray_beams(subarray_beam_configuration)
        self._configured_changed_callback({"configured_changed": True})

        print(result_code)
        if result_code == ResultCode.OK:
            self._configure_completed_callback({"configure_completed": None})

        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED, result="Configure has completed."
            )
        return result_code

    def _configure_stations(
        self: SubarrayComponentManager,
        station_configuration: dict[str, Any],
    ) -> ResultCode:
        """
        Configure the station resources for a scan.

        :param station_configuration: the station configuration to be applied

        :return: a result code
        """
        print("in _config stations")
        result_code = ResultCode.OK
        for (station_id, configuration) in station_configuration.items():
            station_fqdn = f"low-mccs/station/{station_id:03d}"
            station_proxy = self._stations[station_fqdn]
            print(f"-- before configure call for {station_fqdn}")
            print(station_proxy.communication_status)
            print(station_proxy.power_state)
            proxy_result_code, response = station_proxy.configure(configuration)
            print("-- after configure call")
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
            elif proxy_result_code == ResultCode.QUEUED:
                self._configuring_resources.add(station_fqdn)
                self._device_obs_states[station_fqdn] = ObsState.CONFIGURING
                if result_code == ResultCode.OK:
                    result_code = ResultCode.QUEUED
        return result_code

    def _configure_subarray_beams(
        self: SubarrayComponentManager,
        subarray_beam_configuration: dict[str, Any],
    ) -> ResultCode:
        """
        Configure the subarray beam resources for a scan.

        :param subarray_beam_configuration: the subarray beam configuration to be applied

        :return: a result code
        """
        result_code = ResultCode.OK
        for (
            subarray_beam_id,
            configuration,
        ) in subarray_beam_configuration.items():
            subarray_beam_fqdn = f"low-mccs/subarraybeam/{subarray_beam_id:02d}"
            subarray_beam_proxy = self._subarray_beams[subarray_beam_fqdn]
            proxy_result_code = subarray_beam_proxy.configure(configuration)
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
            elif proxy_result_code == ResultCode.QUEUED:
                self._configuring_resources.add(subarray_beam_fqdn)
                if result_code == ResultCode.OK:
                    result_code = ResultCode.QUEUED
        return result_code

    @check_communicating
    def scan(  # type: ignore[override]
        self: SubarrayComponentManager,
        scan_id: int,
        start_time: float,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `Scan` command.

        :param scan_id: the id of the scan
        :param start_time: the start time of the scan
        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._scan,
            args=[scan_id, start_time],
            task_callback=task_callback,
        )

    @check_communicating
    def _scan(  # type: ignore[override]
        self: SubarrayComponentManager,
        scan_id: int,
        start_time: float,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> ResultCode:
        """
        Start scanning.

        :param scan_id: the id of the scan
        :param start_time: the start time of the scan
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        self._scan_id = scan_id

        result_code = ResultCode.OK
        for subarray_beam_proxy in self._subarray_beams.values():                
            proxy_result_code = subarray_beam_proxy.scan(scan_id, start_time)
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
        self._scanning_changed_callback({"scanning_changed": True})
        if task_callback is not None:
            task_callback(status=TaskStatus.COMPLETED, result="Scan has completed.")
        return result_code

    @check_communicating
    def end_scan(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `end_scan` slow command.

        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._end_scan,
            args=[],
            task_callback=task_callback,
        )

    @check_communicating
    def _end_scan(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> ResultCode:
        """
        End scanning.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        self._scan_id = None

        # Stuff goes here. This should tell the subarray beam device to
        # stop scanning, but that device doesn't support it yet.
        self._scanning_changed_callback({"scanning_changed": False})
        if task_callback is not None:
            task_callback(status=TaskStatus.COMPLETED, result="EndScan has completed.")
        return ResultCode.OK

    @check_communicating
    def deconfigure(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `deconfigure` slow command.

        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._deconfigure,
            args=[],
            task_callback=task_callback,
        )

    @check_communicating
    def _deconfigure(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Deconfigure resources.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        for station_proxy in self._stations.values():
            proxy_task_status, response = station_proxy.configure({})
        for subarray_beam_proxy in self._subarray_beams.values():
            proxy_task_status, response = subarray_beam_proxy.configure({})
        self._configured_changed_callback({"configured_changed": False})

        # TODO: Will need to wait here until all subservient devices indicate they've finished and then call the task_callback indicating the results.
        # Might need the task statuses so leave them in (unused) for now.
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED, result="End/Deconfigure has completed."
            )

    @check_communicating
    def abort(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Abort the observation.

        :return: a result code
        """
        # Stuff goes here. This should tell the subarray beam device to
        # abort scanning, but that device doesn't support it yet.
        self._abort_completed_callback({"abort_completed": None})
        return ResultCode.OK

    @check_communicating
    def obsreset(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `ObsReset` slow command.

        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._obsreset,
            args=[],
            task_callback=task_callback,
        )

    @check_communicating
    def _obsreset(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Reset the observation by returning to unconfigured state.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        # other stuff here
        self.deconfigure()
        self._obsreset_completed_callback({"obsreset_completed": None})
        if task_callback is not None:
            task_callback(status=TaskStatus.COMPLETED, result="ObsReset has completed.")

    @check_communicating
    def restart(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the `Restart` slow command.

        :param task_callback: Update task state, defaults to None

        :return: A task status and response message.
        """
        return self.submit_task(
            self._restart,
            args=[],
            task_callback=task_callback,
        )

    @check_communicating
    def _restart(  # type: ignore[override]
        self: SubarrayComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Restart the subarray by returning to unresourced state.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        # other stuff here
        self.deconfigure()
        self.release_all(task_callback=task_callback)
        self._restart_completed_callback({"restart_completed": None})
        if task_callback is not None:
            task_callback(status=TaskStatus.COMPLETED, result="Restart has completed.")

    def send_transient_buffer(
        self: SubarrayComponentManager,
        argin: list[int],
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the send_transient_buffer slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state. Defaults to None.

        :return: Task status and response message.
        """
        return self.submit_task(
            self._send_transient_buffer, args=[argin], task_callback=task_callback,
        )

    @check_communicating
    def _send_transient_buffer(
        self: SubarrayComponentManager,
        argin: list[int],
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Send the transient buffer.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :return: a result code
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        # do stuff here
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="send_transient_buffer command completed.",
            )

    def _device_communication_status_changed(
        self: SubarrayComponentManager,
        fqdn: str,
        communication_status: CommunicationStatus,
    ) -> None:
        if fqdn not in self._device_communication_statuses:
            self.logger.warning(
                "Received a communication status changed event for a device not "
                "managed by this subarray. Probably it was released just a moment ago. "
                "The event will be discarded."
            )
            return

        self._device_communication_statuses[fqdn] = communication_status
        if self.communication_status == CommunicationStatus.DISABLED:
            return

        self._evaluate_communication_status()

    def _evaluate_communication_status(self: SubarrayComponentManager) -> None:
        if CommunicationStatus.DISABLED in self._device_communication_statuses:
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
        elif CommunicationStatus.NOT_ESTABLISHED in self._device_communication_statuses:
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
        else:
            self.update_communication_status(CommunicationStatus.ESTABLISHED)

    def _station_power_state_changed(
        self: SubarrayComponentManager,
        fqdn: str,
        power_mode: PowerState,
    ) -> None:
        self._station_power_modes[fqdn] = power_mode
        if self._is_assigning and all(
            power_mode is not None for power_mode in self._station_power_modes.values()
        ):
            self._is_assigning = False
            self._assign_completed_callback({"assign_completed": None})

    def _device_obs_state_changed(
        self: SubarrayComponentManager,
        fqdn: str,
        obs_state: ObsState,
    ) -> None:
        self._device_obs_states[fqdn] = obs_state
        if obs_state == ObsState.READY and fqdn in self._configuring_resources:
            self._configuring_resources.remove(fqdn)
            if not self._configuring_resources:
                self._configure_completed_callback({"configure_completed": None})
