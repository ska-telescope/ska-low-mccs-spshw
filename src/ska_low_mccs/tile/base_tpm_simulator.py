# type: ignore
# -*- coding: utf-8 -*-
"""
An implementation of a TPM simulator.
"""
import copy

from ska_low_mccs.hardware import HardwareSimulator

__all__ = ["BaseTpmSimulator"]


class BaseTpmSimulator(HardwareSimulator):
    """
    A simulator for a TPM.
    """

    ADC_RMS = tuple(float(i) for i in range(32))
    FPGA1_TIME = 1
    FPGA2_TIME = 2
    CURRENT_TILE_BEAMFORMER_FRAME = 23
    PPS_DELAY = 12
    PHASE_TERMINAL_COUNT = 0
    FIRMWARE_NAME = "itpm_v1_6.bit"
    FIRMWARE_AVAILABLE = {
        "itpm_v1_6.bit": {"design": "model1", "major": 2, "minor": 3},
        "itpm_v1_5.bit": {"design": "model2", "major": 3, "minor": 7},
        "itpm_v1_2.bit": {"design": "model3", "major": 2, "minor": 6},
    }
    REGISTER_MAP = {
        0: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
        1: {"test-reg1": {}, "test-reg2": {}, "test-reg3": {}, "test-reg4": {}},
    }
    # ARP resolution table
    # Values are consistent with unit test test_MccsTile
    #
    ARP_MAP = {
        "10.0.23.56": 0x10FEFA060B99,
        "10.0.98.3": 0x10FEED080B59,
        "10.0.98.4": 0x10FEED080B57,
        "10.0.99.3": 0x10FEED080A58,
        "10.0.99.4": 0x10FEED080A56,
    }
    ARP_TABLE = {0: [0, 1], 1: [1]}
    # TPM version: "tpm_v1_2" or "tpm_v1_6"
    TPM_VERSION = 120

    def _arp(self, ip):
        """
        Return MAC address from ARP resolution table Private method for the simulator.

        :param ip: IP address in dot decimal format
        :type ip: str
        :return: MAC address in xx:xx:xx:xx:xx:xx format
        :rtype: str
        """
        if ip in self.ARP_MAP:
            mac = self.ARP_MAP[ip]
            mac_str = f"{mac:012x}"
            arp = ":".join(mac_str[i : (i + 2)] for i in range(0, 12, 2))
            return arp
        else:
            return "ff:ff:ff:ff:ff:ff"

    def __init__(self, logger, fail_connect=False):
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        """
        self.logger = logger
        self._is_programmed = False
        self._is_beamformer_running = False
        self._phase_terminal_count = self.PHASE_TERMINAL_COUNT
        self._station_id = 0
        self._tile_id = 0

        self._adc_rms = tuple(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._pps_delay = self.PPS_DELAY
        self._firmware_name = self.FIRMWARE_NAME
        self._firmware_available = copy.deepcopy(self.FIRMWARE_AVAILABLE)
        self._arp_table = copy.deepcopy(self.ARP_TABLE)
        self._fpga1_time = self.FPGA1_TIME
        self._fpga2_time = self.FPGA2_TIME

        self._address_map = {}
        self._forty_gb_core_list = []
        self._register_map = copy.deepcopy(self.REGISTER_MAP)
        self._test_generator_active = False
        super().__init__(is_connectible=False, fail_connect=fail_connect)

    @property
    def firmware_available(self):
        """
        Return the firmware list for this TPM simulator.

        :return: the firmware list
        :rtype: dict
        """
        self.logger.debug("TpmSimulator: firmware_available")
        return copy.deepcopy(self._firmware_available)

    @property
    def firmware_name(self):
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        :rtype: str
        """
        self.logger.debug("TpmSimulator: firmware_name")
        return self._firmware_name

    @firmware_name.setter
    def firmware_name(self, value):
        """
        Set firmware name.

        :param value: assigned default firmware name. Can be overriden by parameter of download_firmware
        :type value: str
        """
        self._tile_id = value

    @property
    def firmware_version(self):
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        :rtype: str
        """
        self.logger.debug("TpmSimulator: firmware_version")
        firmware = self._firmware_available[self._firmware_name]
        return "{major}.{minor}".format(**firmware)  # noqa: FS002

    @property
    def is_programmed(self):
        """
        Return whether this TPM is programmed (i.e. firmware has been downloaded to it)

        :return: whether this TPM is programmed
        :rtype: bool
        """
        self.logger.debug(f"TpmSimulator: is_programmed {self._is_programmed}")
        return self._is_programmed

    @property
    def hardware_version(self):
        """
        Return whether this TPM is 1.2 or 1.6.

        :return: TPM hardware version. 120 or 160
        :rtype: int
        """
        return self.TPM_VERSION

    def download_firmware(self, bitfile):
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: the bitfile to be downloaded
        :type bitfile: str
        """
        self.logger.debug("TpmSimulator: download_firmware")
        self._firmware_name = bitfile
        self._is_programmed = True

    def cpld_flash_write(self, bitfile):
        """
        Flash a program to the tile's CPLD (complex programmable logic device).

        :param bitfile: the program to be flashed
        :type bitfile: bytes

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: program_cpld")
        raise NotImplementedError

    def initialise(self):
        """
        Real TPM driver performs connectivity checks, programs and initialises the TPM.

        The simulator will emulate programming the firmware.
        """
        self.logger.debug("TpmSimulator: initialise")
        self.download_firmware(self._firmware_name)

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

    @property
    def board_temperature(self):
        """
        Return the temperature of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'board_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def voltage(self):
        """
        Return the voltage of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'voltage' must be "
            "implemented in a subclass."
        )

    @property
    def current(self):
        """
        Return the current of the TPM.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'current' must be "
            "implemented in a subclass."
        )

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga1_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :raises NotImplementedError: if this method has not been
            implemented by a subclass
        """
        raise NotImplementedError(
            "BaseTpmSimulator is abstract; property 'fpga2_temperature' must be "
            "implemented in a subclass."
        )

    @property
    def adc_rms(self):
        """
        Return the RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        :rtype: list(float)
        """
        self.logger.debug("TpmSimulator: adc_rms")
        return tuple(self._adc_rms)

    @property
    def fpga1_time(self):
        """
        Return the FPGA1 clock time. Useful for detecting clock skew, propagation
        delays, contamination delays, etc.

        :return: the FPGA1 clock time
        :rtype: int
        """
        self.logger.debug("TpmSimulator: fpga1_time")
        return self._fpga1_time

    @property
    def fpga2_time(self):
        """
        Return the FPGA2 clock time. Useful for detecting clock skew, propagation
        delays, contamination delays, etc.

        :return: the FPGA2 clock time
        :rtype: int
        """
        self.logger.debug("TpmSimulator: fpga2_time")
        return self._fpga2_time

    @property
    def pps_delay(self):
        """
        Returns the PPS delay of the TPM.

        :return: PPS delay
        :rtype: float
        """
        self.logger.debug("TpmSimulator: get_pps_delay")
        return self._pps_delay

    @property
    def register_list(self):
        """
        Return a list of registers available on each device.

        :return: list of registers
        :rtype: list(str)
        """
        return list(self._register_map[0].keys())

    def read_register(self, register_name, nb_read, offset, device):
        """
        Read the values in a register.

        :param register_name: name of the register
        :type register_name: str
        :param nb_read: number of values to read
        :type nb_read: int
        :param offset: offset from which to start reading
        :type offset: int
        :param device: The device number: 1 = FPGA 1, 2 = FPGA 2
        :type device: int

        :return: values read from the register
        :rtype: list(int)
        """
        address_map = self._register_map[device].get(register_name, None)
        if address_map is None:
            return tuple()
        values = []
        for i in range(nb_read):
            key = str(offset + i)
            values.append(address_map.get(key, 0))
        return tuple(values)

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
        address_map = self._register_map[device].get(register_name, None)
        if address_map is None:
            return
        for i, value in enumerate(values):
            key = str(offset + i)
            address_map.update({key: value})

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
        for i in range(nvalues):
            key = str(address + i)
            values.append(self._address_map.get(key, 0))
        return tuple(values)

    def write_address(self, address, values):
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :type address: int
        :param values: values to write
        :type values: list(int)
        """
        for i, value in enumerate(values):
            key = str(address + i)
            self._address_map.update({key: value})

    def configure_40g_core(
        self, core_id, arp_table_entry, src_mac, src_ip, src_port, dst_ip, dst_port
    ):
        """
        Configure the 40G code. The dst_mac parameter is ignored in true 40G core (ARP
        resolution used instead)

        :param core_id: id of the core
        :type core_id: int
        :param arp_table_entry: ARP table entry to use
        :type arp_table_entry: int
        :param src_mac: MAC address of the source
        :type src_mac: str
        :param src_ip: IP address of the source
        :type src_ip: str
        :param src_port: port of the source
        :type src_port: int
        :param dst_ip: IP address of the destination
        :type dst_ip: str
        :param dst_port: port of the destination
        :type dst_port: int
        """
        core_dict = {
            "CoreID": core_id,
            "ArpTableEntry": arp_table_entry,
            "SrcMac": src_mac,
            "SrcIP": src_ip,
            "SrcPort": src_port,
            "DstIP": dst_ip,
            "DstPort": dst_port,
        }
        self._forty_gb_core_list.append(core_dict)

    def get_40g_configuration(self, core_id=-1, arp_table_entry=0):
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :type core_id: int, optional
        :param arp_table_entry: ARP table entry to use
        :type arp_table_entry: int

        :return: core configuration or list of core configurations
        :rtype: dict or list(dict)
        """
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("CoreID") == core_id:
                return item
        return

    @property
    def arp_table(self):
        """
        Check that ARP table has been populated in for all used cores. 40G interfaces
        use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer, 1 for LMC. 10G
        interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: dictionary containing coreID and populated arpID
        :rtype: dict
        """
        self.logger.debug("TpmSimulator: arp_table")
        return copy.deepcopy(self._arp_table)

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
        Specify whether control data will be transmitted over 1G or 40G networks.

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
        self.logger.debug("TpmSimulator: set_lmc_download")
        raise NotImplementedError

    def set_channeliser_truncation(self, array):
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: an N * M array, where N is the number of input
            channels, and M is the number of frequency channels. This is
            encoded as a list comprising N, then M, then the flattened
            array
        :type array: list(int)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_channeliser_truncation")
        raise NotImplementedError

    def set_beamformer_regions(self, regions):
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 48 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), a beam index (between 0 and 7)
            and a substation ID.
        :type regions: list(int)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_beamformer_regions")
        raise NotImplementedError

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

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: initialise_beamformer")
        raise NotImplementedError

    def load_calibration_coefficients(self, antenna, calibration_coefficients):
        """
        Load calibration coefficients. These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :type antenna: int
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        :type calibration_coefficients: list(int)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_calibration_coefficients")
        raise NotImplementedError

    def load_calibration_curve(self, antenna, beam, calibration_coefficients):
        """
        Load calibration curve. This is the frequency dependent response for a single
        antenna and beam, as a function of frequency. It will be combined together with
        tapering coefficients and beam angles by ComputeCalibrationCoefficients, and
        made active by SwitchCalibrationBank. The calibration coefficients do not
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
        self.logger.debug("TpmSimulator: load_calibration_curve")
        raise NotImplementedError

    def load_beam_angle(self, angle_coefficients):
        """
        Load the beam angle.

        :param angle_coefficients: list containing angle coefficients for each
            beam
        :type angle_coefficients: list(float)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_beam_angle")
        raise NotImplementedError

    def load_antenna_tapering(self, beam, tapering_coefficients):
        """
        Loat the antenna tapering coefficients.

        :param beam: the beam to which the coefficients apply
        :type beam: int
        :param tapering_coefficients: list of tapering coefficients for each
            antenna
        :type tapering_coefficients: list(float)

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_antenna_tapering")
        raise NotImplementedError

    def switch_calibration_bank(self, switch_time=0):
        """
        Switch the calibration bank (i.e. apply the calibration
        coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        :type switch_time: int, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: switch_calibration_bank")
        raise NotImplementedError

    def compute_calibration_coefficients(self):
        """
        Compute the calibration coefficients from previously specified gain curves,
        tapering weights and beam angles, load them in the hardware. It must be followed
        by switch_calibration_bank() to make these active.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: compute_calibration_coefficients")
        raise NotImplementedError

    def set_pointing_delay(self, delay_array, beam_index):
        """
        Specifies the delay in seconds and the delay rate in seconds/second. The
        delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :type delay_array: list(float)
        :param beam_index: the beam to which the pointing delay should
            be applied
        :type beam_index: int

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_pointing_delay")
        raise NotImplementedError

    def load_pointing_delay(self, load_time):
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        :type load_time: int

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: load_pointing_delay")
        raise NotImplementedError

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
        self.logger.debug("TpmSimulator: Start beamformer")
        self._is_beamformer_running = True

    def stop_beamformer(self):
        """
        Stop the beamformer.
        """
        self.logger.debug("TpmSimulator: Stop beamformer")
        self._is_beamformer_running = False

    def configure_integrated_channel_data(
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=511,
    ):
        """
        Configure the transmission of integrated channel data with the provided
        integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_channel_data")
        raise NotImplementedError

    def stop_integrated_channel_data(self):
        """
        Stop the integrated channel data.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: Stop integrated channel data")
        raise NotImplementedError

    def configure_integrated_beam_data(
        self,
        integration_time=0.5,
        first_channel=0,
        last_channel=191,
    ):
        """
        Configure the transmission of integrated beam data with the provided integration
        time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        :param first_channel: first channel
        :type first_channel: int, optional
        :param last_channel: last channel
        :type last_channel: int, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: configure_integrated_beam_data")
        raise NotImplementedError

    def stop_integrated_beam_data(self):
        """
        Stop the integrated beam data.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: Stop integrated beam data")
        raise NotImplementedError

    def stop_integrated_data(self):
        """
        Stop the integrated data.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: Stop integrated data")
        raise NotImplementedError

    def send_raw_data(self, sync=False, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :type sync: bool, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_raw_data")
        raise NotImplementedError

    def send_channelised_data(
        self,
        number_of_samples=1024,
        first_channel=0,
        last_channel=511,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Transmit a snapshot containing channelized data totalling number_of_samples
        spectra.

        :param number_of_samples: number of spectra to send, defaults to 1024
        :type number_of_samples: int, optional
        :param first_channel: first channel to send, defaults to 0
        :type first_channel: int, optional
        :param last_channel: last channel to send, defaults to 511
        :type last_channel: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data")
        raise NotImplementedError

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
        :param number_of_samples: number of spectra to send, defaults to 1024
        :type number_of_samples: int, optional
        :param wait_seconds: wait time before sending data
        :type wait_seconds: float
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data_continuous")
        raise NotImplementedError

    def send_beam_data(self, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_beam_data")
        raise NotImplementedError

    def stop_data_transmission(self):
        """
        Stop data transmission.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: stop_data_transmission")
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
        self.logger.debug("TpmSimulator:Start acquisition")
        raise NotImplementedError

    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in samples, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        :type delays: int

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_time_delays")
        raise NotImplementedError

    def set_csp_rounding(self, rounding):
        """
        Set output rounding for CSP.

        :param rounding: the output rounding
        :type rounding: float

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: set_csp_rounding")
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
        self.logger.debug("TpmSimulator: set_lmc_integrated_download")
        raise NotImplementedError

    def send_raw_data_synchronised(self, timestamp=None, seconds=0.2):
        """
        Send synchronised raw data.

        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_raw_data_synchronised")
        raise NotImplementedError

    @property
    def current_tile_beamformer_frame(self):
        """
        Return current frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        :rtype: int
        """
        self.logger.debug("TpmSimulator: current_tile_beamformer_frame")
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self):
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        :rtype: bool
        """
        self.logger.debug("TpmSimulator: beamformer_is_running")
        return self._is_beamformer_running

    def check_pending_data_requests(self):
        """
        Check for pending data requests.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: check_pending_data_requests")
        raise NotImplementedError

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
        :param timestamp: when to start, defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: send_channelised_data_narrowband")
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
        self.logger.debug("TpmSimulator: tweak_transceivers")
        raise NotImplementedError

    @property
    def phase_terminal_count(self):
        """
        Return the phase terminal count.

        :return: the phase terminal count
        :rtype: int
        """
        self.logger.debug("TpmSimulator: get_phase_terminal_count")
        return self._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        :type value: int
        """
        self.logger.debug("TpmSimulator: set_phase_terminal_count")
        self._phase_terminal_count = value

    def post_synchronisation(self):
        """
        Perform post tile configuration synchronization.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: post_synchronisation")
        raise NotImplementedError

    def sync_fpgas(self):
        """
        Synchronise the FPGAs.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        self.logger.debug("TpmSimulator: sync_fpgas")
        raise NotImplementedError

    def configure_test_generator(
        self,
        frequency0,
        amplitude0,
        frequency1,
        amplitude1,
        amplitude_noise,
        pulse_code,
        amplitude_pulse,
        load_time=0,
    ):
        """
        test generator configuration.

        :param frequency0: Tone frequency in Hz of DDC 0
        :type frequency0: float
        :param amplitude0: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :type amplitude0: float
        :param frequency1: Tone frequency in Hz of DDC 1
        :type frequency1: float
        :param amplitude1: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :type amplitude1: float
        :param amplitude_noise: Amplitude of pseudorandom noise
            normalized to 26.03 ADC units, resolution 0.102 ADU
        :type amplitude_noise: float
        :param pulse_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :type pulse_code: int
        :param amplitude_pulse: pulse peak amplitude, normalized
            to 127.5 ADC units, resolution 0.5 ADU
        :type amplitude_pulse: float
        :param load_time: Time to start the tone.
        :type load_time: int

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        amplitude_adu = round(amplitude0 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: set_test_generator tone(0):"
            + str(frequency0)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude1 * 255) / 8.0
        self.logger.debug(
            "TpmSimulator: test_generator set_tone(1):"
            + str(frequency1)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        amplitude_adu = round(amplitude_noise * 255) * 0.102
        self.logger.debug(
            "TpmSimulator: set_test_generator noise: "
            + str(amplitude_adu)
            + " ADUs @"
            + str(load_time)
        )
        freqs = [16, 12, 8, 6, 4, 3, 2, 1]
        frequency = 0.925925 * freqs[pulse_code]
        amplitude_adu = round(amplitude_pulse * 255) * 0.25
        self.logger.debug(
            "TpmSimulator: set_test_generator pulse: "
            + str(frequency)
            + "Hz, "
            + str(amplitude_adu)
            + " ADUs"
        )
        raise NotImplementedError

    def test_generator_input_select(self, inputs):
        """
        Specify ADC inputs which are substitute to test signal. Specified using a 32 bit
        mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        :type inputs: int
        """
        self.logger.debug(
            "TpmSimulator: test_generator_input_select: " + str(hex(inputs))
        )
        # raise NotImplementedError

    @property
    def test_generator_active(self):
        """
        check if the test generator is active.

        :return: whether the test generator is active
        :rtype: bool
        """
        return self._test_generator_active

    @test_generator_active.setter
    def test_generator_active(self, active):
        """
        set the test generator active flag.

        :param active: True if the generator has been activated
        :type active: bool
        """
        self._test_generator_active = active

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
