# -*- coding: utf-8 -*-
"""
An implementation of a TPM driver.

The class is basically a wrapper around the HwTile class, in order to
have a consistent interface for driver and simulator. This is an initial
version. Some methods are still simulated. A warning is issued in this
case, or a NotImplementedError exception raised.
"""
import copy
import numpy as np

from ska.low.mccs.hardware import ConnectionStatus, HardwareDriver
from ska.low.mccs.tile import HwTile
from pyfabil.base.definitions import Device


class TpmDriver(HardwareDriver):
    """
    Hardware driver for a TPM.
    """

    # TODO Remove all unnecessary variables and constants after
    # all methods are completed and tested
    VOLTAGE = 4.7
    CURRENT = 0.4
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5
    ADC_RMS = tuple(float(i) for i in range(32))
    FPGA1_TIME = 1
    FPGA2_TIME = 2
    CURRENT_TILE_BEAMFORMER_FRAME = 23
    PPS_DELAY = 12
    PHASE_TERMINAL_COUNT = 0
    FIRMWARE_NAME = "tpm_test"
    FIRMWARE_AVAILABLE = {
        "tpm_test": {"design": "tpm_test", "major": 2, "minor": 3},
        "firmware2": {"design": "model2", "major": 3, "minor": 7},
        "firmware3": {"design": "model3", "major": 2, "minor": 6},
    }
    REGISTER_MAP = {
        0: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
        1: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
    }

    def __init__(self, logger, ip, port):
        """
        Initialise a new TPM driver instance.

        Tries to connect to the given IP and port.

        :param logger: a logger for this simulator to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface
        :param ip: IP address for hardware tile
        :type ip: str
        :param port: IP address for hardware tile control
        :type port: int
        """
        self.logger = logger
        self._is_programmed = False
        self._is_beamformer_running = False
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT

        self._tile_id = 0
        self._station_id = 0
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._board_temperature = self.BOARD_TEMPERATURE
        self._fpga1_temperature = self.FPGA1_TEMPERATURE
        self._fpga2_temperature = self.FPGA2_TEMPERATURE
        self._adc_rms = tuple(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._pps_delay = self.PPS_DELAY
        self._firmware_name = self.FIRMWARE_NAME
        self._firmware_available = copy.deepcopy(self.FIRMWARE_AVAILABLE)

        self._fpga1_time = self.FPGA1_TIME
        self._fpga2_time = self.FPGA2_TIME

        self._address_map = {}
        self._forty_gb_core_list = []
        self._register_map = copy.deepcopy(self.REGISTER_MAP)
        self._ip = ip
        self._port = port
        self.tile = HwTile(ip=self._ip, port=self._port, logger=self.logger)
        super().__init__()

    def _connect(self):
        self.tile.connect()
        return self.tile.tpm is not None

    @property
    def firmware_available(self):
        """
        Return the firmware list for this TPM simulator.

        :return: the firmware list
        :rtype: dict
        """
        self.logger.debug("TpmDriver: firmware_available")
        self.logger.info("TpmDriver: FirmwareAvailable method partially implemented")
        return copy.deepcopy(self._firmware_available)

    @property
    def firmware_name(self):
        """
        Return the name of the firmware that this TPM simulator is
        running.

        :return: firmware name
        :rtype: str
        """
        self.logger.debug("TpmDriver: firmware_name")
        return self._firmware_name

    @property
    def firmware_version(self):
        """
        Return the name of the firmware that this TPM simulator is
        running.

        :return: firmware version (major.minor)
        :rtype: str
        """
        self.logger.debug("TpmDriver: firmware_version")
        self.logger.info("TpmDriver: FirmwareVersion method partially implemented")
        firmware = self._firmware_available[self._firmware_name]
        return "{major}.{minor}".format(**firmware)  # noqa: FS002

    @property
    def is_programmed(self):
        """
        Return whether this TPM is programmed (i.e. firmware has been
        downloaded to it)

        :return: whether this TPM is programmed
        :rtype: bool
        """
        self.logger.debug(f"TpmDriver: is_programmed {self._is_programmed}")
        self._is_programmed = self.tile.tpm.is_programmed()
        return self._is_programmed

    @property
    def connection_status(self):
        """
        Returns the status of the driver-hardware connection.

        :return: the status of the driver-hardware connection.
        :rtype: py:class:`ska.low.mccs.hardware.ConnectionStatus`
        """
        self.logger.debug("TpmDriver: connection_status")
        return (
            ConnectionStatus.NOT_CONNECTED
            if self.tile.tpm is None
            else ConnectionStatus.CONNECTED
        )

    def download_firmware(self, bitfile):
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: a binary firmware blob
        :type bitfile: bytes
        """
        self.logger.debug("TpmDriver: download_firmware")
        self.tile.program_fpgas(bitfile + ".bit")
        self._firmware_name = bitfile
        self._is_programmed = True

    def cpld_flash_write(self, bitfile):
        """
        Flash a program to the tile's CPLD (complex programmable logic
        device).

        :param bitfile: the program to be flashed
        :type bitfile: bytes

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: program_cpld")
        raise NotImplementedError

    def initialise(self):
        """
        Download firmware, if not already downloaded, and initializes
        tile.
        """
        self.logger.debug("TpmDriver: initialise")
        if self.tile.tpm is None or not self.tile.tpm.is_programmed():
            self.tile.program_fpgas(self._firmware_name + ".bit")
        if self.tile.tpm.is_programmed():
            self._is_programmed = True
            self.tile.initialise()
        else:
            self.logger.error("TpmDriver: Cannot initialise board")

    @property
    def tile_id(self):
        """
        Tile ID
        :return: assigned tile Id value
        :rtype: int
        """
        return self._tile_id

    @tile_id.setter
    def tile_id(self, value):
        """
        Set Tile ID.

        :param value: assigned tile Id value
        :type value: int
        """
        self._tile_id = value
        self.tile.set_station_id(self._station_id, self._tile_id)

    @property
    def station_id(self):
        """
        Station ID
        :return: assigned station Id value
        :rtype: int
        """
        return self._station_id

    @station_id.setter
    def station_id(self, value):
        """
        Set Station ID.

        :param value: assigned station Id value
        :type value: int
        """
        self._station_id = value
        self.tile.set_station_id(self._station_id, self._tile_id)

    @property
    def board_temperature(self):
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        :rtype: float
        """
        self.logger.debug("TpmDriver: board_temperature")
        self._board_temperature = self.tile.get_temperature()
        return self._board_temperature

    @property
    def voltage(self):
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        :rtype: float
        """
        self.logger.debug("TpmDriver: voltage")
        self._voltage = self.tile.get_voltage()
        return self._voltage

    @property
    def current(self):
        """
        Return the current of the TPM.

        :return: the current of the TPM
        :rtype: float
        """
        self.logger.debug("TpmDriver: current")
        self._current = self.tile.get_current()
        return self._current

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        self.logger.debug("TpmDriver: fpga1_temperature")
        self._fpga1_temperature = self.tile.get_fpga0_temperature()
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        self.logger.debug("TpmDriver: fpga2_temperature")
        self._fpga2_temperature = self.tile.get_fpga1_temperature()
        return self._fpga2_temperature

    @property
    def adc_rms(self):
        """
        Return the RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        :rtype: list(float)
        """
        self.logger.debug("TpmDriver: adc_rms")
        self._adc_rms = self.tile.get_adc_rms()
        return tuple(self._adc_rms)

    @property
    def fpga1_time(self):
        """
        Return the FPGA1 clock time. Useful for detecting clock skew,
        propagation delays, contamination delays, etc.

        :return: the FPGA1 clock time
        :rtype: int
        """
        self.logger.debug("TpmDriver: fpga1_time")
        self._fpga1_time = self.tile.get_fpga_time(Device.FPGA_1)
        return self._fpga1_time

    @property
    def fpga2_time(self):
        """
        Return the FPGA2 clock time. Useful for detecting clock skew,
        propagation delays, contamination delays, etc.

        :return: the FPGA2 clock time
        :rtype: int
        """
        self.logger.debug("TpmDriver: fpga2_time")
        self._fpga2_time = self.tile.get_fpga_time(Device.FPGA_2)
        return self._fpga2_time

    @property
    def pps_delay(self):
        """
        Returns the PPS delay of the TPM.

        :return: PPS delay
        :rtype: float
        """
        self.logger.debug("TpmDriver: get_pps_delay")
        self._pps_delay = self.tile.get_pps_delay()
        return self._pps_delay

    @property
    def register_list(self):
        """
        Return a list of registers available on each device.

        :return: list of registers
        :rtype: list(str)
        """
        self.logger.warning("TpmDriver: register_list too big to be transmitted")
        regmap = self.tile.tpm.find_register("")
        reglist = []
        for reg in regmap:
            reglist.append(reg.name)
        return reg

    def read_register(self, register_name, nb_read, offset, device):
        """
        Read the values in a register. Named register returns.

        :param register_name: name of the register
        :type register_name: str
        :param nb_read: number of values to read
        :type nb_read: int
        :param offset: offset from which to start reading
        :type offset: int
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2, other = none
        :type device: int

        :return: values read from the register
        :rtype: list(int)
        """
        if device == 1:
            devname = "fpga1."
        elif device == 2:
            devname = "fpga2."
        else:
            devname = ""
        regname = devname + register_name
        if len(self.tile.tpm.find_register(regname)) == 0:
            self.logger.error("Register '" + regname + "' not present")
            value = None
        else:
            value = self.tile[regname]
        if type(value) == list:
            value = tuple(value)
        else:
            value = tuple([value])
        nmin = min(len(value) - 1, offset)
        nmax = min(len(value), nmin + nb_read)
        return value[nmin:nmax]

    def write_register(self, register_name, values, offset, device):
        """
        Read the values in a register.

        :param register_name: name of the register
        :type register_name: str
        :param values: values to write
        :type values: list
        :param offset: offset from which to start reading
        :type offset: int
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2
        :type device: int
        """
        if device == 1:
            devname = "fpga1."
        elif device == 2:
            devname = "fpga2."
        else:
            devname = ""
        regname = devname + register_name
        if len(self.tile.tpm.find_register(regname)) == 0:
            self.logger.error("Register '" + regname + "' not present")
        else:
            self.tile[regname] = values

    def read_address(self, address, nvalues):
        """
        Returns a list of values from a given address.

        :param address: address of start of read
        :type address: int
        :param nvalues: number of values to read
        :type nvalues: int

        :return: values at the address
        :rtype: list(int)
        """
        values = []
        # this is inefficient
        # TODO use list write method for tile
        #
        current_address = int(address & 0xFFFFFFFC)
        for i in range(nvalues):
            self.logger.debug(
                "Reading address "
                + str(current_address)
                + "of type "
                + str(type(current_address))
            )
            values.append(self.tile[current_address])
            current_address = current_address + 4
        return tuple(values)

    def write_address(self, address, values):
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :type address: int
        :param values: values to write
        :type values: list(int)
        """
        # this is inefficient
        # TODO use list write method for tile
        #
        current_address = int(address & 0xFFFFFFFC)
        for value in values:
            self.tile[current_address] = value
            current_address = current_address + 4

    def configure_40g_core(
        self, core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
    ):
        """
        Configure the 40G code.

        :param core_id: id of the core
        :type core_id: int
        :param src_mac: MAC address of the source
        :type src_mac: str
        :param src_ip: IP address of the source
        :type src_ip: str
        :param src_port: port of the source
        :type src_port: int
        :param dst_mac: MAC address of the destination
        :type dst_mac: str
        :param dst_ip: IP address of the destination
        :type dst_ip: str
        :param dst_port: port of the destination
        :type dst_port: int
        """
        core_dict = {
            "CoreID": core_id,
            "SrcMac": src_mac,
            "SrcIP": src_ip,
            "SrcPort": src_port,
            "DstMac": dst_mac,
            "DstIP": dst_ip,
            "DstPort": dst_port,
        }
        self.logger.warning("TpmDriver: configure_40g_core is simulated")
        self._forty_gb_core_list.append(core_dict)

    def get_40g_configuration(self, core_id=-1):
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :type core_id: int, optional

        :return: core configuration or list of core configurations
        :rtype: dict or list(dict)
        """
        self.logger.warning("TpmDriver: get_40g_configuration is simulated")
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("CoreID") == core_id:
                return item
        return

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
        Specify whether control data will be transmitted over 1G or 40G
        networks.

        :param mode: "1g" or "10g"
        :type mode: str
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :type payload_length: int, optional
        :param dst_ip: destination IP, defaults to None
        :type dst_ip: str, optional
        :param src_port: sourced port, defaults to 0xF0D0
        :type src_port: int, optional
        :param dst_port: destination port, defaults to 4660
        :type dst_port: int, optional
        :param lmc_mac: LMC MAC address, defaults to None
        :type lmc_mac: str, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_lmc_download")
        raise NotImplementedError

    def set_channeliser_truncation(self, array):
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: an N * M numpy.array, where N is the number of input
            channels, and M is the number of frequency channels.
        :type array: list(list(int))
        """
        self.logger.debug("TpmDriver: set_channeliser_truncation")
        [nb_chan, nb_freq] = np.shape(array)
        for chan in range(nb_chan):
            trunc = [0] * 512
            trunc[0:nb_freq] = array[chan]
            self.tile.set_channeliser_truncation(trunc, chan)

    def set_beamformer_regions(self, regions):
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 16 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0 and 7)
            and a substation ID (not used)
        :type regions: list(int)
        """
        self.logger.debug("TpmDriver: set_beamformer_regions")
        self.tile.set_beamformer_regions(regions)

    def initialise_beamformer(self, start_channel, nof_channels, is_first, is_last):
        """
        Initialise the beamformer.

        :param start_channel: the start channel
        :type start_channel: int
        :param nof_channels: number of channels
        :type nof_channels: int
        :param is_first: whether this is the first (?)
        :type is_first: bool
        :param is_last: whether this is the last (?)
        :type is_last: bool
        """
        self.logger.debug("TpmDriver: initialise_beamformer")
        self.tile.initialise_beamformer(start_channel, nof_channels, is_first, is_last)

    def load_calibration_coefficients(self, antenna, calibration_coefficients):
        """
        Load calibration coefficients. These may include any rotation
        matrix (e.g. the parallactic angle), but do not include the
        geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :type antenna: int
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        :type calibration_coefficients: list(int)
        """
        self.logger.debug("TpmDriver: load_calibration_coefficients")
        self.tile.load_calibration_coefficients(calibration_coefficients)

    def load_calibration_curve(self, antenna, beam, calibration_coefficients):
        """
        Load calibration curve. This is the frequency dependent response
        for a single antenna and beam, as a function of frequency. It
        will be combined together with tapering coefficients and beam
        angles by ComputeCalibrationCoefficients, and made active by
        SwitchCalibrationBank. The calibration coefficients do not
        include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :type antenna: int
        :param beam: the beam to which the coefficients apply
        :type beam: int
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        :type calibration_coefficients: list(int)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: load_calibration_curve")
        raise NotImplementedError

    def load_beam_angle(self, angle_coefficients):
        """
        Load the beam angle.

        :param angle_coefficients: list containing angle coefficients for each
            beam
        :type angle_coefficients: list(float)
        """
        self.logger.debug("TpmDriver: load_beam_angle")
        self.tile.load_beam_angle(angle_coefficients)

    def load_antenna_tapering(self, beam, tapering_coefficients):
        """
        Loat the antenna tapering coefficients.

        :param beam: the beam to which the coefficients apply
        :type beam: int
        :param tapering_coefficients: list of tapering coefficients for each
            antenna
        :type tapering_coefficients: list(float)
        """
        self.logger.debug("TpmDriver: load_antenna_tapering")
        self.tile.load_antenna_tapering(beam, tapering_coefficients)

    def switch_calibration_bank(self, switch_time=0):
        """
        Switch the calibration bank (i.e. apply the calibration
        coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        :type switch_time: int, optional
        """
        self.logger.debug("TpmDriver: switch_calibration_bank")
        self.tile.switch_calibration_bank(switch_time=0)

    def compute_calibration_coefficients(self):
        """
        Compute the calibration coefficients from previously specified
        gain curves, tapering weights and beam angles, load them in the
        hardware.

        It must be followed by switch_calibration_bank() to make these
        active.
        """
        self.logger.debug("TpmDriver: compute_calibration_coefficients")
        self.tile.compute_calibration_coefficients()

    def set_pointing_delay(self, delay_array, beam_index):
        """
        Specifies the delay in seconds and the delay rate in
        seconds/second. The delay_array specifies the delay and delay
        rate for each antenna. beam_index specifies which beam is
        desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :type delay_array: list(float)
        :param beam_index: the beam to which the pointing delay should
            be applied
        :type beam_index: int

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_pointing_delay")
        raise NotImplementedError

    def load_pointing_delay(self, load_time):
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        :type load_time: int
        """
        self.logger.debug("TpmDriver: load_pointing_delay")
        self.tile.load_pointing_delay(load_time)

    def start_beamformer(self, start_time=0, duration=-1):
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :type start_time: int, optional
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :type duration: int, optional
        """
        self.logger.debug("TpmDriver: Start beamformer")
        if self.tile.start_beamformer(start_time, duration):
            self._is_beamformer_running = True

    def stop_beamformer(self):
        """
        Stop the beamformer.
        """
        self.logger.debug("TpmDriver: Stop beamformer")
        self.tile.stop_beamformer()
        self._is_beamformer_running = False

    def configure_integrated_channel_data(self, integration_time=0.5):
        """
        Configure the transmission of integrated channel data with the
        provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: configure_integrated_channel_data")
        raise NotImplementedError

    def configure_integrated_beam_data(self, integration_time=0.5):
        """
        Configure the transmission of integrated beam data with the
        provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: configure_integrated_beam_data")
        raise NotImplementedError

    def send_raw_data(
        self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2
    ):
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :type sync: bool, optional
        :param period: duration to send data, in seconds, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_raw_data")
        raise NotImplementedError

    def send_channelised_data(
        self,
        number_of_samples=1024,
        first_channel=0,
        last_channel=511,
        period=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Transmit a snapshot containing channelized data totalling
        number_of_samples spectra.

        :param number_of_samples: number of spectra to send, defaults to 1024
        :type number_of_samples: int, optional
        :param first_channel: first channel to send, defaults to 0
        :type first_channel: int, optional
        :param last_channel: last channel to send, defaults to 511
        :type last_channel: int, optional
        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_channelised_data")
        raise NotImplementedError

    def send_channelised_data_continuous(
        self,
        channel_id,
        number_of_samples=128,
        wait_seconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Transmit data from a channel continuously.

        :param channel_id: index of channel to send
        :type channel_id: int
        :param number_of_samples: number of spectra to send, defaults to 1024
        :type number_of_samples: int, optional
        :param wait_seconds: wait time before sending data
        :type wait_seconds: float
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_channelised_data_continuous")
        raise NotImplementedError

    def send_beam_data(self, period=0, timeout=0, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing beamformed data.

        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_beam_data")
        raise NotImplementedError

    def stop_data_transmission(self):
        """
        Stop data transmission.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: stop_data_transmission")
        raise NotImplementedError

    def start_acquisition(self, start_time=None, delay=2):
        """
        Start data acquisitiong.

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :type start_time: int, optional
        :param delay: delay start, defaults to 2
        :type delay: int, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver:Start acquisition")
        raise NotImplementedError

    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in input streams, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        :type delays: list(int)
        """
        self.logger.debug("TpmDriver: set_time_delays")
        self.tile.set_time_delays(delays)

    def set_csp_rounding(self, rounding):
        """
        Set output rounding for CSP.

        :param rounding: the output rounding
        :type rounding: float

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_csp_rounding")
        raise NotImplementedError

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
        :type mode: str
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :type channel_payload_length: int
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :type beam_payload_length: int
        :param dst_ip: Destination IP, defaults to None
        :type dst_ip: str, optional
        :param src_port: source port, defaults to 0xF0D0
        :type src_port: int, optional
        :param dst_port: destination port, defaults to 4660
        :type dst_port: int, optional
        :param lmc_mac: MAC address of destination, defaults to None
        :type lmc_mac: str, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: set_lmc_integrated_download")
        raise NotImplementedError

    def send_raw_data_synchronised(
        self, period=0, timeout=0, timestamp=None, seconds=0.2
    ):
        """
        Send synchronised raw data.

        :param period: period of time in seconds, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_raw_data_synchronised")
        raise NotImplementedError

    @property
    def current_tile_beamformer_frame(self):
        """
        Return current frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        :rtype: int
        """
        self.logger.debug("TpmDriver: current_tile_beamformer_frame")
        self._current_tile_beamformer_frame = self.tile.current_tile_beamformer_frame()
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self):
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        :rtype: bool
        """
        self.logger.debug("TpmDriver: beamformer_is_running")
        self._is_beamformer_running = self.tile.beamformer_is_running()
        return self._is_beamformer_running

    def check_pending_data_requests(self):
        """
        Check for pending data requests.

        :return: whether there are pending send data requests
        :rtype: bool
        """
        self.logger.debug("TpmDriver: check_pending_data_requests")
        return self.tile.check_pending_data_requests()

    def send_channelised_data_narrowband(
        self,
        frequency,
        round_bits,
        number_of_samples=128,
        wait_seconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Continuously send channelised data from a single channel.

        This is a special mode used for UAV campaigns.

        :param frequency: sky frequency to transmit
        :type frequency: int
        :param round_bits: which bits to round
        :type round_bits: int
        :param number_of_samples: number of spectra to send, defaults to 128
        :type number_of_samples: int, optional
        :param wait_seconds: wait time before sending data, defaults to 0
        :type wait_seconds: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start, defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: send_channelised_data_narrowband")
        raise NotImplementedError

    #
    # The synchronisation routine for the current TPM requires that
    # the function below are accessible from the station (where station-level
    # synchronisation is performed), however I am not sure whether the routine
    # for the new TPMs will still required these
    #
    def tweak_transceivers(self):
        """
        Tweak the transceivers.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: tweak_transceivers")
        raise NotImplementedError

    @property
    def phase_terminal_count(self):
        """
        Return the phase terminal count.

        :return: the phase terminal count
        :rtype: int
        """
        self.logger.debug("TpmDriver: get_phase_terminal_count")
        self.logger.debug("TpmDriver: get_phase_terminal_count is simulated")
        return self._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        :type value: int
        """
        self.logger.debug("TpmDriver: set_phase_terminal_count")
        self.logger.debug("TpmDriver: set_phase_terminal_count is simulated")
        self._phase_terminal_count = value

    def post_synchronisation(self):
        """
        Perform post tile configuration synchronization.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: post_synchronisation")
        raise NotImplementedError

    def sync_fpgas(self):
        """
        Synchronise the FPGAs.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmDriver: sync_fpgas")
        raise NotImplementedError

    @staticmethod
    def calculate_delay(current_delay, current_tc, ref_lo, ref_hi):
        """
        Calculate the delay.

        :param current_delay: the current delay
        :type current_delay: float
        :param current_tc: current phase register terminal count
        :type current_tc: int
        :param ref_lo: low reference
        :type ref_lo: float
        :param ref_hi: high reference
        :type ref_hi: float

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        raise NotImplementedError