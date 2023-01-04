# pylint: disable=too-many-lines, too-many-public-methods
#
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for stations."""
from __future__ import annotations

import copy
import functools
import json
import logging
import threading
import time
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

__all__ = ["SpsStationComponentManager"]


class _SubrackProxy(DeviceComponentManager):
    """A proxy to a subrack, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _SubrackProxy,
        fqdn: str,
        station_id: int,
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
        self._connecting = False

        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: _SubrackProxy) -> None:
        self._connecting = True
        super().start_communicating()

    def _device_state_changed(
        self: _SubrackProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if self._connecting and event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            self._connecting = False
        super()._device_state_changed(event_name, event_value, event_quality)


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


# pylint: disable=too-many-instance-attributes
class SpsStationComponentManager(MccsComponentManager):
    """A component manager for a station."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: SpsStationComponentManager,
        station_id: int,
        subrack_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        station_network_address: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param station_id: the id of this station
        :param subrack_fqdns: FQDNs of the Tango devices which manage this
            station's subracks
        :param tile_fqdns: FQDNs of the Tango devices which manage this
            station's TPMs
        :param station_network_address: address prefix for station 40G subnet
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
        self._is_configured = False
        self._on_called = False

        self._communication_state_lock = threading.Lock()
        self._communication_statees = {
            fqdn: CommunicationStatus.DISABLED
            for fqdn in list(subrack_fqdns) + list(tile_fqdns)
        }

        self._tile_power_states = {fqdn: PowerState.UNKNOWN for fqdn in tile_fqdns}
        # TODO
        # tile proxies should be a list (ordered, indexable) not a dictionary.
        # logical tile ID is assigned globally, is not a property assigned
        # by the station
        #
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
        self._subrack_proxies = {
            subrack_fqdn: _SubrackProxy(
                subrack_fqdn,
                station_id,
                logger,
                max_workers,
                functools.partial(
                    self._device_communication_state_changed, subrack_fqdn
                ),
                functools.partial(component_state_changed_callback, fqdn=subrack_fqdn),
            )
            for subrack_id, subrack_fqdn in enumerate(subrack_fqdns)
        }
        self._subrack_power_states = {
            fqdn: PowerState.UNKNOWN for fqdn in subrack_fqdns
        }

        # configuration parameters
        # more to come
        self._csp_ingest_address = "0.0.0.0"
        self._csp_ingest_port = 4660
        self._csp_source_port = 0xF0D0
        self._lmc_param = {
            "mode": "10g",
            "payload_length": 8192,
            "dst_ip": "0.0.0.0",
            "dst_port": 4660,
            "src_port": 0xF0D0,
        }
        self._lmc_integrated_mode = "10g"
        self._lmc_channel_payload_length = 8192
        self._lmc_beam_payload_length = 8192
        self._fortygb_network_address = station_network_address
        self._beamformer_table = [[0, 0, 0, 0, 0, 0, 0]] * 48

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: SpsStationComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.start_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.start_communicating()

    def stop_communicating(self: SpsStationComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.stop_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.stop_communicating()

    def _device_communication_state_changed(
        self: SpsStationComponentManager,
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
        self: SpsStationComponentManager,
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
    def _tile_power_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._tile_power_states[fqdn] = power_state
            self._evaluate_power_state()

    @threadsafe
    def _subrack_power_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._subrack_power_states[fqdn] = power_state
            self._evaluate_power_state()

    def _evaluate_power_state(
        self: SpsStationComponentManager,
    ) -> None:
        with self._power_state_lock:
            power_states = list(self._subrack_power_states.values()) + list(
                self._tile_power_states.values()
            )
            if all(power_state == PowerState.ON for power_state in power_states):
                evaluated_power_state = PowerState.ON
            elif all(power_state == PowerState.OFF for power_state in power_states):
                evaluated_power_state = PowerState.OFF
            else:
                evaluated_power_state = PowerState.UNKNOWN

            self.logger.info(
                "In SpsStationComponentManager._evaluatePowerState with:\n"
                f"\tsubracks: {self._subrack_power_states}\n"
                f"\tiles: {self._tile_power_states}\n"
                f"\tresult: {str(evaluated_power_state)}"
            )
            self.update_component_state({"power_state": evaluated_power_state})

    def set_power_state(
        self: SpsStationComponentManager,
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
            elif fqdn in self._subrack_proxies.keys():
                self._subrack_proxies[fqdn].power_state = power_state
            elif fqdn in self._tile_proxies.keys():
                self._tile_proxies[fqdn].power_state = power_state
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to subrack "
                    "or tile"
                )

    @property
    def power_state_lock(self: MccsComponentManager) -> threading.RLock:
        """
        Return the power state lock of this component manager.

        :return: the power state lock of this component manager.
        """
        return self._power_state_lock

    def off(
        self: SpsStationComponentManager,
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
        self: SpsStationComponentManager,
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
        results = [proxy.off() for proxy in self._subrack_proxies.values()]
        # Never mind tiles, turning off subracks suffices
        # TODO: Here we need to monitor Tiles. This will eventually
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
        self: SpsStationComponentManager,
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
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on this station.

        The order to turn a station on is: subrack, then tiles

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        if not all(
            power_state == PowerState.ON for power_state in self._subrack_power_states
        ):
            result_code = self._turn_on_subracks(task_callback, task_abort_event)

        if not all(
            power_state == PowerState.ON for power_state in self._tile_power_states
        ):
            result_code = self._turn_on_tiles(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            result_code = self._initialise_tiles(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            result_code = self._initialise_station(task_callback, task_abort_event)

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            task_status = TaskStatus.COMPLETED
        else:
            task_status = TaskStatus.FAILED
        if task_callback:
            task_callback(status=task_status)

    @check_communicating
    def _turn_on_subracks(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Turn on subracks if not already on.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        with self._power_state_lock:
            if not all(
                power_state == PowerState.ON
                for power_state in self._subrack_power_states.values()
            ):
                results = []
                for proxy in self._subrack_proxies.values():
                    result_code = proxy.on()
                    results.append(result_code)
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
        # wait for subracks to come up
        timeout = 60  # Seconds
        last_time = time.time() + timeout
        while time.time() < last_time:
            time.sleep(2)
            if all(
                power_state == PowerState.ON
                for power_state in self._subrack_power_states.values()
            ):
                return ResultCode.OK
        self.logger.error("Timed out waiting for subracks to come up")
        return ResultCode.FAILED

    @check_communicating
    def _turn_on_tiles(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Turn on tiles if not already on.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
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
                    time.sleep(4)  # stagger power on by 4 seconds per tile
                    results.append(result_code)
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
        # wait for tiles to come up
        timeout = 60  # Seconds
        last_time = time.time() + timeout
        while time.time() < last_time:
            time.sleep(2)
            results = []
            for proxy in self._tile_proxies.values():
                assert proxy._proxy is not None  # for the type checker
                result_code = proxy._proxy.tileProgrammingState
            if all(result == "INITIALISED" for result in results):
                return ResultCode.OK
        self.logger.error("Timed out waiting for tiles to come up")
        return ResultCode.FAILED

    @check_communicating
    def _initialise_tiles(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Initialise tiles.

        :TODO: MCCS-1257

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        return ResultCode.OK

    @check_communicating
    def _initialise_station(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Initialise complete station.

        :TODO: MCCS-1257

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        return ResultCode.OK

    @property  # type:ignore[misc]
    @check_communicating
    def is_configured(self: SpsStationComponentManager) -> bool:
        """
        Return whether this station component manager is configured.

        :return: whether this station component manager is configured.
        """
        return self._is_configured

    # :TODO: Most methods just return a dummy value
    # ----------
    # Attributes
    # ----------
    @property
    def static_time_delays(self: SpsStationComponentManager) -> list[int]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return copy.deepcopy(self._static_delays)

    @static_time_delays.setter
    def static_time_delays(self: SpsStationComponentManager, delays: list[int]) -> None:
        """
        Set static time delay correction.

        :param delays: Array of one value per antenna/polarization (32 per tile)
        """
        self._static_delays = copy.deepcopy(delays)
        i = 0
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                proxy._proxy.StaticTimeDelays = delays[i : i + 32]
            i = i + 32

    @property
    def channeliser_truncation(self: SpsStationComponentManager) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        return copy.deepcopy(self._channeliser_truncation)

    @channeliser_truncation.setter
    def channeliser_truncation(
        self: SpsStationComponentManager, truncation: list[int]
    ) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self._channeliser_truncation = copy.deepcopy(truncation)
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                proxy._proxy.ChanneliserRoundings = truncation

    @property
    def csp_rounding(self: SpsStationComponentManager) -> list[int]:
        """
        CSP formatter rounding.

        Rounding from 16 to 8 bits in final stage of the
        station beamformer, before sending data to CSP.
        Array of (up to) 384 values, one for each logical channel.
        Range 0 to 7, as number of discarded LS bits.

        :return: CSP formatter rounding for each logical channel.
        """
        return copy.deepcopy(self._csp_rounding)

    @csp_rounding.setter
    def csp_rounding(self: SpsStationComponentManager, truncation: list[int]) -> None:
        """
        Set CSP formatter rounding.

        :param truncation: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self._csp_rounding = copy.deepcopy(truncation)
        proxy = list(self._tile_proxies.values())[-1]
        assert proxy._proxy is not None  # for the type checker
        if proxy._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
            proxy._proxy.set_csp_rounding = truncation

    @property
    def preadu_levels(self: SpsStationComponentManager) -> list[float]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return copy.deepcopy(self._preadu_levels)

    @preadu_levels.setter
    def preadu_levels(self: SpsStationComponentManager, levels: list[float]) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: ttenuator level of preADU channels, one per input channel, in dB
        """
        self._preadu_levels = copy.deepcopy(levels)
        i = 0
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                proxy._proxy.preaduLeves = levels[i : i + 32]
            i = i + 32

    @property
    def beamformer_table(self: SpsStationComponentManager) -> list[list[int]]:
        """
        Get beamformer region table.

        Bidimensional array of one row for each 8 channels, with elements:
        0. start physical channel
        1. beam number
        2. subarray ID
        3. subarray_logical_channel
        4. subarray_beam_id
        5. substation_id
        6. aperture_id

        Each row is a set of 7 consecutive elements in the list.

        :return: list of up to 7*48 values
        """
        return copy.deepcopy(self._beamformer_table)

    @property
    def forty_gb_network_address(self: SpsStationComponentManager) -> str:
        """
        Get 40Gb network address.

        :return: IP network address for station network
        """
        return self._fortygb_network_address

    @property
    def csp_ingest_address(self: SpsStationComponentManager) -> str:
        """
        Get 40Gb CSP address.

        :return: IP address for CSP ingest port
        """
        return self._csp_ingest_address

    @property
    def csp_ingest_port(self: SpsStationComponentManager) -> int:
        """
        Get 40Gb CSP ingest port.

        :return: UDP port for CSP ingest port
        """
        return self._csp_ingest_port

    @property
    def is_programmed(self: SpsStationComponentManager) -> bool:
        """
        Get TPM programming state.

        :return: True if all TPMs are programmed
        """
        return True

    @property
    def test_generator_active(self: SpsStationComponentManager) -> bool:
        """
        Get test generator state.

        :return: True if at least one TPM uses test generator
        """
        return False

    @property
    def is_beamformer_running(self: SpsStationComponentManager) -> bool:
        """
        Get station beamformer state.

        :return: Get station beamformer state
        """
        return False

    def tile_programming_state(self: SpsStationComponentManager) -> list[str]:
        """
        Get TPM programming state.

        :return: list of programming state for all TPMs
        """
        result = []
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            result.append(tile._proxy.tileProgrammingState)
        return result

    def adc_power(self: SpsStationComponentManager) -> list[float]:
        """
        Get input RMS levels.

        :return: list of RMS levels of ADC inputs
        """
        rms_values: list[float] = []
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            rms_values = rms_values + proxy._proxy.AdcPower
        return rms_values

    def board_temperature_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of board temperatures.

        :return: minimum, average and maximum of board temperatures
        """
        return [35.0, 35.0, 35.0]

    def fpga_temperature_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of FPGAs temperatures.

        :return: minimum, average and maximum of FPGAs temperatures
        """
        return [35.0, 35.0, 35.0]

    def pps_delay_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of PPS delays.

        :return: minimum, average and maximum of PPS delays
        """
        return [0.0, 0.0, 0.0]

    def sysref_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of SYSREF presence.

        :return: TRUE if SYSREF is present in all tiles
        """
        return True

    def pll_locked_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of PLL lock state.

        :return: TRUE if SYSREF is present in all tiles
        """
        return True

    def pps_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of PPS presence.

        :return: TRUE if PPS is present in all tiles
        """
        return True

    def clock_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of 10 MHz clock presence.

        :return: TRUE if 10 MHz clock is present in all tiles
        """
        return True

    def forty_gb_network_errors(self: SpsStationComponentManager) -> list[int]:
        """
        Get summary of network errors.

        :return: list of 40Gb network errors for all tiles
        """
        result: list[int] = []
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            result = result + [0, 0]
        return result

    # ------------
    # commands
    # ------------
    def set_lmc_download(
        self: SpsStationComponentManager,
        mode: str,
        payload_length: int,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:
        """
        Configure link and size of LMC channel.

        :param mode: '1g' or '10g'
        :param payload_length: SPEAD payload length for LMC packets
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self._lmc_param["mode"] = mode
        self._lmc_param["payload_length"] = payload_length
        self._lmc_param["dst_ip"] = dst_ip
        self._lmc_param["src_port"] = src_port
        self._lmc_param["dst_port"] = dst_port
        json_param = json.dumps(self._lmc_param)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                tile._proxy.set_lmc_download(json_param)

    def set_lmc_integrated_download(
        self: SpsStationComponentManager,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:
        """
        Configure link and size of integrated LMC channel.

        :param mode: '1g' or '10g'
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self._lmc_integrated_mode = mode
        self._lmc_channel_payload_length = channel_payload_length
        self._lmc_beam_payload_length = beam_payload_length
        json_param = json.dumps(
            {
                "mode": mode,
                "channel_payload_length": channel_payload_length,
                "beam_payload_length": beam_payload_length,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
            }
        )
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                tile._proxy.set_lmc_download(json_param)

    def set_csp_ingest(
        self: SpsStationComponentManager,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:
        """
        Configure link for CSP ingest channel.

        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self._csp_ingest_address = dst_ip
        self._csp_ingest_port = dst_port
        self._csp_source_port = src_port

    def set_beamformer_regions(
        self: SpsStationComponentManager, beamformer_table: list[int]
    ) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param beamformer_table: a list encoding up to 48 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0 and 7)
            and a substation ID (not used)
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                tile._proxy.set_beamformer_regions(beamformer_table)

    def load_calibration_coefficients(
        self: SpsStationComponentManager, calibration_coefficients: list[float]
    ) -> None:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        """
        antenna = int(calibration_coefficients[0])
        tile = antenna // 16
        tile_antenna = antenna % 16
        proxies = list(self._tile_proxies.values())
        proxy = proxies[tile]._proxy
        assert proxy is not None  # for the type checker
        coefs = [float(tile_antenna)] + calibration_coefficients[2:]
        proxy.LoadCalibrationCoefficients(coefs)

    def apply_calibration(self: SpsStationComponentManager, switch_time: str) -> None:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ApplyCalibration()

    def load_pointing_delays(
        self: SpsStationComponentManager, delay_list: list[float]
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param delay_list: delay in seconds, and delay rate in seconds/second
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.LoadPointingDelay(delay_list)

    def apply_pointing_delays(self: SpsStationComponentManager, load_time: str) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ApplyPointingDelay(load_time)

    def start_beamformer(
        self: SpsStationComponentManager,
        start_time: str,
        duration: float,
        subarray_beam_id: int,
        scan_id: int,
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :param subarray_beam_id: ID of the subarray beam to start. Default = -1, all
        :param scan_id: ID of the scan which is started.
        """
        parameter_list = {
            "start_time": start_time,
            "duration": duration,
            "subarray_beam_id": subarray_beam_id,
            "scan_id": scan_id,
        }
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StartBeamformer(json_argument)

    def stop_beamformer(self: SpsStationComponentManager) -> None:
        """Stop the beamformer."""
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StopBeamformer()

    def configure_integrated_channel_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int,
    ) -> None:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        parameter_list = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
        }
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ConfigureIntegratedChannelData(json_argument)

    def configure_integrated_beam_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int,
    ) -> None:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        parameter_list = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
        }
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ConfigureIntegratedBeamData(json_argument)

    def stop_integrated_data(self: SpsStationComponentManager) -> None:
        """Stop the integrated data."""
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StopIntegratedData()

    def send_data_samples(self: SpsStationComponentManager, argin: str) -> None:
        """
        Front end for send_xxx_data methods.

        :param argin: Json encoded parameter List
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.SendDataSamples(argin)

    def stop_data_transmission(self: SpsStationComponentManager) -> None:
        """Stop data transmission for send_channelised_data_continuous."""
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StopDataTransmission()
