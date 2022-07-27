# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for the MCCS controller."""
from __future__ import annotations

import functools
import json
import logging
import threading
from typing import Any, Callable, Hashable, Iterable, Optional

from ska_control_model import (
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    TaskStatus,
)
from ska_low_mccs_common.component import (
    DeviceComponentManager,
    MccsComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs_common.resource_manager import ResourceManager, ResourcePool

from ska_low_mccs.controller import ControllerResourceManager

__all__ = ["ControllerComponentManager"]


class _StationProxy(DeviceComponentManager):
    """A controller's proxy to a station."""

    def __init__(
        self: _StationProxy,
        fqdn: str,
        subarray_fqdns: Iterable[str],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param subarray_fqdns: the FQDNs of subarrays which channel
            blocks can be assigned to.
        :param logger: the logger to be used by this object.
        :param max_workers: nos. of worker threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._channel_block_pool = ResourcePool(channel_blocks=range(1, 49))
        self._resource_manager = ResourceManager(
            subarray_fqdns,
            channel_blocks=range(1, 49),
        )

        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def allocate(
        self: _StationProxy, subarray_fqdn: str, channel_blocks: int
    ) -> ResultCode:
        """
        Allocate channel blocks to a subarray.

        This method removes the requested number of channel blocks from
        the available pool and assigns them to the provided subarray fqdn.

        :param subarray_fqdn: The fqdn of the subarray to which the channel
            blocks are to be assigned.
        :param channel_blocks: The number of channel blocks to assign to the
            subarray.

        :return: a result code
        """
        channel_blocks_to_allocate = []
        for _ in range(channel_blocks):
            channel_blocks_to_allocate.append(
                self._channel_block_pool.get_free_resource("channel_blocks")
            )
        self._resource_manager.allocate(
            subarray_fqdn, channel_blocks=channel_blocks_to_allocate
        )
        return ResultCode.OK

    def release_from_subarray(self: _StationProxy, subarray_fqdn: str) -> None:
        """
        Release all channel blocks assigned to a subarray.

        Channel blocks are released from the subarray and marked as free in the
            station proxy's device pool for reallocation whenever needed.

        :param subarray_fqdn: The fqdn of the subarray from which this station
            proxy's channel blocks are to be released.
        """
        channel_blocks_to_release = self._resource_manager.get_allocated(subarray_fqdn)
        self._resource_manager.deallocate_from(subarray_fqdn)
        self._channel_block_pool.free_resources(channel_blocks_to_release)


class _SubarrayProxy(DeviceComponentManager):
    """A controller's proxy to a subarray."""

    @check_communicating
    @check_on
    def assign_resources(
        self: _SubarrayProxy,
        station_fqdns: Iterable[Iterable[str]],
        subarray_beam_fqdns: Iterable[str],
        station_beam_fqdns: Iterable[str],
        channel_blocks: Iterable[int],
    ) -> ResultCode:
        """
        Tell the subarray what resources are assigned to it.

        :param station_fqdns: FQDNs of stations assigned to the subarray
        :param subarray_beam_fqdns: FQDNs of subarray beams assigned to
            the subarray
        :param station_beam_fqdns: FQDNs of station beams assigned to
            the subarray
        :param channel_blocks: the channel block numbers assigned to the
            subarray

        :return: a result code.
        """
        assert self._proxy is not None
        args = json.dumps(
            {
                "stations": sorted(station_fqdns),
                "subarray_beams": sorted(subarray_beam_fqdns),
                "station_beams": sorted(station_beam_fqdns),
                "channel_blocks": sorted(channel_blocks),
            }
        )
        ([result_code], _) = self._proxy.AssignResources(args)
        return result_code

    @check_communicating
    @check_on
    def release_all_resources(
        self: _SubarrayProxy,
    ) -> ResultCode:
        """
        Tell the subarray that it no longer has any resources.

        :return: a result code.
        """
        assert self._proxy is not None

        ([result_code], _) = self._proxy.ReleaseAllResources()
        return result_code

    @check_communicating
    @check_on
    def restart(
        self: _SubarrayProxy,
    ) -> ResultCode:
        """
        Tell the subarray that it no longer has any resources.

        :return: a result code.
        """
        assert self._proxy is not None
        ([result_code], _) = self._proxy.Restart()
        return result_code


class _SubarrayBeamProxy(DeviceComponentManager):
    """A controller's proxy to a subarray beam."""

    @check_communicating
    @check_on
    def write_station_ids(
        self: _SubarrayBeamProxy,
        new_station_ids: list[int],
    ) -> ResultCode:
        """
        Set the station beam's stationIds attribute.

        :param new_station_ids: the station beam's new station ids.

        :return: a result code
        """
        return self._write_station_ids(new_station_ids)

    def _write_station_ids(
        self: _SubarrayBeamProxy,
        new_station_ids: list[int],
    ) -> ResultCode:
        assert self._proxy is not None
        self._proxy.stationIds = new_station_ids
        return ResultCode.OK


class _StationBeamProxy(DeviceComponentManager):
    """A controller's proxy to a station beam."""

    @check_communicating
    @check_on
    def write_station_id(
        self: _StationBeamProxy,
        new_station_id: int,
    ) -> ResultCode:
        """
        Set the station beam's stationId attribute.

        :param new_station_id: the station beam's new station id.

        :return: a result code
        """
        return self._write_station_id(new_station_id)

    def _write_station_id(
        self: _StationBeamProxy,
        new_station_id: int,
    ) -> ResultCode:
        assert self._proxy is not None
        self._proxy.stationId = new_station_id
        return ResultCode.OK

    @check_communicating
    @check_on
    def write_subarray_id(
        self: _StationBeamProxy,
        new_subarray_id: int,
    ) -> ResultCode:
        """
        Set the station beam's stationId attribute.

        :param new_subarray_id: the station beam's new subaray id.

        :return: a result code
        """
        return self._write_subarray_id(new_subarray_id)

    def _write_subarray_id(
        self: _StationBeamProxy,
        new_subarray_id: int,
    ) -> ResultCode:
        assert self._proxy is not None
        self._proxy.subarrayId = new_subarray_id
        return ResultCode.OK

    @check_communicating
    @check_on
    def write_station_fqdn(
        self: _StationBeamProxy,
        new_station_fqdn: str,
    ) -> ResultCode:
        """
        Set the station beam's stationId attribute.

        :param new_station_fqdn: the station beam's new station fqdn.

        :return: a result code
        """
        return self._write_station_fqdn(new_station_fqdn)

    def _write_station_fqdn(
        self: _StationBeamProxy,
        new_station_fqdn: str,
    ) -> ResultCode:
        assert self._proxy is not None
        self._proxy.stationFqdn = new_station_fqdn
        return ResultCode.OK


class ControllerComponentManager(MccsComponentManager):
    """
    A component manager for an MCCS controller.

    This component manager has three jobs:

    * Monitoring of the devices in the MCCS subsystem

    * Powering the MCCS subsystem off and on

    * Allocating resources to subarrays
    """

    def __init__(
        self: ControllerComponentManager,
        subarray_fqdns: Iterable[str],
        subrack_fqdns: Iterable[str],
        station_fqdns: Iterable[str],
        subarray_beam_fqdns: Iterable[str],
        station_beam_fqdns: Iterable[str],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param subarray_fqdns: FQDNS of all subarray devices
        :param subrack_fqdns: FQDNS of all subrack devices
        :param station_fqdns: FQDNS of all station devices
        :param subarray_beam_fqdns: FQDNS of all subarray beam devices
        :param station_beam_fqdns: FQDNS of all station beam devices
        :param logger: the logger to be used by this object.
        :param max_workers: nos. of worker threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._communication_state_changed_callback = (
            communication_state_changed_callback
        )
        self._component_state_changed_callback = component_state_changed_callback

        self.__communication_state_lock = threading.Lock()
        self._device_communication_states: dict[str, CommunicationStatus] = {}
        self._device_power_states: dict[str, PowerState] = {}

        for fqdn in subarray_fqdns:
            self._device_communication_states[fqdn] = CommunicationStatus.DISABLED

        for fqdn in subrack_fqdns:
            self._device_communication_states[fqdn] = CommunicationStatus.DISABLED
            self._device_power_states[fqdn] = PowerState.UNKNOWN

        for fqdn in station_fqdns:
            self._device_communication_states[fqdn] = CommunicationStatus.DISABLED
            self._device_power_states[fqdn] = PowerState.UNKNOWN

        for fqdn in subarray_beam_fqdns:
            self._device_communication_states[fqdn] = CommunicationStatus.DISABLED

        for fqdn in station_beam_fqdns:
            self._device_communication_states[fqdn] = CommunicationStatus.DISABLED

        self._resource_manager = ControllerResourceManager(
            subarray_fqdns,
            subrack_fqdns,
            subarray_beam_fqdns,
            station_beam_fqdns,
            range(1, 49),
        )

        self._subarrays: dict[str, _SubarrayProxy] = {
            fqdn: _SubarrayProxy(
                fqdn,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, fqdn),
                functools.partial(self._component_state_changed_callback, fqdn=fqdn),
            )
            for fqdn in subarray_fqdns
        }
        self._subracks: dict[str, DeviceComponentManager] = {
            fqdn: DeviceComponentManager(
                fqdn,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, fqdn),
                functools.partial(self._component_state_changed_callback, fqdn=fqdn),
            )
            for fqdn in subrack_fqdns
        }
        self._stations: dict[Hashable, _StationProxy] = {
            fqdn: _StationProxy(
                fqdn,
                subarray_fqdns,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, fqdn),
                functools.partial(self._component_state_changed_callback, fqdn=fqdn),
            )
            for fqdn in station_fqdns
        }
        self._subarray_beams: dict[Hashable, _SubarrayBeamProxy] = {
            fqdn: _SubarrayBeamProxy(
                fqdn,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, fqdn),
                functools.partial(self._component_state_changed_callback, fqdn=fqdn),
            )
            for fqdn in subarray_beam_fqdns
        }
        self._station_beams: dict[Hashable, _StationBeamProxy] = {
            fqdn: _StationBeamProxy(
                fqdn,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, fqdn),
                functools.partial(self._component_state_changed_callback, fqdn=fqdn),
            )
            for fqdn in station_beam_fqdns
        }

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: ControllerComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

        if not self._device_communication_states:
            self.update_communication_state(CommunicationStatus.ESTABLISHED)
        else:
            for subarray_proxy in self._subarrays.values():
                subarray_proxy.start_communicating()
            for subrack_proxy in self._subracks.values():
                subrack_proxy.start_communicating()
            for station_proxy in self._stations.values():
                station_proxy.start_communicating()
            for subarray_beam_proxy in self._subarray_beams.values():
                subarray_beam_proxy.start_communicating()
            for station_beam_proxy in self._station_beams.values():
                station_beam_proxy.start_communicating()

    def stop_communicating(self: ControllerComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for subarray_proxy in self._subarrays.values():
            subarray_proxy.stop_communicating()
        for subrack_proxy in self._subracks.values():
            subrack_proxy.stop_communicating()
        for station_proxy in self._stations.values():
            station_proxy.stop_communicating()
        for subarray_beam_proxy in self._subarray_beams.values():
            subarray_beam_proxy.stop_communicating()
        for station_beam_proxy in self._station_beams.values():
            station_beam_proxy.stop_communicating()

    def _device_communication_state_changed(
        self: ControllerComponentManager,
        fqdn: str,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle communication changes.

        :param fqdn: fqdn of changed device
        :param communication_state: new status
        """
        if fqdn not in self._device_communication_states:
            self.logger.warning(
                f"Received a communication status changed event for device {fqdn} "
                "which is not managed by this controller. "
                "Probably it was released just a moment ago. "
                "The event will be discarded."
            )
            return

        self._device_communication_states[fqdn] = communication_state
        if self.communication_state == CommunicationStatus.DISABLED:
            return
        self._evaluate_communication_state()

    def _evaluate_communication_state(
        self: ControllerComponentManager,
    ) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self.__communication_state_lock:
            if (
                CommunicationStatus.DISABLED
                in self._device_communication_states.values()
            ):
                self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._device_communication_states.values()
            ):
                self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self.update_communication_state(CommunicationStatus.ESTABLISHED)
                self.update_component_state({"fault": False})

    def _evaluate_power_state(self: ControllerComponentManager) -> None:
        for power_state in [
            PowerState.UNKNOWN,
            PowerState.OFF,
            PowerState.STANDBY,
            PowerState.ON,
        ]:
            if power_state in self._device_power_states.values():
                break
        self.logger.info(
            "In ControllerComponentManager._evaluatePowerState with:\n"
            f"\tdevices: {self._device_power_states}\n"
            f"\tresult: {str(power_state)}"
        )
        self.update_component_state({"power_state": power_state})

    def _subarray_health_changed(
        self: ControllerComponentManager,
        fqdn: str,
        health: HealthState | None,
    ) -> None:
        """
        Handle a change in the health of a subarray.

        :param fqdn: the FQDN of the subarray whose health has changed.
        :param health: the new health state of the subarray, or None if
            the subarray's health should not be taken into account.
        """
        # What we're really interested in here is whether the subarray is in the right
        # adminMode. We know that when it's in the wrong adminMode, health will be
        # reported as None. So instead of subscribing to adminMode, we might as well be
        # lazy here and get at the adminMode thorough the healthState that we're already
        # subscribed to.
        self._resource_manager.set_ready(fqdn, health is not None)

    def _station_health_changed_callback(
        self: ControllerComponentManager,
        fqdn: str,
        health: HealthState | None,
    ) -> None:
        """
        Handle a change in the health of a subrack.

        :param fqdn: the FQDN of the subrack whose health has changed.
        :param health: the new health state of the subrack, or None if
            the subrack's health should not be taken into account.
        """
        self._resource_manager.set_health(
            "subracks", fqdn, health in [HealthState.OK, HealthState.DEGRADED]
        )

    def _subarray_beam_health_changed_callback(
        self: ControllerComponentManager,
        fqdn: str,
        health: HealthState | None,
    ) -> None:
        """
        Handle a change in the health of a subarray_beam.

        :param fqdn: the FQDN of the subarray_beam whose health has
            changed.
        :param health: the new health state of the subarray_beam, or
            None if the subarray_beam's health should not be taken into
            account.
        """
        self._resource_manager.set_health(
            "subarray_beams",
            fqdn,
            health in [HealthState.OK, HealthState.DEGRADED],
        )  # False for None

    def _station_beam_health_changed_callback(
        self: ControllerComponentManager,
        fqdn: str,
        health: HealthState | None,
    ) -> None:
        """
        Handle a change in the health of a station_beam.

        :param fqdn: the FQDN of the station_beam whose health has
            changed.
        :param health: the new health state of the station_beam, or
            None if the station_beam's health should not be taken into
            account.
        """
        self._resource_manager.set_health(
            "station_beams",
            fqdn,
            health in [HealthState.OK, HealthState.DEGRADED],
        )  # False for None

    @check_communicating
    def off(
        self: ControllerComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn off the MCCS subsystem.

        :param task_callback: Update task state, defaults to None

        :return: a TaskStatus and message
        """
        if len(self._stations.values()) + len(self._subracks.values()) == 0:
            return (TaskStatus.REJECTED, "No subservient devices to turn off")
        return self.submit_task(self._off, task_callback=task_callback)

    def _off(
        self: ControllerComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn off the MCCS subsystem.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        results = [station_proxy.off() for station_proxy in self._stations.values()] + [
            subrack_proxy.off() for subrack_proxy in self._subracks.values()
        ]
        completed = True
        for result in results:
            if result[0] == TaskStatus.FAILED:
                completed = False
                break
        if task_callback:
            if completed:
                task_callback(
                    status=TaskStatus.COMPLETED, result="The off command has completed"
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="The off command has failed"
                )

    @check_communicating
    def standby(
        self: ControllerComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the MCCS subsystem in standby mode.

        :param task_callback: Update task state, defaults to None

        :returns: task status and message
        """
        if len(self._stations.values()) + len(self._subracks.values()) == 0:
            return (TaskStatus.REJECTED, "No subservient devices to put into standby")
        return self.submit_task(self._standby, task_callback=task_callback)

    def _standby(
        self: ControllerComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Put the MCCS subsystem into low power standby mode.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        results = [
            station_proxy.standby() for station_proxy in self._stations.values()
        ] + [subrack_proxy.standby() for subrack_proxy in self._subracks.values()]

        completed = True
        for result in results:
            if result[0] == TaskStatus.FAILED:
                completed = False
                break
        if task_callback:
            if completed:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The standby command has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="The standby command has failed"
                )

    @check_communicating
    def on(
        self: ControllerComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn on the MCCS subsystem.

        :param task_callback: Update task state, defaults to None

        :returns: task status and message
        """
        if len(self._stations.values()) + len(self._subracks.values()) == 0:
            return (TaskStatus.REJECTED, "No subservient devices to turn on")
        return self.submit_task(self._on, task_callback=task_callback)

    def _on(
        self: ControllerComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on the MCCS subsystem.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        results = [station_proxy.on() for station_proxy in self._stations.values()] + [
            subrack_proxy.on() for subrack_proxy in self._subracks.values()
        ]
        completed = True
        for result in results:
            if result[0] == TaskStatus.FAILED:
                completed = False
                break
        if task_callback:
            if completed:
                task_callback(
                    status=TaskStatus.COMPLETED, result="The On command has completed"
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="The On command has failed"
                )

    @check_communicating
    # @check_on
    def allocate(
        self: ControllerComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Allocate a set of unallocated MCCS resources to a subarray.

        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        subarray_beam.

        :param argin: JSON-formatted string
            {
            "interface": \
            "https://schema.skao.int/ska-low-mccs-assignresources/1.0",
            "subarray_id": int,
            "subarray_beam_ids": list[int],
            "station_ids": list[list[int]],
            "channel_blocks": list[int],
            }
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id
            string to identify the command
        """
        if (
            len(self._subarrays.values())
            + len(self._stations.values())
            + len(self._subarray_beams.values())
            == 0
        ):
            return (TaskStatus.REJECTED, "No subservient devices to allocate")

        if self.power_state != PowerState.ON:
            return (TaskStatus.FAILED, "Controller is not turned on.")

        kwargs = json.loads(argin)
        subarray_id = kwargs.get("subarray_id")

        subarray_beam_ids = kwargs.get("subarray_beam_ids", list())
        subarray_beam_fqdns = [
            f"low-mccs/subarraybeam/{subarray_beam_id:02d}"
            for subarray_beam_id in subarray_beam_ids
        ]
        station_ids = kwargs.get("station_ids", list())

        station_fqdns = []
        for station_id_list in station_ids:
            station_fqdns.append(
                [f"low-mccs/station/{station_id:03d}" for station_id in station_id_list]
            )

        channel_blocks = kwargs.get("channel_blocks", list())

        return self.submit_task(
            self._allocate,
            args=[subarray_id, station_fqdns, subarray_beam_fqdns, channel_blocks],
            task_callback=task_callback,
        )

    def _allocate(
        self: ControllerComponentManager,
        subarray_id: int,
        station_fqdns: Iterable[Iterable[str]],
        subarray_beam_fqdns: Iterable[str],
        channel_blocks: Iterable[int],
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Allocate resources to a subarray.

        :param subarray_id: id of the subarray to which resources are to
            be allocated
        :param station_fqdns: lists of FQDNs of the stations to be allocated to
            each subarray beam
        :param subarray_beam_fqdns: FQDNs of the subarray beams to be
            allocated to the subarray
        :param channel_blocks: numbers of the channel blocks to be allocated
            to the subarray from each station in the associated grouping
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises ValueError: if trying to assign a station not in the
            controller's Stations
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        subarray_fqdn = f"low-mccs/subarray/{subarray_id:02d}"

        flattened_station_fqdns = []
        station_groups = []

        station_fqdns = list(station_fqdns)
        subarray_beam_fqdns = list(subarray_beam_fqdns)
        channel_blocks = list(channel_blocks)

        for group_index, station_group in enumerate(station_fqdns):
            station_groups.append(list(station_group))
            for station_fqdn in station_group:
                # stations are not managed by the resource manager, so we have
                # to explicitely check if they're valid FQDNs here
                if station_fqdn not in self._stations.keys():
                    raise ValueError(f"Unsupported resources: {station_fqdn}.")
                if (
                    not self._stations[station_fqdn].allocate(
                        subarray_fqdn, channel_blocks[group_index]
                    )
                    == ResultCode.OK
                ):
                    raise ValueError(
                        f"Station {station_fqdn} has no more frequency channel capacity"
                        f"(attempted to allocate {channel_blocks[group_index]} blocks)."
                    )
                flattened_station_fqdns.append(station_fqdn)

        # need (subarray-beams * stations) number of station-beams from pool
        station_beam_fqdns = []
        station_beams_required = len(list(subarray_beam_fqdns)) * len(
            flattened_station_fqdns
        )
        for _ in range(station_beams_required):
            station_beam_fqdns.append(
                str(
                    self._resource_manager.resource_pool.get_free_resource(
                        "station_beams"
                    )
                )
            )

        # This needs a better solution to handle the scope of the trapped exception.
        allocate_exc = None
        try:
            self._resource_manager.allocate(
                subarray_fqdn,
                subarray_beams=subarray_beam_fqdns,
                station_beams=station_beam_fqdns,
                channel_blocks=channel_blocks,
            )
            allocate_result_code = ResultCode.OK
        except ValueError as e:
            allocate_result_code = ResultCode.FAILED
            allocate_exc = e

        if allocate_result_code == ResultCode.OK:
            assign_result_code = self._subarrays[subarray_fqdn].assign_resources(
                station_fqdns,
                subarray_beam_fqdns,
                station_beam_fqdns,
                channel_blocks,
            )
        else:
            assign_result_code = ResultCode.FAILED

        # don't forget to release resources if allocate or assign were unsuccessful:
        if ResultCode.FAILED in [assign_result_code, allocate_result_code]:
            self._release_all(subarray_id)
        else:
            for i, subarray_beam_fqdn in enumerate(subarray_beam_fqdns):
                self._subarray_beams[subarray_beam_fqdn].write_station_ids(
                    [
                        int(station_fqdn.split("/")[2])
                        for station_fqdn in station_groups[i]
                    ]
                )
                for j, station_fqdn in enumerate(station_fqdns[i]):
                    station_beam_index = i * (j + 1)
                    self._station_beams[
                        station_beam_fqdns[station_beam_index]
                    ].write_station_id(int(station_fqdn.split("/")[2]))
                    self._station_beams[
                        station_beam_fqdns[station_beam_index]
                    ].write_subarray_id(subarray_id)

        # TODO wait for the respective LRC's to complete, whilst reporting progress
        if task_callback:
            if allocate_result_code == ResultCode.FAILED:
                task_callback(
                    status=TaskStatus.FAILED,
                    result=(
                        "The allocate command has failed. Exception message: "
                        f"{allocate_exc}"
                    ),
                )
            elif assign_result_code == ResultCode.FAILED:
                task_callback(
                    status=TaskStatus.FAILED, result="The assign command has failed"
                )
            else:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The allocate command has completed",
                )

    @check_communicating
    #    @check_on
    def release(
        self: ControllerComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Release a subarray's resources.

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag.
        :param task_callback: Update task state, defaults to None

        :return: a TaskStatus and message
        """
        if len(self._subarrays.values()) == 0:
            return (TaskStatus.REJECTED, "No subservient subarray devices to release")
        if self.power_state != PowerState.ON:
            return (TaskStatus.FAILED, "Controller is not turned on.")

        kwargs = json.loads(argin)
        if kwargs["release_all"]:
            subarray_id = kwargs["subarray_id"]
            return self.submit_task(
                self._release_all, args=[subarray_id], task_callback=task_callback
            )
        else:
            return (
                TaskStatus.FAILED,
                "Currently Release can only be used to release all resources from a subarray.",
            )

    def _release_all(
        self: ControllerComponentManager,
        subarray_id: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Deallocate all resources from a subarray.

        :param subarray_id: Id of the subarray from which all resources
            are to be deallocated
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        subarray_fqdn = f"low-mccs/subarray/{subarray_id:02}"

        allocated = self._resource_manager.get_allocated(subarray_fqdn)
        if not allocated:
            return

        self._resource_manager.deallocate_from(subarray_fqdn)
        station_beams = allocated.get("station_beams", [])
        for station_beam_fqdn in station_beams:
            self._station_beams[station_beam_fqdn].write_subarray_id(0)
            self._station_beams[station_beam_fqdn].write_station_id(0)
            self._station_beams[station_beam_fqdn].write_station_fqdn("")
        self._resource_manager.resource_pool.free_resources(
            {"station_beams": station_beams}
        )

        for station_proxy in self._stations.values():
            station_proxy.release_from_subarray(subarray_fqdn)

        result_code = self._subarrays[subarray_fqdn].release_all_resources()
        # TODO wait for the respective LRC's to complete, whilst reporting progress
        if task_callback:
            if ResultCode.FAILED == result_code:
                task_callback(
                    status=TaskStatus.FAILED, result="The release command has failed"
                )
            else:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The release command has completed",
                )

    @check_communicating
    #    @check_on
    def restart_subarray(
        self: ControllerComponentManager,
        subarray_id: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Restart an MCCS subarray.

        :param subarray_id: an integer subarray_id.
        :param task_callback: Update task state, defaults to None

        :return: a task status and a message
        """
        if len(self._subarrays.values()) == 0:
            return (TaskStatus.REJECTED, "No subservient subarray devices to restart")
        if self.power_state != PowerState.ON:
            return (TaskStatus.FAILED, "Controller is not turned on.")

        return self.submit_task(
            self._restart_subarray,
            [f"low-mcss/subarray/{subarray_id:02d}"],
            task_callback=task_callback,
        )

    def _restart_subarray(
        self: ControllerComponentManager,
        subarray_fqdn: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Deallocate all resources from a subarray.

        :param subarray_fqdn: FQDN of the subarray from which all
            resources are to be deallocated
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        self._resource_manager.deallocate_from(subarray_fqdn)

        # TODO does this return ResultCode or TaskStatus
        result = self._subarrays[subarray_fqdn].restart()
        if task_callback:
            if ResultCode.FAILED == result:
                task_callback(
                    status=TaskStatus.FAILED, result="The restart command has failed"
                )
            else:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The restart command has completed",
                )
