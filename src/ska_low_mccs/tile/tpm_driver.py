# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
An implementation of a Tile component manager that drives a real TPM.

The class is basically a wrapper around the HwTile class, in order to
have a consistent interface for driver and simulator. This is an initial
version. Some methods are still simulated. A warning is issued in this
case, or a NotImplementedError exception raised.
"""

from __future__ import annotations  # allow forward references in type hints

import time
import copy
import logging
import threading
import numpy as np
from typing import Any, Callable, cast, List, Optional

# from contextlib import contextmanager

from pyfabil.base.definitions import Device

from ska_tango_base.commands import ResultCode, BaseCommand
from ska_low_mccs.component import (
    CommunicationStatus,
    MccsComponentManager,
)
from .tpm_status import TpmStatus

from pyaavs.tile_wrapper import Tile as HwTile
from pyaavs.tile import Tile as Tile12


class TpmDriver(MccsComponentManager):
    """Hardware driver for a TPM."""

    # TODO Remove all unnecessary variables and constants after
    # all methods are completed and tested
    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5
    ADC_RMS = tuple(float(i) for i in range(32))
    FPGAS_TIME = [1, 2]
    CURRENT_TILE_BEAMFORMER_FRAME = 23
    PPS_DELAY = 12
    PHASE_TERMINAL_COUNT = 0
    FIRMWARE_NAME = "itpm_v1_6.bit"
    FIRMWARE_LIST = [
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
    ]
    REGISTER_MAP: dict[int, dict[str, dict]] = {
        0: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
        1: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
    }

    def __init__(
        self: TpmDriver,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        ip: str,
        port: int,
        tpm_version: str,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new TPM driver instance.

        Tries to connect to the given IP and port.

        :param logger: a logger for this simulator to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param ip: IP address for hardware tile
        :param port: IP address for hardware tile control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        self._hardware_lock = threading.RLock()
        self._is_programmed = False
        self._is_beamformer_running = False
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT

        self._tile_id = 0
        self._station_id = 0
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._board_temperature = self.BOARD_TEMPERATURE
        self._fpga1_temperature = self.FPGA1_TEMPERATURE
        self._fpga2_temperature = self.FPGA2_TEMPERATURE
        self._adc_rms = tuple(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._pps_delay = self.PPS_DELAY
        self._firmware_name = self.FIRMWARE_NAME
        self._firmware_list = copy.deepcopy(self.FIRMWARE_LIST)
        self._test_generator_active = False
        self._arp_table: dict[int, list[int]] = {}
        self._fpgas_time = self.FPGAS_TIME

        self._address_map: dict = {}
        self._forty_gb_core_list: list = []
        self._register_map = copy.deepcopy(self.REGISTER_MAP)
        self._ip = ip
        self._port = port
        self._tpm_status = TpmStatus.UNKNOWN
        self._tpm_version: str | None  # type hint only
        if tpm_version not in ["tpm_v1_2", "tpm_v1_6"]:
            self.logger.warning(
                "TPM version "
                + tpm_version
                + " not valid. Trying to read version from board, which must be on"
            )
            self._tpm_version = None
        else:
            self._tpm_version = tpm_version

        self.tile = cast(
            Tile12,
            HwTile(
                ip=self._ip, port=self._port, logger=logger, tpm_version=tpm_version
            ),
        )

        super().__init__(
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            component_fault_callback,
        )

    def start_communicating(self: TpmDriver) -> None:
        """Establish communication with the TPM."""
        self.logger.debug("Establish communication with the TPM")
        super().start_communicating()
        connect_to_tile_command = self.ConnectToTile(target=self)
        _ = self.enqueue(connect_to_tile_command)

    class ConnectToTile(BaseCommand):
        """Connect to Tile command class."""

        def do(  # type: ignore[override]
            self: TpmDriver.ConnectToTile,
        ) -> tuple[ResultCode, str]:
            """
            Establish communication with the tile, then start monitoring.

            This contains the actual communication logic that is enqueued to
            be run asynchronously.

            :return: a result code and message
            """
            target = self.target
            target.logger.debug("Trying to connect to tile")
            with target._hardware_lock:
                target.tile.connect()
            if target.tile.tpm is not None:
                self._tpm_status = TpmStatus.UNPROGRAMMED
                with target._hardware_lock:
                    if target.tile.is_programmed():
                        self._tpm_status = TpmStatus.PROGRAMMED
                target.logger.debug("Connected to tile")
                target.update_communication_status(CommunicationStatus.ESTABLISHED)
                return ResultCode.OK, "Connected to Tile"

            self._tpm_status = TpmStatus.UNCONNECTED
            timeout = 0
            max_time = 100  # 50 seconds
            while target.tile.tpm is None:
                time.sleep(0.5)
                with target._hardware_lock:
                    target.tile.connect()
                timeout = timeout + 1
                if timeout > max_time:
                    break
            if target.tile.tpm is not None:
                self._tpm_status = TpmStatus.UNPROGRAMMED
                with target._hardware_lock:
                    if target.tile.is_programmed():
                        self._tpm_status = TpmStatus.PROGRAMMED
                target.logger.debug("Connected to tile")
                target.update_communication_status(CommunicationStatus.ESTABLISHED)
                return ResultCode.OK, "Connected to Tile"
            else:
                target.logger.error(
                    f"Connection to tile failed after {timeout/0.5} seconds"
                )
            return (
                ResultCode.FAILED,
                f"Could not connect to Tile after {timeout/0.5} seconds",
            )

    def stop_communicating(self: TpmDriver) -> None:
        """
        Stop communicating with the TPM.

        :todo: is there a better way to do this? Should Tile16 have a
            disconnect() method that we can call here?
        """
        super().stop_communicating()
        self._tpm_status = TpmStatus.UNCONNECTED
        self.tile.tpm = None

    @property
    def tpm_status(self: TpmDriver) -> TpmStatus:
        """
        Return the TPM status.

        :return: the TPM status
        """
        return self._tpm_status

    @property
    def firmware_available(self: TpmDriver) -> list[dict[str, Any]]:
        """
        Return the list of the firmware loaded in the system.

        :return: the firmware list
        """
        self.logger.debug("TpmDriver: firmware_available")
        self._firmware_list = self.tile.get_firmware_list()
        return copy.deepcopy(self._firmware_list)

    @property
    def firmware_name(self: TpmDriver) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        """
        self.logger.debug("TpmDriver: firmware_name")
        return self._firmware_name

    @property
    def firmware_version(self: TpmDriver) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        """
        self.logger.debug("TpmDriver: firmware_version")
        firmware = self.firmware_available[0]
        return (
            "Ver."
            + str(firmware["major"])
            + "."
            + str(firmware["minor"])
            + " build "
            + str(firmware["build"])
            + ":"
            + str(firmware["time"])
        )

    @property
    def is_programmed(self: TpmDriver) -> bool:
        """
        Return whether this TPM is programmed (i.e. firmware has been downloaded to it).

        :return: whether this TPM is programmed
        """
        self._is_programmed = self.tile.is_programmed()
        self.logger.debug("TpmDriver: is_programmed " + str(self._is_programmed))
        return self._is_programmed

    def download_firmware(self: TpmDriver, bitfile: str) -> None:
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: a binary firmware blob
        """
        with self._hardware_lock:
            self.logger.debug("TpmDriver: download_firmware")
            self.tile.program_fpgas(bitfile)
        self._firmware_name = bitfile
        self._is_programmed = True
        self._tpm_status = TpmStatus.PROGRAMMED

    def cpld_flash_write(self: TpmDriver, bitfile: bytes) -> None:
        """
        Flash a program to the tile's CPLD (complex programmable logic device).

        :param bitfile: the program to be flashed

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: program_cpld")
        raise NotImplementedError

    class Initialise(BaseCommand):
        """Long running command for Tile initialisation."""

        def do(  # type: ignore[override]
            self: TpmDriver.Initialise,
        ) -> tuple[ResultCode, str]:
            """
            Download firmware, if not already downloaded, and initializes tile.

            :return: a result code and message
            """
            target = self.target
            #
            # If not programmed, program it.
            # TODO: there is no way to check whether the TPM is already correctly initialised.
            # If it is, re-initialising it is bad.
            #
            target.logger.debug("TpmDriver: initialise")
            with target._hardware_lock:
                if target.tile.is_programmed() is False:
                    target.tile.program_fpgas(target._firmware_name)
            #
            # Initialisation after programming the FPGA
            #
            if target.tile.is_programmed():
                target._is_programmed = True
                target._tpm_status = TpmStatus.PROGRAMMED
                #
                # Base initialisation
                #
                with target._hardware_lock:
                    target.tile.initialise()
                #
                # extra steps required to have it working
                #
                with target._hardware_lock:
                    target.initialise_beamformer(128, 8, True, True)
                with target._hardware_lock:
                    target.tile.post_synchronisation()
                target._tpm_status = TpmStatus.INITIALISED
                target.logger.debug("TpmDriver: initialisation completed")
                return (ResultCode.OK, "Initlialsation completed")
            else:
                target._tpm_status = TpmStatus.UNPROGRAMMED
                target.logger.error("TpmDriver: Cannot initialise board")
                return (ResultCode.FAILED, "Cannot initialise board")

    def initialise(self: TpmDriver) -> None:
        """Download firmware, if not already downloaded, and initializes tile."""
        initialise_command = self.Initialise(target=self)
        _ = self.enqueue(initialise_command)

    @property
    def tile_id(self: TpmDriver) -> int:
        """
        Get the Tile ID.

        :return: assigned tile Id value
        """
        return self._tile_id

    @tile_id.setter  # type: ignore[no-redef]
    def tile_id(self: TpmDriver, value: int) -> None:
        """
        Set Tile ID.

        :param value: assigned tile Id value
        """
        self._tile_id = value
        self.tile.set_station_id(self._station_id, self._tile_id)

    @property
    def station_id(self: TpmDriver) -> int:
        """
        Get the Station ID.

        :return: assigned station Id value
        """
        return self._station_id

    @station_id.setter  # type: ignore[no-redef]
    def station_id(self: TpmDriver, value: int) -> None:
        """
        Set Station ID.

        :param value: assigned station Id value
        """
        self._station_id = value
        self.tile.set_station_id(self._station_id, self._tile_id)

    @property
    def board_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        self.logger.debug("TpmDriver: board_temperature")
        with self._hardware_lock:
            self._board_temperature = self.tile.get_temperature()
        return self._board_temperature

    @property
    def voltage(self: TpmDriver) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        self.logger.debug("TpmDriver: voltage")
        with self._hardware_lock:
            self._voltage = self.tile.get_voltage()
        return self._voltage

    @property
    def current(self: TpmDriver) -> float:
        """
        Return the current of the TPM.

        :return: the current of the TPM
        """
        self.logger.debug("TpmDriver: current")
        # not implemented
        self._current = 1.0
        return self._current

    @property
    def fpga1_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        self.logger.debug("TpmDriver: fpga1_temperature")
        with self._hardware_lock:
            self._fpga1_temperature = self.tile.get_fpga0_temperature()
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        self.logger.debug("TpmDriver: fpga2_temperature")
        with self._hardware_lock:
            self._fpga2_temperature = self.tile.get_fpga1_temperature()
        return self._fpga2_temperature

    @property
    def adc_rms(self: TpmDriver) -> list[float]:
        """
        Return the RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        """
        self.logger.debug("TpmDriver: adc_rms")
        with self._hardware_lock:
            self._adc_rms = self.tile.get_adc_rms()
        return list(self._adc_rms)

    @property
    def fpgas_time(self: TpmDriver) -> list[int]:
        """
        Return the FPGAs clock time.

        Useful for detecting clock skew, propagation
        delays, contamination delays, etc.

        :return: the FPGAs clock time
        """
        self.logger.debug("TpmDriver: fpgas_time")
        with self._hardware_lock:
            self._fpgas_time = [
                self.tile.get_fpga_time(Device.FPGA_1),
                self.tile.get_fpga_time(Device.FPGA_2),
            ]
        return self._fpgas_time

    @property
    def pps_delay(self: TpmDriver) -> float:
        """
        Return the PPS delay of the TPM.

        :return: PPS delay
        """
        self.logger.debug("TpmDriver: get_pps_delay")
        with self._hardware_lock:
            self._pps_delay = self.tile.get_pps_delay()
        return self._pps_delay

    @property
    def register_list(self: TpmDriver) -> list[str]:
        """
        Return a list of registers available on each device.

        :return: list of registers
        """
        assert self.tile.tpm is not None  # for the type checker
        self.logger.warning("TpmDriver: register_list too big to be transmitted")
        regmap = self.tile.tpm.find_register("")
        reglist = []
        for reg in regmap:
            reglist.append(reg.name)
        return reg

    def read_register(
        self: TpmDriver, register_name: str, nb_read: int, offset: int, device: int
    ) -> list[int]:
        """
        Read the values in a named register.

        :param register_name: name of the register
        :param nb_read: number of values to read
        :param offset: offset from which to start reading
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2, other = none

        :return: values read from the register
        """
        assert self.tile.tpm is not None  # for the type checker
        if device == 1:
            devname = "fpga1."
        elif device == 2:
            devname = "fpga2."
        else:
            devname = ""
        regname = devname + register_name
        if len(self.tile.tpm.find_register(regname)) == 0:
            with self._hardware_lock:
                self.logger.error("Register '" + regname + "' not present")
            value = None
            return []
        else:
            value = cast(Any, self.tile[regname])
        if type(value) != list:
            lvalue = [value]
        else:
            lvalue = cast(List, value)
        nmin = min(len(lvalue) - 1, offset)
        nmax = min(len(lvalue), nmin + nb_read)
        return lvalue[nmin:nmax]

    def write_register(
        self: TpmDriver, register_name: str, values: list[Any], offset: int, device: int
    ) -> None:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param values: values to write
        :param offset: offset from which to start reading. Is this redundant???????
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2
        """
        if device == 1:
            devname = "fpga1."
        elif device == 2:
            devname = "fpga2."
        else:
            devname = ""
        regname = devname + register_name
        assert self.tile.tpm is not None  # for the type checker
        if len(self.tile.tpm.find_register(regname)) == 0:
            self.logger.error("Register '" + regname + "' not present")
        else:
            self.tile[regname] = values

    def read_address(self: TpmDriver, address: int, nvalues: int) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """
        values = []
        # this is inefficient
        # TODO use list write method for tile
        #
        current_address = int(address & 0xFFFFFFFC)
        for _i in range(nvalues):
            self.logger.debug(
                "Reading address "
                + str(current_address)
                + "of type "
                + str(type(current_address))
            )
            values.append(cast(int, self.tile[current_address]))
            current_address = current_address + 4
        return values

    def write_address(self: TpmDriver, address: int, values: list[int]) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """
        # this is inefficient
        # TODO use list write method for tile
        #
        current_address = int(address & 0xFFFFFFFC)
        for value in values:
            with self._hardware_lock:
                self.tile[current_address] = value
            current_address = current_address + 4

    def configure_40g_core(
        self: TpmDriver,
        core_id: int,
        arp_table_entry: int,
        src_mac: int,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
    ) -> None:
        """
        Configure the 40G code.

        :param core_id: id of the core
        :param arp_table_entry: ARP table entry to use
        :param src_mac: MAC address of the source
        :param src_ip: IP address of the source
        :param src_port: port of the source
        :param dst_ip: IP address of the destination
        :param dst_port: port of the destination
        """
        self.logger.debug("TpmDriver: configure_40g_core")
        with self._hardware_lock:
            self.tile.configure_40g_core(
                core_id, arp_table_entry, src_mac, src_ip, src_port, dst_ip, dst_port
            )

    def get_40g_configuration(
        self: TpmDriver, core_id: Optional[int] = -1, arp_table_entry: int = 0
    ) -> list[dict] | dict:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        self.logger.debug("TpmDriver: get_40g_configuration")
        self._forty_gb_core_list = []
        if core_id == -1:
            for core in range(0, 8):
                with self._hardware_lock:
                    dict_to_append = self.tile.get_40g_core_configuration(
                        core, arp_table_entry
                    )
                if dict_to_append is not None:
                    self._forty_gb_core_list.append(dict_to_append)

        else:
            with self._hardware_lock:
                self._forty_gb_core_list = self.tile.get_40g_core_configuration(
                    core_id, arp_table_entry
                )
        return self._forty_gb_core_list

    @property
    def arp_table(self: TpmDriver) -> dict[int, list[int]]:
        """
        Check that ARP table has been populated in for all used cores 40G interfaces.

        Use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer, 1 for LMC 10G
        interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: list of core id and arp table populated
        """
        self.logger.debug("TpmDriver: arp_table")
        with self._hardware_lock:
            self._arp_table = self.tile.get_arp_table()
        return self._arp_table

    def set_lmc_download(
        self: TpmDriver,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = 0xF0D0,
        dst_port: Optional[int] = 4660,
        lmc_mac: Optional[str] = None,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1g" or "10g"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        :param lmc_mac: LMC MAC address, defaults to None
        """
        self.logger.debug("TpmDriver: set_lmc_download")
        with self._hardware_lock:
            self.tile.set_lmc_download(
                mode, payload_length, dst_ip, src_port, dst_port, lmc_mac
            )

    def set_channeliser_truncation(self: TpmDriver, array: list[list[int]]) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: an N * M numpy.array, where N is the number of input
            channels, and M is the number of frequency channels.
        """
        self.logger.debug("TpmDriver: set_channeliser_truncation")
        [nb_chan, nb_freq] = np.shape(array)
        for chan in range(nb_chan):
            trunc = [0] * 512
            trunc[0:nb_freq] = array[chan]
            with self._hardware_lock:
                self.tile.set_channeliser_truncation(trunc, chan)

    def set_beamformer_regions(self: TpmDriver, regions: list[int]) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 16 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0 and 7)
            and a substation ID (not used)
        """
        self.logger.debug("TpmDriver: set_beamformer_regions")
        with self._hardware_lock:
            self.tile.set_beamformer_regions(regions)

    def initialise_beamformer(
        self: TpmDriver,
        start_channel: int,
        nof_channels: int,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Initialise the beamformer.

        :param start_channel: the start channel
        :param nof_channels: number of channels
        :param is_first: whether this is the first (?)
        :param is_last: whether this is the last (?)
        """
        self.logger.debug("TpmDriver: initialise_beamformer")
        with self._hardware_lock:
            self.tile.initialise_beamformer(
                start_channel, nof_channels, is_first, is_last
            )

    def load_calibration_coefficients(
        self: TpmDriver, antenna: int, calibration_coefficients: list[int]
    ) -> None:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        """
        self.logger.debug("TpmDriver: load_calibration_coefficients")
        with self._hardware_lock:
            self.tile.load_calibration_coefficients(calibration_coefficients)

    def load_calibration_curve(
        self: TpmDriver, antenna: int, beam: int, calibration_coefficients: list[int]
    ) -> None:
        """
        Load calibration curve.

        This is the frequency dependent response for a single
        antenna and beam, as a function of frequency. It will be combined together with
        tapering coefficients and beam angles by ComputeCalibrationCoefficients, and
        made active by SwitchCalibrationBank. The calibration coefficients do not
        include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param beam: the beam to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: load_calibration_curve")
        raise NotImplementedError

    def load_beam_angle(self: TpmDriver, angle_coefficients: list[float]) -> None:
        """
        Load the beam angle.

        :param angle_coefficients: list containing angle coefficients for each
            beam
        """
        self.logger.debug("TpmDriver: load_beam_angle")
        self.tile.load_beam_angle(angle_coefficients)

    def load_antenna_tapering(
        self: TpmDriver, beam: int, tapering_coefficients: list[float]
    ) -> None:
        """
        Loat the antenna tapering coefficients.

        :param beam: the beam to which the coefficients apply
        :param tapering_coefficients: list of tapering coefficients for each
            antenna
        """
        self.logger.debug("TpmDriver: load_antenna_tapering")
        self.tile.load_antenna_tapering(beam, tapering_coefficients)

    def switch_calibration_bank(
        self: TpmDriver, switch_time: Optional[int] = 0
    ) -> None:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        """
        self.logger.debug("TpmDriver: switch_calibration_bank")
        with self._hardware_lock:
            self.tile.switch_calibration_bank(switch_time=0)

    def compute_calibration_coefficients(self: TpmDriver) -> None:
        """
        Compute the calibration coefficients.

        Calculate from previously specified gain curves, tapering
        weights and beam angles, load them in the hardware. It must be
        followed by switch_calibration_bank() to make these active.
        """
        self.logger.debug("TpmDriver: compute_calibration_coefficients")
        with self._hardware_lock:
            self.tile.compute_calibration_coefficients()

    def set_pointing_delay(
        self: TpmDriver, delay_array: list[float], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :param beam_index: the beam to which the pointing delay should
            be applied

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_pointing_delay")
        raise NotImplementedError

    def load_pointing_delay(self: TpmDriver, load_time: int) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        """
        self.logger.debug("TpmDriver: load_pointing_delay")
        with self._hardware_lock:
            self.tile.load_pointing_delay(load_time)

    def start_beamformer(
        self: TpmDriver, start_time: int = 0, duration: int = -1
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        """
        self.logger.debug("TpmDriver: Start beamformer")
        with self._hardware_lock:
            if self.tile.start_beamformer(start_time, duration):
                self._is_beamformer_running = True

    def stop_beamformer(self: TpmDriver) -> None:
        """Stop the beamformer."""
        self.logger.debug("TpmDriver: Stop beamformer")
        with self._hardware_lock:
            self.tile.stop_beamformer()
        self._is_beamformer_running = False

    def configure_integrated_channel_data(
        self: TpmDriver,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
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
        self.logger.debug("TpmDriver: configure_integrated_channel_data")
        with self._hardware_lock:
            self.tile.configure_integrated_channel_data(
                integration_time,
                first_channel,
                last_channel,
            )

    def configure_integrated_beam_data(
        self: TpmDriver,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
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
        self.logger.debug("TpmDriver: configure_integrated_beam_data")
        with self._hardware_lock:
            self.tile.configure_integrated_beam_data(
                integration_time,
                first_channel,
                last_channel,
            )

    def stop_integrated_data(self: TpmDriver) -> None:
        """Stop the integrated data."""
        self.logger.debug("TpmDriver: Stop integrated data")
        with self._hardware_lock:
            self.tile.stop_integrated_data()

    def send_raw_data(
        self: TpmDriver,
        sync: bool = False,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :param timestamp: when to start, defaults to now
        :param seconds: delay with respect to timestamp, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_raw_data")
        with self._hardware_lock:
            self.tile.send_raw_data(sync=sync, timestamp=timestamp, seconds=seconds)

    def send_channelised_data(
        self: TpmDriver,
        number_of_samples: int = 1024,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot of channelized data totalling number_of_samples spectra.

        :param number_of_samples: number of spectra to send, defaults to 1024
        :param first_channel: first channel to send, defaults to 0
        :param last_channel: last channel to send, defaults to 511
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data")
        with self._hardware_lock:
            self.tile.send_channelised_data(
                number_of_samples=number_of_samples,
                first_channel=first_channel,
                last_channel=last_channel,
                timestamp=timestamp,
                seconds=seconds,
            )

    def send_channelised_data_continuous(
        self: TpmDriver,
        channel_id: int,
        number_of_samples: int = 1024,
        wait_seconds: int = 0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit data from a channel continuously.

        It can be stopped with stop_data_transmission.

        :param channel_id: index of channel to send
        :param number_of_samples: number of spectra to send, defaults to 1024
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data_continuous")
        with self._hardware_lock:
            self.tile.send_channelised_data_continuous(
                channel_id,
                number_of_samples=number_of_samples,
                wait_seconds=wait_seconds,
                timestamp=timestamp,
                seconds=seconds,
            )

    def send_beam_data(
        self: TpmDriver, timestamp: Optional[str] = None, seconds: float = 0.2
    ) -> None:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_beam_data")
        with self._hardware_lock:
            self.tile.send_beam_data(timestamp=timestamp, seconds=seconds)

    def stop_data_transmission(self: TpmDriver) -> None:
        """Stop data transmission for send_channelised_data_continuous."""
        self.logger.debug("TpmDriver: stop_data_transmission")
        with self._hardware_lock:
            self.tile.stop_data_transmission()

    def start_acquisition(
        self: TpmDriver, start_time: Optional[int] = None, delay: int = 2
    ) -> None:
        """
        Start data acquisition.

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :param delay: delay start, defaults to 2
        """
        self.logger.debug("TpmDriver:Start acquisition")
        with self._hardware_lock:
            self.tile.start_acquisition(start_time, delay)
        self._tpm_status = TpmStatus.SYNCHRONISED

    def set_time_delays(self: TpmDriver, delays: list[int]) -> None:
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in input streams, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        """
        self.logger.debug("TpmDriver: set_time_delays")
        with self._hardware_lock:
            self.tile.set_time_delays(delays)

    def set_csp_rounding(self: TpmDriver, rounding: float) -> None:
        """
        Set output rounding for CSP.

        :param rounding: the output rounding

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_csp_rounding")
        raise NotImplementedError

    def set_lmc_integrated_download(
        self: TpmDriver,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
        lmc_mac: Optional[str] = None,
    ) -> None:
        """
        Configure link and size of control data.

        :param mode: '1g' or '10g'
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        :param lmc_mac: MAC address of destination, defaults to None
        """
        self.logger.debug("TpmDriver: set_lmc_integrated_download")
        with self._hardware_lock:
            self.tile.set_lmc_integrated_download(
                mode,
                channel_payload_length,
                beam_payload_length,
                dst_ip,
                src_port,
                dst_port,
                lmc_mac,
            )

    def send_raw_data_synchronised(
        self: TpmDriver, timestamp: Optional[str] = None, seconds: float = 0.2
    ) -> None:
        """
        Send synchronised raw data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_raw_data_synchronised")
        with self._hardware_lock:
            self.tile.send_raw_data(timestamp, seconds, sync=True)

    @property
    def current_tile_beamformer_frame(self: TpmDriver) -> int:
        """
        Return current frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        """
        self.logger.debug("TpmDriver: current_tile_beamformer_frame")
        with self._hardware_lock:
            self._current_tile_beamformer_frame = (
                self.tile.current_tile_beamformer_frame()
            )
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self) -> bool:
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        """
        self.logger.debug("TpmDriver: beamformer_is_running")
        with self._hardware_lock:
            self._is_beamformer_running = self.tile.beamformer_is_running()
        return self._is_beamformer_running

    def check_pending_data_requests(self: TpmDriver) -> bool:
        """
        Check for pending data requests.

        :return: whether there are pending send data requests
        """
        self.logger.debug("TpmDriver: check_pending_data_requests")
        with self._hardware_lock:
            request = self.tile.check_pending_data_requests()
        return request

    def send_channelised_data_narrowband(
        self: TpmDriver,
        frequency: int,
        round_bits: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Continuously send channelised data from a single channel.

        This is a special mode used for UAV campaigns.

        :param frequency: sky frequency to transmit
        :param round_bits: which bits to round
        :param number_of_samples: number of spectra to send, defaults to 128
        :param wait_seconds: wait time before sending data, defaults to 0
        :param timestamp: when to start, defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data_narrowband")
        self.tile.send_channelised_data_narrowband(
            frequency, round_bits, number_of_samples, wait_seconds, timestamp, seconds
        )

    #
    # The synchronisation routine for the current TPM requires that
    # the function below are accessible from the station (where station-level
    # synchronisation is performed), however I am not sure whether the routine
    # for the new TPMs will still required these
    #
    def tweak_transceivers(self: TpmDriver) -> None:
        """
        Tweak the transceivers.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: tweak_transceivers")
        raise NotImplementedError

    @property
    def phase_terminal_count(self: TpmDriver) -> int:
        """
        Return the phase terminal count.

        :return: the phase terminal count
        """
        self.logger.debug("TpmDriver: get_phase_terminal_count")
        self.logger.debug("TpmDriver: get_phase_terminal_count is simulated")
        return self._phase_terminal_count

    @phase_terminal_count.setter  # type: ignore[no-redef]
    def phase_terminal_count(self: TpmDriver, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.logger.debug("TpmDriver: set_phase_terminal_count")
        self.logger.debug("TpmDriver: set_phase_terminal_count is simulated")
        self._phase_terminal_count = value

    def post_synchronisation(self: TpmDriver) -> None:
        """
        Perform post tile configuration synchronization.

        TODO Private method or must be available externally?
        """
        self.logger.debug("TpmDriver: post_synchronisation")
        with self._hardware_lock:
            self.tile.post_synchronisation()

    def sync_fpgas(self: TpmDriver) -> None:
        """
        Synchronise the FPGAs.

        TODO Method appears to be mostly internal (private).
        """
        self.logger.debug("TpmDriver: sync_fpgas")
        with self._hardware_lock:
            self.tile.sync_fpgas()

    @property
    def test_generator_active(self: TpmDriver) -> bool:
        """
        Check if the test generator is active.

        :return: whether the test generator is active
        """
        return self._test_generator_active

    @test_generator_active.setter  # type: ignore[no-redef]
    def test_generator_active(self: TpmDriver, active: bool) -> None:
        """
        Set the test generator active flag.

        :param active: True if the generator has been activated
        """
        self._test_generator_active = active

    def configure_test_generator(
        self: TpmDriver,
        frequency0: float,
        amplitude0: float,
        frequency1: float,
        amplitude1: float,
        amplitude_noise: float,
        pulse_code: int,
        amplitude_pulse: float,
        load_time: int = 0,
    ) -> None:
        """
        Test generator setting.

        :param frequency0: Tone frequency in Hz of DDC 0
        :param amplitude0: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param frequency1: Tone frequency in Hz of DDC 1
        :param amplitude1: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param amplitude_noise: Amplitude of pseudorandom noise
            normalized to 26.03 ADC units, resolution 0.102 ADU
        :param pulse_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude_pulse: pulse peak amplitude, normalized
            to 127.5 ADC units, resolution 0.5 ADU
        :param load_time: Time to start the generator.
        """
        self.logger.debug(
            "Test generator: set tone 0: "
            + str(frequency0)
            + " Hz"
            + ", tone 1: "
            + str(frequency1)
            + " Hz"
        )
        # If load time not specified, is "now" + 30 ms
        with self._hardware_lock:
            if load_time == 0:
                load_time = self.tile.get_fpga_timestamp() + 108
            # Set everything at same time
            self.tile.set_test_generator_tone(0, frequency0, amplitude0, 0.0, load_time)
            self.tile.set_test_generator_tone(1, frequency1, amplitude1, 0.0, load_time)
            self.tile.set_test_generator_noise(amplitude_noise, load_time)
            self.tile.set_test_generator_pulse(pulse_code, amplitude_pulse)
            end_time = self.tile.get_fpga_timestamp()
        if end_time < load_time:
            self.logger.warning(
                "Test generator: load time="
                + str(load_time)
                + " after current time "
                + str(end_time)
            )

    def test_generator_input_select(self: TpmDriver, inputs: int = 0) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        """
        self.logger.debug("Test generator: set inputs " + hex(inputs))
        with self._hardware_lock:
            self.tile.test_generator_input_select(inputs)

    @staticmethod
    def calculate_delay(
        current_delay: float, current_tc: int, ref_lo: float, ref_hi: float
    ) -> None:
        """
        Calculate the delay.

        :param current_delay: the current delay
        :param current_tc: current phase register terminal count
        :param ref_lo: low reference
        :param ref_hi: high reference

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        raise NotImplementedError
