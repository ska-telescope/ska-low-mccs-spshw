# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS Tile device."""
from __future__ import annotations  # allow forward references in type hints

import json
import logging
import os.path
from typing import Any, List, Optional, Tuple

import numpy as np
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
from ska_tango_base.base import SKABaseDevice

# from ska_tango_base.base.op_state_model import OpStateModel
from ska_tango_base.commands import DeviceInitCommand, FastCommand, SubmittedSlowCommand
from tango.server import attribute, command, device_property

from ska_low_mccs.tile import TileComponentManager, TileHealthModel
from ska_low_mccs.tile.tpm_status import TpmStatus

__all__ = ["MccsTile", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsTile(SKABaseDevice):
    """An implementation of a Tile Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
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
    def init_device(self: MccsTile) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsTile) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TileHealthModel(self.component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsTile,
    ) -> TileComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return TileComponentManager(
            SimulationMode.TRUE,
            TestMode.NONE,
            self.logger,
            self._max_workers,
            self.TileId,
            self.TpmIp,
            self.TpmCpldPort,
            self.TpmVersion,
            self.SubrackFQDN,
            self.SubrackBay,
            self._component_communication_state_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsTile) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        for (command_name, command_object) in [
            ("GetFirmwareAvailable", self.GetFirmwareAvailableCommand),
            ("GetRegisterList", self.GetRegisterListCommand),
            ("ReadRegister", self.ReadRegisterCommand),
            ("WriteRegister", self.WriteRegisterCommand),
            ("ReadAddress", self.ReadAddressCommand),
            ("WriteAddress", self.WriteAddressCommand),
            ("Configure40GCore", self.Configure40GCoreCommand),
            ("Get40GCoreConfiguration", self.Get40GCoreConfigurationCommand),
            ("SetLmcDownload", self.SetLmcDownloadCommand),
            ("SetChanneliserTruncation", self.SetChanneliserTruncationCommand),
            ("SetBeamFormerRegions", self.SetBeamFormerRegionsCommand),
            ("ConfigureStationBeamformer", self.ConfigureStationBeamformerCommand),
            ("LoadCalibrationCoefficients", self.LoadCalibrationCoefficientsCommand),
            ("LoadCalibrationCurve", self.LoadCalibrationCurveCommand),
            ("LoadBeamAngle", self.LoadBeamAngleCommand),
            ("SwitchCalibrationBank", self.SwitchCalibrationBankCommand),
            ("LoadPointingDelay", self.LoadPointingDelayCommand),
            ("StartBeamformer", self.StartBeamformerCommand),
            ("StopBeamformer", self.StopBeamformerCommand),
            (
                "ConfigureIntegratedChannelData",
                self.ConfigureIntegratedChannelDataCommand,
            ),
            ("ConfigureIntegratedBeamData", self.ConfigureIntegratedBeamDataCommand),
            ("StopIntegratedData", self.StopIntegratedDataCommand),
            ("SendRawData", self.SendRawDataCommand),
            ("SendChannelisedData", self.SendChannelisedDataCommand),
            (
                "SendChannelisedDataContinuous",
                self.SendChannelisedDataContinuousCommand,
            ),
            ("SendBeamData", self.SendBeamDataCommand),
            ("StopDataTransmission", self.StopDataTransmissionCommand),
            (
                "ComputeCalibrationCoefficients",
                self.ComputeCalibrationCoefficientsCommand,
            ),
            ("SetTimeDelays", self.SetTimeDelaysCommand),
            ("SetCspRounding", self.SetCspRoundingCommand),
            ("SetLmcIntegratedDownload", self.SetLmcIntegratedDownloadCommand),
            ("SendRawDataSynchronised", self.SendRawDataSynchronisedCommand),
            (
                "SendChannelisedDataNarrowband",
                self.SendChannelisedDataNarrowbandCommand,
            ),
            ("TweakTransceivers", self.TweakTransceiversCommand),
            ("CalculateDelay", self.CalculateDelayCommand),
            ("ConfigureTestGenerator", self.ConfigureTestGeneratorCommand),
        ]:
            self.register_command_object(
                command_name, command_object(self.component_manager, self.logger)
            )

        for (command_name, method_name) in [
            ("Initialise", "initialise"),
            ("DownloadFirmware", "download_firmware"),
            ("GetArpTable", "get_arp_table"),
            ("StartAcquisition", "start_acquisition"),
            ("ProgramCPLD", "cpld_flash_write"),
            ("PostSynchronisation", "post_synchronisation"),
            ("SyncFpgas", "sync_fpgas"),
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

        antenna_args = (self.component_manager, self.logger, self.AntennasPerTile)
        self.register_command_object(
            "LoadAntennaTapering", self.LoadAntennaTaperingCommand(*antenna_args)
        )
        self.register_command_object(
            "SetPointingDelay", self.SetPointingDelayCommand(*antenna_args)
        )

    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS Tile device."""

        def do(  # type: ignore[override]
            self: MccsTile.InitCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MCCS Tile device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._health_state = HealthState.UNKNOWN

            self._device._csp_destination_ip = ""
            self._device._csp_destination_mac = ""
            self._device._csp_destination_port = 0
            self._device._antenna_ids = []

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

    # ----------
    # Callbacks
    # ----------
    def _component_communication_state_changed(
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
        # TODO: The following 2 lines might need some attention/tidying up.
        self.component_manager._tpm_communication_state = communication_state
        self.component_manager._communication_state = communication_state
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: None,
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        # TODO: This admin mode stuff is commented out in main also, why?
        # action_map_established = {
        #     AdminMode.ONLINE: "component_connected",
        #     AdminMode.OFFLINE: "component_disconnected",
        #     AdminMode.MAINTENANCE: "component_connected",
        #     AdminMode.NOT_FITTED: "component_disconnected",
        #     AdminMode.RESERVED: "component_disconnected",
        # }

        admin_mode = self.admin_mode_model.admin_mode
        power_state = self.component_manager.power_state
        self.logger.debug(
            f"communication_state: {communication_state}, adminMode: {admin_mode}, "
            f"powerMode: {power_state}"
        )
        # admin mode stuff here
        action = action_map[communication_state]
        # See TODO above.
        # if communication_state == CommunicationStatus.ESTABLISHED:
        #     action = action_map_established[admin_mode]
        if action is not None:
            self.op_state_model.perform_action(action)
        # if communication has been established, update power mode
        if (communication_state == CommunicationStatus.ESTABLISHED) and (
            admin_mode in [AdminMode.ONLINE, AdminMode.MAINTENANCE]
        ):
            self.component_state_changed_callback({"power_state": power_state})

        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    def component_state_changed_callback(
        self: MccsTile, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: the state change of the component
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }

        if "power_state" in state_change.keys():
            power_state = state_change.get("power_state")
            self.component_manager.update_tpm_power_state(power_state)
            if power_state is not None:
                self.op_state_model.perform_action(action_map[power_state])

        if "fault" in state_change.keys():
            is_fault = state_change.get("fault")
            if is_fault:
                self.op_state_model.perform_action("component_fault")
                self._health_model.component_fault(True)
            else:
                if self.component_manager.power_state is not None:
                    self.op_state_model.perform_action(
                        action_map[self.component_manager.power_state]
                    )
                self._health_model.component_fault(False)

        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------
    @attribute(dtype=SimulationMode, memorized=True, hw_memorized=True)
    def simulationMode(self: MccsTile) -> int:
        """
        Report the simulation mode of the device.

        :return: Return the current simulation mode
        """
        return self.component_manager.simulation_mode

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(self: MccsTile, value):
        """
        Set the simulation mode.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.component_manager.simulation_mode = SimulationMode(value)

    @attribute(dtype=TestMode, memorized=True, hw_memorized=True)
    def testMode(self: MccsTile) -> int:
        """
        Report the test mode of the device.

        :return: the current test mode
        """
        return self.component_manager.test_mode

    @testMode.write  # type: ignore[no-redef]
    def testMode(self: MccsTile, value: int) -> None:
        """
        Set the test mode.

        :param value: The test mode, as a TestMode value
        """
        self.component_manager.test_mode = TestMode(value)

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
        status_names = {
            TpmStatus.UNKNOWN: "Unknown",
            TpmStatus.OFF: "Off",
            TpmStatus.UNCONNECTED: "Unconnected",
            TpmStatus.UNPROGRAMMED: "NotProgrammed",
            TpmStatus.PROGRAMMED: "Programmed",
            TpmStatus.INITIALISED: "Initialised",
            TpmStatus.SYNCHRONISED: "Synchronised",
        }
        status = self.component_manager.tpm_status
        return status_names[status]

    @attribute(dtype="DevLong")
    def stationId(self: MccsTile) -> int:
        """
        Return the id of the station to which this tile is assigned.

        :return: the id of the station to which this tile is assigned
        """
        return self.component_manager.station_id

    @stationId.write  # type: ignore[no-redef]
    def stationId(self: MccsTile, value: int) -> None:
        """
        Set the id of the station to which this tile is assigned.

        :param value: the station id
        """
        self.component_manager.station_id = value

    @attribute(dtype="DevString")
    def cspDestinationIp(self: MccsTile) -> str:
        """
        Return the CSP destination IP address.

        :return: the CSP destination IP address
        """
        return self._csp_destination_ip

    @cspDestinationIp.write  # type: ignore[no-redef]
    def cspDestinationIp(self: MccsTile, value: str) -> None:
        """
        Set the CSP destination IP address.

        :param value: the new IP address
        """
        self._csp_destination_ip = value

    @attribute(dtype="DevString")
    def cspDestinationMac(self: MccsTile) -> str:
        """
        Return the CSP destination MAC address.

        :return: a MAC address
        """
        return self._csp_destination_mac

    @cspDestinationMac.write  # type: ignore[no-redef]
    def cspDestinationMac(self: MccsTile, value: str) -> None:
        """
        Set the CSP destination MAC address.

        :param value: MAC address
        """
        self._csp_destination_mac = value

    @attribute(dtype="DevLong")
    def cspDestinationPort(self: MccsTile) -> int:
        """
        Return the cspDestinationPort attribute.

        :return: CSP destination port
        """
        return self._csp_destination_port

    @cspDestinationPort.write  # type: ignore[no-redef]
    def cspDestinationPort(self: MccsTile, value: int) -> None:
        """
        Set the CSP destination port.

        :param value: CSP destination port
        """
        self._csp_destination_port = value

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
    def voltage(self: MccsTile) -> float:
        """
        Return the voltage.

        :return: voltage
        """
        return self.component_manager.voltage

    @attribute(
        dtype="DevDouble",
        abs_change=0.05,
        min_value=0.0,
        max_value=3.0,
        min_warning=0.1,
        max_warning=2.85,
        min_alarm=0.05,
        max_alarm=2.95,
    )
    def current(self: MccsTile) -> float:
        """
        Return the current.

        :return: current
        """
        return self.component_manager.current

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

    @attribute(dtype=("DevString",), max_dim_x=256)
    def fortyGbDestinationIps(self: MccsTile) -> list[str]:
        """
        Return the destination IPs for all 40Gb ports on the tile.

        :return: IP addresses
        """
        return [
            item["dst_ip"] for item in self.component_manager.get_40g_configuration()
        ]

    @attribute(dtype=("DevLong",), max_dim_x=256)
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
    def checkPendingDataRequests(self: MccsTile) -> bool:
        """
        Check for pending data requests.

        :return: whether there are data requests pending
        """
        return self.component_manager.check_pending_data_requests()

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

        :return: Return the PPS delay
        """
        return self.component_manager.pps_delay

    @attribute(dtype="DevBoolean")
    def TestGeneratorActive(self: MccsTile) -> bool:
        """
        Report if the test generator is used for some channels.

        :return: test generator status
        """
        return self.component_manager.test_generator_active

    # # --------
    # # Commands
    # # --------

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
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetFirmwareAvailableCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.GetFirmwareAvailableCommand,
        ) -> str:
            """
            Implement :py:meth:`.MccsTile.GetFirmwareAvailable` command functionality.

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
        else:
            return ([ResultCode.FAILED], [f"{argin} doesn't exist"])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ProgramCPLD(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Program the CPLD.

        If the TPM has a CPLD (or other management chip which need firmware), this
        function program it with the provided bitfile.

        :param argin: is the path to a file containing the required CPLD firmware

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ProgramCPLD", "/tmp/firmware/bitfile")
        """
        handler = self.get_command_object("ProgramCPLD")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    class GetRegisterListCommand(FastCommand):
        """Class for handling the GetRegisterList() command."""

        def __init__(
            self: MccsTile.GetRegisterListCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new GetRegisterListCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.GetRegisterListCommand,
        ) -> list[str]:
            """
            Implement :py:meth:`.MccsTile.GetRegisterList` command functionality.

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
            component_manager,
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
            self: MccsTile.ReadRegisterCommand, argin: str
        ) -> list[int]:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsTile.ReadRegister` command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                including RegisterName, NbRead, Offset, Device

            :return: list of register values

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self._component_manager.logger.error(
                    "RegisterName is a mandatory parameter"
                )
                raise ValueError("RegisterName is a mandatory parameter")
            nb_read = params.get("NbRead", None)
            if nb_read is None:
                self._component_manager.logger.error("NbRead is a mandatory parameter")
                raise ValueError("NbRead is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self._component_manager.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self._component_manager.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            return self._component_manager.read_register(name, nb_read, offset, device)

    @command(dtype_in="DevString", dtype_out="DevVarLongArray")
    def ReadRegister(self: MccsTile, argin: str) -> list[int]:
        """
        Return the value(s) of the specified register.

        :param argin: json dictionary with mandatory keywords:

        * RegisterName - (string) register_name is the registers string representation
        * NbRead - (int) is the number of 32-bit values to read
        * Offset - (int) offset is the address offset within the register to write to
        * Device - (int) device is the FPGA to write to (0 or 1)

        :return: a list of register values

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "NbRead": nb_read,
                    "Offset": offset, "Device":device}
        >>> jstr = json.dumps(dict)
        >>> values = dp.command_inout("ReadRegister", jstr)
        """
        handler = self.get_command_object("ReadRegister")
        return handler(argin)

    class WriteRegisterCommand(FastCommand):
        """Class for handling the WriteRegister(argin) command."""

        def __init__(
            self: MccsTile.WriteRegisterCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new WriteRegisterCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.WriteRegisterCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.WriteRegister` command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                including RegisterName, Values, Offset, Device

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks
                mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            name = params.get("RegisterName", None)
            if name is None:
                self._component_manager.logger.error(
                    "RegisterName is a mandatory parameter"
                )
                raise ValueError("RegisterName is a mandatory parameter")
            values = params.get("Values", None)
            if values is None:
                self._component_manager.logger.error("Values is a mandatory parameter")
                raise ValueError("Values is a mandatory parameter")
            offset = params.get("Offset", None)
            if offset is None:
                self._component_manager.logger.error("Offset is a mandatory parameter")
                raise ValueError("Offset is a mandatory parameter")
            device = params.get("Device", None)
            if device is None:
                self._component_manager.logger.error("Device is a mandatory parameter")
                raise ValueError("Device is a mandatory parameter")

            self._component_manager.write_register(name, values, offset, device)
            return (ResultCode.OK, "WriteRegister completed OK")

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def WriteRegister(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Write values to the specified register.

        :param argin: json dictionary with mandatory keywords:

        * RegisterName - (string) register_name is the registers string representation
        * Values - (list) is a list containing the 32-bit values to write
        * Offset - (int) offset is the address offset within the register to write to
        * Device - (int) device is the FPGA to write to (0 or 1)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"RegisterName": "test-reg1", "Values": values,
                    "Offset": offset, "Device":device}
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
            component_manager,
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
            self: MccsTile.ReadAddressCommand, argin: list[int]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ReadAddress` command functionality.

            :param argin: sequence of length two, containing an address and
                a value

            :return: [values, ]

            :raises ValueError: if the argin argument has the wrong length
                or structure
            """
            if len(argin) < 2:
                self._component_manager.logger.error("Two parameters are required")
                raise ValueError("Two parameters are required")
            address = argin[0]
            nvalues = argin[1]
            return self._component_manager.read_address(address, nvalues)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarULongArray")
    def ReadAddress(self: MccsTile, argin: list[int]) -> list[int]:
        """
        Read n 32-bit values from address.

        :param argin: [0] = address to read from
                      [1] = number of values to read

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
            component_manager,
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
            self: MccsTile.WriteAddressCommand, argin: list[int]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.WriteAddress` command functionality.

            :param argin: sequence of length two, containing an address and
                a value

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin has the wrong length/structure
            """
            if len(argin) < 2:
                self._component_manager.logger.error(
                    "A minimum of two parameters are required"
                )
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
        """Class for handling the Configure40GCore(argin) command."""

        def __init__(
            self: MccsTile.Configure40GCoreCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new Configure40GCoreCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "Configure40GCore command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.Configure40GCoreCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.Configure40GCore` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)

            core_id = params.get("CoreID", None)
            if core_id is None:
                message = "CoreID is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)
            arp_table_entry = params.get("ArpTableEntry", None)
            if arp_table_entry is None:
                message = "ArpTableEntry is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)
            src_mac = params.get("SrcMac", None)
            if src_mac is None:
                message = "SrcMac is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)
            src_ip = params.get("SrcIP", None)
            src_port = params.get("SrcPort", None)
            if src_port is None:
                message = "SrcPort is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)
            dst_ip = params.get("DstIP", None)
            if dst_ip is None:
                message = "DstIP is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)
            dst_port = params.get("DstPort", None)
            if dst_port is None:
                message = "DstPort is a mandatory parameter."
                self._component_manager.logger.error(message)
                raise ValueError(message)

            self._component_manager.configure_40g_core(
                core_id, arp_table_entry, src_mac, src_ip, src_port, dst_ip, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure40GCore(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Configure 40g core_id with specified parameters.

        :param argin: json dictionary with optional keywords:

        * CoreID - (int) core id
        * ArpTableEntry - (int) ARP table entry ID
        * SrcMac - (int) mac address
        * SrcIP - (string) IP dot notation.
        * SrcPort - (int) source port
        * SrcPort - (int) source port
        * DstIP - (string) IP dot notation
        * DstPort - (int) destination port

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CoreID":2, "ArpTableEntry":0, "SrcMac":0x62000a0a01c9,
                    "SrcIP":"10.0.99.3", "SrcPort":4000, "DstMac":"10:fe:ed:08:0a:58",
                    "DstIP":"10.0.99.3", "DstPort":5000}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("Configure40GCore", jstr)
        """
        handler = self.get_command_object("Configure40GCore")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class Get40GCoreConfigurationCommand(FastCommand):
        """Class for handling the Get40GCoreConfiguration(argin) command."""

        def __init__(
            self: MccsTile.Get40GCoreConfigurationCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new Get40GCoreConfigurationCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.Get40GCoreConfigurationCommand, argin: str
        ) -> str:
            """
            Implement :py:meth:`.MccsTile.Get40GCoreConfiguration` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: json string with configuration

            :raises ValueError: if the argin is an invalid code id
            """
            params = json.loads(argin)
            core_id = params.get("CoreID", None)
            arp_table_entry = params.get("ArpTableEntry", 0)

            item_list = self._component_manager.get_40g_configuration(
                core_id, arp_table_entry
            )
            item_new = []
            for item in item_list:
                item_new.append(
                    {
                        "CoreID": item.get("core_id", None),
                        "ArpTableEntry": item.get("arp_table_entry", None),
                        "SrcMac": item.get("src_mac", None),
                        "SrcIP": item.get("src_ip", None),
                        "SrcPort": item.get("src_port", None),
                        "DstIP": item.get("dst_ip", None),
                        "DstPort": item.get("dst_port", None),
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

        * CoreID - (int) core id
        * ArpTableEntry - (int) ARP table entry ID to use

        :return: the configuration is a json string describilg a list (possibly empty)
                 Each list entry comprising:
                 core_id, arp_table_entry, src_mac, src_ip, src_port, dest_ip, dest_port

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
        """Class for handling the SetLmcDownload(argin) command."""

        def __init__(
            self: MccsTile.SetLmcDownloadCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetLmcDownloadCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetLmcDownload command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetLmcDownloadCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetLmcDownload` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self._component_manager.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            payload_length = params.get("PayloadLength", 1024)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xF0D0)
            dst_port = params.get("DstPort", 4660)

            self._component_manager.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetLmcDownload(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param argin: json dictionary with optional keywords:

        * Mode - (string) '1g' or '10g' (Mandatory) (use '10g' for 40g also)
        * PayloadLength - (int) SPEAD payload length for channel data
        * DstIP - (string) Destination IP.
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"Mode": "1G", "PayloadLength":4,DstIP="10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    @command(dtype_out="DevString")
    def GetArpTable(self: MccsTile) -> str:
        """
        Return a dictionary with populated ARP table for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer,
        1 for LMC.10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for
        beamforming, and 2, 6 for LMC with only one ARP.

        :return: a JSON-encoded dictionary of coreId and populated arpID table

        :example:

        >>> argout = dp.command_inout("GetArpTable")
        >>> dict = json.loads(argout)
        >>>    {
        >>>    "core_id0": [arpID0, arpID1],
        >>>    "core_id1": [arpID0],
        >>>    "core_id3": [],
        >>>    }
        """
        handler = self.get_command_object("GetArpTable")
        return_code, unique_id = handler()
        return ([return_code], [unique_id])

    class SetChanneliserTruncationCommand(FastCommand):
        """Class for handling the SetChanneliserTruncation(argin) command."""

        def __init__(
            self: MccsTile.SetChanneliserTruncationCommand,
            component_manager: TileComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetChanneliserTruncationCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetChannelizerTruncation command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetChanneliserTruncationCommand, argin: list[int]
        ) -> Any:
            """
            Implement :py:meth:`.MccsTile.SetChanneliserTruncation` commands.

            :param argin: a truncation array

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 3:
                self._component_manager.logger.error("Insufficient values supplied")
                raise ValueError("Insufficient values supplied")
            nb_chan = argin[0]
            nb_freq = argin[1]
            arr = np.array(argin[2:])
            array2d = np.reshape(arr, (nb_chan, nb_freq))

            self._component_manager.set_channeliser_truncation(array2d)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    def SetChanneliserTruncation(
        self: MccsTile, argin: list[int]
    ) -> DevVarLongStringArrayType:
        """
        Set the coefficients to modify (flatten) the bandpass.

        :param argin: truncation is a N x M array

        * argin[0] - is N, the number of input channels
        * argin[1] - is M, the number of frequency channel
        * argin[2:] - is the data

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> n=4
        >>> m=3
        >>> trunc = ([0, 1, 2], [3, 4, 5],[6, 7, 0], [1, 2, 3],]
        >>> arr = np.array(trunc).ravel()
        >>> argin = np.concatenate([np.array((4, 3)), arr])
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetChanneliserTruncation", argin)
        """
        handler = self.get_command_object("SetChanneliserTruncation")
        result_code, message = handler(argin)
        return ([result_code], [message])

    class SetBeamFormerRegionsCommand(FastCommand):
        """Class for handling the SetBeamFormerRegions(argin) command."""

        def __init__(
            self: MccsTile.SetBeamFormerRegionsCommand,
            component_manager,
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
            self: MccsTile.SetBeamFormerRegionsCommand, argin: list[int]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetBeamFormerRegions` command functionality.

            :param argin: a region array

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 8:
                self._component_manager.logger.error(
                    "Insufficient parameters specified"
                )
                raise ValueError("Insufficient parameters specified")
            if len(argin) > (48 * 8):
                self._component_manager.logger.error("Too many regions specified")
                raise ValueError("Too many regions specified")
            if len(argin) % 8 != 0:
                self._component_manager.logger.error(
                    "Incomplete specification of region"
                )
                raise ValueError("Incomplete specification of region")
            regions = []
            total_chan = 0
            for i in range(0, len(argin), 8):
                region = argin[i : i + 8]  # noqa: E203
                start_channel = region[0]
                if start_channel % 2 != 0:
                    self._component_manager.logger.error(
                        "Start channel in region must be even"
                    )
                    raise ValueError("Start channel in region must be even")
                nchannels = region[1]
                if nchannels % 8 != 0:
                    self._component_manager.logger.error(
                        "Nos. of channels in region must be multiple of 8"
                    )
                    raise ValueError("Nos. of channels in region must be multiple of 8")
                beam_index = region[2]
                if beam_index < 0 or beam_index > 47:
                    self._component_manager.logger.error(
                        "Beam_index is out side of range 0-47"
                    )
                    raise ValueError("Beam_index is out side of range 0-47")
                total_chan += nchannels
                if total_chan > 384:
                    self._component_manager.logger.error(
                        "Too many channels specified > 384"
                    )
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

        region_array is defined as a 2D array, for a maximum of 48 regions. Total number
        of channels must be <= 384.

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
        """Class for handling the ConfigureStationBeamformer(argin) command."""

        def __init__(
            self: MccsTile.ConfigureStationBeamformerCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureStationBeamformerCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "LoadCalibrationCoefficients command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureStationBeamformerCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureStationBeamformer` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            params = json.loads(argin)
            start_channel = params.get("StartChannel", None)
            if start_channel is None:
                self._component_manager.logger.error(
                    "StartChannel is a mandatory parameter"
                )
                raise ValueError("StartChannel is a mandatory parameter")
            ntiles = params.get("NumTiles", None)
            if ntiles is None:
                self._component_manager.logger.error(
                    "NumTiles is a mandatory parameter"
                )
                raise ValueError("NumTiles is a mandatory parameter")
            is_first = params.get("IsFirst", None)
            if is_first is None:
                self._component_manager.logger.error("IsFirst is a mandatory parameter")
                raise ValueError("IsFirst is a mandatory parameter")
            is_last = params.get("IsLast", None)
            if is_last is None:
                self._component_manager.logger.error("IsLast is a mandatory parameter")
                raise ValueError("IsLast is a mandatory parameter")

            self._component_manager.initialise_beamformer(
                start_channel, ntiles, is_first, is_last
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureStationBeamformer(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Initialise and start the station beamformer.

        :param argin: json dictionary with mandatory keywords:

        * StartChannel - (int) start channel
        * NumTiles - (int) is the number of tiles in the station
        * IsFirst - (bool) specifies whether the tile is the first one in the station
        * IsLast - (bool) specifies whether the tile is the last one in the station

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dict = {"StartChannel":1, "NumTiles":10, "IsTile":True, "isFirst":True,
        >>         "isLast:True}
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
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new LoadCalibrationCoefficientsCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureStationBeamformer command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.LoadCalibrationCoefficientsCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadCalibrationCoefficients` commands.

            :param argin: calibration coefficients

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 9:
                self._component_manager.logger.error(
                    "Insufficient calibration coefficients"
                )
                raise ValueError("Insufficient calibration coefficients")
            if len(argin[1:]) % 8 != 0:
                self._component_manager.logger.error(
                    "Incomplete specification of coefficient"
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

        This is performed by switch_calibration_bank.
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

    class LoadCalibrationCurveCommand(FastCommand):
        """Class for handling the LoadCalibrationCurve(argin) command."""

        def __init__(
            self: MccsTile.LoadCalibrationCurveCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new LoadCalibrationCurveCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "LoadCalibrationCurve command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.LoadCalibrationCurveCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement:py:meth:`.MccsTile.LoadCalibrationCurve` command functionality.

            :param argin: antenna, beam, calibration coefficients

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < 10:
                self._component_manager.logger.error(
                    "Insufficient calibration coefficients"
                )
                raise ValueError("Insufficient calibration coefficients")
            if len(argin[2:]) % 8 != 0:
                self._component_manager.logger.error(
                    "Incomplete specification of coefficient"
                )
                raise ValueError("Incomplete specification of coefficient")
            antenna = int(argin[0])
            beam = int(argin[1])
            calibration_coefficients = [
                [
                    complex(argin[i], argin[i + 1]),
                    complex(argin[i + 2], argin[i + 3]),
                    complex(argin[i + 4], argin[i + 5]),
                    complex(argin[i + 6], argin[i + 7]),
                ]
                for i in range(2, len(argin), 8)
            ]

            self._component_manager.load_calibration_curve(
                antenna, beam, calibration_coefficients
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadCalibrationCurve(
        self: MccsTile, argin: list[float]
    ) -> DevVarLongStringArrayType:
        """
        Load calibration curve.

        This is the frequency dependent response for a single
        antenna and beam, as a function of frequency. It will be combined together with
        tapering coefficients and beam angles by ComputeCalibrationCoefficients, which
        will also make them active like SwitchCalibrationBank. The calibration
        coefficients do not include the geometric delay.

        :param argin: list comprises:

        * antenna - (int) is the antenna to which the coefficients will be applied.
        * beam    - (int) is the beam to which the coefficients will be applied.
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
        >>> beam = 3
        >>> complex_coefficients = [[complex(3.4, 1.2), complex(2.3, 4.1),
        >>>            complex(4.6, 8.2), complex(6.8, 2.4)]]*5
        >>> inp = list(itertools.chain.from_iterable(complex_coefficients))
        >>> out = ([v.real, v.imag] for v in inp]
        >>> coefficients = list(itertools.chain.from_iterable(out))
        >>> coefficients.insert(0, float(antenna))
        >>> coefficients.insert(1, float(beam))
        >>> input = list(itertools.chain.from_iterable(coefficients))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadCalbrationCurve", input)
        """
        handler = self.get_command_object("LoadCalibrationCurve")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class LoadBeamAngleCommand(FastCommand):
        """Class for handling the LoadBeamAngle(argin) command."""

        def __init__(
            self: MccsTile.LoadBeamAngleCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new LoadBeamAngleCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "LoadBeamAngle command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.LoadBeamAngleCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement:py:meth:`.MccsTile.LoadBeamAngle` command functionality.

            :param argin: angle coefficients

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.load_beam_angle(argin)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadBeamAngle(self: MccsTile, argin: list[float]) -> DevVarLongStringArrayType:
        """
        Load the beam angle coefficients.

        angle_coefficients in argin is an array of one element per beam, specifying a
        rotation angle, in radians, for the specified beam. The rotation is the same for
        all antennas. Default is 0 (no rotation). A positive pi/4 value transfers the X
        polarization to the Y polarization. The rotation is applied after regular
        calibration.

        :param argin: list of angle coefficients for each beam

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> angle_coefficients = [3.4] * 16
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadBeamAngle", angle_coefficients)
        """
        handler = self.get_command_object("LoadBeamAngle")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class LoadAntennaTaperingCommand(FastCommand):
        """Class for handling the LoadAntennaTapering(argin) command."""

        SUCCEEDED_MESSAGE = "LoadAntennaTapering command completed OK"

        def __init__(
            self: MccsTile.LoadAntennaTaperingCommand,
            component_manager,
            logger: logging.Logger,
            antennas_per_tile: int,
        ) -> None:
            """
            Initialise a new LoadAntennaTaperingCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :param antennas_per_tile: the number of antennas per tile
            """
            self._component_manager = component_manager
            super().__init__(logger)
            self._antennas_per_tile = antennas_per_tile

        def do(  # type: ignore[override]
            self: MccsTile.LoadAntennaTaperingCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadAntennaTapering` command functionality.

            :param argin: beam index, antenna tapering coefficients

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < self._antennas_per_tile + 1:
                self._component_manager.logger.error(
                    f"Insufficient coefficients should be {self._antennas_per_tile+1}"
                )
                raise ValueError(
                    f"Insufficient coefficients should be {self._antennas_per_tile+1}"
                )

            beam = int(argin[0])
            if beam < 0 or beam > 47:
                self._component_manager.logger.error(
                    "Beam index should be in range 0 to 47"
                )
                raise ValueError("Beam index should be in range 0 to 47")

            tapering = argin[1:]
            self._component_manager.load_antenna_tapering(beam, tapering)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def LoadAntennaTapering(
        self: MccsTile, argin: list[float]
    ) -> DevVarLongStringArrayType:
        """
        Load antenna tapering coefficients.

        tapering_coefficients in argin is a vector contains a value for each antenna the
        TPM processes. Default at initialisation is 1.0.

        :param argin: beam index, list of tapering coefficients for each antenna

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> beam = 2
        >>> tapering_coefficients = [3.4] * 16
        >>> tapering_coefficients.insert(0, float(beam))
        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadAntennaTapering", tapering_coefficients)
        """
        handler = self.get_command_object("LoadAntennaTapering")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SwitchCalibrationBankCommand(FastCommand):
        """Class for handling the SwitchCalibrationBank(argin) command."""

        def __init__(
            self: MccsTile.SwitchCalibrationBankCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SwitchCalibrationBankCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SwitchCalibrationBank command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SwitchCalibrationBankCommand, argin: int
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SwitchCalibrationBank` command functionality.

            :param argin: switch time

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            switch_time = argin

            self._component_manager.switch_calibration_bank(switch_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevLong", dtype_out="DevVarLongStringArray")
    def SwitchCalibrationBank(self: MccsTile, argin: int) -> DevVarLongStringArrayType:
        """
        Load the calibration coefficients at the specified time delay.

        :param argin: switch time

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SwitchCalibrationBank", 10)
        """
        handler = self.get_command_object("SwitchCalibrationBank")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SetPointingDelayCommand(FastCommand):
        """Class for handling the SetPointingDelay(argin) command."""

        SUCCEEDED_MESSAGE = "SetPointingDelay command completed OK"

        def __init__(
            self: MccsTile.SetPointingDelayCommand,
            component_manager,
            logger: logging.Logger,
            antennas_per_tile: int,
        ) -> None:
            """
            Initialise a new SetPointingDelayCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :param antennas_per_tile: the number of antennas per tile
            """
            self._component_manager = component_manager
            super().__init__(logger)
            self._antennas_per_tile = antennas_per_tile

        def do(  # type: ignore[override]
            self: MccsTile.SetPointingDelayCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetPointingDelay` command functionality.

            :param argin: an array containing a beam index and antenna
                delays

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) != self._antennas_per_tile * 2 + 1:
                self._component_manager.logger.error("Insufficient parameters")
                raise ValueError("Insufficient parameters")
            beam_index = int(argin[0])
            if beam_index < 0 or beam_index > 7:
                self._component_manager.logger.error("Invalid beam index")
                raise ValueError("Invalid beam index")
            delay_array = []
            for i in range(self._antennas_per_tile):
                delay_array.append([argin[i * 2 + 1], argin[i * 2 + 2]])

            self._component_manager.set_pointing_delay(delay_array, beam_index)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def SetPointingDelay(
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
        handler = self.get_command_object("SetPointingDelay")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class LoadPointingDelayCommand(FastCommand):
        """Class for handling the LoadPointingDelay(argin) command."""

        def __init__(
            self: MccsTile.LoadPointingDelayCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new LoadPointingDelayCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "LoadPointingDelay command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.LoadPointingDelayCommand, argin: int
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadPointingDelay` command functionality.

            :param argin: load time

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            load_time = argin

            self._component_manager.load_pointing_delay(load_time)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevLong", dtype_out="DevVarLongStringArray")
    def LoadPointingDelay(self: MccsTile, argin: int) -> DevVarLongStringArrayType:
        """
        Load the pointing delays at the specified time delay.

        :param argin: time delay (default = 0)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("LoadPointingDelay", 10)
        """
        handler = self.get_command_object("LoadPointingDelay")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StartBeamformerCommand(FastCommand):
        """Class for handling the StartBeamformer(argin) command."""

        def __init__(
            self: MccsTile.StartBeamformerCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new StartBeamformerCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "StartBeamformer command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.StartBeamformerCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StartBeamformer` command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                "StartTime" and "Duration"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            start_time = params.get("StartTime", 0)
            duration = params.get("Duration", -1)
            self._component_manager.start_beamformer(start_time, duration)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartBeamformer(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Start the beamformer at the specified time delay.

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Duration - (int) if > 0 is a duration in frames * 256 (276.48 us)
                           if == -1 run forever

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
            component_manager,
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

        def do(  # type: ignore[override]
            self: MccsTile.StopBeamformerCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopBeamformer` command functionality.

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
        """Class for handling the ConfigureIntegratedChannelData(argin) command."""

        def __init__(
            self: MccsTile.ConfigureIntegratedChannelDataCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureIntegratedChannelDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureIntegratedChannelData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureIntegratedChannelDataCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedChannelData` commands.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            integration_time = params.get("IntegrationTime", 0.5)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)

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

        * integration time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 511

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedChannelData", 6.284, 0, 511)
        """
        handler = self.get_command_object("ConfigureIntegratedChannelData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ConfigureIntegratedBeamDataCommand(FastCommand):
        """Class for handling the ConfigureIntegratedBeamData(argin) command."""

        def __init__(
            self: MccsTile.ConfigureIntegratedBeamDataCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureIntegratedBeamDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureIntegratedBeamData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureIntegratedBeamDataCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedBeamData` commands.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            integration_time = params.get("IntegrationTime", 0.5)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 191)

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

        * integration time - (float) in seconds (default = 0.5)
        * first_channel - (int) default 0
        * last_channel - (int) default 191

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ConfigureIntegratedBeamData", 3.142, 0, 191)
        """
        handler = self.get_command_object("ConfigureIntegratedBeamData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StopIntegratedDataCommand(FastCommand):
        """Class for handling the StopIntegratedData command."""

        def __init__(
            self: MccsTile.StopIntegratedDataCommand,
            component_manager,
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

        def do(  # type: ignore[override]
            self: MccsTile.StopIntegratedDataCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopIntegratedData` command functionality.

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

    class SendRawDataCommand(FastCommand):
        """Class for handling the SendRawData(argin) command."""

        def __init__(
            self: MccsTile.SendRawDataCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendRawDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendRawData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendRawDataCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendRawData` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            sync = params.get("Sync", False)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            self._component_manager.send_raw_data(sync, timestamp, seconds)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendRawData(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Transmit a snapshot containing raw antenna data.

        :param argin: json dictionary with optional keywords:

        * Sync - (bool) synchronised flag
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Sync":True, "Seconds": 0.2}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawData", jstr)
        """
        handler = self.get_command_object("SendRawData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SendChannelisedDataCommand(FastCommand):
        """Class for handling the SendChannelisedData(argin) command."""

        def __init__(
            self: MccsTile.SendChannelisedDataCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendChannelisedDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendChannelisedData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendChannelisedDataCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendChannelisedData` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            number_of_samples = params.get("NSamples", 1024)
            first_channel = params.get("FirstChannel", 0)
            last_channel = params.get("LastChannel", 511)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            self._component_manager.send_channelised_data(
                number_of_samples, first_channel, last_channel, timestamp, seconds
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendChannelisedData(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Transmit a snapshot of channelized data totalling number_of_samples spectra.

        :param argin: json dictionary with optional keywords:

        * NSamples - (int) number of spectra to send
        * FirstChannel - (int) first channel to send
        * LastChannel - (int) last channel to send
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"FirstChannel":10, "LastChannel": 200, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedData", jstr)
        """
        handler = self.get_command_object("SendChannelisedData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SendChannelisedDataContinuousCommand(FastCommand):
        """Class for handling the SendChannelisedDataContinuous(argin) command."""

        def __init__(
            self: MccsTile.SendChannelisedDataContinuousCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendChannelisedDataContinuousCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendChannelisedDataContinuous command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendChannelisedDataContinuousCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendChannelisedDataContinuous` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            channel_id = params.get("ChannelID")
            if channel_id is None:
                self._component_manager.logger.error(
                    "ChannelID is a mandatory parameter"
                )
                raise ValueError("ChannelID is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            self._component_manager.send_channelised_data_continuous(
                channel_id, number_of_samples, wait_seconds, timestamp, seconds
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendChannelisedDataContinuous(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Send data from channel channel continuously.

        Continues until stopped with StopDataTransmission command.

        :param argin: json dictionary with 1 mandatory and optional keywords:

        * ChannelID - (int) channel_id (Mandatory)
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timestamp - (int??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ChannelID":2, "NSamples":256, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataContinuous", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataContinuous")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SendBeamDataCommand(FastCommand):
        """Class for handling the SendBeamData(argin) command."""

        def __init__(
            self: MccsTile.SendBeamDataCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendBeamDataCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendBeamData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendBeamDataCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendBeamData` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)

            self._component_manager.send_beam_data(timestamp, seconds)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendBeamData(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Transmit a snapshot containing beamformed data.

        :param argin: json dictionary with optional keywords:

        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendBeamData", jstr)
        """
        handler = self.get_command_object("SendBeamData")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class StopDataTransmissionCommand(FastCommand):
        """Class for handling the StopDataTransmission() command."""

        def __init__(
            self: MccsTile.StopDataTransmissionCommand,
            component_manager,
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

        def do(  # type: ignore[override]
            self: MccsTile.StopDataTransmissionCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StopDataTransmission` command functionality.

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

    class ComputeCalibrationCoefficientsCommand(FastCommand):
        """Class for handling the ComputeCalibrationCoefficients() command."""

        def __init__(
            self: MccsTile.ComputeCalibrationCoefficientsCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ComputeCalibrationCoefficientsCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ComputeCalibrationCoefficients command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ComputeCalibrationCoefficientsCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ComputeCalibrationCoefficients` commands.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.compute_calibration_coefficients()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def ComputeCalibrationCoefficients(
        self: MccsTile,
    ) -> DevVarLongStringArrayType:
        """
        Compute the calibration coefficients.

        Use previously specified gain curves, tapering weights and beam angles,
        load them in the hardware. It must be followed
        by switch_calibration_bank() to make these active.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("ComputeCalibrationCoefficients")
        """
        handler = self.get_command_object("ComputeCalibrationCoefficients")
        (return_code, message) = handler()
        return ([return_code], [message])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StartAcquisition(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Start data acquisition.

        :param argin: json dictionary with optional keywords:

        * StartTime - (int) start time
        * Delay - (int) delay start

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"StartTime":10, "Delay":20}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("StartAcquisition", jstr)
        """
        handler = self.get_command_object("StartAcquisition")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    class SetTimeDelaysCommand(FastCommand):
        """Class for handling the SetTimeDelays(argin) command."""

        def __init__(
            self: MccsTile.SetTimeDelaysCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetTimeDelaysCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetTimeDelays command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetTimeDelaysCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement:py:meth:`.MccsTile.SetTimeDelays` command functionality.

            :param argin: time delays

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            delays = argin

            self._component_manager.set_time_delays(delays)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarDoubleArray", dtype_out="DevVarLongStringArray")
    def SetTimeDelays(self: MccsTile, argin: list[float]) -> DevVarLongStringArrayType:
        """
        Set coarse zenith delay for input ADC streams.

        Delay specified in nanoseconds, nominal is 0.

        :param argin: the delay in samples, positive delay adds delay
                       to the signal stream

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >> delays = [3.4] * n (How many & int or float : Alessio?)
        >> dp = tango.DeviceProxy("mccs/tile/01")
        >> dp.command_inout("SetTimedelays", delays)
        """
        handler = self.get_command_object("SetTimeDelays")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SetCspRoundingCommand(FastCommand):
        """Class for handling the SetCspRounding(argin) command."""

        def __init__(
            self: MccsTile.SetCspRoundingCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetCspRoundingCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetCspRounding command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetCspRoundingCommand, argin: float
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetCspRounding` command functionality.

            :param argin: csp rounding

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            rounding = argin

            self._component_manager.set_csp_rounding(rounding)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevDouble", dtype_out="DevVarLongStringArray")
    def SetCspRounding(self: MccsTile, argin: float) -> DevVarLongStringArrayType:
        """
        Set output rounding for CSP.

        :param argin: the rounding

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SetCspRounding", 3.142)
        """
        handler = self.get_command_object("SetCspRounding")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SetLmcIntegratedDownloadCommand(FastCommand):
        """Class for handling the SetLmcIntegratedDownload(argin) command."""

        def __init__(
            self: MccsTile.SetLmcIntegratedDownloadCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SetLmcIntegratedDownloadCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetLmcIntegratedDownload command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetLmcIntegratedDownloadCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SetLmcIntegratedDownload` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            mode = params.get("Mode", None)
            if mode is None:
                self._component_manager.logger.error("Mode is a mandatory parameter")
                raise ValueError("Mode is a mandatory parameter")
            channel_payload_length = params.get("ChannelPayloadLength", 1024)
            beam_payload_length = params.get("BeamPayloadLength", 1024)
            dst_ip = params.get("DstIP", None)
            src_port = params.get("SrcPort", 0xF0D0)
            dst_port = params.get("DstPort", 4660)

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

        * Mode - (string) '1g' or '10g' (Mandatory)
        * ChannelPayloadLength - (int) SPEAD payload length for integrated channel data
        * BeamPayloadLength - (int) SPEAD payload length for integrated beam data
        * DstIP - (string) Destination IP
        * SrcPort - (int) Source port for integrated data streams
        * DstPort - (int) Destination port for integrated data streams

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Mode": "1G", "ChannelPayloadLength":4,
                    "BeamPayloadLength": 1024, DstIP="10.0.1.23"}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SetLmcIntegratedDownload", jstr)
        """
        handler = self.get_command_object("SetLmcIntegratedDownload")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SendRawDataSynchronisedCommand(FastCommand):
        """Class for handling the SendRawDataSynchronised(argin) command."""

        def __init__(
            self: MccsTile.SendRawDataSynchronisedCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendRawDataSynchronisedCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendRawDataSynchronised command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendRawDataSynchronisedCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendRawDataSynchronised` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.1)

            self._component_manager.send_raw_data(
                sync=True, timestamp=timestamp, seconds=seconds
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendRawDataSynchronised(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Send synchronised raw data.

        :param argin: json dictionary with optional keywords:

        * Timestamp - (string??) When to send
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendRawDataSynchronised", jstr)
        """
        handler = self.get_command_object("SendRawDataSynchronised")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class SendChannelisedDataNarrowbandCommand(FastCommand):
        """Class for handling the SendChannelisedDataNarrowband(argin) command."""

        def __init__(
            self: MccsTile.SendChannelisedDataNarrowbandCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendChannelisedDataNarrowbandCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendChannelisedDataNarrowband command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendChannelisedDataNarrowbandCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendChannelisedDataNarrowband` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            frequency = params.get("Frequency", None)
            if frequency is None:
                self._component_manager.logger.error(
                    "Frequency is a mandatory parameter"
                )
                raise ValueError("Frequency is a mandatory parameter")
            round_bits = params.get("RoundBits", None)
            if round_bits is None:
                self._component_manager.logger.error(
                    "RoundBits is a mandatory parameter"
                )
                raise ValueError("RoundBits is a mandatory parameter")
            number_of_samples = params.get("NSamples", 128)
            wait_seconds = params.get("WaitSeconds", 0)
            timestamp = params.get("Timestamp", None)
            seconds = params.get("Seconds", 0.2)
            self._component_manager.send_channelised_data_narrowband(
                frequency,
                round_bits,
                number_of_samples,
                wait_seconds,
                timestamp,
                seconds,
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SendChannelisedDataNarrowband(
        self: MccsTile, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Continuously send channelised data from a single channel.

        and data from channel continuously (until stopped)

        This is a special mode used for UAV campaigns and not really
        part of the standard signal processing chain. I don’t know if
        this mode will be kept or not.

        :param argin: json dictionary with 2 mandatory and optional keywords:

        * Frequency - (int) Sky frequency to transmit
        * RoundBits - (int)  Specify which bits to round
        * NSamples -  (int) number of spectra to send
        * WaitSeconds - (int) Wait time before sending data
        * Timeout - (int) When to stop
        * Timestamp - (string??) When to start
        * Seconds - (float) When to synchronise

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"Frequency":2000, "RoundBits":256, "NSamples":256,
                    "WaitSeconds": 10, "Seconds": 0.5}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("SendChannelisedDataNarrowband", jstr)
        """
        handler = self.get_command_object("SendChannelisedDataNarrowband")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class TweakTransceiversCommand(FastCommand):
        """Class for handling the TweakTransceivers() command."""

        def __init__(
            self: MccsTile.TweakTransceiversCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new TweakTransceiversCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "TweakTransceivers command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.TweakTransceiversCommand,
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.TweakTransceivers` command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._component_manager.tweak_transceivers()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def TweakTransceivers(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Tweak the transceivers.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("tweak_transceivers")
        """
        handler = self.get_command_object("TweakTransceivers")
        (return_code, message) = handler()
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PostSynchronisation(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Post tile configuration synchronization.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("PostSynchronisation")
        """
        handler = self.get_command_object("PostSynchronisation")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def SyncFpgas(self: MccsTile) -> DevVarLongStringArrayType:
        """
        Synchronise the FPGAs.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dp.command_inout("SyncFpgas")
        """
        handler = self.get_command_object("SyncFpgas")
        (return_code, unique_id) = handler()
        return ([return_code], [unique_id])

    class CalculateDelayCommand(FastCommand):
        """Class for handling the CalculateDelay(argin) command."""

        def __init__(
            self: MccsTile.CalculateDelayCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new CalculateDelayCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "CalculateDelay command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.CalculateDelayCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.CalculateDelay` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the JSON input lacks
                mandatory parameters

            :todo: Mandatory JSON parameters should be handled by validation
                against a schema
            """
            params = json.loads(argin)
            current_delay = params.get("CurrentDelay", None)
            if current_delay is None:
                self._component_manager.logger.error(
                    "CurrentDelay is a mandatory parameter"
                )
                raise ValueError("CurrentDelay is a mandatory parameter")
            current_tc = params.get("CurrentTC", None)
            if current_tc is None:
                self._component_manager.logger.error(
                    "CurrentTC is a mandatory parameter"
                )
                raise ValueError("CurrentTC is a mandatory parameter")
            ref_lo = params.get("RefLo", None)
            if ref_lo is None:
                self._component_manager.logger.error("RefLo is a mandatory parameter")
                raise ValueError("RefLo is a mandatory parameter")
            ref_hi = params.get("RefHi", None)
            if ref_hi is None:
                self._component_manager.logger.error("RefHi is a mandatory parameter")
                raise ValueError("RefHi is a mandatory parameter")

            self._component_manager.calculate_delay(
                current_delay, current_tc, ref_lo, ref_hi
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def CalculateDelay(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Calculate delay.

        :param argin: json dictionary with 4 mandatory keywords:

        * CurrentDelay - (float??) Current delay
        * CurrentTC - (float??) Current phase register terminal count
        * RefLo - (float??) Low reference
        * RefHi -(float??) High reference

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"CurrentDelay":0.4, "CurrentTC":56.2, "RefLo":3.0, "RefHi":78.9}
        >>> jstr = json.dumps(dict)
        >>> dp.command_inout("CalculateDelay", jstr)
        """
        handler = self.get_command_object("CalculateDelay")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class ConfigureTestGeneratorCommand(FastCommand):
        """Class for handling the ConfigureTestGenerator(argin) command."""

        def __init__(
            self: MccsTile.ConfigureTestGeneratorCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new ConfigureTestGeneratorCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureTestGenerator command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureTestGeneratorCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureTestGenerator` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :raises ValueError: if the JSON input has invalid parameters

            :todo: Mandatory JSON parameters should be handled by validation
                   against a schema
            :return: A tuple containing a return code and a string
                   message indicating status. The message is for
                   information purpose only.
            """
            params = json.loads(argin)
            active = False
            set_time = params.get("SetTime", 0)
            if "ToneFrequency" in params:
                frequency0 = params["ToneFrequency"]
                amplitude0 = params.get("ToneAmplitude", 1.0)
                active = True
            else:
                frequency0 = 0.0
                amplitude0 = 0.0

            if "Tone2Frequency" in params:
                frequency1 = params["Tone2Frequency"]
                amplitude1 = params.get("Tone2Amplitude", 1.0)
                active = True
            else:
                frequency1 = 0.0
                amplitude1 = 0.0

            if "NoiseAmplitude" in params:
                amplitude_noise = params.get("NoiseAmplitude", 1.0)
                active = True
            else:
                amplitude_noise = 0.0

            if "PulseFrequency" in params:
                pulse_code = params["PulseFrequency"]
                if (pulse_code < 0) or (pulse_code > 7):
                    raise ValueError("PulseFrequency must be between 0 and 7")
                amplitude_pulse = params.get("PulseAmplitude", 1.0)
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

            chans = params.get("AdcChannels")
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

        def check_allowed(
            self: MccsTile.ConfigureTestGeneratorCommand,
        ) -> bool:
            """
            Check if command is allowed.

            It is allowed only in maintenance mode.

            :returns: whether the command is allowed
            """
            return self.target.admin_mode_model.admin_mode == AdminMode.MAINTENANCE

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def ConfigureTestGenerator(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
        """
        Set the test signal generator.

        :param argin: json dictionary with keywords:

        * ToneFrequency: first tone frequency, in Hz. The frequency
            is rounded to the resolution of the generator. If this
            is not specified, the tone generator is disabled.
        * ToneAmplitude: peak tone amplitude, normalized to 31.875 ADC
            units. The amplitude is rounded to 1/8 ADC unit. Default
            is 1.0. A value of -1.0 keeps the previously set value.
        * Tone2Frequency: frequency for the second tone. Same
            as ToneFrequency.
        * Tone2Amplitude: peak tone amplitude for the second tone.
            Same as ToneAmplitude.
        * NoiseAmplitude: RMS amplitude of the pseudorandom Gaussian
            white noise, normalized to 26.03 ADC units.
        * PulseFrequency: frequency of the periodic pulse. A code
            in the range 0 to 7, corresponding to (16, 12, 8, 6, 4, 3, 2)
            times the ADC frame frequency.
        * PulseAmplitude: peak amplitude of the periodic pulse, normalized
            to 127 ADC units. Default is 1.0. A value of -1.0 keeps the
            previously set value.
        * SetTime: time at which the generator is set, for synchronization
            among different TPMs.
        * AdcChannels: list of adc channels which will be substituted with


        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/tile/01")
        >>> dict = {"ToneFrequency": 150e6, "ToneAmplitude": 0.1,
                "NoiseAmplitude": 0.9, "PulseFrequency": 7, "LoadTime":0}
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
