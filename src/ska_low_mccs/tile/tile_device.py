# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS Tile device."""
from __future__ import annotations  # allow forward references in type hints

import itertools
import json
import logging
import os.path
from typing import Any, List, Optional, Tuple, cast

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
        for (command_name, method_name) in [
            ("Initialise", "initialise"),
            ("DownloadFirmware", "download_firmware"),
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

    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS Tile device."""

        def do(  # type: ignore[override]
            self: MccsTile.InitCommand,
        ) -> tuple[ResultCode, str]:
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
            health = cast(HealthState, state_change.get("health_state"))
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
        station = self.component_manager.station_id
        self.logger.debug(f"stationId: read value = {station}")
        return station

    @stationId.write  # type: ignore[no-redef]
    def stationId(self: MccsTile, value: int) -> None:
        """
        Set the id of the station to which this tile is assigned.

        :param value: the station id
        """
        self.logger.debug(f"stationId: write value = {value}")
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
    def voltage(self: MccsTile) -> float:
        """
        Return the voltage.

        :return: voltage
        """
        return self.component_manager.voltage

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

        :return: Return the PPS delay
        """
        return self.component_manager.pps_delay

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

    @channeliserRounding.write
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

    @staticTimeDelays.write
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

    @cspRounding.write
    def cspRounding(self: MccsTile, rounding: list[int]) -> None:
        """
        Set CSP formatter rounding.

        :param rounding: list of up to 384 values in the range 0-7.
            Current hardware supports only a single value, thus oly 1st value is used
        """
        self.component_manager.csp_rounding = rounding

    @attribute(
        dtype=("DevLong",),
        max_dim_x=32,
    )
    def preaduLevels(self: MccsTile) -> list[int]:
        """
        Get attenuator level of preADU channels, one per input channel.

        :return: Array of one value per antenna/polarization (32 per tile)
        """
        return self.component_manager.preadu_levels

    @preaduLevels.write
    def preaduLevels(self: MccsTile, levels: list[int]) -> None:
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

        def do(  # type: ignore[override]
            self: MccsTile.GetRegisterListCommand,
        ) -> list[str]:
            """
            Implement :py:meth:`.MccsTile.GetRegisterList` command functionality.

            :return: a list of firmware & cpld registers
            """
            return self._component_manager.register_list()

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
            self: MccsTile.ReadRegisterCommand, name: str
        ) -> list[int]:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsTile.ReadRegister` command functionality.

            :param name: the register name

            :return: list of register values

            :raises ValueError: if the name is invalid
            """
            if name is None or name == "":
                self._component_manager.logger.error(
                    "register name is a mandatory parameter"
                )
                raise ValueError("register name is a mandatory parameter")
            value = self._component_manager.read_register(name)
            self.logger.debug(f"Register {name} = {value}")
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
        """Class for handling the WriteRegister(argin) command."""

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
            super().__init__(logger)

        def do(  # type: ignore[override]
            self: MccsTile.WriteRegisterCommand, argin: str
        ) -> tuple[ResultCode, str]:
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
            name = params.get("register_name", None)
            if name is None:
                self._component_manager.logger.error(
                    "register_name is a mandatory parameter"
                )
                raise ValueError("register_name is a mandatory parameter")
            values = params.get("values", None)
            if values is None:
                self._component_manager.logger.error("Values is a mandatory parameter")
                raise ValueError("values is a mandatory parameter")

            self._component_manager.write_register(name, values)
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
            self: MccsTile.ReadAddressCommand, argin: list[int]
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ReadAddress` command functionality.

            :param argin: sequence of length two, containing an address and
                a value

            :return: [values, ]

            :raises ValueError: if the argin argument has the wrong length
                or structure
            """
            if len(argin) < 1:
                self._component_manager.logger.error(
                    "At least one parameter is required"
                )
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
            self: MccsTile.WriteAddressCommand, argin: list[int]
        ) -> tuple[ResultCode, str]:
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
            component_manager: TileComponentManager,
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
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.Configure40GCore` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            """
            params = json.loads(argin)

            core_id = params.get("core_id", None)
            arp_table_entry = params.get("arp_table_entry", None)
            src_mac = params.get("source_mac", None)
            src_ip = params.get("source_ip", None)
            src_port = params.get("source_port", None)
            dst_ip = params.get("destination_ip", None)
            dst_port = params.get("destination_port", None)

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
        """Class for handling the Get40GCoreConfiguration(argin) command."""

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
            super().__init__(logger)

        def do(
            self: MccsTile.Get40GCoreConfigurationCommand, argin: str
        ) -> str:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsTile.Get40GCoreConfiguration` commands.

            :param argin: a JSON-encoded dictionary of arguments

            :return: json string with configuration

            :raises ValueError: if the argin is an invalid code id
            """
            params = json.loads(argin)
            core_id = params.get("core_id", None)
            arp_table_entry = params.get("arp_table_entry", 0)

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
        """Class for handling the SetLmcDownload(argin) command."""

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
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SetLmcDownload command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SetLmcDownloadCommand, argin: str
        ) -> tuple[ResultCode, str]:
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
            mode = params.get("mode", None)
            if mode is None:
                self._component_manager.logger.error("mode is a mandatory parameter")
                raise ValueError("mode is a mandatory parameter")
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

            self._component_manager.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetLmcDownload(self: MccsTile, argin: str) -> DevVarLongStringArrayType:
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
        >> dict = {"mode": "1g", "payload_length":4,"destination_ip"="10.0.1.23"}
        >> jstr = json.dumps(dict)
        >> dp.command_inout("SetLmcDownload", jstr)
        """
        handler = self.get_command_object("SetLmcDownload")
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
            mode = params.get("mode", None)
            if mode is None:
                self._component_manager.logger.error("mode is a mandatory parameter")
                raise ValueError("mode is a mandatory parameter")
            if mode == "40g" or mode == "40G":
                mode = "10g"
            channel_payload_length = params.get("channel_payload_lenth", 1024)
            beam_payload_length = params.get("beam_payload_length", 1024)
            dst_ip = params.get("destination_ip", None)
            src_port = params.get("source_port", 0xF0D0)
            dst_port = params.get("destination_port", 4660)

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

            * mode - (string) '1g' or '10g' (Mandatory)
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

        def do(self: MccsTile.GetArpTableCommand) -> str:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsTile.GetArpTable` commands.

            :return: a JSON-encoded dictionary of coreId and populated arpID table
            """
            return json.dumps(self._component_manager.get_arp_table())

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
        return_code, unique_id = handler()
        # TODO If this returns DEVVARLONGSTRINGARRAY where's the Arp table?????
        return ([return_code], [unique_id])

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
            self: MccsTile.SetBeamFormerRegionsCommand, argin: list[int]
        ) -> tuple[ResultCode, str]:
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
                    "Incomplete specification of region. Regions specified by 8 values"
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
        """Class for handling the ConfigureStationBeamformer(argin) command."""

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
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureStationBeamformer command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureStationBeamformerCommand, argin: str
        ) -> tuple[ResultCode, str]:
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
            start_channel = params.get("start_channel", 192)
            if start_channel < 2 or start_channel > 504:
                self.logger.error
            n_channels = params.get("n_channels", 8)
            if start_channel < 2 or (start_channel + n_channels) > 511:
                self.logger.error("Invalid specified observed region")
                raise ValueError("Invalid specified observed region")
            is_first = params.get("is_first", False)
            is_last = params.get("is_last", False)
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
        ) -> tuple[ResultCode, str]:
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
            component_manager,
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

        def do(  # type: ignore[override]
            self: MccsTile.ApplyCalibrationCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ApplyCalibration` command functionality.

            :param argin: switch time

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            switch_time = argin

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
            component_manager,
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
            self: MccsTile.LoadPointingDelaysCommand, argin: list[float]
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.LoadPointingDelays` command functionality.

            :param argin: an array containing a beam index and antenna
                delays

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.

            :raises ValueError: if the argin argument does not have the
                right length / structure
            """
            if len(argin) < self._antennas_per_tile * 2 + 1:
                self._component_manager.logger.error("Insufficient parameters")
                raise ValueError("Insufficient parameters")
            beam_index = int(argin[0])
            if beam_index < 0 or beam_index > 7:
                self._component_manager.logger.error("Invalid beam index")
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
            component_manager,
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

        def do(  # type: ignore[override]
            self: MccsTile.ApplyPointingDelaysCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ApplyPointingDelays` command functionality.

            :param argin: load time

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            load_time = argin

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
        """Class for handling the StartBeamformer(argin) command."""

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
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "StartBeamformer command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.StartBeamformerCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.StartBeamformer` command functionality.

            :param argin: a JSON-encoded dictionary of arguments
                "StartTime" and "Duration"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            start_time = params.get("start_time", None)
            duration = params.get("duration", -1)
            subarray_beam_id = params.get("subarray_beam_id", -1)
            scan_id = params.get("scan_id", 0)
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

        def do(  # type: ignore[override]
            self: MccsTile.StopBeamformerCommand,
        ) -> tuple[ResultCode, str]:
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
            component_manager: TileComponentManager,
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
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedChannelData` commands.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            integration_time = params.get("integration_time", 0.5)
            first_channel = params.get("first_channel", 0)
            last_channel = params.get("last_channel", 511)

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
        """Class for handling the ConfigureIntegratedBeamData(argin) command."""

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
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureIntegratedBeamData command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureIntegratedBeamDataCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.ConfigureIntegratedBeamData` commands.

            :param argin: a JSON-encoded dictionary of arguments
                "integration time", "first_channel", "last_channel"

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            params = json.loads(argin)
            integration_time = params.get("integration_time", 0.5)
            first_channel = params.get("first_channel", 0)
            last_channel = params.get("last_channel", 191)

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

        def do(  # type: ignore[override]
            self: MccsTile.StopIntegratedDataCommand,
        ) -> tuple[ResultCode, str]:
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

    class SendDataSamplesCommand(FastCommand):
        """Class for handling the SendDataSamples(argin) command."""

        def __init__(
            self: MccsTile.SendDataSamplesCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new SendDataSamplesCommand instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "SendDataSamples command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.SendDataSamplesCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsTile.SendDataSamples` command functionality.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :raises ValueError: if mandatory parameters are missing
            """
            params = json.loads(argin)

            # Check for mandatory parameters
            data_type = params.get("data_type", None)
            if data_type is None:
                self._component_manager.logger.error(
                    "data_type is a mandatory parameter"
                )
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
                if frequency < 1e6 or frequency > 399e6:
                    self._component_manager.logger.error(
                        "frequency must be between 1 and 390 MHz"
                    )
                    raise ValueError("frequency must be between 1 and 390 MHz")

            n_samples = None
            if data_type == "channel":
                n_samples = params.get("n_samples", 1024)
            elif data_type == "channel_continuous":
                n_samples = params.get("n_samples", 128)
            elif data_type == "narrowband":
                n_samples = params.get("n_samples", 1024)
            params["n_samples"] = n_samples
            self._component_manager.send_data_samples(**params)
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

        def do(  # type: ignore[override]
            self: MccsTile.StopDataTransmissionCommand,
        ) -> tuple[ResultCode, str]:
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

            :return: A tuple containing a return code and a string
    class ConfigureTestGeneratorCommand(FastCommand):
        """Class for handling the ConfigureTestGenerator(argin) command."""

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
            super().__init__(logger)

        SUCCEEDED_MESSAGE = "ConfigureTestGenerator command completed OK"

        def do(  # type: ignore[override]
            self: MccsTile.ConfigureTestGeneratorCommand, argin: str
        ) -> tuple[ResultCode, str]:
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
            set_time = params.get("set_time", None)
            if "tone_frequency" in params:
                frequency0 = params["tone_frequency"]
                amplitude0 = params.get("tone_amplitude", 1.0)
                active = True
            else:
                frequency0 = 0.0
                amplitude0 = 0.0

            if "tone_2_frequency" in params:
                frequency1 = params["tone_2_frequency"]
                amplitude1 = params.get("tone_2_amplitude", 1.0)
                active = True
            else:
                frequency1 = 0.0
                amplitude1 = 0.0

            if "noise_amplitude" in params:
                amplitude_noise = params.get("noise_amplitude", 1.0)
                active = True
            else:
                amplitude_noise = 0.0

            if "pulse_frequency" in params:
                pulse_code = params["pulse_frequency"]
                if (pulse_code < 0) or (pulse_code > 7):
                    raise ValueError("pulse_frequency must be between 0 and 7")
                amplitude_pulse = params.get("pulse_amplitude", 1.0)
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

            chans = params.get("adc_channels")
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
            return self.adminMode == AdminMode.MAINTENANCE  # type: ignore[attr-defined]

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
