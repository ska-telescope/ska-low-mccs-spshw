# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for the MCCS controller."""
from __future__ import annotations

import functools
import json
import logging
import threading
from typing import Callable, Hashable, Optional, Iterable

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    MccsComponentManager,
    DeviceComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs.controller import ControllerResourceManager
from ska_low_mccs.resource_manager import ResourceManager, ResourcePool


__all__ = ["ControllerComponentManager"]


class _StationProxy(DeviceComponentManager):
    """A controller's proxy to a station."""

    def __init__(
        self: _StationProxy,
        fqdn: str,
        subarray_fqdns: Iterable[str],
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Optional[Callable[[PowerMode], None]],
        component_fault_callback: Optional[Callable[[bool], None]],
        health_changed_callback: Optional[
            Callable[[Optional[HealthState]], None]
        ] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param subarray_fqdns: the FQDNs of subarrays which channel
            blocks can be assigned to.
        :param message_queue: the message queue to be used by this
            component manager
        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param health_changed_callback: callback to be called when the
            health state of the device changes. The value it is called
            with will normally be a HealthState, but may be None if the
            admin mode of the device indicates that the device's health
            should not be included in upstream health rollup.
        """
        self._channel_block_pool = ResourcePool(channel_blocks=range(1, 49))
        self._resource_manager = ResourceManager(
            subarray_fqdns,
            channel_blocks=range(1, 49),
        )

        super().__init__(
            fqdn,
            message_queue,
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            health_changed_callback,
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

        :return: a result code.
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
        station_fqdns: Iterable[str],
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
        (result_code, _) = self._proxy.AssignResources(
            json.dumps(
                {
                    "stations": sorted(station_fqdns),
                    "subarray_beams": sorted(subarray_beam_fqdns),
                    "station_beams": sorted(station_beam_fqdns),
                    "channel_blocks": sorted(channel_blocks),
                }
            )
        )
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
        (result_code, _) = self._proxy.ReleaseAllResources()
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
        (result_code, _) = self._proxy.Restart()
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
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        subrack_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        station_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        subarray_beam_health_changed_callback: Callable[
            [str, Optional[HealthState]], None
        ],
        station_beam_health_changed_callback: Callable[
            [str, Optional[HealthState]], None
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param subarray_fqdns: FQDNS of all subarray devices
        :param subrack_fqdns: FQDNS of all subrack devices
        :param station_fqdns: FQDNS of all station devices
        :param subarray_beam_fqdns: FQDNS of all subarray beam devices
        :param station_beam_fqdns: FQDNS of all station beam devices
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param subrack_health_changed_callback: callback to be called
            when the health of one of this controller's subracks changes
        :param station_health_changed_callback: callback to be called
            when the health of one of this controller's stations changes
        :param subarray_beam_health_changed_callback: callback to be
            called when the health of one of this controller's subarray beams changes
        :param station_beam_health_changed_callback: callback to be
            called when the health of one of this controller's station beams changes
        """
        self._station_health_changed_callback = station_health_changed_callback
        self._subarray_beam_health_changed_callback = (
            subarray_beam_health_changed_callback
        )
        self._station_beam_health_changed_callback = (
            station_beam_health_changed_callback
        )

        self.__communication_status_lock = threading.Lock()
        self._device_communication_statuses: dict[str, CommunicationStatus] = {}

        self.__power_mode_lock = threading.Lock()
        self._station_power_modes: dict[str, PowerMode] = {}
        self._subrack_power_modes: dict[str, PowerMode] = {}

        for fqdn in subarray_fqdns:
            self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED

        for fqdn in subrack_fqdns:
            self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED
            self._subrack_power_modes[fqdn] = PowerMode.UNKNOWN

        for fqdn in station_fqdns:
            self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED
            self._station_power_modes[fqdn] = PowerMode.UNKNOWN

        for fqdn in subarray_beam_fqdns:
            self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED

        for fqdn in station_beam_fqdns:
            self._device_communication_statuses[fqdn] = CommunicationStatus.DISABLED

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
                functools.partial(self._device_communication_status_changed, fqdn),
                None,
                None,
                functools.partial(self._subarray_health_changed, fqdn),
            )
            for fqdn in subarray_fqdns
        }
        self._subracks: dict[str, DeviceComponentManager] = {
            fqdn: DeviceComponentManager(
                fqdn,
                logger,
                functools.partial(self._device_communication_status_changed, fqdn),
                functools.partial(self._subrack_power_mode_changed, fqdn),
                None,
                functools.partial(subrack_health_changed_callback, fqdn),
            )
            for fqdn in subrack_fqdns
        }
        self._stations: dict[Hashable, _StationProxy] = {
            fqdn: _StationProxy(
                fqdn,
                subarray_fqdns,
                logger,
                functools.partial(self._device_communication_status_changed, fqdn),
                functools.partial(self._station_power_mode_changed, fqdn),
                None,
                functools.partial(self._station_health_changed, fqdn),
            )
            for fqdn in station_fqdns
        }
        self._subarray_beams: dict[Hashable, _SubarrayBeamProxy] = {
            fqdn: _SubarrayBeamProxy(
                fqdn,
                logger,
                functools.partial(self._device_communication_status_changed, fqdn),
                None,
                None,
                functools.partial(self._subarray_beam_health_changed, fqdn),
            )
            for fqdn in subarray_beam_fqdns
        }
        self._station_beams: dict[Hashable, _StationBeamProxy] = {
            fqdn: _StationBeamProxy(
                fqdn,
                logger,
                functools.partial(self._device_communication_status_changed, fqdn),
                None,
                None,
                functools.partial(self._station_beam_health_changed, fqdn),
            )
            for fqdn in station_beam_fqdns
        }

        super().__init__(
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            None,
        )

    def start_communicating(self: ControllerComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

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

    def _device_communication_status_changed(
        self: ControllerComponentManager,
        fqdn: str,
        communication_status: CommunicationStatus,
    ) -> None:
        if fqdn not in self._device_communication_statuses:
            self.logger.warning(
                f"Received a communication status changed event for device {fqdn} "
                "which is not managed by this controller. "
                "Probably it was released just a moment ago. "
                "The event will be discarded."
            )
            return

        self._device_communication_statuses[fqdn] = communication_status
        if self.communication_status == CommunicationStatus.DISABLED:
            return
        self._evaluate_communication_status()

    def _evaluate_communication_status(self: ControllerComponentManager) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self.__communication_status_lock:
            if (
                CommunicationStatus.DISABLED
                in self._device_communication_statuses.values()
            ):
                self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._device_communication_statuses.values()
            ):
                self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self.update_communication_status(CommunicationStatus.ESTABLISHED)
                self.update_component_fault(False)

    def _subrack_power_mode_changed(
        self: ControllerComponentManager,
        fqdn: str,
        power_mode: PowerMode,
    ) -> None:
        self._subrack_power_modes[fqdn] = power_mode
        self._evaluate_power_mode()

    def _station_power_mode_changed(
        self: ControllerComponentManager,
        fqdn: str,
        power_mode: PowerMode,
    ) -> None:
        self._station_power_modes[fqdn] = power_mode
        self._evaluate_power_mode()

    def _evaluate_power_mode(self: ControllerComponentManager) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self.__power_mode_lock:
            for power_mode in [
                PowerMode.UNKNOWN,
                PowerMode.OFF,
                PowerMode.STANDBY,
                PowerMode.ON,
            ]:
                if (
                    power_mode in self._subrack_power_modes.values()
                    or power_mode in self._station_power_modes.values()
                ):
                    break
            self.update_component_power_mode(power_mode)

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

    def _station_health_changed(
        self: ControllerComponentManager,
        fqdn: str,
        health: HealthState | None,
    ) -> None:
        """
        Handle a change in the health of a station.

        :param fqdn: the FQDN of the station whose health has changed.
        :param health: the new health state of the station, or None if
            the station's health should not be taken into account.
        """
        if self._station_health_changed_callback is not None:
            self._station_health_changed_callback(fqdn, health)

    def _subarray_beam_health_changed(
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
            "subarray_beams", fqdn, health in [HealthState.OK, HealthState.DEGRADED]
        )  # False for None
        if self._subarray_beam_health_changed_callback is not None:
            self._subarray_beam_health_changed_callback(fqdn, health)

    def _station_beam_health_changed(
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
            "station_beams", fqdn, health in [HealthState.OK, HealthState.DEGRADED]
        )  # False for None
        if self._station_beam_health_changed_callback is not None:
            self._station_beam_health_changed_callback(fqdn, health)

    @check_communicating
    def off(
        self: ControllerComponentManager,
    ) -> ResultCode:
        """
        Turn off the MCCS subsystem.

        :return: a result code
        """
        results = [station_proxy.off() for station_proxy in self._stations.values()] + [
            subrack_proxy.off() for subrack_proxy in self._subracks.values()
        ]
        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        else:
            return ResultCode.QUEUED

    @check_communicating
    def standby(
        self: ControllerComponentManager,
    ) -> ResultCode:
        """
        Put the MCCS subsystem into low power standby mode.

        :return: a result code
        """
        results = [
            station_proxy.standby() for station_proxy in self._stations.values()
        ] + [subrack_proxy.standby() for subrack_proxy in self._subracks.values()]

        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        else:
            return ResultCode.QUEUED

    @check_communicating
    def on(
        self: ControllerComponentManager,
    ) -> ResultCode:
        """
        Turn on the MCCS subsystem.

        :return: a result code
        """
        results = [station_proxy.on() for station_proxy in self._stations.values()] + [
            subrack_proxy.on() for subrack_proxy in self._subracks.values()
        ]

        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        else:
            return ResultCode.QUEUED

    @check_communicating
    @check_on
    def allocate(
        self: ControllerComponentManager,
        subarray_id: int,
        station_fqdns: Iterable[Iterable[str]],
        subarray_beam_fqdns: Iterable[str],
        channel_blocks: Iterable[int],
    ) -> ResultCode:
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

        :raises ValueError: if trying to assign a station not in the controller's Stations

        :return: a result code
        """
        subarray_fqdn = f"low-mccs/subarray/{subarray_id:02d}"

        flattened_station_fqdns = []
        station_groups = []

        station_fqdns = list(station_fqdns)
        subarray_beam_fqdns = list(subarray_beam_fqdns)
        channel_blocks = list(channel_blocks)

        for group_index, station_group in enumerate(station_fqdns):
            station_groups.append(list(station_group))
            for station_fqdn in station_group:
                # stations are not managed by the resource manager, so we have to explicitely check if
                # they're valid FQDNs here
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

        self._resource_manager.allocate(
            subarray_fqdn,
            subarray_beams=subarray_beam_fqdns,
            station_beams=station_beam_fqdns,
            channel_blocks=channel_blocks,
        )

        result_code = self._subarrays[subarray_fqdn].assign_resources(
            list(set(flattened_station_fqdns)),  # unique items only
            subarray_beam_fqdns,
            station_beam_fqdns,
            channel_blocks,
        )

        # don't forget to release resources if allocate was unsuccessful:
        if result_code == ResultCode.FAILED:
            self.deallocate_all(subarray_id)
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

        return result_code

    @check_communicating
    @check_on
    def deallocate_all(
        self: ControllerComponentManager,
        subarray_id: int,
    ) -> ResultCode | None:
        """
        Deallocate all resources from a subarray.

        :param subarray_id: Id of the subarray from which all resources
            are to be deallocated

        :return: a result code, or None if there was nothing to do
        """
        subarray_fqdn = f"low-mccs/subarray/{subarray_id:02}"

        allocated = self._resource_manager.get_allocated(subarray_fqdn)
        if not allocated:
            return None

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

        return self._subarrays[subarray_fqdn].release_all_resources()

    @check_communicating
    @check_on
    def restart_subarray(
        self: ControllerComponentManager,
        subarray_fqdn: str,
    ) -> ResultCode:
        """
        Deallocate all resources from a subarray.

        :param subarray_fqdn: FQDN of the subarray from which all
            resources are to be deallocated

        :return: a result code
        """
        self._resource_manager.deallocate_from(subarray_fqdn)
        return self._subarrays[subarray_fqdn].restart()
