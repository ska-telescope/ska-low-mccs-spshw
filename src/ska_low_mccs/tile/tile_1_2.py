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
import functools
import socket
import os
import logging
import struct

import numpy as np
import time

from pyfabil.base.definitions import Device, LibraryError, BoardError, Status
from pyfabil.base.utils import ip2long
from pyfabil.boards.tpm import TPM


def connected(f):
    """
    Helper to disallow certain function calls on unconnected tiles.

    :param f: the method wrapped by this helper
    :type f: callable

    :return: the wrapped method
    :rtype: callable
    """

    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        """
        Wrapper that checks the TPM is connected before allowing the
        wrapped method to proceed.

        :param self: the method called
        :type self: object
        :param args: positional arguments to the wrapped method
        :type args: list
        :param kwargs: keyword arguments to the wrapped method
        :type kwargs: dict

        :raises LibraryError: if the TPM is not connected

        :return: whatever the wrapped method returns
        :rtype: object
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
        self,
        ip,
        port=10000,
        lmc_ip="0.0.0.0",
        lmc_port=4660,
        sampling_rate=800e6,
        logger=None,
    ):
        """
        HwTile initialization.

        :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
        :type logger: :py:class:`logging.Logger`
        :param ip: IP address of the hardware
        :type ip: str
        :param port: UCP Port address of the hardware port
        :type port: int
        :param lmc_ip: IP address of the MCCS DAQ recevier
        :type lmc_ip: str
        :param lmc_port: UCP Port address of the MCCS DAQ receiver
        :type lmc_port: int
        :param sampling_rate: ADC sampling rate
        :type sampling_rate: float
        """
        if logger is None:
            self.logger = logging.getLogger("")
        else:
            self.logger = logger
        self._lmc_port = lmc_port
        self._lmc_ip = socket.gethostbyname(lmc_ip)
        self._lmc_use_10g = False
        self._port = port
        self._ip = socket.gethostbyname(ip)
        self.tpm = None

        self._channeliser_truncation = 4
        self.subarray_id = 0
        self.station_id = 0
        self.tile_id = 0

        self._sampling_rate = sampling_rate

        # Threads for continuously sending data
        self._RUNNING = 2
        self._ONCE = 1
        self._STOP = 0
        self._daq_threads = {}

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
    def tpm_version(self):
        """
        Determine whether this is a TPM V1.2 or TPM V1.6
        :return: TPM hardware version
        :rtype: string
        """
        return "tpm_v1_2"

    def connect(self, initialise=False, load_plugin=True, enable_ada=False):
        """
        Connect to the hardware and loads initial configuration.

        :param initialise: Initialises the TPM object
        :type initialise: bool
        :param load_plugin: loads software plugins
        :type load_plugin: bool
        :param enable_ada: Enable ADC amplifier (usually not present)
        :type enable_ada: bool
        """
        # Try to connect to board, if it fails then set tpm to None
        self.tpm = TPM()

        # Add plugin directory (load module locally)
        tf = __import__(
            "ska_low_mccs.tile.plugins.tpm.tpm_test_firmware", fromlist=[None]
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
            self.logger.warn("TPM is not programmed! No plugins loaded")

    def is_programmed(self):
        """
        Check whether the TPM is connected and programmed.

        :return: If the TPM is programmed
        :rtype: bool
        """
        if self.tpm is None:
            return False
        return self.tpm.is_programmed()

    def initialise(self, enable_ada=False, enable_test=False):
        """
        Connect and initialise.

        :param enable_ada: enable adc amplifier, Not present in most TPM
            versions
        :type enable_ada: bool
        :param enable_test: setup internal test signal generator instead
            of ADC
        :type enable_test: bool
        """
        # Connect to board
        self.connect(initialise=True, enable_ada=enable_ada)

        # Before initialing, check if TPM is programmed
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

        # Set destination and source IP/MAC/ports for 40G cores
        # This will create a loopback between the two FPGAs
        ip_octets = self._ip.split(".")
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

        for firmware in self.tpm.tpm_test_firmware:
            firmware.check_ddr_initialisation()

<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
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

=======
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
    def program_fpgas(self, bitfile):
        """
        Program both FPGAs with specified firmware.

        :param bitfile: Bitfile to load
        :type bitfile: str
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
    def erase_fpga(self):
        """
        Erase FPGA configuration memory.
        """
        self.tpm.erase_fpga()

    def program_cpld(self, bitfile):
        """
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
        Program CPLD with specified bitfile. Use with VERY GREAT care,
        this might leave the FPGA in an unreachable state. TODO Wiser to
        leave the method out altogether and use a dedicated utility
        instead?
=======
        Program CPLD with specified bitfile.
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py

        :param bitfile: Bitfile to flash to CPLD

        :return: write status
        """
        self.connect(simulation=True)
        self.logger.info("Downloading bitstream to CPLD FLASH")
        if self.tpm is not None:
            return self.tpm.tpm_cpld.cpld_flash_write(bitfile)

    @connected
    def read_cpld(self, bitfile="cpld_dump.bit"):
        """
        Read bitfile in CPLD FLASH.

        :param bitfile: Bitfile where to dump CPLD firmware
        :type bitfile: str
        """
        self.logger.info("Reading bitstream from CPLD FLASH")
        self.tpm.tpm_cpld.cpld_flash_read(bitfile)

    def get_ip(self):
        """
        Get tile IP
        :return: tile IP address
        :rtype: str
        """
        return self._ip

    @connected
    def get_temperature(self):
        """
        Read board temperature
        :return: board temperature
        :rtype: float
        """
        return self.tpm.temperature()

    @connected
    def get_voltage(self):
        """
        Read board voltage
        :return: board supply voltage
        :rtype: float
        """
        return self.tpm.voltage()

    @connected
    def get_current(self):
        """
        Read board current
        :return: board supply current
        :rtype: float
        """
        # not implemented
        # return self.tpm.current()
        return 0.0

    @connected
    def get_adc_rms(self):
        """
        Get ADC power
        :return: ADC RMS power
        :rtype: list(float)
        """
        # If board is not programmed, return None
        if not self.tpm.is_programmed():
            return None

        # Get RMS values from board
        rms = []
        for adc_power_meter in self.tpm.adc_power_meter:
            rms.extend(adc_power_meter.get_RmsAmplitude())

        # Re-map values
        return rms

    @connected
    def get_fpga0_temperature(self):
        """
        Get FPGA0 temperature
        :return: FPGA0 temperature
        :rtype: float
        """
        if self.is_programmed():
            return self.tpm.tpm_sysmon[0].get_fpga_temperature()
        else:
            return 0

    @connected
    def get_fpga1_temperature(self):
        """
        Get FPGA1 temperature
        :return: FPGA0 temperature
        :rtype: float
        """
        if self.is_programmed():
            return self.tpm.tpm_sysmon[1].get_fpga_temperature()
        else:
            return 0

    @connected
    def configure_10g_core(
        self,
        core_id,
        src_mac=None,
        src_ip=None,
        dst_mac=None,
        dst_ip=None,
        src_port=None,
        dst_port=None,
    ):
        """
        Configure a 10G core TODO Legacy method. Checrki if it is to be
        deleted.

        :param core_id: 10G core ID
        :param src_mac: Source MAC address
        :param src_ip: Source IP address
        :param dst_mac: Destination MAC address
        :param dst_ip: Destination IP
        :param src_port: Source port
        :param dst_port: Destination port
        """
        # Configure core
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
        self,
        core_id,
        arp_table_entry=0,
        src_mac=None,
        src_ip=None,
        dst_ip=None,
        src_port=None,
        dst_port=None,
    ):
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
        if src_mac is not None:
            self.tpm.tpm_10g_core[core_id].set_src_mac(src_mac)
        if src_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_src_ip(src_ip)
        # if dst_mac is not None:
        #     self.tpm.tpm_10g_core[core_id].set_dst_mac(dst_mac)
        if dst_ip is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_ip(dst_ip, arp_table_entry)
        if src_port is not None:
            self.tpm.tpm_10g_core[core_id].set_src_port(src_port, arp_table_entry)
        if dst_port is not None:
            self.tpm.tpm_10g_core[core_id].set_dst_port(dst_port, arp_table_entry)
            self.tpm.tpm_10g_core[core_id].set_rx_port_filter(dst_port)

    @connected
    def get_10g_core_configuration(self, core_id):
        """
        Get the configuration for a 10g core TODO CHeck whether to be
        deleted.

        :param core_id: Core ID (0-7)
        :type core_id: int

        :return: core configuration
        :rtype: dict
        """
        return {
            "src_mac": int(self.tpm.tpm_10g_core[core_id].get_src_mac()),
            "src_ip": int(self.tpm.tpm_10g_core[core_id].get_src_ip()),
            "dst_ip": int(self.tpm.tpm_10g_core[core_id].get_dst_ip()),
            "dst_mac": int(self.tpm.tpm_10g_core[core_id].get_dst_mac()),
            "src_port": int(self.tpm.tpm_10g_core[core_id].get_src_port()),
            "dst_port": int(self.tpm.tpm_10g_core[core_id].get_dst_port()),
        }

    @connected
    def get_40g_core_configuration(self, core_id, arp_table_entry=0):
        """
        Get the configuration for a 40g core.

        :param core_id: Core ID
        :type core_id: int
        :param arp_table_entry: ARP table entry to use
        :type arp_table_entry: int

        :return: core configuration
        :rtype: dict
        """
        return {
            "src_mac": int(self.tpm.tpm_10g_core[core_id].get_src_mac()),
            "src_ip": int(self.tpm.tpm_10g_core[core_id].get_src_ip()),
            "dst_ip": int(self.tpm.tpm_10g_core[core_id].get_dst_ip(arp_table_entry)),
            "src_port": int(
                self.tpm.tpm_10g_core[core_id].get_src_port(arp_table_entry)
            ),
            "dst_port": int(
                self.tpm.tpm_10g_core[core_id].get_dst_port(arp_table_entry)
            ),
        }

    @connected
    def set_lmc_download(
        self,
        mode,
        payload_length=1024,
        dst_ip=None,
        src_port=0xF0D0,
        dst_port=4660,
        lmc_mac=None,
    ):
        """
        Configure link and size of control data.

        :param mode: 1g or 10g
        :param payload_length: SPEAD payload length in bytes
        :param dst_ip: Destination IP
        :param src_port: Source port for integrated data streams
        :param dst_port: Destination port for integrated data streams
        :param lmc_mac: LMC Mac address is required for 10G lane configuration
        """
        # Using 10G lane
        if mode.upper() == "10G":
            if payload_length >= 8193:
                self.logger.warning("Packet length too large for 10G")
                return

            if lmc_mac is None:
                self.logger.warning(
                    "LMC MAC must be specified for 10G lane configuration"
                )
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
        self,
        mode,
        channel_payload_length,
        beam_payload_length,
        dst_ip=None,
        src_port=0xF0D0,
        dst_port=4660,
        lmc_mac=None,
    ):
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
        # Using 10G lane
        if mode.upper() == "10G":
            if lmc_mac is None:
                self.logger.error(
                    "LMC MAC must be specified for 10G lane configuration"
                )
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
    def check_arp_table(self):
        """
        Check that ARP table has been populated in for all used cores
        40G interfaces use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for
        beamformer, 1 for LMC 10G interfaces use cores 0,1 (fpga0) and
        4,5 (fpga1) for beamforming, and 2, 6 for LMC with only one ARP.

        :return: if ARP table is populated
        :rtype: bool
        """
        # wait UDP link up
        if self["fpga1.regfile.feature.xg_eth_implemented"] == 1:
            self.logger.info("Checking ARP table...")
            if self.tpm.tpm_test_firmware[0].xg_40g_eth:
                core_id = [0, 1]
                if self._lmc_use_10g:
                    arp_table_id = [0, 1]
                else:
                    arp_table_id = [0]
            else:
                if self._lmc_use_10g:
                    core_id = [0, 1, 2, 4, 5, 6]
                else:
                    core_id = [0, 1, 4, 5]
                arp_table_id = [0]
            times = 0
            while True:
                linkup = True
                for c in core_id:
                    for a in arp_table_id:
                        core_status = self.tpm.tpm_10g_core[c].get_arp_table_status(
                            a, silent_mode=True
                        )
                    if core_status & 0x4 == 0:
                        linkup = False
                if linkup is False:
                    self.logger.info("10G Link established! ARP table populated!")
                    break
                else:
                    times += 1
                    time.sleep(0.1)
                    if times % 10 == 0:
                        self.logger.warning(
                            "10G Links not established after %d seconds! Waiting... "
                            % int(0.1 * times)
                        )
                    if times == 60:
                        self.logger.warning(
                            "10G Links not established after %d seconds! ARP table not populated!"
                            % int(0.5 * times)
                        )
                        break
        else:
            # time.sleep(2)
            self.logger.info("Sending dummy packets to populate switch ARP tables...")
            self.mii_exec_test(100, False)
            self["fpga1.regfile.eth10g_ctrl"] = 0x0
            self["fpga2.regfile.eth10g_ctrl"] = 0x0
            linkup = True
        return linkup

    @connected
    def set_station_id(self, station_id, tile_id):
        """
        Set station ID.

        :param station_id: Station ID
        :param tile_id: Tile ID within station
        """
        fpgas = ["fpga1", "fpga2"]
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
    def get_station_id(self):
        """
        Get station ID
        :return: station ID programmed in HW
        :rtype: int
        """
        if not self.tpm.is_programmed():
            return -1
        else:
            if len(self.tpm.find_register("fpga1.regfile.station_id")) > 0:
                tile_id = self["fpga1.regfile.station_id"]
            else:
                tile_id = self["fpga1.dsp_regfile.config_id.station_id"]
            return tile_id

    @connected
    def get_tile_id(self):
        """
        Get tile ID.

        :return: programmed tile id
        :rtype: int
        """
        if not self.tpm.is_programmed():
            return -1
        else:
            if len(self.tpm.find_register("fpga1.regfile.tpm_id")) > 0:
                tile_id = self["fpga1.regfile.tpm_id"]
            else:
                tile_id = self["fpga1.dsp_regfile.config_id.tpm_id"]
            return tile_id

    @connected
    def tweak_transceivers(self):
        """
        Tweak transceivers.
        """
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
    def get_fpga_time(self, device=Device.FPGA_1):
        """
        Return time from FPGA.

        :param device: FPGA to get time from
        :type device: int
        :return: Internal time for FPGA
        :rtype: int
        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return self["fpga1.pps_manager.curr_time_read_val"]
        elif device == Device.FPGA_2:
            return self["fpga2.pps_manager.curr_time_read_val"]
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def set_fpga_time(self, device, device_time):
        """
        Set Unix time in FPGA.

        :param device: FPGA to get time from
        :type device: int
        :param device_time: Internal time for FPGA
        :type device_time: int
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
    def get_fpga_timestamp(self, device=Device.FPGA_1):
        """
        Get timestamp from FPGA.

        :param device: FPGA to read timestamp from
        :type device: int
        :return: PPS time
        :rtype: int
        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return self["fpga1.pps_manager.timestamp_read_val"]
        elif device == Device.FPGA_2:
            return self["fpga2.pps_manager.timestamp_read_val"]
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def get_phase_terminal_count(self):
        """
        Get PPS phase terminal count
        :return: PPS phase terminal count
        :rtype: int
        """
        return self["fpga1.pps_manager.sync_tc.cnt_1_pulse"]

    @connected
    def set_phase_terminal_count(self, value):
        """
        Set phase terminal count.

        :param value: PPS phase terminal count
        """
        self["fpga1.pps_manager.sync_tc.cnt_1_pulse"] = value
        self["fpga2.pps_manager.sync_tc.cnt_1_pulse"] = value

    @connected
    def get_pps_delay(self):
        """
        Get delay between PPS and 10 MHz clock
        :return: delay between PPS and 10 MHz clock in 200 MHz cycles
        :rtype: int
        """
        return self["fpga1.pps_manager.sync_phase.cnt_hf_pps"]

    @connected
    def wait_pps_event(self):
        """
        Wait for a PPS edge. Added timeout feture to avoid method to
        stuck.

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
    def check_pending_data_requests(self):
        """
        Checks whether there are any pending data requests
        :return: true if pending requests are present
        :rtype: bool
        """
        return (self["fpga1.lmc_gen.request"] + self["fpga2.lmc_gen.request"]) > 0

    ########################################################
    # channeliser
    ########################################################
    @connected
    def set_channeliser_truncation(self, trunc, signal=None):
        """
        Set channeliser truncation scale for the whole tile.

        :param trunc: Truncted bits, channeliser output scaled down
        :type trunc: int
        :param signal: Input signal, 0 to 31. If None, apply to all
        :type signal: int
        """
        # if trunc is a single value, apply to all channels
        if type(trunc) == int:
            if 0 > trunc or trunc > 7:
                self.logger.warn(
                    "Could not set channeliser truncation to "
                    + str(trunc)
                    + ", setting to 0"
                )
                trunc = 0

            trunc_vec1 = 256 * [trunc]
            trunc_vec2 = 256 * [trunc]
        else:
            trunc_vec1 = trunc[0:256]
            trunc_vec2 = trunc[256:512]
            trunc_vec2.reverse()
        #
        # If signal is not specified, apply to all signals
        if signal is None:
            siglist = range(32)
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
                self.logger.warn("Signal " + str(i) + " is outside range (0:31)")

    @connected
    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams Delay specified in
        nanoseconds, nominal is 0.

        :param delays: Delay in samples, positive delay adds delay to the signal stream
        :type delays: list(float)

        :return: Parameters in range
        :rtype: bool
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
        if type(delays) in [float, int]:
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

        elif type(delays) is list and len(delays) == 32:
            # Check that all delays are valid
            delays = np.array(delays, dtype=np.float)
            if np.all(min_delay <= delays) and np.all(delays <= max_delay):
                delays_hw = np.clip(
                    (np.round(delays / frame_length) + 128).astype(np.int), 4, 255
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
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
    @connected
=======
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
    def initialise_beamformer(self, start_channel, nof_channels, is_first, is_last):
        """
        Initialise tile and station beamformers for a simple single beam
        configuration.

        :param start_channel: Initial channel, must be even
        :type start_channel: int
        :param nof_channels: Number of beamformed spectral channels
        :type nof_channels: int
        :param is_first: True for first tile in beamforming chain
        :type is_first: bool
        :param is_last: True for last tile in beamforming chain
        :type is_last: bool
        """
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

    def set_beamformer_regions(self, region_array):
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
        :type region_array: list(list(int))
        """
        self.tpm.beamf_fd[0].set_regions(region_array)
        self.tpm.beamf_fd[1].set_regions(region_array)
        self.tpm.station_beamf[0].defineChannelTable(region_array)
        self.tpm.station_beamf[1].defineChannelTable(region_array)

    def set_pointing_delay(self, delay_array, beam_index):
        """
        The method specifies the delay in seconds and the delay rate in
        seconds/seconds. The delay_array specifies the delay and delay
        rate for each antenna. beam_index specifies which beam is
        described (range 0:7). Delay is updated inside the delay engine
        at the time specified by method load_delay.

        :param delay_array: delay and delay rate for each antenna
        :type delay_array: list(list(float))
        :param beam_index: specifies which beam is described (range 0:7)
        :type beam_index: int
        """
        self.tpm.beamf_fd[0].set_delay(delay_array[0:8], beam_index)
        self.tpm.beamf_fd[1].set_delay(delay_array[8:], beam_index)

    def load_pointing_delay(self, load_time=0):
        """
        Delay is updated inside the delay engine at the time specified
        If time = 0 load immediately
        :param load_time: time (in ADC frames/256) for delay update
        :type load_time: int
        """
        if load_time == 0:
            load_time = self.current_tile_beamformer_frame() + 64

        self.tpm.beamf_fd[0].load_delay(load_time)
        self.tpm.beamf_fd[1].load_delay(load_time)

    def load_calibration_coefficients(self, antenna, calibration_coefs):
        """
        Loads calibration coefficients.
        calibration_coefs is a bi-dimensional complex array of the form
        calibration_coefs[channel, polarization], with each element representing
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
        :type antenna: int
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
        :param calibration_coefficients: Calibration coefficient array
        :type calibration_coefficients: list(float)
=======
        :param calibration_coefs: Calibration coefficient array
        :type calibration_coefs: list(float)
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
        """
        if antenna < 8:
            self.tpm.beamf_fd[0].load_calibration(antenna, calibration_coefs)
        else:
            self.tpm.beamf_fd[1].load_calibration(antenna - 8, calibration_coefs)

    def load_antenna_tapering(self, beam, tapering_coefficients):
        """
        tapering_coefficients is a vector of 16 values, one per antenna.
        Default (at initialization) is 1.0. TODO modify plugin to allow
        for different beams.

        :param beam: Beam index in range 0:47
        :type beam: int
        :param tapering_coefficients: Coefficients for each antenna
        :type tapering_coefficients: list(int)
        """
        if beam > 0:
            self.logger.warning("Tapering implemented only for beam 0")
        self.tpm.beamf_fd[0].load_antenna_tapering(tapering_coefficients[0:8])
        self.tpm.beamf_fd[1].load_antenna_tapering(tapering_coefficients[8:])

    def load_beam_angle(self, angle_coefficients):
        """
        Angle_coefficients is an array of one element per beam,
        specifying a rotation angle, in radians, for the specified beam.

        The rotation is the same for all antennas. Default is 0 (no
        rotation). A positive pi/4 value transfers the X polarization to
        the Y polarization. The rotation is applied after regular
        calibration.

        :param angle_coefficients: Rotation angle, per beam, in radians
        :type angle_coefficients: list(float)
        """
        self.tpm.beamf_fd[0].load_beam_angle(angle_coefficients)
        self.tpm.beamf_fd[1].load_beam_angle(angle_coefficients)

    def compute_calibration_coefficients(self):
        """
        Compute the calibration coefficients and load them in the
        hardware.
        """
        self.tpm.beamf_fd[0].compute_calibration_coefs()
        self.tpm.beamf_fd[1].compute_calibration_coefs()

    def switch_calibration_bank(self, switch_time=0):
        """
        Switches the loaded calibration coefficients at prescribed time
        If time = 0 switch immediately
        :param switch_time: time (in ADC frames/256) for delay update
        :type switch_time: int
        """
        if switch_time == 0:
            switch_time = self.current_tile_beamformer_frame() + 64

        self.tpm.beamf_fd[0].switch_calibration_bank(switch_time)
        self.tpm.beamf_fd[1].switch_calibration_bank(switch_time)

    def set_beamformer_epoch(self, epoch):
        """
        Set the Unix epoch in seconds since Unix reference time.

        :param epoch: Unix epoch for the reference time
        :return: Success status
        :rtype: bool
        """
        ret1 = self.tpm.station_beamf[0].set_epoch(epoch)
        ret2 = self.tpm.station_beamf[1].set_epoch(epoch)
        return ret1 and ret2

    def set_csp_rounding(self, rounding):
        """
        Set output rounding for CSP.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        :return: success status
        :rtype: bool
        """
        ret1 = self.tpm.station_beamf[0].set_csp_rounding(rounding)
        ret2 = self.tpm.station_beamf[1].set_csp_rounding(rounding)
        return ret1 and ret2

    def current_station_beamformer_frame(self):
        """
        Query time of packets at station beamformer input
        :return: current frame, in units of 256 ADC frames (276,48 us)
        :rtype: int
        """
        return self.tpm.station_beamf[0].current_frame()

    def current_tile_beamformer_frame(self):
        """
        Query time of packets at tile beamformer input
        :return: current frame, in units of 256 ADC frames (276,48 us)
        :rtype: int
        """
        return self.tpm.beamf_fd[0].current_frame()

    def set_first_last_tile(self, is_first, is_last):
        """
        Defines if a tile is first, last, both or intermediate.

        One, and only one tile must be first, and last, in a chain. A
        tile can be both (one tile chain), or none.

        :param is_first: True for first tile in beamforming chain
        :type is_first: bool
        :param is_last: True for last tile in beamforming chain
        :type is_last: bool
        :return: success status
        :rtype: bool
        """
        ret1 = self.tpm.station_beamf[0].set_first_last_tile(is_first, is_last)
        ret2 = self.tpm.station_beamf[1].set_first_last_tile(is_first, is_last)
        return ret1 and ret2

    def define_spead_header(
        self, station_id, subarray_id, nof_antennas, ref_epoch=-1, start_time=0
    ):
        """
        Define SPEAD header for last tile.

        All parameters are specified by the LMC.

        :param station_id: Station ID
        :param subarray_id: Subarray ID
        :param nof_antennas: Number of antenns in the station
        :type nof_antennas: int
        :param ref_epoch: Unix time of epoch. -1 uses value defined in set_epoch
        :type ref_epoch: int
        :param start_time: start time (TODO describe better)
        :return: True if parameters OK, False for error
        :rtype: bool
        """
        ret1 = self.tpm.station_beamf[0].define_spead_header(
            station_id, subarray_id, nof_antennas, ref_epoch, start_time
        )
        ret2 = self.tpm.station_beamf[1].define_spead_header(
            station_id, subarray_id, nof_antennas, ref_epoch, start_time
        )
        return ret1 and ret2

    def beamformer_is_running(self):
        """
        Check if station beamformer is running
        :return: beamformer running status
        :rtype: bool
        """
        return self.tpm.station_beamf[0].is_running()

    def start_beamformer(self, start_time=0, duration=-1):
        """
        Start the beamformer.

        Duration: if > 0 is a duration in frames * 256 (276.48 us)
        if == -1 run forever

        :param start_time: time (in ADC frames/256) for first frame sent
        :type start_time: int
        :param duration: duration in ADC frames/256. Multiple of 8
        :type duration: int
        :return: False for error (e.g. beamformer already running)
        :rtype bool:
        """
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
        mask = 0xFFFFF8  # Impose a time multiple of 8 frames
=======
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
        if self.beamformer_is_running():
            return False

        if start_time == 0:
            start_time = self.current_station_beamformer_frame() + 40

<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
        start_time &= mask  # Impose a start time multiple of 8 frames
=======
        start_time &= 0xFFFFFFF8  # Impose a start time multiple of 8 frames
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py

        if duration != -1:
            duration = duration & 0xFFFFFFF8

        ret1 = self.tpm.station_beamf[0].start(start_time, duration)
        ret2 = self.tpm.station_beamf[1].start(start_time, duration)

        if ret1 and ret2:
            return True
        else:
            self.abort()
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
            return False
=======

        return False
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py

    def stop_beamformer(self):
        """
        Stop beamformer.
        """
        self.tpm.station_beamf[0].abort()
        self.tpm.station_beamf[1].abort()
        return

    # Synchronisation routines ------------------------------------
    @connected
    def post_synchronisation(self):
        """
        Post tile configuration synchronization.
        """
        self.wait_pps_event()

        current_tc = self.get_phase_terminal_count()
        delay = self.get_pps_delay()

        self.set_phase_terminal_count(self.calculate_delay(delay, current_tc, 16, 24))

        self.wait_pps_event()

        delay = self.get_pps_delay()
        self.logger.info("Finished tile post synchronisation (" + str(delay) + ")")

    @connected
    def sync_fpgas(self):
        """
        Syncronises the two FPGAs in the tile Returns when these are
        synchronised.
        """
        devices = ["fpga1", "fpga2"]

        # Setting internal PPS generator
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
    def check_synchronization(self):
        """
        Checks FPGA synchronisation, returns when these are
        synchronised.
        """
        devices = ["fpga1", "fpga2"]

        for n in range(5):
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
    def check_fpga_synchronization(self):
        """
        Checks various synchronization parameters.

        Output in the log

        :return: OK status
        :rtype: bool
        """
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
    def set_c2c_burst(self):
        """
        Setting C2C burst when supported by FPGAs and CPLD.
        """
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
    def synchronised_data_operation(self, seconds=0.2, timestamp=None):
        """
        Synchronise data operations between FPGAs.

        :param seconds: Number of seconds to delay operation
        :param timestamp: Timestamp at which tile will be synchronised
        """
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
            t0 = timestamp
        else:
            t0 = max(
                self.tpm["fpga1.pps_manager.timestamp_read_val"],
                self.tpm["fpga2.pps_manager.timestamp_read_val"],
            )

        # Set arm timestamp
        # delay = number of frames to delay * frame time (shift by 8)
        delay = seconds * (1 / (1080 * 1e-9) / 256)
        t1 = t0 + int(delay)
        for fpga in self.tpm.tpm_fpga:
            fpga.fpga_apply_sync_delay(t1)

        tn1 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        tn2 = self.tpm["fpga2.pps_manager.timestamp_read_val"]
        if max(tn1, tn2) >= t1:
            self.logger.error("Synchronised operation failed!")

    @connected
    def synchronised_beamformer_coefficients(self, timestamp=None, seconds=0.2):
        """
        Synchronise beamformer coefficients download.

        :param timestamp: Timestamp to synchronise against
        :param seconds: Number of seconds to delay operation
        """

        # Read timestamp
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
    def start_acquisition(self, start_time=None, delay=2):
        """
        Start data acquisition.

        :param start_time: Time for starting (frames)
        :param delay: delay after start_time (frames)
        """

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
    def calculate_delay(current_delay, current_tc, ref_low, ref_hi):
        """
        Calculate delay for PPS pulse.

        :param current_delay: Current delay
        :type current_delay: int
        :param current_tc: Current phase register terminal count
        :type current_tc: int
        :param ref_low: Low reference
        :type ref_low: int
        :param ref_hi: High reference
        :type ref_hi: int
        :return: Modified phase register terminal count
        :rtype: int
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

    # --------------- Wrapper for data acquisition: ------------------------------------

    @connected
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
    def configure_integrated_channel_data(
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=511,
    ):
        """
        Configure and start continuous integrated channel data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional
        """
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
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=191,
    ):
        """
        Configure and start continuous integrated beam data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure(
                "beamf",
                integration_time,
                first_channel,
                last_channel,
                time_mux_factor=1,
                carousel_enable=0,
            )

    @connected
    def stop_integrated_beam_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_beam_data()

    @connected
    def stop_integrated_channel_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_channel_data()

    @connected
    def stop_integrated_data(self):
        """
        Stop transmission of integrated data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
