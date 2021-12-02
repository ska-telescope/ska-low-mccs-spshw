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
import logging
import threading
from typing import Callable, Optional, Sequence
import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    DeviceComponentManager,
    MccsComponentManager,
    MessageQueue,
    check_communicating,
    check_on,
    enqueue,
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
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Optional[Callable[[bool], None]],
        health_changed_callback: Optional[
            Callable[[Optional[HealthState]], None]
        ] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param station_id: the id of the station to which this station
            is to be assigned
        :param logical_tile_id: the id of the tile within this station.
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
        self._station_id = station_id
        self._logical_tile_id = logical_tile_id
        self._connecting = False

        super().__init__(
            fqdn,
            message_queue,
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            health_changed_callback,
        )

    def _connect_to_device(self: _TileProxy) -> None:
        """
        Establish communication with the component, then start monitoring.

        Overridden here to write initial tile configuration values
        relative to this station.
        """
        super()._connect_to_device()
        self._connecting = True

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
    @enqueue
    def set_pointing_delay(self: _TileProxy, delays: list[float]) -> ResultCode:
        """
        Set the tile's pointing delays.

        :param delays: an array containing a beam index and antenna
            delays

        :return: a result code
        """
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.SetPointingDelay(delays)
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
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        message_queue_size_callback: Callable[[int], None],
        apiu_health_changed_callback: Callable[[Optional[HealthState]], None],
        antenna_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        tile_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        is_configured_changed_callback: Callable[[bool], None],
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
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param message_queue_size_callback: callback to be called when
            the size of the message queue changes
        :param apiu_health_changed_callback: callback to be called when
            the health of this station's APIU changes
        :param antenna_health_changed_callback: callback to be called when
            the health of one of this station's antennas changes
        :param tile_health_changed_callback: callback to be called when
            the health of one of this station's tiles changes
        :param is_configured_changed_callback: callback to be called
            when whether this component manager is configured changes
        """
        self._station_id = station_id

        self._is_configured = False
        self._on_called = False
        self._is_configured_changed_callback = is_configured_changed_callback

        self._communication_status_lock = threading.Lock()
        self._communication_statuses = {
            fqdn: CommunicationStatus.DISABLED
            for fqdn in [apiu_fqdn] + list(antenna_fqdns) + list(tile_fqdns)
        }

        self._power_mode_lock = threading.Lock()
        self._apiu_power_mode = PowerMode.UNKNOWN
        self._antenna_power_modes = {fqdn: PowerMode.UNKNOWN for fqdn in antenna_fqdns}
        self._tile_power_modes = {fqdn: PowerMode.UNKNOWN for fqdn in tile_fqdns}

        self._message_queue = MessageQueue(
            logger,
            queue_size_callback=message_queue_size_callback,
        )

        self._apiu_proxy = DeviceComponentManager(
            apiu_fqdn,
            self._message_queue,
            logger,
            functools.partial(self._device_communication_status_changed, apiu_fqdn),
            self._apiu_power_mode_changed,
            None,
            apiu_health_changed_callback,
        )
        self._antenna_proxies = [
            DeviceComponentManager(
                antenna_fqdn,
                self._message_queue,
                logger,
                functools.partial(
                    self._device_communication_status_changed, antenna_fqdn
                ),
                functools.partial(self._antenna_power_mode_changed, antenna_fqdn),
                None,
                functools.partial(antenna_health_changed_callback, antenna_fqdn),
            )
            for antenna_fqdn in antenna_fqdns
        ]
        self._tile_proxies = [
            _TileProxy(
                tile_fqdn,
                station_id,
                logical_tile_id,
                self._message_queue,
                logger,
                functools.partial(self._device_communication_status_changed, tile_fqdn),
                functools.partial(self._tile_power_mode_changed, tile_fqdn),
                None,
                functools.partial(tile_health_changed_callback, tile_fqdn),
            )
            for logical_tile_id, tile_fqdn in enumerate(tile_fqdns)
        ]

        super().__init__(
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            None,
        )

    def start_communicating(self: StationComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

        self._apiu_proxy.start_communicating()
        for tile_proxy in self._tile_proxies:
            tile_proxy.start_communicating()
        for antenna_proxy in self._antenna_proxies:
            antenna_proxy.start_communicating()

    def stop_communicating(self: StationComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for antenna_proxy in self._antenna_proxies:
            antenna_proxy.stop_communicating()
        for tile_proxy in self._tile_proxies:
            tile_proxy.stop_communicating()
        self._apiu_proxy.stop_communicating()

    def _device_communication_status_changed(
        self: StationComponentManager,
        fqdn: str,
        communication_status: CommunicationStatus,
    ) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self._communication_status_lock:
            self._communication_statuses[fqdn] = communication_status

            if self.communication_status == CommunicationStatus.DISABLED:
                return

            if CommunicationStatus.DISABLED in self._communication_statuses.values():
                self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._communication_statuses.values()
            ):
                self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self.update_communication_status(CommunicationStatus.ESTABLISHED)

    def update_communication_status(
        self: StationComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Update the status of communication with the component.

        Overridden here to fire the "is configured" callback whenever
        communication is freshly established

        :param communication_status: the status of communication with
            the component
        """
        super().update_communication_status(communication_status)

        if communication_status == CommunicationStatus.ESTABLISHED:
            self._is_configured_changed_callback(self._is_configured)

    @threadsafe
    def _antenna_power_mode_changed(
        self: StationComponentManager,
        fqdn: str,
        power_mode: PowerMode,
    ) -> None:
        with self._power_mode_lock:
            self._antenna_power_modes[fqdn] = power_mode
            self._evaluate_power_mode()

    @threadsafe
    def _tile_power_mode_changed(
        self: StationComponentManager,
        fqdn: str,
        power_mode: PowerMode,
    ) -> None:
        with self._power_mode_lock:
            self._tile_power_modes[fqdn] = power_mode
            self._evaluate_power_mode()

    @threadsafe
    def _apiu_power_mode_changed(
        self: StationComponentManager,
        power_mode: PowerMode,
    ) -> None:
        with self._power_mode_lock:
            self._apiu_power_mode = power_mode
            self._evaluate_power_mode()
            if power_mode is PowerMode.ON and self._on_called:
                self._on_called = False
                _ = self._turn_on_tiles_and_antennas()

    def _evaluate_power_mode(
        self: StationComponentManager,
    ) -> None:
        power_modes = (
            [self._apiu_power_mode]
            + list(self._antenna_power_modes.values())
            + list(self._tile_power_modes.values())
        )
        if all(power_mode == PowerMode.ON for power_mode in power_modes):
            evaluated_power_mode = PowerMode.ON
        elif all(power_mode == PowerMode.OFF for power_mode in power_modes):
            evaluated_power_mode = PowerMode.OFF
        else:
            evaluated_power_mode = PowerMode.UNKNOWN

        self.logger.info(
            "In StationComponentManager._evaluatePowerMode with:\n"
            f"\tapiu: {self._apiu_power_mode}"
            f"\antennas: {self._antenna_power_modes}\n"
            f"\tiles: {self._tile_power_modes}\n"
            f"\tresult: {str(evaluated_power_mode)}"
        )
        self.update_component_power_mode(evaluated_power_mode)

    @check_communicating
    def off(
        self: StationComponentManager,
    ) -> ResultCode:
        """
        Turn off this station.

        :return: a result code
        """
        results = [proxy.off() for proxy in self._tile_proxies] + [
            self._apiu_proxy.off()
        ]  # Never mind antennas, turning off APIU suffices

        if ResultCode.FAILED in results:
            return ResultCode.FAILED
        elif ResultCode.QUEUED in results:
            return ResultCode.QUEUED
        else:
            return ResultCode.OK

    @check_communicating
    def on(
        self: StationComponentManager,
    ) -> ResultCode:
        """
        Turn on this station.

        The order to turn a station on is: APIU, then tiles and antennas.

        :return: a result code
        """
        if self._apiu_power_mode == PowerMode.ON:
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
        if not all(
            power_mode == PowerMode.ON for power_mode in self._tile_power_modes.values()
        ):
            results = [proxy.on() for proxy in self._tile_proxies]
            if ResultCode.FAILED in results:
                return ResultCode.FAILED
        if not all(
            power_mode == PowerMode.ON
            for power_mode in self._antenna_power_modes.values()
        ):
            results = [proxy.on() for proxy in self._antenna_proxies]
            if ResultCode.FAILED in results:
                return ResultCode.FAILED
        return ResultCode.QUEUED

    @check_communicating
    @check_on
    def apply_pointing(
        self: StationComponentManager,
        delays: list[float],
    ) -> ResultCode:
        """
        Apply the pointing configuration by setting the delays on each tile.

        :param delays: an array containing a beam index and antenna
            delays

        :return: a result code
        """
        results = [
            tile_proxy.set_pointing_delay(delays) for tile_proxy in self._tile_proxies
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

    @check_communicating
    def configure(
        self: StationComponentManager,
        station_id: int,
    ) -> ResultCode:
        """
        Configure the station.

        This is a placeholder for a real implementation. At present all
        it accepts is the station id, which it checks.

        :param station_id: the id of the station for which the provided
            configuration is intended.

        :raises ValueError: if the configuration was intended for a
            different station
        :return: a result code
        """
        if station_id != self._station_id:
            raise ValueError("Wrong station id")

        self._update_is_configured(True)
        return ResultCode.OK

    def _update_is_configured(
        self: StationComponentManager,
        is_configured: bool,
    ) -> None:
        if self._is_configured != is_configured:
            self._is_configured = is_configured
            self._is_configured_changed_callback(is_configured)
