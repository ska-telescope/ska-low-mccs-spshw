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
        tile_fqdns: Sequence[str],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param station_id: the id of this station
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


        self._tile_power_states = {fqdn: PowerState.UNKNOWN for fqdn in tile_fqdns}
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
        self._subrack_power_states = {fqdn: PowerState.UNKNOWN for fqdn in subrack_fqdns}

        # configuration parameters

        self._
        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: SpsStationComponentManager) -> None:
        """Establish communication with the station components."""
        super().start_communicating()

        self._apiu_proxy.start_communicating()
        for tile_proxy in self._tile_proxies.values():
            tile_proxy.start_communicating()
        for antenna_proxy in self._antenna_proxies.values():
            antenna_proxy.start_communicating()

    def stop_communicating(self: SpsStationComponentManager) -> None:
        """Break off communication with the station components."""
        super().stop_communicating()

        for antenna_proxy in self._antenna_proxies.values():
            antenna_proxy.stop_communicating()
        for tile_proxy in self._tile_proxies.values():
            tile_proxy.stop_communicating()
        self._apiu_proxy.stop_communicating()

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
            power_states = (
                + list(self._subrack_power_states.values())
                + list(self._tile_power_states.values())
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
                self._antenna_proxies[fqdn].power_state = power_state
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
            power_state == PowerState.ON
            for power_state in self._subrack_power_states
        ):
            result_code = self._turn_on_subracks(task_callback, task_abort_event)

        if not all(
            power_state == PowerState.ON
            for power_state in self._tile_power_states
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
        return

    @check_communicating
    def _turn_on_tile(
        self: SpsStationComponentManager,
    ) -> ResultCode:
        """
        Turn on tiles if not already on.

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
                    time.sleep(4)    # stagger power on by 4 seconds per tile
                    results.append(result_code)
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
        # wait for tiles to come up
        timeout = 60 # Seconds
        last_time = time.now + timeout
        while time.now < last_time:
            time.sleep(2):
            results = []
            for proxy in self._tile_proxies.values():
                result_code = proxy._proxy.tileProgrammingState
            if all (
                result == "INITIALISED"
                for result in results
            ):
            return ResultCode.OK
        self.logger.error("Timed out waiting for tiles to come up")
        return ResultCode.FAILED

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
    def static_time_delays(self: SpsStationComponentManager) -> list(int):
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return copy.deepcopy(self._static_delays)

    @static_time_delays.setter(self: SpsStationComponentManager, delays: list[int]) -> None:
        """
        Set static time delay correction.
        :param delays: Array of one value per antenna/polarization (32 per tile)
        """
        self._static_delays = copy.deepcopy(delays)
        i = 0
        for tile in self._tile_proxies:
            if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                tile.proxy.StaticTimeDelays = delays[i:i+32]
            i = i + 32

    @property
    def channeliser_truncation(self: SpsStationComponentManager) -> list(int):
        channeliserRounding(self: SpsStation) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        return copy.deepcopy(self._channeliser_truncation)

    @channeliser_truncation.setter(self: SpsStationComponentManager, truncation: list[int]) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self._channeliser_truncation = copy.deepcopy(truncation)
        for tile in self._tile_proxies:
            if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
                tile.proxy.ChanneliserRoundings = truncation

    @property
    def csp_rounding(self: SpsStationComponentManager) -> list(int):
        return copy.deepcopy(self._csp_rounding)

    @csp_rounding.setter(self: SpsStationComponentManager, truncation: list[int]) -> None:
        self._csp_rounding = copy.deepcopy(truncation)
        tile = self._tile_proxies[-1]
        if tile._proxy.tile_programming_state in ["INITIALISED", "SYNCHRONISED"]:
            tile.proxy.set_csp_rounding = truncation

    @property
    def preadu_levels(self: SpsStationComponentManager) -> list[float]:
        return copy.deepcopy(self._preadu_levels)

    @property
    def beamformer_table(self: SpsStationComponentManager) -> list[list[float]]:
        return copy.deepcopy(self._beamformer_table)

    def forty_gb_network_address(self: SpsStationComponentManager) -> str:
        return self._fortygb_network_address

    def csp_ingest_address(self: SpsStationComponentManager) -> str:
        return self._csp_ingest_address

    def csp_ingest_port(self: SpsStationComponentManager) -> int:
        return self._csp_ingest_port

    def isProgrammed(self: SpsStationComponentManager) -> bool:
        return True

    def testGeneratorActive(self: SpsStationComponentManager) -> bool:
        return False

    def isBeamformerRunning(self: SpsStationComponentManager) -> bool:
        return False

    def tileProgrammingState(self: SpsStationComponentManager) -> list[str]:

    def adc_power(self: SpsStationComponentManager) -> list[float]:
        rms_values = []
        for tile in self._tile_proxies:
            rms_values.append(self._proxy.AdcPower)
        return rms_values

    def board_temperature_summary(self: SpsStationComponentManager) -> list[float]:
        return [35.,35., 35.]

    def fpga_temperatures_summary(self: SpsStationComponentManager) -> list[float]:
        return [35.,35., 35.]

    def pps_delay_summary(self: SpsStationComponentManager) -> list[float]:
        return [0., 0., 0.]

    def sysref_present_summary(self: SpsStationComponentManager) -> bool:
        return True

    def pll_locked_summary(self: SpsStationComponentManager) -> bool:
        return True

    def pps_present_summary(self: SpsStationComponentManager) -> bool:
        return True

    def clock_present_summary(self: SpsStationComponentManager) -> bool:
        return True

    def forty_gb_network_errors(self: SpsStationComponentManager) -> list[int]:
        result = []
        for tile in self._tile_proxies:
            result.append([0, 0])
        return result

    #------------
    # commands
    #------------
    def set_lmc_download(
        self: SpsStationComponentManager,
        mode: str,
        payload_length: int,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:

    def set_lmc_integrated_download(
        self: SpsStationComponentManager,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:

    def set_csp_ingest(
        self: SpsStationComponentManager,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> None:
    self._csp_ingest_address = dst_ip
    self._csp_ingest_port = dst_port
    self._csp_source_port = src_port

    def set_beamformer_regions(
        self: SpsStationComponentManager,
        beamformer_table: list[int]
    ) -> None:


    def load_calibration_coefficients(
        self: SpsStationComponentManager,
        coefficient_list: list[float]
    ) -> None:
        antenna = int(beamformer_table[0])
        tile = antenna // 16
        tile_antenna = antenna % 16

    def apply_calibration(
        self: SpsStationComponentManager,
        switch_time: str
    ) -> None:
        for tile in self._tile_proxies:
            self._proxy.ApplyCalibration()

    def load_pointing_delays(
        self: SpsStationComponentManager,
        delay_list: list[float]
    ) -> None:
        for tile in self._tile_proxies:
            self._proxy.LoadPointingDelay(delay_list)

    def apply_pointing_delys(self: SpsStationComponentManager,switch_time) -> None:
        for tile in self._tile_proxies:
            self._proxy.ApplyPointingDelay(switch_time)

    def start_beamformer(
        self: SpsStationComponentManager,
        start_time: str,
        duration: float,
        subarray_beam_id: int,
        scan_id: int
    ) -> None:
        parameter_list = {
            "start_time": start_time,
            "duration": duration,
            "subarray_beam_id": subarray_beam_id,
            "scan_id": scan_id
        }
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies:
            self._proxy.StartBeamformer(json_argument)

    def stop_beamformer(self: SpsStationComponentManager) -> None:
        for tile in self._tile_proxies:
            self._proxy.StopBeamformer()

    def configure_integrated_channel_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int,
    ) -> None:

    def configure_integrated_beam_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int
    ) -> None:
        parameter_list = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel
        }
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies:
            self._proxy.ConfigureIntegratedBeamData(json_argument)

    def stop_integrated_data(self: SpsStationComponentManager) -> None:
        for tile in self._tile_proxies:
            self._proxy.StopIntegratedData()

    def send_data_samples(self: SpsStationComponentManager, argin: str) -> None:
        for tile in self._tile_proxies:
            self._proxy.SendDataSamples(argin)

    def stop_data_transmission(self: SpsStationComponentManager) -> None:
        for tile in self._tile_proxies:
            self._proxy.StopDataTransmission()
