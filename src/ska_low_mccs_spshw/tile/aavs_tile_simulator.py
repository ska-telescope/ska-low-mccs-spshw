# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
An implementation of a aavs Tile simulator.

#TODO:
 - Fill in this skeleton code.
 - TypeHint file
"""
from __future__ import annotations  # allow forward references in type hints

import copy
import logging
import re
from typing import Any, List, Optional, Union

from pyfabil.base.definitions import Device, LibraryError

from .dynamic_values_generator import _DynamicValuesGenerator, _DynamicValuesUpdater

__all__ = ["AavsDynamicTileSimulator", "AavsTileSimulator"]


class StationBeamformer:
    """Station beamformer."""

    def __init__(self: StationBeamformer):
        """Initialise the station beamformer object."""
        self._channel_table = [[0, 0, 0, 0, 0, 0]] * 48
        self._nof_channels = 0
        self._is_running = False
        self._start_frame = 0
        self._last_frame = 0

    def define_channel_table(self: StationBeamformer, table: list[list[int]]) -> None:
        """
        Define station beamformer table.

        :param table: table
        """
        # TODO
        return

    def get_channel_table(self: StationBeamformer) -> list[list[int]]:
        """
        Get channel table.

        :return: channel table
        """
        nof_blocks = self._nof_channels // 8
        # TODO
        return copy.deepcopy(self._channel_table[0:nof_blocks])

    def start(
        self: StationBeamformer,
    ) -> None:
        """Start."""
        # TODO
        pass

    def stop(self: StationBeamformer) -> None:
        """stop."""
        # TODO
        pass

    def is_running(self: StationBeamformer) -> bool:
        """:return: is running."""
        return self._is_running


class MockTpm:
    """Simulator for a pyfabil::Tpm class."""

    # Register map.
    # Requires only registers which are directly accessed from
    # the TpmDriver.
    _register_map: dict[Union[int, str], Any] = {
        "0x30000000": [0x21033009],
        "fpga1.dsp_regfile.stream_status.channelizer_vld": 0,
        "fpga2.dsp_regfile.stream_status.channelizer_vld": 0,
        "fpga1.test_generator.delay_0": 0,
        "fpga1.test_generator.delay_1": 0,
        "fpga1.test_generator.delay_2": 0,
        "fpga1.test_generator.delay_3": 0,
        "fpga1.test_generator.delay_4": 0,
        "fpga1.test_generator.delay_5": 0,
        "fpga1.test_generator.delay_6": 0,
        "fpga1.test_generator.delay_7": 0,
        "fpga1.test_generator.delay_8": 0,
        "fpga1.test_generator.delay_9": 0,
        "fpga1.test_generator.delay_10": 0,
        "fpga1.test_generator.delay_11": 0,
        "fpga1.test_generator.delay_12": 0,
        "fpga1.test_generator.delay_13": 0,
        "fpga1.test_generator.delay_14": 0,
        "fpga1.test_generator.delay_15": 0,
        "fpga2.test_generator.delay_0": 0,
        "fpga2.test_generator.delay_1": 0,
        "fpga2.test_generator.delay_2": 0,
        "fpga2.test_generator.delay_3": 0,
        "fpga2.test_generator.delay_4": 0,
        "fpga2.test_generator.delay_5": 0,
        "fpga2.test_generator.delay_6": 0,
        "fpga2.test_generator.delay_7": 0,
        "fpga2.test_generator.delay_8": 0,
        "fpga2.test_generator.delay_9": 0,
        "fpga2.test_generator.delay_10": 0,
        "fpga2.test_generator.delay_11": 0,
        "fpga2.test_generator.delay_12": 0,
        "fpga2.test_generator.delay_13": 0,
        "fpga2.test_generator.delay_14": 0,
        "fpga2.test_generator.delay_15": 0,
        "fpga1.pps_manager.pps_detected": 1,
        "fpga2.pps_manager.pps_detected": 1,
        "fpga1.pps_manager.sync_time_val": 0,
    }

    def __init__(self) -> None:
        """Initialise the MockTPM."""
        self._is_programmed = False
        self.beam1 = StationBeamformer()
        self.beam2 = StationBeamformer()
        self.preadu = [PreAdu()] * 32
        self._station_beamf = [self.beam1, self.beam2]

    def find_register(self: MockTpm, address: str) -> List[Any]:
        """
        Find a item in a dictionary.

        This is mocking the reading of a register for the purpose of
        testing TPM_driver

        :param address: address of start of read

        :return: registers found at address.
        """
        matches = []
        for k in self._register_map.keys():
            if isinstance(k, int):
                pass
            elif re.search(str(address), k) is not None:
                matches.append(k)
        return matches

    @property
    def station_beamf(self: MockTpm) -> List[StationBeamformer]:
        """
        Station beamf.

        :return: the station_beamf.
        """
        return self._station_beamf

    @property
    def tpm_preadu(self: MockTpm) -> List[PreAdu]:
        """
        Tpm pre adu.

        :return: the preadu.
        """
        return self.preadu

    def write_register(
        self: MockTpm,
        register: int | str,
        values: int,
        offset: int = 0,
        retry: bool = True,
    ) -> None:
        """
        Set register value.

        :param register: Register name
        :param values: Values to write
        :param offset: Memory address offset to write to
        :param retry: retry

        :raises LibraryError:Attempting to set a register not in the memory address.
        """
        if isinstance(register, int):
            register = hex(register)
        if register == "" or register == "unknown":
            raise LibraryError(f"Unknown register: {register}")
        self._register_map[register] = values

    def read_register(self: MockTpm, address: int | str, n: int = 1) -> Optional[Any]:
        """
        Get register value.

        :param address: Memory address to read from
        :param n: Number of words to read

        :return: Values
        """
        if address == ("pll", 0x508):
            return 0xE7
        if type(address) == int:
            address = hex(address)
        return self._register_map.get(address)

    def read_address(self: MockTpm, address: int | str, n: int = 1) -> Optional[Any]:
        """
        Get address value.

        :param address: Memory address to read from
        :param n: Number of words to read

        :return: Values
        """
        if address == ("pll", 0x508):
            return 0xE7
        if type(address) == int:
            address = hex(address)
        return self._register_map.get(address)

    def write_address(
        self: MockTpm, address: int | str, values: int, retry: bool = True
    ) -> None:
        """
        Write address value.

        :param address: Memory address to read from
        :param values: value to write
        :param retry: retry

        :raises LibraryError:Attempting to set a register not in the memory address.
        """
        if isinstance(address, int):
            address = hex(address)
        if address == "" or address == "unknown":
            raise LibraryError(f"Unknown register: {address}")
        self._register_map[address] = values

    def __getitem__(self: MockTpm, key: int | str) -> Optional[Any]:
        """
        Check if the specified key is a memory address or register name.

        :param key: the key to a register.

        :raises LibraryError:Attempting to set a register not in the memory address.
        :return: the value at the mocked register
        """
        if isinstance(key, int):
            key = hex(key)
        if key == "" or key == "unknown":
            raise LibraryError(f"Unknown register: {key}")
        return self._register_map.get(key)

    def __setitem__(self: MockTpm, key: int | str, value: Any) -> None:
        """
        Check if the specified key is a memory address or register name.

        :param key: the key to a register.
        :param value: the value to write in register.

        :raises LibraryError:Attempting to set a register not in the memory address.
        """
        if isinstance(key, int):
            key = hex(key)
        if key == "" or key == "unknown":
            raise LibraryError(f"Unknown register: {key}")
        self._register_map[key] = value


class PreAdu:
    """Mock preadu plugin."""

    def __init__(self: PreAdu) -> None:
        """Initialise mock plugin."""
        self.channel_filters: list[int] = [0] * 16

    def set_attenuation(self: PreAdu, attenuation: int, channel: int) -> None:
        """
        Set preadu channel attenuation.

        :param attenuation: the attenuation.
        :param channel: the channel.
        """
        self.channel_filters[channel] = (attenuation & 0x1F) << 3

    def select_low_passband(self: PreAdu) -> None:
        """Select low pass band."""
        self.bandpass = "low"

    def read_configuration(self: PreAdu) -> None:
        """
        Read configuration.

        :return: none
        """
        return


class AavsTileSimulator:
    """
    This attempts to simulate pyaavs Tile.

    This is used for testing the tpm_driver, it implements __getitem__,
    __setitem__ so that the TileSimulator can interface with the
    TPMSimulator in the same way as the AAVS Tile interfaces with the
    pyfabil TPM. Instead of writing to a register we write to a
    dictionary. It overwrite read_address, write_address, read_register,
    write_register for simplicity.
    """

    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5
    ADC_RMS = [float(i) for i in range(32)]
    FPGAS_TIME = [1, 2]
    CURRENT_TILE_BEAMFORMER_FRAME = 0
    PPS_DELAY = 12
    PHASE_TERMINAL_COUNT = 0
    FIRMWARE_NAME = "itpm_v1_6.bit"
    FIRMWARE_LIST = [
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
    ]

    STATION_ID = 0
    TILE_ID = 1
    # VOLTAGE = 5.0
    # CURRENT = 0.4
    # BOARD_TEMPERATURE = 36.0
    # FPGA1_TEMPERATURE = 38.0
    # FPGA2_TEMPERATURE = 37.5
    # # this is just mocked with some dummy information.
    # FIRMWARE_LIST = [
    #     {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
    #     {"design": "tpm_test1", "major": 2, "minor": 1, "build": 1, "time": "4"},
    # ]

    def __init__(
        self: AavsTileSimulator,
        logger: logging.Logger,
        # ip="10.0.10.2",
        # port=10000,
        # lmc_ip="10.0.10.1",
        # lmc_port=4660,
        # sampling_rate=800e6,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self.logger: logging.Logger = logger
        self._forty_gb_core_list: list[Any] = []
        self.tpm: Optional[MockTpm] = None
        self._is_programmed: bool = False
        self._pending_data_request = False
        self._is_first = False
        self._is_last = False
        self._tile_id = self.TILE_ID
        self._voltage: Optional[float] = self.VOLTAGE
        self._current: Optional[float] = self.CURRENT
        self._board_temperature: Optional[float] = self.BOARD_TEMPERATURE
        self._fpga1_temperature: Optional[float] = self.FPGA1_TEMPERATURE
        self._fpga2_temperature: Optional[float] = self.FPGA2_TEMPERATURE
        self.fortygb_core_list: list[dict[str, Any]] = [
            {},
        ]
        self._station_id = self.STATION_ID
        self._timestamp = 0
        self._pps_delay = self.PPS_DELAY
        self.delay_array = 0
        self.beam_index = 0
        # return self._register_map.get(str(address), 0)

    # def find_register(self, address: int) -> List[Any]:
    #     """
    #     Find a item in a dictionary.

    #     This is mocking the reading of a register for the purpose of
    #     testing TPM_driver

    #     :param address: address of start of read

    #     :return: registers found at address
    #     """
    #     matches = []
    #     for k, v in self._register_map.items():
    #         if type(k) == int:
    #             pass
    #         elif re.search(str(address), k) is not None:
    #             matches.append(v)
    #     return matches

    def get_firmware_list(self: AavsTileSimulator) -> List[dict[str, Any]]:
        """:return: firmware list."""
        return self.FIRMWARE_LIST

    def get_fpga0_temperature(self: AavsTileSimulator) -> Optional[float]:
        """:return: the mocked fpga0 temperature."""
        return self._fpga1_temperature

    def get_fpga1_temperature(self: AavsTileSimulator) -> Optional[float]:
        """:return: the mocked fpga1 temperature."""
        return self._fpga2_temperature

    def get_temperature(self: AavsTileSimulator) -> Optional[float]:
        """:return: the mocked board temperature."""
        return self._board_temperature

    def get_voltage(self: AavsTileSimulator) -> Optional[float]:
        """:return: the mocked voltage."""
        return self._voltage

    def get_tile_id(self: AavsTileSimulator) -> int:
        """:return: the mocked tile_id."""
        # this is set in the initialise
        return self._tile_id

    def get_adc_rms(self: AavsTileSimulator) -> list[float]:
        """:return: the mock ADC rms values."""
        return self.ADC_RMS

    def check_pending_data_requests(self: AavsTileSimulator) -> bool:
        """:return: the pending data requess flag."""
        return False
        # return self._pending_data_requests

    def initialise_beamformer(
        self: AavsTileSimulator, start_channel: float, nof_channels: int
    ) -> None:
        """
        Mock set the beamformer parameters.

        :param start_channel: start_channel
        :param nof_channels: nof_channels
        """
        # self.attributes.update({"start_channel": start_channel})
        # self.attributes.update({"nof_channels": nof_channels})
        pass

    def program_fpgas(self: AavsTileSimulator, firmware_name: str) -> None:
        """
        Mock programmed state to True.

        :param firmware_name: firmware_name
        """
        self.tpm._is_programmed = True  # type: ignore

    def erase_fpga(self: AavsTileSimulator) -> None:
        """
        Erase the fpga firmware.

        :return: none.
        """
        return

    def initialise(
        self: AavsTileSimulator,
        station_id: int = 0,
        pps_delay: int = 0,
        tile_id: int = 0,
        is_first_tile: bool = False,
        is_last_tile: bool = False,
    ) -> bool:
        """
        Initialise tile.

        :param station_id: station id
        :param tile_id: tile id
        :param pps_delay: pps_delay
        :param is_first_tile: is the first tile in chain
        :param is_last_tile: is the lase tile in chain

        :return: none.
        """
        # synchronise the time of both FPGAs UTC time
        # define if the tile is the first or last in the station_beamformer
        # for station_beamf in self.tpm._station_beamf:
        # station_beamf.set_first_last_tile(is_first_tile, is_last_tile)

        self._is_first = is_first_tile
        self._is_last = is_last_tile

        self._tile_id = tile_id
        self._station_id = station_id
        return True

    def get_fpga_time(self: AavsTileSimulator, device: Device = Device.FPGA_1) -> int:
        """
        :param device: device.

        :return: the fpga_time.
        """
        return self.FPGAS_TIME[device.value - 1]

    def set_station_id(self: AavsTileSimulator, station_id: int, tile_id: int) -> None:
        """
        Set mock registers to some value.

        :param tile_id: tile_id
        :param station_id: station_id
        """
        self._tile_id = tile_id
        self._station_id = station_id
        # fpgas = ["fpga1", "fpga2"]
        # for f in fpgas:
        #     self[f + ".dsp_regfile.config_id.station_id"] = station_id
        #     self[f + ".dsp_regfile.config_id.tpm_id"] = tile_id

        # return

    def get_pps_delay(self: AavsTileSimulator) -> float:
        """:return: the pps delay."""
        return self._pps_delay

    def is_programmed(self: AavsTileSimulator) -> Union[MockTpm, bool]:
        """
        Return whether the mock has been implemented.

        :return: the mocked programmed state
        """
        return self.tpm._is_programmed  # type: ignore

    def configure_40g_core(
        self: AavsTileSimulator,
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

    def get_40g_core_configuration(
        self: AavsTileSimulator,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict | Optional[list[dict]]:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be returned. Defaults to -1, in which case all core
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations or none
        """
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("core_id") == core_id:
                # This is just so we do not recount
                # TODO: improve this
                if arp_table_entry == 1:
                    return item
        return None

    def check_arp_table(self: AavsTileSimulator) -> None:
        """Not Implemented."""
        return
        # raise NotImplementedError

    def set_lmc_download(
        self: AavsTileSimulator,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = 0xF0D0,
        dst_port: Optional[int] = 4660,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1g" or "10g"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660

        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def reset_eth_errors(self: AavsTileSimulator) -> None:
        """Not Implemented."""
        return
        # raise NotImplementedError

    def connect(self: AavsTileSimulator) -> None:
        """Fake a connection by constructing the TPM."""
        self.tpm = MockTpm()

    def __getitem__(self: AavsTileSimulator, key: int | str) -> Any:
        """
        Get the register from the TPM.

        :param key: key
        :return: mocked item at address
        """
        return self.tpm[key]  # type: ignore

    def __setitem__(self: AavsTileSimulator, key: int | str, value: Any) -> None:
        """
        Set a registers value in the TPM.

        :param key: key
        :param value: value
        """
        self.tpm[key] = value  # type: ignore

    def set_channeliser_truncation(
        self: AavsTileSimulator, trunc: list[int], chan: int
    ) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param trunc: list with M values, one for each of the
            frequency channels. Same truncation is applied to the corresponding
            frequency channels in all inputs.
        :param chan: Input channel to set
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def set_time_delays(self: AavsTileSimulator, delays: list[float]) -> None:
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in input streams, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        """
        for i in range(16):
            self[f"fpga1.test_generator.delay_{i}"] = int(delays[i] / 1.25 + 0.5) + 128
            self[f"fpga2.test_generator.delay_{i}"] = (
                int(delays[i + 16] / 1.25 + 0.5) + 128
            )

    def current_tile_beamformer_frame(self: AavsTileSimulator) -> int:
        """:return: beamformer frame."""
        return self.get_fpga_timestamp()

    def set_csp_rounding(self: AavsTileSimulator, rounding: int) -> None:
        """
        Set the final rounding in the CSP samples, one value per beamformer channel.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def set_beamformer_regions(
        self: AavsTileSimulator, regions: list[list[int]]
    ) -> None:
        """
        Set beamformer regions.

        :param regions: regions
        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def set_first_last_tile(
        self: AavsTileSimulator, is_first: bool, is_last: bool
    ) -> None:
        """
        Set first last tile in chain.

        :param is_first: true if first
        :param is_last: true if last
        """
        registers_to_set = {
            "fpga1.beamf_ring.control.first_tile": int(is_first),
            "fpga2.beamf_ring.control.first_tile": int(is_first),
            "fpga1.beamf_ring.control.last_tile": int(is_last),
            "fpga2.beamf_ring.control.last_tile": int(is_last),
        }

        for register in registers_to_set:
            self.tpm[register] = registers_to_set[register]  # type: ignore

    def load_calibration_coefficients(
        self: AavsTileSimulator, antenna: int, coefs: list[float]
    ) -> None:
        """
        Load calibration coefficients.

        calibration_coefficients is a bi-dimensional complex array of the form
        calibration_coefficients[channel, polarization], with each element representing
        a normalized coefficient, with (1.0, 0.0) the normal, expected response for
        an ideal antenna.
        Channel is the index specifying the channels at the beamformer output,
        i.e. considering only those channels actually processed and beam assignments.
        The polarization index ranges from 0 to 3.
        0: X polarization direct element
        1: X->Y polarization cross element
        2: Y->X polarization cross element
        3: Y polarization direct element
        The calibration coefficients may include any rotation matrix (e.g.
        the parallitic angle), but do not include the geometric delay.

        :param antenna: Antenna number (0-15)
        :param coefs: Calibration coefficient array
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def switch_calibration_bank(self: AavsTileSimulator, switch_time: int = 0) -> None:
        """
        Switch calibration bank.

        :param switch_time: switch time
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    @property
    def tpm_preadu(self: AavsTileSimulator) -> List[PreAdu]:
        """
        Tpm pre adu.

        :return: the preadu
        """
        return self.tpm.preadu  # type: ignore

    def set_pointing_delay(
        self: AavsTileSimulator, delay_array: list[float], beam_index: int
    ) -> None:
        """
        Set pointing delay.

        :param delay_array: delay array
        :param beam_index: beam index
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def load_pointing_delay(self: AavsTileSimulator, load_time: int) -> None:
        """
        Load pointing delay.

        :param load_time: load time
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def start_beamformer(
        self: AavsTileSimulator, start_time: int, duration: int
    ) -> bool:
        """
        Start beamformer.

        :param start_time: start time UTC
        :param duration: duration

        :return: true if the beamformer was started successfully.
        """
        if self.beamformer_is_running():
            return False
        self.tpm.beam1._is_running = True  # type: ignore
        self.tpm.beam2._is_running = True  # type: ignore

        return True

    def stop_beamformer(self: AavsTileSimulator) -> None:
        """Stop beamformer."""
        self.tpm.beam1._is_running = False  # type: ignore
        self.tpm.beam2._is_running = False  # type: ignore

    def configure_integrated_channel_data(
        self: AavsTileSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 512,
    ) -> None:
        """
        Configure and start continuous integrated channel data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def configure_integrated_beam_data(
        self: AavsTileSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 512,
    ) -> None:
        """
        Configure and start continuous integrated beam data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def stop_integrated_data(self: AavsTileSimulator) -> None:
        """
        Stop integrated data.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def send_raw_data(
        self: AavsTileSimulator, sync: bool, timestamp: int, seconds: int
    ) -> None:
        """
        Send raw data.

        :param sync: true to sync
        :param timestamp: timestamp
        :param seconds: When to synchronise
        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def send_channelised_data(
        self: AavsTileSimulator,
        number_of_samples: int = 1024,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send channelised data from the TPM.

        :param number_of_samples: Number of spectra to send
        :param first_channel: First channel to send
        :param last_channel: Last channel to send
        :param timestamp: When to start transmission
        :param seconds: When to synchronise
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def send_channelised_data_continuous(
        self: AavsTileSimulator,
        channel_id: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Continuously send channelised data from a single channel.

        :param channel_id: Channel ID
        :param number_of_samples: Number of spectra to send
        :param wait_seconds: Wait time before sending data
        :param timestamp: When to start
        :param seconds: When to synchronise
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def send_channelised_data_narrowband(
        self: AavsTileSimulator,
        frequency: int,
        round_bits: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Continuously send channelised data from a single channel.

        :param frequency: Sky frequency to transmit
        :param round_bits: Specify which bits to round
        :param number_of_samples: Number of spectra to send
        :param wait_seconds: Wait time before sending data
        :param timestamp: When to start
        :param seconds: When to synchronise
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def send_beam_data(
        self: AavsTileSimulator,
        timeout: int = 0,
        timestamp: int = 0,
        seconds: float = 0.2,
    ) -> None:
        """
        Send beam data.

        :param timeout: timeout
        :param timestamp: timestamp
        :param seconds: When to synchronise
        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def stop_data_transmission(self: AavsTileSimulator) -> None:
        """
        Stop data transmission.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def start_acquisition(
        self: AavsTileSimulator, start_time: int, delay: float
    ) -> None:
        """
        Start data acquisition.

        :param start_time: Time for starting (frames)
        :param delay: delay after start_time (frames)
        """
        pass

    def set_lmc_integrated_download(
        self: AavsTileSimulator,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Configure link and size of control data for integrated LMC packets.

        :param mode: '1g' or '10g'
        :param channel_payload_length: SPEAD payload length for integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated beam data
        :param dst_ip: Destination IP
        :param src_port: Source port for integrated data streams
        :param dst_port: Destination port for integrated data streams
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def sync_fpgas(self: AavsTileSimulator) -> None:
        """
        Sync FPGA's.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def test_generator_set_tone(
        self: AavsTileSimulator,
        generator: int,
        frequency: float = 100e6,
        amplitude: float = 0.0,
        phase: float = 0.0,
        load_time: int = 0,
    ) -> None:
        """
        Test generator tone setting.

        :param generator: generator select. 0 or 1
        :param frequency: Tone frequency in Hz
        :param amplitude: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param phase: Initial tone phase, in turns
        :param load_time: Time to start the tone.
        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def test_generator_set_noise(
        self: AavsTileSimulator, amplitude_noise: int, load_time: int
    ) -> None:
        """
        Set generator test noise.

        :param amplitude_noise: amplitude of noise
        :param load_time: load time
        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def set_test_generator_pulse(
        self: AavsTileSimulator, pulse_code: Any, amplitude_pulse: int
    ) -> None:
        """
        Set test generator pulse.

        :param pulse_code: pulse code
        :param amplitude_pulse: amplitude pulse
        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def get_fpga_timestamp(self: AavsTileSimulator) -> int:
        """:return: timestamp."""
        return self._timestamp

    def test_generator_input_select(self: AavsTileSimulator, inputs: Any) -> None:
        """
        Test generator input select.

        :param inputs: inputs
        :return: none.
        """
        return

    # def _timed_thread(self: AavsTileSimulator) -> None:
    #     """Thread."""
    #     # should this be able to run for a infinite amount of time?
    #     while True:
    #         time_utc = time.time()
    #         self._fpgatime = int(time_utc)
    #         if self.sync_time > 0 and self.sync_time < time_utc:
    #             self._timestamp = int((time_utc - self.sync_time) / (256 * 1.08e-6))
    #             self.tpm["fpga1.dsp_regfile.stream_status.channelizer_vld"] = 1
    #             self.tpm["fpga2.dsp_regfile.stream_status.channelizer_vld"] = 1
    #         elif self._timestamp == 0:
    #             self.tpm["fpga1.pps_manager.timestamp_read_val"] = self._timestamp
    #             time.sleep(0.1)

    def get_arp_table(self: AavsTileSimulator) -> dict[str, Any]:
        """
        Get arp table.

        :return: the app table
        """
        return {"0": [0, 1], "1": [1]}

    def load_beam_angle(
        self: AavsTileSimulator, angle_coefficients: list[float]
    ) -> None:
        """
        Load beam angle.

        :param angle_coefficients: angle coefficients.
        :return: none
        """
        return

    def load_antenna_tapering(
        self: AavsTileSimulator, beam: int, tapering_coefficients: list[float]
    ) -> None:
        """
        Load antenna tapering.

        :param beam: beam
        :param tapering_coefficients: tapering coefficients
        :return: none
        """
        return

    def compute_calibration_coefficients(self: AavsTileSimulator) -> None:
        """
        Compute calibration coefficients.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def beamformer_is_running(self: AavsTileSimulator) -> bool:
        """
        Beamformer is running.

        :return: is the beam is running
        """
        return self.tpm.beam1.is_running()  # type: ignore

    def set_test_generator_tone(self: AavsTileSimulator) -> None:
        """
        Set test generator tone.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def set_test_generator_noise(self: AavsTileSimulator) -> None:
        """
        Set test generator noise.

        :raises NotImplementedError: if not overwritten.
        """
        raise NotImplementedError

    def get_phase_terminal_count(self: AavsTileSimulator) -> None:
        """
        Get PPS phase terminal count.

        :return: PPS phase terminal count
        :rtype: int
        """
        return

    def get_station_id(self: AavsTileSimulator) -> int:
        """
        Get station ID.

        :return: station ID programmed in HW
        :rtype: int
        """
        return self._station_id

    def __getattr__(self, name: str) -> object:
        """
        Get the attribute.

        :param name: name of the requested attribute
        :type name: str

        :raises AttributeError: if neither this class nor the TPM has
            the named attribute.

        :return: the requested attribute
        :rtype: object
        """
        if self.tpm:
            return getattr(self.tpm, name)
        else:
            raise AttributeError("'Tile' or 'TPM' object have no attribute " + name)


class AavsDynamicTileSimulator(AavsTileSimulator):
    """A simulator for a TPM, with dynamic value updates to certain attributes."""

    def __init__(self: AavsDynamicTileSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new Dynamic Tile simulator instance.

        :param logger: a logger for this simulator to use
        """
        self._voltage: Optional[float] = None
        self._current: Optional[float] = None
        self._board_temperature: Optional[float] = None
        self._fpga1_temperature: Optional[float] = None
        self._fpga2_temperature: Optional[float] = None

        self._updater = _DynamicValuesUpdater(1.0)
        self._updater.add_target(
            _DynamicValuesGenerator(4.55, 5.45), self._voltage_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(0.05, 2.95), self._current_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0),
            self._board_temperature_changed,
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0),
            self._fpga1_temperature_changed,
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0),
            self._fpga2_temperature_changed,
        )
        self._updater.start()

        super().__init__(logger)

    def __del__(self: AavsDynamicTileSimulator) -> None:
        """Garbage-collection hook."""
        self._updater.stop()

    def get_board_temperature(self: AavsDynamicTileSimulator) -> Optional[float]:
        """:return: the mocked board temperature."""
        return self._board_temperature

    @property
    def board_temperature(self: AavsDynamicTileSimulator) -> Optional[float]:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        assert self._board_temperature is not None  # for the type checker
        return self._board_temperature

    def _board_temperature_changed(
        self: AavsDynamicTileSimulator, board_temperature: float
    ) -> None:
        """
        Call this method when the board temperature changes.

        :param board_temperature: the new board temperature
        """
        self._board_temperature = board_temperature

    def get_voltage(self: AavsDynamicTileSimulator) -> Optional[float]:
        """:return: the mocked voltage."""
        return self._voltage

    @property
    def voltage(self: AavsDynamicTileSimulator) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        assert self._voltage is not None  # for the type checker
        return self._voltage

    def _voltage_changed(self: AavsDynamicTileSimulator, voltage: float) -> None:
        """
        Call this method when the voltage changes.

        :param voltage: the new voltage
        """
        self._voltage = voltage

    def get_current(self: AavsDynamicTileSimulator) -> Optional[float]:
        """:return: the mocked current."""
        return self._current

    @property
    def current(self: AavsDynamicTileSimulator) -> float:
        """
        Return the current of the TPM.

        :return: the current of the TPM
        """
        assert self._current is not None  # for the type checker
        return self._current

    def _current_changed(self: AavsDynamicTileSimulator, current: float) -> None:
        """
        Call this method when the current changes.

        :param current: the new current
        """
        self._current = current

    def get_fpga0_temperature(self: AavsDynamicTileSimulator) -> Optional[float]:
        """:return: the mocked fpga0 temperature."""
        return self._fpga1_temperature

    @property
    def fpga1_temperature(self: AavsDynamicTileSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        assert self._fpga1_temperature is not None  # for the type checker
        return self._fpga1_temperature

    def _fpga1_temperature_changed(
        self: AavsDynamicTileSimulator, fpga1_temperature: float
    ) -> None:
        """
        Call this method when the FPGA1 temperature changes.

        :param fpga1_temperature: the new FPGA1 temperature
        """
        self._fpga1_temperature = fpga1_temperature

    def get_fpga1_temperature(self: AavsDynamicTileSimulator) -> Optional[float]:
        """:return: the mocked fpga1 temperature."""
        return self._fpga2_temperature

    @property
    def fpga2_temperature(self: AavsDynamicTileSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        assert self._fpga2_temperature is not None  # for the type checker
        return self._fpga2_temperature

    def _fpga2_temperature_changed(
        self: AavsDynamicTileSimulator, fpga2_temperature: float
    ) -> None:
        """
        Call this method when the FPGA2 temperature changes.

        :param fpga2_temperature: the new FPGA2 temperature
        """
        self._fpga2_temperature = fpga2_temperature
