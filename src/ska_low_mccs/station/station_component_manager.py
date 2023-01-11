#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for stations."""
from __future__ import annotations

import functools
import json
import logging
import threading
from typing import Any, Callable, Optional, Sequence

import tango
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common.component import (
    DeviceComponentManager,
    MccsComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs_common.utils import threadsafe

__all__ = ["StationComponentManager"]


class _ApiuProxy(DeviceComponentManager):
    """A proxy to a APIU device, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _ApiuProxy,
        fqdn: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    @check_communicating
    def configure(self: _ApiuProxy, config: str) -> None:
        """
        Configure the device proxy.

        :param config: json string of configuration.
        """
        assert self._proxy is not None  # for the type checker
        self._proxy.connect()
        assert self._proxy._device is not None  # for the type checker
        self._proxy._device.Configure(config)


class _AntennaProxy(DeviceComponentManager):
    """A proxy to a antenna device, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _AntennaProxy,
        fqdn: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    @check_communicating
    def configure(self: _AntennaProxy, config: str) -> None:
        """
        Configure the device proxy.

        :param config: json string of configuration.
        """
        assert self._proxy is not None  # for the type checker
        self._proxy.connect()
        assert self._proxy._device is not None  # for the type checker
        self._proxy._device.Configure(config)


class _TileProxy(DeviceComponentManager):
    """A proxy to a tile, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _TileProxy,
        fqdn: str,
        station_id: int,
        logical_tile_id: int,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param station_id: the id of the station to which this station
            is to be assigned
        :param logical_tile_id: the id of the tile within this station.
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._station_id = station_id
        self._logical_tile_id = logical_tile_id
        self._connecting = False

        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: _TileProxy) -> None:
        self._connecting = True
        super().start_communicating()

    def _device_state_changed(
        self: _TileProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if self._connecting and event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            self._proxy.stationId = self._station_id
            self._proxy.logicalTileId = self._logical_tile_id
            self._connecting = False
        super()._device_state_changed(event_name, event_value, event_quality)

    @check_communicating
    @check_on
    def set_pointing_delay(self: _TileProxy, delays: list[float]) -> ResultCode:
        """
        Set the tile's pointing delays.

        :param delays: an array containing a beam index and antenna
            delays

        :return: a result code
        """
        assert self._proxy is not None  # for the type checker
        ([result_code], _) = self._proxy.SetPointingDelay(delays)
        return result_code

    @check_communicating
    def configure(self: _TileProxy, config: str) -> None:
        """
        Configure the device proxy.

        :param config: json string of configuration.
        """
        assert self._proxy is not None  # for the type checker
        self._proxy.connect()
        assert self._proxy._device is not None  # for the type checker
        self._proxy._device.Configure(config)


# pylint: disable=too-many-instance-attributes
class StationComponentManager(MccsComponentManager):
    """A component manager for a station."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: StationComponentManager,
        station_id: int,
        apiu_fqdn: str,
        antenna_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param station_id: the id of this station
        :param apiu_fqdn: FQDN of the Tango device that manages this
            station's APIU
        :param antenna_fqdns: FQDNs of the Tango devices and manage this
            station's antennas
        :param tile_fqdns: FQDNs of the Tango devices and manage this
            station's TPMs
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._station_id = station_id
        self._apiu_fqdn = apiu_fqdn

        self._is_configured = False
        self._on_called = False

        self._communication_state_lock = threading.Lock()
        self._communication_statees = {
            fqdn: CommunicationStatus.DISABLED
            for fqdn in [apiu_fqdn] + list(antenna_fqdns) + list(tile_fqdns)
        }

        self._apiu_power_state = PowerState.UNKNOWN
        self._antenna_power_states = {
            fqdn: PowerState.UNKNOWN for fqdn in antenna_fqdns
        }
        self._tile_power_states = {fqdn: PowerState.UNKNOWN for fqdn in tile_fqdns}
        self._apiu_proxy = _ApiuProxy(
            apiu_fqdn,
            logger,
            max_workers,
            functools.partial(self._device_communication_state_changed, apiu_fqdn),
            functools.partial(component_state_changed_callback, fqdn=apiu_fqdn),
        )
        self._antenna_proxies = {
            antenna_fqdn: _AntennaProxy(
                antenna_fqdn,
                logger,
                max_workers,
                functools.partial(
                    self._device_communication_state_changed, antenna_fqdn
                ),
                functools.partial(component_state_changed_callback, fqdn=antenna_fqdn),
            )
            for antenna_fqdn in antenna_fqdns
        }
        self._tile_proxies = {
            tile_fqdn: _TileProxy(
                tile_fqdn,
                station_id,
                logical_tile_id,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, tile_fqdn),
                functools.partial(component_state_changed_callback, fqdn=tile_fqdn),
            )
            for logical_tile_id, tile_fqdn in enumerate(tile_fqdns)
        }

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: StationComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

        self._apiu_proxy.start_communicating()
        for tile_proxy in self._tile_proxies.values():
            tile_proxy.start_communicating()
        for antenna_proxy in self._antenna_proxies.values():
            antenna_proxy.start_communicating()

    def stop_communicating(self: StationComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for antenna_proxy in self._antenna_proxies.values():
            antenna_proxy.stop_communicating()
        for tile_proxy in self._tile_proxies.values():
            tile_proxy.stop_communicating()
        self._apiu_proxy.stop_communicating()

    def _device_communication_state_changed(
        self: StationComponentManager,
        fqdn: str,
        communication_state: CommunicationStatus,
    ) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self._communication_state_lock:
            self._communication_statees[fqdn] = communication_state

            if self.communication_state == CommunicationStatus.DISABLED:
                return

            if CommunicationStatus.DISABLED in self._communication_statees.values():
                self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._communication_statees.values()
            ):
                self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self.update_communication_state(CommunicationStatus.ESTABLISHED)

    def update_communication_state(
        self: StationComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Update the status of communication with the component.

        Overridden here to fire the "is configured" callback whenever
        communication is freshly established

        :param communication_state: the status of communication with
            the component
        """
        super().update_communication_state(communication_state)

        if communication_state == CommunicationStatus.ESTABLISHED:
            if self._component_state_changed_callback is not None:
                self._component_state_changed_callback(
                    {"is_configured": self.is_configured}
                )

    @threadsafe
    def _antenna_power_state_changed(
        self: StationComponentManager,
        fqdn: str,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._antenna_power_states[fqdn] = power_state
            self._evaluate_power_state()

    @threadsafe
    def _tile_power_state_changed(
        self: StationComponentManager,
        fqdn: str,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._tile_power_states[fqdn] = power_state
            self._evaluate_power_state()

    @threadsafe
    def _apiu_power_state_changed(
        self: StationComponentManager,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._apiu_power_state = power_state
            self._evaluate_power_state()
        if power_state is PowerState.ON and self._on_called:
            self._on_called = False
            _ = self._turn_on_tiles_and_antennas()

    def _evaluate_power_state(
        self: StationComponentManager,
    ) -> None:
        with self._power_state_lock:
            power_states = (
                [self._apiu_power_state]
                + list(self._antenna_power_states.values())
                + list(self._tile_power_states.values())
            )
            if all(power_state == PowerState.ON for power_state in power_states):
                evaluated_power_state = PowerState.ON
            elif all(power_state == PowerState.OFF for power_state in power_states):
                evaluated_power_state = PowerState.OFF
            else:
                evaluated_power_state = PowerState.UNKNOWN

            self.logger.info(
                "In StationComponentManager._evaluatePowerState with:\n"
                f"\tapiu: {self._apiu_power_state}\n"
                f"\tantennas: {self._antenna_power_states}\n"
                f"\ttiles: {self._tile_power_states}\n"
                f"\tresult: {str(evaluated_power_state)}"
            )
            self.update_component_state({"power_state": evaluated_power_state})

    def set_power_state(
        self: StationComponentManager,
        power_state: PowerState,
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Set the power_state of the component.

        :param power_state: the value of PowerState to be set.
        :param fqdn: the fqdn of the component's device.

        :raises ValueError: fqdn not found
        """
        # Note: this setter was, prior to V0.13 of the base classes, in
        # MccsComponentManager.update_component_power_mode
        with self._power_state_lock:
            if fqdn is None:
                self.power_state = power_state
            elif fqdn in self._antenna_proxies.keys():
                self._antenna_proxies[fqdn].power_state = power_state
            elif fqdn in self._tile_proxies.keys():
                self._tile_proxies[fqdn].power_state = power_state
            elif fqdn == self._apiu_fqdn:
                self._apiu_proxy.power_state = power_state
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to antenna, "
                    "tile or apiu"
                )

    @property
    def power_state_lock(self: MccsComponentManager) -> threading.RLock:
        """
        Return the power state lock of this component manager.

        :return: the power state lock of this component manager.
        """
        return self._power_state_lock

    def off(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _off method.

        This method returns immediately after it submitted
        `self._off` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a result code and response message
        """
        return self.submit_task(self._off, task_callback=task_callback)

    @check_communicating
    def _off(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn off this station.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        results = [proxy.off() for proxy in self._tile_proxies.values()] + [
            self._apiu_proxy.off()
        ]  # Never mind antennas, turning off APIU suffices
        # TODO: Here we need to monitor the APIU and Tiles. This will eventually
        # use the mechanism described in MCCS-945, but until that is implemented
        # we might instead just poll these devices' longRunngCommandAttribute.
        # For the moment, however, we just submit the subservient devices' commands
        # for execution and forget about them.
        if all(
            result in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]
            for (result, _) in results
        ):
            task_status = TaskStatus.COMPLETED
        else:
            task_status = TaskStatus.FAILED
        if task_callback:
            task_callback(status=task_status)

    def on(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _on method.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a task staus and response message
        """
        return self.submit_task(self._on, task_callback=task_callback)

    @check_communicating
    def _on(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on this station.

        The order to turn a station on is: APIU, then tiles and
        antennas.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        if self._apiu_power_state == PowerState.ON:
            result_code = self._turn_on_tiles_and_antennas()
            # TODO: Monitor the Tiles' & antennas' On command statuses and update
            # the Station On command status accordingly.
            if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
                task_status = TaskStatus.COMPLETED
            else:
                task_status = TaskStatus.FAILED
            if task_callback:
                task_callback(status=task_status)
            return
        self._on_called = True
        # result_code, _ = self._apiu_proxy.on()
        task_status, _ = self._apiu_proxy.on()
        # TODO: Monitor the APIU On command status and update the Station
        # On command status accordingly.
        # check return codes!!!!!!!!!!!
        if task_status == TaskStatus.QUEUED:
            # if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            task_status = TaskStatus.COMPLETED
        else:
            task_status = TaskStatus.FAILED
        if task_callback:
            task_callback(status=task_status)

    @check_communicating
    def _turn_on_tiles_and_antennas(
        self: StationComponentManager,
    ) -> ResultCode:
        """
        Turn on tiles and antennas if not already on.

        :return: a result code
        """
        with self._power_state_lock:
            if not all(
                power_state == PowerState.ON
                for power_state in self._tile_power_states.values()
            ):
                results = []
                for proxy in self._tile_proxies.values():
                    result_code = proxy.on()
                    results.append(result_code)
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
            if not all(
                power_state == PowerState.ON
                for power_state in self._antenna_power_states.values()
            ):
                results = [proxy.on() for proxy in self._antenna_proxies.values()]
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
            return ResultCode.QUEUED

    def apply_pointing(
        self: StationComponentManager,
        delays: list[float],
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the apply_pointing method.

        This method returns immediately after it submitted
        `self._apply_pointing` for execution.

        :param delays: an array containing a beam index and antenna
            delays
        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._apply_pointing, [delays], task_callback=task_callback
        )

    @check_communicating
    @check_on
    def _apply_pointing(
        self: StationComponentManager,
        delays: list[float],
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Apply the pointing configuration by setting the delays on each tile.

        :param delays: an array containing a beam index and antenna
            delays
        :param task_callback: :param task_callback:
        :param task_abort_event: Abort the task
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        results = [
            tile_proxy.set_pointing_delay(delays)
            for tile_proxy in self._tile_proxies.values()
        ]
        # TODO: Monitor the Tiles' SetPointingDelay command status and update
        # the Station command status accordingly.
        if all(
            result in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]
            for result in results
        ):
            task_status = TaskStatus.COMPLETED
        else:
            task_status = TaskStatus.FAILED
        if task_callback:
            task_callback(status=task_status)

    @property  # type:ignore[misc]
    @check_communicating
    def is_configured(self: StationComponentManager) -> bool:
        """
        Return whether this station component manager is configured.

        :return: whether this station component manager is configured.
        """
        return self._is_configured

    def _update_station_configs(
        self: StationComponentManager,
        configuration: dict,
    ) -> None:
        """
        Update the config for the station device.

        :param configuration: dict containing the config of the device
        """
        if self._component_state_changed_callback is not None:
            self._is_configured = True
            self._component_state_changed_callback(
                {"configuration_changed": configuration}
            )

    def _update_children_configs(
        self: StationComponentManager,
        configuration: dict,
    ) -> None:
        """
        Update the config for the station device.

        :param configuration: dict containing the config of the device
        """
        self.start_communicating()
        for fqdn in self._antenna_proxies.keys():
            self._antenna_proxies[fqdn].on()
        apiu_config = configuration.get("apiu")
        if apiu_config is not None:
            self._apiu_proxy.configure(json.dumps(apiu_config))

        antenna_config = configuration.get("antennas")
        if antenna_config:
            for fqdn in self._antenna_proxies.keys():
                config = antenna_config[fqdn]
                self._antenna_proxies[fqdn].configure(json.dumps(config))
        tiles_config = configuration.get("tiles")
        if tiles_config:
            for fqdn in self._tile_proxies.keys():
                config = tiles_config[fqdn]
                self._tile_proxies[fqdn].configure(json.dumps(config))
        self.stop_communicating()

    def configure(
        self: StationComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the configure method.

        This method returns immediately after it submitted
        `self._configure` for execution.

        :param argin: Configuration specification dict as a json string.
        :param task_callback: Update task state, defaults to None

        :return: a result code and response string
        """
        configuration = json.loads(argin)
        return self.submit_task(
            self._configure, args=[configuration], task_callback=task_callback
        )

    # @check_communicating
    def _configure(
        self: StationComponentManager,
        configuration: dict,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Configure the stations children.

        This sends off configuration commands to all of the devices that
        this station manages.

        :param configuration: Configuration specification dict.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            station_config = configuration.get("station")
            if (
                station_config is None
                or station_config.get("StationId") != self._station_id
            ):
                raise ValueError("Wrong station id")
            self._update_station_configs(station_config)
            self._update_children_configs(configuration)
        except ValueError as value_error:
            if task_callback:
                task_callback(
                    status=TaskStatus.FAILED,
                    result=f"Configure command has failed: {value_error}",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Configure command has completed"
            )
