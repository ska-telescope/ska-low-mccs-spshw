# -*- coding: utf-8 -*-
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
from typing import Callable, Optional, Sequence

import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.component import (
    DeviceComponentManager,
    MccsComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs.utils import threadsafe

__all__ = ["StationComponentManager"]


class _TileProxy(DeviceComponentManager):
    """A proxy to a tile, for a station to use."""

    def __init__(
        self: _TileProxy,
        fqdn: str,
        station_id: int,
        logical_tile_id: int,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[PowerState], None],
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


class StationComponentManager(MccsComponentManager):
    """A component manager for a station."""

    def __init__(
        self: StationComponentManager,
        station_id: int,
        apiu_fqdn: str,
        antenna_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[CommunicationStatus], None],
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
        self._apiu_proxy = DeviceComponentManager(
            apiu_fqdn,
            logger,
            max_workers,
            functools.partial(self._device_communication_state_changed, apiu_fqdn),
            functools.partial(component_state_changed_callback, fqdn=apiu_fqdn),
        )
        #self._antenna_proxies = [
        self._antenna_proxies = {antenna_fqdn:
            DeviceComponentManager(
                antenna_fqdn,
                logger,
                max_workers,
                functools.partial(
                    self._device_communication_state_changed, antenna_fqdn
                ),
                functools.partial(
                    component_state_changed_callback, fqdn=antenna_fqdn
                ),
            )
            for antenna_fqdn in antenna_fqdns
        }
        #]
        #self._tile_proxies = [
        self._tile_proxies = {tile_fqdn:
            _TileProxy(
                tile_fqdn,
                station_id,
                logical_tile_id,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, tile_fqdn),
                functools.partial(
                    component_state_changed_callback, fqdn=tile_fqdn
                ),
            )
            for logical_tile_id, tile_fqdn in enumerate(tile_fqdns)
        }
        #]

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
            self._component_state_changed_callback({"is_configured": self.is_configured})

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
                f"\tiles: {self._tile_power_states}\n"
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
                    f"unknown fqdn '{fqdn}', should be None or belong to antenna, tile or apiu"
                )
        
    @property
    def power_state_lock(self: MccsComponentManager) -> Optional[PowerState]:
        """
        Return the power state lock of this component manager.

        :return: the power state lock of this component manager.
        """
        return self._power_state_lock   

    def off(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> ResultCode:
        """
        Submit the _off method.

        This method returns immediately after it submitted
        `self._off` for execution.

        :param task_callback: Update task state, defaults to None
        :type task_callback: Callable, optional
        :return: a result code and response message
        """
        task_status, response = self.submit_task(self._off, task_callback=task_callback)
        return task_status, response

    @check_communicating
    def _off(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> ResultCode:
        """
        Turn off this station.

        :param task_callback: Update task state, defaults to None
        :return: a result code
        """
        task_callback(status=TaskStatus.IN_PROGRESS)
        results = [proxy.off() for proxy in self._tile_proxies.values()] + [
            self._apiu_proxy.off()
        ]  # Never mind antennas, turning off APIU suffices

        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        elif ResultCode.QUEUED in results:
            return ResultCode.QUEUED
        else:
            return ResultCode.OK

        task_callback(status=TaskStatus.IN_PROGRESS)
        with self._power_state_lock:
            self._target_power_state = PowerState.ON
        self._review_power()
        task_callback(
            status=TaskStatus.COMPLETED, result="This slow task has completed"
        )
        return ResultCode.OK

    def on(
        self: StationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> ResultCode:
        """
        Submit the _on method.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None
        :type task_callback: Callable, optional
        :return: a result code and response message
        """
        task_status, response = self.submit_task(self._on, task_callback=task_callback)
        return task_status, response

    @check_communicating
    def _on(
        self: StationComponentManager,
    ) -> ResultCode:
        """
        Turn on this station.

        The order to turn a station on is: APIU, then tiles and antennas.

        :return: a result code
        """
        if self._apiu_power_state == PowerState.ON:
            return self._turn_on_tiles_and_antennas()
        self._on_called = True
        result_code = self._apiu_proxy.on()
        if result_code:
            return result_code
        return ResultCode.OK

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
    ) -> ResultCode:
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
    ) -> tuple[ResultCode, str]:
        """
        Apply the pointing configuration by setting the delays on each tile.

        :param delays: an array containing a beam index and antenna
            delays
        :param task_callback: :param task_callback:

        :return: a result code
        """
        results = [
            tile_proxy.set_pointing_delay(delays) for tile_proxy in self._tile_proxies.values()
        ]
        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        elif ResultCode.QUEUED in results:
            return ResultCode.QUEUED
        return ResultCode.OK

    @property  # type:ignore[misc]
    @check_communicating
    def is_configured(self: StationComponentManager) -> bool:
        """
        Return whether this station component manager is configured.

        :return: whether this station component manager is configured.
        """
        return self._is_configured

    def _update_is_configured(
        self: StationComponentManager,
        is_configured: bool,
    ) -> None:
        if self._is_configured != is_configured:
            self._is_configured = is_configured
            self._component_state_changed_callback({"is_configured": is_configured})

    def configure(
        self: StationComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[ResultCode, str]:
        """
        Submit the configure method.

        This method returns immediately after it submitted
        `self._configure` for execution.

        :param argin: Configuration specification dict as a json string.
        :param task_callback: Update task state, defaults to None

        :return: a result code and response string
        """
        configuration = json.loads(argin)
        station_id = configuration.get("station_id")
        return self.submit_task(
            self._configure, args=[station_id], task_callback=task_callback
        )

    # @check_communicating
    def _configure(
        self: StationComponentManager,
        station_id: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
    ) -> None:
        """
        Configure the station.

        This is a placeholder for a real implementation. At present all
        it accepts is the station id, which it checks.

        :param station_id: the id of the station for which the provided
            configuration is intended.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: abort event
        """
        task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            if station_id != self._station_id:
                raise ValueError("Wrong station id")
            self._update_is_configured(True)
        except ValueError as value_error:
            task_callback(
                status=TaskStatus.FAILED,
                result=f"Configure command has failed: {value_error}",
            )
            return

        task_callback(
            status=TaskStatus.COMPLETED, result="Configure command has completed"
        )
