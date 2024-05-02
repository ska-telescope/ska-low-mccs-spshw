# pylint: disable=too-many-lines, too-many-public-methods
#
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS station device."""

from __future__ import annotations

import ipaddress
import itertools
import json
import sys
from functools import wraps
from typing import Any, Callable, Optional, cast

import numpy as np
import tango
from numpy import ndarray
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
)
from ska_tango_base import SKABaseDevice
from ska_tango_base.commands import JsonValidator, SubmittedSlowCommand
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command, device_property

from ..version import version_info
from .station_component_manager import SpsStationComponentManager
from .station_health_model import SpsStationHealthModel
from .station_obs_state_model import SpsStationObsStateModel

DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]

__all__ = ["SpsStation", "main"]


def engineering_mode_required(func: Callable) -> Callable:
    """
    Return a decorator for engineering only commands.

    :param func: the command which is engineering mode only.

    :returns: decorator to check for engineering mode before running command.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> DevVarLongStringArrayType:
        device: SKABaseDevice = args[0]
        if device._admin_mode != AdminMode.ENGINEERING:
            return (
                [ResultCode.REJECTED],
                [
                    f"Device in adminmode {device._admin_mode.name}, "
                    "this command requires engineering."
                ],
            )
        return func(*args, **kwargs)

    return wrapper


