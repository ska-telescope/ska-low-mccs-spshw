# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
Hardware functions for the TPM 1.6 hardware.

This is derived from pyaavs.Tile object and depends heavily on the
pyfabil low level software and specific hardware module plugins.
"""

from __future__ import annotations  # allow forward references in type hints

import functools
import logging
import os
from typing import Callable, Optional

from pyfabil.base.definitions import Device, LibraryError, BoardError
from pyfabil.base.utils import ip2long
from pyfabil.boards.tpm_1_6 import TPM_1_6
from ska_low_mccs.tile import Tile12


# Helper to disallow certain function calls on unconnected tiles
def connected(f: Callable) -> Callable:
    """
    Help to disallow certain function calls on unconnected tiles.

    :param f: the method wrapped by this helper

    :return: the wrapped method
    """

    @functools.wraps(f)
    def wrapper(self: Tile16, *args: list, **kwargs: dict) -> object:
        """
        Check the TPM is connected before allowing the wrapped method to proceed.

        :param self: the method called
        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :raises LibraryError: if the TPM is not connected

        :return: whatever the wrapped method returns
        """
        if self.tpm is None:
            logging.warn("Cannot call function " + f.__name__ + " on unconnected TPM")
            raise LibraryError(
                "Cannot call function " + f.__name__ + " on unconnected TPM"
            )
        else:
            return f(self, *args, **kwargs)

    return wrapper


class Tile16(Tile12):
    """
    Tile hardware interface library. Methods specific for TPM 1.6.

    Streamlined and edited version of the AAVS Tile object
    """

    def __init__(
        self: Tile16,
        ip: str,
        port: int = 10000,
        lmc_ip: str = "0.0.0.0",
        lmc_port: int = 4660,
        sampling_rate: float = 800e6,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize a new Tile16 instance.

        :param ip: IP address of the hardware
        :param port: UCP Port address of the hardware port
        :param lmc_ip: IP address of the MCCS DAQ recevier
        :param lmc_port: UCP Port address of the MCCS DAQ receiver
        :param sampling_rate: ADC sampling rate
        :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
        """
        super(Tile16, self).__init__(ip, port, lmc_ip, lmc_port, sampling_rate, logger)

    # Main functions ------------------------------------
    def tpm_version(self: Tile16) -> str:
        """
        Determine whether this is a TPM V1.2 or TPM V1.6.

        :return: TPM hardware version
        """
        return "tpm_v1_6"

    def connect(
        self: Tile16,
        initialise: bool = False,
        load_plugin: bool = True,
        enable_ada: bool = False,
        enable_adc: bool = True,
        dsp_core: bool = True,
    ) -> None:
        """
        Connect to the hardware and loads initial configuration.

        :param initialise: Initialises the TPM object
        :param load_plugin: loads software plugins
        :param enable_ada: Enable ADC amplifier (usually not present)
        :param enable_adc: Enable ADC
        :param dsp_core: Enable loading of DSP core plugins
        """
        # Try to connect to board, if it fails then set tpm to None
        self.tpm = TPM_1_6()

        # Add plugin directory (load module locally)
        tf = __import__(
            "ska_low_mccs.tile.plugins.tpm_1_6.tpm_test_firmware", fromlist=[""]
        )
        self.tpm.add_plugin_directory(os.path.dirname(tf.__file__))

        try:
            self.tpm.connect(
                ip=self._ip,
                port=self._port,
                initialise=initialise,
                simulator=not load_plugin,
                enable_ada=enable_ada,
                enable_adc=enable_adc,
                fsample=self._sampling_rate,
            )
        except (BoardError, LibraryError):
            self.tpm = None
            self.logger.error("Failed to connect to board at " + self._ip)
            return
        # Load tpm test firmware for both FPGAs (no need to load in simulation)
        if load_plugin and self.tpm.is_programmed():
            self.tpm.load_plugin(
                "Tpm16TestFirmware",
                device=Device.FPGA_1,
                fsample=self._sampling_rate,
                dsp_core=dsp_core,
            )
            self.tpm.load_plugin(
                "Tpm16TestFirmware",
                device=Device.FPGA_2,
                fsample=self._sampling_rate,
                dsp_core=dsp_core,
            )
        elif not self.tpm.is_programmed():
            logging.warning("TPM is not programmed! No plugins loaded")

    def initialise(
        self: Tile16,
        enable_ada: bool = False,
        enable_test: bool = False,
        enable_adc: bool = True,
    ) -> None:
        """
        Connect and initialise.

        :param enable_ada: enable adc amplifier, Not present in most TPM versions
        :param enable_test: setup internal test signal generator instead of ADC
        :param enable_adc: Enable ADC
        """
        assert self.tpm is not None  # for the type checker
        # Connect to board
        self.connect(initialise=True, enable_ada=enable_ada, enable_adc=enable_adc)

        # Before initialing, check if TPM is programmed
        if not self.tpm.is_programmed():
            logging.error("Cannot initialise board which is not programmed")
            return

        # Disable debug UDP header
        self.tpm["board.regfile.ena_header"] = 0x1

        # Initialise firmware plugin
        for firmware in self.tpm.tpm_test_firmware:
            firmware.initialise_firmware()

        # Set LMC IP
        self.tpm.set_lmc_ip(self._lmc_ip, self._lmc_port)

        # Enable C2C streaming
        self.tpm["board.regfile.ena_stream"] = 0x1
        # self.tpm['board.regfile.ethernet_pause']=10000
        self.set_c2c_burst()

        # Synchronise FPGAs
        self.sync_fpgas()

        # Initialize f2f link
        for f2f in self.tpm.tpm_f2f:
            f2f.assert_reset()
        for f2f in self.tpm.tpm_f2f:
            f2f.deassert_reset()

        # Reset test pattern generator
        self.tpm.test_generator[0].channel_select(0x0000)
        self.tpm.test_generator[1].channel_select(0x0000)
        self.tpm.test_generator[0].disable_prdg()
        self.tpm.test_generator[1].disable_prdg()

        # Use test_generator plugin instead!
        if enable_test:
            # Test pattern. Tones on channels 72 & 75 + pseudo-random noise
            logging.info("Enabling test pattern")
            for generator in self.tpm.test_generator:
                generator.set_tone(0, 72 * self._sampling_rate / 1024, 0.0)
                generator.enable_prdg(0.4)
                generator.channel_select(0xFFFF)

        self.fortyg_cores_destination()

        for firmware in self.tpm.tpm_test_firmware:
            firmware.check_ddr_initialisation()

        # Set channeliser truncation
        self.logger.info("Configuring channeliser and beamformer")
        self.set_channeliser_truncation(self._channeliser_truncation)

        self.logger.info("Setting data acquisition")
        self.start_acquisition()

    def fortyg_core_destination(self: Tile16) -> None:
        """
        Set destination and source IP/MAC/ports for 10G cores.

        This will create a loopback between the two FPGAs
        """
        assert self.tpm is not None  # for the type checker
        ip_octets = self._ip.split(".")
        for n in range(len(self.tpm.tpm_10g_core)):
            src_ip = "10.10." + str(n + 1) + "." + str(ip_octets[3])
            # dst_ip = "10.{}.{}.{}".format((1 + n) + (4 if n < 4 else -4), ip_octets[2], ip_octets[3])
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

    def f2f_aurora_test_start(self: Tile16) -> None:
        """Start test on Aurora f2f link."""
        assert self.tpm is not None  # for the type checker
        for f2f in self.tpm.tpm_f2f:
            f2f.start_tx_test()
        for f2f in self.tpm.tpm_f2f:
            f2f.start_rx_test()

    def f2f_aurora_test_check(self: Tile16) -> None:
        """Get test results for Aurora f2f link Tests printed on stdout."""
        assert self.tpm is not None  # for the type checker
        for f2f in self.tpm.tpm_f2f:
            f2f.get_test_result()

    def f2f_aurora_test_stop(self: Tile16) -> None:
        """Stop test on Aurora f2f link."""
        assert self.tpm is not None  # for the type checker
        for f2f in self.tpm.tpm_f2f:
            f2f.stop_test()
