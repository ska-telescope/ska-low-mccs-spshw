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
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from queue import Empty
from statistics import mean
from typing import Any, Callable, Optional, Sequence, Union, cast

import numpy as np
import tango
from astropy.time import Time  # type: ignore
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    TaskStatus,
)
from ska_low_mccs_common import EventSerialiser
from ska_low_mccs_common.communication_manager import CommunicationManager
from ska_low_mccs_common.component import (
    CompositeCommandResultEvaluator,
    DeviceComponentManager,
    MccsBaseComponentManager,
    MccsCommandProxy,
    MccsCompositeCommandProxy,
)
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from ska_low_mccs_common.utils import UniqueQueue, lock_power_state, threadsafe
from ska_tango_base.base import check_communicating
from ska_tango_base.executor import TaskExecutorComponentManager
from ska_telmodel.data import TMData  # type: ignore

from ska_low_mccs_spshw.tile.tpm_status import TpmStatus

from ..tile.tile_data import TileData
from .station_self_check_manager import SpsStationSelfCheckManager
from .tests.base_tpm_test import TestResult

__all__ = ["SpsStationComponentManager"]


def retry_command_on_exception(
    device_proxy: tango.Deviceproxy,
    command_name: str,
    command_arguments: Any = None,
    timeout: int = 30,
) -> Any:
    """
    Retry command when DevFailed exception raised.

    NOTE: By default this command will retry the command up to 30 seconds

    :param device_proxy: A 'tango.DeviceProxy' to the backend device.
    :param command_name: A string containing the command name.
    :param command_arguments: The arguments to pass to command.
        defaults to None
    :param timeout: A max time in seconds before we give up trying

    :returns: The response from the command.

    :raises TimeoutError: if the command did not execute without exception in
        timeout period.
    """
    assert device_proxy.adminMode in [
        AdminMode.ONLINE,
        AdminMode.ENGINEERING,
    ], "Unable to execute command on a OFFLINE device."
    tick = 2
    terminate_time = time.time() + timeout
    while time.time() < terminate_time:
        try:
            if command_arguments is None:
                return getattr(device_proxy, command_name)()
            return getattr(device_proxy, command_name)(command_arguments)
        except tango.DevFailed as df:
            print(
                f"{device_proxy.dev_name()} failed to communicate with backend.\n"
                f"{df}"
            )
            time.sleep(tick)
    raise TimeoutError(
        f"Unable to execute command {command_name} on {device_proxy.dev_name()}"
    )


