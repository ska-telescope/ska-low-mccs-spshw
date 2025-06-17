# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a Tile simulator."""

from __future__ import annotations  # allow forward references in type hints

import copy
import functools
import json
import logging
import random
import re
import threading
import time
from ipaddress import IPv4Address
from typing import Any, Callable, Final, Generator, List, Optional, TypeVar, cast

import numpy as np
from ska_low_sps_tpm_api.base.definitions import (
    BoardError,
    Device,
    LibraryError,
    RegisterInfo,
)

from .dynamic_value_generator import DynamicValuesGenerator, DynamicValuesUpdater
from .spead_data_simulator import SpeadDataSimulator
from .tile_data import TileData

__all__ = [
    "DynamicTileSimulator",
    "TileSimulator",
    "MockTpm",
    "PreAdu",
    "StationBeamformer",
]

Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


def connected(func: Wrapped) -> Wrapped:
    """
    Return a function that checks if the TileSimulator is connectable.

    The TileSimulator needs to be mocked on to allow a connection.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @connected
        def set_pps_delay(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        self: TileSimulator,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check the TPM is connected.

        :param self: the method called
        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :return: whatever the wrapped method returns

        :raises LibraryError: if the TPM is not connected
        """
        if self.mock_connection_success is False or self.tpm is None:
            self.logger.warning(
                "Cannot call function " + func.__name__ + " on unconnected TPM"
            )
            raise LibraryError(
                "Cannot call function " + func.__name__ + " on unconnected TPM"
            )
        else:
            return func(self, *args, **kwargs)

    return cast(Wrapped, _wrapper)


def check_mocked_overheating(func: Wrapped) -> Wrapped:
    """
    Return a function that checks if the TileSimulator is mocked overheating.

    The TileSimulator needs to be realistic with the behaviour of the system.
    The TPM can overheat, in this situation the FPGAs turn off, but the CPLD is
    connectable still. This decorator is to be placed on methods that cannot be called
    in the case of overheating.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @check_mocked_overheating
        def set_pps_delay(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        self: TileSimulator,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check if the TPM is overheating.

        :param self: the method called
        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :return: whatever the wrapped method returns

        :raises BoardError: if the TPM is mocked overheating.
        """
        if self.tpm_mocked_overheating:
            self.logger.warning(
                "BoardError: Not possible to communicate with the FPG0: "
                "Failed to read_address 0x4 on board: UCP::read. "
                "Command failed on board. "
                "Requested address 0x4 received address 0xfffffffb"
            )
            raise BoardError(
                "BoardError: Not possible to communicate with the FPG0: "
                "Failed to read_address 0x4 on board: UCP::read. "
                "Command failed on board. "
                "Requested address 0x4 received address 0xfffffffb"
            )
        else:
            return func(self, *args, **kwargs)

    return cast(Wrapped, _wrapper)


def antenna_buffer_implemented(func: Wrapped) -> Wrapped:
    """
    Return a function that checks if Antenna buffer is implmented.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @antenna_buffer_implemented
        def set_up_antenna_buffer(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    def _wrapper(
        self: TileSimulator,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Mock checks if the antenna buffer is implemented in the firmware.

        :param self: the method called
        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :raises LibraryError: when Antenna Buffer is not implemented

        :return: whatever the wrapped method returns
        """
        if not self._antenna_buffer_implemented:
            raise LibraryError("Antenna Buffer not implemented by FPGA firmware")
        return func(self, *args, **kwargs)

    return cast(Wrapped, _wrapper)


