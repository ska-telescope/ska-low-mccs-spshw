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

from .base_tpm_simulator import BaseTpmSimulator


class StaticTpmSimulator(BaseTpmSimulator):
    """A simulator for a TPM."""

    VOLTAGE = 5.0
    CURRENT_FE0_mVA = 0.4
    CURRENT_FE1_mVA = 0.45
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(
        self: StaticTpmSimulator,
        logger: logging.Logger,
        component_state_changed_callback: Optional[Callable[..., None]] = None,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        super().__init__(logger, component_state_changed_callback)

        self._tile_health_structure["voltages"]["MON_5V0"] = self.VOLTAGE
        self._tile_health_structure["currents"]["FE0_mVA"] = self.CURRENT_FE0_mVA
        self._tile_health_structure["currents"]["FE1_mVA"] = self.CURRENT_FE1_mVA
        self._tile_health_structure["temperatures"]["board"] = self.BOARD_TEMPERATURE
        self._tile_health_structure["temperatures"]["FPGA0"] = self.FPGA1_TEMPERATURE
        self._tile_health_structure["temperatures"]["FPGA1"] = self.FPGA2_TEMPERATURE

    @property
    def board_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        return self._tile_health_structure["temperatures"]["board"]

    @property
    def voltage_mon(self: StaticTpmSimulator) -> float:
        """
        Return the internal 5V supply of the TPM.

        :return: the internal 5V supply of the TPM
        """
        return self._tile_health_structure["voltages"]["MON_5V0"]

    @property
    def currents(self: StaticTpmSimulator) -> dict[str, Any]:
        """
        Return a dictionary of all current values available in the TPM.

        :return: currents in the TPM
        """
        return self._tile_health_structure["currents"]

    @property
    def fpga1_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        return self._tile_health_structure["temperatures"]["FPGA0"]

    @property
    def fpga2_temperature(self: StaticTpmSimulator) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        return self._tile_health_structure["temperatures"]["FPGA1"]


class StaticTpmSimulatorPatchedReadWrite(BaseTpmSimulator):
    """
    This attempts to simulate pyfabil TPM.

    This is used for testing the tpm_driver, it implements __getitem__,
    __setitem__ so that the TileSimulator can interface with the
    TPMSimulator in the same way as the AAVS Tile interfaces with the
    pyfabil TPM. Instead of writing to a register we write to a
    dictionary. It overwrite read_address, write_address, read_register,
    write_register for simplicity.

    The reason for this class is that the BaseTPMSimulator does not have
    the same interface as the pyfabil TPM, so a subclass has wrapped
    this to give that interface needed for testing tpm_driver.
    """

    def __init__(
        self: StaticTpmSimulatorPatchedReadWrite,
        logger: logging.Logger,
        component_state_changed_callback: Optional[Callable[..., None]] = None,
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
        self: StaticTpmSimulatorPatchedReadWrite, address: int | str
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
        self: StaticTpmSimulatorPatchedReadWrite, key: int | str
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
