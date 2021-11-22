# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for subarrays."""
from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable, Optional, Sequence

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, ObsState, PowerMode
import ska_tango_base.subarray

from ska_low_mccs.component import (
    CommunicationStatus,
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
    def configure(self: _StationProxy, configuration: dict) -> ResultCode:
        """
        Configure the station.

        :param configuration: the configuration to be applied to this
            station

        :return: a result code.
        """
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        ([result_code], _) = self._proxy.Configure(configuration_str)
        return result_code


class _SubarrayBeamProxy(ObsDeviceComponentManager):
    """A subarray's proxy to its subarray beams."""

    @check_communicating
    @check_on
    def configure(self: _SubarrayBeamProxy, configuration: dict) -> ResultCode:
        """
        Configure the subarray beam.

        :param configuration: the configuration to be applied to this
            subarray beam

        :return: a result code.
        """
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        ([result_code], _) = self._proxy.Configure(configuration_str)
        return result_code

    @check_communicating
    @check_on
    def scan(self: _SubarrayBeamProxy, scan_id: int, start_time: float) -> ResultCode:
        """
        Start the subarray beam scanning.

        :param scan_id: the id of the scan
        :param start_time: the start time of the scan

        :return: a result code.
        """
        assert self._proxy is not None
        scan_arg = json.dumps({"scan_id": scan_id, "start_time": start_time})
        ([result_code], _) = self._proxy.Scan(scan_arg)
        return result_code


class _StationBeamProxy(ObsDeviceComponentManager):
    """A subarray's proxy to its station beams."""

    @check_communicating
    @check_on
    def configure(self: _StationBeamProxy, configuration: dict) -> ResultCode:
        """
        Configure the station beam.

        :param configuration: the configuration to be applied to this
            station beam

        :return: a result code.
        """
        assert self._proxy is not None
        configuration_str = json.dumps(configuration)
        ([result_code], _) = self._proxy.Configure(configuration_str)
        return result_code


class SubarrayComponentManager(
    MccsComponentManager,
    ska_tango_base.subarray.SubarrayComponentManager,
):
    """A component manager for a subarray."""

    def __init__(
        self: SubarrayComponentManager,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        assign_completed_callback: Callable[[], None],
        release_completed_callback: Callable[[], None],
        configure_completed_callback: Callable[[], None],
        abort_completed_callback: Callable[[], None],
        obsreset_completed_callback: Callable[[], None],
        restart_completed_callback: Callable[[], None],
        resources_changed_callback: Callable[[set[str], set[str], set[str]], None],
        configured_changed_callback: Callable[[bool], None],
        scanning_changed_callback: Callable[[bool], None],
        obs_fault_callback: Callable[[], None],
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
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param assign_completed_callback: callback to be called when the
            component completes a resource assignment.
        :param release_completed_callback: callback to be called when
            the component completes a resource release.
        :param configure_completed_callback: callback to be called when
            the component completes a configuration.
        :param abort_completed_callback: callback to be called when the
            component completes an abort.
        :param obsreset_completed_callback: callback to be called when
            the component completes an observation reset.
        :param restart_completed_callback: callback to be called when
            the component completes a restart.
        :param resources_changed_callback: callback to be called when
            this subarray's resources changes
        :param configured_changed_callback: callback to be called when
            whether the subarray is configured changes
        :param scanning_changed_callback: callback to be called when
            whether the subarray is scanning changes
        :param obs_fault_callback: callback to be called when whether
            the subarray is experiencing an observation fault changes.
        :param station_health_changed_callback: callback to be called
            when the health of this station's APIU changes
        :param subarray_beam_health_changed_callback: callback to be
            called when the health of one of this station's antennas
            changes
        :param station_beam_health_changed_callback: callback to be
            called when the health of one of this subarray's station beams
            changes
        """
        self._assign_completed_callback = assign_completed_callback
        self._release_completed_callback = release_completed_callback
        self._configure_completed_callback = configure_completed_callback
        self._abort_completed_callback = abort_completed_callback
        self._obsreset_completed_callback = obsreset_completed_callback
        self._restart_completed_callback = restart_completed_callback
        self._resources_changed_callback = resources_changed_callback
        self._configured_changed_callback = configured_changed_callback
        self._scanning_changed_callback = scanning_changed_callback
        self._obs_fault_callback = obs_fault_callback
        self._station_health_changed_callback = station_health_changed_callback
        self._subarray_beam_health_changed_callback = (
            subarray_beam_health_changed_callback
        )
        self._station_beam_health_changed_callback = (
            station_beam_health_changed_callback
        )

        self._device_communication_statuses: dict[str, CommunicationStatus] = {}
        self._station_power_modes: dict[str, Optional[PowerMode]] = {}
        self._device_obs_states: dict[str, Optional[ObsState]] = {}
        self._is_assigning = False
        self._configuring_resources: set[str] = set()
        self._stations: dict[str, _StationProxy] = dict()
        self._subarray_beams: dict[str, _SubarrayBeamProxy] = dict()
        self._station_beams: dict[str, _StationBeamProxy] = dict()

        self._scan_id: Optional[int] = None

        super().__init__(
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            None,
            None,
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
            with self._power_mode_lock:
                self.update_component_power_mode(PowerMode.ON)

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
    def assign(  # type: ignore[override]
        self: SubarrayComponentManager,
        argin: str,
    ) -> ResultCode:
        """
        Assign resources to this subarray.

        This is just for communication and health roll-up, resource management is done by controller.

        :param argin: a JSON encoded resource specification; for example

            .. code-block:: python

                {
                    "subarray_beams": ["low-mccs/subarraybeam/01"],
                    "stations": ["low-mccs/station/001", "low-mccs/station/002"],
                    "station_beams": ["low-mccs/beam/01","low-mccs/beam/02"]
                    "channel_blocks": [3]
                }

        :return: a result code
        """
        resource_spec = json.loads(argin)

        station_fqdns: Sequence[str] = resource_spec.get("stations", [])
        subarray_beam_fqdns: Sequence[str] = resource_spec.get("subarray_beams", [])
        station_beam_fqdns: Sequence[str] = resource_spec.get("station_beams", [])

        station_fqdns_to_add = station_fqdns - self._stations.keys()
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
                    self._push_change_event,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    functools.partial(self._station_power_mode_changed, fqdn),
                    None,
                    functools.partial(self._station_health_changed_callback, fqdn),
                    functools.partial(self._device_obs_state_changed, fqdn),
                )
            for fqdn in subarray_beam_fqdns_to_add:
                self._subarray_beams[fqdn] = _SubarrayBeamProxy(
                    fqdn,
                    self.logger,
                    self._push_change_event,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    None,
                    None,
                    functools.partial(
                        self._subarray_beam_health_changed_callback, fqdn
                    ),
                    functools.partial(self._device_obs_state_changed, fqdn),
                )
            for fqdn in station_beam_fqdns_to_add:
                self._station_beams[fqdn] = _StationBeamProxy(
                    fqdn,
                    self.logger,
                    self._push_change_event,
                    functools.partial(self._device_communication_status_changed, fqdn),
                    None,
                    None,
                    functools.partial(self._station_beam_health_changed_callback, fqdn),
                    functools.partial(self._device_obs_state_changed, fqdn),
                )
            self._resources_changed_callback(
                set(self._stations.keys()),
                set(self._subarray_beams.keys()),
                set(self._station_beams.keys()),
            )

            self._is_assigning = True
            for fqdn in station_fqdns_to_add:
                self._stations[fqdn].start_communicating()
            for fqdn in subarray_beam_fqdns_to_add:
                self._subarray_beams[fqdn].start_communicating()
            for fqdn in station_beam_fqdns_to_add:
                self._station_beams[fqdn].start_communicating()

        return ResultCode.OK

    @property  # type: ignore[misc]
    @check_communicating
    def assigned_resources(
        self: SubarrayComponentManager,
    ) -> set[str]:
        """
        Return this subarray's resources.

        :return: this subarray's resources.
        """
        return (
            set(self._stations) | set(self._subarray_beams) | set(self._station_beams)
        )

    @check_communicating
    def release(  # type: ignore[override]
        self: SubarrayComponentManager,
        resource_spec: dict[str, Sequence[Any]],
    ) -> ResultCode:
        """
        Assign resources to this subarray.

        :param resource_spec: a resource specification; for example

            .. code-block:: python

                {
                    "subarray_beams": ["low-mccs/subarraybeam/01"],
                    "stations": ["low-mccs/station/001", "low-mccs/station/002"],
                    "station_beams": ["low-mccs/beam/01","low-mccs/beam/02"],
                    "channel_blocks": [3]
                }

        :return: a result code
        """
        station_fqdns: Sequence[str] = resource_spec.get("stations", [])
        subarray_beam_fqdns: Sequence[str] = resource_spec.get("subarray_beams", [])
        station_beam_fqdns: Sequence[str] = resource_spec.get("station_beams", [])

        station_fqdns_to_remove = self._stations.keys() & station_fqdns
        subarray_beam_fqdns_to_remove = (
            self._subarray_beams.keys() & subarray_beam_fqdns
        )
        station_beam_fqdns_to_remove = self._station_beams.keys() & station_beam_fqdns

        if len(station_fqdns_to_remove) != len(subarray_beam_fqdns_to_remove):
            self.logger.error(
                f"Mismatch: releasing {len(station_fqdns_to_remove)} stations, "
                f"{len(subarray_beam_fqdns_to_remove)} subarray beams."
            )
            self._release_completed_callback()
            return ResultCode.FAILED

        if (
            station_fqdns_to_remove
            or subarray_beam_fqdns_to_remove
            or station_beam_fqdns_to_remove
        ):
            for fqdn in station_fqdns_to_remove:
                del self._stations[fqdn]
                del self._device_communication_statuses[fqdn]
                del self._device_obs_states[fqdn]
            for fqdn in subarray_beam_fqdns_to_remove:
                del self._subarray_beams[fqdn]
                del self._device_communication_statuses[fqdn]
                del self._device_obs_states[fqdn]
            for fqdn in station_beam_fqdns_to_remove:
                del self._station_beams[fqdn]
                del self._device_communication_statuses[fqdn]
                del self._device_obs_states[fqdn]

            self._resources_changed_callback(
                set(self._stations.keys()),
                set(self._subarray_beams.keys()),
                set(self._station_beams.keys()),
            )
            self._evaluate_communication_status()

        self._release_completed_callback()
        return ResultCode.OK

    @check_communicating
    def release_all(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Release all resources from this subarray.

        :return: a result code
        """
        if self._stations or self._subarray_beams or self._station_beams:
            self._stations.clear()
            self._subarray_beams.clear()
            self._station_beams.clear()
            self._device_communication_statuses.clear()
            self._device_obs_states.clear()

            self._resources_changed_callback(
                set(self._stations.keys()),
                set(self._subarray_beams.keys()),
                set(self._station_beams.keys()),
            )
            self._evaluate_communication_status()
        self._release_completed_callback()
        return ResultCode.OK

    @check_communicating
    def configure(  # type: ignore[override]
        self: SubarrayComponentManager,
        configuration: dict[str, Any],
    ) -> ResultCode:
        """
        Configure the resources for a scan.

        :param configuration: the configurations to be applied

        :return: a result code
        """
        stations = configuration["stations"]
        station_configuration = {station["station_id"]: station for station in stations}
        subarray_beams = configuration["subarray_beams"]
        subarray_beam_configuration = {
            subarray_beam["subarray_beam_id"]: subarray_beam
            for subarray_beam in subarray_beams
        }

        result_code = self._configure_stations(station_configuration)
        if result_code != ResultCode.FAILED:
            result_code = self._configure_subarray_beams(subarray_beam_configuration)
        self._configured_changed_callback(True)

        if result_code == ResultCode.OK:
            self._configure_completed_callback()

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
        result_code = ResultCode.OK
        for (station_id, configuration) in station_configuration.items():
            station_fqdn = f"low-mccs/station/{station_id:03d}"
            station_proxy = self._stations[station_fqdn]
            proxy_result_code = station_proxy.configure(configuration)
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
        for (subarray_beam_id, configuration) in subarray_beam_configuration.items():
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
    ) -> ResultCode:
        """
        Start scanning.

        :param scan_id: the id of the scan
        :param start_time: the start time of the scan

        :return: a result code
        """
        self._scan_id = scan_id

        result_code = ResultCode.OK
        for subarray_beam_proxy in self._subarray_beams.values():
            proxy_result_code = subarray_beam_proxy.scan(scan_id, start_time)
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
        self._scanning_changed_callback(True)
        return result_code

    @check_communicating
    def end_scan(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        End scanning.

        :return: a result code
        """
        self._scan_id = None

        # Stuff goes here. This should tell the subarray beam device to
        # stop scanning, but that device doesn't support it yet.
        self._scanning_changed_callback(False)
        return ResultCode.OK

    @check_communicating
    def deconfigure(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Deconfigure resources.

        :return: a result code
        """
        result_code = ResultCode.OK
        for station_proxy in self._stations.values():
            proxy_result_code = station_proxy.configure({})
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
        for subarray_beam_proxy in self._subarray_beams.values():
            proxy_result_code = subarray_beam_proxy.configure({})
            if proxy_result_code == ResultCode.FAILED:
                result_code = ResultCode.FAILED
        self._configured_changed_callback(False)
        return result_code

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
        self._abort_completed_callback()
        return ResultCode.OK

    @check_communicating
    def obsreset(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Reset the observation by returning to unconfigured state.

        :return: a result code
        """
        # other stuff here
        self.deconfigure()
        self._obsreset_completed_callback()
        return ResultCode.OK

    @check_communicating
    def restart(  # type: ignore[override]
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Restart the subarray by returning to unresourced state.

        :return: a result code
        """
        # other stuff here
        self.deconfigure()
        result_code = self.release_all()
        self._restart_completed_callback()
        return result_code

    @check_communicating
    def send_transient_buffer(
        self: SubarrayComponentManager,
    ) -> ResultCode:
        """
        Send the transient buffer.

        :return: a result code
        """
        # stuff here
        return ResultCode.OK

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

    def _station_power_mode_changed(
        self: SubarrayComponentManager,
        fqdn: str,
        power_mode: PowerMode,
    ) -> None:
        self._station_power_modes[fqdn] = power_mode

        if self._is_assigning and all(
            power_mode is not None for power_mode in self._station_power_modes.values()
        ):
            self._is_assigning = False
            self._assign_completed_callback()

    def _device_obs_state_changed(
        self: SubarrayComponentManager,
        fqdn: str,
        obs_state: ObsState,
    ) -> None:
        self._device_obs_states[fqdn] = obs_state
        if obs_state == ObsState.READY and fqdn in self._configuring_resources:
            self._configuring_resources.remove(fqdn)
            if not self._configuring_resources:
                self._configure_completed_callback()