=======
    def configure_integrated_channel_data(self, integration_time=0.5):
        """
        Configure continuous integrated channel data lmc integrator
        module will generate an integrated channel spectrum at end of
        each integration, until stop_integrated_channel_data() is
        issued.

        :param integration_time: integration time in seconds
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure(
                "channel",
                integration_time,
                first_channel=0,
                last_channel=512,
                time_mux_factor=2,
                carousel_enable=0x1,
            )

    @connected
    def configure_integrated_beam_data(self, integration_time=0.5):
        """
        Configure continuous integrated beam data lmc integrator module
        will generate an integrated channel spectrum at end of each
        integration, until stop_integrated_beam_data() is issued.

        :param integration_time: integration time in seconds
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure(
                "beamf",
                integration_time,
                first_channel=0,
                last_channel=192,
                time_mux_factor=1,
                carousel_enable=0x0,
            )

    @connected
    def stop_integrated_beam_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_beam_data()

    @connected
    def stop_integrated_channel_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_channel_data()

    @connected
    def stop_integrated_data(self):
        """
        Stop transmission of integrated data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
            self.tpm.tpm_integrator[i].stop_integrated_data()

    @connected
    def send_raw_data(self, sync=False, timestamp=None, seconds=0.2):
        """
        send raw data from the TPM.

        :param timestamp: When to start. Default now.
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py
        :type timestamp: int, optional
        :param seconds: delay with respect to timestamp, in seconds
        :type seconds: float, optional
        :param sync: Get synchronised
        :type sync: bool, optional
        """
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(secondsi=seconds, timestamp=timestamp)
=======
        :param seconds: delay with respect to timestamp, in seconds
        :param sync: Get synchronised packets
        """
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(seconds, timestamp)
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            if sync:
                self.tpm.tpm_test_firmware[i].send_raw_data_synchronised()
            else:
                self.tpm.tpm_test_firmware[i].send_raw_data()
