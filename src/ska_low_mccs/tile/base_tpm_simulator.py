# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import copy
import logging
import time
from typing import Any, Optional

from ska_low_mccs_common.component import ObjectComponent
from typing_extensions import Final

from .tile_data import TileData
from .tpm_status import TpmStatus

__all__ = ["BaseTpmSimulator"]


class BaseTpmSimulator(ObjectComponent):
    """
    A simulator for a TPM.

    :todo: The current TPM driver has a wrapper to make it consistent
        with the interface of this simulator. It would be more better if
        we updated this simulator's interface to better reflect the
        natural interface of the driver that it is simulating.
    :todo: The initialiser for this class accepts a component fault
        callback, but at present there is nothing implemented to allow
        this simulator to simulate a fault state that would warrant the
        callback being called.
    """

    ADC_RMS = tuple(float(i) for i in range(32))
    FPGAS_TIME = [1, 2]
    CURRENT_TILE_BEAMFORMER_FRAME: Final = 23
    PPS_DELAY: Final = 12
    PHASE_TERMINAL_COUNT: Final = 0
    FIRMWARE_NAME: Final = "itpm_v1_6.bit"
    FIRMWARE_AVAILABLE: dict[str, dict[str, str | int]] = {
        "itpm_v1_6.bit": {"design": "model1", "major": 2, "minor": 3},
        "itpm_v1_5.bit": {"design": "model2", "major": 3, "minor": 7},
        "itpm_v1_2.bit": {"design": "model3", "major": 2, "minor": 6},
    }
    REGISTER_MAP: dict[int, dict[str, dict]] = {
        0: {
            "test-reg1": {},
            "test-reg2": {},
            "test-reg3": {},
            "test-reg4": {},
        },
        1: {
            "test-reg1": {},
            "test-reg2": {},
            "test-reg3": {},
            "test-reg4": {},
        },
    }
    # ARP resolution table
    # Values are consistent with unit test test_MccsTile
    #
    ARP_MAP = {
        "10.0.23.56": 0x10FEFA060B99,
        "10.0.98.3": 0x10FEED080B59,
        "10.0.98.4": 0x10FEED080B57,
        "10.0.99.3": 0x10FEED080A58,
        "10.0.99.4": 0x10FEED080A56,
    }
    ARP_TABLE = {0: [0, 1], 1: [1]}
    # TPM version: "tpm_v1_2" or "tpm_v1_6"
    TPM_VERSION = 120

    def _arp(self: BaseTpmSimulator, ip: str) -> str:
        """
        Return MAC address from ARP resolution table Private method for the simulator.

        :param ip: IP address in dot decimal format

        :return: MAC address in xx:xx:xx:xx:xx:xx format
        """
        if ip in self.ARP_MAP:
            mac = self.ARP_MAP[ip]
            mac_str = f"{mac:012x}"
            arp = ":".join(mac_str[i : (i + 2)] for i in range(0, 12, 2))
            return arp
        else:
            return "ff:ff:ff:ff:ff:ff"

    def __init__(self: BaseTpmSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self.logger = logger
        self._is_programmed = False
        self._tpm_status = TpmStatus.UNKNOWN
        self._is_beamformer_running = False
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT
        self._station_id = 0
        self._tile_id = 0

        self._adc_rms = tuple(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._pps_delay = self.PPS_DELAY
        self._firmware_name = self.FIRMWARE_NAME
        self._firmware_available = copy.deepcopy(self.FIRMWARE_AVAILABLE)
        self._arp_table = copy.deepcopy(self.ARP_TABLE)
        self._fpgas_time = copy.deepcopy(self.FPGAS_TIME)

        self._address_map: dict[str, int] = {}
        self._forty_gb_core_list: list[dict[str, Any]] = []
        self._register_map = copy.deepcopy(self.REGISTER_MAP)
        self._test_generator_active = False
        self._sync_time = 0

    @property
    def firmware_available(
        self: BaseTpmSimulator,
    ) -> dict[str, dict[str, Any]]:
        """
        Return the firmware list for this TPM simulator.

        :return: the firmware list
        """
        self.logger.debug("TpmSimulator: firmware_available")
        return copy.deepcopy(self._firmware_available)

    @property
    def firmware_name(self: BaseTpmSimulator) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        """
        self.logger.debug("TpmSimulator: firmware_name")
        return self._firmware_name

    @firmware_name.setter
    def firmware_name(self: BaseTpmSimulator, value: str) -> None:
        """
        Set firmware name.

        :param value: assigned default firmware name. Can be overriden by
            parameter of download_firmware
        """
        self._firmware_name = value

    @property
    def firmware_version(self: BaseTpmSimulator) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        """
        self.logger.debug("TpmSimulator: firmware_version")
        firmware = self._firmware_available[self._firmware_name]
        return "{major}.{minor}".format(**firmware)  # noqa: FS002

    @property
    def is_programmed(self: BaseTpmSimulator) -> bool:
        """
        Return whether this TPM is programmed (ie. firmware has been downloaded to it).

        :return: whether this TPM is programmed
        """
        self.logger.debug(f"TpmSimulator: is_programmed {self._is_programmed}")
        return self._is_programmed

    @property
    def hardware_version(self: BaseTpmSimulator) -> int:
        """
        Return whether this TPM is 1.2 or 1.6.

        :return: TPM hardware version. 120 or 160
        """
        return self.TPM_VERSION

    def download_firmware(self: BaseTpmSimulator, bitfile: str) -> None:
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: the bitfile to be downloaded
        """
        self.logger.debug("TpmSimulator: download_firmware")
        self._firmware_name = bitfile
        self._is_programmed = True
        self._tpm_status = TpmStatus.PROGRAMMED

    def erase_fpga(self: BaseTpmSimulator) -> None:
        """Erase the firmware form the FPGA, to reduce power."""
        self.logger.debug("TpmSimulator: erase_fpga")
        self._is_programmed = False
        self._tpm_status = TpmStatus.UNPROGRAMMED

    def cpld_flash_write(self: BaseTpmSimulator, bitfile: bytes) -> None:
        """
        Flash a program to the tile's CPLD (complex programmable logic device).

        :param bitfile: the program to be flashed

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: program_cpld")
        raise NotImplementedError

    def get_arp_table(self: BaseTpmSimulator) -> None:
        """
        Get the arp table.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: get_arp_table")
        raise NotImplementedError

    def initialise(self: BaseTpmSimulator) -> None:
        """
        Real TPM driver performs connectivity checks, programs and initialises the TPM.

        The simulator will emulate programming the firmware.
        """
        self.logger.debug("TpmSimulator: initialise")
        self.download_firmware(self._firmware_name)
        self._tpm_status = TpmStatus.INITIALISED

    @property
    def tpm_status(self: BaseTpmSimulator) -> TpmStatus:
        """
        Get the tpm status.

        :return: tpm status
        """
        return self._tpm_status

    @property
    def tile_id(self: BaseTpmSimulator) -> int:
        """
        Tile ID.

        :return: assigned tile Id value
        """
        return self._tile_id

    @tile_id.setter
    def tile_id(self: BaseTpmSimulator, value: int) -> None:
        """
        Set Tile ID.

        :param value: assigned tile Id value
        """
        self._tile_id = value

    @property
    def station_id(self: BaseTpmSimulator) -> int:
        """
        Station ID.

        :return: assigned station Id value
        """
        return self._station_id

    @station_id.setter
    def station_id(self: BaseTpmSimulator, value: int) -> None:
        """
        Set Station ID.

        :param value: assigned station Id value
        """
        self._station_id = value

    @property
    def board_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'board_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def voltage(self: BaseTpmSimulator) -> float:
        """
        Return the voltage of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'voltage' must be "
            "implemented in a subclass."
        )

    @property
    def current(self: BaseTpmSimulator) -> float:
        """
        Return the current of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'current' must be "
            "implemented in a subclass."
        )

    @property
    def fpga1_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga1_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def fpga2_temperature(self: BaseTpmSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga2_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def adc_rms(self: BaseTpmSimulator) -> tuple[float, ...]:
        """
        Return the RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        """
        self.logger.debug("TpmSimulator: adc_rms")
        return self._adc_rms

    @property
    def fpgas_time(self: BaseTpmSimulator) -> list[int]:
        """
        Return the FPGAs clock time.

        Useful for detecting clock skew, propagation delays, contamination delays, etc.

        :return: the FPGAs clock time
        """
        self.logger.debug("TpmSimulator: fpgas_time")
        # self._fpgas_time[0] = int(time.time())
        # self._fpgas_time[1] = self._fpgas_time[0]
        return self._fpgas_time

    @property
    def pps_delay(self: BaseTpmSimulator) -> float:
        """
        Return the PPS delay of the TPM.

        :return: PPS delay
        """
        self.logger.debug("TpmSimulator: get_pps_delay")
        return self._pps_delay

    @property
    def register_list(self: BaseTpmSimulator) -> list[str]:
        """
        Return a list of registers available on each device.

        :return: list of registers
        """
        return list(self._register_map[0].keys())

    def read_register(
        self: BaseTpmSimulator,
        register_name: str,
        nb_read: int,
        offset: int,
        device: int,
    ) -> list[int]:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param nb_read: number of values to read
        :param offset: offset from which to start reading
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2

        :return: values read from the register
        """
        address_map = self._register_map[device].get(register_name, None)
        values = []
        if address_map is not None:
            for i in range(nb_read):
                key = str(offset + i)
                values.append(address_map.get(key, 0))
        return values

    def write_register(
        self: BaseTpmSimulator,
        register_name: str,
        values: list[int],
        offset: int,
        device: int,
    ) -> None:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param values: values to write
        :param offset: offset from which to start reading
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2
        """
        address_map = self._register_map[device].get(register_name, None)
        if address_map is not None:
            for i, value in enumerate(values):
                key = str(offset + i)
                address_map.update({key: value})

    def read_address(
        self: BaseTpmSimulator, address: int, nvalues: int = 1
    ) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """
        values = []
        for i in range(nvalues):
            key = str(address + i)
            values.append(self._address_map.get(key, 0))
        return values

    def write_address(self: BaseTpmSimulator, address: int, values: list[int]) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """
        for i, value in enumerate(values):
            key = str(address + i)
            self._address_map.update({key: value})

    def configure_40g_core(
        self: BaseTpmSimulator,
        core_id: int,
        arp_table_entry: int,
        src_mac: str,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
    ) -> None:
        """
        Configure the 40G code.

        The dst_mac parameter is ignored in true 40G core (ARP resolution used instead)

        :param core_id: id of the core
        :param arp_table_entry: ARP table entry to use
        :param src_mac: MAC address of the source
        :param src_ip: IP address of the source
        :param src_port: port of the source
        :param dst_ip: IP address of the destination
        :param dst_port: port of the destination
        """
        core_dict = {
            "core_id": core_id,
            "arp_table_entry": arp_table_entry,
            "src_mac": src_mac,
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
        }
        self._forty_gb_core_list.append(core_dict)

    def get_40g_configuration(
        self: BaseTpmSimulator,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict | list[dict] | None:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("core_id") == core_id:
                return [item]
        return

    @property
    def arp_table(self: BaseTpmSimulator) -> dict[int, list[int]]:
        """
        Check that ARP table has been populated in for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer,
        1 for LMC. 10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for
        beamforming, and 2, 6 for LMC with only one ARP.

        :return: dictionary containing coreID and populated arpID
        """
        self.logger.debug("TpmSimulator: arp_table")
        return copy.deepcopy(self._arp_table)

    @property
    def fpga_sync_time(self: BaseTpmSimulator) -> int:
        """
        Return reference time for timestamp.

        :return: reference time
        """
        return self._sync_time

    @property
    def fpga_current_frame(self: BaseTpmSimulator) -> int:
        """
        Return current frame from timestamp.

        :return: current frame
        """
        if self._sync_time == 0:
            return 0
        else:
            return int((time.time() - self._sync_time) / (TileData.FRAME_PERIOD))

    def set_lmc_download(
        self: BaseTpmSimulator,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1g" or "10g"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_lmc_download")
        raise NotImplementedError

    def set_channeliser_truncation(self: BaseTpmSimulator, array: list[int]) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: an N * M array, where N is the number of input
            channels, and M is the number of frequency channels. This is
            encoded as a list comprising N, then M, then the flattened
            array

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_channeliser_truncation")
        raise NotImplementedError

    def set_beamformer_regions(self: BaseTpmSimulator, regions: list[int]) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 48 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), a beam index (between 0 and 7)
            and a substation ID.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_beamformer_regions")
        raise NotImplementedError

    def initialise_beamformer(
        self: BaseTpmSimulator,
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

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: initialise_beamformer")
        raise NotImplementedError

    def load_calibration_coefficients(
        self: BaseTpmSimulator,
        antenna: int,
        calibration_coefficients: list[int],
    ) -> None:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_calibration_coefficients")
        raise NotImplementedError

    def load_calibration_curve(
        self: BaseTpmSimulator,
        antenna: int,
        beam: int,
        calibration_coefficients: list[int],
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
        self.logger.debug("TpmSimulator: load_calibration_curve")
        raise NotImplementedError

    def load_beam_angle(
        self: BaseTpmSimulator, angle_coefficients: list[float]
    ) -> None:
        """
        Load the beam angle.

        :param angle_coefficients: list containing angle coefficients for each
            beam

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_beam_angle")
        raise NotImplementedError

    def load_antenna_tapering(
        self: BaseTpmSimulator, beam: int, tapering_coefficients: list[float]
    ) -> None:
        """
        Loat the antenna tapering coefficients.

        :param beam: the beam to which the coefficients apply
        :param tapering_coefficients: list of tapering coefficients for each
            antenna

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_antenna_tapering")
        raise NotImplementedError

    def switch_calibration_bank(self: BaseTpmSimulator, switch_time: int = 0) -> None:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: switch_calibration_bank")
        raise NotImplementedError

    def compute_calibration_coefficients(self: BaseTpmSimulator) -> None:
        """
        Compute the calibration coefficients.

        Calculate from previously specified gain curves, tapering weights
        and beam angles, load them in the hardware. It must be followed
        by switch_calibration_bank() to make these active.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: compute_calibration_coefficients")
        raise NotImplementedError

    def set_pointing_delay(
        self: BaseTpmSimulator, delay_array: list[float], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :param beam_index: the beam to which the pointing delay should
            be applied

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_pointing_delay")
        raise NotImplementedError

    def load_pointing_delay(self: BaseTpmSimulator, load_time: int) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_pointing_delay")
        raise NotImplementedError

    def start_beamformer(
        self: BaseTpmSimulator,
        start_time: int = 0,
        duration: int = -1,
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        """
        self.logger.debug("TpmSimulator: Start beamformer")
        self._is_beamformer_running = True

    def stop_beamformer(self: BaseTpmSimulator) -> None:
        """Stop the beamformer."""
        self.logger.debug("TpmSimulator: Stop beamformer")
        self._is_beamformer_running = False

    def configure_integrated_channel_data(
        self: BaseTpmSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Configure the integrated channel data with the provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_channel_data")
        raise NotImplementedError

    def configure_integrated_beam_data(
        self: BaseTpmSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
    ) -> None:
        """
        Configure the integrated beam data with the provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_beam_data")
        raise NotImplementedError

    def stop_integrated_data(self: BaseTpmSimulator) -> None:
        """
        Stop the integrated data.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: Stop integrated data")
        raise NotImplementedError

    def send_raw_data(
        self: BaseTpmSimulator,
        sync: bool = False,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_raw_data")
        raise NotImplementedError

    def send_channelised_data(
        self: BaseTpmSimulator,
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

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data")
        raise NotImplementedError

    def send_channelised_data_continuous(
        self: BaseTpmSimulator,
        channel_id: int,
        number_of_samples: int = 128,
        wait_seconds: float = 0.0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit data from a channel continuously.

        :param channel_id: index of channel to send
        :param number_of_samples: number of spectra to send, defaults to 1024
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data_continuous")
        raise NotImplementedError

    def send_beam_data(
        self: BaseTpmSimulator,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_beam_data")
        raise NotImplementedError

    def stop_data_transmission(self: BaseTpmSimulator) -> None:
        """
        Stop data transmission.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: stop_data_transmission")
        raise NotImplementedError

    def start_acquisition(
        self: BaseTpmSimulator,
        start_time: Optional[int] = None,
        delay: Optional[int] = 2,
    ) -> None:
        """
        Start data acquisition.

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :param delay: delay start, defaults to 2
        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator:Start acquisition")
        self._tpm_status = TpmStatus.SYNCHRONISED
        self._sync_time = int(time.time())
        raise NotImplementedError

    def set_time_delays(self: BaseTpmSimulator, delay: int) -> None:
        """
        Set coarse zenith delay for input ADC streams.

        :param delay: the delay in samples, specified in nanoseconds.
            A positive delay adds delay to the signal stream

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_time_delays")
        raise NotImplementedError

    def set_csp_rounding(self: BaseTpmSimulator, rounding: float) -> None:
        """
        Set output rounding for CSP.

        :param rounding: the output rounding

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_csp_rounding")
        raise NotImplementedError

    def set_lmc_integrated_download(
        self: BaseTpmSimulator,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
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

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_lmc_integrated_download")
        raise NotImplementedError

    def send_raw_data_synchronised(
        self: BaseTpmSimulator,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send synchronised raw data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_raw_data_synchronised")
        raise NotImplementedError

    @property
    def current_tile_beamformer_frame(self: BaseTpmSimulator) -> int:
        """
        Return current frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        """
        self.logger.debug("TpmSimulator: current_tile_beamformer_frame")
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self: BaseTpmSimulator) -> bool:
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        """
        self.logger.debug("TpmSimulator: beamformer_is_running")
        return self._is_beamformer_running

    def check_pending_data_requests(self: BaseTpmSimulator) -> None:
        """
        Check for pending data requests.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: check_pending_data_requests")
        raise NotImplementedError

    def send_channelised_data_narrowband(
        self: BaseTpmSimulator,
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

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data_narrowband")
        raise NotImplementedError

    #
    # The synchronisation routine for the current TPM requires that
    # the function below are accessible from the station (where station-level
    # synchronisation is performed), however I am not sure whether the routine
    # for the new TPMs will still required these
    #
    def tweak_transceivers(self: BaseTpmSimulator) -> None:
        """
        Tweak the transceivers.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: tweak_transceivers")
        raise NotImplementedError

    @property
    def phase_terminal_count(self: BaseTpmSimulator) -> int:
        """
        Return the phase terminal count.

        :return: the phase terminal count
        """
        self.logger.debug("TpmSimulator: get_phase_terminal_count")
        return self._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self: BaseTpmSimulator, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.logger.debug("TpmSimulator: set_phase_terminal_count")
        self._phase_terminal_count = value

    def post_synchronisation(self) -> None:
        """
        Perform post tile configuration synchronization.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: post_synchronisation")
        raise NotImplementedError

    def sync_fpgas(self) -> None:
        """
        Synchronise the FPGAs.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: sync_fpgas")
        raise NotImplementedError

    def configure_test_generator(
        self: BaseTpmSimulator,
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
        Test generator configuration.

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
        :param load_time: Time to start the tone.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        amplitude_adu = round(amplitude0 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: set_test_generator tone(0):"
            + str(frequency0)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude1 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: test_generator set_tone(1):"
            + str(frequency1)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude_noise * 255) * 0.102
        self.logger.debug(
            "TpmSimulator: set_test_generator noise: "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        freqs = [16, 12, 8, 6, 4, 3, 2, 1]
        frequency = 0.925925 * freqs[pulse_code]
        amplitude_adu = round(amplitude_pulse * 255) * 0.25
        self.logger.debug(
            "TpmSimulator: set_test_generator pulse: "
            + str(frequency)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs"
        )
        raise NotImplementedError

    def test_generator_input_select(self: BaseTpmSimulator, bit_mask: int) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param bit_mask: Bit mask of inputs using test signal
        """
        self.logger.debug(
            "TpmSimulator: test_generator_input_select: " + str(hex(bit_mask))
        )
        # raise NotImplementedError

    @property
    def test_generator_active(self) -> bool:
        """
        Check if the test generator is active.

        :return: whether the test generator is active
        """
        return self._test_generator_active

    @test_generator_active.setter
    def test_generator_active(self: BaseTpmSimulator, active: bool) -> None:
        """
        Set the test generator active flag.

        :param active: True if the generator has been activated
        """
        self._test_generator_active = active

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
