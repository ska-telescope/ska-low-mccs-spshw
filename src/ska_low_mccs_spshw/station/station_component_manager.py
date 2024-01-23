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
import itertools
import json
import logging
import threading
import time
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Callable, Optional, Sequence, cast

import tango
from pyfabil.base.utils import ip2long
from ska_control_model import (
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    TaskStatus,
)
from ska_low_mccs_common.component import (
    DeviceComponentManager,
    MccsBaseComponentManager,
)
from ska_low_mccs_common.utils import threadsafe
from ska_tango_base.base import check_communicating
from ska_tango_base.executor import TaskExecutorComponentManager
from ska_telmodel.data import TMData  # type: ignore

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

    def _update_communication_state(
        self: _SubrackProxy,
        communication_state: CommunicationStatus,
    ) -> None:
        # If communication is established with this Tango device,
        # configure it to use the device as the source, not the Tango attribute cache.
        # This might be better done for all of these proxy devices in the common repo.
        if communication_state == CommunicationStatus.ESTABLISHED:
            assert self._proxy is not None
            self._proxy.set_source(tango.DevSource.DEV)
        super()._update_communication_state(communication_state)


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

    def _update_communication_state(
        self: _TileProxy,
        communication_state: CommunicationStatus,
    ) -> None:
        # If communication is established with this Tango device,
        # configure it to use the device as the source, not the Tango attribute cache.
        # This might be better done for all of these proxy devices in the common repo.
        if communication_state == CommunicationStatus.ESTABLISHED:
            assert self._proxy is not None
            self._proxy.set_source(tango.DevSource.DEV)
        super()._update_communication_state(communication_state)