class _TileProxy(DeviceComponentManager):
    """A proxy to a tile, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _TileProxy,
        fqdn: str,
        station_id: int,
        logical_tile_id: int,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        attribute_changed_callback: Callable,
        event_serialiser: Optional[EventSerialiser] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param station_id: the id of the station to which this station
            is to be assigned
        :param logical_tile_id: the id of the tile within this station.
        :param logger: the logger to be used by this object.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param attribute_changed_callback: callback to be called when
            desired attributes change.
        :param event_serialiser: the event serialiser to be used by this object
        """
        self._station_id = station_id
        self._logical_tile_id = logical_tile_id
        self._attribute_changed_callback = attribute_changed_callback
        super().__init__(
            fqdn,
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            event_serialiser=event_serialiser,
        )

    def get_change_event_callbacks(self) -> dict[str, Callable]:
        return {
            **super().get_change_event_callbacks(),
            "adcPower": self._on_attribute_change,
            "staticTimeDelays": self._on_attribute_change,
            "preaduLevels": self._on_attribute_change,
            "ppsDelay": self._on_attribute_change,
            "tileProgrammingState": self._on_attribute_change,
            "beamformerTable": self._on_attribute_change,
            "beamformerRegions": self._on_attribute_change,
        }

    def _on_attribute_change(self, *args: Any, **kwargs: Any) -> None:
        self._attribute_changed_callback(self._logical_tile_id, *args, **kwargs)

    def _device_state_changed(
        self: _TileProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            try:
                __tile_id = self._proxy.logicalTileId
            except tango.DevFailed:
                __tile_id = None
            try:
                __station_id = self._proxy.stationId
            except tango.DevFailed:
                __station_id = None
            if __station_id is not None and __station_id != self._station_id:
                self.logger.warning(
                    f"Expected {self._proxy.dev_name()} stationId "
                    f"{self._station_id}, tile has stationId {__station_id}. "
                    "Is this a configuration issue?"
                )
            if __tile_id is not None and __tile_id != self._logical_tile_id:
                self.logger.warning(
                    f"Expected {self._proxy.dev_name()} logicalTileId "
                    f"{self._logical_tile_id}, tile has logicalTileID "
                    f"{__tile_id}. "
                    "Is this a configuration issue?"
                )
        super()._device_state_changed(event_name, event_value, event_quality)

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


class _LMCDaqProxy(DeviceComponentManager):
    """A proxy to a LMC DAQ, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _LMCDaqProxy,
        fqdn: str,
        station_id: int,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        event_serialiser: Optional[EventSerialiser] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param station_id: the id of the station to which this daq
            is to be assigned
        :param logger: the logger to be used by this object.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param event_serialiser: the event serialiser to be used by this object
        """
        self._station_id = station_id
        super().__init__(
            fqdn,
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            event_serialiser=event_serialiser,
        )

    def get_change_event_callbacks(self) -> dict[str, Callable]:
        return {
            **super().get_change_event_callbacks(),
            "dataReceivedResult": self._daq_data_callback,
        }

    def _configure_station_id(self: _LMCDaqProxy) -> None:
        assert self._proxy is not None
        cfg = json.dumps({"station_id": self._station_id})
        self._proxy.Configure(cfg)

    def _device_state_changed(
        self: _LMCDaqProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if (
            self._communication_state == CommunicationStatus.ESTABLISHED
            and event_value == tango.DevState.ON
        ):
            assert self._proxy is not None  # for the type checker
            self._configure_station_id()
        super()._device_state_changed(event_name, event_value, event_quality)

    def _daq_data_callback(
        self: _LMCDaqProxy,
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
            if attribute_name.lower() == "datareceivedresult":
                self.logger.debug("Processing change event for dataReceivedResult")
                self._component_state_callback(dataReceivedResult=attribute_data)
            else:
                self.logger.error(
                    f"Got unexpected change event for: {attribute_name} "
                    "in DaqProxy._daq_data_callback."
                )


class _BandpassDaqProxy(DeviceComponentManager):
    """A proxy to a Bandpass DAQ, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _BandpassDaqProxy,
        fqdn: str,
        station_id: int,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        event_serialiser: Optional[EventSerialiser] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param station_id: the id of the station to which this daq
            is to be assigned
        :param logger: the logger to be used by this object.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param event_serialiser: the event serialiser to be used by this object
        """
        self._station_id = station_id
        super().__init__(
            fqdn,
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            event_serialiser=event_serialiser,
        )

    def get_change_event_callbacks(self) -> dict[str, Callable]:
        return {
            **super().get_change_event_callbacks(),
            "xPolBandpass": self._daq_data_callback,
            "yPolBandpass": self._daq_data_callback,
        }

    def _configure_station_id(self: _BandpassDaqProxy) -> None:
        assert self._proxy is not None
        cfg = json.dumps({"station_id": self._station_id})
        self._proxy.Configure(cfg)

    def _device_state_changed(
        self: _BandpassDaqProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if (
            self._communication_state == CommunicationStatus.ESTABLISHED
            and event_value == tango.DevState.ON
        ):
            assert self._proxy is not None  # for the type checker
            self._configure_station_id()
        super()._device_state_changed(event_name, event_value, event_quality)

    def _daq_data_callback(
        self: _BandpassDaqProxy,
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
        lmc_daq_trl: str,
        bandpass_daq_trl: str,
        sdn_first_interface: ipaddress.IPv4Interface,
        sdn_gateway: ipaddress.IPv4Address | None,
        csp_ingest_ip: ipaddress.IPv4Address | None,
        channeliser_rounding: list[int] | None,
        csp_rounding: int,
        antenna_config_uri: Optional[list[str]],
        start_bandpasses_in_initialise: bool,
        bandpass_integration_time: float,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        tile_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        subrack_health_changed_callback: Callable[[str, Optional[HealthState]], None],
        event_serialiser: Optional[EventSerialiser] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param station_id: the id of this station
        :param subrack_fqdns: FQDNs of the Tango devices which manage this
            station's subracks
        :param tile_fqdns: FQDNs of the Tango devices which manage this
            station's TPMs
        :param lmc_daq_trl: The TRL of this Station's DAQ Receiver for general LMC use.
            Could be empty if the device property is not set.
        :param bandpass_daq_trl: The TRL of this Station's DAQ Receiver for bandpasses.
            Could be empty if the device property is not set.
        :param sdn_first_interface: CIDR-style IP address with mask,
            for the first interface in the block assigned for science data
            For example, "10.130.0.1/25" means
            "address 10.130.0.1 on network 10.130.0.0/25".
        :param sdn_gateway: IP address of the SDN gateway,
            or None if the network has no gateway.
        :param csp_ingest_ip: IP address of the CSP ingest for this station.
        :param channeliser_rounding: The channeliser rounding to use for this station.
        :param csp_rounding: The CSP rounding to use for this station.
            An integer value between 0 and 7.
            Currently the underlying library accepts a list of 384 values
            (one for each coarse channel sent to CSP)
            but it actually only uses the first one of these.
            Until it is updated to support a full list,
            we restrict this interface to one integer.
        :param antenna_config_uri: location of the antenna mapping file
        :param start_bandpasses_in_initialise: whether to start bandpasses
            in initialise.
        :param bandpass_integration_time: the integration time for channelised data
            capture started in initialise.
        :param logger: the logger to be used by this object.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param tile_health_changed_callback: callback to be
            called when a tile's health changed
        :param subrack_health_changed_callback: callback to be
            called when a subrack's health changed
        :param event_serialiser: the event serialiser to be used by this object.
        """
        self._event_serialiser = event_serialiser
        self._lmc_daq_proxy: Optional[_LMCDaqProxy] = None
        self._bandpass_daq_proxy: Optional[_BandpassDaqProxy] = None
        self._bandpass_integration_time = bandpass_integration_time
        self._station_id = station_id
        self._lmc_daq_trl = lmc_daq_trl
        self._bandpass_daq_trl = bandpass_daq_trl
        self._start_bandpasses_in_initialise = start_bandpasses_in_initialise
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
        self._number_of_tiles = len(tile_fqdns)
        self._adc_power: dict[int, Optional[list[float]]] = {}
        self._static_delays: dict[int, Optional[list[float]]] = {}
        self._preadu_levels: dict[int, Optional[list[float]]] = {}
        for logical_tile_id in range(self._number_of_tiles):
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
                functools.partial(self._device_communication_state_changed, tile_fqdn),
                functools.partial(self._tile_state_changed, tile_fqdn),
                self._on_tile_attribute_change,
                event_serialiser=self._event_serialiser,
            )
            # TODO: Extracting tile id from TRL of the form "low-mccs/tile/s8-1-tpm01"
            # But this code should not be relying on assumptions about TRL structure
            self._tile_id_mapping[tile_fqdn.split("-")[-1][3:]] = logical_tile_id

        self._subrack_proxies = {
            subrack_fqdn: DeviceComponentManager(
                subrack_fqdn,
                logger,
                functools.partial(
                    self._device_communication_state_changed, subrack_fqdn
                ),
                functools.partial(self._subrack_state_changed, subrack_fqdn),
                event_serialiser=self._event_serialiser,
            )
            for subrack_id, subrack_fqdn in enumerate(subrack_fqdns)
        }
        if self._lmc_daq_trl:
            # TODO: Detect a bad daq trl.
            self._lmc_daq_proxy = _LMCDaqProxy(
                self._lmc_daq_trl,
                station_id,
                logger,
                functools.partial(
                    self._device_communication_state_changed, self._lmc_daq_trl
                ),
                functools.partial(self._lmc_daq_state_changed, self._lmc_daq_trl),
                event_serialiser=self._event_serialiser,
            )
            self._lmc_daq_power_state = {lmc_daq_trl: PowerState.UNKNOWN}
        if self._bandpass_daq_trl:
            # TODO: Detect a bad daq trl.
            self._bandpass_daq_proxy = _BandpassDaqProxy(
                self._bandpass_daq_trl,
                station_id,
                logger,
                functools.partial(
                    self._device_communication_state_changed, self._bandpass_daq_trl
                ),
                functools.partial(
                    self._bandpass_daq_state_changed, self._bandpass_daq_trl
                ),
                event_serialiser=self._event_serialiser,
            )
            self._bandpass_daq_power_state = {bandpass_daq_trl: PowerState.UNKNOWN}
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
        self._csp_spead_format = "SKA"
        self._global_reference_time = ""

        # TODO: this needs to be scaled,
        self.tile_attributes_to_subscribe = [
            "adcPower",
            "staticTimeDelays",
            "preaduLevels",
            "ppsDelay",
            "tileProgrammingState",
        ]

        self._source_port = 0xF0D0
        self._destination_port: int = 4660

        self._sdn_first_address = sdn_first_interface.ip
        self._sdn_netmask = str(sdn_first_interface.netmask)
        self._sdn_gateway: str | None = str(sdn_gateway) if sdn_gateway else None

        self._lmc_param: dict[str, str | int | None] = {
            "mode": "10G",
            "payload_length": 8192,
            "destination_ip": "0.0.0.0",
            "destination_port": self._destination_port,
            "source_port": self._source_port,
            "netmask_40g": self._sdn_netmask,
            "gateway_40g": self._sdn_gateway,
        }
        self._lmc_integrated_mode = "1G"
        self._lmc_integrated_ip = "0.0.0.0"
        self._lmc_integrated_port = self._destination_port
        self._lmc_channel_payload_length = 1024
        self._lmc_beam_payload_length = 1024

        self._lmc_mode = "10G"
        self._lmc_ip = "0.0.0.0"
        self._lmc_port = self._destination_port
        self._lmc_payload_length = 8192

        self._desired_beamformer_table = np.zeros(shape=(48, 7), dtype=int)
        self._desired_beamformer_table[0] = [128, 0, 0, 0, 0, 0, 0]
        self._beamformer_table = np.zeros(shape=(48, 7), dtype=int)
        self._beamformer_table[0] = [128, 0, 0, 0, 0, 0, 0]
        self._beamformer_regions = np.zeros(shape=(48, 8), dtype=int)
        self._pps_delays = [0] * 16
        self._pps_delay_spread = 0
        self._pps_delay_corrections = [0] * 16
        self._tile_programming_state: list[str] = ["Unknown"] * self._number_of_tiles
        self._channeliser_rounding = channeliser_rounding or ([3] * 512)
        self._csp_rounding = [csp_rounding] * 384
        self._desired_static_delays: None | list[float] = None
        self._desired_preadu_levels: None | list[float] = None
        self._base_mac_address = 0x620000000000 + int(self._sdn_first_address)

        self._antenna_info: dict[int, dict[str, Union[int, dict[str, float]]]] = {}

        self._antenna_mapping: dict[int, dict[str, int]] = {}
        self._cable_lengths: dict[int, float] = {}
        self.last_pointing_delays = [0.0] * 513

        # Flag for whether to execute MccsTile batch commands async or sync.
        self.excecute_async = True

        self._power_command_in_progress = (
            threading.Lock()
        )  # Used to lock DevState during power command execution.

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            power=PowerState.UNKNOWN,
            fault=None,
            is_configured=None,
            adc_power=None,
        )

        optional_devices: dict[str, DeviceComponentManager] = {}
        if self._lmc_daq_proxy:
            optional_devices[self._lmc_daq_trl] = self._lmc_daq_proxy
        if self._bandpass_daq_proxy:
            optional_devices[self._bandpass_daq_trl] = self._bandpass_daq_proxy

        self._communication_manager = CommunicationManager(
            self._update_communication_state,
            self._update_component_state,
            self.logger,
            self._subrack_proxies,
            self._tile_proxies,
            optional_devices,
        )

        self.self_check_manager = SpsStationSelfCheckManager(
            component_manager=self,
            logger=self.logger,
            tile_trls=list(self._tile_proxies.keys()),
            subrack_trls=list(self._subrack_proxies.keys()),
            daq_trl=self._lmc_daq_trl,
        )

        self.acquiring_data_for_calibration = threading.Event()
        self.calibration_data_received_queue = UniqueQueue(logger=self.logger)

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

    @staticmethod
    def _find_by_key(data: dict, target: str) -> Any:
        """
        Search nested dict breadth-first for the first target key and return its value.

        This method is used to find station and antenna config within Low platform spec
        files, and should eventually be replaced by functions specifically designed to
        parse these files, aware of schema versions, etc, probably within ska-telmodel.

        :param data: generic nested dictionary to traverse through.
        :param target: key to find the first value of.

        :returns: the next value for given key.
        """
        bfs_queue = list(data.items())
        while bfs_queue:
            key, value = bfs_queue.pop(0)
            if key == target:
                return value
            if isinstance(value, dict):
                bfs_queue.extend(value.items())
        return None

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

        stations = self._find_by_key(full_dict, "stations")
        if not stations:
            self.logger.error(
                f"Couldn't find station {self._station_id} in imported TMData."
            )
            return

        # Look through all the stations on this cluster, find antennas on this station.
        antennas = {}
        for station_config in stations.values():
            if station_config["id"] == self._station_id:
                antennas = self._find_by_key(station_config, "antennas")
                break

        if not antennas:
            self.logger.error(f"Couldn't find antennas on station {self._station_id}.")
            return

        try:
            for _, antenna_config in antennas.items():
                antenna_number: int = int(antenna_config["eep"])  # 1 based numbering
                tpm_number: int = int(antenna_config["tpm"].split("tpm")[-1])
                self._antenna_mapping[antenna_number] = {
                    "tpm": tpm_number,  # 1 based numbering
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
        tile_delays = [
            [0] * TileData.ADC_CHANNELS for _ in range(len(self._tile_proxies))
        ]
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
            tile_no = self._antenna_mapping[antenna_no + 1]["tpm"] - 1
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
        self._communication_manager.start_communicating()

    def stop_communicating(self: SpsStationComponentManager) -> None:
        """Break off communication with the station components."""
        self._communication_manager.stop_communicating()

    def _device_communication_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        communication_state: CommunicationStatus,
    ) -> None:
        self._communication_manager.update_communication_status(
            fqdn, communication_state
        )

    def _on_tile_attribute_change(
        self: SpsStationComponentManager,
        logical_tile_id: int,
        attribute_name: str,
        attribute_value: Any,
        attribute_quality: tango.AttrQuality,
    ) -> None:
        # TODO: See THORN-89: Mark SpsStation Attributes as INVALID.
        if attribute_quality == tango.AttrQuality.ATTR_INVALID:
            self.logger.debug(
                f"Tile {logical_tile_id} attribute {attribute_name} "
                f"has quality {attribute_quality}. "
                "SpsStation is not yet capable of handling this. "
                "Ignoring!"
            )
            return
        attribute_name = attribute_name.lower()
        match attribute_name:
            case "adcpower":
                self._adc_power[logical_tile_id] = list(attribute_value)
                adc_powers: list[float] = []
                for _, adc_power in self._adc_power.items():
                    if adc_power is not None:
                        adc_powers += adc_power
                self._update_component_state(adc_power=adc_powers)
            case "statictimedelays":
                self._static_delays[logical_tile_id] = list(attribute_value)
            case "preadulevels":
                # Note: Currently all we do is update the attribute value.
                self._preadu_levels[logical_tile_id] = list(attribute_value)
            case "ppsdelay":
                # Only calc for TPMs actually present.
                self._pps_delays[logical_tile_id] = attribute_value
                self._pps_delay_spread = max(
                    self._pps_delays[0 : self._number_of_tiles]
                ) - min(self._pps_delays[0 : self._number_of_tiles])
                if self._component_state_callback:
                    self._component_state_callback(
                        ppsDelaySpread=self._pps_delay_spread
                    )
            case "tileprogrammingstate":
                self._tile_programming_state[logical_tile_id] = attribute_value

                if self._component_state_callback:
                    self._component_state_callback(
                        tileProgrammingState=self._tile_programming_state
                    )

            case "beamformertable":
                if logical_tile_id == len(self._tile_proxies) - 1:
                    reshaped_table = np.reshape(
                        np.pad(attribute_value, (0, (48 * 7 - len(attribute_value)))),
                        (48, 7),
                    )
                    if not np.array_equal(reshaped_table, self._beamformer_table):
                        filtered_old = self._beamformer_table[
                            ~np.all(self._beamformer_table == 0, axis=1)
                        ]
                        filtered_new = reshaped_table[
                            ~np.all(reshaped_table == 0, axis=1)
                        ]
                        self.logger.warning(
                            "Received HW readback of beamformer "
                            "table which doesn't match local cache. "
                            "Overwritting local cache with HW table. "
                            f"\nNew table: \n{filtered_new} "
                            f"\nOld table: \n{filtered_old}"
                        )
                    self._beamformer_table = reshaped_table
                    if self._component_state_callback:
                        self._component_state_callback(beamformerTable=attribute_value)
            case "beamformerregions":
                if logical_tile_id == len(self._tile_proxies) - 1:
                    reshaped_table = np.reshape(
                        np.pad(attribute_value, (0, (48 * 8 - len(attribute_value)))),
                        (48, 8),
                    )
                    self._beamformer_regions = reshaped_table
                    if self._component_state_callback:
                        self._component_state_callback(
                            beamformerRegions=attribute_value
                        )
            case _:
                self.logger.error(
                    f"Unrecognised tile attribute changing {attribute_name} "
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
        fault: Optional[bool] = None,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._tile_power_states[fqdn] = power
                if self._component_state_callback is not None:
                    self._component_state_callback(device_name=fqdn, power=power)

                self._evaluate_power_state()

        if health is not None:
            # Old health model.
            self._tile_health_changed_callback(fqdn, HealthState(health))
            # New health model.
            if self._component_state_callback is not None:
                self._component_state_callback(device_name=fqdn, health=health)

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
        # Old health model.
        if health is not None:
            self._subrack_health_changed_callback(fqdn, HealthState(health))
        # New health model.
        if self._component_state_callback is not None and health is not None:
            self._component_state_callback(
                device_name=fqdn,
                health=health,
            )

    @threadsafe
    def _lmc_daq_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        **state_change: Any,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._lmc_daq_power_state[fqdn] = power
                self._evaluate_power_state()
        if "dataReceivedResult" in state_change:
            data_received_result: tuple[str, str] = state_change.get(
                "dataReceivedResult", ("", "")
            )
            if (
                data_received_result[0] == "correlator"
                and self.acquiring_data_for_calibration.is_set()
            ):
                self.calibration_data_received_queue.put(
                    json.loads(data_received_result[1])["file_name"]
                )
            if self._component_state_callback is not None:
                self._component_state_callback(dataReceivedResult=data_received_result)

    @threadsafe
    def _bandpass_daq_state_changed(
        self: SpsStationComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        **state_change: Any,
    ) -> None:
        if power is not None:
            with self._power_state_lock:
                self._bandpass_daq_power_state[fqdn] = power
                self._evaluate_power_state()
        if "xPolBandpass" in state_change:
            x_bandpass_data = state_change.get("xPolBandpass")
            if self._component_state_callback is not None:
                self._component_state_callback(xPolBandpass=x_bandpass_data)
        if "yPolBandpass" in state_change:
            y_bandpass_data = state_change.get("yPolBandpass")
            if self._component_state_callback is not None:
                self._component_state_callback(yPolBandpass=y_bandpass_data)

    def _evaluate_power_state(
        self: SpsStationComponentManager,
    ) -> None:
        # 1. Any Tile ON, result = ON. (Subrack must therefore be on.)
        # 2. Any Subrack ON, All Tile OFF/NO_SUPP, result = STANDBY
        # 3. All Subrack NO_SUPP, All Tile NO_SUPP, result = NO_SUPP
        # 4. All Subracks OFF/NO_SUPP, All Tiles OFF/NO_SUPP, result = OFF
        # 5. Any subrack UNKNOWN AND no subrack ON |OR| Any tile UNKNOWN AND no tile ON
        if self._power_command_in_progress.locked():
            # Suppress power state evaluation whilst power command in progress.
            # This is to prevent the Station changing to DevState.ON before all tiles
            # have had a chance to turn on.
            return
        with self._power_state_lock:
            tile_power_states = list(self._tile_power_states.values())
            subrack_power_states = list(self._subrack_power_states.values())
            # Assume that with any Tile ON the subrack must also be ON.
            if any(power_state == PowerState.ON for power_state in tile_power_states):
                evaluated_power_state = PowerState.ON  # 1
            elif any(
                power_state == PowerState.ON for power_state in subrack_power_states
            ) and all(
                power_state in [PowerState.OFF, PowerState.NO_SUPPLY]
                for power_state in tile_power_states
            ):
                evaluated_power_state = PowerState.STANDBY  # 2
            elif all(
                power_state == PowerState.NO_SUPPLY
                for power_state in subrack_power_states
            ) and all(
                power_state == PowerState.NO_SUPPLY for power_state in tile_power_states
            ):
                evaluated_power_state = PowerState.NO_SUPPLY  # 3
            elif all(
                power_state in [PowerState.OFF, PowerState.NO_SUPPLY]
                for power_state in subrack_power_states
            ) and all(
                power_state in [PowerState.OFF, PowerState.NO_SUPPLY]
                for power_state in tile_power_states
            ):
                evaluated_power_state = PowerState.OFF  # 4
            else:
                # We get here by:
                # Any subrack UNKNOWN AND no subrack ON
                # Any tile UNKNOWN AND no tile ON
                self.logger.debug(f"tile powers: {tile_power_states}")
                self.logger.debug(f"subrack powers: {subrack_power_states}")
                evaluated_power_state = PowerState.UNKNOWN  # 5

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

    @lock_power_state
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

    @lock_power_state
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
        self.logger.debug(
            "Starting standby. State transitions suppressed during power command."
        )
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
                time.sleep(0.25)  # stagger power off by 0.25 seconds per tile
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

    @lock_power_state
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
        # pylint: disable=too-many-branches
        message: str = ""
        self.logger.debug("Starting on sequence.")
        self.logger.debug("State transitions suppressed during power command.")
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        result_code = ResultCode.OK

        # TODO MCCS-2212 Must revise the possible cases, avoiding potential deadlocks.
        if all(
            proxy._proxy is not None
            and proxy._proxy.tileProgrammingState in {"Initialised", "Synchronised"}
            for proxy in self._tile_proxies.values()
        ):
            self.logger.debug("Tiles already initialised")
            result_code = ResultCode.OK
            return

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

        if result_code == ResultCode.OK:
            self.logger.debug("Setting global reference time")
            self._set_global_reference_time(self._global_reference_time or None)

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
            # End of the actual power on sequence.

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising station")
            result_code = self._initialise_station(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Waiting for ARP table")
            result_code = self._wait_for_arp_table(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Routing data")
            result_code = self._route_data(None, task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Checking synchronisation")
            result_code = self._check_station_synchronisation(
                task_callback, task_abort_event
            )

        if result_code in [ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED]:
            self.logger.debug("End initialisation")
            task_status = TaskStatus.COMPLETED
            message = "On Command Completed"
        elif result_code is ResultCode.ABORTED:
            self.logger.error("Initialisation aborted")
            task_status = TaskStatus.ABORTED
            message = "On Command aborted"
        else:
            self.logger.error("Initialisation failed")
            task_status = TaskStatus.FAILED
            message = "On Command failed"
        if task_callback:
            task_callback(status=task_status, result=(result_code, message))

    def initialise(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        start_bandpasses: Optional[bool] = None,
        global_reference_time: Optional[str] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _initialise method.

        This method returns immediately after it submitted
        `self._initialise` for execution.

        :param task_callback: Update task state, defaults to None
        :param start_bandpasses: Whether to configure TPMs to send
            integrated data. Defaults to True.
        :param global_reference_time: Common global reference time for all TPMs,
            needs to be some time in the last 2 weeks.
            If not provided, 8am on the most recent Monday AWST will be used.

        :return: a task status and response message
        """
        return self.submit_task(
            self._initialise,
            task_callback=task_callback,
            args=[start_bandpasses, global_reference_time],
        )

    @check_communicating
    # pylint: disable=too-many-branches
    def _initialise(
        self: SpsStationComponentManager,
        start_bandasses: Optional[bool] = None,
        global_reference_time: Optional[str] = None,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Initialise this station.

        The order to turn a station on is: subrack, then tiles

        :param start_bandasses: Whether to configure TPMs to send
            integrated data.
        :param global_reference_time: Common global reference time for all TPMs,
            needs to be some time in the last 2 weeks.
            If not provided, 8am on the most recent Monday AWST will be used.
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
            self.logger.debug("Setting global reference time")
            self._set_global_reference_time(global_reference_time)

        if result_code == ResultCode.OK:
            self.logger.debug("Re-initialising tiles")
            result_code = self._reinitialise_tiles(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising tile parameters")
            result_code = self._initialise_tile_parameters(
                task_callback,
                task_abort_event,
            )

        if result_code == ResultCode.OK:
            self.logger.debug("Initialising station")
            result_code = self._initialise_station(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Waiting for ARP table")
            result_code = self._wait_for_arp_table(task_callback, task_abort_event)

        if result_code == ResultCode.OK:
            self.logger.debug("Routing data")
            result_code = self._route_data(
                start_bandasses,
                task_callback,
                task_abort_event,
            )

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
                    time.sleep(0.25)  # stagger power on by 0.25 seconds per tile
                    results.append(result_code)
                if TaskStatus.FAILED in results:
                    return ResultCode.FAILED
        # wait for tiles to come up
        timeout = 180  # Seconds. Switch may take up to 3 min to recognize a new link
        tick = 2
        last_time = time.time() + timeout
        desired_states = ["Synchronised"]
        if self._global_reference_time == "":
            desired_states.append("Initialised")
        while time.time() < last_time:
            time.sleep(tick)
            if task_abort_event and task_abort_event.is_set():
                self.logger.info("_turn_on_tiles task has been aborted")
                return ResultCode.ABORTED
            states = self.tile_programming_state()
            self.logger.debug(f"tileProgrammingState: {states}")
            if all(state in desired_states for state in states):
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
    def _set_global_reference_time(
        self: SpsStationComponentManager, global_reference_time: Optional[str] = None
    ) -> ResultCode:
        if self.csp_spead_format != "SKA":
            self.logger.debug("Not setting global reference time for non-SKA format")
            return ResultCode.OK
        if global_reference_time is not None:
            self.global_reference_time = global_reference_time
        else:
            rfc_format = "%Y-%m-%dT%H:%M:%S.%fZ"

            time_ref = int(
                Time(  # parse
                    date.today().isoformat(),  # last midnight
                    scale="tai",  # as a TAI time
                ).unix  # convert to unix timestamp
            )

            self.global_reference_time = datetime.strftime(
                datetime.fromtimestamp(time_ref, tz=timezone.utc), rfc_format
            )
        self.logger.debug(f"Global reference time: {self.global_reference_time}")
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
                time.sleep(0.25)  # stagger initialisation by 0.25 seconds per tile
                results.append(result_code)
        if ResultCode.FAILED in results:
            return ResultCode.FAILED

        # wait for tiles to come up
        timeout = 180  # Seconds. Switch may take up to 3 min to recognize a new link
        tick = 2
        last_time = time.time() + timeout
        desired_states = ["Synchronised"]
        if self._global_reference_time == "":
            desired_states.append("Initialised")
        while time.time() < last_time:
            time.sleep(tick)
            states = self.tile_programming_state()
            self.logger.debug(f"tileProgrammingState: {states}")
            if all(state in desired_states for state in states):
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
            if self._desired_preadu_levels is not None:
                self.logger.info(
                    "Initialise routine overriding MccsTile instance PreaduAttenuation "
                )
                tile.preaduLevels = self._desired_preadu_levels[i1:i2]
            if self._desired_static_delays is not None:
                self.logger.info(
                    "Initialise routine overriding MccsTile instance StaticTimeDelays "
                )
                tile.staticTimeDelays = self._desired_static_delays[i1:i2]
            tile.channeliserRounding = self._channeliser_rounding
            tile.cspRounding = self._csp_rounding
            tile.cspSpeadFormat = self._csp_spead_format
            tile.globalReferenceTime = self._global_reference_time
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
        last_tile_id = len(tiles) - 1
        for tile_id, proxy in enumerate(tiles):
            assert proxy._proxy is not None

            if tile_id == last_tile_id:
                is_last_tile = True
                dst_ip1 = self._csp_ingest_address
                dst_ip2 = self._csp_ingest_address
            else:
                is_last_tile = False
                dst_ip1 = str(self._sdn_first_address + 2 * tile_id + 2)
                dst_ip2 = str(self._sdn_first_address + 2 * tile_id + 3)

            proxy._proxy.SetCspDownload(
                json.dumps(
                    {
                        "source_port": self._source_port,
                        "destination_ip_1": dst_ip1,
                        "destination_ip_2": dst_ip2,
                        "destination_port": self._destination_port,
                        "is_last": is_last_tile,
                        "netmask": self._sdn_netmask,
                        "gateway": self._sdn_gateway,
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

        for i in range(5):
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
                self.logger.error("FPGA time counters not synced, try again")
                time.sleep(1)
            else:
                return ResultCode.OK

        self.logger.error("FPGA time counters not synced after 5 retries")
        return ResultCode.FAILED

    def _route_data(
        self: SpsStationComponentManager,
        start_bandpasses: Optional[bool] = None,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> ResultCode:
        """
        Route data streams to relevant DAQs.

        Route integrated data (for bandpasses) over the 1G to bandpass DAQ, route
        everything else over the 10G to the LMC DAQ.

        :param start_bandpasses: whether to start sending
            integrated data, defaults to deployed default.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Abort the task
        :return: a result code
        """
        if self._lmc_daq_proxy is not None and self._lmc_daq_proxy._proxy is not None:
            lmc_daq_status = json.loads(self._lmc_daq_proxy._proxy.DaqStatus())
            self._lmc_ip = lmc_daq_status["Receiver IP"][0]
            self._lmc_port = lmc_daq_status["Receiver Ports"][0]
        if (
            self._bandpass_daq_proxy is not None
            and self._bandpass_daq_proxy._proxy is not None
        ):
            bandpass_daq_status = json.loads(
                self._bandpass_daq_proxy._proxy.DaqStatus()
            )
            self._lmc_integrated_ip = bandpass_daq_status["Receiver IP"][0]
            self._lmc_integrated_port = bandpass_daq_status["Receiver Ports"][0]
        self.logger.debug(f"Configuring LMC Download: {self._lmc_ip}:{self._lmc_port}")
        self.logger.debug(
            "Configuring LMC Integrated Download: "
            f"{self._lmc_integrated_ip}:{self._lmc_integrated_port}"
        )
        self.set_lmc_integrated_download(
            mode=self._lmc_integrated_mode,
            dst_ip=self._lmc_integrated_ip,
            dst_port=self._lmc_integrated_port,
            channel_payload_length=self._lmc_channel_payload_length,
            beam_payload_length=self._lmc_beam_payload_length,
        )
        self.set_lmc_download(
            mode=self._lmc_mode,
            dst_ip=self._lmc_ip,
            dst_port=self._lmc_port,
            payload_length=self._lmc_payload_length,
        )
        if (
            start_bandpasses
            if start_bandpasses is not None
            else self._start_bandpasses_in_initialise
        ):
            self.configure_integrated_channel_data(
                integration_time=self._bandpass_integration_time,
                first_channel=0,
                last_channel=511,
            )
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
            assert proxy._proxy.ppsDelay is not None
            self._pps_delays[i] = proxy._proxy.ppsDelay
        return copy.deepcopy(self._pps_delays)

    @property
    def pps_delay_spread(self: SpsStationComponentManager) -> int:
        """
        Get PPS delay delta.

        Returns the difference between the maximum and minimum delays so
        that users can track an observed pps drift.
        Returns a result in samples, each sample is 1.25ns.

        :return: Maximum delay difference between tiles in samples.
        """
        return self._pps_delay_spread

    @property
    def pps_delay_corrections(self: SpsStationComponentManager) -> list[int]:
        """
        Get the PPS delay correction.

        :return: Array of pps delay corrections, one value per tile, in nanoseconds
        """
        for i, proxy in enumerate(self._tile_proxies.values()):
            assert proxy._proxy is not None  # for the type checker
            assert proxy._proxy.ppsDelayCorrection is not None
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
        Delay in nanoseconds (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        static_delays: list[float] = []
        for _, static_delay in self._static_delays.items():
            if static_delay is not None:
                static_delays += static_delay
        return static_delays

    @static_delays.setter
    def static_delays(
        self: SpsStationComponentManager, delays: list[int | float]
    ) -> None:
        """
        Set static time delay correction.

        :param delays: Array of one value per antenna/polarization (32 per tile)

        :raises RuntimeError: When the tiles logicalTileId is not known,
            this information is required to ensure the delays are applied
            to the correct TPM.
        """
        self._desired_static_delays = delays
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            __tile_id = proxy._proxy.logicalTileId
            if __tile_id is None:
                raise RuntimeError(
                    "logicalTileId is not valid. "
                    "Unable to set static delays without knowledge of mapping"
                )
            start_entry = (__tile_id) * TileData.ADC_CHANNELS
            end_entry = (__tile_id + 1) * TileData.ADC_CHANNELS
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
    def global_reference_time(self: SpsStationComponentManager) -> str:
        """
        Return the UTC time used as global synchronization time.

        :return: UTC time in ISOT format used as global synchronization time
        """
        return self._global_reference_time

    @global_reference_time.setter  # type: ignore[no-redef]
    def global_reference_time(
        self: SpsStationComponentManager, reference_time: str
    ) -> None:
        """
        Set the Unix time used as global synchronization time.

        Time will be used by all tiles as a common start time for timestamps.
        If specified, StartAcquisition is also performed in Station.On()
        :param reference_time: Reference time in ISOT format, or null string
        """
        self._global_reference_time = reference_time
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            proxy._proxy.globalReferenceTime = reference_time

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
        self._desired_preadu_levels = levels
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
        return copy.deepcopy(self._beamformer_table.tolist())

    @property
    def beamformer_regions(self: SpsStationComponentManager) -> list[list[int]]:
        """
        Get beamformer region table.

        Bidimensional array of one row for each 8 channels, with elements:
        0. start physical channel
        1. number of channels
        2. beam index
        3. subarray ID
        4. subarray_logical_channel
        5. subarray_beam_id
        6. substation_id
        8. aperture_id

        Each row is a set of 8 consecutive elements in the list.

        :return: list of up to 8*48 values
        """
        return copy.deepcopy(self._beamformer_regions.tolist())

    @beamformer_regions.setter
    def beamformer_regions(
        self: SpsStationComponentManager, regions: np.ndarray
    ) -> None:
        """
        Set beamformer region table.

        :param regions: bidimensional array of one row for each 8 channels,
            with elements:
            0. start physical channel
            1. number of channels
            2. beam index
            3. subarray ID
            4. subarray_logical_channel
            5. subarray_beam_id
            6. substation_id
            7. aperture_id

        Each row is a set of 8 consecutive elements in the list.
        """
        self._beamformer_regions = regions

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
        for tile_id, tile in enumerate(self._tile_proxies.values()):
            assert tile._proxy is not None  # for the type checker
            assert tile._proxy.tileProgrammingState is not None
            self._tile_programming_state[tile_id] = tile._proxy.tileProgrammingState
        return self._tile_programming_state.copy()

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

    def board_temperature_summary(
        self: SpsStationComponentManager,
    ) -> list[float] | None:
        """
        Get summary of board temperatures.

        :return: minimum, average and maximum of board temperatures
        """
        board_temperatures = [
            tile._proxy.boardTemperature
            for tile in self._tile_proxies.values()
            if tile._proxy is not None and tile._proxy.boardTemperature is not None
        ]
        if len(board_temperatures) == 0:
            self.logger.info("No data available for summary.")
            return None
        return [
            min(board_temperatures),
            mean(board_temperatures),
            max(board_temperatures),
        ]

    def fpga_temperature_summary(
        self: SpsStationComponentManager,
    ) -> list[float] | None:
        """
        Get summary of FPGAs temperatures.

        :return: minimum, average and maximum of FPGAs temperatures
        """
        fpga_1_temperatures = [
            tile._proxy.fpga1Temperature
            for tile in self._tile_proxies.values()
            if tile._proxy is not None and tile._proxy.fpga1Temperature is not None
        ]
        fpga_2_temperatures = [
            tile._proxy.fpga2Temperature
            for tile in self._tile_proxies.values()
            if tile._proxy is not None and tile._proxy.fpga2Temperature is not None
        ]
        if len(fpga_1_temperatures) == 0 or len(fpga_2_temperatures) == 0:
            self.logger.info("No data available for summary.")
            return None
        fpga_temperatures = fpga_1_temperatures + fpga_2_temperatures
        return [min(fpga_temperatures), mean(fpga_temperatures), max(fpga_temperatures)]

    def pps_delay_summary(self: SpsStationComponentManager) -> list[float] | None:
        """
        Get summary of PPS delays.

        :return: minimum, average and maximum of PPS delays
        """
        pps_delays = [
            tile._proxy.ppsDelay
            for tile in self._tile_proxies.values()
            if tile._proxy is not None and tile._proxy.ppsDelay is not None
        ]
        if len(pps_delays) == 0:
            self.logger.info("No data available for summary.")
            return None

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

    @property
    def keep_test_data(self: "SpsStationComponentManager") -> bool:
        """
        Get whether test data will be kept from the self_check_manager.

        :return: whether the test data will be kept.
        """
        return self.self_check_manager.keep_test_data

    @keep_test_data.setter
    def keep_test_data(self: "SpsStationComponentManager", value: bool) -> None:
        """
        Set whether test data will be kept from the self_check_manager.

        :param value: whether or not to keep test data.
        """
        self.self_check_manager.keep_test_data = value

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
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Configure link and size of LMC channel.

        :param mode: '1G' or '10G'
        :param payload_length: SPEAD payload length for LMC packets
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self._lmc_param["mode"] = mode
        self._lmc_param["payload_length"] = payload_length
        self._lmc_param["destination_ip"] = dst_ip
        self._lmc_param["source_port"] = src_port
        self._lmc_param["destination_port"] = int(dst_port)
        self._lmc_param["netmask_40g"] = self._sdn_netmask
        self._lmc_param["gateway_40g"] = self._sdn_gateway
        json_param = json.dumps(self._lmc_param)
        return self._execute_async_on_tiles(
            "SetLmcDownload", json_param, require_initialised=True
        )

    def set_lmc_integrated_download(
        self: SpsStationComponentManager,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: str = "",
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
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

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
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
                "destination_port": int(dst_port),
                "netmask_40g": self._sdn_netmask,
                "gateway_40g": self._sdn_gateway,
            }
        )
        return self._execute_async_on_tiles(
            "SetLmcIntegratedDownload", json_param, require_initialised=True
        )

    def set_csp_ingest(
        self: SpsStationComponentManager,
        dst_ip: str,
        src_port: int,
        dst_port: int,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Configure last tile link for CSP ingest channel.

        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660

        :return: tuple containing Resultcode and message.
        """
        self._csp_ingest_address = dst_ip
        self._csp_ingest_port = dst_port
        self._csp_source_port = src_port

        (fqdn, proxy) = list(self._tile_proxies.items())[-1]
        assert proxy._proxy is not None  # for the type checker
        if self._tile_power_states[fqdn] != PowerState.ON:
            return ([ResultCode.FAILED], [f"{fqdn} is not in PowerState.ON"])

        return proxy._proxy.SetCspDownload(
            json.dumps(
                {
                    "source_port": self._csp_source_port,
                    "destination_ip_1": self._csp_ingest_address,
                    "destination_ip_2": self._csp_ingest_address,
                    "destination_port": self._csp_ingest_port,
                    "is_last": True,
                    "netmask": self._sdn_netmask,
                    "gateway": self._sdn_gateway,
                }
            )
        )

    def set_beamformer_table(
        self: SpsStationComponentManager, beamformer_table: list[list[int]]
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Set the frequency regions to be beamformed into each beam.

        :param beamformer_table: a list encoding up to 48 regions, with each
            region corresponding to 8 channels. Entry items specify:

        * start physical channel
        * beam_index:  subarray beam used for this region, range [0:48)
        * subarray_id: ID of the subarray [1:48]
        * subarray_logical_channel: Logical channel in the subarray
            it is the same for all (sub)stations in the subarray
            Defaults to station logical channel
        * subarray_beam_id: ID of the subarray beam
            Defaults to beam index
        * substation_ID: ID of the substation
            Defaults to 0 (no substation)
        * aperture_id:  ID of the aperture (station*100+substation?)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        number_entries = len(beamformer_table)
        for i in range(number_entries):
            self._desired_beamformer_table[i] = beamformer_table[i]
        for i in range(number_entries, 48):
            self._desired_beamformer_table[i] = [0, 0, 0, 0, 0, 0, 0]
        return self._set_beamformer_table()

    def _set_beamformer_table(
        self: SpsStationComponentManager,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Set the frequency regions to be beamformed into a single beam.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        # At least one entry in the beamformer table must be not null
        # Entries with start channel & subarray ID = 0 are ignored in MccsTile
        if all(
            (entry[0] == 0 and entry[2] == 0)  # At least one region must exist
            for entry in self._desired_beamformer_table
        ):
            self._desired_beamformer_table[0] = [128, 0, 0, 0, 0, 0, 0]
            self.logger.warning("No regions specified, providing a default one")
        last_entry = 0
        using_channel_0 = False
        # transmit only entries up to the last valid one
        for index, entry in enumerate(self._desired_beamformer_table):
            if entry[0] != 0 or entry[2] != 0:  # valid entry
                last_entry = index
                if entry[0] == 0:  # DC channel is not properly handled in HW
                    using_channel_0 = True
        if using_channel_0:
            self.logger.warning("Using channel 0: DC channel not handled in hardware")
        beamformer_regions = []
        for entry in self._desired_beamformer_table[0 : last_entry + 1]:
            beamformer_regions.append(list([entry[0], 8]) + list(entry[1:7]))
        return self._execute_async_on_tiles(
            "SetBeamformerRegions",
            list(itertools.chain.from_iterable(beamformer_regions)),
            require_initialised=True,
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
        proxy.LoadCalibrationCoefficients(list(coefs))

    def apply_calibration(
        self: SpsStationComponentManager, switch_time: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("ApplyCalibration", switch_time)

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

        self.last_pointing_delays = delay_list

        for tile_proxy in self._tile_proxies.values():
            assert tile_proxy._proxy is not None

            # TODO: Extracting tile id from TRL of the form "low-mccs/tile/s8-1-tpm01"
            # But this code should not be depending on assumptions about TRL structure
            tile_no = int(tile_proxy._proxy.dev_name().split("-")[-1][3:])
            delays_for_tile = tile_delays[tile_no - 1]
            tile_proxy._proxy.LoadPointingDelays(delays_for_tile)

    def apply_pointing_delays(
        self: SpsStationComponentManager, load_time: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("ApplyPointingDelays", load_time)

    def start_beamformer(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        start_time: Optional[str] = None,
        duration: int = -1,
        channel_groups: Optional[list[int]] = None,
        scan_id: int = 0,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _start_beamformer method.

        This method returns immediately after it submitted
        `self._start_beamformer` for execution.

        :param task_callback: Update task state, defaults to None
        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :param channel_groups: Channel groups to which the command applies.
        :param scan_id: ID of the scan which is started.

        :return: a task status and response message
        """
        return self.submit_task(
            self._start_beamformer,
            args=[start_time, duration, channel_groups, scan_id],
            task_callback=task_callback,
        )

    def _start_beamformer(
        self: SpsStationComponentManager,
        start_time: str,
        duration: float,
        channel_groups: list[int] | None,
        scan_id: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :param channel_groups: Channel groups to which the command applies.
        :param scan_id: ID of the scan which is started.
        :param task_callback: Update task state, defaults to None.
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)
        parameter_list = {
            "start_time": start_time,
            "duration": duration,
            "scan_id": scan_id,
        }
        if channel_groups is not None:
            parameter_list["channel_groups"] = channel_groups
        json_argument = json.dumps(parameter_list)
        start_beamformer_commands = MccsCompositeCommandProxy(self.logger)
        for tile_trl in self._tile_proxies:
            start_beamformer_commands += MccsCommandProxy(
                device_name=tile_trl,
                command_name="StartBeamformer",
                logger=self.logger,
                default_args=json_argument,
            )
        result, message = start_beamformer_commands(
            command_evaluator=CompositeCommandResultEvaluator(),
        )
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(result, message),
            )

    def stop_beamformer(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _stop_beamformer method.

        This method returns immediately after it submitted
        `self._stop_beamformer` for execution.

        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._stop_beamformer, args=[None], task_callback=task_callback
        )

    def stop_beamformer_for_channels(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        channel_groups: Optional[list[int]] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the _stop_beamformer method.

        This method returns immediately after it submitted
        `self._stop_beamformer` for execution.

        :param channel_groups: Channel groups to which the command applies.

        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        logging.info(f"stop_beamformer called for channel_groups {channel_groups}")
        return self.submit_task(
            self._stop_beamformer, args=[channel_groups], task_callback=task_callback
        )

    def _stop_beamformer(
        self: SpsStationComponentManager,
        channel_groups: Optional[list[int]],
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Stop the beamformer.

        :param channel_groups: Channel groups to which the command applies.
        :param task_callback: Update task state, defaults to None.
        :param task_abort_event: Check for abort, defaults to None
        """
        parameter_list = {}
        parameter_list = {"channel_groups": channel_groups}
        json_argument = json.dumps(parameter_list)
        if task_callback is not None:
            task_callback(status=TaskStatus.IN_PROGRESS)

        stop_beamformer_commands = MccsCompositeCommandProxy(self.logger)
        for tile_trl in self._tile_proxies:
            stop_beamformer_commands += MccsCommandProxy(
                device_name=tile_trl,
                command_name="StopBeamformer",
                logger=self.logger,
                default_args=json_argument,
            )
        result, message = stop_beamformer_commands(
            command_evaluator=CompositeCommandResultEvaluator()
        )
        if task_callback is not None:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(result, message),
            )

    def beamformer_running_for_channels(
        self: SpsStationComponentManager,
        channel_groups: list[int] | None,
    ) -> bool:
        """
        Check if the beamformer is running in a list of channel blocks.

        :param channel_groups: List of channel blocks to check

        :return: True if the beamformer is running
        """
        json_arg = json.dumps({"channel_groups": channel_groups})
        return all(
            tile._proxy is not None
            and tile._proxy.BeamformerRunningForChannels(json_arg)
            for tile in self._tile_proxies.values()
        )

    def configure_integrated_channel_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        parameter_list = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
        }
        json_argument = json.dumps(parameter_list)
        return self._execute_async_on_tiles(
            "ConfigureIntegratedChannelData", json_argument
        )

    def configure_integrated_beam_data(
        self: SpsStationComponentManager,
        integration_time: float,
        first_channel: int,
        last_channel: int,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        parameter_list = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
        }
        json_argument = json.dumps(parameter_list)
        return self._execute_async_on_tiles(
            "ConfigureIntegratedBeamData", json_argument
        )

    def stop_integrated_data(
        self: SpsStationComponentManager,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Stop the integrated data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("StopIntegratedData")

    def send_data_samples(
        self: SpsStationComponentManager, argin: str, force: bool = False
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Front end for send_xxx_data methods.

        :param argin: Json encoded parameter List
        :param force: whether to cancel ongoing requests first.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        pending_requests = [
            dev._proxy.pendingDataRequests
            for dev in self._tile_proxies.values()
            if dev._proxy is not None
        ]
        if any(pending_requests):
            if not force:
                return [ResultCode.REJECTED], [
                    f"Current pending data requests: {pending_requests}."
                    " Call with 'force: True' to abort current send operations."
                ]
            result_code, message = self.stop_data_transmission()

            if result_code[0] != ResultCode.OK:
                return result_code, [f"Couldn't stop data transmission: {message[0]}"]
        return self._execute_async_on_tiles(
            "SendDataSamples", argin, require_synchronised=True
        )

    def stop_data_transmission(
        self: SpsStationComponentManager,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Stop data transmission for send_channelised_data_continuous.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("StopDataTransmission")

    def configure_test_generator(
        self: SpsStationComponentManager, argin: str
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Distribute to tiles command configure_test_generator.

        :param argin: Json encoded parameter List

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("ConfigureTestGenerator", argin)

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

        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

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
        task_callback: Optional[Callable] = None,
        *,
        first_channel: int,
        last_channel: int,
        start_time: str | None = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the acquire data for calibration method.

        This method returns immediately after it submitted
        `self._acquire_data_for_calibration` for execution.

        :param first_channel: first channel to calibrate for
        :param last_channel: last channel to calibrate for
        :param start_time: UTC Time for start sending data.
        :param task_callback: Update task state, defaults to None

        :return: a task staus and response message
        """
        return self.submit_task(
            self._acquire_data_for_calibration,
            args=[first_channel, last_channel, start_time],
            task_callback=task_callback,
        )

    def _start_daq(
        self: SpsStationComponentManager,
        daq_mode: str,
        max_tries: int = 10,
        tick: float = 0.5,
    ) -> None:
        assert self._lmc_daq_proxy is not None
        retry_command_on_exception(
            self._lmc_daq_proxy._proxy,
            "Start",
            json.dumps(
                {"modes_to_start": daq_mode},
            ),
        )
        self.logger.info(f"Starting daq to capture in mode {daq_mode}")
        for _ in range(max_tries):
            daq_status = json.loads(
                retry_command_on_exception(self._lmc_daq_proxy._proxy, "DaqStatus")
            )
            if any(
                status_list[0] == daq_mode
                for status_list in daq_status["Running Consumers"]
            ):
                return
            time.sleep(tick)

        assert (
            len(daq_status["Running Consumers"]) > 0
            and daq_mode in daq_status["Running Consumers"][0]
        ), f"Failed to start {daq_mode}."

    def _stop_daq(
        self: SpsStationComponentManager, max_tries: int = 10, tick: float = 0.5
    ) -> None:
        assert self._lmc_daq_proxy is not None
        retry_command_on_exception(self._lmc_daq_proxy._proxy, "Stop")
        for _ in range(max_tries):
            daq_status = json.loads(
                retry_command_on_exception(self._lmc_daq_proxy._proxy, "DaqStatus")
            )
            if len(daq_status["Running Consumers"]) == 0:
                return
            time.sleep(tick)

        assert daq_status["Running Consumers"] == [], "Failed to stop Daq."

    # pylint: disable = too-many-branches
    @check_communicating
    def _acquire_data_for_calibration(
        self: SpsStationComponentManager,
        first_channel: int,
        last_channel: int,
        start_time: str | None = None,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Acquire data for calibration.

        :param start_time: UTC Time for start sending data.
        :param first_channel: first channel to calibrate for
        :param last_channel: last channel to calibrate for
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        self.acquiring_data_for_calibration.set()
        try:
            states = self.tile_programming_state()
            self.logger.debug(f"tileProgrammingState: {states}")
            if any(state != TpmStatus.SYNCHRONISED.pretty_name() for state in states):
                if task_callback:
                    task_callback(
                        status=TaskStatus.REJECTED,
                        result=(
                            ResultCode.REJECTED,
                            "AcquireDataForCalibration failed. Tiles not synchronised.",
                        ),
                    )
                return

            def _check_aborted() -> bool:
                if task_abort_event and task_abort_event.is_set():
                    self.logger.info(
                        "ConfigureStationForCalibration task has been aborted"
                    )
                    if task_callback:
                        task_callback(
                            status=TaskStatus.ABORTED,
                            result=(ResultCode.ABORTED, "Task aborted"),
                        )
                    return True
                return False

            if task_callback:
                task_callback(status=TaskStatus.IN_PROGRESS)

            self._start_daq("CORRELATOR_DATA")
            if start_time is None:
                self.logger.info(
                    "No start_time defined. Defaulting to 2 seconds in the future."
                )
                start_time = (
                    datetime.now(timezone.utc) + timedelta(seconds=2)
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            # Send data from tpms
            self.send_data_samples(
                json.dumps(
                    {
                        "start_time": start_time,
                        "data_type": "channel",
                        "first_channel": first_channel,
                        "last_channel": last_channel,
                        "n_samples": 1835008,
                    }
                )
            )
            self.logger.debug(
                f"Raw channel spigot sent for {first_channel=}, {last_channel=}"
            )
            self.logger.debug("Waiting for data to be received...")
            success = True
            while True:
                if _check_aborted():
                    return
                try:
                    filename = self.calibration_data_received_queue.get(
                        timeout=10
                    ).split("correlation_burst_")[1]
                except Empty:
                    self.logger.error("Failed to receive data in 10 seconds.")
                    success = False
                    break
                channel = int(filename.split("_")[0])
                if channel == last_channel:
                    self.logger.info(
                        f"Got data for {channel}, this is the last channel expected."
                    )
                    break
                self.logger.debug(
                    f"Got data for {channel}, waiting "
                    f"for {last_channel}, {last_channel - channel} more."
                )
            self.logger.info("Stopping all consumers...")
            self._stop_daq()

            if task_callback:
                if success:
                    task_callback(
                        status=TaskStatus.COMPLETED,
                        result=(ResultCode.OK, "AcquireDataForCalibration Completed."),
                    )
                else:
                    task_callback(
                        status=TaskStatus.FAILED,
                        result=(
                            ResultCode.FAILED,
                            "Failed to receive data in 10 seconds.",
                        ),
                    )
        finally:
            self.acquiring_data_for_calibration.clear()
            self.calibration_data_received_queue = UniqueQueue(logger=self.logger)

    def configure_station_for_calibration(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        **daq_config: dict[str, Any],
    ) -> tuple[TaskStatus, str]:
        """
        Submit the configure station for calibration method.

        This method returns immediately after it submitted
        `self._configure_station_for_calibration` for execution.

        :param task_callback: Update task state, defaults to None
        :param daq_config: any extra config to configure DAQ with

        :return: a task staus and response message
        """
        return self.submit_task(
            self._configure_station_for_calibration,
            task_callback=task_callback,
            kwargs=daq_config,
        )

    @check_communicating
    def _configure_station_for_calibration(
        self: SpsStationComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
        **daq_config: dict[str, Any],
    ) -> None:
        """
        Configure station for calibration.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        :param daq_config: any extra config to configure DAQ with
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        def _check_aborted() -> bool:
            if task_abort_event and task_abort_event.is_set():
                self.logger.info("ConfigureStationForCalibration task has been aborted")
                if task_callback:
                    task_callback(
                        status=TaskStatus.ABORTED,
                        result=(ResultCode.ABORTED, "Task aborted"),
                    )
                return True
            return False

        nof_correlator_samples: int = 1835008
        receiver_frame_size: int = 9000

        max_tries: int = 10
        tick: float = 0.5

        # Get DAQ running with correlator
        assert self._lmc_daq_proxy is not None
        assert self._lmc_daq_proxy._proxy is not None

        daq_status = json.loads(
            retry_command_on_exception(self._lmc_daq_proxy._proxy, "DaqStatus", None)
        )
        if _check_aborted():
            return

        # TODO: We have to stop all consumers before sending again
        # https://jira.skatelescope.org/browse/MCCS-2183
        if len(daq_status["Running Consumers"]) > 0:
            self.logger.info("Stopping all consumers...")
            rc, _ = retry_command_on_exception(self._lmc_daq_proxy._proxy, "Stop", None)
            if rc != ResultCode.OK:
                self.logger.warning("Unable to stop daq consumers.")
            for _ in range(max_tries):
                daq_status = json.loads(
                    retry_command_on_exception(
                        self._lmc_daq_proxy._proxy, "DaqStatus", None
                    )
                )
                if len(daq_status["Running Consumers"]) == 0:
                    break
                if _check_aborted():
                    return
                time.sleep(tick)

            assert daq_status["Running Consumers"] == [], "Failed to stop Daq."

        base_config = {
            "nof_tiles": 16,  # always 16 for correlation mode.
            "directory": "correlator_data",  # Appended to ADR-55 path.
            "nof_correlator_samples": nof_correlator_samples,
            "receiver_frame_size": receiver_frame_size,
            "description": "Data from AcquireDataForCalibration",
        }
        base_config.update(daq_config)

        retry_command_on_exception(
            self._lmc_daq_proxy._proxy,
            "configure",
            json.dumps(base_config),
        )
        if _check_aborted():
            return

        self.set_lmc_download(
            mode="10g",
            payload_length=8192,  # Default for using 10g
            dst_ip=daq_status["Receiver IP"][0],
            dst_port=daq_status["Receiver Ports"][0],
        )
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Station configured for calibration."),
            )

    @property
    def csp_spead_format(self: SpsStationComponentManager) -> str:
        """
        Get CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :return: CSP Spead format. AAVS or SKA
        """
        return self._csp_spead_format

    @csp_spead_format.setter  # type: ignore[no-redef]
    def csp_spead_format(self: SpsStationComponentManager, spead_format: str) -> None:
        """
        Set CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :param spead_format: format used in CBF SPEAD header: "AAVS" or "SKA"
        """
        if spead_format in ["AAVS", "SKA"]:
            self._csp_spead_format = spead_format
        else:
            self.logger.error("Invalid SPEAD format: should be AAVS or SKA")
            return
        for proxy in self._tile_proxies.values():
            assert proxy._proxy is not None  # for the type checker
            proxy._proxy.cspSpeadFormat = spead_format

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

        self._channeliser_rounding = list(channeliser_rounding)

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
        *,
        target_adc: float,
        bias: float,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the trigger adc equalisation method.

        This method returns immediately after it submitted
        `self._trigger_adc_equalisation` for execution.

        :param task_callback: Update task state, defaults to None
        :param target_adc: adc value in ADU units. Defaults to 17.
        :param bias: user specifed bias in dB added to the antenna preadu levels.
                Defaults to 0.

        :return: a task status and response message
        """
        return self.submit_task(
            self._trigger_adc_equalisation,
            args=[target_adc, bias],
            task_callback=task_callback,
        )

    @check_communicating
    def _trigger_adc_equalisation(
        self: SpsStationComponentManager,
        target_adc: float = 17.0,
        bias: float = 0.0,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Equalise adc using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        :param target_adc: adc value in ADU units. Defaults to 17.
        :param bias: user specifed bias in dB added to the antenna preadu levels.
                Defaults to 0.
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)

        tpms = self._tile_proxies.values()
        num_samples = 20

        adc_data = np.empty([num_samples, 32 * len(tpms)])
        for i in range(num_samples):
            time.sleep(1)
            adc_data[i] = self.adc_power()

        # calculate difference in dB between current and target values
        adc_medians = np.median(adc_data, axis=0)

        # adc deltas
        # The maximum attenuation is 127/4=31.75 dB
        # 10^(-31.75/10) = 0.000668
        # any target_adc < 0.000668 will be larger than the limit set.
        # We allow a 32 dB bias range -> reduce to 4.2*10^(-7) from:
        # 10^(-3.175-3.2) = 10^(-6.375)
        adc_deltas = 20 * np.log10(adc_medians / max(target_adc, 4.2e-7))

        # calculate ideal attenuation
        preadu_levels = np.concatenate([t.preadu_levels() for t in tpms])
        desired_levels = preadu_levels + adc_deltas + bias * np.ones(32 * len(tpms))

        # quantise and clip to valid range
        sanitised_levels = (desired_levels * 4).round().clip(0, 127) / 4

        # apply new preADU levels to the station
        self.preadu_levels = sanitised_levels

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "ADC equalisation complete."),
            )

    def start_adcs(
        self: SpsStationComponentManager,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Start ADCs on all tiles.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("StartADCs", require_synchronised=True)

    def stop_adcs(
        self: SpsStationComponentManager,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Stop ADCs on all tiles.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._execute_async_on_tiles("StopADCs", require_synchronised=True)

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

    # pylint: disable=broad-exception-caught
    def _execute_async_on_tiles(
        self: SpsStationComponentManager,
        command_name: str,
        command_args: Optional[Any] = None,
        timeout: int = 20,
        require_initialised: bool = False,
        require_synchronised: bool = False,
    ) -> tuple[list[ResultCode], list[Optional[str]]]:
        """
        Execute a given command on all tile proxies in separate threads.

        This is for commands which return a DevVarLongStringArrayType.

        :param command_name: command to execute.
        :param command_args: args to execute commands with.
        :param timeout: timeout in which to expect command completion.
        :param require_initialised: if this command can only execute on an initialised
            tile.
        :param require_synchronised: if this command can only execute on a synchronised
            tile.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.logger.debug(f"calling {command_name} with {command_args=}")
        command_args = [command_args] if command_args is not None else []

        # Ideally we wouldn't handle the exceptions, and let them hit the user.
        # However we need to do more work in MccsTile before that. I'd like to get
        # to a situation where MccsTile returns ResultCode.FAILED if we're OK with
        # the failure (e.g failed to acquire lock), but raises an exception to us if
        # something really janky happened, which should be sent straight to the user.
        def _run_while_handling_errors(
            proxy: MccsDeviceProxy,
        ) -> tuple[list[ResultCode], list[Optional[str]]]:
            try:
                return proxy.command_inout(
                    command_name,
                    *command_args,
                )
            except Exception as e:
                self.logger.error(
                    f"Error running {command_name} on {proxy.dev_name()}: {e}"
                )
                return [ResultCode.FAILED], [
                    f"Command raised {str(type(e))}, check logs."
                ]

        commands_to_execute = [
            (_run_while_handling_errors, dev._proxy)
            for dev in self._tile_proxies.values()
            if dev._proxy is not None
            and (
                not require_initialised
                or dev._proxy.tileProgrammingState in ["Initialised", "Synchronised"]
            )
            and (
                not require_synchronised
                or dev._proxy.tileProgrammingState in ["Synchronised"]
            )
        ]

        def _build_msg(
            command_name: str,
            base_msg: str,
            require_initialised: bool,
            require_synchronised: bool,
        ) -> str:
            if require_initialised:
                base_msg += f" {command_name} requires Initialised MccsTiles."
            if require_synchronised:
                base_msg += f" {command_name} requires Synchronised MccsTiles."
            return base_msg

        if not commands_to_execute:
            msg = _build_msg(
                command_name,
                f"{command_name} wouldn't be called on any MccsTiles."
                " Check MccsTile adminMode.",
                require_initialised,
                require_synchronised,
            )
            self.logger.error(msg)
            return [ResultCode.REJECTED], [msg]

        if len(commands_to_execute) != len(self._tile_proxies):
            msg = _build_msg(
                command_name,
                f"{command_name} won't be called on all tiles. Will be called on: "
                f"{[proxy.dev_name() for _, proxy in commands_to_execute]}."
                " Check MccsTile adminMode.",
                require_initialised,
                require_synchronised,
            )
            self.logger.warning(msg)

        if not self.excecute_async:
            self.logger.debug(f"Calling {command_name} synchronously.")
            results = [command(proxy) for command, proxy in commands_to_execute]
        else:
            # We'd really prefer to use GreenMode.Asyncio or similar here. This appears
            # to be buggy/unsupported with a tango.DeviceProxy. We'd have to move to a
            # tango.asyncio.DeviceProxy to use that functionality, which would involve a
            # general refactor of SpsStation. So for now we just spin up some threads,
            # and execute each synchronous call in it's own thread manually.
            with ThreadPoolExecutor(max_workers=len(self._tile_proxies)) as executor:
                futures: list[Future] = [
                    executor.submit(command, proxy)
                    for command, proxy in commands_to_execute
                ]
                complete, incomplete = wait(futures, timeout=timeout)
                if incomplete:
                    msg = f"{len(incomplete)} commands failed to complete in time."
                    self.logger.warning(msg)
                    return [ResultCode.FAILED], [msg]
                results = [future.result() for future in complete]

        result_codes, _ = zip(*results)
        self.logger.debug(f"Tiles response from {command_name}: {str(results)}")
        if all(result[0] == ResultCode.OK for result in result_codes):
            return [ResultCode.OK], [f"{command_name} finished OK."]
        return [ResultCode.FAILED], [
            f"{command_name} didn't finish OK. Results: {str(results)}"
        ]
