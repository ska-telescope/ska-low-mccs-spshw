# type: ignore
# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS station device."""

from __future__ import annotations

import functools
import itertools
import json
from typing import Any, Optional, cast

import tango
from ska_control_model import CommunicationStatus, HealthState, PowerState, ResultCode
from ska_low_mccs_common import release
from ska_tango_base.commands import SubmittedSlowCommand
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command, device_property

from ska_low_mccs_spshw.station.station_component_manager import (
    SpsStationComponentManager,
)
from ska_low_mccs_spshw.station.station_health_model import SpsStationHealthModel
from ska_low_mccs_spshw.station.station_obs_state_model import SpsStationObsStateModel

DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]

__all__ = ["SpsStation", "main"]


class SpsStation(SKAObsDevice):
    """An implementation of a station beam Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    TileFQDNs = device_property(dtype=(str,), default_value=[])
    SubrackFQDNs = device_property(dtype=(str,), default_value=[])
    CabinetNetworkAddress = device_property(dtype=(str,), default_value=["10.0.0.0"])

    # ---------------
    # Initialisation
    # ---------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        # We aren't supposed to define initialisation methods for Tango
        # devices; we are only supposed to define an `init_device` method. But
        # we insist on doing so here, just so that we can define some
        # attributes, thereby stopping the linters from complaining about
        # "attribute-defined-outside-init" etc. We still need to make sure that
        # `init_device` re-initialises any values defined in here.
        super().__init__(*args, **kwargs)

        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: SpsStationHealthModel
        self.component_manager: SpsStationComponentManager
        self._obs_state_model: SpsStationObsStateModel

    def init_device(self: SpsStation) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: SpsStation) -> None:
        super()._init_state_model()
        self._obs_state_model = SpsStationObsStateModel(
            self.logger, self._update_obs_state
        )
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SpsStationHealthModel(
            self.SubrackFQDNs,
            self.TileFQDNs,
            self.component_state_changed_callback,
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: SpsStation,
    ) -> SpsStationComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return SpsStationComponentManager(
            self.StationId,
            self.SubrackFQDNs,
            self.TileFQDNs,
            self.CabinetNetworkAddress,
            self.logger,
            self._max_workers,
            self._communication_state_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: SpsStation) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        #
        # Long running commands
        #
        for (command_name, method_name) in [
            ("Initialise", "initialise"),
            ("StartAcquisition", "start_acquisition"),
        ]:
            self.register_command_object(
                command_name,
                SubmittedSlowCommand(
                    command_name,
                    self._command_tracker,
                    self.component_manager,
                    method_name,
                    callback=None,
                    logger=self.logger,
                ),
            )

    # pylint: disable=too-few-public-methods
    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.SpsStation`'s Init command.

        The :py:meth:`~.SpsStation.InitCommand.do` method below is
        called upon :py:class:`~.SpsStation`'s initialisation.
        """

        def do(
            self: SpsStation.InitCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the :py:class:`.SpsStation`.

            :param args: positional args to the component manager method
            :param kwargs: keyword args to the component manager method

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._is_calibrated = False
            self._device._is_programmed = False
            self._device._test_generator_active = False
            self._device._is_beamformer_running = False
            self._device._current_beamformer_table = [[0] * 7] * 48
            self._device._desired_beamformer_table = [[0] * 7] * 48

            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            self._device.set_archive_event("tileProgrammingState", True, False)

            super().do()

            return (ResultCode.OK, "Initialisation complete")

    def is_On_allowed(self: SpsStation) -> bool:
        """
        Check if command `On` is allowed in the current device state.

        :return: ``True`` if the command is allowed
        """
        return self.get_state() in [
            tango.DevState.OFF,
            tango.DevState.STANDBY,
            tango.DevState.ON,
            tango.DevState.UNKNOWN,
            tango.DevState.FAULT,
        ]

    # ----------
    # Callbacks
    # ----------
    def _communication_state_changed(
        self: SpsStation,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    def component_state_changed_callback(
        self: SpsStation,
        state_change: dict[str, Any],
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.
        For the power_state parameter it is implemented here to drive the op_state.
        For the health parameter it is implemented to update the health attribute
        and push change events whenever the HealthModel's evaluated health state
        changes.

        :param state_change: a dict containing the state parameters to be set,
            and new values.
        :param fqdn: fully qualified domain name of the device whos state has changed.
            None if the device is a station.

        :raises ValueError: fqdn not found
        """
        if fqdn is None:
            health_state_changed_callback = self.health_changed
            power_state_changed_callback = self._component_power_state_changed
        else:
            device_family = fqdn.split("/")[1]
            if device_family == "subrack":
                health_state_changed_callback = functools.partial(
                    self._health_model.subrack_health_changed, fqdn
                )
                power_state_changed_callback = functools.partial(
                    self.component_manager._subrack_power_state_changed, fqdn
                )
            elif device_family == "tile":
                health_state_changed_callback = functools.partial(
                    self._health_model.tile_health_changed, fqdn
                )
                power_state_changed_callback = functools.partial(
                    self.component_manager._tile_power_state_changed, fqdn
                )
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to subrack"
                    " or tile"
                )

        if "power_state" in state_change.keys():
            power_state = state_change.get("power_state")
            with self.component_manager.power_state_lock:
                self.component_manager.set_power_state(
                    cast(PowerState, power_state), fqdn=fqdn
                )
                if power_state is not None:
                    power_state_changed_callback(power_state)

        if "health_state" in state_change.keys():
            health = cast(HealthState, state_change.get("health_state"))
            health_state_changed_callback(health)

        if "is_initialised" in state_change.keys():
            is_initialised = cast(bool, state_change.get("is_initialised"))
            self._obs_state_model.is_initialised(is_initialised)

    def _component_power_state_changed(
        self: SpsStation,
        power_state: PowerState,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_state: the power mode of the component.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_state])

    def health_changed(self: SpsStation, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state != health:
            self._health_state = health
            self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="DevBoolean")
    def isCalibrated(self: SpsStation) -> bool:
        """
        Return a flag indicating whether this station is currently calibrated or not.

        :return: a flag indicating whether this station is currently
            calibrated or not.
        """
        return self._is_calibrated

    @attribute(dtype="DevBoolean")
    def isConfigured(self: SpsStation) -> bool:
        """
        Return a flag indicating whether this station is currently configured or not.

        :return: a flag indicating whether this station is currently
            configured or not.
        """
        return self.component_manager._is_configured

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=512,
    )
    def staticTimeDelays(self: SpsStation) -> list[float]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.static_delays

    @staticTimeDelays.write
    def staticTimeDelays(self: SpsStation, delays: list[float]) -> None:
        """
        Set static time delay.

        :param delays: Delay in samples (positive = increase the signal delay)
             to correct for static delay mismathces, e.g. cable length.
             2 values per antenna (pol. X and Y), 32 values per tile, 512 total.
        """
        self.component_manager.static_delays = delays

    @attribute(
        dtype=("DevLong",),
        max_dim_x=512,
    )
    def channeliserRounding(self: SpsStation) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        return self.component_manager.channeliser_truncation

    @channeliserRounding.write
    def channeliserRounding(self: SpsStation, truncation: list[int]) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self.component_manager.channeliser_truncation = truncation

    @attribute(
        dtype=("DevLong",),
        max_dim_x=384,
    )
    def cspRounding(self: SpsStation) -> list[int]:
        """
        CSP formatter rounding.

        Rounding from 16 to 8 bits in final stage of the
        station beamformer, before sending data to CSP.
        Array of (up to) 384 values, one for each logical channel.
        Range 0 to 7, as number of discarded LS bits.

        :return: CSP formatter rounding for each logical channel.
        """
        return self.component_manager.csp_rounding

    @cspRounding.write
    def cspRounding(self: SpsStation, rounding: list[int]) -> None:
        """
        Set CSP formatter rounding.

        :param rounding: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self.component_manager.csp_rounding = rounding

    @attribute(
        dtype=("DevLong",),
        max_dim_x=512,
    )
    def preaduLevels(self: SpsStation) -> list[int]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.preadu_levels

    @preaduLevels.write
    def preaduLevels(self: SpsStation, levels: list[int]) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: attenuator level of preADU channels, one per input
            channel (2 per antenna, 32 per tile, 512 total), in dB
        """
        self.component_manager.preadu_levels = levels

    @attribute(dtype=("DevLong",), max_dim_x=336)
    def beamformerTable(self: SpsStation) -> list[int]:
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
        return list(
            itertools.chain.from_iterable(self.component_manager.beamformer_table)
        )

    @attribute(dtype="DevBoolean")
    def fortyGbNetworkAddress(self: SpsStation) -> str:
        """
        Get 40Gb network address for cabinet subnet.

        :return: IP subnet address
        """
        return self.component_manager.fortyGb_network_address

    @attribute(dtype="DevBoolean")
    def cspIngestAddress(self: SpsStation) -> str:
        """
        Get CSP ingest IP address.

        CSP ingest address and port are set by the SetCspIngest command

        :return: IP net address for CSP ingest port
        """
        return self.component_manager.csp_ingest_address

    @attribute(dtype="DevBoolean")
    def cspIngestPort(self: SpsStation) -> int:
        """
        Get CSP ingest port.

        CSP ingest address and port are set by the SetCspIngest command

        :return: UDP port for the CSP ingest port
        """
        return self.component_manager.csp_ingest_port

    @attribute(dtype="DevBoolean")
    def isProgrammed(self: SpsStation) -> bool:
        """
        Return a flag indicating whether of not the TPM boards are programmed.

        Attribute is False if at least one TPM is not programmed.

        :return: whether of not the TPM boards are programmed
        """
        return self.component_manager.is_programmed()

    @attribute(dtype="DevBoolean")
    def testGeneratorActive(self: SpsStation) -> bool:
        """
        Get the state of the test generator.

        :return: true if the test generator is active in at least one tile
        """
        return self.component_manager.test_generator_active()

    @attribute(dtype="DevBoolean")
    def isBeamformerRunning(self: SpsStation) -> bool:
        """
        Get the state of the test generator.

        :return: true if the test generator is active in at least one tile
        """
        return self.component_manager.is_beamformer_running()

    @attribute(
        dtype="DevVarStringArray",
        max_dim_x=16,
    )
    def tileProgrammingState(self: SpsStation) -> list(str):
        """
        Get the tile programming state.

        :return: a list of strings describing the programming state of the tiles
        """
        return self.component_manager.tile_programming_state()

    @attribute(dtype="DevVarDoubleArray", max_dim_x=512)
    def adcPower(self: SpsStation) -> list[float]:
        """
        Get the ADC RMS input levels for all input signals.

        Returns an array of 2 values (X and Y polarizations) per antenna, 32
        per tile, 512 per station

        :return: the ADC RMS input levels, in ADC units
        """
        return self.component_manager.adc_power()

    @attribute(dtype="DevDoubleArray", dim_x=3)
    def boardTemperaturesSummary(self: SpsStation) -> list[float]:
        """
        Get summary of board temperatures (minimum, average, maximum).

        :returns: minimum, average, maximum board temperatures, in deg Celsius
        """
        return self.component_manager.board_temperature_summary()

    @attribute(dtype="DevDoubleArray", dim_x=3)
    def fpgaTemperaturesSummary(self: SpsStation) -> list[float]:
        """
        Get summary of FPGA temperatures (minimum, average, maximum).

        :returns: minimum, average, maximum board temperatures, in deg Celsius
        """
        return self.component_manager.fpga_temperature_summary()

    @attribute(dtype="DevDoubleArray", dim_x=3)
    def ppsDelaySummary(self: SpsStation) -> list[float]:
        """
        Get summary of PPS delay (minimum, average, maximum).

        :returns: minimum, average, maximum board temperatures, in deg Celsius
        """
        return self.component_manager.pps_delay_summary()

    @attribute(dtype="DevBoolean")
    def sysrefPresentSummary(self: SpsStation) -> bool:
        """
        Get summary of sysrf present status for all tiles.

        :returns: True if SYSREF signal is present in all tiles
        """
        return self.component_manager.sysref_present_summary()

    @attribute(dtype="DevBoolean")
    def pllLockedSummary(self: SpsStation) -> bool:
        """
        Get summary of PLL locked status for all tiles.

        :returns: True if PLL is locked to reference in all tiles
        """
        return self.component_manager.pll_locked_summary()

    @attribute(dtype="DevBoolean")
    def ppsPresentSummary(self: SpsStation) -> bool:
        """
        Get summary of PPS present status for all tiles.

        :returns: True if PPS signal is present in all tiles
        """
        return self.component_manager.pps_present_summary()

    @attribute(dtype="DevBoolean")
    def clockPresentSummary(self: SpsStation) -> bool:
        """
        Get summary of clock present status for all tiles.

        :returns: True if 10 MHz clock signal is present in all tiles
        """
        return self.component_manager.clock_present_summary()

    @attribute(dtype="DevVarULongArray", max_dim_x=32)
    def fortyGbNetworkErrors(self: SpsStation) -> list[int]:
        """
        Get number of network errors for all 40 Gb interfaces.

        :return: Total number of errors on each interface (2 per tile)
        """
        return self.component_manager.forty_gb_network_errors()

    # -------------
    # Slow Commands
    # -------------

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def Initialise(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the station with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/station/001")
            >>> dp.command_inout("Initialise")
        """
        handler = self.get_command_object("Initialise")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def StartAcquisition(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Start the acquisition synchronously for all tiles, checks for synchronisation.

        :param argin: Start acquisition time in ISO9601 format
        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/station/001")
            >>> dp.command_inout("StartAcquisition", "20230101T12:34:55.000Z")
        """
        handler = self.get_command_object("StartAcquisition")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    # -------------
    # Fast Commands
    # -------------

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SetLmcDownload(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param argin: json dictionary with optional keywords:

            * mode - (string) '1g' or '10g' (Mandatory) (use '10g' for 40g also)
            * payload_length - (int) SPEAD payload length for channel data
            * destination_ip - (string) Destination IP.
            * source_port - (int) Source port for integrated data streams
            * destination_port - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"mode": "1g", "payload_length":1024,"destination_ip"="10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        params = json.loads(argin)
        mode = params.get("mode", "40G")

        if mode == "40g" or mode == "40G":
            mode = "10g"
        payload_length = params.get("payload_length", None)
        if payload_length is None:
            if mode == "10g" or mode == "10G":
                payload_length = 8192
            else:
                payload_length = 1024
        dst_ip = params.get("destination_ip", None)
        src_port = params.get("source_port", 0xF0D0)
        dst_port = params.get("destination_port", 4660)

        self.component_manager.set_lmc_download(
            mode, payload_length, dst_ip, src_port, dst_port
        )
        return ([ResultCode.OK], ["SetLmcDownload command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SetLmIntegratedcDownload(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Configure link and size for integrated data packets, for all tiles.

        :param argin: json dictionary with optional keywords:

            * mode - (string) '1g' '10g' '40g' - default 40g
            * channel_payload_lenth - (int) SPEAD payload length for integrated
                 channel data
            * beam_payload_length - (int) SPEAD payload length for integrated beam data
            * destination_ip - (string) Destination IP
            * source_port - (int) Source port for integrated data streams
            * destination_port - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"mode": "1G", "channel_payload_lenth":4,
                    "beam_payload_length": 1024, "destination_ip"="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        params = json.loads(argin)
        mode = params.get("mode", "40G")

        if mode == "40g" or mode == "40G":
            mode = "10g"
        channel_payload_length = params.get("channel_payload_lenth", 1024)
        beam_payload_length = params.get("beam_payload_length", 1024)
        dst_ip = params.get("destination_ip", None)
        src_port = params.get("source_port", 0xF0D0)
        dst_port = params.get("destination_port", 4660)

        self.component_manager.set_lmc_integrated_download(
            mode,
            channel_payload_length,
            beam_payload_length,
            dst_ip,
            src_port,
            dst_port,
        )
        return ([ResultCode.OK], ["SetLmcIntegratedDownload command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SetCspIngest(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Configure link for beam data packets to CSP.

        :param argin: json dictionary with optional keywords:

            * destination_ip - (string) Destination IP
            * source_port - (int) Source port for integrated data streams
            * destination_port - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"destination_ip"="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetCspIngest", jstr)
        """
        params = json.loads(argin)
        dst_ip = params.get("destination_ip", None)
        src_port = params.get("source_port", 0xF0D0)
        dst_port = params.get("destination_port", 4660)

        self.component_manager.set_csp_ingest(
            dst_ip,
            src_port,
            dst_port,
        )
        return ([ResultCode.OK], ["SetCspIngest command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SetBeamFormerRegions(
        self: SpsStation, argin: list(int)
    ) -> DevVarLongStringArrayType:
        """
        Set the frequency regions which are going to be beamformed into each beam.

        region_array is defined as a flattened 2D array, for a maximum of 48 regions.
        Total number of channels must be <= 384.

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel, must be even in range 0 to 510
        * num_channels - (int) size of the region, must be a multiple of 8
        * beam_index - (int) beam used for this region with range 0 to 47
        * subarray_id - (int) Subarray
        * subarray_logical_channel - (int) logical channel # in the subarray
        * subarray_beam_id - (int) ID of the subarray beam
        * substation_id - (int) Substation
        * aperture_id:  ID of the aperture (station*100+substation?)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: if parameters are illegal or inconsistent

        :example:

        >>> regions = [[4, 24, 0, 0, 0, 3, 1, 101], [26, 40, 1, 0, 24, 4, 2, 102]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        if len(argin) < 8:
            self.logger.error("Insufficient parameters specified")
            raise ValueError("Insufficient parameters specified")
        if len(argin) > (48 * 8):
            self.logger.error("Too many regions specified")
            raise ValueError("Too many regions specified")
        if len(argin) % 8 != 0:
            self.logger.error(
                "Incomplete specification of region. Regions specified by 8 values"
            )
            raise ValueError("Incomplete specification of region")
        regions = []
        total_chan = 0
        for i in range(0, len(argin), 8):
            region = argin[i : i + 8]  # noqa: E203
            start_channel = region[0]
            if start_channel % 2 != 0:
                self.logger.error("Start channel in region must be even")
                raise ValueError("Start channel in region must be even")
            nchannels = region[1]
            if nchannels % 8 != 0:
                self.logger.error("Nos. of channels in region must be multiple of 8")
                raise ValueError("Nos. of channels in region must be multiple of 8")
            beam_index = region[2]
            if beam_index < 0 or beam_index > 47:
                self.logger.error("Beam_index is out side of range 0-47")
                raise ValueError("Beam_index is out side of range 0-47")
            total_chan += nchannels
            if total_chan > 384:
                self.logger.error("Too many channels specified > 384")
                raise ValueError("Too many channels specified > 384")
            regions.append(region)
        self.component_manager.set_beamformer_regions(argin)
        # handler = self.get_command_object("SetBeamformerRegions")
        # (return_code, message) = handler(argin)
        return ([ResultCode.OK], ["SetBeamFormerRegions command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def LoadCalibrationCoefficients(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Load the calibration coefficients, but does not apply them.

        This is performed by apply_calibration.
        The calibration coefficients may include any rotation
        matrix (e.g. the parallactic angle), but do not include the geometric delay.

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * calibration_coefficients - [array] a bidimensional complex array comprising
            calibration_coefficients[channel, polarization], with each element
            representing a normalized coefficient, with (1.0, 0.0) being the
            normal, expected response for an ideal antenna.

            * channel - (int) channel is the index specifying the channels at the
                              beamformer output, i.e. considering only those channels
                              actually processed and beam assignments.
            * polarization index ranges from 0 to 3.

                * 0: X polarization direct element
                * 1: X->Y polarization cross element
                * 2: Y->X polarization cross element
                * 3: Y polarization direct element

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :raises ValueError: if parameters are illegal or inconsistent

        :example:

        >>> antenna = 2
        >>> complex_coefficients = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = ([v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(antenna))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalibrationCoefficients", input)
        """
        if len(argin) < 9:
            self.logger.error("Insufficient calibration coefficients")
            raise ValueError("Insufficient calibration coefficients")
        if len(argin[1:]) % 8 != 0:
            self.logger.error(
                "Incomplete specification of coefficient. "
                "Needs 8 values (4 complex Jones) per channel"
            )
            raise ValueError("Incomplete specification of coefficient")

        self.component_manager.load_calibration_coefficients(argin)

        # handler = self.get_command_object("LoadCalibrationCoefficients")
        # (return_code, message) = handler(argin)
        return ([ResultCode.OK], ["LoadCalibrationCoefficients command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def ApplyCalibration(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Load the calibration coefficients at the specified time delay.

        :param argin: switch time, in ISO formatted time. Default: now

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ApplyCalibration", "")
        """
        switch_time = argin

        self.component_manager.apply_calibration(switch_time)
        return ([ResultCode.OK], ["ApplyCalibration command completed OK"])
        # handler = self.get_command_object("ApplyCalibration")
        # (return_code, message) = handler(argin)
        # return ([return_code], [message])

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    def LoadPointingDelays(
        self: SpsStation, argin: list[float]
    ) -> DevVarLongStringArrayType:
        """
        Set the pointing delay parameters of this Station's Tiles.

        :param argin: an array containing a beam index followed by antenna delays

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :raises ValueError: if parameters are illegal or inconsistent

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("LoadPointingDelays", delay_list)
        """
        if len(argin) < self._antennas_per_tile * 2 + 1:
            self._component_manager.logger.error("Insufficient parameters")
            raise ValueError("Insufficient parameters")
        beam_index = int(argin[0])
        if beam_index < 0 or beam_index > 7:
            self._component_manager.logger.error("Invalid beam index")
            raise ValueError("Invalid beam index")

        self.component_manager.load_pointing_delays(argin)
        return ([ResultCode.OK], ["LoadPointingDelays command completed OK"])
        # handler = self.get_command_object("LoadPointingDelays")
        # (return_code, message) = handler(argin)
        # return ([return_code], [message])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def ApplyPointingDelays(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Set the pointing delay parameters of this Station's Tiles.

        :param argin: switch time, in ISO formatted time. Default: now

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> time_string = switch time as ISO formatted time
        >>> dp.command_inout("ApplyPointingDelays", time_string)
        """
        self.component_manager.apply_pointing_delays(argin)
        return ([ResultCode.OK], ["LoadPointingDelays command completed OK"])
        # handler = self.get_command_object("ApplyPointingDelays")
        # (return_code, message) = handler(argin)
        # return ([return_code], [message])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def StartBeamformer(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Start the beamformer at the specified time delay.

        :param argin: json dictionary with optional keywords:

        * start_time - (str, ISO UTC time) start time
        * duration - (int) if > 0 is a duration in seconds
               if < 0 run forever
        * subarray_beam_id - (int) : Subarray beam ID of the channels to be started
                Command affects only beamformed channels for given subarray ID
                Default -1: all channels
        * scan_id - (int) The unique ID for the started scan. Default 0

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime": "2022-01-02T34:56:08.987Z", "Duration": 30.0}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """
        params = json.loads(argin)
        start_time = params.get("start_time", None)
        duration = params.get("duration", -1)
        subarray_beam_id = params.get("subarray_beam_id", -1)
        scan_id = params.get("scan_id", 0)
        self._component_manager.start_beamformer(
            start_time, duration, subarray_beam_id, scan_id
        )
        return ([ResultCode.OK], ["StartBeamformer command completed OK"])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def StopBeamformer(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        self.component_manager.stop_beamformer()
        return ([ResultCode.OK], ["StopBeamformer command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def ConfigureIntegratedChannelData(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Configure and start the transmission of integrated channel data.

        Using the provided integration time, first channel and last channel.
        Data are sent continuously until the StopIntegratedData command is run.

        :param argin: json dictionary with optional keywords:

        * integration_time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 511

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"integration_time": 0.2, "first_channel":0, "last_channel": 191}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureIntegratedChannelData", jstr)
        """
        params = json.loads(argin)
        integration_time = params.get("integration_time", 0.5)
        first_channel = params.get("first_channel", 0)
        last_channel = params.get("last_channel", 511)

        self.component_manager.configure_integrated_channel_data(
            integration_time, first_channel, last_channel
        )
        return (
            [ResultCode.OK],
            ["ConfigureIntegratedChannelData command completed OK"],
        )

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def ConfigureIntegratedBeamData(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Configure the transmission of integrated beam data.

        Using the provided integration time, the first channel and the last channel.
        The data are sent continuously until the StopIntegratedData command is run.

        :param argin: json dictionary with optional keywords:

        * integration_time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 191

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"integration_time": 0.2, "first_channel":0, "last_channel": 191}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("ConfigureIntegratedBeamData", jstr)
        """
        params = json.loads(argin)
        integration_time = params.get("integration_time", 0.5)
        first_channel = params.get("first_channel", 0)
        last_channel = params.get("last_channel", 191)

        self.component_manager.configure_integrated_beam_data(
            integration_time, first_channel, last_channel
        )
        return ([ResultCode.OK], ["ConfigureIntegratedBeamData command completed OK"])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def StopIntegratedData(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Stop the integrated  data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.component_manager.stop_integrated_data()
        return ([ResultCode.OK], ["StopIntegratedData command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SendDataSamples(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Transmit a snapshot containing raw antenna data.

        :param argin: json dictionary with optional keywords:

        * data_type - type of snapshot data (mandatory): "raw", "channel",
                    "channel_continuous", "narrowband", "beam"
        * start_time - Time (UTC string) to start sending data. Default immediately
        * seconds - (float) Delay if timestamp is not specified. Default 0.2 seconds

        Depending on the data type:
        raw:

        * sync: bool: send synchronised samples for all antennas, vs. round robin
                larger snapshot from each antenna

        channel:

        * n_samples: Number of samples per channel, default 1024
        * first_channel - (int) first channel to send, default 0
        * last_channel - (int) last channel to send, default 511

        channel_continuous

        * channel_id - (int) channel_id (Mandatory)
        * n_samples -  (int) number of samples to send per packet, default 128

        narrowband:

        * frequency - (int) Sky frequency for band centre, in Hz (Mandatory)
        * round_bits - (int)  Specify whow many bits to round
        * n_samples -  (int) number of spectra to send

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises ValueError: if mandatory parameters are missing

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"data_type": "raw", "Sync":True, "Seconds": 0.2}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendDataSamples", jstr)
        """
        params = json.loads(argin)

        # Check for mandatory parameters and syntax.
        # argin is left as is and forwarded to tiles
        data_type = params.get("data_type", None)
        if data_type is None:
            self._component_manager.logger.error("data_type is a mandatory parameter")
            raise ValueError("data_type is a mandatory parameter")
        if data_type not in [
            "raw",
            "channel",
            "channel_continuous",
            "narrowband",
            "beam",
        ]:
            self._component_manager.logger.error("Invalid data_type specified")
            raise ValueError("Invalid data_type specified")
        if data_type == "channel_continuous":
            channel_id = params.get("channel_id", None)
            if channel_id is None:
                self._component_manager.logger.error(
                    "channel_id is a mandatory parameter"
                )
                raise ValueError("channel_id is a mandatory parameter")
            if channel_id < 1 or channel_id > 511:
                self._component_manager.logger.error(
                    "channel_id must be between 1 and 511"
                )
                raise ValueError("channel_id must be between 1 and 511")
        if data_type == "narrowband":
            frequency = params.get("frequency", None)
            if frequency is None:
                self._component_manager.logger.error(
                    "frequency is a mandatory parameter"
                )
                raise ValueError("frequency is a mandatory parameter")
            if frequency < 1e6 or frequency > 390e6:
                self._component_manager.logger.error(
                    "frequency must be between 1 and 390 MHz"
                )
                raise ValueError("frequency must be between 1 and 390 MHz")
        self.component_manager.send_data_samples(argin)
        return ([ResultCode.OK], ["SendDataSamples command completed OK"])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def StopDataTransmission(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Stop data transmission from board.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        self.component_manager.stop_data_transmission()
        return ([ResultCode.OK], ["StopDataTransmission command completed OK"])


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return SpsStation.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