<<<<<<< HEAD:src/ska_low_mccs/tile/tile_1_2.py

    @connected
    def send_channelised_data(
        self,
        number_of_samples=1024,
        first_channel=0,
        last_channel=511,
        timestamp=None,
        seconds=0.2,
    ):
        """
        send channelised data from the TPM.

        :param number_of_samples: number of spectra to send
        :type number_of_samples: int, optional
        :param first_channel: first channel to send
        :type first_channel: int, optional
        :param last_channel: last channel to send
        :type last_channel: int, optional
        :param timestamp: when to start(?)
        :type timestamp: int, optional
        :param seconds: when to synchronise
        :type seconds: float, optional
        """
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data(
                number_of_samples, first_channel, last_channel
            )

    @connected
    def send_beam_data(self, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?)
        :type timestamp: int, optional
        :param seconds: when to synchronise
        :type seconds: float, optional
        """
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_beam_data()

    @connected
    def send_channelised_data_continuous(
        self,
        channel_id,
        number_of_samples=128,
        wait_seconds=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Transmit data from a channel continuously.

        :param channel_id: index of channel to send
        :type channel_id: int
        :param number_of_samples: number of spectra to send
        :type number_of_samples: int, optional
        :param wait_seconds: wait time before sending data
        :type wait_seconds: float
        :param timestamp: when to start(?)
        :type timestamp: int, optional
        :param seconds: when to synchronise
        :type seconds: float, optional
        """
        time.sleep(wait_seconds)
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data_continuous(
                channel_id, number_of_samples
            )

    @connected
    def send_channelised_data_narrowband(
        self,
        frequency,
        round_bits,
        number_of_samples=128,
        wait_seconds=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Send channelised data from a single channel.

        :param frequency: sky frequency to transmit
        :type frequency: int
        :param round_bits: which bits to round
        :type round_bits: int
        :param number_of_samples: number of spectra to send
        :type number_of_samples: int, optional
        :param wait_seconds: wait time before sending data
        :type wait_seconds: int, optional
        :param timestamp: when to start
        :type timestamp: int, optional
        :param seconds: when to synchronise
        :type seconds: float, optional
        """
        time.sleep(wait_seconds)
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].send_channelised_data_narrowband(
                frequency, round_bits, number_of_samples
            )
=======
>>>>>>> f9e104a553397f78ce380de9245951ec78dd0ee0:src/ska_low_mccs/tile/hw_tile.py

    # ---------------------------- Wrapper for test generator ----------------------------
    @connected
    def set_test_generator_tone(
        self, generator, frequency=100e6, amplitude=0.0, phase=0.0, load_time=0
    ):
        """
        test generator tone setting.

        :param generator: generator select. 0 or 1
        :type generator: int
        :param frequency: Tone frequency in Hz
        :type frequency: float
        :param amplitude: Tone peak amplitude, normalized to 31.875 ADC units, resolution 0.125 ADU
        :type amplitude: float
        :param phase: Initial tone phase, in turns
        :type phase: float
        :param load_time: Time to start the tone.
        :type load_time: int
        """
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
    def set_test_generator_noise(self, amplitude=0.0, load_time=0):
        """
        test generator Gaussian white noise  setting.

        :param amplitude: Tone peak amplitude, normalized to 26.03 ADC units, resolution 0.102 ADU
        :type amplitude: float
        :param load_time: Time to start the tone.
        :type load_time: int
        """
        if load_time == 0:
            t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
            load_time = t0 + 128
        self.tpm.test_generator[0].enable_prdg(amplitude, load_time)
        self.tpm.test_generator[1].enable_prdg(amplitude, load_time)

    @connected
    def set_test_generator_pulse(self, freq_code, amplitude=0.0):
        """
        test generator Gaussian white noise  setting.

        :param freq_code: Code for pulse frequency. Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :type freq_code: int
        :param amplitude: Tone peak amplitude, normalized to 127.5 ADC units, resolution 0.5 ADU
        :type amplitude: float
        """
        self.tpm.test_generator[0].set_pulse_frequency(freq_code, amplitude)
        self.tpm.test_generator[1].set_pulse_frequency(freq_code, amplitude)

    @connected
    def test_generator_input_select(self, inputs):
        """
        Specify ADC inputs which are substitute to test signal.
        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        :type inputs: int
        """
        self.tpm.test_generator[0].channel_select(inputs & 0xFFFF)
        self.tpm.test_generator[1].channel_select((inputs >> 16) & 0xFFFF)

    # ------------------------ Wrapper for index and attribute methods ---------------
    def __str__(self):
        """
        Produces list of tile information
        :return: Information string
        :rtype: str
        """
        return str(self.tpm)

    def __getitem__(self, key):
        """
        Read a register using indexing syntax:
        value=tile['registername']

        :param key: register address, symbolic or numeric
        :type key: str
        :return: indexed register content
        :rtype: int
        """
        return self.tpm[key]

    def __setitem__(self, key, value):
        """
        Set a register to a value.

        :param key: register address, symbolic or numeric
        :type key: str
        :param value: value to be written into register
        :type value: int
        """
        self.tpm[key] = value

    def __getattr__(self, name):
        """
        Handler for any requested attribute not found in the usual way;
        tries to return the corresponding attribute of the connected
        TPM.

        :param name: name of the requested attribute
        :type name: str

        :raises AttributeError: if neither this class nor the TPM has
            the named attribute.

        :return: the requested attribute
        :rtype: object
        """
        if name in dir(self.tpm):
            return getattr(self.tpm, name)
        else:
            raise AttributeError("'Tile' or 'TPM' object have no attribute " + name)

    # ------------------- Test methods
    @connected
    def check_jesd_lanes(self):
        """
        check if JESD204 lanes are error free.

        :return: true if all OK
        :rtype: bool
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

    def reset_jesd_error_counter(self):
        """
        Reset errors in JESD lanes.
        """
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

    def check_jesd_error_counter(self, show_result=True):
        """
        check JESD204 lanes errors.

        :param show_result: prints error counts on logger
        :type show_result: bool
        :return: error count vector
        :rtype: list(int)
        """
        errors = []
        for lane in range(32):
            fpga_id = lane / 16
            core_id = (lane % 16) / 8
            lane_id = lane % 8
            reg = self[
                "fpga%d.jesd204_if.core_id_%d_lane_%d_link_error_count"
                % (fpga_id + 1, core_id, lane_id)
            ]
            errors.append(reg)
            if show_result:
                self.logger.info("Lane " + str(lane) + " error count " + str(reg))
        return errors

    def download_firmware(self, device, bitfile):
        """
        Download bitfile to FPGA.

        :param device: FPGA to download bitfile
        :param bitfile: Bitfile to download

        :raises LibraryError: if the TPM is not connected
        """
        # Check if connected
        if self.tpm.status[Device.Board] != Status.OK:
            raise LibraryError("TPM needs to be connected in order to program FPGAs")

        required_cpld_version = 0x17041801
        cpld_version = self[0x30000000]
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
        # formatted_data = list(struct.unpack_from('I' * (len(data) // 4), data))
        bitfile_length = len(data)

        # Check if ucp_smap_write is supported
        start = time.time()
        if self[0x30000000] >= 0x18050200:
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
            while self[xil_register] & 0x2 != 0x2:  # DONE high
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

        # Brute force check to make sure we can communicate with programmed TPM
        for n in range(4):
            try:
                self.tpm.calibrate_fpga_to_cpld()
                magic0 = self[0x4]
                magic1 = self[0x10000004]
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

    def get_firmware_list(self):
        """
        Get information for loaded firmware
        :return: Firmware information dictionary for each loaded firmware
        :rtype: list(dict)
        """
        # Got through all firmware information plugins and extract information
        # If firmware is not yet loaded, fill in some dummy information
        firmware = []
        if not hasattr(self.tpm, "tpm_firmware_information"):
            for i in range(3):
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
