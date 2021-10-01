# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
Hardware functions for the TPM 1.2 hardware.

This is derived from pyaavs.Tile object and depends heavily on the
pyfabil low level software and specific hardware module plugins.
"""

from __future__ import annotations  # allow forward references in type hints

import functools
import socket
import os
import logging
import struct
from typing import Any, Callable, cast, List, Optional
import numpy as np
import time

from pyfabil.base.definitions import Device, LibraryError, BoardError, Status
from pyfabil.base.utils import ip2long
from pyfabil.boards.tpm import TPM


def connected(f: Callable) -> Callable:
    """
    Help disallow certain function calls on unconnected tiles.

    :param f: the method wrapped by this helper

    :return: the wrapped method
    """

    @functools.wraps(f)
    def wrapper(self: Tile12, *args: list, **kwargs: dict) -> object:
        """
        Check the TPM is connected before allowing the wrapped method to proceed.

        :param self: the method called
        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :raises LibraryError: if the TPM is not connected

        :return: whatever the wrapped method returns
        """
        if self.tpm is None:
            self.logger.warning(
                "Cannot call function " + f.__name__ + " on unconnected TPM"
            )
            raise LibraryError(
                "Cannot call function " + f.__name__ + " on unconnected TPM"
            )
        else:
            return f(self, *args, **kwargs)

    return wrapper


class Tile12(object):
    """
    Tile hardware interface library.

    Streamlined and edited version of the AAVS Tile object
    """

    def __init__(
        self: Tile12,
        ip: str,
        port: int = 10000,
        lmc_ip: str = "0.0.0.0",
        lmc_port: int = 4660,
        sampling_rate: float = 800e6,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Iniitalise a new Tile12 instance.

        :param ip: IP address of the hardware
        :param port: UCP Port address of the hardware port
        :param lmc_ip: IP address of the MCCS DAQ recevier
        :param lmc_port: UCP Port address of the MCCS DAQ receiver
        :param sampling_rate: ADC sampling rate
        :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
        """
        if logger is None:
            self.logger = logging.getLogger("")
        else:
            self.logger = logger
        self._lmc_port = lmc_port
        self._lmc_ip = socket.gethostbyname(lmc_ip)
        self._lmc_use_10g = False
        self._arp_table: dict[int, list[int]] = {}
        self._40g_configuration: dict[str, Any] = {}
        self._port = port
        self._ip = socket.gethostbyname(ip)
        self.tpm: Optional[TPM] = None

        self._channeliser_truncation = 4
        self.subarray_id = 0
        self.station_id = 0
        self.tile_id = 0
        self._sampling_rate = sampling_rate

        # Mapping between preadu and TPM inputs
        self.fibre_preadu_mapping = {
            0: 1,
            1: 2,
            2: 3,
            3: 4,
            7: 13,
            6: 14,
            5: 15,
            4: 16,
            8: 5,
            9: 6,
            10: 7,
            11: 8,
            15: 9,
            14: 10,
            13: 11,
            12: 12,
        }

    # ---------------------------- Main functions ------------------------------------
    def tpm_version(self: Tile12) -> str:
        """
        Determine whether this is a TPM V1.2 or TPM V1.6.

        :return: TPM hardware version
        """
        return "tpm_v1_2"

    def connect(
        self: Tile12,
        initialise: bool = False,
        load_plugin: bool = True,
        enable_ada: bool = False,
    ) -> None:
        """
        Connect to the hardware and loads initial configuration.

        :param initialise: Initialises the TPM object
        :param load_plugin: loads software plugins
        :param enable_ada: Enable ADC amplifier (usually not present)
        """
        # Try to connect to board, if it fails then set tpm to None
        self.tpm = TPM()

        # Add plugin directory (load module locally)
        tf = __import__(
            "ska_low_mccs.tile.plugins.tpm.tpm_test_firmware", fromlist=["Dummy"]
        )
        self.tpm.add_plugin_directory(os.path.dirname(tf.__file__))
        # Connect using tpm object.
        # simulator parameter is used not to load the TPM specific plugins,
        # no actual simulation is performed.
        try:
            self.tpm.connect(
                ip=self._ip,
                port=self._port,
                initialise=initialise,
                simulator=not load_plugin,
                enable_ada=enable_ada,
                fsample=self._sampling_rate,
            )
        except (BoardError, LibraryError):
            self.tpm = None
            self.logger.error("Failed to connect to board at " + self._ip)
            return
        # Load tpm test firmware for both FPGAs (no need to load in simulation)
        if load_plugin and self.tpm.is_programmed():
            for device in [Device.FPGA_1, Device.FPGA_2]:
                self.tpm.load_plugin(
                    "TpmTestFirmware",
                    device=device,
                    fsample=self._sampling_rate,
                    logger=self.logger,
                )
        elif not self.tpm.is_programmed():
            self.logger.warning("TPM is not programmed! No plugins loaded")

    def is_programmed(self: Tile12) -> bool:
        """
        Check whether the TPM is connected and programmed.

        :return: If the TPM is programmed
        """
        if self.tpm is None:
            return False
        return self.tpm.is_programmed()

    def initialise(
        self: Tile12,
        enable_ada: bool = False,
        enable_test: bool = False,
    ) -> None:
        """
        Connect and initialise.

        :param enable_ada: enable adc amplifier, Not present in most TPM
            versions
        :param enable_test: setup internal test signal generator instead
            of ADC
        """
        # Connect to board
        self.connect(initialise=True, enable_ada=enable_ada)

        # Before initialing, check if TPM is programmed
        assert self.tpm is not None  # for the type checker
        if not self.tpm.is_programmed():
            self.logger.error("Cannot initialise board which is not programmed")
            return

        # Disable debug UDP header
        self[0x30000024] = 0x2

        # Calibrate FPGA to CPLD streaming
        # self.calibrate_fpga_to_cpld()

        # Initialise firmware plugin
        for firmware in self.tpm.tpm_test_firmware:
            firmware.initialise_firmware()

        # Set LMC IP
        self.tpm.set_lmc_ip(self._lmc_ip, self._lmc_port)

        # Enable C2C streaming
        self.tpm["board.regfile.c2c_stream_enable"] = 0x1
        self.set_c2c_burst()

        # Switch off both PREADUs
        self.tpm.tpm_preadu[0].switch_off()
        self.tpm.tpm_preadu[1].switch_off()

        # Switch on preadu
        for preadu in self.tpm.tpm_preadu:
            preadu.switch_on()
            time.sleep(1)
            preadu.select_low_passband()
            preadu.read_configuration()

        # Synchronise FPGAs
        self.sync_fpgas()

        # Initialize f2f link
        self.tpm.tpm_f2f[0].initialise_core("fpga2->fpga1")
        self.tpm.tpm_f2f[1].initialise_core("fpga1->fpga2")

        # AAVS-only - swap polarisations due to remapping performed by preadu
        # TODO verify if this is required on final hardware
        # self.tpm['fpga1.jesd204_if.regfile_pol_switch'] = 0b00001111
        # self.tpm['fpga2.jesd204_if.regfile_pol_switch'] = 0b00001111

        # Reset test pattern generator
        self.tpm.test_generator[0].channel_select(0x0000)
        self.tpm.test_generator[1].channel_select(0x0000)
        self.tpm.test_generator[0].disable_prdg()
        self.tpm.test_generator[1].disable_prdg()

        # Use test_generator plugin instead!
        if enable_test:
            # Test pattern. Tones on channels 72 & 75 + pseudo-random noise
            self.logger.info("Enabling test pattern")
            for generator in self.tpm.test_generator:
                generator.set_tone(0, 72 * self._sampling_rate / 1024, 0.0)
                generator.enable_prdg(0.4)
                generator.channel_select(0xFFFF)

        self.fortyg_cores_destination()

        for firmware in self.tpm.tpm_test_firmware:
            firmware.check_ddr_initialisation()

        # Initialise beamformer using a standard configuration,
        # only not to leave it in an unprogrammed state
        # single beam, 300 MHz bandwidth, 50-350 MHz
        # All IDs in spead header are set to 0, 16 antennas, no time info
        self.logger.info("Initialising beamformer")
        self.initialise_beamformer(
            start_channel=64,  # 50 MHz
            nof_channels=384,  # 300 MHz bandwidth
            is_first=False,  # usually a tile is not the first
            is_last=False,  # or the last in the station chain
        )
        self.define_spead_header(
            station_id=0, subarray_id=0, nof_antennas=16, ref_epoch=-1, start_time=0
        )

        # Perform synchronisation
        self.post_synchronisation()

    def fortyg_cores_destination(self: Tile12) -> None:
        """
        Set destination and source IP/MAC/ports for 40G cores.

        This will create a loopback between the two FPGAs
        """
        ip_octets = self._ip.split(".")
        assert self.tpm is not None  # for the type checker
        for n in range(len(self.tpm.tpm_10g_core)):
            if self["fpga1.regfile.feature.xg_eth_implemented"] == 1:
                src_ip = "10.10." + str(n + 1) + "." + str(ip_octets[3])
            else:
                src_ip = (
                    "10."
                    + str(n + 1)
                    + "."
                    + str(ip_octets[2])
                    + "."
                    + str(ip_octets[3])
                )
            if self.tpm.tpm_test_firmware[0].xg_40g_eth:
                self.configure_40g_core(
                    n,
                    0,
                    src_mac=0x620000000000 + ip2long(src_ip),
                    # dst_mac=None,  # 0x620000000000 + ip2long(dst_ip),
                    src_ip=src_ip,
                    dst_ip=None,  # dst_ip,
                    src_port=0xF0D0,
                    dst_port=4660,
                )
            else:
                self.configure_10g_core(
                    n,
                    src_mac=0x620000000000 + ip2long(src_ip),
                    dst_mac=None,  # 0x620000000000 + ip2long(dst_ip),
                    src_ip=src_ip,
                    dst_ip=None,  # dst_ip,
                    src_port=0xF0D0,
                    dst_port=4660,
                )

    def program_fpgas(self: Tile12, bitfile: str) -> None:
        """
        Program both FPGAs with specified firmware.

        :param bitfile: Bitfile to load
        """
        self.connect(load_plugin=False)
        if self.tpm is not None:
            self.logger.info("Downloading bitfile " + bitfile + " to board")
            # Uses own version of download bitfile, which uses less memory
            # than Pyfabil one
            self.tpm.download_firmware(Device.FPGA_1, bitfile)
        else:
            self.logger.warning(
                "Can not download bitfile " + bitfile + ": board not connected"
            )

    @connected
    def erase_fpga(self: Tile12) -> None:
        """Erase FPGA configuration memory."""
        assert self.tpm is not None  # for the type checker
        self.tpm.erase_fpga()

    def program_cpld(self: Tile12, bitfile: str) -> None:
        """
        Program CPLD with specified bitfile.

        Use with VERY GREAT care, this might leave
        the FPGA in an unreachable state. TODO Wiser to leave the method out altogether
        and use a dedicated utility instead?

        :param bitfile: Bitfile to flash to CPLD

        :return: write status
        """
        self.connect(load_plugin=True)
        self.logger.info("Downloading bitstream to CPLD FLASH")
        if self.tpm is not None:
            return self.tpm.tpm_cpld.cpld_flash_write(bitfile)

    @connected
    def read_cpld(self: Tile12, bitfile: str = "cpld_dump.bit") -> None:
        """
        Read bitfile in CPLD FLASH.

        :param bitfile: Bitfile where to dump CPLD firmware
        """
        self.logger.info("Reading bitstream from CPLD FLASH")
        assert self.tpm is not None  # for the type checker
        self.tpm.tpm_cpld.cpld_flash_read(bitfile)

    def get_ip(self: Tile12) -> str:
        """
        Get tile IP.

        :return: tile IP address
        """
        return self._ip

    @connected
    def get_temperature(self: Tile12) -> float:
        """
        Read board temperature.

        :return: board temperature
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm.temperature()

    @connected
    def get_voltage(self: Tile12) -> float:
        """
        Read board voltage.

        :return: board supply voltage
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm.voltage()

    @connected
    def get_current(self: Tile12) -> float:
        """
        Read board current.

        :return: board supply current
        """
        # not implemented
        # return self.tpm.current()
        return 0.0

    @connected
    def get_adc_rms(self: Tile12) -> list[float] | None:
        """
        Get ADC power.

        :return: ADC RMS power
        """
        # If board is not programmed, return None
        assert self.tpm is not None  # for the type checker
        if not self.tpm.is_programmed():
            return None

        # Get RMS values from board
        rms = []
        for adc_power_meter in self.tpm.adc_power_meter:
            rms.extend(adc_power_meter.get_RmsAmplitude())

        # Re-map values
        return rms

    @connected
    def get_fpga0_temperature(self: Tile12) -> float:
        """
        Get FPGA0 temperature.

        :return: FPGA0 temperature
        """
        if self.is_programmed():
            assert self.tpm is not None  # for the type checker
            return self.tpm.tpm_sysmon[0].get_fpga_temperature()
        else:
            return 0.0

    @connected
    def get_fpga1_temperature(self: Tile12) -> float:
        """
        Get FPGA1 temperature.

        :return: FPGA0 temperature
        """
        if self.is_programmed():
            assert self.tpm is not None  # for the type checker
            return self.tpm.tpm_sysmon[1].get_fpga_temperature()
        else:
            return 0.0

    @connected
    def configure_10g_core(
        self: Tile12,
        core_id: int,
        src_mac: Optional[str] = None,
        src_ip: Optional[str] = None,
        dst_mac: Optional[str] = None,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_port: Optional[int] = None,
    ) -> None:
        """
        Configure a 10G core.

        :todo: Legacy method. Check whether to be deleted.

        :param core_id: 10G core ID
        :param src_mac: Source MAC address
        :param src_ip: Source IP address
        :param dst_mac: Destination MAC address
        :param dst_ip: Destination IP
        :param src_port: Source port
        :param dst_port: Destination port
        """
        # Configure core
        assert self.tpm is not None  # for the type checker
        if src_mac is not None:
            self.tpm.tpm_10g_core[core_id].set_src_mac(src_mac)
        if src_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_src_ip(src_ip)
        if dst_mac is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_mac(dst_mac)
        if dst_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_ip(dst_ip)
        if src_port is not None:
            self.tpm.tpm_10g_core[core_id].set_src_port(src_port)
        if dst_port is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_port(dst_port)

    @connected
    def configure_40g_core(
        self: Tile12,
        core_id: int,
        arp_table_entry: int = 0,
        src_mac: Optional[str] = None,
        src_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_ip: Optional[str] = None,
        dst_port: Optional[int] = None,
    ) -> None:
        """
        Configure a 40G core.

        :param core_id: 40G core ID
        :param arp_table_entry: ARP table entry ID
        :param src_mac: Source MAC address
        :param src_ip: Source IP address
        :param dst_ip: Destination IP
        :param src_port: Source port
        :param dst_port: Destination port
        """
        # Configure core
        assert self.tpm is not None  # for the type checker
        if src_mac is not None:
            self.tpm.tpm_10g_core[core_id].set_src_mac(src_mac)
        if src_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_src_ip(src_ip)
        if dst_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_ip(dst_ip, arp_table_entry)
        if src_port is not None:
            self.tpm.tpm_10g_core[core_id].set_src_port(src_port, arp_table_entry)
        if dst_port is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_port(dst_port, arp_table_entry)
            self.tpm.tpm_10g_core[core_id].set_rx_port_filter(dst_port)

    @connected
    def get_10g_core_configuration(self: Tile12, core_id: int) -> dict[str, int]:
        """
        Get the configuration for a 10g core.

        :param core_id: Core ID (0-7)

        :return: core configuration

        :todo: Check whether to be deleted.
        """
        assert self.tpm is not None  # for the type checker
        return {
            "src_mac": int(self.tpm.tpm_10g_core[core_id].get_src_mac()),
            "src_ip": int(self.tpm.tpm_10g_core[core_id].get_src_ip()),
            "dst_ip": int(self.tpm.tpm_10g_core[core_id].get_dst_ip()),
            "dst_mac": int(self.tpm.tpm_10g_core[core_id].get_dst_mac()),
            "src_port": int(self.tpm.tpm_10g_core[core_id].get_src_port()),
            "dst_port": int(self.tpm.tpm_10g_core[core_id].get_dst_port()),
        }

    @connected
    def get_40g_core_configuration(
        self: Tile12, core_id: int, arp_table_entry: int = 0
    ) -> Optional[dict[str, int]]:
        """
        Get the configuration for a 40g core.

        :param core_id: Core ID
        :param arp_table_entry: ARP table entry to use

        :return: core configuration
        """
        try:
            assert self.tpm is not None  # for the type checker
            self._40g_configuration = {
                "core_id": core_id,
                "arp_table_entry": arp_table_entry,
                "src_mac": int(self.tpm.tpm_10g_core[core_id].get_src_mac()),
                "src_ip": int(self.tpm.tpm_10g_core[core_id].get_src_ip()),
                "dst_ip": int(
                    self.tpm.tpm_10g_core[core_id].get_dst_ip(arp_table_entry)
                ),
                "src_port": int(
                    self.tpm.tpm_10g_core[core_id].get_src_port(arp_table_entry)
                ),
                "dst_port": int(
                    self.tpm.tpm_10g_core[core_id].get_dst_port(arp_table_entry)
                ),
            }
        except IndexError:
            self._40g_configuration = {}

        return self._40g_configuration

    @connected
    def set_lmc_download(
        self: Tile12,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
        lmc_mac: Optional[str] = None,
    ) -> None:
        """
        Configure link and size of control data.

        :param mode: 1g or 10g
        :param payload_length: SPEAD payload length in bytes
        :param dst_ip: Destination IP
        :param src_port: Source port for integrated data streams
        :param dst_port: Destination port for integrated data streams
        :param lmc_mac: LMC Mac address is required for 10G lane configuration
        """
        assert self.tpm is not None  # for the type checker
        # Using 10G lane
        if mode.upper() == "10G":
            if payload_length >= 8193:
                self.logger.warning("Packet length too large for 10G")
                return

            # If dst_ip is None, use local lmc_ip
            if dst_ip is None:
                dst_ip = self._lmc_ip

            if self.tpm.tpm_test_firmware[0].xg_40g_eth:
                self.configure_40g_core(
                    1, 1, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
                )

                self.configure_40g_core(
                    0, 1, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
                )
            else:
                if lmc_mac is None:
                    self.logger.warning(
                        "LMC MAC must be specified for 10G lane configuration"
                    )
                    return

                self.configure_10g_core(
                    2,
                    dst_mac=lmc_mac,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                )

                self.configure_10g_core(
                    6,
                    dst_mac=lmc_mac,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                )

            self["fpga1.lmc_gen.payload_length"] = payload_length
            self["fpga2.lmc_gen.payload_length"] = payload_length

            self["fpga1.lmc_gen.tx_demux"] = 2
            self["fpga2.lmc_gen.tx_demux"] = 2
            self._lmc_use_10g = True

        # Using dedicated 1G link
        elif mode.upper() == "1G":
            if dst_ip is not None:
                self._lmc_ip = dst_ip
            self.tpm.set_lmc_ip(self._lmc_ip, self._lmc_port)
            self["fpga1.lmc_gen.tx_demux"] = 1
            self["fpga2.lmc_gen.tx_demux"] = 1
            self._lmc_use_10g = False
        else:
            self.logger.warning("Supported modes are 1g, 10g")
            return

    @connected
    def set_lmc_integrated_download(
        self: Tile12,
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
        :param channel_payload_length: SPEAD payload length for integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated beam data
        :param dst_ip: Destination IP
        :param src_port: Source port for integrated data streams
        :param dst_port: Destination port for integrated data streams
        :param lmc_mac: LMC Mac address is required for 10G lane configuration
        """
        assert self.tpm is not None  # for the type checker
        # Using 10G lane
        if mode.upper() == "10G":

            # If dst_ip is None, use local lmc_ip
            if dst_ip is None:
                dst_ip = self._lmc_ip

            if self.tpm.tpm_test_firmware[0].xg_40g_eth:
                self.configure_40g_core(
                    1, 1, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
                )

                self.configure_40g_core(
                    0, 1, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
                )
            else:
                if lmc_mac is None:
                    self.logger.error(
                        "LMC MAC must be specified for 10G lane configuration"
                    )
                    return
                self.configure_10g_core(
                    2,
                    dst_mac=lmc_mac,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                )

                self.configure_10g_core(
                    6,
                    dst_mac=lmc_mac,
                    dst_ip=dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                )

        # Using dedicated 1G link
        elif mode.upper() == "1G":
            pass
        else:
            self.logger.error("Supported mode are 1g, 10g")
            return

        # Setting payload lengths
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure_download(
                mode, channel_payload_length, beam_payload_length
            )

    @connected
    def get_arp_table(self: Tile12) -> dict[int, list[int]]:
        """
        Check that ARP table has been populated in for all used cores.

        40G interfaces use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer,1 for LMC.
        10G interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: list of core id and arp table populated
        """
        assert self.tpm is not None  # for the type checker
        # wait UDP link up
        if self["fpga1.regfile.feature.xg_eth_implemented"] == 1:
            self.logger.info("Checking ARP table...")

            if self.tpm.tpm_test_firmware[0].xg_40g_eth:
                core_ids = [0, 1]
                if self._lmc_use_10g:
                    arp_table_ids = [0, 1]
                else:
                    arp_table_ids = [0]
            else:
                if self._lmc_use_10g:
                    core_ids = [0, 1, 2, 4, 5, 6]
                else:
                    core_ids = [0, 1, 4, 5]
                arp_table_ids = [0]

            linkup = False
            self._arp_table = {i: [] for i in core_ids}

            for core_id in core_ids:
                for arp_table in arp_table_ids:
                    core_status = self.tpm.tpm_10g_core[core_id].get_arp_table_status(
                        arp_table, silent_mode=True
                    )
                    if core_status & 0x4 == 0:
                        message = (
                            f"CoreID {core_id} with ArpID {arp_table} is not "
                            f"populated"
                        )

                        self.logger.info(message)
                    else:
                        self._arp_table[core_id].append(arp_table)
                        linkup = True

            if linkup:
                self.logger.info("10G Link established! ARP table populated!")

        return self._arp_table

    @connected
    def set_station_id(self: Tile12, station_id: int, tile_id: int) -> None:
        """
        Set station ID.

        :param station_id: Station ID
        :param tile_id: Tile ID within station
        """
        fpgas = ["fpga1", "fpga2"]
        assert self.tpm is not None  # for the type checker
        if len(self.tpm.find_register("fpga1.regfile.station_id")) > 0:
            self["fpga1.regfile.station_id"] = station_id
            self["fpga2.regfile.station_id"] = station_id
            self["fpga1.regfile.tpm_id"] = tile_id
            self["fpga2.regfile.tpm_id"] = tile_id
        else:
            for f in fpgas:
                self[f + ".dsp_regfile.config_id.station_id"] = station_id
                self[f + ".dsp_regfile.config_id.tpm_id"] = tile_id

    @connected
    def get_station_id(self: Tile12) -> int:
        """
        Get station ID.

        :return: station ID programmed in HW
        """
        assert self.tpm is not None  # for the type checker
        if not self.tpm.is_programmed():
            return -1
        else:
            if len(self.tpm.find_register("fpga1.regfile.station_id")) > 0:
                station_id = cast(int, self["fpga1.regfile.station_id"])
            else:
                station_id = cast(int, self["fpga1.dsp_regfile.config_id.station_id"])
            return station_id

    @connected
    def get_tile_id(self: Tile12) -> int:
        """
        Get tile ID.

        :return: programmed tile id
        """
        assert self.tpm is not None  # for the type checker
        if not self.tpm.is_programmed():
            return -1
        else:
            if len(self.tpm.find_register("fpga1.regfile.tpm_id")) > 0:
                tile_id = cast(int, self["fpga1.regfile.tpm_id"])
            else:
                tile_id = cast(int, self["fpga1.dsp_regfile.config_id.tpm_id"])
            return tile_id

    @connected
    def tweak_transceivers(self: Tile12) -> None:
        """Tweak transceivers."""
        assert self.tpm is not None  # for the type checker
        for f in ["fpga1", "fpga2"]:
            for n in range(4):
                if len(self.tpm.find_register("fpga1.eth_10g_drp.gth_channel_0")) > 0:
                    add = (
                        int(
                            self.tpm.memory_map[
                                f + ".eth_10g_drp.gth_channel_" + str(n)
                            ].address
                        )
                        + 4 * 0x7C
                    )
                else:
                    add = (
                        int(
                            self.tpm.memory_map[
                                f + ".eth_drp.gth_channel_" + str(n)
                            ].address
                        )
                        + 4 * 0x7C
                    )
                self[add] = 0x6060

    ###########################################
    # Time related methods
    ###########################################
    @connected
    def get_fpga_time(self: Tile12, device: int) -> int:
        """
        Return time from FPGA.

        :param device: FPGA to get time from

        :return: Internal time for FPGA
        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return cast(int, self["fpga1.pps_manager.curr_time_read_val"])
        elif device == Device.FPGA_2:
            return cast(int, self["fpga2.pps_manager.curr_time_read_val"])
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def set_fpga_time(self: Tile12, device: int, device_time: int) -> None:
        """
        Set Unix time in FPGA.

        :param device: FPGA to get time from
        :param device_time: Internal time for FPGA

        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            self["fpga1.pps_manager.curr_time_write_val"] = device_time
            self["fpga1.pps_manager.curr_time_cmd.wr_req"] = 0x1
        elif device == Device.FPGA_2:
            self["fpga2.pps_manager.curr_time_write_val"] = device_time
            self["fpga2.pps_manager.curr_time_cmd.wr_req"] = 0x1
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def get_fpga_timestamp(self: Tile12, device: int = Device.FPGA_1) -> int:
        """
        Get timestamp from FPGA.

        :param device: FPGA to read timestamp from

        :return: PPS time

        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return cast(int, self["fpga1.pps_manager.timestamp_read_val"])
        elif device == Device.FPGA_2:
            return cast(int, self["fpga2.pps_manager.timestamp_read_val"])
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def get_phase_terminal_count(self: Tile12) -> int:
        """
        Get PPS phase terminal count.

        :return: PPS phase terminal count
        """
        return cast(int, self["fpga1.pps_manager.sync_tc.cnt_1_pulse"])

    @connected
    def set_phase_terminal_count(self: Tile12, value: int) -> None:
        """
        Set phase terminal count.

        :param value: PPS phase terminal count
        """
        self["fpga1.pps_manager.sync_tc.cnt_1_pulse"] = value
        self["fpga2.pps_manager.sync_tc.cnt_1_pulse"] = value

    @connected
    def get_pps_delay(self: Tile12) -> int:
        """
        Get delay between PPS and 10 MHz clock.

        :return: delay between PPS and 10 MHz clock in 200 MHz cycles
        """
        return cast(int, self["fpga1.pps_manager.sync_phase.cnt_hf_pps"])

    @connected
    def wait_pps_event(self: Tile12) -> None:
        """
        Wait for a PPS edge. Added timeout feture to avoid method to stuck.

        :raises BoardError: Hardware PPS stuck
        """
        timeout = 1100
        t0 = self.get_fpga_time(Device.FPGA_1)
        while t0 == self.get_fpga_time(Device.FPGA_1):
            if timeout > 0:
                time.sleep(0.001)
                timeout = timeout - 1
                pass
            else:
                raise BoardError("TPM PPS counter does not advance")

    @connected
    def check_pending_data_requests(self: Tile12) -> bool:
        """
        Check whether there are any pending data requests.

        :return: true if pending requests are present
        """
        return (
            cast(int, self["fpga1.lmc_gen.request"])
            + cast(int, self["fpga2.lmc_gen.request"])
            > 0
        )

    ########################################################
    # channeliser
    ########################################################
    @connected
    def set_channeliser_truncation(
        self: Tile12, trunc: int | list[int], signal: Optional[int] = None
    ) -> None:
        """
        Set channeliser truncation scale for the whole tile.

        :param trunc: Truncated bits, channeliser output scaled down
        :param signal: Input signal, 0 to 31. If None, apply to all
        """
        # if trunc is a single value, apply to all channels
        if type(trunc) == int:
            if 0 > trunc or trunc > 7:
                self.logger.warning(
                    f"Could not set channeliser truncation to " f"{trunc}, setting to 0"
                )
                trunc = 0

            trunc_vec1 = 256 * [trunc]
            trunc_vec2 = 256 * [trunc]
        else:
            trunc_vec1 = cast(list[int], trunc)[0:256]
            trunc_vec2 = cast(list[int], trunc)[256:512]
            trunc_vec2.reverse()
        #
        # If signal is not specified, apply to all signals
        if signal is None:
            siglist = cast(List[int], range(32))
        else:
            siglist = [signal]

        for i in siglist:
            if i >= 0 and i < 16:
                self["fpga1.channelizer.block_sel"] = 2 * i
                self["fpga1.channelizer.rescale_data"] = trunc_vec1
                self["fpga1.channelizer.block_sel"] = 2 * i + 1
                self["fpga1.channelizer.rescale_data"] = trunc_vec2
            elif i >= 16 and i < 32:
                i = i - 16
                self["fpga2.channelizer.block_sel"] = 2 * i
                self["fpga2.channelizer.rescale_data"] = trunc_vec1
                self["fpga2.channelizer.block_sel"] = 2 * i + 1
                self["fpga2.channelizer.rescale_data"] = trunc_vec2
            else:
                self.logger.warning("Signal " + str(i) + " is outside range (0:31)")

    @connected
    def set_time_delays(self: Tile12, delays: list[float]) -> bool:
        """
        Set coarse zenith delay for input ADC streams Delay specified in nanoseconds.

        nominal is 0.

        :param delays: Delay in samples, positive delay adds delay to the signal stream

        :return: Parameters in range
        """
        # Compute maximum and minimum delay
        frame_length = (1.0 / self._sampling_rate) * 1e9
        min_delay = frame_length * -124
        max_delay = frame_length * 127

        self.logger.debug(
            "frame_length = "
            + str(frame_length)
            + " , min_delay = "
            + str(min_delay)
            + " , max_delay = "
            + str(max_delay)
        )

        # Check that we have the correct numnber of delays (one or 16)
        if isinstance(delays, float):
            # Check that we have a valid delay
            if min_delay <= delays <= max_delay:
                # possible problem to fix here :
                #                delays_hw = [int(round(delays / frame_length))] * 32
                # Test from Riccardo :
                delays_hw = [int(round(delays / frame_length) + 128)] * 32
            else:
                self.logger.warning(
                    "Specified delay "
                    + str(delays)
                    + " out of range ["
                    + str(min_delay)
                    + ", "
                    + str(max_delay)
                    + "], skipping"
                )
                return False

        elif isinstance(delays, list) and len(delays) == 32:
            # Check that all delays are valid
            delays = np.array(delays, dtype=np.float)
            if np.all(min_delay <= delays) and np.all(delays <= max_delay):  # type: ignore[operator]
                delays_hw = np.clip(
                    (np.round(delays / frame_length) + 128).astype(np.int), 4, 255  # type: ignore[operator]
                ).tolist()
            else:
                self.logger.warning(
                    "Specified delay "
                    + str(delays)
                    + " out of range ["
                    + str(min_delay)
                    + ", "
                    + str(max_delay)
                    + "], skipping"
                )
                return False

        else:
            self.logger.warning(
                "Invalid delays specfied (must be a number of list of numbers of length 32)"
            )
            return False

        self.logger.info("Setting hardware delays = " + str(delays_hw))
        # Write delays to board
        self["fpga1.test_generator.delay_0"] = delays_hw[:16]
        self["fpga2.test_generator.delay_0"] = delays_hw[16:]
        return True

    # ---------------------------- Pointing and calibration routines ---------------------------
    @connected
    def initialise_beamformer(
        self: Tile12,
        start_channel: int,
        nof_channels: int,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Initialise tile and station beamformers for a simple single beam configuration.

        :param start_channel: Initial channel, must be even
        :param nof_channels: Number of beamformed spectral channels
        :param is_first: True for first tile in beamforming chain
        :param is_last: True for last tile in beamforming chain
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].initialise_beamf()
        self.tpm.beamf_fd[1].initialise_beamf()
        self.tpm.beamf_fd[0].set_regions([[start_channel, nof_channels, 0]])
        self.tpm.beamf_fd[1].set_regions([[start_channel, nof_channels, 0]])
        self.tpm.beamf_fd[0].antenna_tapering = [1.0] * 8
        self.tpm.beamf_fd[1].antenna_tapering = [1.0] * 8
        self.tpm.beamf_fd[0].compute_calibration_coefs()
        self.tpm.beamf_fd[1].compute_calibration_coefs()

        # Interface towards beamformer in FPGAs
        self.tpm.station_beamf[0].initialize()
        self.tpm.station_beamf[1].initialize()
        self.set_first_last_tile(is_first, is_last)
        self.tpm.station_beamf[0].defineChannelTable([[start_channel, nof_channels, 0]])
        self.tpm.station_beamf[1].defineChannelTable([[start_channel, nof_channels, 0]])

    @connected
    def set_beamformer_regions(self: Tile12, region_array: list[list[int]]) -> None:
        """
        Set frequency regions.

        Regions are defined in a 2-d array, for a maximum of 48 regions.
        Each element in the array defines a region, with the form
        [start_ch, nof_ch, beam_index]

        - start_ch:    region starting channel (currently must be a
                       multiple of 2, LS bit discarded)
        - nof_ch:      size of the region: must be multiple of 8 chans
        - beam_index:  beam used for this region, range [0:8)

        Total number of channels must be <= 384
        The routine computes the arrays beam_index, region_off, region_sel,
        and the total number of channels nof_chans, and programs it in the HW
        :param region_array: list of region array descriptors
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].set_regions(region_array)
        self.tpm.beamf_fd[1].set_regions(region_array)
        self.tpm.station_beamf[0].defineChannelTable(region_array)
        self.tpm.station_beamf[1].defineChannelTable(region_array)

    @connected
    def set_pointing_delay(
        self: Tile12, delay_array: list[list[float]], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/seconds.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is described (range 0:7). Delay is updated inside the delay
        engine at the time specified by method load_delay.

        :param delay_array: delay and delay rate for each antenna
        :param beam_index: specifies which beam is described (range 0:7)
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].set_delay(delay_array[0:8], beam_index)
        self.tpm.beamf_fd[1].set_delay(delay_array[8:], beam_index)

    @connected
    def load_pointing_delay(self: Tile12, load_time: int = 0) -> None:
        """
        Update the delay inside the delay engine at the time specified.

         If time = 0 load immediately

        :param load_time: time (in ADC frames/256) for delay update
        """
        if load_time == 0:
            load_time = self.current_tile_beamformer_frame() + 64

        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].load_delay(load_time)
        self.tpm.beamf_fd[1].load_delay(load_time)

    @connected
    def load_calibration_coefficients(
        self: Tile12, antenna: int, calibration_coefficients: list[float]
    ) -> None:
        """
        Load the calibration coefficients.

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
        assert self.tpm is not None  # for the type checker
        if antenna < 8:
            self.tpm.beamf_fd[0].load_calibration(antenna, calibration_coefficients)
        else:
            self.tpm.beamf_fd[1].load_calibration(antenna - 8, calibration_coefficients)

    @connected
    def load_antenna_tapering(
        self: Tile12, beam: int, tapering_coefficients: list[int]
    ) -> None:
        """
        Tapering_coefficients is a vector of 16 values, one per antenna.

        Default (at
        initialization) is 1.0. TODO modify plugin to allow for different beams.

        :param beam: Beam index in range 0:47
        :param tapering_coefficients: Coefficients for each antenna
        """
        assert self.tpm is not None  # for the type checker
        if beam > 0:
            self.logger.warning("Tapering implemented only for beam 0")
        self.tpm.beamf_fd[0].load_antenna_tapering(tapering_coefficients[0:8])
        self.tpm.beamf_fd[1].load_antenna_tapering(tapering_coefficients[8:])

    @connected
    def load_beam_angle(self: Tile12, angle_coefficients: list[float]) -> None:
        """
        Load beam angle coefficients.

        Angle_coefficients is an array of one element per beam, specifying a rotation
        angle, in radians, for the specified beam.

        The rotation is the same for all antennas. Default is 0 (no
        rotation). A positive pi/4 value transfers the X polarization to
        the Y polarization. The rotation is applied after regular
        calibration.

        :param angle_coefficients: Rotation angle, per beam, in radians
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].load_beam_angle(angle_coefficients)
        self.tpm.beamf_fd[1].load_beam_angle(angle_coefficients)

    def compute_calibration_coefficients(self: Tile12) -> None:
        """Compute the calibration coefficients and load them in the hardware."""
        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].compute_calibration_coefs()
        self.tpm.beamf_fd[1].compute_calibration_coefs()

    def switch_calibration_bank(self: Tile12, switch_time: int = 0) -> None:
        """
        Switches the loaded calibration coefficients at a prescribed time.

        If time = 0 switch immediately

        :param switch_time: time (in ADC frames/256) for delay update
        """
        if switch_time == 0:
            switch_time = self.current_tile_beamformer_frame() + 64

        assert self.tpm is not None  # for the type checker
        self.tpm.beamf_fd[0].switch_calibration_bank(switch_time)
        self.tpm.beamf_fd[1].switch_calibration_bank(switch_time)

    def set_beamformer_epoch(self: Tile12, epoch: int) -> bool:
        """
        Set the Unix epoch in seconds since Unix reference time.

        :param epoch: Unix epoch for the reference time

        :return: Success status
        """
        assert self.tpm is not None  # for the type checker
        ret1 = self.tpm.station_beamf[0].set_epoch(epoch)
        ret2 = self.tpm.station_beamf[1].set_epoch(epoch)
        return ret1 and ret2

    def set_csp_rounding(self: Tile12, rounding: int) -> bool:
        """
        Set output rounding for CSP.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP

        :return: success status
        """
        assert self.tpm is not None  # for the type checker
        ret1 = self.tpm.station_beamf[0].set_csp_rounding(rounding)
        ret2 = self.tpm.station_beamf[1].set_csp_rounding(rounding)
        return ret1 and ret2

    def current_station_beamformer_frame(self: Tile12) -> int:
        """
        Query time of packets at station beamformer input.

        :return: current frame, in units of 256 ADC frames (276,48 us)
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm.station_beamf[0].current_frame()

    def current_tile_beamformer_frame(self: Tile12) -> int:
        """
        Query time of packets at tile beamformer input.

        :return: current frame, in units of 256 ADC frames (276,48 us)
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm.beamf_fd[0].current_frame()

    def set_first_last_tile(self: Tile12, is_first: bool, is_last: bool) -> bool:
        """
        Define if a tile is first, last, both or intermediate.

        One, and only one tile must be first, and last, in a chain. A
        tile can be both (one tile chain), or none.

        :param is_first: True for first tile in beamforming chain
        :param is_last: True for last tile in beamforming chain

        :return: success status
        """
        assert self.tpm is not None  # for the type checker
        ret1 = self.tpm.station_beamf[0].set_first_last_tile(is_first, is_last)
        ret2 = self.tpm.station_beamf[1].set_first_last_tile(is_first, is_last)
        return ret1 and ret2

    def define_spead_header(
        self: Tile12,
        station_id: int,
        subarray_id: int,
        nof_antennas: int,
        ref_epoch: int = -1,
        start_time: int = 0,
    ) -> bool:
        """
        Define SPEAD header for last tile.

        All parameters are specified by the LMC.

        :param station_id: Station ID
        :param subarray_id: Subarray ID
        :param nof_antennas: Number of antenns in the station
        :param ref_epoch: Unix time of epoch. -1 uses value defined in set_epoch
        :param start_time: start time (TODO describe better)

        :return: True if parameters OK, False for error
        """
        assert self.tpm is not None  # for the type checker
        ret1 = self.tpm.station_beamf[0].define_spead_header(
            station_id, subarray_id, nof_antennas, ref_epoch, start_time
        )
        ret2 = self.tpm.station_beamf[1].define_spead_header(
            station_id, subarray_id, nof_antennas, ref_epoch, start_time
        )
        return ret1 and ret2

    def beamformer_is_running(self: Tile12) -> bool:
        """
        Check if station beamformer is running.

        :return: beamformer running status
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm.station_beamf[0].is_running()

    def start_beamformer(self: Tile12, start_time: int = 0, duration: int = -1) -> bool:
        """
        Start the beamformer.

        Duration: if > 0 is a duration in frames * 256 (276.48 us)
        if == -1 run forever

        :param start_time: time (in ADC frames/256) for first frame sent
        :param duration: duration in ADC frames/256. Multiple of 8

        :return: False for error (e.g. beamformer already running)
        """
        mask = 0xFFFFFFF8  # Impose a time multiple of 8 frames
        if self.beamformer_is_running():
            return False

        if start_time == 0:
            start_time = self.current_station_beamformer_frame() + 40

        start_time &= mask  # Impose a start time multiple of 8 frames

        if duration != -1:
            duration = duration & mask

        assert self.tpm is not None  # for the type checker
        ret1 = self.tpm.station_beamf[0].start(start_time, duration)
        ret2 = self.tpm.station_beamf[1].start(start_time, duration)

        if ret1 and ret2:
            return True
        else:
            self.abort()
            return False

    def stop_beamformer(self: Tile12) -> None:
        """Stop beamformer."""
        assert self.tpm is not None  # for the type checker
        self.tpm.station_beamf[0].abort()
        self.tpm.station_beamf[1].abort()
        return

    # Synchronisation routines ------------------------------------
    @connected
    def post_synchronisation(self: Tile12) -> None:
        """Post tile configuration synchronization."""
        self.wait_pps_event()

        current_tc = self.get_phase_terminal_count()
        delay = self.get_pps_delay()

        self.set_phase_terminal_count(self.calculate_delay(delay, current_tc, 16, 24))

        self.wait_pps_event()

        delay = self.get_pps_delay()
        self.logger.info("Finished tile post synchronisation (" + str(delay) + ")")

    @connected
    def sync_fpgas(self: Tile12) -> None:
        """Syncronises the two FPGAs in the tile Returns when these are synchronised."""
        devices = ["fpga1", "fpga2"]

        # Setting internal PPS generator
        assert self.tpm is not None  # for the type checker
        for f in devices:
            self.tpm[f + ".pps_manager.pps_gen_tc"] = int(self._sampling_rate / 4) - 1

        # Setting sync time
        for f in devices:
            self.tpm[f + ".pps_manager.curr_time_write_val"] = int(time.time())

        # sync time write command
        for f in devices:
            self.tpm[f + ".pps_manager.curr_time_cmd.wr_req"] = 0x1

        self.check_synchronization()

    @connected
    def check_synchronization(self: Tile12) -> None:
        """Check FPGA synchronisation, returns when these are synchronised."""
        devices = ["fpga1", "fpga2"]

        assert self.tpm is not None  # for the type checker
        for _n in range(5):
            self.logger.info("Synchronising FPGA UTC time.")
            self.wait_pps_event()
            time.sleep(0.5)

            t = int(time.time())
            for f in devices:
                self.tpm[f + ".pps_manager.curr_time_write_val"] = t
            # sync time write command
            for f in devices:
                self.tpm[f + ".pps_manager.curr_time_cmd.wr_req"] = 0x1

            self.wait_pps_event()
            time.sleep(0.1)
            t0 = self.tpm["fpga1.pps_manager.curr_time_read_val"]
            t1 = self.tpm["fpga2.pps_manager.curr_time_read_val"]

            if t0 == t1:
                return
        self.logger.error("Not possible to synchronise FPGA UTC time!")

    @connected
    def check_fpga_synchronization(self: Tile12) -> bool:
        """
        Check various synchronization parameters.

        Output in the log

        :return: OK status
        """
        assert self.tpm is not None  # for the type checker
        result = True
        # check PLL status
        pll_status = self.tpm["pll", 0x508]
        if pll_status == 0xE7:
            self.logger.debug("PLL locked to external reference clock.")
        elif pll_status == 0xF2:
            self.logger.warning("PLL locked to internal reference clock.")
        else:
            self.logger.error(
                "PLL is not locked! - Status Readback 0 (0x508): " + hex(pll_status)
            )
            result = False

        assert self.tpm is not None  # for the type checker
        # check PPS detection
        if self.tpm["fpga1.pps_manager.pps_detected"] == 0x1:
            self.logger.debug("FPGA1 is locked to external PPS")
        else:
            self.logger.warning("FPGA1 is not locked to external PPS")
        if self.tpm["fpga2.pps_manager.pps_detected"] == 0x1:
            self.logger.debug("FPGA2 is locked to external PPS")
        else:
            self.logger.warning("FPGA2 is not locked to external PPS")

        # check FPGA time
        self.wait_pps_event()
        t0 = self.tpm["fpga1.pps_manager.curr_time_read_val"]
        t1 = self.tpm["fpga2.pps_manager.curr_time_read_val"]
        self.logger.info("FPGA1 time is " + str(t0))
        self.logger.info("FPGA2 time is " + str(t1))
        if t0 != t1:
            self.logger.error("Time different between FPGAs detected!")
            result = False

        # check FPGA timestamp
        t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        t1 = self.tpm["fpga2.pps_manager.timestamp_read_val"]
        self.logger.info("FPGA1 timestamp is " + str(t0))
        self.logger.info("FPGA2 timestamp is " + str(t1))
        if abs(t0 - t1) > 1:
            self.logger.warning("Timestamp different between FPGAs detected!")

        # Check FPGA ring beamfomrer timestamp
        t0 = self.tpm["fpga1.beamf_ring.current_frame"]
        t1 = self.tpm["fpga2.beamf_ring.current_frame"]
        self.logger.info("FPGA1 station beamformer timestamp is " + str(t0))
        self.logger.info("FPGA2 station beamformer timestamp is " + str(t1))
        if abs(t0 - t1) > 1:
            self.logger.warning(
                "Beamformer timestamp different between FPGAs detected!"
            )

        return result

    @connected
    def set_c2c_burst(self: Tile12) -> None:
        """Set C2C burst when supported by FPGAs and CPLD."""
        assert self.tpm is not None  # for the type checker
        self.tpm["fpga1.regfile.c2c_stream_ctrl.idle_val"] = 0
        self.tpm["fpga2.regfile.c2c_stream_ctrl.idle_val"] = 0
        if len(self.tpm.find_register("fpga1.regfile.feature.c2c_linear_burst")) > 0:
            fpga_burst_supported = self.tpm["fpga1.regfile.feature.c2c_linear_burst"]
        else:
            fpga_burst_supported = 0
        if len(self.tpm.find_register("board.regfile.c2c_ctrl.mm_burst_enable")) > 0:
            self.tpm["board.regfile.c2c_ctrl.mm_burst_enable"] = 0
            cpld_burst_supported = 1
        else:
            cpld_burst_supported = 0

        if cpld_burst_supported == 1 and fpga_burst_supported == 1:
            self.tpm["board.regfile.c2c_ctrl.mm_burst_enable"] = 1
            self.logger.debug("C2C burst activated.")
            return
        if fpga_burst_supported == 0:
            self.logger.debug("C2C burst is not supported by FPGAs.")
        if cpld_burst_supported == 0:
            self.logger.debug("C2C burst is not supported by CPLD.")

    @connected
    def synchronised_data_operation(
        self: Tile12, seconds: float = 0.2, timestamp: Optional[str] = None
    ) -> None:
        """
        Synchronise data operations between FPGAs.

        :param seconds: Number of seconds to delay operation
        :param timestamp: Timestamp at which tile will be synchronised
        """
        assert self.tpm is not None  # for the type checker
        # Wait while previous data requests are processed
        while (
            self.tpm["fpga1.lmc_gen.request"] != 0
            or self.tpm["fpga2.lmc_gen.request"] != 0
        ):
            self.logger.info("Waiting for enable to be reset")
            time.sleep(0.05)

        self.logger.debug("Command accepted")

        # Read timestamp
        if timestamp is not None:
            t0 = int(timestamp)
        else:
            t0 = max(
                self.tpm["fpga1.pps_manager.timestamp_read_val"],
                self.tpm["fpga2.pps_manager.timestamp_read_val"],
            )

        # Set arm timestamp
        # delay = number of frames to delay * frame time (shift by 8)
        delay = seconds * (1.0 / (1080.0 * 1e-9) / 256.0)
        t1 = t0 + int(delay)
        for fpga in self.tpm.tpm_fpga:
            fpga.fpga_apply_sync_delay(t1)

        tn1 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        tn2 = self.tpm["fpga2.pps_manager.timestamp_read_val"]
        if max(tn1, tn2) >= t1:
            self.logger.error("Synchronised operation failed!")

    @connected
    def synchronised_beamformer_coefficients(
        self: Tile12, timestamp: Optional[str] = None, seconds: float = 0.2
    ) -> None:
        """
        Synchronise beamformer coefficients download.

        :param timestamp: Timestamp to synchronise against
        :param seconds: Number of seconds to delay operation
        """
        # Read timestamp
        assert self.tpm is not None  # for the type checker
        if timestamp is None:
            t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        else:
            t0 = timestamp

        # Set arm timestamp
        # delay = number of frames to delay * frame time (shift by 8)
        delay = seconds * (1 / (1080 * 1e-9) / 256)
        for f in ["fpga1", "fpga2"]:
            self.tpm[f + ".beamf.timestamp_req"] = t0 + int(delay)

    @connected
    def start_acquisition(
        self: Tile12, start_time: Optional[int] = None, delay: int = 2
    ) -> None:
        """
        Start data acquisition.

        :param start_time: Time for starting (frames)
        :param delay: delay after start_time (frames)
        """
        assert self.tpm is not None  # for the type checker
        devices = ["fpga1", "fpga2"]
        for f in devices:
            self.tpm[f + ".regfile.eth10g_ctrl"] = 0x0

        # Temporary (moved here from TPM control)
        if len(self.tpm.find_register("fpga1.regfile.c2c_stream_header_insert")) > 0:
            self.tpm["fpga1.regfile.c2c_stream_header_insert"] = 0x1
            self.tpm["fpga2.regfile.c2c_stream_header_insert"] = 0x1
        else:
            self.tpm["fpga1.regfile.c2c_stream_ctrl.header_insert"] = 0x1
            self.tpm["fpga2.regfile.c2c_stream_ctrl.header_insert"] = 0x1

        if len(self.tpm.find_register("fpga1.regfile.lmc_stream_demux")) > 0:
            self.tpm["fpga1.regfile.lmc_stream_demux"] = 0x1
            self.tpm["fpga2.regfile.lmc_stream_demux"] = 0x1

        for f in devices:
            # Disable start force (not synchronised start)
            self.tpm[f + ".pps_manager.start_time_force"] = 0x0
            self.tpm[f + ".lmc_gen.timestamp_force"] = 0x0

        # Read current sync time
        if start_time is None:
            t0 = self.tpm["fpga1.pps_manager.curr_time_read_val"]
        else:
            t0 = start_time

        sync_time = t0 + delay
        # Write start time
        for station_beamformer in self.tpm.station_beamf:
            station_beamformer.set_epoch(sync_time)
        for f in devices:
            self.tpm[f + ".pps_manager.sync_time_val"] = sync_time

    @staticmethod
    def calculate_delay(
        current_delay: int, current_tc: int, ref_low: int, ref_hi: int
    ) -> int:
        """
        Calculate delay for PPS pulse.

        :param current_delay: Current delay
        :param current_tc: Current phase register terminal count
        :param ref_low: Low reference
        :param ref_hi: High reference

        :return: Modified phase register terminal count
        """
        for n in range(5):
            if current_delay <= ref_low:
                new_delay = current_delay + int((n * 40) / 5)
                new_tc = (current_tc + n) % 5
                if new_delay >= ref_low:
                    return new_tc
            elif current_delay >= ref_hi:
                new_delay = current_delay - int((n * 40) / 5)
                new_tc = current_tc - n
                if new_tc < 0:
                    new_tc += 5
                if new_delay <= ref_hi:
                    return new_tc
            else:
                return current_tc
        return current_tc

    # --------------- Wrapper for data acquisition: ------------------------------------

    @connected
    def configure_integrated_channel_data(
        self: Tile12,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Configure and start continuous integrated channel data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        assert self.tpm is not None  # for the type checker
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure_parameters(
                "channel",
                integration_time,
                first_channel,
                last_channel,
                time_mux_factor=2,
                carousel_enable=1,
            )

    @connected
    def configure_integrated_beam_data(
        self: Tile12,
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
        assert self.tpm is not None  # for the type checker
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure_parameters(
                "beamf",
                integration_time,
                first_channel,
                last_channel,
                time_mux_factor=1,
                carousel_enable=0,
            )

    @connected
    def stop_integrated_data(self: Tile12) -> None:
        """Stop transmission of integrated data."""
        assert self.tpm is not None  # for the type checker
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_data()

    @connected
    def send_raw_data(
        self: Tile12,
        sync: bool = False,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send raw data from the TPM.

        :param sync: Get synchronised
        :param timestamp: When to start. Default now.
        :param seconds: delay with respect to timestamp, in seconds
        """
        assert self.tpm is not None  # for the type checker
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(seconds=seconds, timestamp=timestamp)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            if sync:
                self.tpm.tpm_test_firmware[i].send_raw_data_synchronised()
            else:
                self.tpm.tpm_test_firmware[i].send_raw_data()

    @connected
    def send_channelised_data(
        self: Tile12,
        number_of_samples: int = 1024,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send channelised data from the TPM.

        :param number_of_samples: number of spectra to send
        :param first_channel: first channel to send
        :param last_channel: last channel to send
        :param timestamp: when to start(?)
        :param seconds: when to synchronise
        """
        assert self.tpm is not None  # for the type checker
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data(
                number_of_samples, first_channel, last_channel
            )

    @connected
    def send_beam_data(
        self: Tile12, timestamp: Optional[str] = None, seconds: float = 0.2
    ) -> None:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?)
        :param seconds: when to synchronise
        """
        assert self.tpm is not None  # for the type checker
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_beam_data()

    @connected
    def send_channelised_data_continuous(
        self: Tile12,
        channel_id: int,
        number_of_samples: int = 128,
        wait_seconds: float = 0.0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit data from a channel continuously.

        It can be stopped with stop_data_transmission.

        :param channel_id: index of channel to send
        :param number_of_samples: number of spectra to send
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start(?)
        :param seconds: when to synchronise
        """
        assert self.tpm is not None  # for the type checker
        time.sleep(wait_seconds)
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data_continuous(
                channel_id, number_of_samples
            )

    @connected
    def stop_data_transmission(self: Tile12) -> None:
        """Stop all data transmission from TPM."""
        for k, v in self._daq_threads.items():
            if v == self._RUNNING:
                self._daq_threads[k] = self._STOP
        self.stop_channelised_data_continuous()

    @connected
    def send_channelised_data_narrowband(
        self: Tile12,
        frequency: int,
        round_bits: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Send channelised data from a single channel.

        :param frequency: sky frequency to transmit
        :param round_bits: which bits to round
        :param number_of_samples: number of spectra to send
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start
        :param seconds: when to synchronise
        """
        assert self.tpm is not None  # for the type checker
        time.sleep(wait_seconds)
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data_narrowband(
                frequency, round_bits, number_of_samples
            )

    # ---------------------------- Wrapper for test generator ----------------------------
    @connected
    def set_test_generator_tone(
        self: Tile12,
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
        :param amplitude: Tone peak amplitude, normalized to 31.875 ADC units, resolution 0.125 ADU
        :param phase: Initial tone phase, in turns
        :param load_time: Time to start the tone.
        """
        assert self.tpm is not None  # for the type checker
        delay = 128
        if load_time == 0:
            t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
            load_time = t0 + delay
        self.tpm.test_generator[0].set_tone(
            generator, frequency, amplitude, phase, load_time
        )
        self.tpm.test_generator[1].set_tone(
            generator, frequency, amplitude, phase, load_time
        )

    @connected
    def set_test_generator_noise(
        self: Tile12, amplitude: float = 0.0, load_time: int = 0
    ) -> None:
        """
        Test generator Gaussian white noise setting.

        :param amplitude: Tone peak amplitude, normalized to 26.03 ADC units, resolution 0.102 ADU
        :param load_time: Time to start the tone.
        """
        assert self.tpm is not None  # for the type checker
        if load_time == 0:
            t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
            load_time = t0 + 128
        self.tpm.test_generator[0].enable_prdg(amplitude, load_time)
        self.tpm.test_generator[1].enable_prdg(amplitude, load_time)

    @connected
    def set_test_generator_pulse(
        self: Tile12, freq_code: int, amplitude: float = 0.0
    ) -> None:
        """
        Test generator Gaussian white noise setting.

        :param freq_code: Code for pulse frequency. Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude: Tone peak amplitude, normalized to 127.5 ADC units, resolution 0.5 ADU
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.test_generator[0].set_pulse_frequency(freq_code, amplitude)
        self.tpm.test_generator[1].set_pulse_frequency(freq_code, amplitude)

    @connected
    def test_generator_input_select(self: Tile12, inputs: int) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit
        mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        """
        assert self.tpm is not None  # for the type checker
        self.tpm.test_generator[0].channel_select(inputs & 0xFFFF)
        self.tpm.test_generator[1].channel_select((inputs >> 16) & 0xFFFF)

    # ------------------------ Wrapper for index and attribute methods ---------------
    def __str__(self: Tile12) -> str:
        """
        Produce a list of tile information.

        :return: Information string
        """
        assert self.tpm is not None  # for the type checker
        return str(self.tpm)

    def __getitem__(self: Tile12, key: str | int) -> int | list[int]:
        """
        Read a register using indexing syntax: value=tile['registername'].

        :param key: register address, symbolic or numeric

        :return: indexed register content
        """
        assert self.tpm is not None  # for the type checker
        return self.tpm[key]

    def __setitem__(self: Tile12, key: str | int, value: int | list[int]) -> None:
        """
        Set a register to a value.

        :param key: register address, symbolic or numeric
        :param value: value to be written into register
        """
        assert self.tpm is not None  # for the type checker
        self.tpm[key] = value

    def __getattr__(self: Tile12, name: str) -> Any:
        """
        Handle any requested attribute not found in the usual way.

        Tries to return the corresponding attribute of the connected TPM.

        :param name: name of the requested attribute

        :raises AttributeError: if neither this class nor the TPM has
            the named attribute.

        :return: the requested attribute
        """
        assert self.tpm is not None  # for the type checker
        if name in dir(self.tpm):
            return getattr(self.tpm, name)
        else:
            raise AttributeError("'Tile' or 'TPM' object have no attribute " + name)

    # ------------------- Test methods
    @connected
    def check_jesd_lanes(self: Tile12) -> bool:
        """
        Check if JESD204 lanes are error free.

        :return: true if all OK
        """
        rd = np.zeros(4, dtype=int)
        rd[0] = self["fpga1.jesd204_if.core_id_0_link_error_status_0"]
        rd[1] = self["fpga1.jesd204_if.core_id_1_link_error_status_0"]
        rd[2] = self["fpga2.jesd204_if.core_id_0_link_error_status_0"]
        rd[3] = self["fpga2.jesd204_if.core_id_1_link_error_status_0"]

        lane_ok = True
        for n in range(4):
            for c in range(8):
                if rd[n] & 0x7 != 0:
                    self.logger.error(
                        "Lane %s error detected! Error code: %d"
                        % (str(n * 8 + c), rd[n] & 0x7)
                    )
                    lane_ok = False
                rd[n] = rd[n] >> 3
        return lane_ok

    def reset_jesd_error_counter(self: Tile12) -> None:
        """Reset errors in JESD lanes."""
        self["fpga1.jesd204_if.core_id_0_error_reporting"] = 1
        self["fpga1.jesd204_if.core_id_1_error_reporting"] = 1
        self["fpga2.jesd204_if.core_id_0_error_reporting"] = 1
        self["fpga2.jesd204_if.core_id_1_error_reporting"] = 1

        self["fpga1.jesd204_if.core_id_0_error_reporting"] = 0
        self["fpga1.jesd204_if.core_id_1_error_reporting"] = 0
        self["fpga2.jesd204_if.core_id_0_error_reporting"] = 0
        self["fpga2.jesd204_if.core_id_1_error_reporting"] = 0

        self["fpga1.jesd204_if.core_id_0_error_reporting"] = 1
        self["fpga1.jesd204_if.core_id_1_error_reporting"] = 1
        self["fpga2.jesd204_if.core_id_0_error_reporting"] = 1
        self["fpga2.jesd204_if.core_id_1_error_reporting"] = 1

    def check_jesd_error_counter(self: Tile12, show_result: bool = True) -> list[int]:
        """
        Check JESD204 lanes errors.

        :param show_result: prints error counts on logger

        :return: error count vector
        """
        errors = []
        for lane in range(32):
            fpga_id = lane / 16
            core_id = (lane % 16) / 8
            lane_id = lane % 8
            reg = cast(
                int,
                self[
                    "fpga%d.jesd204_if.core_id_%d_lane_%d_link_error_count"
                    % (fpga_id + 1, core_id, lane_id)
                ],
            )
            errors.append(reg)
            if show_result:
                self.logger.info("Lane " + str(lane) + " error count " + str(reg))
        return errors

    def download_firmware(self: Tile12, device: int, bitfile: str) -> None:
        """
        Download bitfile to FPGA.

        :param device: FPGA to download bitfile
        :param bitfile: Bitfile to download

        :raises LibraryError: if the TPM is not connected
        """
        assert self.tpm is not None  # for the type checker
        # Check if connected
        if cast(int, self.tpm.status[Device.Board]) != Status.OK:
            raise LibraryError("TPM needs to be connected in order to program FPGAs")

        required_cpld_version = 0x17041801
        cpld_version = cast(int, self[0x30000000])
        if cpld_version < required_cpld_version or cpld_version & 0xF0 == 0xB0:
            self.logger.error(
                "CPLD firmware version is too old. Required version is "
                + hex(required_cpld_version)
            )
            raise LibraryError(
                "CPLD firmware version is too old. Required version is "
                + hex(required_cpld_version)
            )

        # Disable C2C stream
        self[0x30000018] = 0x0

        # Select FPGAs to program
        self.tpm.smap_deselect_fpga([0, 1])
        self[self.tpm._global_register] = 0x3

        # Erase FPGAs SRAM
        self.tpm.erase_fpga(force=True)

        # Read bitstream
        with open(bitfile, "rb") as fp:
            data = fp.read()

        self.tpm.smap_select_fpga([0, 1])
        self[self.tpm._global_register] = 0x2

        # Read bitfile and cast as a list of unsigned integers
        # Cast in pieces to save memory
        bitfile_length = len(data)

        # Check if ucp_smap_write is supported
        start = time.time()
        if cast(int, self[0x30000000]) >= 0x18050200:
            self.logger.info("FPGA programming using fast SelectMap write")
            packet_size = 65536
            num = int(np.floor(bitfile_length / float(packet_size)))
            for i in range(num):
                formatted_data = list(
                    struct.unpack_from(
                        "I" * (packet_size // 4),
                        data[i * packet_size : (i + 1) * packet_size],
                    )
                )
                self.tpm._protocol.select_map_program(formatted_data)
            remaining = bitfile_length - packet_size * num
            formatted_data = list(
                struct.unpack_from("I" * (remaining // 4), data[num * packet_size :])
            )
            self.tpm._protocol.select_map_program(formatted_data)
        else:
            # Write bitfile to FPGA
            self.logger.info("FPGA programming using UCP write")

            packet_size = 1024
            num = int(np.floor(bitfile_length / float(packet_size)))

            fifo_register = 0x50001000
            for i in range(num):
                formatted_data = list(
                    struct.unpack_from(
                        "I" * (packet_size // 4),
                        data[i * packet_size : (i + 1) * packet_size],
                    )
                )
                self[fifo_register] = formatted_data
            remaining = bitfile_length - packet_size * num
            formatted_data = list(
                struct.unpack_from("I" * (remaining // 4), data[num * packet_size :])
            )
            self[fifo_register] = formatted_data

        end = time.time()
        self.logger.info("FPGA programming time: " + str(end - start) + "s")

        # Wait for operation to complete
        status_read = 0
        for xil_register in self.tpm._xil_registers:
            while cast(int, self[xil_register]) & 0x2 != 0x2:  # DONE high
                time.sleep(0.01)
                status_read += 1
                if status_read == 100:
                    self.logger.error(
                        "Not possible to program the FPGAs. Power cycle the board!"
                    )
                    break

        end = time.time()
        self.logger.info("FPGA programming time: " + str(end - start) + "s")

        self.tpm.smap_deselect_fpga([0, 1])
        self[self._global_register] = 0x3
        self.tpm_communication_check()

    def tpm_communication_check(self: Tile12) -> None:
        """Brute force check to make sure we can communicate with programmed TPM."""
        assert self.tpm is not None  # for the type checker
        for _n in range(4):
            try:
                self.tpm.calibrate_fpga_to_cpld()
                magic0 = cast(int, self[0x4])
                magic1 = cast(int, self[0x10000004])
                if magic0 == magic1 == 0xA1CE55AD:
                    return
                else:
                    self.logger.info(
                        "FPGA magic numbers are not correct %s, %s"
                        % (hex(magic0), hex(magic1))
                    )
            except Exception as e:  # noqa: F841
                pass

            self.logger.info(
                "Not possible to communicate with the FPGAs. Resetting CPLD..."
            )
            self.tpm.write_address(0x30000008, 0x8000, retry=False)  # Global Reset CPLD
            time.sleep(0.2)
            self.tpm.write_address(0x30000008, 0x8000, retry=False)  # Global Reset CPLD
            time.sleep(0.2)

    def get_firmware_list(self: Tile12) -> list[dict[str, Any]]:
        """
        Get information for loaded firmware.

        :return: Firmware information dictionary for each loaded firmware
        """
        # Got through all firmware information plugins and extract information
        # If firmware is not yet loaded, fill in some dummy information
        firmware = []
        if not hasattr(self.tpm, "tpm_firmware_information"):
            for _i in range(3):
                firmware.append(
                    {
                        "design": "unknown",
                        "major": 0,
                        "minor": 0,
                        "build": 0,
                        "time": "",
                        "author": "",
                        "board": "",
                    }
                )
        else:
            assert self.tpm is not None  # for the type checker
            for plugin in self.tpm.tpm_firmware_information:
                # Update information
                plugin.update_information()
                # Check if design is valid:
                if plugin.get_design() is not None:
                    firmware.append(
                        {
                            "design": plugin.get_design(),
                            "major": plugin.get_major_version(),
                            "minor": plugin.get_minor_version(),
                            "build": plugin.get_build(),
                            "time": plugin.get_time(),
                            "author": plugin.get_user(),
                            "board": plugin.get_board(),
                        }
                    )
        return firmware
