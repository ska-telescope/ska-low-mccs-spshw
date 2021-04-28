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
import time
from builtins import str
import numpy as np
import logging

from pyfabil.base.definitions import Device, LibraryError, BoardError
from pyfabil.boards.tpm import TPM


def connected(method):
    """
    Helper to disallow certain function calls on unconnected tiles.

    :param method: the method wrapped by this helper
    :type method: callable

    :return: the wrapped method
    :rtype: callable
    """

    @functools.wraps(method)
    def _wrapper(self, *args, **kwargs):
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
                "Cannot call function " + str(method.__name__) + " on unconnected TPM"
            )
            raise LibraryError(
                "Cannot call function " + str(method.__name__) + " on unconnected TPM"
            )
        else:
            return method(self, *args, **kwargs)

    return _wrapper


class HwTile(object):
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
        self._port = port
        self._ip = socket.gethostbyname(ip)
        self._channeliser_truncation = 4
        self.tpm = None

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
        # TODO These two lines do not work.
        # Somewhat there is some reference error
        # The tpm_test_firmware has been added to the tpm plugins
        # tf = __import__("ska_low_mccs.tile.tpm_test_firmware", fromlist=[None])
        # self.tpm.add_plugin_directory(os.path.dirname(tf.__file__))

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
        if load_plugin:
            if self.tpm.is_programmed():
                for device in [Device.FPGA_1, Device.FPGA_2]:
                    self.tpm.load_plugin(
                        "TpmTestFirmware",
                        device=device,
                        fsample=self._sampling_rate,
                        logger=self.logger,
                    )
            else:
                self.logger.warning("TPM is not programmed! No plugins loaded")

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
        # Before initialing, check if TPM is programmed
        if self.tpm is None or not self.tpm.is_programmed():
            self.logger.warning("Cannot initialise; board is not programmed")
            return

        # Connect to board
        self.connect(initialise=True, enable_ada=enable_ada)

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
        self.tpm.preadu[0].switch_off()
        self.tpm.preadu[1].switch_off()

        # Switch on preadu
        for preadu in self.tpm.preadu:
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
        # self.tpm["fpga1.jesd204_if.regfile_pol_switch"] = 0b00001111
        # self.tpm["fpga2.jesd204_if.regfile_pol_switch"] = 0b00001111

        # Reset test pattern generator
        self.tpm.test_generator[0].channel_select(0x0000)
        self.tpm.test_generator[1].channel_select(0x0000)
        self.tpm.test_generator[0].disable_prdg()
        self.tpm.test_generator[1].disable_prdg()

        # (TODO) Set destination and source IP/MAC/ports for 10G cores

        # (TODO) wait UDP link up

        # Initialise firmware plugin
        for firmware in self.tpm.tpm_test_firmware:
            firmware.initialise_firmware()

        # Set channeliser truncation
        self.logger.info("Configuring channeliser and beamformer")
        self.set_channeliser_truncation(self._channeliser_truncation)

        # TODO Configure continuous transmission of integrated channel and beam data

        # Initialise beamformer
        self.logger.info("Initialising beamformer")
        self.initialise_beamformer(
            start_channel=64,  # 50 MHz
            nof_channels=384,  # 300 MHz bandwidth
            is_first=False,  # usually a tile is not the first
            is_last=False,  # or the last in the station chain
        )
        self.set_first_last_tile(False, False)
        # TODO Use meaningful numbers instead of just magic
        self.define_spead_header(
            station_id=0, subarray_id=0, nof_antennas=16, ref_epoch=-1, start_time=0
        )
        # Do not start beamformer as default
        # self.start_beamformer(start_time=0, duration=-1)

        # Perform synchronisation
        self.post_synchronisation()

        self.logger.info("Setting data acquisition")
        self.start_acquisition()

    def program_fpgas(self, bitfile):
        """
        Program both FPGAs with specified firmware.

        :param bitfile: Bitfile to load
        :type bitfile: str
        """
        self.connect(load_plugin=False)
        if self.tpm is not None:
            self.logger.info("Downloading bitfile " + bitfile + " to board")
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
        # Current meter not implemented in hardware in TPM 1.2
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
        Get FPGA0 temperature
        :return: FPGA0 temperature
        :rtype: float
        """
        if self.is_programmed():
            return self.tpm.tpm_sysmon[1].get_fpga_temperature()
        else:
            return 0

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
        Get delay between PPS and 20 MHz clock
        :return: delay between PPS and 20 MHz clock in 200 MHz cycles
        :rtype: int
        """
        return self["fpga1.pps_manager.sync_phase.cnt_hf_pps"]

    @connected
    def wait_pps_event(self):
        """
        Wait for a PPS edge.

        :todo: Add a timeout feature, to avoid potential lock.

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

    @connected
    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams.

        Delay specified in nanoseconds, nominal is 0. Delay in samples,
        positive delay adds delay to the signal stream.

        :param delays: array of delays for each signal (2 signals per antenna)
        :type delays: list(float)
        :return: True on success, False on error
        :rtype: bool
        """

        # Compute maximum and minimum delay
        frame_length = (1.0 / self._sampling_rate) * 1e9
        min_delay = frame_length * -124
        max_delay = frame_length * 127

        self.logger.info(
            "frame_length = "
            + str(frame_length)
            + ", min_delay = "
            + str(min_delay)
            + ", max_delay = "
            + str(max_delay)
        )

        # Check that we have the correct numnber of delays (one or 16)
        if type(delays) in [float, int]:
            # Check that we have a valid delay
            if min_delay <= delays <= max_delay:
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
                "Invalid delays specfied (must be a number or a "
                "list of numbers of length 32)"
            )
            return False

        self.logger.info("Setting hardware delays = " + str(delays_hw))

        # Write delays to board
        self["fpga1.test_generator.delay_0"] = delays_hw[:16]
        self["fpga2.test_generator.delay_0"] = delays_hw[16:]
        return True

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
                self.logger.warning(
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
                self.logger.warning("Signal " + str(i) + " is outside range (0:31)")

    @connected
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

    @connected
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

    @connected
    def set_pointing_delay(self, delay_array, beam_index):
        """
        Specifies the delay in seconds and the delay rate in
        seconds/seconds.

        Delay is updated inside the delay engine at the time specified
        by method load_delay.

        :param delay_array: delay and delay rate for each antenna
        :type delay_array: list(list(float))
        :param beam_index: specifies which beam is described (range 0:7)
        :type beam_index: int
        """
        self.tpm.beamf_fd[0].set_delay(delay_array[0:8], beam_index)
        self.tpm.beamf_fd[1].set_delay(delay_array[8:], beam_index)

    @connected
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

    @connected
    def load_calibration_coefficients(self, antenna, calibration_coefficients):
        """
        Loads calibration coefficients.
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
        :param antenna: Antenna ID for the calibration coefficients
        :param calibration_coefficients: bi-dimensional complex array of coefficients
        """
        if antenna < 8:
            self.tpm.beamf_fd[0].load_calibration(antenna, calibration_coefficients)
        else:
            self.tpm.beamf_fd[1].load_calibration(antenna - 8, calibration_coefficients)

    @connected
    def load_antenna_tapering(self, beam, tapering_coefficients):
        """
        tapering_coefficients is a vector of 16 values, one per antenna.
        Default (at initialization) is 1.0.

        :param beam: Beam index (optional) in range 0:47
        :type beam: int
        :param tapering_coefficients: Coefficients for each antenna
        :type tapering_coefficients: list(int)
        """
        self.tpm.beamf_fd[0].load_antenna_tapering(tapering_coefficients[0:8])
        self.tpm.beamf_fd[1].load_antenna_tapering(tapering_coefficients[8:])

    @connected
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

        mask = 0xFFFFF8  # Impose a time multiple of 8 frames
        if self.beamformer_is_running():
            return False

        if start_time == 0:
            start_time = self.current_station_beamformer_frame() + 40

        start_time &= mask

        if duration != -1:
            duration = duration & mask

        ret1 = self.tpm.station_beamf[0].start(start_time, duration)
        ret2 = self.tpm.station_beamf[1].start(start_time, duration)

        if ret1 and ret2:
            return True
        else:
            # self.abort()
            return False

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
        Post tile configuration synchronization for PPS signal.
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
        t0, t1, t2 = 0, 0, 1
        while t0 != t2:
            t0 = self.tpm["fpga1.pps_manager.curr_time_read_val"]
            t1 = self.tpm["fpga2.pps_manager.curr_time_read_val"]
            t2 = self.tpm["fpga1.pps_manager.curr_time_read_val"]

        fpga = "fpga1" if t0 > t1 else "fpga2"
        for i in range(abs(t1 - t0)):
            self.logger.debug("Decrementing " + fpga + " by 1")
            self.tpm[fpga + ".pps_manager.curr_time_cmd.down_req"] = 0x1

    @connected
    def check_fpga_synchronization(self):
        """
        Checks various synchronization parameters.

        Output in the log

        :todo: Output in the return value.
        """
        # check PLL status
        pll_status = self.tpm["pll", 0x508]
        if pll_status == 0xE7:
            self.logger.debug("PLL locked to external reference clock.")
        elif pll_status == 0xF2:
            self.logger.warning("PLL locked to internal reference clock.")
        else:
            self.logger.error("PLL is not locked!")

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
        self.logger.debug("FPGA1 time is " + str(t0))
        self.logger.debug("FPGA2 time is " + str(t1))
        if t0 != t1:
            self.logger.warning("Time different between FPGAs detected!")

        # check FPGA timestamp
        t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        t1 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
        self.logger.info("FPGA1 timestamp is " + str(t0))
        self.logger.info("FPGA2 timestamp is " + str(t1))
        if abs(t0 - t1) > 1:
            self.logger.warning("Timestamp different between FPGAs detected!")

        # Check FPGA ring beamformer timestamp
        t0 = self.tpm["fpga1.beamf_ring.current_frame"]
        t1 = self.tpm["fpga2.beamf_ring.current_frame"]
        self.logger.info("FPGA1 beamformer timestamp is " + str(t0))
        self.logger.info("FPGA2 beamformer timestamp is " + str(t1))
        if abs(t0 - t1) > 1:
            self.logger.warning(
                "Beamformer timestamp different between FPGAs detected!"
            )

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
            time.sleep(2)

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
        delay = seconds * int((1.0 / 1080e-9) / 256)
        for fpga in self.tpm.tpm_fpga:
            fpga.fpga_apply_sync_delay(t0 + int(delay))

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

    # ------------------------ Wrapper for test generator ----------------------
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
        if load_time == 0:
            t0 = self.tpm["fpga1.pps_manager.timestamp_read_val"]
            load_time = t0 + 128
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

    # ------------------------ Wrapper for spigot generators ----------------------
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
                logging.warning("Packet length too large for 10G")
                return

            if lmc_mac is None:
                logging.warning("LMC MAC must be specified for 10G lane configuration")
                return

            # If dst_ip is None, use local lmc_ip
            if dst_ip is None:
                dst_ip = self._lmc_ip

            self.configure_10g_core(
                2, dst_mac=lmc_mac, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
            )

            self.configure_10g_core(
                6, dst_mac=lmc_mac, dst_ip=dst_ip, src_port=src_port, dst_port=dst_port
            )

            self["fpga1.lmc_gen.payload_length"] = payload_length
            self["fpga2.lmc_gen.payload_length"] = payload_length

            self["fpga1.lmc_gen.tx_demux"] = 2
            self["fpga2.lmc_gen.tx_demux"] = 2

        # Using dedicated 1G link
        elif mode.upper() == "1G":
            self["fpga1.lmc_gen.tx_demux"] = 1
            self["fpga2.lmc_gen.tx_demux"] = 1
            if dst_ip is not None:
                self.tpm.set_lmc_ip(dst_ip, dst_port)
        else:
            logging.warning("Supported modes are 1g, 10g")
            return

    def stop_data_transmission(self):
        """
        Stop sending channelised data.
        """
        for i in range(len(self.tpm.tpm_test_firmware)):
            self.tpm.tpm_test_firmware[i].stop_channelised_data_continuous()

    def stop_integrated_beam_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_beam_data()

    def stop_integrated_channel_data(self):
        """
        Stop transmission of integrated beam data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_channel_data()

    def stop_integrated_data(self):
        """
        Stop transmission of integrated data.
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].stop_integrated_data()

    @connected
    def send_raw_data(self, sync=False, timestamp=None, seconds=0.2):
        """
        send raw data from the TPM.

        :param timestamp: When to start. Default now.
        :type timestamp: int, optional
        :param seconds: delay with respect to timestamp, in seconds
        :type seconds: float, optional
        :param sync: Get synchronised
        :type sync: bool, optional
        """
        # Data transmission should be synchronised across FPGAs
        self.synchronised_data_operation(timestamp=timestamp, seconds=seconds)
        # Send data from all FPGAs
        for i in range(len(self.tpm.tpm_test_firmware)):
            if sync:
                self.tpm.tpm_test_firmware[i].send_raw_data_synchronised()
            else:
                self.tpm.tpm_test_firmware[i].send_raw_data()

    @connected
    def configure_integrated_channel_data(
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=512,
        time_mux_factor=2,
        carousel_enable=0x1,
    ):
        """
        Configure continuous integrated channel data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional
        :param time_mux_factor: TODO
        :type time_mux_factor: int, optional
        :param carousel_enable: TODO
        :type carousel_enable: optional
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure(
                "channel",
                integration_time,
                first_channel,
                last_channel,
                time_mux_factor,
                carousel_enable,
            )

    @connected
    def configure_integrated_beam_data(
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=192,
        time_mux_factor=1,
        carousel_enable=0x0,
    ):
        """
        Configure continuous integrated beam data.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional
        :param time_mux_factor: TODO
        :type time_mux_factor: int, optional
        :param carousel_enable: TODO
        :type carousel_enable: optional
        """
        for i in range(len(self.tpm.tpm_integrator)):
            self.tpm.tpm_integrator[i].configure(
                "beamf",
                integration_time,
                first_channel,
                last_channel,
                time_mux_factor,
                carousel_enable,
            )

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

    # ------------------------ Wrapper for index and attribute methods ---------------
    @connected
    def get_tile_id(self):
        """
        Get tile ID
        :return: station ID programmed in HW
        :rtype: int
        """
        if not self.tpm.is_programmed():
            return -1
        else:
            if len(self.tpm.find_register("fpga1.regfile.station_id")) > 0:
                tile_id = self["fpga1.regfile.tpm_id"]
            else:
                tile_id = self["fpga1.dsp_regfile.config_id.tpm_id"]
            return tile_id

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
            raise AttributeError(
                "'Tile' or 'TPM' object have no attribute " + str(name)
            )