class StationBeamformer:
    """Station beamformer."""

    def __init__(self: StationBeamformer):
        """Initialise the station beamformer object."""
        self._channel_table = [[0, 0, 0, 0, 0, 0, 0]] * 48
        self._nof_channels = 0
        self._is_running = False
        self._start_frame = 0
        self._last_frame = 0

    def define_channel_table(self: StationBeamformer, table: list[list[int]]) -> None:
        """
        Define station beamformer table.

        Defines the station beamformer table. Each entry in the list contains:
        - start channel
        - number of channels
        - hw beam ID
        - subarray ID
        - subarray_logical_channel
        - subarray_beam_id
        - substation_id
        - aperture_id

        :param table: table of channel blocks. Entries of 8 items each:
        :raises ValueError: if wrong value passed.
        """
        if len(table) > 48:
            raise ValueError(f"Too many values: {len(table)} > 48")
        for item in table:
            if item[0] % 2 != 0:
                raise ValueError("value passed for start_ch is not a multiple of 2")
            if item[1] % 8 != 0:
                raise ValueError("value passed for nof_ch is a multiple by 8")
            if item[2] not in range(48):
                raise ValueError("value passed for beam_index is not in range [0-48]")

        block = 0
        for item in table:
            start_channel = item[0]
            num_blocks = int(item[1] // 8)
            logical_channel = item[4]
            for i in range(num_blocks):
                self._channel_table[block] = [
                    start_channel + 8 * i,
                    item[2],
                    item[3],
                    logical_channel + 8 * i,
                    item[5],
                    item[6],
                    item[7],
                ]
                block += 1
        # raise NotImplementedError
        for i in range(block, 48):
            self._channel_table[i] = [0] * 7

    def get_channel_table(self: StationBeamformer) -> list[list[int]]:
        """
        Get channel table.

        :return: channel table
        """
        return copy.deepcopy(self._channel_table)

    def start(
        self: StationBeamformer,
    ) -> None:
        """Start."""
        self._is_running = True

    def stop(self: StationBeamformer) -> None:
        """stop."""
        self._is_running = False

    def is_running(self: StationBeamformer) -> bool:
        """:return: is running."""
        return self._is_running


class MockTpmFirmwareInformation:
    """Simulator for firmware information."""

    def __init__(self: MockTpmFirmwareInformation) -> None:
        self._reset_information()

    def _reset_information(self: MockTpmFirmwareInformation) -> None:
        """Reset firmware information."""
        self._major = -1
        self._minor = -1
        self._host = "<mock_host>"
        self._design = "<mock_design>"
        self._user = "<mock_user>"
        self._time = "<mock_time>"
        self._build = "<mock_build>"
        self._board = "<mock_board>"
        self._git_branch = "<mock_branch>"
        self._git_commit = "<mock_commit>"
        self._git_dirty_flag = "<mock_dirty_flag>"
        self._firmware_version = "<mock_firmware_version"

    def get_design(self: MockTpmFirmwareInformation) -> str:
        return self._design

    def get_build(self: MockTpmFirmwareInformation) -> str:
        return self._build

    def get_time(self: MockTpmFirmwareInformation) -> str:
        return self._time

    def get_user(self: MockTpmFirmwareInformation) -> str:
        return self._user

    def get_host(self: MockTpmFirmwareInformation) -> str:
        return self._host

    def get_git_branch(self: MockTpmFirmwareInformation) -> str:
        return self._git_branch

    def get_git_commit(self: MockTpmFirmwareInformation) -> str:
        return self._git_commit

    def get_firmware_version(self: MockTpmFirmwareInformation) -> str:
        return self._firmware_version


class MockTpm:
    """Simulator for a ska_low_sps_tpm_api.boards::Tpm class."""

    # Register map.
    # Requires only registers which are directly accessed from
    # the TpmDriver.
    PLL_LOCKED_REGISTER: Final = 0xE7
    REGISTER_MAP_DEFAULTS: dict[str, int] = {
        "0x30000000": 0x21033009,
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

    def __init__(self: MockTpm, logger: logging.Logger) -> None:
        """
        Initialise the MockTPM.

        :param logger: a logger for this simulator to use
        """
        # In hardware we will initialise a sequence to bring the
        # device into the programmed state. We do not simulate these
        # low level details and just assume all went ok.
        self.logger = logger
        self._is_programmed = False
        self.beam1 = StationBeamformer()
        self.beam2 = StationBeamformer()
        self.preadu = [PreAdu(logger)] * 2
        self._station_beamf = [self.beam1, self.beam2]
        self._address_map: dict[str, int] = {}
        self.tpm_firmware_information = MockTpmFirmwareInformation()
        self._40g_configuration: dict[str, Any] = {}
        self._station_beam_flagging = False

        self._register_map = MockTpm.REGISTER_MAP_DEFAULTS.copy()

    def get_board_info(self: MockTpm) -> dict[str, Any]:
        """
        Retrieve TPM board information.

        :return: A dictionary of board info.
        """
        board_info = {
            "ip_address": self.get_ip(),
            "netmask": self.get_netmask(),
            "gateway": self.get_gateway(),
            "ip_address_eep": self.get_ip_eep(),
            "netmask_eep": self.get_netmask_eep(),
            "gateway_eep": self.get_gateway_eep(),
            "MAC": self.get_mac(),
            "SN": self.get_serial_number(),
            "PN": self.get_part_number(),
            "bios": self.get_bios(),
        }
        return board_info

    def get_ip(self: MockTpm) -> str:
        """
        Return a mock ip string.

        :return: A string ip.
        """
        return "123.123.123.100"

    def get_netmask(self: MockTpm) -> str:
        """
        Return a mock netmask string.

        :return: A string netmask.
        """
        return "123.123.123.101"

    def get_gateway(self: MockTpm) -> str:
        """
        Return a mock gateway string.

        :return: A string gateway.
        """
        return "123.123.123.102"

    def get_ip_eep(self: MockTpm) -> str:
        """
        Return a mock ip_eep string.

        :return: A string ip_eep.
        """
        return "123.123.123.103"

    def get_netmask_eep(self: MockTpm) -> str:
        """
        Return a mock netmask_eep string.

        :return: A string netmask_eep.
        """
        return "123.123.123.104"

    def get_gateway_eep(self: MockTpm) -> str:
        """
        Return a mock gateway_eep string.

        :return: A string gateway_eep.
        """
        return "123.123.123.105"

    def get_mac(self: MockTpm) -> str:
        """
        Return a mock mac address string.

        :return: A string mac address.
        """
        return "e1:13:9a:7d:18:7d"

    def get_serial_number(self: MockTpm) -> str:
        """
        Return a mock serial_number string.

        :return: A string serial_number.
        """
        return "1234567890"

    def get_part_number(self: MockTpm) -> str:
        """
        Return a mock part_number string.

        :return: A string part_number.
        """
        return "0987654321"

    def get_bios(self: MockTpm) -> str:
        """
        Return a mock bios string.

        :return: A string bios version.
        """
        return "TileSimulatorBios"

    def get_40g_core_configuration(
        self: MockTpm,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict[str, Any]:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be returned. Defaults to -1, in which case all core
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations or none
        """
        # Fake some values. In reality we'd query the TPM here.
        self._40g_configuration = {
            "core_id": core_id,
            "arp_table_entry": arp_table_entry,
            "src_mac": self._get_src_mac(),
            "src_ip": self._get_src_ip(),
            "dst_ip": self._get_dst_ip(),
            "src_port": self._get_src_port(),
            "dst_port": self._get_dst_port(),
            "netmask": self._get_netmask(),
            "gateway_ip": self._get_gateway_ip(),
        }
        return self._40g_configuration

    def _get_src_mac(self: MockTpm) -> int:
        return 107752315813889

    def _get_src_ip(self: MockTpm) -> int:
        return 167774722

    def _get_dst_ip(self: MockTpm) -> int:
        return 167774723

    def _get_src_port(self: MockTpm) -> int:
        return 1234

    def _get_dst_port(self: MockTpm) -> int:
        return 5678

    def _get_netmask(self: MockTpm) -> int:
        return 4294967040

    def _get_gateway_ip(self: MockTpm) -> int:
        return 167774721

    def find_register(
        self: MockTpm,
        string: str,
        display: bool | None = False,
        info: bool | None = False,
    ) -> List[RegisterInfo | None]:
        """
        Find a item in a dictionary.

        This is mocking the reading of a register for the purpose of
        testing TPM_driver

        :param string: Regular expression to search against
        :param display: True to output result to console
        :param info: for linter.

        :return: registers found at address.
        """
        matches = []
        for k, v in self._register_map.items():
            if isinstance(k, int):
                pass
            elif re.search(str(string), k) is not None:
                reg_info = RegisterInfo(
                    k,
                    0x00,
                    "int",
                    "fpga_x",
                    "READ_WRITE",
                    "/24",
                    "30",
                    "2",
                    v,
                    2048,
                    "mocked values",
                )
                matches.append(reg_info)
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

    @property
    def info(self: MockTpm) -> dict[str, Any]:
        """
        Report MockTPM information.

        :return: the info
        """
        # TODO: Update this with representative data and types rather
        # than just arbitrary strings.
        communication_status = {"CPLD": True, "FPGA0": True, "FPGA1": True}
        info: dict[str, Any] = {}
        info["hardware"] = self.get_board_info()
        info["hardware"]["HARDWARE_REV"] = "<current hardware revision>"
        info["hardware"]["BOARD_MODE"] = "<current board mode>"
        info["hardware"]["LOCATION"] = "<current hardware location>"
        info["hardware"]["DDR_SIZE_GB"] = "<current hardware DDR size>"

        # Skip this as we're using strings for now.
        # # Convert EEP information to IPv4Address type
        info["hardware"]["ip_address_eep"] = IPv4Address(
            info["hardware"]["ip_address_eep"]
        )
        info["hardware"]["netmask_eep"] = IPv4Address(info["hardware"]["netmask_eep"])
        info["hardware"]["gateway_eep"] = IPv4Address(info["hardware"]["gateway_eep"])
        # Populate Firmware Build information from first FPGA
        info["fpga_firmware"] = {}
        info["fpga_firmware"]["design"] = self.tpm_firmware_information.get_design()
        info["fpga_firmware"]["build"] = self.tpm_firmware_information.get_build()
        info["fpga_firmware"][
            "version"
        ] = self.tpm_firmware_information.get_firmware_version()
        info["fpga_firmware"]["compile_time"] = self.tpm_firmware_information.get_time()
        info["fpga_firmware"]["compile_user"] = self.tpm_firmware_information.get_user()
        info["fpga_firmware"]["compile_host"] = self.tpm_firmware_information.get_host()
        info["fpga_firmware"][
            "git_branch"
        ] = self.tpm_firmware_information.get_git_branch()
        info["fpga_firmware"][
            "git_commit"
        ] = self.tpm_firmware_information.get_git_commit()
        # Dictionary manipulation, move 1G network information
        info["network"] = {}
        info["network"]["1g_ip_address"] = IPv4Address(info["hardware"]["ip_address"])
        info["network"]["1g_mac_address"] = info["hardware"]["MAC"]
        info["network"]["1g_netmask"] = IPv4Address(info["hardware"]["netmask"])
        info["network"]["1g_gateway"] = IPv4Address(info["hardware"]["gateway"])
        del info["hardware"]["ip_address"]
        del info["hardware"]["MAC"]
        del info["hardware"]["netmask"]
        del info["hardware"]["gateway"]
        # TODO: What should we do about this bit? Where to check comms in sim?
        # Add 40G network information, using ARP table entry for station beam packets
        if communication_status["FPGA0"] and communication_status["FPGA1"]:
            config_40g_1 = self.get_40g_core_configuration(arp_table_entry=0, core_id=0)
            config_40g_2 = self.get_40g_core_configuration(arp_table_entry=0, core_id=1)
            if config_40g_1 is not None:
                info["network"]["40g_ip_address_p1"] = IPv4Address(
                    config_40g_1["src_ip"]
                )
                mac = config_40g_1["src_mac"]
                info["network"]["40g_mac_address_p1"] = ":".join(
                    f"{(mac >> (i * 8)) & 0xFF:02X}" for i in reversed(range(6))
                )
                info["network"]["40g_gateway_p1"] = IPv4Address(
                    config_40g_1["gateway_ip"]
                )
                info["network"]["40g_netmask_p1"] = IPv4Address(config_40g_1["netmask"])

            if config_40g_2 is not None:
                info["network"]["40g_ip_address_p2"] = IPv4Address(
                    config_40g_2["src_ip"]
                )
                mac = config_40g_2["src_mac"]
                info["network"]["40g_mac_address_p2"] = ":".join(
                    f"{(mac >> (i * 8)) & 0xFF:02X}" for i in reversed(range(6))
                )
                info["network"]["40g_gateway_p2"] = IPv4Address(
                    config_40g_2["gateway_ip"]
                )
                info["network"]["40g_netmask_p2"] = IPv4Address(config_40g_2["netmask"])
        else:
            info["network"].update(
                dict.fromkeys(
                    [
                        "40g_ip_address_p1",
                        "40g_mac_address_p1",
                        "40g_gateway_p1",
                        "40g_netmask_p1",
                        "40g_ip_address_p2",
                        "40g_mac_address_p2",
                        "40g_gateway_p2",
                        "40g_netmask_p2",
                    ]
                )
            )
        return info

    def write_register(
        self: MockTpm,
        register: int | str,
        values: list[int],
        offset: int = 0,
        retry: bool = True,
    ) -> None:
        """
        Set register value.

        :param register: Register name
        :param values: Values to write
        :param offset: Memory address offset to write to
        :param retry: retry

        :raises LibraryError: Attempting to set a register not in the memory address.
        :raises NotImplementedError: if trying to write more than one value

        """
        if len(values) != 1 or offset != 0:
            raise NotImplementedError(
                "MockTpm can only write one value to a register at a time."
            )

        if isinstance(register, int):
            register = hex(register)
        if register == "" or register == "unknown":
            raise LibraryError(f"Unknown register: {register}")
        self._register_map[register] = values[0]

    def read_register(
        self: MockTpm, register: int | str, n: int = 1, offset: int = 0
    ) -> list[int]:
        """
        Get register value.

        :param register: Memory register to read from
        :param n: Number of words to read
        :param offset: Memory address offset to read from

        :raises NotImplementedError: if trying to read more than one value

        :return: Values
        """
        if n != 1 or offset != 0:
            raise NotImplementedError(
                "MockTpm can only read one value from a register at a time."
            )

        if register == ("pll", 0x508):
            return [self.PLL_LOCKED_REGISTER]
        if isinstance(register, int):
            register = hex(register)

        return [self._register_map[register]]

    def read_address(self: MockTpm, address: int, n: int = 1) -> Any:
        """
        Get address value.

        :param address: Memory address to read from
        :param n: Number of items to read

        :return: Values
        """
        return [self._address_map.get(str(address + i), 0) for i in range(n)]

    def write_address(
        self: MockTpm, address: int, values: list[int], retry: bool = True
    ) -> None:
        """
        Write address value.

        :param address: Memory address to write
        :param values: value to write
        :param retry: retry (does nothing yet.)
        """
        for i, value in enumerate(values):
            key = str(address + i)
            self._address_map.update({key: value})

    def __getitem__(self: MockTpm, key: Any) -> Any:
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
        if key == ("pll", 1288):
            return self.PLL_LOCKED_REGISTER
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

    def __init__(self: PreAdu, logger: logging.Logger) -> None:
        """
        Initialise mock plugin.

        :param logger: a logger for this simulator to use
        """
        self.logger = logger
        self.channel_filters: list[float] = [0.00] * 16
        self._nof_channels: int = 16

    def set_attenuation(
        self: PreAdu, attenuation: float, channels: list[int] | None = None
    ) -> None:
        """
        Set preadu channel attenuation.

        :param attenuation: the attenuation.
        :param channels: the channels.
        """
        if channels is None:
            channels = list(range(self._nof_channels))
        self.channel_filters[channels[0]] = attenuation

    def get_attenuation(self: PreAdu) -> list[float]:
        """
        Get preadu attenuation for all channels.

        :return: attenuation for all channels.
        """
        return self.channel_filters

    def write_configuration(self: PreAdu) -> None:
        """Write configuration to preadu."""
        self.logger.info("Not yet implemented.")
        return

    def select_low_passband(self: PreAdu) -> None:
        """Select low pass band."""
        self.bandpass = "low"

    def read_configuration(self: PreAdu) -> None:
        """Read configuration."""
        self.logger.info("Not yet implemented.")
        return


class TileSimulator:
    """
    This attempts to simulate ska_low_sps_tpm_api.Tile.

    This is used for testing the tpm_driver, it implements __getitem__,
    __setitem__ so that the TileSimulator can interface with the
    TPMSimulator in the same way as the ska_low_sps_tpm_api.Tile
    interfaces with the ska_low_sps_tpm_api.boards.TPM. Instead of
    writing to a register we write to a dictionary. It overwrite
    read_address, write_address, read_register, write_register
    for simplicity.
    """

    CHANNELISER_TRUNCATION: list[int] = [3] * 512
    CSP_ROUNDING: list[int] = [2] * 384
    STATIC_DELAYS = [-160.0] * 32
    PREADU_LEVELS = [0.0] * 32
    CLOCK_SIGNALS_OK = True
    TILE_MONITORING_POINTS = copy.deepcopy(TileData.get_tile_defaults())
    VOLTAGE = 5.0
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5
    ADC_RMS = [float(i) for i in range(32)]
    FPGAS_TIME = [0, 0]
    CURRENT_TILE_BEAMFORMER_FRAME = 0
    TILE_MONITORING_POINTS = copy.deepcopy(TileData.get_tile_defaults())
    PPS_DELAY = 12
    PHASE_TERMINAL_COUNT = 2
    TPM_TEMPERATURE_THRESHOLDS = {
        "board_warning_threshold": (-273.0, 90.0),
        "board_alarm_threshold": (-273.0, 90.0),
        "fpga1_warning_threshold": (-273.0, 90.0),
        "fpga1_alarm_threshold": (-273.0, 90.0),
        "fpga2_warning_threshold": (-273.0, 90.0),
        "fpga2_alarm_threshold": (-273.0, 90.0),
    }

    FIRMWARE_NAME = "itpm_v1_6.bit"
    FIRMWARE_LIST = [
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
    ]
    STATION_ID = 1
    TILE_ID = 1
    CSP_SPEAD_FORMAT = "SKA"

    def __init__(
        self: TileSimulator,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self.logger: logging.Logger = logger
        self._forty_gb_core_list: list[Any] = []
        self.tpm: MockTpm | None = None
        self._is_programmed: bool = False
        self._pending_data_request = False
        self._is_first = False
        self._is_last = False
        self._tile_id = self.TILE_ID
        self.pps_correction = 0
        self.fortygb_core_list: list[dict[str, Any]] = [
            {},
        ]
        # An optional mocked TPM to use in testing.
        self._mocked_tpm: MockTpm | None = None
        self._power_locked = False
        self.mock_connection_success = True
        self.fpgas_time: list[int] = self.FPGAS_TIME
        self._start_polling_event = threading.Event()
        self._tile_health_structure: dict[Any, Any] = copy.deepcopy(
            self.TILE_MONITORING_POINTS
        )
        self._station_id = self.STATION_ID
        self._timestamp = 0
        self._pps_delay: int = self.PPS_DELAY
        self._polling_thread = threading.Thread(
            target=self._timed_thread, name="tpm_polling_thread", daemon=True
        )
        self._polling_thread.start()
        self.dst_ip: str | None = None
        self.dst_port: int | None = None
        self.is_csp_write_successful: bool = True
        self.sync_time = 0
        self.csp_spead_format = self.CSP_SPEAD_FORMAT
        self._is_arp_table_healthy: bool = True
        self._is_set_first_last_tile_write_successful: bool = True
        self._is_spead_header_write_successful: bool = True
        self.csp_rounding = list(self.CSP_ROUNDING)
        self._adc_rms: list[float] = list(self.ADC_RMS)
        self.spead_data_simulator = SpeadDataSimulator(logger)
        self.tpm_mocked_overheating = False
        self._active_40g_ports_setting: str = ""
        self._pending_data_requests = False
        self._phase_terminal_count: int = self.PHASE_TERMINAL_COUNT
        self._tpm_temperature_thresholds = dict(self.TPM_TEMPERATURE_THRESHOLDS)
        self._is_cpld_connectable = True
        self._is_fpga1_connectable = True
        self._is_fpga2_connectable = True
        self._global_status_alarms: dict[str, int] = {
            "I2C_access_alm": 0,
            "temperature_alm": 0,
            "voltage_alm": 0,
            "SEM_wd": 0,
            "MCU_wd": 0,
        }
        self.integrated_channel_configuration = {
            "integration_time": -1.0,
            "first_channel": 0,
            "last_channel": 511,
            "current_channel": 0,
        }
        self.integrated_beam_configuration = {
            "integration_time": -1.0,
            "first_channel": 0,
            "last_channel": 383,
            "current_channel": 0,
        }
        self._rfi_count = np.zeros(
            (TileData.ANTENNA_COUNT, TileData.POLS_PER_ANTENNA), dtype=int
        )
        self._antenna_buffer_tile_attribute: dict[str, Any] = {
            "DDR_start_address": 0,
            "max_DDR_byte_size": 0,
            "set_up_complete": False,
            "data_capture_initiated": False,
            "used_fpga_id": [],
        }
        self._antenna_buffer_implemented = True

    @connected
    def get_health_status(self: TileSimulator, **kwargs: Any) -> dict[str, Any]:
        """
        Get the health state of the tile.

        :param kwargs: Any kwargs to identify health group.
            see ska_low_sps_tpm_api.Tile

        :return: mocked fetch of health.
        """
        if any([value == 2 for value in self._global_status_alarms.values()]):
            # ska-low-sps-tpm-api returns a subset of the health with mcu alarms
            # when a hard shutoff has occured.
            return {"alarms": self._tile_health_structure["alarms"]}
        return copy.deepcopy(self._tile_health_structure)

    @check_mocked_overheating
    @connected
    def get_firmware_list(self: TileSimulator) -> List[dict[str, Any]]:
        """:return: firmware list."""
        return self.FIRMWARE_LIST

    @check_mocked_overheating
    @connected
    def get_tile_id(self: TileSimulator) -> int:
        """:return: the mocked tile_id."""
        # this is set in the initialise
        return self._tile_id

    @check_mocked_overheating
    @connected
    def get_adc_rms(self: TileSimulator, sync: bool | None = False) -> list[float]:
        """
        Get ADC power, immediate.

        :param sync: Synchronise RMS read

        :return: the mock ADC rms values.
        """
        return self._adc_rms

    @check_mocked_overheating
    @connected
    def check_pending_data_requests(self: TileSimulator) -> bool:
        """:return: the pending data requess flag."""
        return self._pending_data_requests

    @connected
    def check_global_status_alarms(self: TileSimulator) -> dict[str, int]:
        """
        Check global status alarms.

        :return: a dictionary with the simulated alarm status.
        """
        return copy.deepcopy(self._global_status_alarms)

    @connected
    def get_temperature(self: TileSimulator) -> float:
        """
        Get the board temperature.

        :return: a float with the board temperature.
        """
        return self._tile_health_structure["temperatures"]["board"]

    @check_mocked_overheating
    @connected
    def initialise_beamformer(
        self: TileSimulator, start_channel: int, nof_channels: int
    ) -> None:
        """
        Mock set the beamformer parameters.

        :param start_channel: start_channel
        :param nof_channels: nof_channels

        :raises ValueError: For out of range values.
        """
        if start_channel < 0:
            raise ValueError("cannot be negative")
        if nof_channels > 384:
            raise ValueError("too many channels")
        pass

    @check_mocked_overheating
    def program_fpgas(self: TileSimulator, bitfile: str) -> None:
        """
        Mock programmed state to True.

        :param bitfile: the name of the bitfile to download

        :raises LibraryError: if bitfile is of type None.
        """
        self.connect()
        if bitfile is None:
            self.logger.error("Provided bitfile is None type")
            raise LibraryError("bitfile is None type")
        # Every time we reprogram the temperature thresholds get reset.
        self._tpm_temperature_thresholds = {
            "board_warning_threshold": (-273.0, 90.0),
            "board_alarm_threshold": (-273.0, 90.0),
            "fpga1_warning_threshold": (-273.0, 90.0),
            "fpga1_alarm_threshold": (-273.0, 90.0),
            "fpga2_warning_threshold": (-273.0, 90.0),
            "fpga2_alarm_threshold": (-273.0, 90.0),
        }
        self.evaluate_mcu_action()
        self.tpm._is_programmed = True  # type: ignore

    @property
    def spead_ska_format_supported(self) -> bool:
        """
        Check if new (SKA) format for CSP SPEAD header is supported.

        :return: True if new (SKA) format for CSP SPEAD header is supported
        """
        return True

    @check_mocked_overheating
    @connected
    def erase_fpgas(self: TileSimulator) -> None:
        """Erase the fpga firmware."""
        self.logger.error("erasing in tile sim")
        assert self.tpm
        self.tpm._is_programmed = False

    @check_mocked_overheating
    def initialise(
        self: TileSimulator,
        station_id: int = 0,
        tile_id: int = 0,
        lmc_use_40g: bool = False,
        lmc_dst_ip: str | None = None,
        lmc_dst_port: int = 4660,
        lmc_integrated_use_40g: bool = False,
        src_ip_fpga1: str | None = None,
        src_ip_fpga2: str | None = None,
        dst_ip_fpga1: str | None = None,
        dst_ip_fpga2: str | None = None,
        src_port: int = 4661,
        dst_port: int = 4660,
        dst_port_single_port_mode: int = 4662,
        rx_port_single_port_mode: int = 4662,
        netmask_40g: str | None = None,
        gateway_ip_40g: str | None = None,
        active_40g_ports_setting: str = "port1-only",
        enable_adc: bool = True,
        enable_ada: bool = False,
        enable_test: bool = False,
        use_internal_pps: bool = False,
        pps_delay: int = 0,
        time_delays: float | int | list = 0,
        is_first_tile: bool = False,
        is_last_tile: bool = False,
        qsfp_detection: str = "auto",
        adc_mono_channel_14_bit: bool = False,
        adc_mono_channel_sel: int = 0,
        global_start_time: int | None = None,
    ) -> None:
        """
        Initialise tile.

        :param station_id: station ID
        :param tile_id: Tile ID in the station
        :param lmc_use_40g: if True use 40G interface to transmit LMC data,
            otherwise use 1G
        :param lmc_dst_ip: destination IP address for LMC data packets
        :param lmc_dst_port: destination UDP port for LMC data packets
        :param lmc_integrated_use_40g: if True use 40G interface to transmit LMC
            integrated data, otherwise use 1G
        :param src_ip_fpga1: source IP address for FPGA1 40G interface
        :param src_ip_fpga2: source IP address for FPGA2 40G interface
        :param dst_ip_fpga1: destination IP address for beamformed data from
            FPGA1 40G interface
        :param dst_ip_fpga2: destination IP address for beamformed data from
            FPGA2 40G interface
        :param src_port: source UDP port for beamformed data packets
        :param dst_port: destination UDP port for beamformed data packets
        :param enable_ada: enable adc amplifier, Not present in most TPM versions
        :param enable_adc: Enable ADC
        :param active_40g_ports_setting: placeholder docstring
        :param dst_port_single_port_mode: placeholder docstring
        :param gateway_ip_40g: placeholder docstring
        :param netmask_40g: placeholder docstring
        :param rx_port_single_port_mode: placeholder docstring
        :param enable_test: setup internal test signal generator instead of ADC
        :param use_internal_pps: use internal PPS generator synchronised across FPGAs
        :param pps_delay: PPS delay correction in 625ps units
        :param time_delays: time domain delays for 32 inputs
        :param is_first_tile: True if this tile is the first tile in the
            beamformer chain
        :param is_last_tile: True if this tile is the last tile in the beamformer chain
        :param qsfp_detection: "auto" detects QSFP cables automatically,
            "qsfp1", force QSFP1 cable detected,
            QSFP2 cable not detected
            "qsfp2", force QSFP1 cable not detected,
            QSFP2 cable detected
            "all", force QSFP1 and QSFP2 cable detected
            "flyover_test", force QSFP1 and QSFP2
            cable detected and adjust
            polarity for board-to-board cable
            "none", force no cable not detected
        :param adc_mono_channel_14_bit: Enable ADC mono channel 14bit mode
        :param adc_mono_channel_sel: Select channel in mono channel mode (0=A, 1=B)
        :param global_start_time: TPM will act as if it is
            started at this time (seconds)
        """
        # synchronise the time of both FPGAs UTC time
        # define if the tile is the first or last in the station_beamformer
        # for station_beamf in self.tpm._station_beamf:
        # station_beamf.set_first_last_tile(is_first_tile, is_last_tile)
        # Before initialing, check if TPM is programmed
        if not self.is_programmed():
            self.logger.error("Cannot initialise board which is not programmed")
            return
        self.logger.info(f"delay correction set to {pps_delay}")
        self.pps_correction = pps_delay
        self.set_time_delays(time_delays)
        self._is_first = is_first_tile
        self._is_last = is_last_tile
        self._tile_id = tile_id
        self._station_id = station_id
        self.sync_time = 0
        reg1 = "fpga1.dsp_regfile.stream_status.channelizer_vld"
        reg2 = "fpga2.dsp_regfile.stream_status.channelizer_vld"
        if self.tpm:
            self.tpm[reg1] = 0
            self.tpm[reg2] = 0
        self._active_40g_ports_setting = active_40g_ports_setting
        self._start_polling_event.set()
        time.sleep(random.randint(1, 3))
        self.logger.debug("Initialise complete in Tpm.")

    @connected
    def find_register(
        self: TileSimulator, string: str = "", display: bool = False, info: bool = False
    ) -> list[None | RegisterInfo]:
        """
        Return register information from a provided search string.

        Note: this is a wrapper method of 'ska_low_sps_tpm_api.boards.tpm.find_register'

        :param string: Regular expression to search against
        :param display: True to output result to console
        :param info: print a message with additional information if True.

        :return: List of found registers
        """
        assert self.tpm
        return self.tpm.find_register(string, display, info)

    @connected
    def check_pll_locked(
        self: TileSimulator,
    ) -> bool:
        """
        Check in hardware if PLL is locked.

        :return: True if PLL is locked.
        """
        assert self.tpm
        pll_status = self.tpm["pll", 0x508]  # type: ignore
        return pll_status in [0xF2, 0xE7]

    @connected
    def get_beamformer_table(self: TileSimulator, fpga_id: int = 0) -> list[list[int]]:
        """
        Return the beamformer table.

        Returns a table with the following entries for each 8-channel block:
        >> 0: start physical channel (64-440)
        >> 1: beam_index:  subarray beam used for this region, range [0:48)
        >> 2: subarray_id: ID of the subarray [1:48]
        >>     Here is the same for all channels
        >> 3: subarray_logical_channel: Logical channel in the subarray
        >>     Here equal to the station logical channel
        >> 4: subarray_beam_id: ID of the subarray beam
        >> 5: substation_id: ID of the substation
        >> 6: aperture_id:  ID of the aperture (station*100+substation?)

        :param fpga_id: A parameter to specify what fpga we want
            to return the beamformer table for. (Default fpga_id = 0)

        Note: this is a wrapper method of
        'ska_low_sps_tpm_api.boards.tpm.station_beamf.get_channel_table'

        :return: Nx7 table with one row every 8 channels
        """
        assert self.tpm
        return self.tpm.station_beamf[fpga_id].get_channel_table()

    @connected
    def define_channel_table(
        self: TileSimulator, region_array: list[list[int]], fpga_id: None | int = None
    ) -> bool:
        """
        Set frequency regions.

        Regions are defined in a 2-d array, for a maximum of 16 regions.
        Each element in the array defines a region, with the form:
        >>    [start_ch, nof_ch, beam_index, <optional>
        >>    subarray_id, subarray_logical_ch, aperture_id, substation_id]
        >>    0: start_ch:    region starting channel (currently must be a
        >>        multiple of 2, LS bit discarded)
        >>    1: nof_ch:      size of the region: must be multiple of 8 chans
        >>    2: beam_index:  subarray beam used for this region, range [0:48)
        >>    3: subarray_id: ID of the subarray [1:48]
        >>    4: subarray_logical_channel: Logical channel in the subarray
        >>        it is the same for all (sub)stations in the subarray
        >>        Defaults to station logical channel
        >>    5: subarray_beam_id: ID of the subarray beam
        >>        Defaults to beam index
        >>    6: substation_ID: ID of the substation
        >>        Defaults to 0 (no substation)
        >>    7: aperture_id:  ID of the aperture (station*100+substation?)
        >>        Defaults to

        Total number of channels must be <= 384
        The routine computes the arrays beam_index, region_off, region_sel,
        and the total number of channels nof_chans,
        and programs it in the hardware.
        Optional parameters are placeholders for firmware supporting
        more than 1 subarray. Current firmware supports only one subarray
        and substation, so corresponding IDs must be the same in each row

        :param fpga_id: the id of the fpga we want to define the channel table for.
            if None both are configured.
        :param region_array: bidimensional array, one row for each
                        spectral region, 3 or 8 items long

        :return: True if OK
        """
        assert self.tpm
        if fpga_id is None:
            # define in both fpga.
            self.tpm.station_beamf[0].define_channel_table(region_array)
            self.tpm.station_beamf[1].define_channel_table(region_array)
            return True

        self.tpm.station_beamf[fpga_id].define_channel_table(region_array)
        return True

    @connected
    def get_tpm_temperature_thresholds(
        self: TileSimulator,
    ) -> dict[str, tuple[float, float]]:
        """
        Return a dictionary of temperature thresholds.

        return structure looks like:
        >>{
        >>    "board_warning_threshold": (min, max),
        >>    "board_alarm_threshold"  : (min, max),
        >>    "fpga1_warning_threshold": (min, max),
        >>    "fpga1_alarm_threshold": (min, max),
        >>    "fpga2_warning_threshold": (min, max),
        >>    "fpga2_alarm_threshold": (min, max),
        >>}

        :return: A dictionary containing the temperature thresholds.
        :rtype: dict
        """
        return self._tpm_temperature_thresholds

    @check_mocked_overheating
    @connected
    def get_fpga_time(self: TileSimulator, device: Device) -> int:
        """
        :param device: device.

        :return: the fpga_time.

        :raises LibraryError: If invalid device specified.
        """
        try:
            return self.fpgas_time[device.value - 1]
        except Exception as e:
            raise LibraryError("Invalid device specified") from e

    @check_mocked_overheating
    @connected
    def set_station_id(self: TileSimulator, station_id: int, tile_id: int) -> None:
        """
        Set mock registers to some value.

        :param tile_id: tile_id
        :param station_id: station_id
        """
        self._tile_id = tile_id
        self._station_id = station_id

    @check_mocked_overheating
    @connected
    def get_pps_delay(self: TileSimulator, enable_correction: bool = True) -> int:
        """
        Get the pps delay.

        :param enable_correction: enable correction.

        :return: the pps delay.
        """
        if enable_correction:
            return self._pps_delay + self.pps_correction
        return self._pps_delay

    @check_mocked_overheating
    @connected
    def is_programmed(self: TileSimulator) -> bool:
        """
        Return whether the mock has been implemented.

        :return: the mocked programmed state
        """
        if self.tpm is None:
            return False
        return self.tpm._is_programmed

    @connected
    @antenna_buffer_implemented
    def set_up_antenna_buffer(
        self: TileSimulator,
        mode: str = "SDN",
        ddr_start_byte_address: int = 512 * 1024**2,
        max_ddr_byte_size: Optional[int] = None,
    ) -> None:
        """Mock set_up_antenna_buffer.

        :param mode: netwrok to transmit antenna buffer data to. Options: 'SDN'
            (Science Data Network) and 'NSDN' (Non-Science Data Network)
        :param ddr_start_byte_address: first address in the DDR for antenna buffer
            data to be written in (in bytes).
        :param max_ddr_byte_size: last address for writing antenna buffer data
            (in bytes). If 'None' is chosen, the method will assume the last
            address to be the final address of the DDR chip
        """
        payload_length = 8192 if mode.upper() == "SDN" else 1536

        if not max_ddr_byte_size:
            # assume the antenna buffer capacity is 4 GB
            max_ddr_byte_size = (4 * 1024**3) - ddr_start_byte_address

        # log the original message
        self.logger.info(
            f"AntennaBuffer: Setup parameters - Mode={mode}, "
            + f"Payload Length={payload_length},"
            + f" DDR Start Address={ddr_start_byte_address},"
            + f" Max DDR Size={max_ddr_byte_size}"
        )
        # save values to buffer attributes
        self._antenna_buffer_tile_attribute["mode"] = mode
        self._antenna_buffer_tile_attribute[
            "DDR_start_address"
        ] = ddr_start_byte_address
        self._antenna_buffer_tile_attribute["max_DDR_byte_size"] = max_ddr_byte_size
        self._antenna_buffer_tile_attribute["set_up_complete"] = True

    @connected
    @antenna_buffer_implemented
    def start_antenna_buffer(
        self: TileSimulator,
        antennas: list,
        start_time: int = -1,
        timestamp_capture_duration: int = 75,
        continuous_mode: bool = False,
    ) -> int:
        """Mock start_antenna_buffer.

        :param antennas: a list of antenna IDs to be used by the buffer, from 0 to 15.
            One or two antennas can be used for each FPGA, or 1 to 4 per buffer.
        :param start_time: the first time stamp that will be written into the DDR.
            When set to -1, the buffer will begin writing as soon as possible.
        :param timestamp_capture_duration: the capture duration in timestamps.
        :param continuous_mode: "True" for continous capture. If enabled, time capture
            durations is ignored

        :raises Exception: when antenna IDS are missing/incorrect or antenna
            buffer was not intiated.

        :return: ddr write size
        """
        # Check that the antenna buffer was set up
        if not self._antenna_buffer_tile_attribute["set_up_complete"]:
            raise Exception(
                "AntennaBuffer ERROR: Please set up the antenna buffer "
                + "before writing"
            )

        # Antennas must be specifed.
        if not antennas:
            raise Exception(
                "AntennaBuffer ERROR: Antennas list is empty "
                + "please give at lease one antenna ID"
            )

        # Antenna index is from 0 to 15.
        invalid_input = [x for x in antennas if x < 0 or x > 15]
        if invalid_input:
            raise Exception(
                "AntennaBuffer ERROR: out of range antenna IDs present "
                + f"{invalid_input}. Please give an antenna ID from 0 to 15"
            )

        # Save values to buffer attributes for testing
        self._antenna_buffer_tile_attribute["antennas"] = antennas

        # Remove duplicates and then split the list in 2 parts
        antennas = list(dict.fromkeys(antennas))
        antennas = [[x for x in antennas if x < 8], [x - 8 for x in antennas if x >= 8]]
        self.logger.info(f"Antennas lists of lists = {antennas}")

        # clear old fpgas
        self._antenna_buffer_tile_attribute["used_fpga_id"] = []

        for fpga_id in range(2):
            if antennas[fpga_id]:
                # log which antennas and fpgas are used
                self.logger.info(
                    f"AntennaBuffer will be using FPGA {fpga_id+1},"
                    + f" antennas = {antennas[fpga_id]}"
                )
                self._antenna_buffer_tile_attribute["used_fpga_id"].append(fpga_id)

                # Note: this may need improvement later if we want to test in more
                # detail, for now we mock the possible errors
                # Try and calculate a value for the ddr_write_size
                if continuous_mode:
                    ddr_write_size = (
                        self._antenna_buffer_tile_attribute["max_DDR_byte_size"]
                        - self._antenna_buffer_tile_attribute["DDR_start_address"]
                    )
                else:
                    # capture duration is in seconds and 4 GiB lasts about 2.68
                    # so the size of the ddr is 4GiB/2.64 * capture duration
                    ddr_write_size = (
                        timestamp_capture_duration * (4032 * 1024**2 / 2.68)
                        - self._antenna_buffer_tile_attribute["DDR_start_address"]
                    )

        self._antenna_buffer_tile_attribute.update({"data_capture_initiated": True})

        # Save values to buffer attributes for testing
        self._antenna_buffer_tile_attribute["start_time"] = start_time
        self._antenna_buffer_tile_attribute[
            "timestamp_capture_duration"
        ] = timestamp_capture_duration
        self._antenna_buffer_tile_attribute["continuous_mode"] = continuous_mode
        self._antenna_buffer_tile_attribute["read_antenna_buffer"] = False
        self._antenna_buffer_tile_attribute["stop_antenna_buffer"] = False
        return ddr_write_size

    @connected
    @antenna_buffer_implemented
    def read_antenna_buffer(self: TileSimulator) -> None:
        """Mock read AntennaBuffer data from the DDR.

        :raises Exception: when antenna buffer was not intiated or started.
        """
        if not self._antenna_buffer_tile_attribute["set_up_complete"]:
            raise Exception(
                "AntennaBuffer ERROR: Please set up the antenna buffer before reading"
            )
        if not self._antenna_buffer_tile_attribute["data_capture_initiated"]:
            raise Exception(
                "AntennaBuffer ERROR: Please capture antenna buffer data before reading"
            )

        # Save values to buffer attributes for testing
        self._antenna_buffer_tile_attribute["read_antenna_buffer"] = True
        self._antenna_buffer_tile_attribute["stop_antenna_buffer"] = True
        return

    @connected
    @antenna_buffer_implemented
    def stop_antenna_buffer(self: TileSimulator) -> None:
        """Mock stop the antenna buffer."""
        self.logger.info(f"AntennaBuffer: Stopping for tile {self.get_tile_id()}")

        # Save values to buffer attributes for testing
        self._antenna_buffer_tile_attribute["stop_antenna_buffer"] = True

    @connected
    def enable_station_beam_flagging(
        self: TileSimulator, fpga_id: Optional[int] = None
    ) -> None:
        """
        Enable station beam flagging.

        :param fpga_id: id of the fpga.
        """
        self._station_beam_flagging = True

    @connected
    def disable_station_beam_flagging(
        self: TileSimulator, fpga_id: Optional[int] = None
    ) -> None:
        """
        Disable station beam flagging.

        :param fpga_id: id of the fpga.
        """
        self._station_beam_flagging = False

    @property
    def tile_info(self: TileSimulator) -> str:
        """
        Report tile firmware information.

        :returns: A string of tile information.
        """
        self.logger.debug("getting tile info")
        # return str(self)
        assert self.tpm is not None
        info: dict[str, Any] = self.tpm.info
        self._convert_ip_to_str(info)
        # Prints out a nice table to the logs.
        self.logger.info(str(self))
        return json.dumps(info)

    def _convert_ip_to_str(self: TileSimulator, nested_dict: dict[str, Any]) -> None:
        """
        Convert IPAddresses to str in (possibly nested) dict.

        :param nested_dict: A (possibly nested) dict with IPAddresses to convert.
        """
        for k, v in nested_dict.items():
            if isinstance(v, IPv4Address):
                nested_dict[k] = str(v)
            elif isinstance(v, dict):
                self._convert_ip_to_str(v)

    @check_mocked_overheating
    @connected
    def configure_40g_core(
        self: TileSimulator,
        core_id: int = 0,
        arp_table_entry: int = 0,
        src_mac: int | None = None,
        src_ip: str | None = None,
        src_port: int | None = None,
        dst_ip: str | None = None,
        dst_port: int | None = None,
        rx_port_filter: int | None = None,
        netmask: int | None = None,
        gateway_ip: int | None = None,
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
        :param rx_port_filter: Filter for incoming packets
        :param netmask: Netmask
        :param gateway_ip: Gateway IP

        :raises ValueError: when the core_id is not [0,1]
        """
        if core_id not in [0, 1]:
            raise ValueError(f"Invalid core_id {core_id}, must be 0 or 1.")

        core_dict = {
            "core_id": core_id,
            "arp_table_entry": arp_table_entry,
            "src_mac": src_mac,
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "rx_port_filter": rx_port_filter,
            "netmask": netmask,
            "gateway_ip": gateway_ip,
        }
        self._forty_gb_core_list.append(core_dict)

    @check_mocked_overheating
    @connected
    def get_40g_core_configuration(
        self: TileSimulator,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict[str, Any] | list[dict] | None:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be returned. Defaults to -1, in which case all core
            configurations are returned, defaults to -1
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations or none
        """
        # Fake some values. In reality we'd query the TPM here.
        if self.tpm is not None:
            self._40g_configuration = {
                "core_id": core_id,
                "arp_table_entry": arp_table_entry,
                "src_mac": self.tpm._get_src_mac(),
                "src_ip": self.tpm._get_src_ip(),
                "dst_ip": self.tpm._get_dst_ip(),
                "src_port": self.tpm._get_src_port(),
                "dst_port": self.tpm._get_dst_port(),
                "netmask": self.tpm._get_netmask(),
                "gateway_ip": self.tpm._get_gateway_ip(),
            }
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("core_id") == core_id:
                if item.get("arp_table_entry") == arp_table_entry:
                    return item
        return None

    @check_mocked_overheating
    @connected
    def check_arp_table(self: TileSimulator, timeout: float = 30.0) -> bool:
        """
        Check arp table.

        :param timeout: Timeout in seconds

        :return: a bool representing if arp table is healthy.
        """
        return self._is_arp_table_healthy

    @check_mocked_overheating
    @connected
    def set_lmc_download(
        self: TileSimulator,
        mode: str,
        payload_length: int = 1024,
        dst_ip: str | None = None,
        src_port: int | None = 0xF0D0,
        dst_port: int | None = 4660,
        netmask_40g: int | None = None,
        gateway_ip_40g: int | None = None,
    ) -> None:
        """
        Specify where the control data will be transmitted.

        With the simulator no traffic will leave the cluster.
        To transmit data from the pod hosting the simulator
        to the DAQ (data acquisition) receiver, a Kubernetes service is required.
        Therefore dst_ip is the name of the service to use rather than the IP.

        :param mode: "1G" or "10G"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination service.
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        :param netmask_40g: the mask to apply
        :param gateway_ip_40g: the gateway ip.
        """
        # This is required to work out where the Tile will send data to.
        # In the Tile simulator we will not be using IP addresses but rather services
        # to route data to the correct location.
        self.dst_ip = dst_ip
        self.dst_port = dst_port

    @check_mocked_overheating
    @connected
    def reset_eth_errors(self: TileSimulator) -> None:
        """Reset Ethernet errors."""
        self.logger.info("This is not implemented")
        return

    def connect(
        self: TileSimulator,
        initialise: bool = False,
        load_plugin: bool = True,
        enable_ada: bool = False,
        enable_adc: bool = True,
        dsp_core: bool = True,
        adc_mono_channel_14_bit: bool = False,
        adc_mono_channel_sel: int = 0,
    ) -> None:
        """
        Attempt to form a connection with TPM.

        :param initialise: Initialises the TPM object
        :param load_plugin: loads software plugins
        :param enable_ada: Enable ADC amplifier (usually not present)
        :param enable_adc: Enable ADC
        :param dsp_core: Enable loading of DSP core plugins
        :param adc_mono_channel_14_bit: Enable ADC mono channel 14bit mode
        :param adc_mono_channel_sel: Select channel in mono channel mode (0=A, 1=B)
        """
        self.logger.info("Connect called on the simulator")
        if self.mock_connection_success:
            if self.tpm is None:
                # Use defined tpm if specified.
                self.tpm = self._mocked_tpm or MockTpm(self.logger)
                # This sleep is to wait for the timed thread to
                # update a register.
                time.sleep(0.12)
        else:
            self.tpm = None
            self.logger.error("Failed to connect to board at 'some_mocked_ip'")

    def mock_off(self: TileSimulator, lock: bool = False) -> None:
        """
        Fake a connection by constructing the TPM.

        :param lock: True if we want to lock this state.
        """
        if lock:
            self.mock_connection_success = False
            self.__is_connectable(False)
            self._power_locked = lock
        elif self._power_locked:
            self.logger.error("Failed to change mocked tile state")
            self.logger.error(f"is connectable {self.mock_connection_success}")
        else:
            self.mock_connection_success = False
            self.__is_connectable(False)

    def mock_on(self: TileSimulator, lock: bool = False) -> None:
        """
        Fake a connection by constructing the TPM.

        :param lock: True if we want to lock this state.
        """
        if lock:
            self.mock_connection_success = True
            self.__is_connectable(True)
            self._power_locked = lock
        elif self._power_locked:
            self.logger.error("Failed to change mocked tile state")
            self.logger.error(f"is connectable {self.mock_connection_success}")
        else:
            self.mock_connection_success = True
            self.__is_connectable(True)

    def __is_connectable(self: TileSimulator, connectable: bool) -> None:
        """
        Set the connection status.

        :param connectable: True if the CPLD and FPGAs are connectable.
        """
        self._is_cpld_connectable = connectable
        self._is_fpga1_connectable = connectable
        self._is_fpga2_connectable = connectable

    @connected
    def __getitem__(self: TileSimulator, key: int | str) -> Any:
        """
        Get the register from the TPM.

        :param key: key
        :return: mocked item at address

        :raises BoardError: if you are trying to attempt communication with
            a FPGA that is OFF.
        """
        cpld_registers = [int(0x30000000)]
        if self.tpm_mocked_overheating:
            # We can still access the (CPLD version) when FPGAs are shutdown.
            if key in cpld_registers and self._is_cpld_connectable:
                pass
            else:
                self.logger.warning(
                    "BoardError: Not possible to communicate with the FPG0: "
                    "Failed to read_address 0x4 on board: UCP::read. "
                    "Command failed on board. "
                    "Requested address 0x4 received address 0xfffffffb"
                )
                raise BoardError(
                    "BoardError: Not possible to communicate with the FPG0: "
                    "Failed to read_address 0x4 on board: UCP::read. "
                    "Command failed on board. "
                    "Requested address 0x4 received address 0xfffffffb"
                )

        return self.tpm[key]  # type: ignore

    @check_mocked_overheating
    @connected
    def __setitem__(self: TileSimulator, key: int | str, value: Any) -> None:
        """
        Set a registers value in the TPM.

        :param key: key
        :param value: value
        """
        self.tpm[key] = value  # type: ignore

    @check_mocked_overheating
    @connected
    def set_channeliser_truncation(
        self: TileSimulator, trunc: list[int], signal: int | None = None
    ) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param trunc: list with M values, one for each of the
            frequency channels. Same truncation is applied to the corresponding
            frequency channels in all inputs.
        :param signal: Input signal, 0 to 31. If None, apply to all
        """
        self._channeliser_truncation = trunc
        # self.logger.info("Not implemented, return without error to allow poll.")
        return

    @check_mocked_overheating
    @connected
    def set_time_delays(self: TileSimulator, delays: int | float | list[float]) -> bool:
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in input streams, specified in nanoseconds.
            A positive delay adds delay to the signal stream

        :returns: True if command executed to completion.
        """
        if isinstance(delays, int | float):
            # simply convert to list
            delays = [delays] * 32
        if len(delays) != 32:
            self.logger.error(
                "Invalid delays specfied (must be a " "list of numbers of length 32)"
            )
            return False
        for i in range(16):
            self[f"fpga1.test_generator.delay_{i}"] = int(delays[i] / 1.25 + 0.5) + 128
            self[f"fpga2.test_generator.delay_{i}"] = (
                int(delays[i + 16] / 1.25 + 0.5) + 128
            )
        return True

    @check_mocked_overheating
    @connected
    def current_tile_beamformer_frame(self: TileSimulator) -> int:
        """:return: beamformer frame."""
        return self.get_fpga_timestamp()

    @check_mocked_overheating
    @connected
    def set_csp_rounding(self: TileSimulator, rounding: list[int]) -> bool:
        """
        Set the final rounding in the CSP samples, one value per beamformer channel.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP

        :return: true is write a success.
        """
        if self.is_csp_write_successful:
            self.csp_rounding = rounding
        return self.is_csp_write_successful

    @check_mocked_overheating
    @connected
    def define_spead_header(
        self: TileSimulator,
        station_id: int,
        subarray_id: int,
        nof_antennas: int,
        ref_epoch: int = -1,
        start_time: int | None = 0,
        ska_spead_header_format: bool = False,
    ) -> bool:
        """
        Define the SPEAD header for the given parameters.

        :param station_id: The ID of the station.
        :param subarray_id: The ID of the subarray.
        :param nof_antennas: Number of antennas in the station
        :param ref_epoch: Unix time of epoch. -1 uses value defined in set_epoch
        :param start_time: start time
        :param ska_spead_header_format: True for new (SKA) CBF SPEAD header format


        :return: a bool representing if command executed without error.
        """
        if self._is_spead_header_write_successful:
            self._station_id = station_id
        return self._is_spead_header_write_successful

    @check_mocked_overheating
    @connected
    def set_beamformer_regions(
        self: TileSimulator, region_array: list[list[int]]
    ) -> None:
        """
        Set beamformer region_array.

        :param region_array: region_array
        """
        if self.tpm is None:
            return
        self.tpm.station_beamf[0].define_channel_table(region_array)
        self.tpm.station_beamf[1].define_channel_table(region_array)

    @check_mocked_overheating
    @connected
    def set_first_last_tile(self: TileSimulator, is_first: bool, is_last: bool) -> bool:
        """
        Set first last tile in chain.

        :param is_first: true if first
        :param is_last: true if last

        :return: a bool representing if command executed without error.
        """
        if self._is_set_first_last_tile_write_successful:
            self._is_first = is_first
            self._is_last = is_last
        return self._is_set_first_last_tile_write_successful

    @check_mocked_overheating
    @connected
    def load_calibration_coefficients(
        self: TileSimulator, antenna: int, calibration_coefficients: list[list[complex]]
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
        :param calibration_coefficients: Calibration coefficient array
        """
        self.logger.debug(f"Received calibration coefficients for antenna {antenna}")

    @check_mocked_overheating
    @connected
    def switch_calibration_bank(self: TileSimulator, switch_time: int = 0) -> None:
        """
        Switch calibration bank.

        :param switch_time: switch time
        """
        self.logger.debug("Applying calibration coefficients")

    @check_mocked_overheating
    @connected
    def set_pointing_delay(
        self: TileSimulator, delay_array: list[list[float]], beam_index: int
    ) -> None:
        """
        Set pointing delay.

        :param delay_array: delay array
        :param beam_index: beam index
        """
        self.logger.debug(f"Received pointing delays for beam {beam_index}")

    @check_mocked_overheating
    @connected
    def load_pointing_delay(
        self: TileSimulator, load_time: int = 0, load_delay: int = 64
    ) -> None:
        """
        Load pointing delay.

        :param load_time: load time
        :param load_delay: delay in (in ADC frames/256) to apply when load_time == 0
        """
        self.logger.debug("Applying pointing delays")

    @check_mocked_overheating
    @connected
    def start_beamformer(
        self: TileSimulator,
        start_time: int = 0,
        duration: int = -1,
        scan_id: int = 0,
        mask: int | None = None,
        subarray_beam: int | None = None,
        channel_groups: list[int] | None = None,
    ) -> bool:
        """
        Start beamformer.

        :param start_time: start time UTC
        :param duration: duration
        :param scan_id: ID of the scan, to be specified in the CSP SPEAD header
        :param mask: Bitmask of the channels to be started.
            Ignored if beam is specified.
        :param subarray_beam: subarray_beam number to start.
            Computes the mask using beam table
        :param channel_groups: list of channel groups, in range 0:48.
            group 0 for channels 0-7, to group 47 for channels 380-383.

        :return: true if the beamformer was started successfully.
        """
        if self.beamformer_is_running():
            return False
        if subarray_beam is None:
            self.tpm.beam1.start()  # type: ignore
            self.tpm.beam2.start()  # type: ignore
        elif subarray_beam == 1:
            self.tpm.beam1.start()  # type: ignore
        elif subarray_beam == 2:
            self.tpm.beam2.start()  # type: ignore
        return True

    @check_mocked_overheating
    @connected
    def stop_beamformer(
        self: TileSimulator,
        mask: bool | None = None,
        subarray_beam: int | None = None,
        channel_groups: list[int] | None = None,
    ) -> None:
        """
        Stop beamformer.

        :param mask: Bitmask of the channels to be started.
            Ignored if beam is specified.
        :param subarray_beam: Subarray beam number to start.
            Computes the mask using beam table
        :param channel_groups: list of channel groups, in range 0:48.
            group 0 for channels 0-7, to group 47 for channels 380-383.
        """
        if subarray_beam is None:
            self.tpm.beam1.stop()  # type: ignore
            self.tpm.beam2.stop()  # type: ignore
        elif subarray_beam == 1:
            self.tpm.beam1.stop()  # type: ignore
        elif subarray_beam == 2:
            self.tpm.beam2.stop()  # type: ignore

    @check_mocked_overheating
    @connected
    def configure_integrated_channel_data(
        self: TileSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Configure and start continuous integrated channel data.

        TODO Implement generation of integrated packets
        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        self.integrated_channel_configuration = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
            "current_channel": first_channel,
        }

    @check_mocked_overheating
    @connected
    def configure_integrated_beam_data(
        self: TileSimulator,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
    ) -> None:
        """
        Configure and start continuous integrated beam data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        self.integrated_beam_configuration = {
            "integration_time": integration_time,
            "first_channel": first_channel,
            "last_channel": last_channel,
            "current_channel": first_channel,
        }

    @check_mocked_overheating
    @connected
    def stop_integrated_data(self: TileSimulator) -> None:
        """Stop integrated data."""
        self.integrated_channel_configuration["integration_time"] = -1
        self.integrated_beam_configuration["integration_time"] = -1

    @check_mocked_overheating
    @connected
    def send_raw_data(
        self: TileSimulator,
        sync: bool | None = False,
        timestamp: int | None = None,
        seconds: float | None = 0.2,
        fpga_id: int | None = None,
    ) -> None:
        """
        Send raw data.

        :param sync: true to sync
        :param timestamp: timestamp
        :param seconds: When to synchronise
        :param fpga_id: Specify which FPGA should transmit, 0,1,
            or None for both FPGAs
        """
        # TODO: This does not send raw SPEAD packets but sends Integrated channel data.
        # Should we create a raw data SPEAD packet generator?
        # Should the data created be meaningful? to what extent?
        # (delay, attenuation, random)
        self.stop_data_transmission()
        if not self.dst_ip:
            _dst_ip: str = ""
        if not self.dst_port:
            _dst_port: int = 8080
        _dst_ip = self.dst_ip or _dst_ip
        _dst_port = self.dst_port or _dst_port
        self.spead_data_simulator.set_destination_ip(_dst_ip, _dst_port)
        self.spead_data_simulator.send_raw_data(1)

    @check_mocked_overheating
    @connected
    def send_channelised_data(
        self: TileSimulator,
        number_of_samples: int = 1024,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: int | None = None,
        seconds: float = 0.4,
    ) -> None:
        """
        Send channelised data from the TPM.

        :param number_of_samples: Number of spectra to send
        :param first_channel: First channel to send
        :param last_channel: Last channel to send
        :param timestamp: When to start transmission
        :param seconds: When to synchronise
        """
        # Check if number of samples is a multiple of 32

        # if number_of_samples % 32 != 0:
        #     new_value = (int(number_of_samples / 32) + 1) * 32
        #     self.logger.warning(
        #         f"{number_of_samples} is not a multiple of 32, using {new_value}"
        #     )
        #     number_of_samples = new_value
        self.stop_data_transmission()

        if not self.dst_ip:
            _dst_ip: str = ""
        if not self.dst_port:
            _dst_port: int = 8080
        _dst_ip = self.dst_ip or _dst_ip
        _dst_port = self.dst_port or _dst_port
        self.spead_data_simulator.set_destination_ip(_dst_ip, _dst_port)
        self.spead_data_simulator.send_channelised_data(
            1, number_of_samples, first_channel, last_channel
        )

    @check_mocked_overheating
    @connected
    def send_channelised_data_continuous(
        self: TileSimulator,
        channel_id: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: int | None = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Continuously send channelised data from a single channel.

        :param channel_id: Channel ID
        :param number_of_samples: Number of spectra to send
        :param wait_seconds: Wait time before sending data
        :param timestamp: When to start
        :param seconds: When to synchronise
        """
        self._pending_data_requests = True

    @check_mocked_overheating
    @connected
    def send_channelised_data_narrowband(
        self: TileSimulator,
        frequency: float,
        round_bits: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: int | None = None,
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
        """
        self.logger.error(
            "send_channelised_data_narrowband not implemented in simulator"
        )

    @check_mocked_overheating
    @connected
    def send_beam_data(
        self: TileSimulator,
        timeout: int = 0,
        timestamp: int | None = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send beam data.

        :param timeout: timeout
        :param timestamp: timestamp
        :param seconds: When to synchronise
        """
        self.logger.error("send_beam_data not implemented in simulator")

    @check_mocked_overheating
    @connected
    def stop_data_transmission(self: TileSimulator) -> None:
        """Stop data transmission."""
        self.spead_data_simulator.stop_sending_data()
        self._pending_data_requests = False

    @check_mocked_overheating
    @connected
    def start_acquisition(
        self: TileSimulator,
        start_time: int | None = None,
        delay: int = 2,
        global_start_time: int | None = None,
    ) -> None:
        """
        Start data acquisition.

        :param start_time: Time for starting (frames)
        :param delay: delay after start_time (frames)
        :param global_start_time: TPM will act as if it is
            started at this time (seconds)
        """
        # if global start time is set, either in parameter or in attribute,
        # use it as sync time
        if global_start_time:
            sync_time = global_start_time
        elif start_time is None:
            sync_time = int(time.time()) + delay
        else:
            sync_time = start_time + delay

        self.sync_time = sync_time  # type: ignore
        self.tpm["fpga1.pps_manager.sync_time_val"] = sync_time  # type: ignore

    @check_mocked_overheating
    @connected
    def set_lmc_integrated_download(
        self: TileSimulator,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: str | None = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
        netmask_40g: int | None = None,
        gateway_ip_40g: int | None = None,
    ) -> None:
        """
        Configure link and size of control data for integrated LMC packets.

        :param mode: '1G' or '10G'
        :param channel_payload_length: SPEAD payload length for integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated beam data
        :param dst_ip: Destination IP
        :param src_port: Source port for integrated data streams
        :param dst_port: Destination port for integrated data streams
        :param netmask_40g: the mask to apply to the 40g.
        :param gateway_ip_40g: the gateway ip for the 40g.
        """
        self.logger.error("set_lmc_integrated_download not implemented in simulator")

    @check_mocked_overheating
    @connected
    def test_generator_set_tone(
        self: TileSimulator,
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
        """
        self.logger.error("test_generator_set_tone not implemented in simulator")

    @check_mocked_overheating
    @connected
    def test_generator_set_noise(
        self: TileSimulator, amplitude_noise: float = 0.0, load_time: int = 0
    ) -> None:
        """
        Set generator test noise.

        :param amplitude_noise: amplitude of noise
        :param load_time: load time
        """
        self.logger.error("test_generator_set_noise not implemented in simulator")

    @check_mocked_overheating
    @connected
    def set_test_generator_pulse(
        self: TileSimulator, freq_code: int, amplitude: float = 0.0
    ) -> None:
        """
        Set test generator pulse.

        :param freq_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude: Tone peak amplitude,
            normalized to 127.5 ADC units, resolution 0.5 ADU
        """
        self.logger.error("set_test_generator_pulse not implemented in simulator")

    @check_mocked_overheating
    @connected
    def get_fpga_timestamp(self: TileSimulator, device: Device = Device.FPGA_1) -> int:
        """
        Get timestamp from FPGA.

        :param device: device.

        :return: the simulated timestamp.

        :raises LibraryError: Invalid device specified
        """
        try:
            return self._timestamp
        except Exception as e:
            raise LibraryError("Invalid device specified") from e

    @check_mocked_overheating
    @connected
    def test_generator_input_select(self: TileSimulator, inputs: int) -> None:
        """
        Test generator input select.

        :param inputs: inputs
        """
        self.logger.error("test_generator_input_select not implemented in simulator")

    @check_mocked_overheating
    @connected
    def set_pattern(
        self: TileSimulator,
        stage: str,
        pattern: list[int],
        adders: list[int],
        start: bool,
        shift: int = 0,
        zero: int = 0,
    ) -> None:
        """
        Configure the TPM pattern generator.

        :param stage: The stage in the signal chain where the pattern is injected.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer) or 'all' for all stages.
        :param pattern: The data pattern in time order. This must be a list of integers
            with a length between 1 and 1024. The pattern represents values
            in time order (not antennas or polarizations).
        :param adders: A list of 32 integers that expands the pattern to cover 16
            antennas and 2 polarizations in hardware. This list maps the pattern to the
            corresponding signals for the antennas and polarizations.
        :param start: Boolean flag indicating whether to start the pattern immediately.
            If False, the pattern will need to be started manually later.
        :param shift: Optional bit shift (divides the pattern by 2^shift). This must not
            be used in the 'beamf' stage, where it is always overridden to 4.
            The default value is 0.
        :param zero: An integer (0-65535) used as a mask to disable the pattern on
            specific antennas and polarizations. The same mask is applied to both FPGAs,
            supporting up to 8 antennas and 2 polarizations. The default value is 0.
        """
        self.logger.info(f"Setting pattern generator on stage: {stage}")
        self.logger.debug(f"Pattern: {pattern}")
        self.logger.debug(f"Adders: {adders}")
        self.logger.debug(f"Start: {start}")
        self.logger.debug(f"Shift: {shift}")
        self.logger.debug(f"Zero: {zero}")
        self.logger.error("set_pattern not implemented in simulator yet.")

    @check_mocked_overheating
    @connected
    def start_pattern(self: TileSimulator, stage: str) -> None:
        """
        Start the pattern generator at the specified stage.

        :param stage: The stage in the signal chain where the pattern should be started.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer), or 'all' for all stages.
        """
        self.logger.info(f"Starting pattern generator on stage: {stage}")
        self.logger.error("start_pattern not implemented in simulator yet.")

    @check_mocked_overheating
    @connected
    def stop_pattern(self: TileSimulator, stage: str) -> None:
        """
        Stop the pattern generator at the specified stage.

        :param stage: The stage in the signal chain where the pattern should be stopped.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer), or 'all' for all stages.
        """
        self.logger.info(f"Stopping pattern generator on stage: {stage}")
        self.logger.error("stop_pattern not fully implemented in simulator yet.")

    def _timed_thread(self: TileSimulator) -> None:
        """Thread to update time related registers."""
        while True:
            self._start_polling_event.wait()
            time_utc = time.time()
            _fpgatime = int(time_utc)
            if self.sync_time > 0 and self.sync_time < time_utc:
                self._timestamp = int((time_utc - self.sync_time) / (256 * 1.08e-6))
                reg1 = "fpga1.dsp_regfile.stream_status.channelizer_vld"
                reg2 = "fpga2.dsp_regfile.stream_status.channelizer_vld"
                if self.tpm:
                    self.tpm[reg1] = 1
                    self.tpm[reg2] = 1
            self.fpgas_time[0] = _fpgatime
            self.fpgas_time[1] = _fpgatime
            time.sleep(0.1)

    @check_mocked_overheating
    @connected
    def get_arp_table(self: TileSimulator) -> dict[int, list[int]]:
        """
        Get arp table.

        :return: the app table
        """
        return {0: [0, 1], 1: [1]}

    @check_mocked_overheating
    @connected
    def load_beam_angle(self: TileSimulator, angle_coefficients: list[float]) -> None:
        """
        Load beam angle.

        :param angle_coefficients: angle coefficients.
        """
        self.logger.error("load_beam_angle not implemented in simulator")

    @check_mocked_overheating
    @connected
    def load_antenna_tapering(
        self: TileSimulator, beam: int, tapering_coefficients: list[int]
    ) -> None:
        """
        Load antenna tapering.

        :param beam: beam
        :param tapering_coefficients: tapering coefficients
        """
        self.logger.error("load_antenna_tapering not implemented in simulator")

    @check_mocked_overheating
    @connected
    def compute_calibration_coefficients(self: TileSimulator) -> None:
        """Compute calibration coefficients."""
        self.logger.error(
            "compute_calibration_coefficients not implemented in simulator"
        )

    @check_mocked_overheating
    @connected
    def beamformer_is_running(
        self: TileSimulator,
        mask: bool | None = None,
        subarray_beam: int | None = None,
        channel_groups: list[int] | None = None,
    ) -> bool:
        """
        Beamformer is running.

        :param mask: Bitmask of the channels to be started.
            Ignored if beam is specified.
        :param subarray_beam: subarray beam number to start.
            Computes the mask using beam table
        :param channel_groups: list of channel groups, in range 0:48.
            group 0 for channels 0-7, to group 47 for channels 380-383.

        :return: is the beam is running
        """
        return (
            self.tpm.beam1.is_running()  # type: ignore
            and self.tpm.beam2.is_running()  # type: ignore
        )

    def set_tpm_temperature_thresholds(
        self: TileSimulator,
        board_alarm_threshold: tuple[float, float] | None = None,
        fpga1_alarm_threshold: tuple[float, float] | None = None,
        fpga2_alarm_threshold: tuple[float, float] | None = None,
    ) -> None:
        """
        Set the temperature thresholds.

        NOTE: Warning this method can configure the shutdown temperature of
        components and must be used with care. This method is capped to a minimum
        of 20 and maximum of 50 (unit: Degree Celsius). And is ONLY supported in tpm1_6.

        :param board_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the board (unit: Degree Celsius)
        :param fpga1_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the fpga1 (unit: Degree Celsius)
        :param fpga2_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the fpga2 (unit: Degree Celsius)

        :raises ValueError: is the value set is not in the set range.
        """

        def _is_in_range_20_50(value: float) -> bool:
            """
            Return True if value is larger than 20 and less than 50.

            :param value: value under test

            :return: True when test value in range.
            """
            min_settable = 20
            max_settable = 50
            if min_settable <= value <= max_settable:
                return True
            return False

        if board_alarm_threshold is not None:
            if _is_in_range_20_50(board_alarm_threshold[0]) and _is_in_range_20_50(
                board_alarm_threshold[1]
            ):
                self._tpm_temperature_thresholds[
                    "board_alarm_threshold"
                ] = board_alarm_threshold
            else:
                raise ValueError(
                    f"{board_alarm_threshold=} not in capped range 20-50. Doing nothing"
                )
        if fpga1_alarm_threshold is not None:
            if _is_in_range_20_50(fpga1_alarm_threshold[0]) and _is_in_range_20_50(
                fpga1_alarm_threshold[1]
            ):
                self._tpm_temperature_thresholds[
                    "fpga1_alarm_threshold"
                ] = fpga1_alarm_threshold
            else:
                raise ValueError(
                    f"{fpga1_alarm_threshold=} not in capped range 20-50. Doing nothing"
                )
        if fpga2_alarm_threshold is not None:
            if _is_in_range_20_50(fpga2_alarm_threshold[0]) and _is_in_range_20_50(
                fpga2_alarm_threshold[1]
            ):
                self._tpm_temperature_thresholds[
                    "fpga2_alarm_threshold"
                ] = fpga2_alarm_threshold
            else:
                raise ValueError(
                    f"{fpga2_alarm_threshold=} not in capped range 20-50. Doing nothing"
                )
        self.evaluate_mcu_action()

    def evaluate_mcu_action(self: TileSimulator) -> None:
        """
        Evaluate thresholds to temperatures.

        In the case of overheating, we will mock the action of the
        MCU (micro controller unit).
        """
        if (
            self._tile_health_structure["temperatures"]["board"]
            > self._tpm_temperature_thresholds["board_alarm_threshold"][1]
            or self._tile_health_structure["temperatures"]["FPGA0"]
            > self._tpm_temperature_thresholds["fpga1_alarm_threshold"][1]
            or self._tile_health_structure["temperatures"]["FPGA1"]
            > self._tpm_temperature_thresholds["fpga2_alarm_threshold"][1]
        ):
            self.logger.warning(
                "We are overheating, CPLD is turning the overheating components OFF!"
            )
            self._tile_health_structure["alarms"]["temperature_alm"] = 2
            self._global_status_alarms["temperature_alm"] = 2
            self._is_fpga1_connectable = False
            self._is_fpga2_connectable = False
            self.tpm_mocked_overheating = True
        else:
            self._tile_health_structure["alarms"]["temperature_alm"] = 0
            self._global_status_alarms["temperature_alm"] = 0
            self.tpm_mocked_overheating = False
            self._is_fpga1_connectable = True
            self._is_fpga2_connectable = True

    def check_communication(self: TileSimulator) -> dict[str, bool]:
        """
        Return status of connection to TPM CPLD and FPGAs.

        :example:

        >> OK Status:
          {'CPLD': True, 'FPGA0': True, 'FPGA1': True}
        >> TPM ON, FPGAs not programmed or TPM overtemperature self shutdown:
          {'CPLD': True, 'FPGA0': False, 'FPGA1': False}
        >> TPM OFF or Network Issue:
          {'CPLD': False, 'FPGA0': False, 'FPGA1': False}

        :return: a dictionary with the key communication information.
        """
        return {
            "CPLD": self._is_cpld_connectable,
            "FPGA0": self._is_fpga1_connectable,
            "FPGA1": self._is_fpga2_connectable,
        }

    @check_mocked_overheating
    @connected
    def get_phase_terminal_count(self: TileSimulator) -> int:
        """
        Get PPS phase terminal count.

        :return: the simulated phase terminal count.
        """
        return self._phase_terminal_count

    @check_mocked_overheating
    @connected
    def get_station_id(self: TileSimulator) -> int:
        """
        Get station ID.

        :return: station ID programmed in HW
        :rtype: int
        """
        return self._station_id

    @check_mocked_overheating
    @connected
    def set_preadu_levels(self: TileSimulator, levels: list[float]) -> None:
        """
        Set preADU attenuation levels.

        :param levels: Desired attenuation levels for each ADC channel, in dB.
        """
        assert len(levels) == 32
        assert self.tpm  # for mypy
        for adc_channel, level in enumerate(levels):
            preadu_id, preadu_ch = divmod(adc_channel, 16)
            self.tpm.preadu[preadu_id].set_attenuation(level, [preadu_ch])

    @check_mocked_overheating
    @connected
    def get_preadu_levels(self: TileSimulator) -> list[float]:
        """
        Get preADU attenuation levels.

        :return: Attenuation levels corresponding to each ADC channel, in dB.
        """
        assert self.tpm  # for mypy
        levels = []
        for adc_channel in range(32):
            preadu_id, preadu_ch = divmod(adc_channel, 16)
            attenuation = self.tpm.preadu[preadu_id].get_attenuation()[preadu_ch]
            levels.append(attenuation)
        return levels

    def set_spead_format(self, ska_spead_header_format: bool) -> None:
        """
        Set CSP SPEAD format.

        :param ska_spead_header_format: True for new (SKA) format, False for old (AAVS)
        """
        spead_format = "AAVS"
        if ska_spead_header_format:
            spead_format = "SKA"
        self.csp_spead_format = spead_format

    @property
    def ska_spead_header(self) -> bool:
        """
        Return format of the CSP Spead header.

        :return: True for new new (SKA) format, False for old (AAVS)
        """
        return self.csp_spead_format == "SKA"

    def read_broadband_rfi(self, antennas: range = range(16)) -> np.ndarray:
        """
        Read out the broadband RFI counters.

        :param antennas: list antennas of which rfi counters to read

        :return: rfi counters
        """
        return self._rfi_count[np.array(antennas)]

    @check_mocked_overheating
    @connected
    def __getattr__(self: TileSimulator, name: str) -> Any:
        """
        Get the attribute.

        :param name: name of the requested attribute
        :type name: str

        :raises AttributeError: if neither this class nor the TPM has
            the named attribute.

        :return: the requested attribute
        """
        if self.tpm:
            return getattr(self.tpm, name)
        else:
            raise AttributeError("'Tile' or 'TPM' object have no attribute " + name)

    def __str__(self: TileSimulator) -> str:
        """
        Produce a list of tile information.

        :return: Information string
        :rtype: str
        """
        if self.tpm is None:
            return ""
        info: dict[str, Any] = self.tpm.info
        return (
            f"\nTile Processing Module {info['hardware']['HARDWARE_REV']} "
            f"Serial Number: {info['hardware']['SN']} \n"
            f"{'_'*90} \n"
            f"{' '*29}| \n"
            f"Classification               | "
            f"{info['hardware']['PN']}-{info['hardware']['BOARD_MODE']} \n"
            f"Hardware Revision            | {info['hardware']['HARDWARE_REV']} \n"
            f"Serial Number                | {info['hardware']['SN']} \n"
            f"BIOS Revision                | {info['hardware']['bios']} \n"
            f"Board Location               | {info['hardware']['LOCATION']} \n"
            f"DDR Memory Capacity          | {info['hardware']['DDR_SIZE_GB']} "
            f"GB per FPGA \n"
            f"{'_'*29}|{'_'*60} \n"
            f"{' '*29}| \n"
            f"FPGA Firmware Design         | {info['fpga_firmware']['design']} \n"
            f"FPGA Firmware Revision       | {info['fpga_firmware']['build']} \n"
            f"FPGA Firmware Compile Time   | {info['fpga_firmware']['compile_time']} "
            f"UTC \n"
            f"FPGA Firmware Compile User   | {info['fpga_firmware']['compile_user']} "
            f" \n"
            f"FPGA Firmware Compile Host   | {info['fpga_firmware']['compile_host']} \n"
            f"FPGA Firmware Git Branch     | {info['fpga_firmware']['git_branch']} \n"
            f"FPGA Firmware Git Commit     | {info['fpga_firmware']['git_commit']} \n"
            f"{'_'*29}|{'_'*60} \n"
            f"{' '*29}| \n"
            f"1G (MGMT) IP Address         | {str(info['network']['1g_ip_address'])} \n"
            f"1G (MGMT) MAC Address        | {info['network']['1g_mac_address']} \n"
            f"1G (MGMT) Netmask            | {str(info['network']['1g_netmask'])} \n"
            f"1G (MGMT) Gateway IP         | {str(info['network']['1g_gateway'])} \n"
            f"EEP IP Address               | {str(info['hardware']['ip_address_eep'])}"
            f" \n"
            f"EEP Netmask                  | {str(info['hardware']['netmask_eep'])} \n"
            f"EEP Gateway IP               | {str(info['hardware']['gateway_eep'])} \n"
            f"40G Port 1 IP Address        | "
            f"{str(info['network']['40g_ip_address_p1'])} \n"
            f"40G Port 1 MAC Address       | "
            f"{str(info['network']['40g_mac_address_p1'])} \n"
            f"40G Port 1 Netmask           | {str(info['network']['40g_netmask_p1'])}"
            f" \n"
            f"40G Port 1 Gateway IP        | {str(info['network']['40g_gateway_p1'])}"
            f" \n"
            f"40G Port 2 IP Address        | "
            f"{str(info['network']['40g_ip_address_p2'])} \n"
            f"40G Port 2 MAC Address       | "
            f"{str(info['network']['40g_mac_address_p2'])} \n"
            f"40G Port 2 Netmask           | {str(info['network']['40g_netmask_p2'])}"
            f" \n"
            f"40G Port 2 Gateway IP        | {str(info['network']['40g_gateway_p2'])}"
            f" \n"
        )


class DynamicTileSimulator(TileSimulator):
    """A simulator for a TPM, with dynamic value updates to certain attributes."""

    def __init__(self: DynamicTileSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new Dynamic Tile simulator instance.

        :param logger: a logger for this simulator to use
        """
        super().__init__(logger)
        self._voltage: float | None = None
        self._current: float | None = None
        self._board_temperature: float | None = None
        self._fpga1_temperature: float | None = None
        self._fpga2_temperature: float | None = None

        self._updater = DynamicValuesUpdater(1.0)
        self._updater.add_target(
            DynamicValuesGenerator(4.9, 5.1), self._voltage_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(0.05, 2.95), self._current_changed
        )
        self._updater.add_target(
            DynamicValuesGenerator(30.0, 47.0),
            self._board_temperature_changed,
        )
        self._updater.add_target(
            DynamicValuesGenerator(30.0, 47.0),
            self._fpga1_temperature_changed,
        )
        self._updater.add_target(
            DynamicValuesGenerator(30.0, 47.0),
            self._fpga2_temperature_changed,
        )
        self._updater.add_target(self.random_antenna_generator(), self._rfi_changed)
        self._updater.start()

    def __del__(self: DynamicTileSimulator) -> None:
        """Garbage-collection hook."""
        self._updater.stop()

    def get_board_temperature(self: DynamicTileSimulator) -> float | None:
        """:return: the mocked board temperature."""
        return self._board_temperature

    @property
    def board_temperature(self: DynamicTileSimulator) -> float | None:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        assert self._board_temperature is not None  # for the type checker
        return self._board_temperature

    def _board_temperature_changed(
        self: DynamicTileSimulator, board_temperature: float
    ) -> None:
        """
        Call this method when the board temperature changes.

        :param board_temperature: the new board temperature
        """
        self._board_temperature = board_temperature
        self._tile_health_structure["temperatures"]["board"] = board_temperature

    def get_voltage(self: DynamicTileSimulator) -> float | None:
        """:return: the mocked voltage."""
        return self._voltage

    @property
    def voltage(self: DynamicTileSimulator) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        assert self._voltage is not None  # for the type checker
        return self._voltage

    def _voltage_changed(self: DynamicTileSimulator, voltage: float) -> None:
        """
        Call this method when the voltage changes.

        :param voltage: the new voltage
        """
        self._voltage = voltage
        self._tile_health_structure["voltages"]["MON_5V0"] = voltage

    def get_current(self: DynamicTileSimulator) -> float | None:
        """:return: the mocked current."""
        return self._current

    @property
    def current(self: DynamicTileSimulator) -> float:
        """
        Return the current of the TPM.

        :return: the current of the TPM
        """
        assert self._current is not None  # for the type checker
        return self._current

    def _current_changed(self: DynamicTileSimulator, current: float) -> None:
        """
        Call this method when the current changes.

        :param current: the new current
        """
        self._current = current

    @connected
    def get_fpga0_temperature(self: DynamicTileSimulator) -> float | None:
        """:return: the mocked fpga0 temperature."""
        return self._fpga1_temperature

    @property
    def fpga1_temperature(self: DynamicTileSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        assert self._fpga1_temperature is not None  # for the type checker
        return self._fpga1_temperature

    def _fpga1_temperature_changed(
        self: DynamicTileSimulator, fpga1_temperature: float
    ) -> None:
        """
        Call this method when the FPGA1 temperature changes.

        :param fpga1_temperature: the new FPGA1 temperature
        """
        self._fpga1_temperature = fpga1_temperature
        self._tile_health_structure["temperatures"]["FPGA0"] = fpga1_temperature

    @connected
    def get_fpga1_temperature(self: DynamicTileSimulator) -> float | None:
        """:return: the mocked fpga1 temperature."""
        return self._fpga2_temperature

    @property
    def fpga2_temperature(self: DynamicTileSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        assert self._fpga2_temperature is not None  # for the type checker
        return self._fpga2_temperature

    def _fpga2_temperature_changed(
        self: DynamicTileSimulator, fpga2_temperature: float
    ) -> None:
        """
        Call this method when the FPGA2 temperature changes.

        :param fpga2_temperature: the new FPGA2 temperature
        """
        self._fpga2_temperature = fpga2_temperature
        self._tile_health_structure["temperatures"]["FPGA1"] = fpga2_temperature

    def _rfi_changed(
        self: DynamicTileSimulator, antenna_incremented: tuple[int, int]
    ) -> None:
        """
        Call this method when the RFI count increments.

        :param antenna_incremented: which antenna/pol got RFI.
        """
        self._rfi_count[antenna_incremented[0]][antenna_incremented[1]] += 1

    @classmethod
    def random_antenna_generator(cls) -> Generator[tuple[int, int]]:
        """
        Generate a random antenna/pol number.

        :yields: a random antenna/pol number.
        """
        while True:
            yield (
                random.randint(0, TileData.ANTENNA_COUNT - 1),
                random.randint(0, TileData.POLS_PER_ANTENNA - 1),
            )
