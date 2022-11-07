# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import logging

from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator


class StaticTpmSimulator(BaseTpmSimulator):
    """A simulator for a TPM."""

    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(self: StaticTpmSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._board_temperature = self.BOARD_TEMPERATURE
        self._fpga1_temperature = self.FPGA1_TEMPERATURE
        self._fpga2_temperature = self.FPGA2_TEMPERATURE

        super().__init__(logger)

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
        
class StaticTpmDriverSimulator(StaticTpmSimulator):
    """A simulator for a TPM."""


    def __init__(self: StaticTpmSimulator, logger: logging.Logger) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self.memory_map= {}
        self.tpm = False
        super().__init__(logger)

    def get_fpga0_temperature(self):
        return self.fpga1_temperature

    def get_fpga1_temperature(self):
        return self.fpga2_temperature
    def get_temperature(self):
        return self.board_temperature
    def get_voltage(self):
        return self.voltage
    def get_tile_id(self):
        print("getting tile id")
        return self.tile_id
    def get_firmware_list(self):
        return
    def program_fpgas(self):
        return 
    def set_station_id(self):
        return 
    def get_adc_rms(self):
        return self.adc_rms

    def get_fpga_time(self):
        return 
    def get_adc_rms(self):
        return self.adc_rms
    def get_adc_rms(self):
        return self.adc_rms
    def get_adc_rms(self):
        return self.adc_rms
    def get_40g_core_configuration(
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
                print(item)
                return item
        return 

    def read_address(self: BaseTpmSimulator, address: int) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """

        return self._address_map.get(str(address), 0)

    def write_address(self: BaseTpmSimulator, address: int, values: int) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """

        self._address_map.update({str(address): values})

    def connect(self):
        self[int(0x30000000)] = [3,7]
        self.tpm = {""}

    def __getitem__(self, key):
                # Check if the specified key is a memory address or register name
        if isinstance(key, int):
            return self.read_address(key)

        # Check if the specified key is a tuple, in which case we are reading from a device
        if type(key) is tuple:
            # Run checks
            if not self._checks():
                return

            if len(key) == 2:
                return self.read_device(key[0], key[1])
            else:
                raise LibraryError("A device name and address need to be specified for writing to SPI devices")

        elif type(key) is str or isinstance(key, basestring):
            # Run checks
            if not self._checks():
                return

            # Check if a device is specified in the register name
            if self.memory_map.has_register(key):
                reg = self.memory_map[key]
                return self.read_register(key, reg.size)
        else:
            raise LibraryError("Unrecognised key type, must be register name, memory address or SPI device tuple")

        # Register not found
        raise LibraryError("Register %s not found" % key)

        
    def __setitem__(self, key, value):
                # Check is the specified key is a memory address or register name
        if isinstance(key, int):
            print("dsd")
            return self.write_address(key, value)

        # Check if the specified key is a tuple, in which case we are writing to a device
        if type(key) is tuple:
            # Run checks
            if not self._checks():
                return

            if len(key) == 2:
                return self.write_device(key[0], key[1], value)
            else:
                raise LibraryError("A device name and address need to be specified for writing to SPI devices")

        elif type(key) is str or isinstance(key, basestring):
            # Run checks
            if not self._checks():
                return

            # Check if device is specified in the register name
            if self.memory_map.has_register(key):
                return self.write_register(key, value)
        else:
            raise LibraryError(
            	"Unrecognised key type (%s), must be register name or memory address" % key.__class__.__name__)

        # Register not found
        raise LibraryError("Register %s not found" % key)