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
import ipaddress
import itertools
import json
import logging
import threading
import time
from concurrent import futures
from statistics import mean
from typing import Any, Callable, Generator, Optional, Sequence, Union, cast

import numpy as np
import tango
from astropy.time import Time  # type: ignore
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

from ..tile.tile_data import TileData
from .station_self_check_manager import SpsStationSelfCheckManager
from .tests.base_tpm_test import TestResult

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
        if event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            if self._proxy.stationId != self._station_id:
                self.logger.warning(
                    f"Expected {self._proxy.dev_name()} stationId "
                    f"{self._station_id}, tile has stationId {self._proxy.stationid}"
                )
            if self._proxy.logicalTileId != self._logical_tile_id:
                self.logger.warning(
                    f"Expected {self._proxy.dev_name()} logicalTileId "
                    f"{self._logical_tile_id}, tile has logicalTileID "
                    f"{self._proxy.logicalTileId}"
                )
            if self._connecting:
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

    def preadu_levels(self: _TileProxy) -> list[float]:
        """
        Return preAdu levels.

        :return: preAdu levels
        """
        assert self._proxy is not None  # for the type checker
        return self._proxy.preaduLevels

    def adc_power(self: _TileProxy) -> list[float]:
        """
        Return adcPower.

        :return: adcPower
        """
        assert self._proxy is not None  # for the type checker
        return self._proxy.adcPower


