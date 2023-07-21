#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS Tile device."""
from __future__ import annotations

import importlib  # allow forward references in type hints
import itertools
import json
import logging
import os.path
import sys
from typing import Any, Callable, Final, Optional, cast

import tango
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    SimulationMode,
    TestMode,
)
from ska_tango_base.base import CommandTracker, SKABaseDevice
from ska_tango_base.commands import (
    DeviceInitCommand,
    FastCommand,
    JsonValidator,
    SubmittedSlowCommand,
)
from tango.server import attribute, command, device_property

from .tile_component_manager import TileComponentManager
from .tile_health_model import TileHealthModel
from .tpm_status import TpmStatus

__all__ = ["MccsTile", "main"]

DevVarLongStringArrayType = tuple[list[ResultCode], list[str]]


# pylint: disable=too-many-lines, too-many-public-methods, too-many-instance-attributes
class MccsTile(SKABaseDevice[TileComponentManager]):
    """An implementation of a Tile Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    SimulationConfig = device_property(dtype=int, default_value=SimulationMode.FALSE)
    TestConfig = device_property(dtype=int, default_value=TestMode.NONE)

    AntennasPerTile = device_property(dtype=int, default_value=16)

    SubrackFQDN = device_property(dtype=str)
    SubrackBay = device_property(dtype=int)  # position of TPM in subrack

    TileId = device_property(dtype=int, default_value=1)  # Tile ID must be nonzero
    TpmIp = device_property(dtype=str, default_value="0.0.0.0")
    TpmCpldPort = device_property(dtype=int, default_value=10000)
    TpmVersion = device_property(dtype=str, default_value="tpm_v1_6")

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
        self._health_model: TileHealthModel
        self._tile_programming_state: TpmStatus
        self._adc_rms: list[float]
        self._antenna_ids: list[int]
        self._max_workers: int = 1

    def init_device(self: MccsTile) -> None:
        """Initialise the device."""
        self._tile_programming_state = TpmStatus.UNKNOWN
        self._adc_rms = [0.0] * 32
        self._max_workers = 1
        super().init_device()

        self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
        device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
        version = f"{device_name} Software Version: {self._version_id}"
        properties = (
            f"Initialised {device_name} device with properties:\n"
            f"\tSubrackFQDN: {self.SubrackFQDN}\n"
            f"\tSubrackBay: {self.SubrackBay}\n"
            f"\tTileId: {self.TileId}\n"
            f"\tTpmIp: {self.TpmIp}\n"
            f"\tTpmCpldPort: {self.TpmCpldPort}\n"
            f"\tTpmVersion: {self.TpmVersion}\n"
            f"\tAntennasPerTile: {self.AntennasPerTile}\n"
            f"\tSimulationConfig: {self.SimulationConfig}\n"
            f"\tTestConfig: {self.TestConfig}\n"
        )
        self.logger.info(
            "\n%s\n%s\n%s", str(self.GetVersionInfo()), version, properties
        )

    def _init_state_model(self: MccsTile) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TileHealthModel(self._health_changed)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsTile,
    ) -> TileComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return TileComponentManager(
            self.SimulationConfig,
            self.TestConfig,
            self.logger,
            self._max_workers,
            self.TileId,
            self.TpmIp,
            self.TpmCpldPort,
            self.TpmVersion,
            self.SubrackFQDN,
            self.SubrackBay,
            self._communication_state_changed,
            self._component_state_changed,
        )

    def init_command_objects(self: MccsTile) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        for command_name, command_object in [
            ("GetFirmwareAvailable", self.GetFirmwareAvailableCommand),
            ("GetRegisterList", self.GetRegisterListCommand),
            ("ReadRegister", self.ReadRegisterCommand),
            ("WriteRegister", self.WriteRegisterCommand),
            ("ReadAddress", self.ReadAddressCommand),
            ("WriteAddress", self.WriteAddressCommand),
            ("Configure40GCore", self.Configure40GCoreCommand),
            ("Get40GCoreConfiguration", self.Get40GCoreConfigurationCommand),
            ("GetArpTable", self.GetArpTableCommand),
            ("SetLmcDownload", self.SetLmcDownloadCommand),
            ("SetLmcIntegratedDownload", self.SetLmcIntegratedDownloadCommand),
            ("SetBeamFormerRegions", self.SetBeamFormerRegionsCommand),
            ("ConfigureStationBeamformer", self.ConfigureStationBeamformerCommand),
            ("LoadCalibrationCoefficients", self.LoadCalibrationCoefficientsCommand),
            ("ApplyCalibration", self.ApplyCalibrationCommand),
            ("LoadPointingDelays", self.LoadPointingDelaysCommand),
            ("ApplyPointingDelays", self.ApplyPointingDelaysCommand),
            ("StartBeamformer", self.StartBeamformerCommand),
            ("StopBeamformer", self.StopBeamformerCommand),
            (
                "ConfigureIntegratedChannelData",
                self.ConfigureIntegratedChannelDataCommand,
            ),
            ("ConfigureIntegratedBeamData", self.ConfigureIntegratedBeamDataCommand),
            ("StopIntegratedData", self.StopIntegratedDataCommand),
            ("SendDataSamples", self.SendDataSamplesCommand),
            ("StopDataTransmission", self.StopDataTransmissionCommand),
            ("ConfigureTestGenerator", self.ConfigureTestGeneratorCommand),
        ]:
            self.register_command_object(
                command_name, command_object(self.component_manager, self.logger)
            )
        #
        # Long running commands
        #
        for command_name, method_name in [
            ("Initialise", "initialise"),
            ("DownloadFirmware", "download_firmware"),
            ("Configure", "configure"),
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
        self.register_command_object(
            "StartAcquisition",
            MccsTile.StartAcquisitionCommand(
                self._command_tracker,
                self.component_manager,
                callback=None,
                logger=self.logger,
            ),
        )

    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS Tile device."""

        def do(
            self: MccsTile.InitCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MCCS Tile device.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            assert (
                not args and not kwargs
            ), f"do method has unexpected arguments {args}, {kwargs}"
            self._device._health_state = HealthState.UNKNOWN

            self._device._csp_destination_ip = ""
            self._device._csp_destination_mac = ""
            self._device._csp_destination_port = 0
            self._device._antenna_ids = []
            self._device.set_change_event("tileProgrammingState", True, False)
            self._device.set_change_event("adcPower", True, False)

            return (ResultCode.OK, "Init command completed OK")

    # class OnCommand(SKABaseDevice):
    #     """
    #     A class for the MccsTile's On() command.

    #     This class overrides the SKABaseDevice OnCommand to allow for an
    #     eventual consistency semantics. For example it is okay to call
    #     On() before the subrack is on; this device will happily wait for
    #     the subrack to come on, then tell it to turn on its TPM. This
    #     change of semantics requires an override because the
    #     SKABaseDevice OnCommand only allows On() to be run when in OFF
    #     state.
    #     """

    #     def do(  # type: ignore[override]
    #         self: MccsTile.OnCommand,
    #     ) -> tuple[ResultCode, str]:
    #         """
    #         Stateless hook for On() command functionality.

    #         :return: A tuple containing a return code and a string
    #             message indicating status. The message is for
    #             information purpose only.
    #         """
    #         # It's fine to complete this long-running command here
    #         # (returning ResultCode.OK), even though the component manager
    #         # may not actually be finished turning everything on.
    #         # The completion of the original On command to MccsController
    #         # is waiting for the various power mode callbacks to be received
    #         # rather than completion of the various long-running commands.
    #         _ = self.target.on()
    #         message = "Tile On command completed OK"
    #         return (ResultCode.OK, message)

    def is_On_allowed(self: MccsTile) -> bool:
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

    def is_Off_allowed(self: MccsTile) -> bool:
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
        self: MccsTile, communication_state: CommunicationStatus
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
        self: MccsTile,
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
        super()._component_state_changed(fault=fault, power=power)
        self._health_model.update_state(fault=fault, power=power)

        if "programming_state" in state_change:
            tile_programming_state = cast(
                TpmStatus, state_change.get("programming_state")
            )
            message = (
                f"programming_state callback. Old: {self._tile_programming_state}"
                f" -> {tile_programming_state}"
            )
            self.logger.debug(message)
            if self._tile_programming_state != tile_programming_state:
                self._tile_programming_state = tile_programming_state
                self.push_change_event(
                    "tileProgrammingState", tile_programming_state.pretty_name()
                )
        if "tile_health_structure" in state_change:
            self._health_model.update_state(
                tile_health_structure=state_change["tile_health_structure"]
            )
        if "adc_rms" in state_change:
            adc_rms = state_change["adc_rms"]
            if self._adc_rms != adc_rms:
                self._adc_rms = adc_rms
                self.push_change_event("adcPower", adc_rms)

    def _health_changed(self: MccsTile, health: HealthState) -> None:
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
        dtype="DevString",
        label="voltages",
    )
    def voltages(self: MccsTile) -> str:
        """
        Return all the voltage values available.

        :return: voltages available
        """
        return json.dumps(self.component_manager.voltages)

    @attribute(
        dtype="DevString",
        label="temperatures",
    )
    def temperatures(self: MccsTile) -> str:
        """
        Return all the temperatures values available.

        :return: temperatures available
        """
        return json.dumps(self.component_manager.temperatures)

    @attribute(
        dtype="DevString",
        label="currents",
    )
    def currents(self: MccsTile) -> str:
        """
        Return all the currents values available.

        :return: currents available
        """
        return json.dumps(self.component_manager.currents)

    @attribute(
        dtype="DevString",
        label="timing",
    )
    def timing(self: MccsTile) -> str:
        """
        Return a dictionary of the timing signals status.

        :return: timing signals status
        """
        return json.dumps(self.component_manager.timing)

    @attribute(
        dtype="DevString",
        label="io",
    )
    def io(self: MccsTile) -> str:
        """
        Return a dictionary of I/O interfaces status available.

        :return: I/O interfaces status
        """
        return json.dumps(self.component_manager.io)

    @attribute(
        dtype="DevString",
        label="dsp",
    )
    def dsp(self: MccsTile) -> str:
        """
        Return the tile beamformer and station beamformer status.

        :return: the tile beamformer and station beamformer status
        """
        return json.dumps(self.component_manager.dsp)

    @attribute(
        dtype="DevString",
        label="cspDestinationIp",
    )
    def cspDestinationIp(self: MccsTile) -> str:
        """
        Return the cspDestinationIp attribute.

        :return: the IP address of the csp destination
        """
        return self._csp_destination_ip

    @attribute(
        dtype="DevString",
        label="cspDestinationMac",
    )
    def cspDestinationMac(self: MccsTile) -> str:
        """
        Return the cspDestinationMac attribute.

        :return: the MAC address of the csp destination
        """
        return self._csp_destination_mac

    @attribute(
        dtype="DevLong",
        label="cspDestinationPort",
    )
    def cspDestinationPort(self: MccsTile) -> int:
        """
        Return the cspDestinationMac attribute.

        :return: the port of the csp destination
        """
        return self._csp_destination_port

    @attribute(dtype=SimulationMode, memorized=True, hw_memorized=True)
    def simulationMode(self: MccsTile) -> int:
        """
        Report the simulation mode of the device.

        :return: Return the current simulation mode
        """
        return self.SimulationConfig

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(  # pylint: disable=arguments-differ
        self: MccsTile, value: SimulationMode
    ) -> None:
        """
        Set the simulation mode.

        Writing this attribute is deliberately unimplemented. The
        simulation mode should instead be set by setting the device's
        `SimulationConfig` property at launch.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.logger.warning(
            "MccsTile's simulationMode attribute is currently unimplemented. "
            "To change the simulation mode, relaunch the device with the"
            "'SimulationConfig' property set as desired. "
        )

    @attribute(dtype=TestMode, memorized=True, hw_memorized=True)
    def testMode(self: MccsTile) -> int:
        """
        Report the test mode of the device.

        :return: the current test mode
        """
        return self.TestConfig

    # pylint: disable=arguments-differ
    @testMode.write  # type: ignore[no-redef]
    def testMode(self: MccsTile, value: int) -> None:
        """
        Set the test mode.

        Writing this attribute is deliberately unimplemented. The test
        mode should instead be set by setting the device's `TestConfig`
        property at launch.

        :param value: The test mode, as a TestMode value
        """
        self.logger.warning(
            "Changing MccsTile's testMode attribute is currently "
            "unimplemented. To change the test mode, relaunch the device with "
            "the 'TestConfig' property set as desired."
        )

    @attribute(dtype="DevLong")
    def logicalTileId(self: MccsTile) -> int:
        """
        Return the logical tile id.

        The logical tile id is the id of the tile in the station.

        :return: the logical tile id
        """
        return self.component_manager.tile_id

    @logicalTileId.write  # type: ignore[no-redef]
    def logicalTileId(self: MccsTile, value: int) -> None:
        """
        Set the logicalTileId attribute.

        The logical tile id is the id of the tile in the station.

        :param value: the new logical tile id
        """
        self.component_manager.tile_id = value

    @attribute(dtype="DevString")
    def tileProgrammingState(self: MccsTile) -> str:
        """
        Get the tile programming state.

        :return: a string describing the programming state of the tile
        """
        status = self.component_manager.tpm_status
        self._tile_programming_state = status
        return status.pretty_name()

    @attribute(dtype="DevLong")
    def stationId(self: MccsTile) -> int:
        """
        Return the id of the station to which this tile is assigned.

        :return: the id of the station to which this tile is assigned
        """
        station = self.component_manager.station_id
        message = f"stationId: read value = {station}"
        self.logger.debug(message)
        return station

    @stationId.write  # type: ignore[no-redef]
    def stationId(self: MccsTile, value: int) -> None:
        """
        Set the id of the station to which this tile is assigned.

        :param value: the station id
        """
        message = f"stationId: write value = {value}"
        self.logger.debug(message)
        self.component_manager.station_id = value

    @attribute(dtype="DevString")
    def firmwareName(self: MccsTile) -> str:
        """
        Return the firmware name.

        :return: firmware name
        """
        return self.component_manager.firmware_name

    @firmwareName.write  # type: ignore[no-redef]
    def firmwareName(self: MccsTile, value: str) -> None:
        """
        Set the firmware name.

        :param value: firmware name
        """
        self.component_manager.firmware_name = value

    @attribute(dtype="DevString")
    def firmwareVersion(self: MccsTile) -> str:
        """
        Return the firmware version.

        :return: firmware version
        """
        return self.component_manager.firmware_version

    @firmwareVersion.write  # type: ignore[no-redef]
    def firmwareVersion(self: MccsTile, value: str) -> None:
        """
        Set the firmware version.

        :param value: firmware version
        """
        self.component_manager.firmware_version = value

    @attribute(
        dtype="DevDouble",
        abs_change=0.05,
        min_value=4.5,
        max_value=5.5,
        min_alarm=4.55,
        max_alarm=5.45,
    )
    def voltageMon(self: MccsTile) -> float:
        """
        Return the internal 5V supply of the TPM.

        :return: Internal supply of the TPM
        """
        return self.component_manager.voltage_mon

    @attribute(dtype="DevBoolean")
    def isProgrammed(self: MccsTile) -> bool:
        """
        Return a flag indicating whether of not the board is programmed.

        :return: whether of not the board is programmed
        """
        return self.component_manager.is_programmed

    @attribute(
        dtype="DevDouble",
        abs_change=0.1,
        min_value=15.0,
        max_value=70.0,
        min_alarm=16.0,
        max_alarm=65.0,
    )
    def boardTemperature(self: MccsTile) -> float:
        """
        Return the board temperature.

        :return: the board temperature
        """
        return self.component_manager.board_temperature

    @attribute(
        dtype="DevDouble",
        abs_change=0.1,
        min_value=15.0,
        max_value=75.0,
        min_alarm=16.0,
        max_alarm=68.0,
    )
    def fpga1Temperature(self: MccsTile) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        return self.component_manager.fpga1_temperature

    @attribute(
        dtype="DevDouble",
        abs_change=0.2,
        min_value=15.0,
        max_value=75.0,
        min_alarm=16.0,
        max_alarm=68.0,
    )
    def fpga2Temperature(self: MccsTile) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        return self.component_manager.fpga2_temperature

    @attribute(dtype=("DevLong",), max_dim_x=2)
    def fpgasUnixTime(self: MccsTile) -> list[int]:
        """
        Return the time for FPGAs.

        :return: the time for FPGAs
        """
        return self.component_manager.fpgas_unix_time

    @attribute(dtype="DevString")
    def fpgaTime(self: MccsTile) -> str:
        """
        Return the FPGA internal time.

        :return: the FPGA time, in UTC format
        """
        return self.component_manager.fpga_time

    @attribute(dtype="DevString")
    def fpgaReferenceTime(self: MccsTile) -> str:
        """
        Return the FPGA synchronization timestamp.

        :return: the FPGA timestamp, in UTC format
        """
        return self.component_manager.fpga_reference_time

    @attribute(dtype="DevString")
    def fpgaFrameTime(self: MccsTile) -> str:
        """
        Return the FPGA synchronization timestamp.

        :return: the FPGA timestamp, in UTC format
        """
        return self.component_manager.fpga_frame_time

    @attribute(dtype=("DevLong",), max_dim_x=16, label="Antenna ID's")
    def antennaIds(self: MccsTile) -> list[int]:
        """
        Return the antenna IDs.

        :return: the antenna IDs
        """
        return self._antenna_ids

    @antennaIds.write  # type: ignore[no-redef]
    def antennaIds(self: MccsTile, antenna_ids: list[int]) -> None:
        """
        Set the antenna IDs.

        :param antenna_ids: the antenna IDs
        """
        self._antenna_ids = list(antenna_ids)

    @attribute(dtype=("DevString",), max_dim_x=16)
    def fortyGbDestinationIps(self: MccsTile) -> list[str]:
        """
        Return the destination IPs for all 40Gb ports on the tile.

        :return: IP addresses
        """
        return [
            item["dst_ip"] for item in self.component_manager.get_40g_configuration()
        ]

    @attribute(dtype=("DevLong",), max_dim_x=16)
    def fortyGbDestinationPorts(self: MccsTile) -> list[int]:
        """
        Return the destination ports for all 40Gb ports on the tile.

        :return: ports
        """
        return [
            item["dst_port"] for item in self.component_manager.get_40g_configuration()
        ]

    @attribute(dtype=("DevDouble",), max_dim_x=32)
    def adcPower(self: MccsTile) -> list[float]:
        """
        Return the RMS power of every ADC signal.

        (so a TPM processes 16 antennas, this should return 32 RMS value.

        :return: RMP power of ADC signals
        """
        return self.component_manager.adc_rms

    @attribute(dtype="DevLong")
    def currentTileBeamformerFrame(self: MccsTile) -> int:
        """
        Return current frame.

        in units of 256 ADC frames (276,48 us) Currently this is
        required, not sure if it will remain so.

        :return: current frame
        """
        return self.component_manager.current_tile_beamformer_frame

    @attribute(dtype="DevLong")
    def currentFrame(self: MccsTile) -> int:
        """
        Return current frame.

        in units of 256 ADC frames (276,48 us) Currently this is
        required, not sure if it will remain so.

        :return: current frame
        """
        return self.component_manager.fpga_current_frame

    @attribute(dtype="DevBoolean")
    def pendingDataRequests(self: MccsTile) -> bool:
        """
        Check for pending data requests.

        :return: whether there are data requests pending
        """
        return self.component_manager.pending_data_requests

    @attribute(dtype="DevBoolean")
    def isBeamformerRunning(self: MccsTile) -> bool:
        """
        Check if beamformer is running.

        :return: whether the beamformer is running
        """
        return self.component_manager.is_beamformer_running

    @attribute(dtype="DevLong")
    def phaseTerminalCount(self: MccsTile) -> int:
        """
        Get phase terminal count.

        :return: phase terminal count
        """
        return self.component_manager.phase_terminal_count

    @phaseTerminalCount.write  # type: ignore[no-redef]
    def phaseTerminalCount(self: MccsTile, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.component_manager.phase_terminal_count = value

    @attribute(dtype="DevLong")
    def ppsDelay(self: MccsTile) -> int:
        """
        Return the PPS delay.

        :return: Return the PPS delay in nanoseconds
        """
        return self.component_manager.pps_delay

    @ppsDelay.write  # type: ignore[no-redef]
    def ppsDelay(self: MccsTile, delay: int) -> None:
        """
        Set PPS delay correction.

        :param delay: PPS delay correction in nanoseconds. Value is
            internally rounded to 1.25 ns units
        """
        self.component_manager.pps_delays = delay

    @attribute(dtype="DevBoolean")
    def testGeneratorActive(self: MccsTile) -> bool:
        """
        Report if the test generator is used for some channels.

        :return: test generator status
        """
        return self.component_manager.test_generator_active

    @attribute(dtype="DevBoolean")
    def ppsPresent(self: MccsTile) -> bool:
        """
        Report if PPS signal is present at the TPM input.

        :return: presence of PPS signal
        """
        return self.component_manager.pps_present

    @attribute(dtype="DevBoolean")
    def clockPresent(self: MccsTile) -> bool:
        """
        Report if 10 MHz clock signal is present at the TPM input.

        :return: presence of 10 MHz clock signal
        """
        return self.component_manager.clock_present

    @attribute(dtype="DevBoolean")
    def sysrefPresent(self: MccsTile) -> bool:
        """
        Report if SYSREF signal is present at the FPGA.

        :return: presence of SYSREF signal
        """
        return self.component_manager.sysref_present

    @attribute(dtype="DevBoolean")
    def pllLocked(self: MccsTile) -> bool:
        """
        Report if ADC clock PLL is in locked state.

        :return: PLL lock state
        """
        return self.component_manager.pll_locked

    @attribute(
        dtype=("DevLong",),
        max_dim_x=512,
    )
    def channeliserRounding(self: MccsTile) -> list[int]:
        """
        Channeliser rounding.

        Number of LS bits dropped in each channeliser frequency channel.
        Valid values 0-7 Same value applies to all antennas and
        polarizations

        :returns: list of 512 values, one per channel.
        """
        return self.component_manager.channeliser_truncation

    @channeliserRounding.write  # type: ignore[no-redef]
    def channeliserRounding(self: MccsTile, truncation: list[int]) -> None:
        """
        Set channeliser rounding.

        :param truncation: List with either a single value (applies to all channels)
            or a list of 512 values. Range 0 (no truncation) to 7
        """
        self.component_manager.channeliser_truncation = truncation

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=32,
    )
    def staticTimeDelays(self: MccsTile) -> list[int]:
        """
        Get static time delay correction.

        Array of one value per antenna/polarization (32 per tile), in range +/-124.
        Delay in samples (positive = increase the signal delay) to correct for
        static delay mismathces, e.g. cable length.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.static_delays

    @staticTimeDelays.write  # type: ignore[no-redef]
    def staticTimeDelays(self: MccsTile, delays: list[float]) -> None:
        """
        Set static time delay.

        :param delays: Delay in samples (positive = increase the signal delay)
             to correct for static delay mismathces, e.g. cable length.
        """
        self.component_manager.static_delays = delays

    @attribute(
        dtype=("DevLong",),
        max_dim_x=384,
    )
    def cspRounding(self: MccsTile) -> list[int]:
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
    def cspRounding(self: MccsTile, rounding: list[int]) -> None:
        """
        Set CSP formatter rounding.

        :param rounding: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self.component_manager.csp_rounding = rounding

    @attribute(
        dtype=(float,),
        max_dim_x=32,
    )
    def preaduLevels(self: MccsTile) -> list[float]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.preadu_levels

    @preaduLevels.write  # type: ignore[no-redef]
    def preaduLevels(self: MccsTile, levels: list[float]) -> None:
        """
        Set attenuator level of preADU channels, one per input channel.

        :param levels: ttenuator level of preADU channels, one per input channel, in dB
        """
        self.component_manager.preadu_levels = levels

    @attribute(dtype=("DevLong",), max_dim_x=336)
    def beamformerTable(self: MccsTile) -> list[int]:
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

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def healthModelParams(self: MccsTile) -> str:
        """
        Get the health params from the health model.

        :return: the health params
        """
        return json.dumps(self._health_model.health_params)

    @healthModelParams.write  # type: ignore[no-redef]
    def healthModelParams(self: MccsTile, argin: str) -> None:
        """
        Set the params for health transition rules.

        :param argin: JSON-string of dictionary of health states
        """
        self._health_model.health_params = json.loads(argin)

    @attribute(dtype=HealthState)
    def temperatureHealth(self: MccsTile) -> HealthState:
        """
        Read the temperature Health State of the device.

        This is an aggregated quantity representing if any of the temperature
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: temperature Health State of the device
        """
        return self._health_model._intermediate_healths["temperatures"]

    @attribute(dtype=HealthState)
    def voltageHealth(self: MccsTile) -> HealthState:
        """
        Read the voltage Health State of the device.

        This is an aggregated quantity representing if any of the voltage
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: voltage Health State of the device
        """
        return self._health_model._intermediate_healths["voltages"]

    @attribute(dtype=HealthState)
    def currentHealth(self: MccsTile) -> HealthState:
        """
        Read the current Health State of the device.

        This is an aggregated quantity representing if any of the current
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: current Health State of the device
        """
        return self._health_model._intermediate_healths["currents"]

    @attribute(dtype=HealthState)
    def alarmHealth(self: MccsTile) -> HealthState:
        """
        Read the alarm Health State of the device.

        This is an aggregated quantity representing if any of the alarm
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: alarm Health State of the device
        """
        return self._health_model._intermediate_healths["alarms"]

    @attribute(dtype=HealthState)
    def adcHealth(self: MccsTile) -> HealthState:
        """
        Read the ADC Health State of the device.

        This is an aggregated quantity representing if any of the ADC
        monitoring points are outside of their thresholds. This is used to compute
        the overall healthState of the tile.

        :return: ADC Health State of the device
        """
        return self._health_model._intermediate_healths["adcs"]

    @attribute(dtype=HealthState)
    def timingHealth(self: MccsTile) -> HealthState:
        """
        Read the timing Health State of the device.

        This is an aggregated quantity representing if any of the timing
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: timing Health State of the device
        """
        return self._health_model._intermediate_healths["timing"]

    @attribute(dtype=HealthState)
    def ioHealth(self: MccsTile) -> HealthState:
        """
        Read the io Health State of the device.

        This is an aggregated quantity representing if any of the io
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: io Health State of the device
        """
        return self._health_model._intermediate_healths["io"]

    @attribute(dtype=HealthState)
    def dspHealth(self: MccsTile) -> HealthState:
        """
        Read the dsp Health State of the device.

        This is an aggregated quantity representing if any of the dsp
        monitoring points do not have a permitted value. This is used to compute
        the overall healthState of the tile.

        :return: dsp Health State of the device
        """
        return self._health_model._intermediate_healths["dsp"]

    # # --------
    # # Commands
    # # --------

    @command(dtype_in="DevString")
    def Configure(self: MccsTile, argin: str) -> None:
        """
        Configure the tile device attributes.

        :param argin: the configuration for the device in stringified json format
        """
        config = json.loads(argin)

        def apply_if_valid(attribute_name: str, default: Any) -> Any:
            value = config.get(attribute_name)
            if isinstance(value, type(default)):
                return value
            return default

        static_delays = config.get("fixed_delays")
        if static_delays:
            self.component_manager.static_delays = static_delays

        self._antenna_ids = apply_if_valid("antenna_ids", self._antenna_ids)

    @command(dtype_out="DevVarLongStringArray")
    def Initialise(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Perform all required initialisation.

        (switches on on-board devices, locks PLL,
        performs synchronisation and other operations required to start configuring the
        signal processing functions of the firmware, such as channelisation and
        beamforming)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("Initialise")
        """
        handler = self.get_command_object("Initialise")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    class GetFirmwareAvailableCommand(FastCommand):
        """Class for handling the GetFirmwareAvailable() command."""

        def __init__(
            self: MccsTile.GetFirmwareAvailableCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetFirmwareAvailableCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(
            self: MccsTile.GetFirmwareAvailableCommand,
            *args: Any,
            **kwargs: Any,
        ) -> str:
            """
            Implement :py:meth:`.MccsTile.GetFirmwareAvailable` command functionality.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: json encoded string containing list of dictionaries
            """
            return json.dumps(self._component_manager.firmware_available)

    @command(dtype_out="DevString")
    def GetFirmwareAvailable(self: MccsTile) -> str:
        """
        Get available firmware.

        Return a dictionary containing the following information for
        each firmware stored on the board (such as in Flash memory).

        For each firmware, a dictionary containing the following keys
        with their respective values should be provided: ‘design’, which
        is a textual name for the firmware, ‘major’, which is the major
        version number, and ‘minor’.

        :return: a JSON-encoded dictionary of firmware details

        :example:
            >>> dp = tango.DeviceProxy("mccs/tile/01")
            >>> jstr = dp.command_inout("GetFirmwareAvailable")
            >>> dict = json.load(jstr)
            {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
            }
        """
        handler = self.get_command_object("GetFirmwareAvailable")
        return handler()

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def DownloadFirmware(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Download the firmware contained in bitfile to all FPGAs on the board.

        This should also update the internal register mapping, such that registers
        become available for use.

        :param argin: can either be the design name returned from
            :py:meth:`.GetFirmwareAvailable` command, or a path to a
            file

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("DownloadFirmware", "/tmp/firmware/bitfile")
        """
        if os.path.isfile(argin):
            handler = self.get_command_object("DownloadFirmware")
            (return_code, unique_id) = handler(argin)
            return ([return_code], [unique_id])
        return ([ResultCode.FAILED], [f"{argin} doesn't exist"])

    class GetRegisterListCommand(FastCommand):
        """Class for handling the GetRegisterList() command."""

        def __init__(
            self: MccsTile.GetRegisterListCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetRegisterListCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(
            self: MccsTile.GetRegisterListCommand,
            *args: Any,
            **kwargs: Any,
        ) -> list[str]:
            """
            Implement :py:meth:`.MccsTile.GetRegisterList` command functionality.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: a list of firmware & cpld registers
            """
            return self._component_manager.register_list

    @command(dtype_out="DevVarStringArray")
    def GetRegisterList(self: MccsTile) -> list[str]:
        """
        Return a list of descriptions of the exposed firmware (and CPLD) registers.

        :return: a list of register names

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("GetRegisterList")
        """
        handler = self.get_command_object("GetRegisterList")
        return handler()

    class ReadRegisterCommand(FastCommand):
        """Class for handling the ReadRegister(argin) command."""

        def __init__(
            self: MccsTile.ReadRegisterCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ReadRegisterCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(
            self: MccsTile.ReadRegisterCommand,
            *args: Any,
            **kwargs: Any,
        ) -> list[int]:
            """
            Implement :py:meth:`.MccsTile.ReadRegister` command functionality.

            :param args: the register name
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: list of register values

            :raises ValueError: if the name is invalid
            """
            name = args[0]
            if name is None or name == "":
                self.logger.error("register name is a mandatory parameter")
                raise ValueError("register name is a mandatory parameter")
            value = self._component_manager.read_register(name)
            message = f"Register {name} = {value}"
            self.logger.debug(message)
            return value

    @command(dtype_in="DevString", dtype_out="DevVarULongArray")
    def ReadRegister(self: MccsTile, register_name: str) -> list[int]:
        """
        Return the value(s) of the specified register.

        :param register_name: full hyerarchic register name
        :return: a list of register values

        :example:

        >>> dp = tango.DeviceProxy("fpga1./tile/01")
        >>> values = dp.command_inout("ReadRegister", "test-reg1")
        """
        handler = self.get_command_object("ReadRegister")
        return handler(register_name)

    class WriteRegisterCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the WriteRegister() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_WriteRegister.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_WriteRegister.json",
            )
        )

        def __init__(
            self: MccsTile.WriteRegisterCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new WriteRegisterCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("WriteRegister", self.SCHEMA, logger)
            super().__init__(logger, validator)

        def do(
            self: MccsTile.WriteRegisterCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.WriteRegister` command functionality.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.write_register(
                kwargs["register_name"], kwargs["values"]
            )
            return (ResultCode.OK, "WriteRegister completed OK")

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def WriteRegister(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Write values to the specified register.

        :param argin: json dictionary with mandatory keywords:

            * register_name - (string) register fully qualified string representation
            * values - (list) is a list containing the 32-bit values to write

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"register_name": "test-reg1", "values": values,
                    "offset": 0}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("WriteRegister", jstr)
        """
        handler = self.get_command_object("WriteRegister")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ReadAddressCommand(FastCommand):
        """Class for handling the ReadAddress(argin) command."""

        def __init__(
            self: MccsTile.ReadAddressCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ReadAddressCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.ReadAddressCommand,
            argin: list[int],
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ReadAddress` command functionality.

            :param argin: sequence of length two, containing an address and
                a value
            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: [values, ]

            :raises ValueError: if the argin argument has the wrong length
                or structure
            """
            if len(argin) < 1:
                self.logger.error("At least one parameter is required")
                raise ValueError("One or two parameters are required")
            if len(argin) == 1:
                nvalues = 1
            else:
                nvalues = argin[1]
            address = argin[0]
            return self._component_manager.read_address(address, nvalues)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarULongArray")
    def ReadAddress(self: MccsTile, argin: list[int]) -> list[int]:
        """
        Read n 32-bit values from address.

        :param argin: [0] = address to read from
                      [1] = number of values to read, default 1

        :return: list of values

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> reglist = dp.command_inout("ReadAddress", [address, nvalues])
        """
        handler = self.get_command_object("ReadAddress")
        return handler(argin)

    class WriteAddressCommand(FastCommand):
        """Class for handling the WriteAddress(argin) command."""

        def __init__(
            self: MccsTile.WriteAddressCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new WriteAddressCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "WriteAddress command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.WriteAddressCommand,
            argin: list[int],
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.WriteAddress` command functionality.

            :param argin: sequence of length two, containing an address and
                a value
            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin has the wrong length/structure
            """
            if len(argin) < 2:
                self.logger.error("A minimum of two parameters are required")
                raise ValueError("A minium of two parameters are required")
            self._component_manager.write_address(argin[0], argin[1:])
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarULongArray", dtype_out="DevVarLongStringArray")
    def WriteAddress(self: MccsTile, argin: list[int]) -> DevVarLongStringArrayType:
        """
        Write list of values at address.

        :param argin: [0] = address to write to
                      [1..n] = list of values to write

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> values = [.....]
        >>> address = 0xfff
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("WriteAddress", [address, values])
        """
        handler = self.get_command_object("WriteAddress")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class Configure40GCoreCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the Configure40GCore() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_Configure40gCore.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_Configure40gCore.json",
            )
        )

        def __init__(
            self: MccsTile.Configure40GCoreCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new Configure40GCoreCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("Configure40GCore", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "Configure40GCore command completed OK"

        def do(
            self: MccsTile.Configure40GCoreCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.Configure40GCore` command functionality.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            core_id = kwargs.get("core_id", None)
            arp_table_entry = kwargs.get("arp_table_entry", 0)
            src_mac = kwargs.get("source_mac", None)
            src_ip = kwargs.get("source_ip", None)
            src_port = kwargs.get("source_port", None)
            dst_ip = kwargs.get("destination_ip", None)
            dst_port = kwargs.get("destination_port", None)

            self._component_manager.configure_40g_core(
                core_id, arp_table_entry, src_mac, src_ip, src_port, dst_ip, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure40GCore(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Configure 40g core_id with specified parameters.

        :param argin: json dictionary with only optional keywords:

            * core_id - (int) core id
            * arp_table_entry - (int) ARP table entry ID
            * source_mac - (int) mac address
            * source_ip - (string) IP dot notation.
            * source_port - (int) source port
            * destination_ip - (string) IP dot notation
            * destination_port - (int) destination port

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"core_id":2, "arp_table_entry":0, "source_mac":0x62000a0a01c9,
                    "source_ip":"10.0.99.3", "source_port":4000,
                    "destination_ip":"10.0.99.3", "destination_port":5000}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("Configure40GCore", jstr)
        """
        handler = self.get_command_object("Configure40GCore")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class Get40GCoreConfigurationCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the Get40GCoreConfiguration() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_Get40gCoreConfiguration.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_Get40gCoreConfiguration.json",
            )
        )

        def __init__(
            self: MccsTile.Get40GCoreConfigurationCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new Get40GCoreConfigurationCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("Get40GCoreConfiguration", self.SCHEMA, logger)
            super().__init__(logger, validator)

        def do(
            self: MccsTile.Get40GCoreConfigurationCommand,
            *args: Any,
            **kwargs: Any,
        ) -> str:
            """
            Implement :py:meth:`.MccsTile.Get40GCoreConfiguration` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: json string with configuration

            :raises ValueError: if the argin is an invalid code id
            """
            core_id = kwargs.get("core_id", None)
            arp_table_entry = kwargs.get("arp_table_entry", 0)

            item_list = self._component_manager.get_40g_configuration(
                core_id, arp_table_entry
            )
            item_new = []
            for item in item_list:
                item_new.append(
                    {
                        "core_id": item.get("core_id", None),
                        "arp_table_entry": item.get("arp_table_entry", None),
                        "source_mac": item.get("src_mac", None),
                        "source_ip": item.get("src_ip", None),
                        "source_port": item.get("src_port", None),
                        "destination_ip": item.get("dst_ip", None),
                        "destination_port": item.get("dst_port", None),
                    }
                )
            if len(item_new) == 0:
                raise ValueError("Invalid core id or arp table id specified")
            if len(item_new) == 1:
                return json.dumps(item_new[0])
            return json.dumps(item_new)

    @command(dtype_in="DevString", dtype_out="DevString")
    def Get40GCoreConfiguration(self: MccsTile, argin: str) -> str:
        """
        Get 40g core configuration for core_id.

        This is required to chain up TPMs to form a station.

        :param argin: json dictionary with optional keywords:

        * core_id - (int) core id
        * arp_table_entry - (int) ARP table entry ID to use

        :return: the configuration is a json string describilg a list (possibly empty)
                 Each list entry comprising:
                 core_id, arp_table_entry, source_mac, source_ip, source_port,
                 destination_ip, destination_port

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> core_id = 2
        >>> arp_table_entry = 0
        >>> argout = dp.command_inout(Get40GCoreConfiguration, core_id, arp_table_entry)
        >>> params = json.loads(argout)
        """
        handler = self.get_command_object("Get40GCoreConfiguration")
        return handler(argin)

    class SetLmcDownloadCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the SetLmcDownload() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_SetLmcDownload.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_SetLmcDownload.json",
            )
        )

        def __init__(
            self: MccsTile.SetLmcDownloadCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetLmcDownloadCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("SetLmcDownload", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "SetLmcDownload command completed OK"

        def do(
            self: MccsTile.SetLmcDownloadCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetLmcDownload` command functionality.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            mode: str = kwargs["mode"]
            payload_length = kwargs.get("payload_length", None)
            if payload_length is None:
                if mode.upper() == "10G":
                    payload_length = 8192
                else:
                    payload_length = 1024
            dst_ip = kwargs.get("destination_ip", None)
            src_port = kwargs.get("source_port", 0xF0D0)
            dst_port = kwargs.get("destination_port", 4660)

            self._component_manager.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetLmcDownload(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
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
        >> dict = {"mode": "1G", "payload_length": 4, "destination_ip": "10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SetLmcIntegratedDownloadCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the SetLmcIntegratedDownload() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_SetLmcIntegratedDownload.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_SetLmcIntegratedDownload.json",
            )
        )

        def __init__(
            self: MccsTile.SetLmcIntegratedDownloadCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetLmcIntegratedDownloadCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("SetLmcIntegratedDownload", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "SetLmcIntegratedDownload command completed OK"

        def do(
            self: MccsTile.SetLmcIntegratedDownloadCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetLmcIntegratedDownload` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            mode = kwargs["mode"]
            channel_payload_length = kwargs.get("channel_payload_length", 1024)
            beam_payload_length = kwargs.get("beam_payload_length", 1024)
            dst_ip = kwargs.get("destination_ip", None)
            src_port = kwargs.get("source_port", 0xF0D0)
            dst_port = kwargs.get("destination_port", 4660)

            self._component_manager.set_lmc_integrated_download(
                mode,
                channel_payload_length,
                beam_payload_length,
                dst_ip,
                src_port,
                dst_port,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetLmcIntegratedDownload(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Configure link and size of control data.

        :param argin: json dictionary with optional keywords:

            * mode - (string) '1G' or '10G' (Mandatory)
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
                    "beam_payload_length": 1024, "destination_ip": "10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        handler = self.get_command_object("SetLmcIntegratedDownload")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class GetArpTableCommand(FastCommand):
        """Class for handling the GetArpTable() command."""

        def __init__(
            self: MccsTile.GetArpTableCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetArpTableCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(self: MccsTile.GetArpTableCommand, *args: Any, **kwargs: Any) -> str:
            """
            Implement :py:meth:`.MccsTile.GetArpTable` commands.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: a JSON-encoded dictionary of coreId and populated arpID table
            """
            return json.dumps(self._component_manager.arp_table)

    @command(dtype_out="DevString")
    def GetArpTable(self: MccsTile) -> str:
        """
        Return a dictionary with populated ARP table for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and
        ARP ID 0 for beamformer, 1 for LMC.
        10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming,
        and 2, 6 for LMC with only one ARP.

        :return: a JSON-encoded dictionary of coreId and populated arpID table

        :example:

        >>> argout = dp.command_inout("GetArpTable")
        >>> dict = json.loads(argout)
        >>>    {
        >>>    "core_id0": [0, 1],
        >>>    "core_id1": [0],
        >>>    "core_id3": [],
        >>>    }
        """
        handler = self.get_command_object("GetArpTable")
        return handler()

    class SetBeamFormerRegionsCommand(FastCommand):
        """Class for handling the SetBeamFormerRegions(argin) command."""

        def __init__(
            self: MccsTile.SetBeamFormerRegionsCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetBeamFormerRegionsCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetBeamFormerRegions command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetBeamFormerRegionsCommand,
            argin: list[int],
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetBeamFormerRegions` command functionality.

            :param argin: a region array
            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
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
                    self.logger.error(
                        "Nos. of channels in region must be multiple of 8"
                    )
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

            self._component_manager.set_beamformer_regions(regions)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def SetBeamFormerRegions(
        self: MccsTile, argin: list[int]
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

        :example:

        >>> regions = [[4, 24, 0, 0, 0, 3, 1, 101], [26, 40, 1, 0, 24, 4, 2, 102]]
        >>> input = list(itertools.chain.from_iterable(regions))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetBeamFormerRegions", input)
        """
        handler = self.get_command_object("SetBeamFormerRegions")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ConfigureStationBeamformerCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the ConfigureStationBeamformer() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_ConfigureStationBeamformer.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_ConfigureStationBeamformer.json",
            )
        )

        def __init__(
            self: MccsTile.ConfigureStationBeamformerCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureStationBeamformerCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("ConfigureStationBeamformer", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "ConfigureStationBeamformer command completed OK"

        def do(
            self: MccsTile.ConfigureStationBeamformerCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureStationBeamformer` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            start_channel = kwargs.get("start_channel", 192)
            n_channels = kwargs.get("n_channels", 8)
            if start_channel + n_channels > 511:
                self.logger.error("Invalid specified observed region")
                raise ValueError("Invalid specified observed region")
            is_first = kwargs.get("is_first", False)
            is_last = kwargs.get("is_last", False)
            self._component_manager.initialise_beamformer(
                start_channel, n_channels, is_first, is_last
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureStationBeamformer(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Initialise and start the station beamformer.

        Initial configuration of the tile-station beamformer.
        Optionally set the observed region, Default is 6.25 MHz starting at 150 MHz,
        and set whether the tile is the first or last in the beamformer chain.

        :param argin: json dictionary with mandatory keywords:

            * start_channel - (int) start channel of the observed region
              default = 192 (150 MHz)
            * n_channels - (int) is the number of channels in the observed region
              default = 8 (6.25 MHz)
            * is_first - (bool) whether the tile is the first one in the station
              default False
            * is_last - (bool) whether the tile is the last one in the station
              default False

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"start_channel":64, "n_channels":10, "is_first":True,
        >>         "is_last:True}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("ConfigureStationBeamformer", jstr)
        """
        handler = self.get_command_object("ConfigureStationBeamformer")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class LoadCalibrationCoefficientsCommand(FastCommand):
        """Class for handling the LoadCalibrationCoefficients(argin) command."""

        def __init__(
            self: MccsTile.LoadCalibrationCoefficientsCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new LoadCalibrationCoefficientsCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "LoadCalibrationCoefficents command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.LoadCalibrationCoefficientsCommand,
            argin: list[float],
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadCalibrationCoefficients` commands.

            :param argin: calibration coefficients
            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
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
            antenna = int(argin[0])
            calibration_coefficients = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(1, len(argin), 8)
            ]

            self._component_manager.load_calibration_coefficients(
                antenna, calibration_coefficients
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadCalibrationCoefficients(
        self: MccsTile, argin: list[float]
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
        handler = self.get_command_object("LoadCalibrationCoefficients")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ApplyCalibrationCommand(FastCommand):
        """Class for handling the ApplyCalibration(argin) command."""

        def __init__(
            self: MccsTile.ApplyCalibrationCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ApplyCalibrationCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ApplyCalibration command completed OK"

        def do(
            self: MccsTile.ApplyCalibrationCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ApplyCalibration` command functionality.

            :param args: switch time
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            switch_time = args[0]

            self._component_manager.apply_calibration(switch_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ApplyCalibration(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Load the calibration coefficients at the specified time delay.

        :param argin: switch time, in ISO formatted time

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ApplyCalibration", "")
        """
        handler = self.get_command_object("ApplyCalibration")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class LoadPointingDelaysCommand(FastCommand):
        """Class for handling the LoadPointingDelays(argin) command."""

        SUCCEEDED_MESSAGE = "LoadPointingDelays command completed OK"

        def __init__(
            self: MccsTile.LoadPointingDelaysCommand,
            component_manager: TileComponentManager,
            logger: logging.Logger,
        ) -> None:
            """
            Initialise a new LoadPointingDelaysCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            self._component_manager = component_manager
            super().__init__(logger)
            self._antennas_per_tile = 16

        def do(  # type: ignore[override]
            self: MccsTile.LoadPointingDelaysCommand,
            argin: list[float],
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadPointingDelays` command functionality.

            :param argin: an array containing a beam index and antenna
                delays
            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < self._antennas_per_tile * 2 + 1:
                self.logger.error("Insufficient parameters")
                raise ValueError("Insufficient parameters")
            beam_index = int(argin[0])
            if beam_index < 0 or beam_index > 7:
                self.logger.error("Invalid beam index")
                raise ValueError("Invalid beam index")
            delay_array = []
            for i in range(self._antennas_per_tile):
                delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])

            self._component_manager.load_pointing_delays(delay_array, beam_index)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadPointingDelays(
        self: MccsTile, argin: list[float]
    ) -> DevVarLongStringArrayType:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param argin: the delay in seconds and the delay rate in
            seconds/second.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("LoadPointingDelays")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ApplyPointingDelaysCommand(FastCommand):
        """Class for handling the ApplyPointingDelays(argin) command."""

        def __init__(
            self: MccsTile.ApplyPointingDelaysCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ApplyPointingDelayommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ApplyPointingDelays command completed OK"

        def do(
            self: MccsTile.ApplyPointingDelaysCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ApplyPointingDelays` command functionality.

            :param args: load time
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            load_time = args[0]

            self._component_manager.apply_pointing_delays(load_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ApplyPointingDelays(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Apply the pointing delays at the specified time delay.

        :param argin: time delay (default = 0)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ApplyPointingDelays", "")
        """
        handler = self.get_command_object("ApplyPointingDelays")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StartBeamformerCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the StartBeamformer(argin) command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_StartBeamformer.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_StartBeamformer.json",
            )
        )

        def __init__(
            self: MccsTile.StartBeamformerCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new StartBeamformerCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("StartBeamformer", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "StartBeamformer command completed OK"

        def do(
            self: MccsTile.StartBeamformerCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StartBeamformer` command functionality.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            start_time = kwargs.get("start_time", None)
            duration = kwargs.get("duration", -1)
            subarray_beam_id = kwargs.get("subarray_beam_id", -1)
            scan_id = kwargs.get("scan_id", 0)
            self._component_manager.start_beamformer(
                start_time, duration, subarray_beam_id, scan_id
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartBeamformer(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Start the beamformer at the specified time delay.

        :param argin: json dictionary with optional keywords:

        * start_time - (str, ISO UTC time) start time
        * duration - (int) if > 0 is a duration in CSP frames (2211.84 us)
               if == -1 run forever
        * subarray_beam_id - (int) : Subarray beam ID of the channels to be started
                Command affects only beamformed channels for given subarray ID
                Default -1: all channels
        * scan_id - (int) The unique ID for the started scan. Default 0

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Duration":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartBeamformer", jstr)
        """
        handler = self.get_command_object("StartBeamformer")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StopBeamformerCommand(FastCommand):
        """Class for handling the StopBeamformer() command."""

        def __init__(
            self: MccsTile.StopBeamformerCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new StopBeamformerCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "StopBeamformer command completed OK"

        def do(
            self: MccsTile.StopBeamformerCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopBeamformer` command functionality.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.stop_beamformer()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def StopBeamformer(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopBeamformer")
        """
        handler = self.get_command_object("StopBeamformer")
        (return_code, message) = handler()
        return ([return_code], [message])

    class ConfigureIntegratedChannelDataCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the ConfigureIntegratedChannelData(argin) command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_ConfigureIntegratedChannelData.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_ConfigureIntegratedChannelData.json",
            )
        )

        def __init__(
            self: MccsTile.ConfigureIntegratedChannelDataCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureIntegratedChannelDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator(
                "ConfigureIntegratedChannelData", self.SCHEMA, logger
            )
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "ConfigureIntegratedChannelData command completed OK"

        def do(
            self: MccsTile.ConfigureIntegratedChannelDataCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedChannelData` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            integration_time = kwargs.get("integration_time", 0.5)
            first_channel = kwargs.get("first_channel", 0)
            last_channel = kwargs.get("last_channel", 511)

            self._component_manager.configure_integrated_channel_data(
                integration_time, first_channel, last_channel
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureIntegratedChannelData(
        self: MccsTile, argin: str
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
        handler = self.get_command_object("ConfigureIntegratedChannelData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ConfigureIntegratedBeamDataCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the ConfigureIntegratedBeamData() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_ConfigureIntegratedBeamData.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_ConfigureIntegratedBeamData.json",
            )
        )

        def __init__(
            self: MccsTile.ConfigureIntegratedBeamDataCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureIntegratedBeamDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator(
                "ConfigureIntegratedBeamData", self.SCHEMA, logger
            )
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "ConfigureIntegratedBeamData command completed OK"

        def do(
            self: MccsTile.ConfigureIntegratedBeamDataCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedBeamData` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            integration_time = kwargs.get("integration_time", 0.5)
            first_channel = kwargs.get("first_channel", 0)
            last_channel = kwargs.get("last_channel", 191)

            self._component_manager.configure_integrated_beam_data(
                integration_time, first_channel, last_channel
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureIntegratedBeamData(
        self: MccsTile, argin: str
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
        handler = self.get_command_object("ConfigureIntegratedBeamData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StopIntegratedDataCommand(FastCommand):
        """Class for handling the StopIntegratedData command."""

        def __init__(
            self: MccsTile.StopIntegratedDataCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new StopIntegratedDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "StopIntegratedData command completed OK"

        def do(
            self: MccsTile.StopIntegratedDataCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopIntegratedData` command functionality.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.stop_integrated_data()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def StopIntegratedData(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Stop the integrated  data.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StopIntegratedData")
        (return_code, message) = handler()
        return ([return_code], [message])

    class SendDataSamplesCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the SendDataSamples() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_SendDataSamples.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas", "MccsTile_SendDataSamples.json"
            )
        )

        def __init__(
            self: MccsTile.SendDataSamplesCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendDataSamplesCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("SendDataSamples", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "SendDataSamples command completed OK"

        def do(
            self: MccsTile.SendDataSamplesCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendDataSamples` command functionality.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :raises ValueError: if mandatory parameters are missing
            """
            data_type = kwargs["data_type"]
            if data_type == "channel":
                first_ch = kwargs.get("first_channel", 0)
                last_ch = kwargs.get("last_channel", 511)
                if last_ch < first_ch:
                    err = (
                        f"last channel ({last_ch}) cannot be less than first "
                        f"channel ({first_ch})."
                    )
                    self.logger.error(err)
                    raise ValueError(err)

            if data_type in ["channel", "narrowband"]:
                kwargs.setdefault("n_samples", 1024)
            elif data_type == "channel_continuous":
                kwargs.setdefault("n_samples", 128)
            else:
                kwargs.setdefault("n_samples", None)

            self._component_manager.send_data_samples(**kwargs)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendDataSamples(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
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

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"data_type": "raw", "Sync":True, "Seconds": 0.2}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendDataSamples", jstr)
        """
        handler = self.get_command_object("SendDataSamples")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StopDataTransmissionCommand(FastCommand):
        """Class for handling the StopDataTransmission() command."""

        def __init__(
            self: MccsTile.StopDataTransmissionCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new StopDataTransmissionCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "StopDataTransmission command completed OK"

        def do(
            self: MccsTile.StopDataTransmissionCommand, *args: Any, **kwargs: Any
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopDataTransmission` command functionality.

            :param args: unspecified positional arguments. This should be empty and is
                provided for type hinting only
            :param kwargs: unspecified keyword arguments. This should be empty and is
                provided for type hinting only

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.stop_data_transmission()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def StopDataTransmission(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Stop data transmission from board.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("StopDataTransmission")
        """
        handler = self.get_command_object("StopDataTransmission")
        (return_code, message) = handler()
        return ([return_code], [message])

    class StartAcquisitionCommand(SubmittedSlowCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the StartAcquisition() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_StartAcquisition.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_StartAcquisition.json",
            )
        )

        def __init__(
            self: MccsTile.StartAcquisitionCommand,
            command_tracker: CommandTracker,
            component_manager: TileComponentManager,
            callback: Optional[Callable] = None,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param command_tracker: the device's command tracker
            :param component_manager: the device's component manager
            :param callback: an optional callback to be called when this
                command starts and finishes.
            :param logger: a logger for this command to log with.
            """
            validator = JsonValidator("StartAcquisition", self.SCHEMA, logger)
            super().__init__(
                "StartAcquisition",
                command_tracker,
                component_manager,
                "start_acquisition",
                callback=callback,
                logger=logger,
                validator=validator,
            )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartAcquisition(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Start data acquisition.

        :param argin: json dictionary with optional keywords:

        * start_time - (ISO UTC time) start time
        * delay - (int) delay start if StartTime is not specified, default 0.2s

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"start_time":"2021-11-22, "delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """
        handler = self.get_command_object("StartAcquisition")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    class ConfigureTestGeneratorCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the ConfigureTestGenerator() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/tile/schemas/MccsTile_ConfigureTestGenerator.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.tile.schemas",
                "MccsTile_ConfigureTestGenerator.json",
            )
        )

        def __init__(
            self: MccsTile.ConfigureTestGeneratorCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureTestGeneratorCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            validator = JsonValidator("ConfigureTestGenerator", self.SCHEMA, logger)
            super().__init__(logger, validator)

        SUCCEEDED_MESSAGE = "ConfigureTestGenerator command completed OK"

        def do(
            self: MccsTile.ConfigureTestGeneratorCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureTestGenerator` commands.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                   message indicating status. The message is for
                   information purpose only.
            """
            active = False
            set_time = kwargs.get("set_time", None)
            if "tone_frequency" in kwargs:
                frequency0 = kwargs["tone_frequency"]
                amplitude0 = kwargs.get("tone_amplitude", 1.0)
                active = True
            else:
                frequency0 = 0.0
                amplitude0 = 0.0

            if "tone_2_frequency" in kwargs:
                frequency1 = kwargs["tone_2_frequency"]
                amplitude1 = kwargs.get("tone_2_amplitude", 1.0)
                active = True
            else:
                frequency1 = 0.0
                amplitude1 = 0.0

            if "noise_amplitude" in kwargs:
                amplitude_noise = kwargs["noise_amplitude"]
                active = True
            else:
                amplitude_noise = 0.0

            if "pulse_frequency" in kwargs:
                pulse_code = kwargs["pulse_frequency"]
                amplitude_pulse = kwargs.get("pulse_amplitude", 1.0)
                active = True
            else:
                pulse_code = 7
                amplitude_pulse = 0.0

            self._component_manager.configure_test_generator(
                frequency0,
                amplitude0,
                frequency1,
                amplitude1,
                amplitude_noise,
                pulse_code,
                amplitude_pulse,
                set_time,
            )

            chans = kwargs.get("adc_channels")
            inputs = 0
            if chans is None:
                if active:
                    inputs = 0xFFFFFFFF
            else:
                for channel in chans:
                    inputs = inputs | (1 << channel)
            self._component_manager.test_generator_input_select(inputs)
            self._component_manager.test_generator_active = active
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    def is_ConfigureTestGenerator_allowed(self: MccsTile) -> bool:
        """
        Check if command is allowed.

        It is allowed only in maintenance mode.

        :returns: whether the command is allowed
        """
        return self.admin_mode_model.admin_mode == AdminMode.MAINTENANCE

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureTestGenerator(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
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
        handler = self.get_command_object("ConfigureTestGenerator")
        (return_code, message) = handler(argin)
        return ([return_code], [message])


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
    return MccsTile.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