# pylint: disable=too-many-instance-attributes
class SpsStationComponentManager(
    MccsBaseComponentManager, TaskExecutorComponentManager
):
    """A component manager for a station."""

    RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    # pylint: disable=too-many-arguments
    def __init__(
        self: SpsStationComponentManager,
        station_id: int,
        subrack_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        daq_trl: str,
        station_network_address: str,
        antenna_config_uri: Optional[list[str]],
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        tile_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        subrack_health_changed_callback: Callable[[str, Optional[HealthState]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param station_id: the id of this station
        :param subrack_fqdns: FQDNs of the Tango devices which manage this
            station's subracks
        :param tile_fqdns: FQDNs of the Tango devices which manage this
            station's TPMs
        :param daq_trl: The TRL of this Station's DAQ Receiver.
        :param station_network_address: address prefix for station 40G subnet
        :param antenna_config_uri: location of the antenna mapping file
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param tile_health_changed_callback: callback to be
            called when a tile's health changed
        :param subrack_health_changed_callback: callback to be
            called when a subrack's health changed
        """
        self._station_id = station_id
        self._daq_trl = daq_trl
        self._is_configured = False
        self._on_called = False

        self._device_communication_state_lock = threading.Lock()
        self._communication_states = {
            fqdn: CommunicationStatus.DISABLED
            for fqdn in list(subrack_fqdns) + list(tile_fqdns)
        }

        self._power_state_lock = threading.RLock()
        self._tile_power_states = {fqdn: PowerState.UNKNOWN for fqdn in tile_fqdns}
        # TODO
        # tile proxies should be a list (ordered, indexable) not a dictionary.
        # logical tile ID is assigned globally, is not a property assigned
        # by the station
        #
        self._adc_power = {
            logical_tile_id: None for logical_tile_id, _ in enumerate(tile_fqdns)
        }
        self._tile_proxies = {
            tile_fqdn: _TileProxy(
                tile_fqdn,
                station_id,
                logical_tile_id,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, tile_fqdn),
                functools.partial(self._tile_state_changed, tile_fqdn),
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
                functools.partial(self._subrack_state_changed, subrack_fqdn),
            )
            for subrack_id, subrack_fqdn in enumerate(subrack_fqdns)
        }
        self._subrack_power_states = {
            fqdn: PowerState.UNKNOWN for fqdn in subrack_fqdns
        }
        self._tile_health_changed_callback = tile_health_changed_callback
        self._subrack_health_changed_callback = subrack_health_changed_callback
        # configuration parameters
        # more to come
        self._csp_ingest_address = "0.0.0.0"
        self._csp_ingest_port = 4660
        self._csp_source_port = 0xF0D0

        # TODO: this needs to be scaled,
        # We are interested in more than adcPower!!
        self.tile_attributes_to_subscribe = ["adcPower"]

        self._lmc_param = {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": 4660,
            "source_port": 0xF0D0,
        }
        self._lmc_integrated_mode = "10G"
        self._lmc_channel_payload_length = 8192
        self._lmc_beam_payload_length = 8192
        self._fortygb_network_address = station_network_address
        self._beamformer_table = [[0, 0, 0, 0, 0, 0, 0]] * 48
        self._pps_delays = [0] * 16
        self._static_delays = [0] * 512
        self._channeliser_rounding = [3] * 512
        self._csp_rounding = [3] * 384
        self._preadu_levels = [0.0] * 512
        self._source_port = 0xF0D0
        self._destination_port = 4660
        self._base_mac_address = 0x620000000000 + ip2long(self._fortygb_network_address)

        self._antenna_mapping: dict[int, tuple[float, float]] = {}

        if antenna_config_uri:
            self._get_mappings(antenna_config_uri, logger)
        else:
            logger.debug("No antenna mapping provided, skipping")

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            max_workers=1,
            power=PowerState.UNKNOWN,
            fault=None,
            is_configured=None,
            adc_powers=None,
        )

    def _get_mappings(
        self: SpsStationComponentManager,
        antenna_config_uri: list[str],
        logger: logging.Logger,
    ) -> None:
        """
        Get mappings from TelModel.

        :param antenna_config_uri: Repo and filepath for antenna mapping config
        :param logger: the logger to be used by this object.

        Need to pass the logger through as its not been setup by the super yet.
        """
        antenna_mapping_uri = antenna_config_uri[0]
        antenna_mapping_filepath = antenna_config_uri[1]
        station_cluster = antenna_config_uri[2]
        tmdata = TMData([antenna_mapping_uri])
        full_dict = tmdata[antenna_mapping_filepath].get_dict()

        try:
            antennas = full_dict["platform"]["array"]["station_clusters"][
                station_cluster
            ]["stations"][str(self._station_id)]["antennas"]
            for antenna in antennas:
                self._antenna_mapping[int(antenna)] = (
                    antennas[antenna]["tpm_x_channel"],
                    antennas[antenna]["tpm_y_channel"],
                )
        except KeyError as err:
            logger.error(
                "Antenna mapping dictionary structure not as expected, skipping, "
                f"err: {err}",
            )

    def start_communicating(self: SpsStationComponentManager) -> None:
        """Establish communication with the station components."""
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.start_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.start_communicating()

    def stop_communicating(self: SpsStationComponentManager) -> None:
        """Break off communication with the station components."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.stop_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.stop_communicating()

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)

    def _device_communication_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        communication_state: CommunicationStatus,
    ) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self._device_communication_state_lock:
            self._communication_states[fqdn] = communication_state

            if self.communication_state == CommunicationStatus.DISABLED:
                return

            if CommunicationStatus.DISABLED in self._communication_states.values():
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._communication_states.values()
            ):
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self.submit_task(self.subscribe_to_attributes)
                self._update_communication_state(CommunicationStatus.ESTABLISHED)

    def subscribe_to_attributes(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Subscribe to attributes of interest.

        This will form subscriptions to attributes on subdevices
        `MccsTile` and `MccsSubrack` if attribute not already subscribed.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        # Subscribe to Subrack attributes
        for fqdn in self._subrack_proxies.keys():
            self.logger.warning(
                f"Subscriptions for subrack attributes not yet implemented {fqdn}"
            )

        # Subscribe to Tile attributes
        for fqdn, proxy_object in self._tile_proxies.items():
            try:
                assert proxy_object is not None
                if proxy_object._proxy is not None:
                    for tile_attribute in self.tile_attributes_to_subscribe:
                        if (
                            tile_attribute
                            not in proxy_object._proxy._change_event_callbacks.keys()
                        ):
                            proxy_object._proxy.add_change_event_callback(
                                tile_attribute,
                                functools.partial(
                                    self._on_tile_attribute_change,
                                    proxy_object._logical_tile_id,
                                ),
                                stateless=True,
                            )
            except Exception as e:  # pylint: disable=broad-except
                self.logger.warning(
                    "Exception raised when attempting to subscribe "
                    f"to attribute on device{fqdn} :{repr(e)}"
                )

    def _on_tile_attribute_change(
        self: SpsStationComponentManager,
        logical_tile_id: int,
        attribute_name: str,
        attribute_value: Any,
        attribute_quality: tango.AttrQuality,
    ) -> None:
        attribute_name = attribute_name.lower()
        match attribute_name:
            case "adcpower":
                self._adc_power[logical_tile_id] = attribute_value
                adc_powers: list[int] = []
                for _, adc_power in self._adc_power.items():
                    if adc_power is not None:
                        adc_powers += adc_power.tolist()
                self._update_component_state(adc_powers=adc_powers)
            case _:
                self.logger.error(
                    f"Unrecognised tile attribute changing {attribute_name}"
                    "Nothing is updated."
                )

    def _update_communication_state(
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
        super()._update_communication_state(communication_state)
        if communication_state == CommunicationStatus.ESTABLISHED:
            self._update_component_state(is_configured=self.is_configured)

    @threadsafe
    def _tile_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        health: Optional[HealthState] = None,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._tile_power_states[fqdn] = power
                self._evaluate_power_state()
        if health is not None:
            self._tile_health_changed_callback(fqdn, health)

    @threadsafe
    def _subrack_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        health: Optional[HealthState] = None,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._subrack_power_states[fqdn] = power
                self._evaluate_power_state()
        if health is not None:
            self._subrack_health_changed_callback(fqdn, health)

    def _evaluate_power_state(
        self: SpsStationComponentManager,
    ) -> None:
        with self._power_state_lock:
            power_states = list(self._tile_power_states.values())
            if all(power_state == PowerState.ON for power_state in power_states):
                evaluated_power_state = PowerState.ON
            elif all(
                power_state == PowerState.NO_SUPPLY for power_state in power_states
            ):
                evaluated_power_state = PowerState.OFF
            elif all(
                power_state == PowerState.ON
                for power_state in list(self._subrack_power_states.values())
            ) and all(
                power_state == PowerState.OFF
                for power_state in list(self._tile_power_states.values())
            ):
                evaluated_power_state = PowerState.STANDBY
            elif all(
                power_state == PowerState.OFF
                for power_state in list(self._subrack_power_states.values())
            ) and all(
                power_state == PowerState.OFF
                for power_state in list(self._tile_power_states.values())
            ):
                evaluated_power_state = PowerState.OFF
            else:
                evaluated_power_state = PowerState.UNKNOWN
            self.logger.debug(
                "In SpsStationComponentManager._evaluatePowerState with:\n"
                f"\tsubracks: {self._subrack_power_states.values()}\n"
                f"\ttiles: {self._tile_power_states.values()}\n"
                f"\tresult: {str(evaluated_power_state)}"
            )
            self._update_component_state(power=evaluated_power_state)

    def set_power_state(
        self: SpsStationComponentManager,
        power_state: PowerState,
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Set the power_state of the component.

        :TODO: Power state should be set in the component mananger and then
            the device updated. Current design sets the component power state
            from the device component_state_changed callback. This should be
            corrected

        :param power_state: the value of PowerState to be set.
        :param fqdn: the fqdn of the component's device.

        :raises ValueError: fqdn not found
        """
        # Note: this setter was, prior to V0.13 of the base classes, in
        # MccsComponentManager.update_component_power_mode
        with self._power_state_lock:
            if fqdn is None:
                # pylint: disable-next=attribute-defined-outside-init
                self.power_state = power_state
            elif fqdn in self._subrack_proxies.keys():
                self._subrack_proxies[fqdn]._power_state = power_state
            elif fqdn in self._tile_proxies.keys():
                self._tile_proxies[fqdn]._power_state = power_state
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to subrack "
                    "or tile"
                )

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

    @check_communicating
    def standby(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _standby method.

        This method returns immediately after it submitted
        `self._standby` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a task staus and response message
        """
        return self.submit_task(self._standby, task_callback=task_callback)

    @check_communicating
    def _standby(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Put the station in standby: subracks on, tiles off.

        The order to turn a station on is: subrack, then tiles

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        self.logger.debug("Starting standby sequence")
        result_code = ResultCode.OK  # default if nothing to do
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        if not all(
            power_state == PowerState.ON
            for power_state in self._subrack_power_states.values()
        ):
            self.logger.debug("Starting on sequence on subracks")
            result_code = self._turn_on_subracks(task_callback, task_abort_event)
        self.logger.debug("Subracks now on")
        self.logger.debug(f"Tile power states: {self._tile_power_states.values()}")
        with self._power_state_lock:
            self.logger.debug("Starting off sequence on tiles")
            results = []
            for proxy in self._tile_proxies.values():
                [task_status, task_id] = proxy.off()
                time.sleep(2)  # stagger power on by 2 seconds per tile
                results.append(task_status)
            if ResultCode.FAILED in results:
                result_code = ResultCode.FAILED
            else:
                result_code = ResultCode.OK
        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            timeout = 60
            tick = 2
            while timeout > 0:
                if all(
                    states == PowerState.OFF
                    for states in self._tile_power_states.values()
                ):
                    break
                timeout -= tick
                time.sleep(tick)
            if timeout > 0:
                self.logger.debug("End standby")
                task_status = TaskStatus.COMPLETED
            else:
                self.logger.debug("Timeout in standby")
                task_status = TaskStatus.FAILED
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
        self.logger.debug("Starting on sequence")
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        result_code = ResultCode.OK

        if all(
            proxy._proxy is not None
            and proxy._proxy.tileProgrammingState in {"Initialised", "Synchronised"}
            for proxy in self._tile_proxies.values()
        ):
            self.logger.debug("Tiles already initialised")
            result_code = ResultCode.FAILED

        if result_code == ResultCode.OK and not all(
            power_state == PowerState.ON
            for power_state in self._subrack_power_states.values()
        ):
            self.logger.debug("Starting on sequence on subracks")
            result_code = self._turn_on_subracks(task_callback, task_abort_event)
        self.logger.debug("Subracks now on")

        if result_code == ResultCode.OK and not all(
            power_state == PowerState.ON
            for power_state in self._tile_power_states.values()
        ):
            self.logger.debug("Starting on sequence on tiles")
            result_code = self._turn_on_tiles(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising tiles")
            result_code = self._initialise_tile_parameters(
                task_callback, task_abort_event
            )

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising station")
            result_code = self._initialise_station(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Checking synchronisation")
            result_code = self._check_station_synchronisation(
                task_callback, task_abort_event
            )

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            self.logger.debug("End initialisation")
            task_status = TaskStatus.COMPLETED
        else:
            self.logger.error("Initialisation failed")
            task_status = TaskStatus.FAILED
        if task_callback:
            task_callback(status=task_status)

    def initialise(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _initialise method.

        This method returns immediately after it submitted
        `self._initialise` for execution.

        :param task_callback: Update task state, defaults to None
        :return: a task staus and response message
        """
        return self.submit_task(self._initialise, task_callback=task_callback)

    @check_communicating
    def _initialise(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Initialise this station.

        The order to turn a station on is: subrack, then tiles

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        """
        self.logger.debug("Starting initialise sequence")
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        result_code = ResultCode.OK
        if not all(
            power_state == PowerState.ON
            for power_state in self._subrack_power_states.values()
        ):
            self.logger.debug("Subracks not on.")
            result_code = ResultCode.FAILED

        if not all(
            power_state == PowerState.ON
            for power_state in self._tile_power_states.values()
        ):
            self.logger.debug("Tiles not on.")
            result_code = ResultCode.FAILED

        if result_code == ResultCode.OK:
            self.logger.debug("Re-initialising tiles")
            result_code = self._reinitialise_tiles(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising tile parameters")
            result_code = self._initialise_tile_parameters(
                task_callback, task_abort_event
            )

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising station")
            result_code = self._initialise_station(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Checking synchronisation")
            result_code = self._check_station_synchronisation(
                task_callback, task_abort_event
            )

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            self.logger.debug("End initialisation")
            task_status = TaskStatus.COMPLETED
        else:
            self.logger.error("Initialisation failed")
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
        timeout = 180  # Seconds. Switch may take up to 3 min to recognize a new link
        tick = 2
        last_time = time.time() + timeout
        while time.time() < last_time:
            time.sleep(tick)
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
                    assert proxy._proxy is not None
                    self.logger.debug(f"Powering on tile {proxy._proxy.name()}")
                    result_code = proxy.on()
                    time.sleep(4)  # stagger power on by 4 seconds per tile
                    results.append(result_code)
                if ResultCode.FAILED in results:
                    return ResultCode.FAILED
        # wait for tiles to come up
        timeout = 180  # Seconds. Switch may take up to 3 min to recognize a new link
        tick = 2
        last_time = time.time() + timeout
        while time.time() < last_time:
            time.sleep(tick)
            states = self.tile_programming_state()
            self.logger.debug(f"tileProgrammingState: {states}")
            if all(state in ["Initialised", "Synchronised"] for state in states):
                return ResultCode.OK
        self.logger.error("Timed out waiting for tiles to come up")
        return ResultCode.FAILED

    @check_communicating
    def _reinitialise_tiles(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Initialise tiles.

        Initialise tiles by completely reprogram and reconfigure all internal
        peripherals. This is required prior to station synchronization.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code

        """
        with self._power_state_lock:
            results = []
            for proxy in self._tile_proxies.values():
                assert proxy._proxy is not None
                self.logger.debug(f"Re-initialising tile {proxy._proxy.name()}")
                result_code = proxy._proxy.initialise()
                time.sleep(2)  # stagger initialisation by 2 seconds per tile
                results.append(result_code)
        if ResultCode.FAILED in results:
            return ResultCode.FAILED

        # wait for tiles to come up
        timeout = 180  # Seconds. Switch may take up to 3 min to recognize a new link
        tick = 2
        last_time = time.time() + timeout
        while time.time() < last_time:
            time.sleep(tick)
            states = self.tile_programming_state()
            self.logger.debug(f"tileProgrammingState: {states}")
            if all(state in ["Initialised", "Synchronised"] for state in states):
                return ResultCode.OK
        self.logger.error("Timed out waiting for tiles to come up")
        return ResultCode.FAILED

    @check_communicating
    def _initialise_tile_parameters(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Initialise tile parameters.

        Inilitalse parameters which are individually set in each tile,
        after the tile has been programmed.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        tile_no = 0
        last_tile = len(self._tile_proxies.values()) - 1
        for proxy in self._tile_proxies.values():
            tile = proxy._proxy
            assert tile is not None
            i1 = tile_no * 32  # indexes for parameters for individual signals
            i2 = i1 + 32
            self.logger.debug(f"Initialising tile {tile_no}: {tile.name()}")
            tile.preaduLevels = self._preadu_levels[i1:i2]
            tile.staticTimeDelays = self._static_delays[i1:i2]
            tile.channeliserRounding = self._channeliser_rounding
            tile.cspRounding = self._csp_rounding
            tile.ppsDelay = self._pps_delays[tile_no]
            tile.SetLmcDownload(json.dumps(self._lmc_param))
            tile.ConfigureStationBeamformer(
                json.dumps(
                    {"is_first": (tile_no == 0), "is_last": (tile_no == last_tile)}
                )
            )
            tile_no = tile_no + 1
        self._set_beamformer_table()
        return ResultCode.OK

    @check_communicating
    def _initialise_station(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Initialise complete station.

        Set parameters in individual tiles which depend on the whole station.

        :TODO: MCCS-1257

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        tiles = list(self._tile_proxies.values())
        #
        # Configure 40G ports. IP address is determined by cabinet IP
        # 40G subnet is upper /25 part of /24 cabinet network
        # Each TPM has 2 IP addresses starting at address 24
        # Each TPM 40G port point to the corresponding
        # Last TPM uses CSP ingest address and port
        #
        base_ip = self._fortygb_network_address.split(".")
        if self._station_id % 2 == 1:
            base_ip3 = 0x80
        else:
            base_ip3 = 0xC0
        last_tile = len(tiles) - 1
        tile = 0
        for proxy in tiles:
            assert proxy._proxy is not None
            src_ip1 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+24+2*tile}"
            src_ip2 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+25+2*tile}"
            dst_ip1 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+26+2*tile}"
            dst_ip2 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+27+2*tile}"
            dst_port = self._destination_port
            src_mac = self._base_mac_address + base_ip3 + 24 + 2 * tile
            if tile == last_tile:
                dst_ip1 = self._csp_ingest_address
                dst_ip2 = self._csp_ingest_address
                dst_port = self._csp_ingest_port
            self.logger.debug(f"Tile {tile}: 40G#1: {src_ip1} -> {dst_ip1}")
            self.logger.debug(f"Tile {tile}: 40G#2: {src_ip2} -> {dst_ip2}")
            proxy._proxy.Configure40GCore(
                json.dumps(
                    {
                        "core_id": 0,
                        "arp_table_entry": 0,
                        "source_ip": src_ip1,
                        "source_mac": src_mac,
                        "source_port": self._source_port,
                        "destination_ip": dst_ip1,
                        "destination_port": dst_port,
                    }
                )
            )
            proxy._proxy.Configure40GCore(
                json.dumps(
                    {
                        "core_id": 1,
                        "arp_table_entry": 0,
                        "source_ip": src_ip2,
                        "source_mac": src_mac + 1,
                        "source_port": self._source_port,
                        "destination_ip": dst_ip2,
                        "destination_port": dst_port,
                    }
                )
            )
            proxy._proxy.SetLmcDownload(json.dumps(self._lmc_param))
            proxy._proxy.SetLmcIntegratedDownload(
                json.dumps(
                    {
                        "mode": self._lmc_integrated_mode,
                        "destination_ip": self._lmc_param["destination_ip"],
                        "channel_payload_length": self._lmc_channel_payload_length,
                        "beam_payload_length": self._lmc_beam_payload_length,
                    }
                )
            )
            tile = tile + 1
        return ResultCode.OK

    @check_communicating
    def _check_station_synchronisation(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Check tile synchronization.

        Wait for a second boundary and check all FPGAs in all tiles report
        the same time
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        tiles = list(self._tile_proxies.values())
        tile0 = tiles[0]._proxy
        assert tile0 is not None
        time0 = (tile0.fpgasUnixTime)[0]
        timeout = 15
        while (tile0.fpgasUnixTime)[0] == time0:
            if timeout == 0:
                self.logger.error("Timeout waiting for FPGA time second tick")
                return ResultCode.FAILED
            time.sleep(0.1)
            timeout = timeout - 1
        result: list[int] = []
        time.sleep(0.4)  # Wait till mid second
        for proxy in tiles:
            assert proxy._proxy is not None
            result = result + list(proxy._proxy.fpgasUnixTime)
        self.logger.debug(f"Current FPGA times:{result}")
        if any(result[0] != time_n for time_n in result):
            self.logger.error("FPGA time counters not synced")
            return ResultCode.FAILED
        return ResultCode.OK

    @property  # type:ignore[misc]
    @check_communicating
    def is_configured(self: SpsStationComponentManager) -> bool:
        """
        Return whether this station component manager is configured.

        :return: whether this station component manager is configured.
        """
        return self._is_configured

    # ----------
    # Attributes
    # ----------
    @property
    def pps_delays(self: SpsStationComponentManager) -> list[int]:
        """
        Get PPS delay correction.

        Array of one value per tile. Defines PPS delay correction,
        Values are internally rounded to 1.25 ns steps

        :return: Array of one value per tile, in nanoseconds
        """
        return copy.deepcopy(self._pps_delays)

    @pps_delays.setter
    def pps_delays(self: SpsStationComponentManager, delays: list[int]) -> None:
        """
        Set PPS delay correction.

        :param delays: Array of one value per tile, in nanoseconds.
            Values are internally rounded to 1.25 ns steps
        """
        self._pps_delays = copy.deepcopy(delays)
        i = 0
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.ppsDelays = delays[i]
            i = i + 1

    @property
    def static_delays(self: SpsStationComponentManager) -> list[int]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return copy.deepcopy(self._static_delays)

    @static_delays.setter
    def static_delays(self: SpsStationComponentManager, delays: list[int]) -> None:
        """
        Set static time delay correction.

        :param delays: Array of one value per antenna/polarization (32 per tile)
        """
        self._static_delays = copy.deepcopy(delays)
        i = 0
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.staticTimeDelays = delays[i : i + 32]
            i = i + 32

    @property
    def channeliser_rounding(self: SpsStationComponentManager) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        return copy.deepcopy(self._channeliser_rounding)

    @channeliser_rounding.setter
    def channeliser_rounding(
        self: SpsStationComponentManager, truncation: list[int]
    ) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self._channeliser_rounding = copy.deepcopy(truncation)
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                self.logger.debug(
                    f"Writing truncation  {truncation[0]} in {proxy._proxy.name()}"
                )
                proxy._proxy.channeliserRounding = truncation

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
        if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
            self.logger.debug(
                f"Writing csp rounding  {truncation[0]} in {proxy._proxy.name()}"
            )
            proxy._proxy.cspRounding = truncation

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
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.preaduLevels = levels[i : i + 32]
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
    def csp_source_port(self: SpsStationComponentManager) -> int:
        """
        Get 40Gb CSP source port.

        :return: UDP port for CSP source port
        """
        return self._csp_source_port

    @property
    def is_programmed(self: SpsStationComponentManager) -> bool:
        """
        Get TPM programming state.

        :return: True if all TPMs are programmed
        """
        return all(
            programming_state in {"Programmed", "Initialised", "Synchronised"}
            for programming_state in self.tile_programming_state()
        )

    @property
    def test_generator_active(self: SpsStationComponentManager) -> bool:
        """
        Get test generator state.

        :return: True if at least one TPM uses test generator
        """
        return any(
            tile._proxy is not None and tile._proxy.testGeneratorActive
            for tile in self._tile_proxies.values()
        )

    @property
    def is_beamformer_running(self: SpsStationComponentManager) -> bool:
        """
        Get station beamformer state.

        :return: Get station beamformer state
        """
        return all(
            tile._proxy is not None and tile._proxy.isBeamformerRunning
            for tile in self._tile_proxies.values()
        )

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
            rms_values = rms_values + list(proxy._proxy.adcPower)
        return rms_values

    def board_temperature_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of board temperatures.

        :return: minimum, average and maximum of board temperatures
        """
        board_temperatures = list(
            tile._proxy is not None and tile._proxy.boardTemperature
            for tile in self._tile_proxies.values()
        )
        return [
            min(board_temperatures),
            mean(board_temperatures),
            max(board_temperatures),
        ]

    def fpga_temperature_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of FPGAs temperatures.

        :return: minimum, average and maximum of FPGAs temperatures
        """
        fpga_temperatures = list(
            tile._proxy is not None and tile._proxy.fpgaTemperature
            for tile in self._tile_proxies.values()
        )
        return [min(fpga_temperatures), mean(fpga_temperatures), max(fpga_temperatures)]

    def pps_delay_summary(self: SpsStationComponentManager) -> list[float]:
        """
        Get summary of PPS delays.

        :return: minimum, average and maximum of PPS delays
        """
        pps_delays = list(
            tile._proxy is not None and tile._proxy.ppsDelay
            for tile in self._tile_proxies.values()
        )
        return [min(pps_delays), mean(pps_delays), max(pps_delays)]

    def sysref_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of SYSREF presence.

        :return: TRUE if SYSREF is present in all tiles
        """
        return all(
            tile._proxy is not None and tile._proxy.sysrefPresent
            for tile in self._tile_proxies.values()
        )

    def pll_locked_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of PLL lock state.

        :return: TRUE if PLL locked in all tiles
        """
        return all(
            tile._proxy is not None and tile._proxy.pllLocked
            for tile in self._tile_proxies.values()
        )

    def pps_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of PPS presence.

        :return: TRUE if PPS is present in all tiles
        """
        return all(
            tile._proxy is not None and tile._proxy.ppsPresent
            for tile in self._tile_proxies.values()
        )

    def clock_present_summary(self: SpsStationComponentManager) -> bool:
        """
        Get summary of 10 MHz clock presence.

        :return: TRUE if 10 MHz clock is present in all tiles
        """
        return all(
            tile._proxy is not None and tile._proxy.clockPresent
            for tile in self._tile_proxies.values()
        )

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
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Configure link and size of LMC channel.

        :param mode: '1G' or '10G'
        :param payload_length: SPEAD payload length for LMC packets
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self._lmc_param["mode"] = mode
        self._lmc_param["payload_length"] = payload_length
        self._lmc_param["destination_ip"] = dst_ip
        self._lmc_param["source_port"] = src_port
        self._lmc_param["destination_port"] = dst_port
        json_param = json.dumps(self._lmc_param)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                tile._proxy.SetLmcDownload(json_param)

    def set_lmc_integrated_download(
        self: SpsStationComponentManager,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: str = "",
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Configure link and size of integrated LMC channel.

        :param mode: '1G' or '10G'
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
        if dst_ip == "":
            dst_ip = cast(str, self._lmc_param["destination_ip"])
        json_param = json.dumps(
            {
                "mode": mode,
                "channel_payload_length": channel_payload_length,
                "beam_payload_length": beam_payload_length,
                "destination_ip": dst_ip,
                "source_port": src_port,
                "destination_port": dst_port,
            }
        )
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                tile._proxy.SetLmcIntegratedDownload(json_param)

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
        base_ip = self._fortygb_network_address.split(".")
        if self._station_id % 2 == 1:
            base_ip3 = 0x80
        else:
            base_ip3 = 0xC0
        (fqdn, proxy) = list(self._tile_proxies.items())[-1]
        assert proxy._proxy is not None  # for the type checker
        if self._tile_power_states[fqdn] != PowerState.ON:
            return  # Do not access an unprogrammed TPM

        last_tile = len(self._tile_proxies) - 1
        src_ip1 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+24+2*last_tile}"
        src_ip2 = f"{base_ip[0]}.{base_ip[1]}.{base_ip[2]}.{base_ip3+25+2*last_tile}"
        dst_ip1 = self._csp_ingest_address
        dst_ip2 = self._csp_ingest_address
        dst_port = self._csp_ingest_port
        src_mac = self._base_mac_address + base_ip3 + 24 + 2 * last_tile
        self.logger.debug(f"Tile {last_tile}: 40G#1: {src_ip1} -> {dst_ip1}")
        self.logger.debug(f"Tile {last_tile}: 40G#2: {src_ip2} -> {dst_ip2}")
        proxy._proxy.Configure40GCore(
            json.dumps(
                {
                    "core_id": 0,
                    "arp_table_entry": 0,
                    "source_ip": src_ip1,
                    "source_mac": src_mac,
                    "source_port": self._source_port,
                    "destination_ip": dst_ip1,
                    "destination_port": dst_port,
                }
            )
        )
        proxy._proxy.Configure40GCore(
            json.dumps(
                {
                    "core_id": 1,
                    "arp_table_entry": 0,
                    "source_ip": src_ip2,
                    "source_mac": src_mac + 1,
                    "source_port": self._source_port,
                    "destination_ip": dst_ip2,
                    "destination_port": dst_port,
                }
            )
        )

    def set_beamformer_table(
        self: SpsStationComponentManager, beamformer_table: list[list[int]]
    ) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param beamformer_table: a list encoding up to 48 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0 and 7)
            and a substation ID (not used)
        """
        self._beamformer_table = copy.deepcopy(beamformer_table)
        self._set_beamformer_table()

    def _set_beamformer_table(
        self: SpsStationComponentManager,
    ) -> None:
        """Set the frequency regions to be beamformed into a single beam."""
        beamformer_regions = []
        for entry in self._beamformer_table:
            beamformer_regions.append(list([entry[0], 8]) + list(entry[1:7]))
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if tile._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                self.logger.debug(f"Set beamformer table on tile {tile._proxy.name()}")
                tile._proxy.SetBeamformerRegions(
                    list(itertools.chain.from_iterable(beamformer_regions))
                )

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
        coefs = copy.deepcopy(calibration_coefficients)
        coefs[0] = float(tile_antenna)
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
            tile._proxy.ApplyCalibration(switch_time)

    def load_pointing_delays(
        self: SpsStationComponentManager, delay_list: list[float]
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-47, limited to 7 in the current
        firmware)

        :param delay_list: delay in seconds, and delay rate in seconds/second
        """
        beam_index = delay_list[0]
        delays_for_tile = [beam_index] + [0.0] * 32
        first_delay = 1
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            last_delay = first_delay + 32
            delays_for_tile[1:33] = delay_list[first_delay:last_delay]
            tile._proxy.LoadPointingDelays(delays_for_tile)
            first_delay = last_delay

    def apply_pointing_delays(self: SpsStationComponentManager, load_time: str) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ApplyPointingDelays(load_time)

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

    def configure_test_generator(self: SpsStationComponentManager, argin: str) -> None:
        """
        Distribute to tiles command configure_test_generator.

        :param argin: Json encoded parameter List
        """
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.ConfigureTestGenerator(argin)

    def start_acquisition(
        self: SpsStationComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the start acquisition method.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param argin: json dictionary with optional keywords

        * start_time - (str) start time
        * delay - (int) delay start

        :param task_callback: Update task state, defaults to None

        :return: a task staus and response message
        """
        params = json.loads(argin)
        start_time = params.get("start_time", None)
        delay = params.get("delay", 0)

        if start_time is None:
            start_time = datetime.strftime(
                datetime.fromtimestamp(time.time(), tz=timezone.utc), self.RFC_FORMAT
            )
        else:
            delay = 0

        return self.submit_task(
            self._start_acquisition,
            args=[start_time, delay],
            task_callback=task_callback,
        )

    @check_communicating
    def _start_acquisition(
        self: SpsStationComponentManager,
        start_time: Optional[str] = None,
        delay: Optional[int] = 2,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Start acquisition using slow command.

        :param start_time: the time at which to start data acquisition, defaults to None
        :param delay: delay start, defaults to 2
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        success = True

        parameter_list = {"start_time": start_time, "delay": delay}
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StartAcquisition(json_argument)

        if task_callback:
            if success:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="Start acquisition has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="Start acquisition task failed"
                )
            return