class _DaqProxy(DeviceComponentManager):
    """A proxy to a subrack, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _DaqProxy,
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

    def start_communicating(self: _DaqProxy) -> None:
        self._connecting = True
        super().start_communicating()

    def _device_state_changed(
        self: _DaqProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if self._connecting and event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            self._connecting = False
        super()._device_state_changed(event_name, event_value, event_quality)

    def _update_communication_state(
        self: _DaqProxy,
        communication_state: CommunicationStatus,
    ) -> None:
        # If communication is established with this Tango device,
        # configure it to use the device as the source, not the Tango attribute cache.
        # This might be better done for all of these proxy devices in the common repo.
        if communication_state == CommunicationStatus.ESTABLISHED:
            assert self._proxy is not None
            self._proxy.set_source(tango.DevSource.DEV)

            self._proxy.add_change_event_callback(
                "xPolBandpass", self._daq_data_callback
            )
            self._proxy.add_change_event_callback(
                "yPolBandpass", self._daq_data_callback
            )
            self._proxy.add_change_event_callback(
                "dataReceivedResult", self._daq_data_callback
            )
        super()._update_communication_state(communication_state)

    def _daq_data_callback(
        self: _DaqProxy,
        attribute_name: str,
        attribute_data: Any,
        attribute_quality: Any,
    ) -> None:
        """
        Extract bandpass data or data received from event and call cb to update.

        :param attribute_name: Name of attribute that changed.
        :param attribute_data: New value of attribute.
        :param attribute_quality: Validity of attribute change.
        """
        if self._component_state_callback:
            if attribute_name.lower() == "xpolbandpass":
                self.logger.debug("Processing change event for xPolBandpass")
                self._component_state_callback(xPolBandpass=attribute_data)
            elif attribute_name.lower() == "ypolbandpass":
                self.logger.debug("Processing change event for yPolBandpass")
                self._component_state_callback(yPolBandpass=attribute_data)
            elif attribute_name.lower() == "datareceivedresult":
                self.logger.debug("Processing change event for dataReceivedResult")
                self._component_state_callback(dataReceivedResult=attribute_data)
            else:
                self.logger.error(
                    f"Got unexpected change event for: {attribute_name} "
                    "in DaqProxy._daq_data_callback."
                )


# pylint: disable=too-many-instance-attributes
class SpsStationComponentManager(
    MccsBaseComponentManager, TaskExecutorComponentManager
):
    """A component manager for a station."""

    RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    # pylint: disable=too-many-arguments, too-many-locals, too-many-statements
    def __init__(
        self: SpsStationComponentManager,
        station_id: int,
        subrack_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        daq_trl: str,
        sdn_first_interface: ipaddress.IPv4Interface,
        sdn_gateway: ipaddress.IPv4Address | None,
        csp_ingest_ip: ipaddress.IPv4Address | None,
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
        :param sdn_first_interface: CIDR-style IP address with mask,
            for the first interface in the block assigned for science data
            For example, "10.130.0.1/25" means
            "address 10.130.0.1 on network 10.130.0.0/25".
        :param sdn_gateway: IP address of the SDN gateway,
            or None if the network has no gateway.
        :param csp_ingest_ip: IP address of the CSP ingest for this station.
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
        self._daq_proxy: Optional[_DaqProxy] = None
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
        self._tile_id_mapping: dict[str, int] = {}
        number_of_tiles = len(tile_fqdns)
        self._adc_power: dict[int, Optional[list[float]]] = {}
        self._static_delays: dict[int, Optional[list[float]]] = {}
        self._preadu_levels: dict[int, Optional[list[float]]] = {}
        for logical_tile_id in range(number_of_tiles):
            self._adc_power[logical_tile_id] = None
            self._static_delays[logical_tile_id] = None
            self._preadu_levels[logical_tile_id] = None
        # TODO
        # tile proxies should be a list (ordered, indexable) not a dictionary.
        # logical tile ID is assigned globally, is not a property assigned
        # by the station
        self._tile_proxies: dict[str, _TileProxy] = {}
        for logical_tile_id, tile_fqdn in enumerate(tile_fqdns):
            self._tile_proxies[tile_fqdn] = _TileProxy(
                tile_fqdn,
                station_id,
                logical_tile_id,
                logger,
                max_workers,
                functools.partial(self._device_communication_state_changed, tile_fqdn),
                functools.partial(self._tile_state_changed, tile_fqdn),
            )
            # TODO: Extracting tile id from TRL of the form "low-mccs/tile/s8-1-tpm01"
            # But this code should not be relying on assumptions about TRL structure
            self._tile_id_mapping[tile_fqdn.split("-")[-1][3:]] = logical_tile_id

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
        if self._daq_trl is not None:
            # TODO: Detect a bad daq trl.
            self._daq_proxy = _DaqProxy(
                self._daq_trl,
                station_id,
                logger,
                max_workers,
                functools.partial(
                    self._device_communication_state_changed, self._daq_trl
                ),
                functools.partial(self._daq_state_changed, self._daq_trl),
            )
            self._daq_power_state = {daq_trl: PowerState.UNKNOWN}
        self._subrack_power_states = {
            fqdn: PowerState.UNKNOWN for fqdn in subrack_fqdns
        }
        self._tile_health_changed_callback = tile_health_changed_callback
        self._subrack_health_changed_callback = subrack_health_changed_callback
        # configuration parameters
        # more to come
        self._csp_ingest_address = str(csp_ingest_ip) if csp_ingest_ip else "0.0.0.0"
        self._csp_ingest_port = 4660
        self._csp_source_port = 0xF0D0

        # TODO: this needs to be scaled,
        self.tile_attributes_to_subscribe = [
            "adcPower",
            "staticTimeDelays",
            "preaduLevels",
        ]

        self._source_port = 0xF0D0
        self._destination_port = 4660

        self._sdn_first_address = sdn_first_interface.ip
        self._sdn_netmask = int(sdn_first_interface.netmask)
        self._sdn_gateway: int | None = int(sdn_gateway) if sdn_gateway else None

        self._lmc_param = {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": self._destination_port,
            "source_port": self._source_port,
            "netmask_40g": self._sdn_netmask,
            "gateway_40g": self._sdn_gateway,
        }
        self._lmc_integrated_mode = "10G"
        self._lmc_channel_payload_length = 8192
        self._lmc_beam_payload_length = 8192

        self._beamformer_table = [[0, 0, 0, 0, 0, 0, 0]] * 48
        self._pps_delays = [0] * 16
        self._pps_delay_corrections = [0] * 16
        self._desired_static_delays = [0] * 512
        self._channeliser_rounding = [3] * 512
        self._csp_rounding = [3] * 384
        self._desired_preadu_levels = [0.0] * len(tile_fqdns) * TileData.ADC_CHANNELS
        self._base_mac_address = 0x620000000000 + int(self._sdn_first_address)

        self._antenna_info: dict[int, dict[str, Union[int, dict[str, float]]]] = {}

        self._antenna_mapping: dict[int, dict[str, int]] = {}
        self._cable_lengths: dict[int, float] = {}

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            max_workers=1,
            power=PowerState.UNKNOWN,
            fault=None,
            is_configured=None,
            adc_power=None,
        )

        self.self_check_manager = SpsStationSelfCheckManager(
            component_manager=self,
            logger=self.logger,
            tile_trls=list(self._tile_proxies.keys()),
            subrack_trls=list(self._subrack_proxies.keys()),
            daq_trl=self._daq_trl,
        )

        if antenna_config_uri:
            logger.debug("Retrieving antenna mapping.")
            self._get_mappings(antenna_config_uri)
        else:
            logger.debug("No antenna mapping provided, skipping")

    def _port_to_antenna_order(
        self: SpsStationComponentManager,
        antenna_mapping: dict[int, dict[str, int]],
        data: np.ndarray,
    ) -> np.ndarray:
        """
        Reorder bandpass data from port order to antenna order.

        Data is a 2D array expected in blocks ordered by TPM number and each block
            is expected in TPM port order.

        :param antenna_mapping: A mapping of antenna to tpm and ports.
            dict[ant_id: (tpm_id, tpm_x_port, tpm_y_port)]
        :param data: Full station data in TPM and port order.
        :returns: Full station data in Antenna order or `None` if the operation failed.
        """
        if antenna_mapping == {}:
            self.logger.warning(
                "No antenna mapping provided, returning data unmodified and exiting.",
            )
            return data
        ordered_data = np.zeros(data.shape)
        nof_antennas_per_tile = TileData.ANTENNA_COUNT
        skipped_antennas: bool = False
        try:
            for antenna in range(1, data.shape[0] + 1):  # 1 based antenna numbering
                tpm_number = int(antenna_mapping[antenna]["tpm"])
                tile_base_index = (tpm_number - 1) * nof_antennas_per_tile
                # So long as X and Y pols are always on adjacent ports this should work.
                tpm_port_number = antenna_mapping[antenna]["tpm_x_channel"]
                port_offset = int(tpm_port_number // 2)
                antenna_index = tile_base_index + port_offset
                ordered_data[antenna - 1, :] = data[antenna_index, :]
        except KeyError:
            # Generally we'll get here when we have fewer than 256 antennas.
            # Keep a note if we skipped some but don't flood the logs.
            skipped_antennas = True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(
                "Caught exception in "
                f"SpsStationComponentManager._port_to_antenna_order: {repr(e)}"
            )
        if skipped_antennas:
            self.logger.warning(
                "Data remapped but some antennas that were not found were skipped."
            )

        return ordered_data

    def _find_by_key(
        self: SpsStationComponentManager, data: dict, target: str
    ) -> Generator:
        """
        Traverse nested dictionary, yield next value for given target.

        :param data: generic nested dictionary to traverse through.
        :param target: key to find the next value of.

        :yields: the next value for given key.
        """
        for key, value in data.items():
            if key == target:
                yield value
            elif isinstance(value, dict):
                yield from self._find_by_key(value, target)

    def _get_mappings(
        self: SpsStationComponentManager,
        antenna_config_uri: list[str],
    ) -> None:
        """
        Get mappings from TelModel.

        :param antenna_config_uri: Repo and filepath for antenna mapping config
        """
        (
            antenna_mapping_uri,
            antenna_mapping_filepath,
        ) = antenna_config_uri

        try:
            tmdata = TMData([antenna_mapping_uri])
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.error(f"Unable to create TMData object, check uri. Error: {e}")
            return

        try:
            full_dict = tmdata[antenna_mapping_filepath].get_dict()
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.error(
                "Unable to create dictionary from imported TMData,"
                f"check uploaded TelModel data. Error: {e}"
            )
            return

        stations = list(self._find_by_key(full_dict, "stations"))
        if not stations:
            self.logger.error(
                f"Couldn't find station {self._station_id} in imported TMData."
            )
            return

        # Look through all the stations on this cluster, find antennas on this station.
        antennas = {}
        for station in stations:
            for _, station_config in station.items():
                if station_config["id"] == self._station_id:
                    antennas = next(self._find_by_key(station_config, "antennas"))

        if not antennas:
            self.logger.error(f"Couldn't find antennas on station {self._station_id}.")
            return

        try:
            for _, antenna_config in antennas.items():
                antenna_number: int = int(antenna_config["eep"])  # 1 based numbering
                tpm_number: int = int(antenna_config["tpm"].split("tpm")[-1])
                self._antenna_mapping[antenna_number] = {
                    "tpm": tpm_number,
                    "tpm_x_channel": antenna_config["tpm_x_channel"],
                    "tpm_y_channel": antenna_config["tpm_y_channel"],
                    "delay": antenna_config["delay"],
                }
                # Construct labels for bandpass data.
                self._antenna_info[antenna_number] = {
                    "station_id": self._station_id,
                    "tpm_id": tpm_number,
                    "antenna_location": antenna_config["location_offset"],
                }
        except KeyError as err:
            self.logger.error(
                "Antenna mapping dictionary structure not as expected, skipping, "
                f"err: {err}",
            )

        self.logger.debug("Successfully loaded antenna mapping.")

    def _update_static_delays(
        self: SpsStationComponentManager,
    ) -> list[float]:
        """
        Fetch static delays from the TelModel config.

        :returns: list of static delays in tile/channel order
        """
        tile_delays = [[0] * TileData.ADC_CHANNELS] * len(self._tile_proxies)
        for antenna_config in self._antenna_mapping.values():
            try:
                tile_logical_id = self._tile_id_mapping[f"{antenna_config['tpm']:02}"]
            except KeyError:
                self.logger.debug(
                    f"Mapping for tile {antenna_config['tpm']} present, "
                    "but device not deployed. Skipping."
                )
                continue
            tile_delays[tile_logical_id][
                antenna_config["tpm_x_channel"]
            ] = antenna_config["delay"]
            tile_delays[tile_logical_id][
                antenna_config["tpm_y_channel"]
            ] = antenna_config["delay"]
        for tile_no, tile in enumerate(tile_delays):
            self.logger.debug(f"Delays for tile logcial id {tile_no} = {tile}")
        return [
            channel_delay
            for channel_delays in tile_delays
            for channel_delay in channel_delays
        ]

    def _calculate_delays_per_tile(
        self: SpsStationComponentManager,
        antenna_order_delays: list[float],
    ) -> dict[int, list[float]]:
        beam_index = antenna_order_delays[0]

        # pre-allocate arrays for each of our tiles
        tile_delays: dict[int, list] = {}
        # element 0: beam index
        # odd elements: delay
        # even elements: delay rate
        for tile_proxy in self._tile_proxies.values():
            assert tile_proxy._proxy is not None
            tile_no = tile_proxy._proxy.logicalTileId
            tile_delays[tile_no] = [beam_index] + [0.0] * TileData.ADC_CHANNELS

        # remove element 0 from antenna_order_delays to aid in indexing,
        # we have used it now
        antenna_order_delays = antenna_order_delays[1:]

        # This array should now be of even length as it corresponds to pairs of
        # delay/delay rates
        assert len(antenna_order_delays) % 2 == 0

        # Loop through each pair of delay/delay rates
        for antenna_no in range(len(antenna_order_delays) // 2):
            delay = antenna_order_delays[antenna_no * 2]
            delay_rate = antenna_order_delays[antenna_no * 2 + 1]

            # Fetch which tpm this antenna belongs to
            tile_no = self._antenna_mapping[antenna_no + 1]["tpm"]
            channel = (
                self._antenna_mapping[antenna_no + 1]["tpm_y_channel"] // 2
            )  # y channel, even

            # We may have mapping for devices we don't have deployed
            if tile_no in tile_delays:
                tile_delays[tile_no][(channel) * 2 + 1] = delay
                tile_delays[tile_no][(channel) * 2 + 2] = delay_rate

        return tile_delays

    def start_communicating(self: SpsStationComponentManager) -> None:
        """Establish communication with the station components."""
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.start_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.start_communicating()
        if self._daq_proxy is not None:
            self._daq_proxy.start_communicating()

    def stop_communicating(self: SpsStationComponentManager) -> None:
        """Break off communication with the station components."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        for tile_proxy in self._tile_proxies.values():
            tile_proxy.stop_communicating()
        for subrack_proxy in self._subrack_proxies.values():
            subrack_proxy.stop_communicating()
        if self._daq_proxy is not None:
            self._daq_proxy.stop_communicating()

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
                if proxy_object._proxy is None:
                    raise ValueError(f"proxy for {fqdn} is None " "Unable to subscribe")
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
            except ValueError as e:
                self.logger.warning(
                    f"unable to form subscription for {fqdn} : {repr(e)}"
                )
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(
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
                self.logger.debug("handling change in adcpower")
                self._adc_power[logical_tile_id] = attribute_value.tolist()
                adc_powers: list[float] = []
                for _, adc_power in self._adc_power.items():
                    if adc_power is not None:
                        adc_powers += adc_power
                self._update_component_state(adc_power=adc_powers)
            case "statictimedelays":
                self._static_delays[logical_tile_id] = attribute_value.tolist()
            case "preadulevels":
                self.logger.debug("handling change in preaduLevels")
                # Note: Currently all we do is update the attribute value.
                self._preadu_levels[logical_tile_id] = attribute_value.tolist()
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
            self.submit_task(self.subscribe_to_attributes)
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

    @threadsafe
    def _daq_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        **state_change: Any,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._daq_power_state[fqdn] = power
                self._evaluate_power_state()
        if "xPolBandpass" in state_change:
            x_bandpass_data = state_change.get("xPolBandpass")
            if self._component_state_callback is not None:
                self._component_state_callback(xPolBandpass=x_bandpass_data)
        if "yPolBandpass" in state_change:
            y_bandpass_data = state_change.get("yPolBandpass")
            if self._component_state_callback is not None:
                self._component_state_callback(yPolBandpass=y_bandpass_data)
        if "dataReceivedResult" in state_change:
            data_received_result = state_change.get("dataReceivedResult")
            if self._component_state_callback is not None:
                self._component_state_callback(dataReceivedResult=data_received_result)

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
            elif fqdn in self._subrack_proxies:
                self._subrack_proxies[fqdn]._power_state = power_state
            elif fqdn in self._tile_proxies:
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
            task_callback(
                status=TaskStatus.REJECTED,
                result=(
                    ResultCode.REJECTED,
                    "MCCS has no control over subrack PDUs. "
                    "Unable to drive to the OFF state."
                    "Try Standby to turn off all TPMs.",
                ),
            )
        # The following is commented out because
        # MCCS has no control over subrack PDUs, meaning
        # the lowest drivable state for spsStation is STANDBY.
        # There is already a method Standby() that does this.
        # message: str = ""
        # if task_callback:
        #     task_callback(status=TaskStatus.IN_PROGRESS)
        # results = [proxy.off() for proxy in self._subrack_proxies.values()]
        # # Never mind tiles, turning off subracks suffices
        # # TODO: Here we need to monitor Tiles. This will eventually
        # # use the mechanism described in MCCS-945, but until that is implemented
        # # we might instead just poll these devices' longRunngCommandAttribute.
        # # For the moment, however, we just submit the subservient devices' commands
        # # for execution and forget about them.
        # if all(
        #     result in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]
        #     for (result, _) in results
        # ):
        #     task_status = TaskStatus.COMPLETED
        #     result_code = ResultCode.OK
        #     message = "Off Command Completed"
        # else:
        #     task_status = TaskStatus.FAILED
        #     result_code = ResultCode.FAILED
        #     message = "Off Command Failed"

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

        :return: a task status and response message
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
                message = "Standby command completed."
            else:
                self.logger.debug("Timeout in standby")
                task_status = TaskStatus.FAILED
                message = "Standby command timeout."
        else:
            task_status = TaskStatus.FAILED
            message = ""
        if task_callback:
            task_callback(status=task_status, result=(result_code, message))

    def on(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _on method.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
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
        message: str = ""
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

        if result_code == ResultCode.OK:
            self.logger.debug("Setting tile source IPs before initialisation")
            result_code = self._set_tile_source_ips(task_callback, task_abort_event)

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
            self.logger.debug("Waiting for ARP table")
            result_code = self._wait_for_arp_table(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Checking synchronisation")
            result_code = self._check_station_synchronisation(
                task_callback, task_abort_event
            )

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            self.logger.debug("End initialisation")
            task_status = TaskStatus.COMPLETED
            message = "On Command Completed"
        else:
            self.logger.error("Initialisation failed")
            task_status = TaskStatus.FAILED
            message = "On Command failed"
        if task_callback:
            task_callback(status=task_status, result=(result_code, message))

    def initialise(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _initialise method.

        This method returns immediately after it submitted
        `self._initialise` for execution.

        :param task_callback: Update task state, defaults to None
        :return: a task status and response message
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
        message: str = ""
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
            self.logger.debug("Setting tile source IPs before initialisation")
            result_code = self._set_tile_source_ips(task_callback, task_abort_event)

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
            self.logger.debug("Waiting for ARP table")
            result_code = self._wait_for_arp_table(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Checking synchronisation")
            result_code = self._check_station_synchronisation(
                task_callback, task_abort_event
            )

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            self.logger.debug("End initialisation")
            task_status = TaskStatus.COMPLETED
            message = "Initialisation Complete"
        else:
            self.logger.error("Initialisation failed")
            task_status = TaskStatus.FAILED
            message = "Initialisation Failed"
        if task_callback:
            task_callback(status=task_status, result=(result_code, message))

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

        return ResultCode.FAILED

    @check_communicating
    def _set_tile_source_ips(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Set source IPs on tiles before initialising.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        for tile_id, tile_proxy in enumerate(list(self._tile_proxies.values())):
            tile = tile_proxy._proxy
            if tile is None:
                self.logger.error(f"Tile {tile_id} proxy not formed.")
                return ResultCode.FAILED
            src_ip1 = str(self._sdn_first_address + 2 * tile_id)
            src_ip2 = str(self._sdn_first_address + 2 * tile_id + 1)
            tile.srcip40gfpga1 = src_ip1
            tile.srcip40gfpga2 = src_ip2
        return ResultCode.OK

    @check_communicating
    def _wait_for_arp_table(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Wait for ARP tables on tiles before continuing.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        timeout = 30
        tick = 2
        for tile_trl, tile_proxy in self._tile_proxies.items():
            last_time = time.time() + timeout
            tile = tile_proxy._proxy
            if tile is None:
                self.logger.error(f"{tile_trl} proxy not set up.")
                return ResultCode.FAILED
            while time.time() < last_time:
                self.logger.debug(f"Waiting on {tile_trl} ARP table.")
                if tile.GetArpTable() != '{"0": [], "1": []}':
                    break
                time.sleep(tick)
            if tile.GetArpTable() == '{"0": [], "1": []}':
                self.logger.error(f"Failed to populate ARP table of {tile_trl}")
                return ResultCode.FAILED
            self.logger.debug(f"Got ARP table for {tile_trl}")
        return ResultCode.OK

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
            i1 = (
                tile_no * TileData.ADC_CHANNELS
            )  # indexes for parameters for individual signals
            i2 = i1 + TileData.ADC_CHANNELS
            self.logger.debug(f"Initialising tile {tile_no}: {tile.name()}")
            tile.preaduLevels = self._desired_preadu_levels[i1:i2]
            tile.staticTimeDelays = self._desired_static_delays[i1:i2]
            tile.channeliserRounding = self._channeliser_rounding
            tile.cspRounding = self._csp_rounding
            tile.ppsDelayCorrection = self._pps_delay_corrections[tile_no]
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
        # Configure 40G ports.
        # Each TPM has 2 IP addresses starting at the provided address
        # Each TPM 40G port point to the corresponding
        # Last TPM uses CSP ingest address and port
        #
        # ip_head, ip_tail = self._fortygb_network_address.rsplit(".", maxsplit=1)
        # base_ip3 = int(ip_tail)
        last_tile = len(tiles) - 1
        tile = 0
        num_cores = 2
        for proxy in tiles:
            assert proxy._proxy is not None
            dst_ip1 = str(self._sdn_first_address + 2 * tile + 2)
            dst_ip2 = str(self._sdn_first_address + 2 * tile + 3)
            dst_ip_list = [dst_ip1, dst_ip2]
            dst_port_1 = self._destination_port
            dst_port_2 = dst_port_1 + 2

            for core in range(num_cores):
                dst_ip = dst_ip_list[core]

                if tile == last_tile:
                    dst_ip = self._csp_ingest_address
                    dst_port_1 = self._csp_ingest_port
                    dst_port_2 = dst_port_1

                # ARP Table Entry 0 of each 40G core specifies destination
                # for station beam packets
                proxy._proxy.Configure40GCore(
                    json.dumps(
                        {
                            "core_id": core,
                            "arp_table_entry": 0,
                            "source_port": self._source_port,
                            "destination_ip": dst_ip,
                            "destination_port": dst_port_1,
                            "rx_port_filter": dst_port_1,
                            "netmask": self._sdn_netmask,
                            "gateway_ip": self._sdn_gateway,
                        }
                    )
                )
                # Also configure entry 2 with the same settings
                # Required for operation with single 40G connection to each TPM
                # With two connections, each core uses arp table entry 0
                # for station beam transmission to the next tile in the chain
                # and lastly to CSP.
                # Two FPGAs = Two Simultaneous Daisy chains
                # (a chain of FPGA1s and a chain of FPGA2s)
                # With one 40G connection, Master FPGA uses arp table entry 0,
                # Slave FPGA uses arp table entry 2 to achieve the same functionality
                # but with a single core.
                proxy._proxy.Configure40GCore(
                    json.dumps(
                        {
                            "core_id": core,
                            "arp_table_entry": 2,
                            "source_port": self._source_port,
                            "destination_ip": dst_ip,
                            "destination_port": dst_port_2,
                            "netmask": self._sdn_netmask,
                            "gateway_ip": self._sdn_gateway,
                        }
                    )
                )
                # Set RX port filter for RX channel 1
                # Required for operation with single 40G connection to each TPM
                proxy._proxy.Configure40GCore(
                    json.dumps(
                        {
                            "core_id": core,
                            "arp_table_entry": 1,
                            "rx_port_filter": dst_port_1 + 2,
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
                        "netmask_40g": self._sdn_netmask,
                        "gateway_40g": self._sdn_gateway,
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

    def self_check(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _self_check method.

        This method returns immediately after it submitted
        `self._self_check` for execution.

        :param task_callback: Update task state, defaults to None
        :return: a task status and response message
        """
        return self.submit_task(self._self_check, task_callback=task_callback)

    def _self_check(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        test_results = self.self_check_manager.run_tests()

        if all(
            test_result in [TestResult.PASSED, TestResult.NOT_RUN]
            for test_result in test_results
        ):
            if task_callback is not None:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result=(ResultCode.OK, "Tests completed OK."),
                )
            return
        if task_callback is not None:
            task_callback(
                status=TaskStatus.FAILED,
                result=(
                    ResultCode.FAILED,
                    "Not all tests passed or skipped, check report.",
                ),
            )

    def run_test(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        count: Optional[int] = 1,
        test_name: str,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _run_test method.

        This method returns immediately after it submitted
        `self._run_test` for execution.

        :param task_callback: Update task state, defaults to None
        :param count: how many times to run the test, default is 1.
        :param test_name: which test to run.

        :return: a task status and response message
        """
        return self.submit_task(
            self._run_test, args=[count, test_name], task_callback=task_callback
        )

    def _run_test(
        self: SpsStationComponentManager,
        count: int,
        test_name: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        test_results = self.self_check_manager.run_test(
            test_name=test_name, count=count
        )

        if all(test_result == TestResult.PASSED for test_result in test_results):
            if task_callback is not None:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result=(ResultCode.OK, "Tests completed OK."),
                )
            return
        if all(test_result == TestResult.NOT_RUN for test_result in test_results):
            if task_callback is not None:
                task_callback(
                    status=TaskStatus.REJECTED,
                    result=(
                        ResultCode.REJECTED,
                        "Tests requirements not met, check logs.",
                    ),
                )
            return
        if task_callback is not None:
            task_callback(
                status=TaskStatus.FAILED,
                result=(
                    ResultCode.FAILED,
                    "Not all tests passed, check report.",
                ),
            )

    # ----------
    # Attributes
    # ----------
    @property
    def pps_delays(self: SpsStationComponentManager) -> list[int]:
        """
        Get PPS delay.

        Array of one value per tile. Returns the PPS delay,
        Values are internally rounded to 1.25 ns steps

        :return: Array of one value per tile, in nanoseconds
        """
        for i, proxy in enumerate(self._tile_proxies.values()):
            assert proxy._proxy is not None  # for the type checker
            self._pps_delays[i] = proxy._proxy.ppsDelay
        return copy.deepcopy(self._pps_delays)

    @property
    def pps_delay_corrections(self: SpsStationComponentManager) -> list[int]:
        """
        Get the PPS delay correction.

        :return: Array of pps delay corrections, one value per tile, in nanoseconds
        """
        for i, proxy in enumerate(self._tile_proxies.values()):
            assert proxy._proxy is not None  # for the type checker
            self._pps_delay_corrections[i] = proxy._proxy.ppsDelayCorrection

        return copy.deepcopy(self._pps_delay_corrections)

    @pps_delay_corrections.setter
    def pps_delay_corrections(
        self: SpsStationComponentManager, delays: list[int]
    ) -> None:
        """
        Set PPS delay correction.

        This will be applied during the following Initialisation.

        :param delays: Array of one value per tile, in nanoseconds.
            Values are internally rounded to 1.25 ns steps
        """
        for i, proxy in enumerate(self._tile_proxies.values()):
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.ppsDelayCorrection = delays[i]

    @property
    def static_delays(self: SpsStationComponentManager) -> list[float]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        static_delays: list[float] = []
        for _, static_delay in self._static_delays.items():
            if static_delay is not None:
                static_delays += static_delay
        return static_delays

    @static_delays.setter
    def static_delays(self: SpsStationComponentManager, delays: list[int]) -> None:
        """
        Set static time delay correction.

        :param delays: Array of one value per antenna/polarization (32 per tile)
        """
        self._desired_static_delays = copy.deepcopy(delays)
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            start_entry = (proxy._proxy.logicalTileId) * TileData.ADC_CHANNELS
            end_entry = (proxy._proxy.logicalTileId + 1) * TileData.ADC_CHANNELS
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.staticTimeDelays = delays[start_entry:end_entry]

    @property
    def channeliser_rounding(self: SpsStationComponentManager) -> np.ndarray:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values for each Tile, one per channel.
        """
        channeliser_roundings: np.ndarray = np.zeros([16, 512])

        for tile_idx, proxy in enumerate(self._tile_proxies.values()):
            assert proxy._proxy is not None  # for the type checker
            try:
                channeliser_roundings[tile_idx, :] = proxy._proxy.channeliserRounding
            except ValueError as e:
                self.logger.error(
                    f"unable to update array with {proxy._name} "
                    f"channeliserRounding attribute: {repr(e)}"
                )
        return channeliser_roundings

    @property
    def csp_rounding(self: SpsStationComponentManager) -> list[int] | None:
        """
        CSP formatter rounding.

        Rounding from 16 to 8 bits in final stage of the
        station beamformer, before sending data to CSP.
        Array of (up to) 384 values, one for each logical channel.
        Range 0 to 7, as number of discarded LS bits.

        :return: CSP formatter rounding for each logical channel.
        """
        proxy = list(self._tile_proxies.values())[-1]
        assert proxy._proxy is not None  # for the type checker
        return proxy._proxy.cspRounding

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
        preadu_levels_concatenated: list[float] = []
        for preadu_levels in self._preadu_levels.values():
            if preadu_levels is not None:
                preadu_levels_concatenated += preadu_levels
        return preadu_levels_concatenated

    @preadu_levels.setter
    def preadu_levels(self: SpsStationComponentManager, levels: list[float]) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: ttenuator level of preADU channels, one per input channel, in dB
        """
        self._desired_preadu_levels = copy.deepcopy(levels)
        i = 0
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                proxy._proxy.preaduLevels = levels[i : i + TileData.ADC_CHANNELS]
            else:
                self.logger.error(
                    f"Not setting preadu levels on {proxy._name}"
                    "TileProgramming state not `Initialised` or `Synchronised`."
                )
            i = i + TileData.ADC_CHANNELS

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
        return str(self._sdn_first_address)

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
            rms_values = rms_values + list(proxy.adc_power())
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
        fpga_1_temperatures = list(
            tile._proxy is not None and tile._proxy.fpga1Temperature
            for tile in self._tile_proxies.values()
        )
        fpga_2_temperatures = list(
            tile._proxy is not None and tile._proxy.fpga2Temperature
            for tile in self._tile_proxies.values()
        )
        fpga_temperatures = fpga_1_temperatures + fpga_2_temperatures
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

    @property
    def test_logs(self: SpsStationComponentManager) -> str:
        """
        Get logs of most recently run self-check test set.

        :return: logs of most recently run self-check test set.
        """
        return self.self_check_manager._test_logs

    @property
    def test_report(self: SpsStationComponentManager) -> str:
        """
        Get report of most recently run self-check test set.

        :return: report of most recently run self-check test set.
        """
        return self.self_check_manager._test_report

    @property
    def test_list(self: SpsStationComponentManager) -> list[str]:
        """
        Get list of self-check tests available.

        :return: list of self-check tests available.
        """
        return self.self_check_manager._tpm_test_names

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
        self._lmc_param["netmask_40g"] = self._sdn_netmask
        self._lmc_param["gateway_40g"] = self._sdn_gateway
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
                "netmask_40g": self._sdn_netmask,
                "gateway_40g": self._sdn_gateway,
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

        (fqdn, proxy) = list(self._tile_proxies.items())[-1]
        assert proxy._proxy is not None  # for the type checker
        if self._tile_power_states[fqdn] != PowerState.ON:
            return  # Do not access an unprogrammed TPM

        num_cores = 2
        last_tile = len(self._tile_proxies) - 1
        src_ip1 = str(self._sdn_first_address + 2 * last_tile)
        src_ip2 = str(self._sdn_first_address + 2 * last_tile + 1)
        dst_port = self._csp_ingest_port
        src_ip_list = [src_ip1, src_ip2]
        src_mac = self._base_mac_address + 2 * last_tile
        self.logger.debug(f"Tile {last_tile}: 40G#1: {src_ip1} -> {dst_ip}")
        self.logger.debug(f"Tile {last_tile}: 40G#2: {src_ip2} -> {dst_ip}")
        for core in range(num_cores):
            src_ip = src_ip_list[core]
            proxy._proxy.Configure40GCore(
                json.dumps(
                    {
                        "core_id": core,
                        "arp_table_entry": 0,
                        "source_ip": src_ip,
                        "source_mac": src_mac + core,
                        "source_port": self._source_port,
                        "destination_ip": dst_ip,
                        "destination_port": dst_port,
                        "rx_port_filter": dst_port,
                        "netmask": self._sdn_netmask,
                        "gateway_ip": self._sdn_gateway,
                    }
                )
            )
            # Also configure entry 2 with the same settings
            # Required for operation with single 40G connection to each TPM
            # With two connections, each core uses arp table entry 0
            # for station beam transmission to the next tile in the chain
            # and lastly to CSP.
            # Two FPGAs = Two Simultaneous Daisy chains
            # (a chain of FPGA1s and a chain of FPGA2s)
            # With one 40G connection, Master FPGA uses arp table entry 0,
            # Slave FPGA uses arp table entry 2 to achieve the same functionality
            # but with a single core.
            proxy._proxy.Configure40GCore(
                json.dumps(
                    {
                        "core_id": core,
                        "arp_table_entry": 2,
                        "source_ip": src_ip,
                        "source_mac": src_mac + core,
                        "source_port": self._source_port,
                        "destination_ip": dst_ip,
                        "destination_port": dst_port,
                        "netmask": self._sdn_netmask,
                        "gateway_ip": self._sdn_gateway,
                    }
                )
            )
            # Set RX port filter for RX channel 1
            # Required for operation with single 40G connection to each TPM
            proxy._proxy.Configure40GCore(
                json.dumps(
                    {
                        "core_id": core,
                        "arp_table_entry": 1,
                        "rx_port_filter": dst_port + 2,
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
        tile_delays = self._calculate_delays_per_tile(delay_list)

        for tile_proxy in self._tile_proxies.values():
            assert tile_proxy._proxy is not None

            # TODO: Extracting tile id from TRL of the form "low-mccs/tile/s8-1-tpm01"
            # But this code should not be depending on assumptions about TRL structure
            tile_no = int(tile_proxy._proxy.dev_name().split("-")[-1][3:])
            delays_for_tile = tile_delays[tile_no]
            tile_proxy._proxy.LoadPointingDelays(delays_for_tile)

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
        future_results = [
            dev._proxy.command_inout(
                "StopDataTransmission",
                green_mode=tango.GreenMode.Futures,
                wait=False,
            )
            for dev in self._tile_proxies.values()
            if dev._proxy is not None
        ]
        futures.wait(future_results)
        if len(future_results) != len(self._tile_proxies):
            self.logger.warning(
                "StopDataTransmission how not been called on all Tiles."
            )
        self.logger.debug(
            "Tiles response from StopDataTransmission: "
            f" {[f.result() for f in future_results]}"
        )

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

        :return: a task status and response message
        """
        params = json.loads(argin)
        start_time = params.get("start_time", None)
        delay = params.get("delay", 0)

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

        if start_time is None:
            start_time = Time(int(time.time() + 2), format="unix").isot + "Z"
        else:
            delay = 0

        parameter_list = {"start_time": start_time, "delay": delay}
        json_argument = json.dumps(parameter_list)
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            tile._proxy.StartAcquisition(json_argument)

        if task_callback:
            if success:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result=(ResultCode.OK, "Start acquisition has completed"),
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED,
                    result=(ResultCode.FAILED, "Start acquisition task failed"),
                )
            return

    def acquire_data_for_calibration(
        self: SpsStationComponentManager,
        channel: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the acquire data for calibration method.

        This method returns immediately after it submitted
        `self._acquire_data_for_calibration` for execution.

        :param channel: channel to calibrate for
        :param task_callback: Update task state, defaults to None

        :return: a task staus and response message
        """
        if channel < 0 or channel > 510:
            self.logger.error(f"Invalid channel{channel}")
            return (TaskStatus.REJECTED, "Invalid channel")

        return self.submit_task(
            self._acquire_data_for_calibration,
            args=[channel],
            task_callback=task_callback,
        )

    @check_communicating
    def _acquire_data_for_calibration(
        self: SpsStationComponentManager,
        channel: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Acquire data for calibration.

        :param channel: channel to calibrate for
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        daq_mode = "INTEGRATED_CHANNEL_DATA"
        data_send_mode = "channel"
        # Verify all tiles are acquiring data
        for tile in self._tile_proxies.values():
            assert tile._proxy is not None  # for the type checker
            if not tile._proxy.tileProgrammingState == "Synchronised":
                if task_callback:
                    task_callback(
                        status=TaskStatus.FAILED,
                        result=(
                            ResultCode.FAILED,
                            "AcquireDataForCalibration failed. Tiles not synchronised.",
                        ),
                    )
                return

        # Get DAQ running with correlator
        assert self._daq_proxy is not None
        assert self._daq_proxy._proxy is not None
        daq_status = json.loads(self._daq_proxy._proxy.DaqStatus())
        if all(
            status_list[0] != daq_mode
            for status_list in daq_status["Running Consumers"]
        ):
            if len(daq_status["Running Consumers"]) > 0:
                rc, _ = self._daq_proxy._proxy.StopDaq()
                if rc != ResultCode.OK:
                    if task_callback:
                        task_callback(
                            status=TaskStatus.FAILED,
                            result=(
                                ResultCode.FAILED,
                                "AcquireDataForCalibration failed. Failed to stop daq.",
                            ),
                        )
                    return
            self._daq_proxy._proxy.Start(json.dumps({"modes_to_start": daq_mode}))
            max_tries = 10
            for _ in range(max_tries):
                daq_status = json.loads(self._daq_proxy._proxy.DaqStatus())
                if any(
                    status_list[0] == daq_mode
                    for status_list in daq_status["Running Consumers"]
                ):
                    break
                time.sleep(0.5)
            if all(
                status_list[0] != daq_mode
                for status_list in daq_status["Running Consumers"]
            ):
                if task_callback:
                    task_callback(
                        status=TaskStatus.FAILED,
                        result=(
                            ResultCode.FAILED,
                            "AcquireDataForCalibration failed. Failed to start daq.",
                        ),
                    )
                return

        # Send data from tpms
        self.send_data_samples(
            json.dumps(
                {
                    "data_type": data_send_mode,
                    #"first_channel": channel,
                    #"last_channel": channel,
                }
            )
        )

    @check_communicating
    def set_channeliser_rounding(
        self: SpsStationComponentManager,
        channeliser_rounding: np.ndarray,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the channeliserRounding in all Tiles.

        :param channeliser_rounding: the number of LS bits dropped in
            each channeliser frequency channel.
        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._set_channeliser_rounding,
            args=[channeliser_rounding],
            task_callback=task_callback,
        )

    def _set_channeliser_rounding(
        self: SpsStationComponentManager,
        channeliser_rounding: np.ndarray,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Set the channeliserRounding in all Tiles.

        :param channeliser_rounding: the number of LS bits dropped in
            each channeliser frequency channel.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        result_code = ResultCode.OK
        message = ""
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            if proxy._proxy.tileProgrammingState in ["Initialised", "Synchronised"]:
                self.logger.debug(f"Writing truncation in {proxy._proxy.name()}")
                try:
                    proxy._proxy.channeliserRounding = channeliser_rounding
                except tango.DevFailed:
                    self.logger.warning(
                        f"Failed to load truncation for {proxy._proxy.name()}"
                    )
                    message = "Failed to set channeliserRounding for 1 or more Tiles."
                    result_code = ResultCode.FAILED
            else:
                message += (
                    "unable to set channeliserRounding for 1 or more tiles. "
                    "Tile not Initialised. "
                )
                result_code = ResultCode.FAILED

        if not message:
            message = "channeliserRounding loaded into all Tiles successfully."

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(result_code, message),
            )

    def trigger_adc_equalisation(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the trigger adc equalisation method.

        This method returns immediately after it submitted
        `self._trigger_adc_equalisation` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._trigger_adc_equalisation,
            task_callback=task_callback,
        )

    @check_communicating
    def _trigger_adc_equalisation(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Equalise adc using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        tpms = self._tile_proxies.values()
        num_samples = 20
        target_adc = 17

        adc_data = np.empty([num_samples, 32 * len(tpms)])
        for i in range(num_samples):
            time.sleep(1)
            adc_data[i] = self.adc_power()

        # calculate difference in dB between current and target values
        adc_medians = np.median(adc_data, axis=0)

        # adc deltas
        adc_deltas = 20 * np.log10(adc_medians / target_adc)

        # calculate ideal attenuation
        preadu_levels = np.concatenate([t.preadu_levels() for t in tpms])
        desired_levels = preadu_levels + adc_deltas

        # quantise and clip to valid range
        sanitised_levels = (desired_levels * 4).round().clip(0, 127) / 4

        # apply new preADU levels to the station
        self.preadu_levels = sanitised_levels

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "ADC equalisation complete."),
            )

    def describe_test(self, test_name: str) -> str:
        """
        Return the doc string of a given self-check test.

        :param test_name: name of the test.

        :returns: the doc string of a given self-check test.
        """
        docs = self.self_check_manager._tpm_tests[test_name].__doc__
        if docs is None:
            return f"{test_name} appears to have no description."
        return docs