# pylint: disable=too-many-instance-attributes
class SpsStation(SKAObsDevice):
    """An implementation of an  SPS Station Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    TileFQDNs = device_property(dtype=(str,), default_value=[])
    SubrackFQDNs = device_property(dtype=(str,), default_value=[])

    # IP address and mask of first interface in allocated block for science data,
    # using CIDR-style slash notation.
    # e.g. "10.130.0.1/25" means "address 10.130.0.1 on network 10.130.0.0/25"
    SdnFirstInterface = device_property(dtype=str)
    SdnGateway = device_property(dtype=str, default_value="")
    CspIngestIp = device_property(dtype=str, default_value="")

    DaqTRL = device_property(dtype=str, default_value="")
    AntennaConfigURI = device_property(
        dtype=(str,),
        default_value=[],
    )

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
        self._adc_power: Optional[list[float]] = None

    def init_device(self: SpsStation) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
        version = f"{device_name} Software Version: {self._version_id}"
        properties = (
            f"Initialised {device_name} device with properties:\n"
            f"\tStationId: {self.StationId}\n"
            f"\tTileFQDNs: {self.TileFQDNs}\n"
            f"\tDaqTRL: {self.DaqTRL}\n"
            f"\tSubrackFQDNs: {self.SubrackFQDNs}\n"
            f"\tSdnFirstInterface: {self.SdnFirstInterface}\n"
            f"\tSdnGateway: {self.SdnGateway}\n"
            f"\tCspIngestIp: {self.CspIngestIp}\n"
            f"\tAntennaConfigURI: {self.AntennaConfigURI}\n"
        )
        self.logger.info(
            "\n%s\n%s\n%s", str(self.GetVersionInfo()), version, properties
        )

    def _init_state_model(self: SpsStation) -> None:
        super()._init_state_model()
        self._obs_state_model = SpsStationObsStateModel(
            self.logger, self._update_obs_state
        )
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SpsStationHealthModel(
            self.SubrackFQDNs,
            self.TileFQDNs,
            self._health_changed,
        )
        self.set_change_event("healthState", True, False)

        # pylint: disable=attribute-defined-outside-init
        self._x_bandpass_data: np.ndarray = np.zeros(shape=(256, 512), dtype=float)
        # pylint: disable=attribute-defined-outside-init
        self._y_bandpass_data: np.ndarray = np.zeros(shape=(256, 512), dtype=float)

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
            self.DaqTRL,
            ipaddress.IPv4Interface(self.SdnFirstInterface),
            ipaddress.IPv4Address(self.SdnGateway) if self.SdnGateway else None,
            ipaddress.IPv4Address(self.CspIngestIp) if self.CspIngestIp else None,
            self.AntennaConfigURI,
            self.logger,
            self._max_workers,
            self._communication_state_changed,
            self._component_state_changed,
            self._health_model.tile_health_changed,
            self._health_model.subrack_health_changed,
        )

    def init_command_objects(self: SpsStation) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        #
        # Long running commands
        #

        run_test_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "test_name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["test_name"],
        }

        for command_name, method_name, schema in [
            ("Initialise", "initialise", None),
            ("StartAcquisition", "start_acquisition", None),
            ("AcquireDataForCalibration", "acquire_data_for_calibration"),
            ("TriggerAdcEqualisation", "trigger_adc_equalisation", None),
            ("SetChanneliserRounding", "set_channeliser_rounding", None),
            ("SelfCheck", "self_check", None),
            ("RunTest", "run_test", run_test_schema),
        ]:
            validator = (
                None
                if schema is None
                else JsonValidator(
                    command_name,
                    schema,
                    logger=self.logger,
                )
            )

            self.register_command_object(
                command_name,
                SubmittedSlowCommand(
                    command_name,
                    self._command_tracker,
                    self.component_manager,
                    method_name,
                    callback=None,
                    logger=self.logger,
                    validator=validator,
                ),
            )

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

            self._device._build_state = ",".join(
                [
                    version_info["name"],
                    version_info["version"],
                    version_info["description"],
                ]
            )
            self._device._version_id = version_info["version"]

            self._device.set_change_event("xPolBandpass", True, False)
            self._device.set_change_event("yPolBandpass", True, False)
            self._device.set_change_event("antennaInfo", True, False)

            self._device.set_archive_event("xPolBandpass", True, False)
            self._device.set_archive_event("yPolBandpass", True, False)
            self._device.set_archive_event("antennaInfo", True, False)
            self._device.set_archive_event("tileProgrammingState", True, False)
            self._device.set_change_event("adcPower", True, False)
            self._device.set_archive_event("adcPower", True, False)

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

    def is_Standby_allowed(self: SpsStation) -> bool:
        """
        Check if command `Standby` is allowed in the current device state.

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
        super()._communication_state_changed(communication_state)
        self._health_model.update_state(
            communicating=(communication_state == CommunicationStatus.ESTABLISHED)
        )

    # TODO: Upstream this interface change to SKABaseDevice
    # pylint: disable-next=arguments-differ
    def _component_state_changed(  # type: ignore[override]
        self: SpsStation,
        *,
        fault: Optional[bool] = None,
        power: Optional[PowerState] = None,
        **state_change: Any,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param fault: whether the component is in fault or not
        :param power: the power state of the component
        :param state_change: other state updates
        """
        bandpass_data_shape = (256, 512)
        super()._component_state_changed(fault=fault, power=power)
        self._health_model.update_state(fault=fault, power=power)

        # Helper function to *expand* a numpy array to a shape and pad with zeros.
        def to_shape(a: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
            y_, x_ = shape
            y, x = a.shape
            y_pad = y_ - y
            x_pad = x_ - x
            return np.pad(
                a,
                (
                    (y_pad // 2, y_pad // 2 + y_pad % 2),
                    (x_pad // 2, x_pad // 2 + x_pad % 2),
                ),
                mode="constant",
            )

        if "is_configured" in state_change:
            is_configured = cast(bool, state_change.get("is_configured"))
            self._obs_state_model.is_configured_changed(is_configured)
        if "adc_power" in state_change:
            self._adc_power = state_change.get("adc_power")
            self.push_change_event("adcPower", self._adc_power)
            self.push_archive_event("adcPower", self._adc_power)

        if "xPolBandpass" in state_change:
            x_bandpass_data = state_change.get("xPolBandpass")
            if isinstance(x_bandpass_data, np.ndarray):
                x_pol_bandpass_ordered: np.ndarray = np.zeros(
                    shape=bandpass_data_shape, dtype=float
                )
                try:
                    # Resize data to match attr.
                    x_bandpass_data = to_shape(x_bandpass_data, bandpass_data_shape)
                    # Change bandpass data from port order to antenna order.
                    x_pol_bandpass_ordered = (
                        self.component_manager._port_to_antenna_order(
                            self.component_manager._antenna_mapping, x_bandpass_data
                        )
                    )
                    # pylint: disable=attribute-defined-outside-init
                    self._x_bandpass_data = x_pol_bandpass_ordered
                    self.push_change_event("xPolBandpass", x_pol_bandpass_ordered)
                    self.push_archive_event("xPolBandpass", x_pol_bandpass_ordered)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.error(
                        f"Caught exception setting station X bandpass:\n {e}"
                    )
            else:
                self.logger.error(
                    "X polarised bandpass data has incorrect format.\
                        Expected np.ndarray, got %s",
                    type(x_bandpass_data),
                )

        if "yPolBandpass" in state_change:
            y_bandpass_data = state_change.get("yPolBandpass")
            if isinstance(y_bandpass_data, np.ndarray):
                y_pol_bandpass_ordered: np.ndarray = np.zeros(
                    shape=bandpass_data_shape, dtype=float
                )
                try:
                    # Resize data to match attr.
                    y_bandpass_data = to_shape(y_bandpass_data, bandpass_data_shape)
                    # Change bandpass data from port order to antenna order.
                    y_pol_bandpass_ordered = (
                        self.component_manager._port_to_antenna_order(
                            self.component_manager._antenna_mapping, y_bandpass_data
                        )
                    )
                    # pylint: disable=attribute-defined-outside-init
                    self._y_bandpass_data = y_pol_bandpass_ordered
                    self.push_change_event("yPolBandpass", y_pol_bandpass_ordered)
                    self.push_archive_event("yPolBandpass", y_pol_bandpass_ordered)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.error(
                        f"Caught exception setting station Y bandpass:\n {e}"
                    )
            else:
                self.logger.error(
                    "Y polarised bandpass data has incorrect format. \
                    Expected np.ndarray, got %s",
                    type(y_bandpass_data),
                )

    def _health_changed(self: SpsStation, health: HealthState) -> None:
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

    @attribute(
        dtype=(("DevFloat",),),
        max_dim_x=512,  # Channels
        max_dim_y=256,  # Antennas
    )
    def xPolBandpass(self: SpsStation) -> np.ndarray:
        """
        Read the last bandpass plot data for the x-polarisation.

        :return: The last block of x-polarised bandpass data.
        """
        return self._x_bandpass_data

    @attribute(
        dtype=(("DevFloat",),),
        max_dim_x=512,  # Channels
        max_dim_y=256,  # Antennas
    )
    def yPolBandpass(self: SpsStation) -> np.ndarray:
        """
        Read the last bandpass plot data for the y-polarisation.

        :return: The last block of y-polarised bandpass data.
        """
        return self._y_bandpass_data

    @attribute(dtype=str)
    def daqTRL(self: SpsStation) -> str:
        """
        Report the Tango Resource Locator for this SpsStation's DAQ instance.

        :return: Return the current DAQ TRL.
        """
        return self.DaqTRL

    @daqTRL.write  # type: ignore[no-redef]
    def daqTRL(self: SpsStation, value: str) -> None:
        """
        Set the Tango Resource Locator for this SpsStation's DAQ instance.

        :param value: The new DAQ TRL.
        """
        self.DaqTRL = value
        self.component_manager._daq_trl = value

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

    @attribute(dtype="DevString")
    def antennasMapping(self: SpsStation) -> str:
        """
        Return the mappings of the antennas.

        Returns a mapping of antenna number to
            TPM port number.

        :return: json string containing antenna mappings
        """
        return json.dumps(self.component_manager._antenna_mapping)

    @attribute(dtype="DevString")
    def antennaInfo(self: SpsStation) -> str:
        """
        Return antenna information.

        Returns a json string representing a dictionary coded
            by antenna number and presenting that antenna's
            station_id, tile_id and location information.

        :return: json string containing antenna information.
        """
        return json.dumps(self.component_manager._antenna_info)

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

    @staticTimeDelays.write  # type: ignore[no-redef]
    def staticTimeDelays(self: SpsStation, delays: list[float]) -> None:
        """
        Set static time delay.

        :param delays: Delay in samples (positive = increase the signal delay)
             to correct for static delay mismathces, e.g. cable length.
             2 values per antenna (pol. X and Y), 32 values per tile, 512 total.
        """
        self.component_manager.static_delays = delays

    @attribute(
        dtype=(("DevLong",),),
        max_dim_x=512,  # Channels
        max_dim_y=16,  # Tiles
    )
    def channeliserRounding(self: SpsStation) -> ndarray:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: A list of 512 values for every tile, one per channel.
        """
        return self.component_manager.channeliser_rounding

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

    @cspRounding.write  # type: ignore[no-redef]
    def cspRounding(self: SpsStation, rounding: list[int]) -> None:
        """
        Set CSP formatter rounding.

        :param rounding: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self.component_manager.csp_rounding = rounding

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=512,
    )
    def preaduLevels(self: SpsStation) -> list[float]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.preadu_levels

    @preaduLevels.write  # type: ignore[no-redef]
    def preaduLevels(self: SpsStation, levels: list[float]) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: attenuator level of preADU channels, one per input
            channel (2 per antenna, 32 per tile, 512 total), in dB
        """
        self.component_manager.preadu_levels = levels

    @attribute(
        dtype=("DevLong",),
        max_dim_x=16,
    )
    def ppsDelays(self: SpsStation) -> list[int]:
        """
        Get PPS delay correction, one per tile.

        :return: Array of PPS delay in nanoseconds, one value per tile.
        """
        return self.component_manager.pps_delays

    @attribute(
        dtype=("DevLong",),
        max_dim_x=16,
    )
    def ppsDelayCorrections(self: SpsStation) -> list[int]:
        """
        Return PPS delay correction, one per tile.

        :return: Array of PPS delay correction in nanoseconds, one value per tile.
        """
        return self.component_manager.pps_delay_corrections

    @ppsDelayCorrections.write  # type: ignore[no-redef]
    def ppsDelayCorrections(self: SpsStation, delays: list[int]) -> None:
        """
        Set PPS delay correction, one per tile.

        Note: this will be set in the next initialisation.

        :param delays: PPS delay correction in nanoseconds, one value per tile.
            Values are internally rounded to 1.25 ns units.
        """
        self.component_manager.pps_delay_corrections = delays

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

    @attribute(dtype="DevString")
    def fortyGbNetworkAddress(self: SpsStation) -> str:
        """
        Get 40Gb network address for this station.

        :return: IP subnet address
        """
        return self.component_manager.forty_gb_network_address

    @attribute(dtype="DevString")
    def cspIngestAddress(self: SpsStation) -> str:
        """
        Get CSP ingest IP address.

        CSP ingest address and port are set by the SetCspIngest command

        :return: IP net address for CSP ingest port
        """
        return self.component_manager.csp_ingest_address

    @attribute(dtype="DevLong")
    def cspIngestPort(self: SpsStation) -> int:
        """
        Get CSP ingest port.

        CSP ingest address and port are set by the SetCspIngest command

        :return: UDP port for the CSP ingest port
        """
        return self.component_manager.csp_ingest_port

    @attribute(dtype="DevLong")
    def cspSourcePort(self: SpsStation) -> int:
        """
        Get CSP source port.

        CSP source port is set by the SetCspIngest command

        :return: UDP port for the CSP source port
        """
        return self.component_manager.csp_source_port

    @attribute(dtype="DevBoolean")
    def isProgrammed(self: SpsStation) -> bool:
        """
        Return a flag indicating whether of not the TPM boards are programmed.

        Attribute is False if at least one TPM is not programmed.

        :return: whether of not the TPM boards are programmed
        """
        return self.component_manager.is_programmed

    @attribute(dtype="DevBoolean")
    def testGeneratorActive(self: SpsStation) -> bool:
        """
        Get the state of the test generator.

        :return: true if the test generator is active in at least one tile
        """
        return self.component_manager.test_generator_active

    @attribute(dtype="DevBoolean")
    def isBeamformerRunning(self: SpsStation) -> bool:
        """
        Get the state of the test generator.

        :return: true if the test generator is active in at least one tile
        """
        return self.component_manager.is_beamformer_running

    @attribute(dtype=("DevString",), max_dim_x=16)
    def tileProgrammingState(self: SpsStation) -> list[str]:
        """
        Get the tile programming state.

        :return: a list of strings describing the programming state of the tiles
        """
        return self.component_manager.tile_programming_state()

    @attribute(dtype=("DevDouble",), max_dim_x=512)
    def adcPower(self: SpsStation) -> list[float] | None:
        """
        Get the ADC RMS input levels for all input signals.

        Returns an array of 2 values (X and Y polarizations) per antenna, 32
        per tile, 512 per station

        :return: the ADC RMS input levels, in ADC units
        """
        return self._adc_power

    @attribute(dtype=("DevDouble",), max_dim_x=3)
    def boardTemperaturesSummary(self: SpsStation) -> list[float]:
        """
        Get summary of board temperatures (minimum, average, maximum).

        :returns: minimum, average, maximum board temperatures, in deg Celsius
        """
        return self.component_manager.board_temperature_summary()

    @attribute(dtype=("DevDouble",), max_dim_x=3)
    def fpgaTemperaturesSummary(self: SpsStation) -> list[float]:
        """
        Get summary of FPGA temperatures (minimum, average, maximum).

        :returns: minimum, average, maximum board temperatures, in deg Celsius
        """
        return self.component_manager.fpga_temperature_summary()

    @attribute(dtype=("DevDouble",), max_dim_x=3)
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

    @attribute(dtype=("DevLong",), max_dim_x=32)
    def fortyGbNetworkErrors(self: SpsStation) -> list[int]:
        """
        Get number of network errors for all 40 Gb interfaces.

        :return: Total number of errors on each interface (2 per tile)
        """
        return self.component_manager.forty_gb_network_errors()

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def healthModelParams(self: SpsStation) -> str:
        """
        Get the health params from the health model.

        :return: the health params
        """
        return json.dumps(self._health_model.health_params)

    @healthModelParams.write  # type: ignore[no-redef]
    def healthModelParams(self: SpsStation, argin: str) -> None:
        """
        Set the params for health transition rules.

        :param argin: JSON-string of dictionary of health states
        """
        self._health_model.health_params = json.loads(argin)

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def testLogs(self: SpsStation) -> str:
        """
        Get logs of the most recently run self-check test.

        :return: the logs of the most recently run self-check test.
        """
        return self.component_manager.test_logs

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def testReport(self: SpsStation) -> str:
        """
        Get the report for the most recently run self-check test set.

        :return: the report for the most recently run self-check test set.
        """
        return self.component_manager.test_report

    @attribute(dtype=("DevString",), format="%s", max_dim_x=32)
    def testList(self: SpsStation) -> list[str]:
        """
        Get the list of self-check tests available.

        :return: the list of self-check tests available.
        """
        return self.component_manager.test_list

    # -------------
    # Slow Commands
    # -------------

    @command(
        dtype_in="DevVoid",
        dtype_out="DevVarLongStringArray",
    )
    def Initialise(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Initialise the station.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/station/001")
            >>> dp.command_inout("Initialise")
        """
        handler = self.get_command_object("Initialise")
        (return_code, message) = handler()
        return ([return_code], [message])

    @command(dtype_in=("DevLong",), dtype_out="DevVarLongStringArray")
    def SetChanneliserRounding(
        self: SpsStation, channeliser_rounding: ndarray
    ) -> DevVarLongStringArrayType:
        """
        Set the ChanneliserRounding to all Tiles in this Station.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :param channeliser_rounding: list of 512 values, one per channel.
            this will apply to all Tiles in this station.
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("low-mccs/station/aavs3")
            >>> dp.command_inout("SetChanneliserRounding", np.array([2]*512))
        """
        handler = self.get_command_object("SetChanneliserRounding")
        (return_code, message) = handler(channeliser_rounding)
        return ([return_code], [message])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def StartAcquisition(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Start the acquisition synchronously for all tiles, checks for synchronisation.

        If a start time isn't given, it will default to 'now'.

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

    @command(
        dtype_in="DevLong",
        dtype_out="DevVarLongStringArray",
    )
    def AcquireDataForCalibration(self: SpsStation, channel: int) -> DevVarLongStringArrayType:
        """
        Start acquiring data for calibration.

        :param channel: channel to calibrate for
        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("low-mccs/station/ci-1")
            >>> dp.command_inout("AcquireDataForCalibration", 153)
        """
        handler = self.get_command_object("AcquireDataForCalibration")
        (return_code, message) = handler(channel)
        return ([return_code], [message])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def TriggerAdcEqualisation(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Get the equalised ADC values.

        Getting the equalised values takes up to 20 seconds (to get an average to
        avoid spikes). So we trigger the collection and publish to dbmPowers

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/station/001")
            >>> dp.command_inout("TriggerAdcEqualisation")
        """
        handler = self.get_command_object("TriggerAdcEqualisation")
        (return_code, message) = handler()
        return ([return_code], [message])

    @engineering_mode_required
    @command(
        dtype_out="DevVarLongStringArray",
    )
    def SelfCheck(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Run all the self-check tests once.

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("low-mccs/spsstation/aavs3")
            >>> dp.SelfCheck()
        """
        handler = self.get_command_object("SelfCheck")
        (return_code, message) = handler()
        return ([return_code], [message])

    @engineering_mode_required
    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def RunTest(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Run a self-check test and optional amount of times.

        :param argin: json-ified args, containing a required 'test_name', and optional
            'count'

        :return: A tuple containing a return code and a string message indicating
            status. The message is for information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("low-mccs/spsstation/aavs3")
            >>> dp.RunTest(json.dumps({"test_name" : "my_test", "count" : 5}))
        """
        test_name = json.loads(argin)["test_name"]
        if test_name not in self.component_manager.test_list:
            return (
                [ResultCode.REJECTED],
                [
                    f"{test_name} not in available tests: "
                    f"{self.component_manager.test_list}"
                ],
            )

        handler = self.get_command_object("RunTest")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    @command(
        dtype_in="DevString",
        dtype_out="DevString",
    )
    def DescribeTest(self: SpsStation, test_name: str) -> str:
        """
        Fetch the docstring of a given test.

        :param test_name: the name of the test you wish to fetch the details of.

        :returns: the docstring of a given test.
        """
        if test_name not in self.component_manager.test_list:
            return (
                f"{test_name} not in available tests: "
                f"{self.component_manager.test_list}"
            )

        return self.component_manager.describe_test(test_name)

    # -------------
    # Fast Commands
    # -------------

    @command(dtype_out="DevVarLongStringArray")
    def UpdateStaticDelays(self: SpsStation) -> DevVarLongStringArrayType:
        """
        Update static delays from TelModel.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        """
        self.component_manager.static_delays = (
            self.component_manager._update_static_delays()
        )
        return ([ResultCode.OK], ["UpdateStaticDelays command completed OK"])

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def SetLmcDownload(self: SpsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param argin: json dictionary with optional keywords:

            * mode - (string) '1G' or '10G' (Mandatory) (use '10G' for 40G also)
            * payload_length - (int) SPEAD payload length for channel data
            * destination_ip - (string) Destination IP.
            * source_port - (int) Source port for integrated data streams
            * destination_port - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"mode": "1G", "payload_length": 1024, "destination_ip": "10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        params = json.loads(argin)
        mode = params.get("mode", "40G")

        if mode.upper == "40G":
            mode = "10G"
        payload_length = params.get("payload_length", None)
        if payload_length is None:
            if mode in ("10g", "10G"):
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
    def SetLmcIntegratedDownload(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Configure link and size for integrated data packets, for all tiles.

        :param argin: json dictionary with optional keywords:

            * mode - (string) '1G' '10G' '40G' - default 40G
            * channel_payload_length - (int) SPEAD payload length for integrated
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
        >>> dict = {"mode": "1G", "channel_payload_length":4,
                    "beam_payload_length": 1024, "destination_ip"="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        params = json.loads(argin)
        mode: str = params.get("mode", "40G")

        if mode.upper() == "40G":
            mode = "10G"
        channel_payload_length = params.get("channel_payload_length", 1024)
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
        dtype_in="DevVarLongArray",
        dtype_out="DevVarLongStringArray",
    )
    def SetBeamFormerTable(
        self: SpsStation, argin: list[int]
    ) -> DevVarLongStringArrayType:
        """
        Set the beamformer table which are going to be beamformed into each beam.

        region_array is defined as a flattened 2D array, for a maximum of 48 entries.
        Each entry corresponds to 8 consecutive frequency channels.
        This is equivalent to SetBeamformerRegions, with a different way
        to specify the bandwidth of each spectral region.
        Input is consistent with the beamformerTable attribute

        :param argin: list of regions. Each region comprises:

        * start_channel - (int) region starting channel, must be even in range 0 to 510
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

        >>> regions = [[4, 0, 0, 0, 3, 1, 101], [26, 1, 0, 24, 4, 2, 102]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        if len(argin) < 7:
            self.logger.error("Insufficient parameters specified")
            raise ValueError("Insufficient parameters specified")
        if len(argin) > (48 * 7):
            self.logger.error("Too many channel groups specified")
            raise ValueError("Too many channel groups specified")
        if len(argin) % 7 != 0:
            self.logger.error(
                "Incomplete specification of region. Groups specified by 7 values"
            )
            raise ValueError("Incomplete specification of channel group")
        beamformer_table: list[list[int]] = []
        for i in range(0, len(argin), 7):
            group = argin[i : i + 7]  # noqa: E203
            start_channel = group[0]
            if start_channel % 2 != 0:
                self.logger.error("Start channel in group must be even")
                raise ValueError("Start channel in group must be even")
            beam_index = group[1]
            if beam_index < 0 or beam_index > 47:
                self.logger.error("Beam_index is out side of range 0-47")
                raise ValueError("Beam_index is out side of range 0-47")
            beamformer_table.append(group)
        self.component_manager.set_beamformer_table(beamformer_table)

        return ([ResultCode.OK], ["SetBeamFormerTable command completed OK"])

    @command(
        dtype_in="DevVarLongArray",
        dtype_out="DevVarLongStringArray",
    )
    def SetBeamFormerRegions(
        self: SpsStation, argin: list[int]
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
        beamformer_table: list[list[int]] = []
        total_chan = 0
        for i in range(0, len(argin), 8):
            region = list(argin[i : i + 8])  # noqa: E203
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
            subarray_logical_channel = region[4]
            for channel_0 in range(start_channel, start_channel + nchannels, 8):
                entry = [channel_0] + region[2:8]
                entry[3] = subarray_logical_channel
                subarray_logical_channel = subarray_logical_channel + 8
                beamformer_table.append(entry)
        self.component_manager.set_beamformer_table(beamformer_table)
        # handler = self.get_command_object("SetBeamformerRegions")
        # (return_code, message) = handler(argin)
        return ([ResultCode.OK], ["SetBeamFormerRegions command completed OK"])

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    def LoadCalibrationCoefficients(
        self: SpsStation, argin: list[float]
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

        :param argin: an array containing a beam index followed by
            pairs of antenna delays + delay rates, delay in seconds
            and the delay rate in seconds/second

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :raises ValueError: if parameters are illegal or inconsistent

        :example:

        >>> # example delays: 256 values from -32 to +32 ns, rates = 0
        >>> delays = [step * 0.25e-9 for step in list(range(-128, 128))]
        >>> rates = [0.0]*256
        >>> beam = 0.0
        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> arg = [beam]
        >>> for i in range(256)
        >>>   arg.append(delays[i])
        >>>   arg.append(rates[i])
        >>> dp.command_inout("LoadPointingDelays", arg)
        """
        if len(argin) < 513:  # self._antennas_per_tile * 2 + 1:
            self.component_manager.logger.error("Insufficient parameters")
            raise ValueError("Insufficient parameters")
        beam_index = int(argin[0])
        if beam_index < 0 or beam_index > 7:
            self.component_manager.logger.error("Invalid beam index")
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
        self.component_manager.start_beamformer(
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
            self.component_manager.logger.error("data_type is a mandatory parameter")
            raise ValueError("data_type is a mandatory parameter")
        if data_type not in [
            "raw",
            "channel",
            "channel_continuous",
            "narrowband",
            "beam",
        ]:
            self.component_manager.logger.error("Invalid data_type specified")
            raise ValueError("Invalid data_type specified")
        if data_type == "channel_continuous":
            channel_id = params.get("channel_id", None)
            if channel_id is None:
                self.component_manager.logger.error(
                    "channel_id is a mandatory parameter"
                )
                raise ValueError("channel_id is a mandatory parameter")
            if channel_id < 1 or channel_id > 511:
                self.component_manager.logger.error(
                    "channel_id must be between 1 and 511"
                )
                raise ValueError("channel_id must be between 1 and 511")
        if data_type == "narrowband":
            frequency = params.get("frequency", None)
            if frequency is None:
                self.component_manager.logger.error(
                    "frequency is a mandatory parameter"
                )
                raise ValueError("frequency is a mandatory parameter")
            if frequency < 1e6 or frequency > 390e6:
                self.component_manager.logger.error(
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

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def ConfigureTestGenerator(
        self: SpsStation, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Set the test signal generator.

        :param argin: json dictionary with keywords:

        * tone_frequency: first tone frequency, in Hz. The frequency
            is rounded to the resolution of the generator. If this
            is not specified, the tone generator is disabled.
        * tone_amplitude: peak tone amplitude, normalized to 31.875 ADC
            units. The amplitude is rounded to 1/8 ADC unit. Default
            is 1.0. A value of -1.0 keeps the previously set value.
        * tone_2_frequency: frequency for the second tone. Same
            as ToneFrequency.
        * tone_2_amplitude: peak tone amplitude for the second tone.
            Same as ToneAmplitude.
        * noise_amplitude: RMS amplitude of the pseudorandom Gaussian
            white noise, normalized to 26.03 ADC units.
        * pulse_frequency: frequency of the periodic pulse. A code
            in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
            times the ADC frame frequency.
        * pulse_amplitude: peak amplitude of the periodic pulse, normalized
            to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
            previously set value.
        * set_time: time at which the generator is set, for synchronization
            among different TPMs. In UTC ISO format (string)
        * adc_channels: list of adc channels which will be substituted with
            the generated signal. It is a 32 integer, with each bit representing
            an input channel. Default: all if at least q source is specified,
            none otherwises.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"tone_frequency": 150e6, "tone_amplitude": 0.1,
                "noise_amplitude": 0.9, "pulse_frequency": 7,
                "set_time": "2022-08-09T12:34:56.7Z"}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ConfigureTestGenerator", jstr)
        """
        self.component_manager.configure_test_generator(argin)
        return ([ResultCode.OK], ["ConfigureTestGenerator command completed OK"])


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
