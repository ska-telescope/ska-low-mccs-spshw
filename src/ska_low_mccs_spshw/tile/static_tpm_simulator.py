#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import logging
import re
from typing import Any, Callable, Optional

from pyfabil.base.definitions import LibraryError

from ska_low_mccs_spshw.tile.base_tpm_simulator import BaseTpmSimulator


class StaticTpmSimulator(BaseTpmSimulator):
    """A simulator for a TPM."""

    VOLTAGE = 5.0
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(
        self: StaticTpmSimulator,
        logger: logging.Logger,
        component_state_changed_callback: Optional[
            Callable[[dict[str, Any]], None]
        ] = None,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._voltage: float = self.VOLTAGE
        self._current: float = self.CURRENT
        self._board_temperature: float = self.BOARD_TEMPERATURE
        self._fpga1_temperature: float = self.FPGA1_TEMPERATURE
        self._fpga2_temperature: float = self.FPGA2_TEMPERATURE

        super().__init__(logger, component_state_changed_callback)

    @property
    def board_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        return self._board_temperature

    @property
    def voltage(self: StaticTpmSimulator) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        return self._voltage

    @property
    def current(self: StaticTpmSimulator) -> float:
        """
        Return the current of the TPM.

        :return: the current of the TPM
        """
        return self._current

    @property
    def fpga1_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        return self._fpga2_temperature


class StaticTpmSimulatorPatchedReadWrite(BaseTpmSimulator):
    """
    This attempts to simulate pyfabil TPM.

    This is used for testing the tpm_driver, it implements
    __getitem__, __setitem__ so that the TileSimulator can
    interface with the TPMSimulator in the same way as the
    AAVS Tile interfaces with the pyfabil TPM. Instead of writing to
    a register we write to a dictionary. It overwrite read_address,
    write_address, read_register, write_register for simplicity.

    The reason for this class is that the BaseTPMSimulator does not
    have the same interface as the pyfabil TPM, so a subclass has
    wrapped this to give that interface needed for testing tpm_driver.
    """

    def __init__(
        self: StaticTpmSimulatorPatchedReadWrite,
        logger: logging.Logger,
        component_state_changed_callback: Optional[
            Callable[[dict[str, Any]], None]
        ] = None,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        super().__init__(logger, component_state_changed_callback)

    # pylint: disable=arguments-renamed
    def write_register(
        self: StaticTpmSimulatorPatchedReadWrite, address: str, values: list[int]
    ) -> None:
        """
        Write a integer value to a given register.

        :param address: register to write
        :param values: values to write
        """
        self._register_map.update({address: values})

    # pylint: disable=arguments-renamed
    def read_register(
        self: StaticTpmSimulatorPatchedReadWrite, address: str
    ) -> list[int]:
        """
        Read a value at a given register.

        :param address: address of start of read

        :return: values at the address
        """
        return self._register_map.get(str(address), [])

    def find_register(
        self: StaticTpmSimulatorPatchedReadWrite, address: int
    ) -> list[Any]:
        """
        Find a item in a dictionary.

        This is mocking the reading of a register for the purpose of
        testing TPM_driver

        :param address: address of start of read

        :return: registers found at address
        """
        matches = []
        for k, v in self._register_map.items():
            if isinstance(k, int):
                pass
            elif re.search(str(address), k) is not None:
                matches.append(v)
        return matches

    def __getitem__(
        self: StaticTpmSimulatorPatchedReadWrite, key: int
    ) -> Any | LibraryError:
        """
        Check if the specified key is a memory address or register name.

        :param key: the key to a register.

        :return: the value at the mocked register

        :raises LibraryError: Attempting to get a register not in the memory address.
        """
        if isinstance(key, int):
            return self.read_address(key)

        if isinstance(key, str):
            # Check if a device is specified in the register name
            return self.read_register(key)
        raise LibraryError("must be register name, memory address or SPI device tuple")
        # Register not found
        # raise LibraryError(f"Register {key} not found")

    def __setitem__(
        self: StaticTpmSimulatorPatchedReadWrite, key: int | str, value: Any
    ) -> None:
        """
        Check if the specified key is a memory address or register name.

        This calls either write register or write address depending whether
        the key is a int or a str.

        :param key: the key to a register.
        :param value: the value to write in register.

        :raises LibraryError:Attempting to set a register not in the memory address.

        :return:none
        """
        if isinstance(key, int):
            self.write_address(key, value)
            return

        if isinstance(key, str):
            # Check if device is specified in the register name
            self.write_register(key, value)
            return
        raise LibraryError(f"Unrecognised key type {key.__class__.__name__}")


class StaticTileSimulator(StaticTpmSimulator):
    """
    A simulator for a AAVS Tile.

    A AAVS Tile simulator. Allows for testing of the tpm_driver against a
    simulated Tile with the same interface as the AAVS Tile.

    The connect method constructs a TPM instead of forming a UDP connection for
    simplicity.
    """

    # this is just mocked with some dummy information.
    FIRMWARE_LIST = [
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test1", "major": 2, "minor": 1, "build": 1, "time": "4"},
    ]

    def __init__(self: StaticTileSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new Tile simulator instance.

        :param logger: a logger for this simulator to use
        """
        self.firmware_list = self.FIRMWARE_LIST
        self.memory_map: dict[str, Any] = {}
        self.tpm = None
        self.logger = logger
        self.fpga_time = 2
        self.attributes: dict[str, Any] = {}
        super().__init__(logger)

    def get_fpga0_temperature(self: StaticTileSimulator) -> float:
        """:return: the mocked fpga0 temperature."""
        assert self.tpm  # for the type checker
        return self.tpm.fpga1_temperature

    def get_fpga1_temperature(self: StaticTileSimulator) -> float:
        """:return: the mocked fpga1 temperature."""
        assert self.tpm  # for the type checker
        return self.tpm.fpga2_temperature

    def get_temperature(self: StaticTileSimulator) -> float:
        """:return: the mocked board temperature."""
        assert self.tpm  # for the type checker
        return self.tpm.board_temperature

    def get_voltage(self: StaticTileSimulator) -> float:
        """:return: the mocked voltage."""
        assert self.tpm  # for the type checker
        return self.tpm.voltage

    def get_tile_id(self: StaticTileSimulator) -> int:
        """:return: the mocked tile_id."""
        assert self.tpm  # for the type checker
        return self.tpm.tile_id

    def initialise_beamformer(
        self: StaticTileSimulator,
        start_channel: float,
        nof_channels: int,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Mock set the beamformer parameters.

        :param start_channel: start_channel
        :param nof_channels: nof_channels
        :param is_first: unused
        :param is_last: unused
        """
        self.attributes.update({"start_channel": start_channel})
        self.attributes.update({"nof_channels": nof_channels})

    def get_firmware_list(self: StaticTileSimulator) -> list[dict]:
        """
        Return the list of firmaware available.

        :return: the firmware list.
        """
        return self.firmware_list

    def program_fpgas(self: StaticTileSimulator, firmware_name: str) -> None:
        """
        Mock programmed state to True.

        :param firmware_name: firmware_name
        """
        assert self.tpm  # for the type checker
        self.tpm._is_programmed = True

    def set_station_id(
        self: StaticTileSimulator, tile_id: int, station_id: int
    ) -> None:
        """
        Set mock registers to some value.

        :param tile_id: tile_id
        :param station_id: station_id
        """
        fpgas = ["fpga1", "fpga2"]
        for f in fpgas:
            self[f + ".dsp_regfile.config_id.station_id"] = station_id
            self[f + ".dsp_regfile.config_id.tpm_id"] = tile_id

    def get_adc_rms(self: StaticTileSimulator) -> tuple[tuple[float]]:
        """:return: the adc_rms."""
        assert self.tpm  # for the type checker
        return self.tpm.adc_rms

    def get_fpga_time(self: StaticTileSimulator, device: str) -> float:
        """
        :param device: device.

        :return: the fpga_time.
        """
        return self.fpga_time

    def get_pps_delay(self: StaticTileSimulator) -> float:
        """:return: the pps delay."""
        assert self.tpm  # for the type checker
        return self.tpm._pps_delay

    @property
    def is_programmed(self: StaticTileSimulator) -> bool:
        """
        Return whether the mock has been implemented.

        :return: the mocked programmed state
        """
        assert self.tpm  # for the type checker
        return self.tpm.is_programmed

    def get_40g_core_configuration(
        self: StaticTileSimulator,
        core_id: int = -1,
        arp_table_entry: int = 0,
    ) -> dict | list[dict] | None:
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
            if (
                item.get("core_id") == core_id
                and item.get("arp_table_entry") == arp_table_entry
            ):

                return item
        return None

    def check_arp_table(self: StaticTileSimulator) -> NotImplementedError:
        """
        Not Implemented.

        :raises NotImplementedError: if not overwritten
        """
        raise NotImplementedError

    def reset_eth_errors(self: StaticTileSimulator) -> None:
        """Not Implemented."""

    def connect(self: StaticTileSimulator) -> None:
        """Fake a connection by constructing the TPM."""
        self.tpm = StaticTpmSimulatorPatchedReadWrite(
            self.logger
        )  # type: ignore[assignment]
        self[int(0x30000000)] = [3, 7]

    def __getitem__(self: StaticTileSimulator, key: int | str) -> Any:
        """
        Get the register from the TPM.

        :param key: key
        :return: mocked item at address
        """
        assert self.tpm  # for the type checker
        return self.tpm[key]

    def __setitem__(self: StaticTileSimulator, key: int | str, value: Any) -> None:
        """
        Set a registers value in the TPM.

        :param key: key
        :param value: value
        """
        assert self.tpm  # for the type checker
        self.tpm[key] = value

    def __getattr__(self: StaticTileSimulator, name: str) -> Any | AttributeError:
        """
        Get the attribute from the tpm if not found here.

        :param name: name of the attribute
        :return: the attribute
        :raises AttributeError: if not found
        """
        if name in dir(self.tpm):
            return getattr(self.tpm, name)
        raise AttributeError(f"TPM object has no attribute: {name}")
