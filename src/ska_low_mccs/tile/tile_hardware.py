# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains classes that support the MCCS Tile device's
management of hardware.
"""
__all__ = ["TileHardwareFactory", "TileHardwareHealthEvaluator", "TileHardwareManager"]

from ska_tango_base.control_model import SimulationMode, TestMode
from ska_low_mccs.hardware import (
    HardwareHealthEvaluator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska_low_mccs.tile import DynamicTpmSimulator, StaticTpmSimulator, TpmDriver


class TileHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A very rudimentary stub
    :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareHealthEvaluator`
    for tile hardware.

    At present this returns
    * FAILED if the connection to the TPM has been lost
    * OK otherwise.
    """

    pass


class TileHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for tile hardware.

    At present, this returns a
    :py:class:`~ska_low_mccs.tile.base_tpm_simulator.BaseTpmSimulator`
    object when in simulation mode, and a
    :py:class:`~ska_low_mccs.tile.tpm_driver.TpmDriver` object if
    the hardware is sought whilst not in simulation mode
    """

    def __init__(
        self, simulation_mode, test_mode, logger, tpm_ip="0.0.0.0", tpm_cpld_port=0
    ):
        """
        Create a new factory instance.

        :param simulation_mode: the initial simulation mode of this
            hardware factory
        :type simulation_mode:
            :py:class:`~ska_tango_base.control_model.SimulationMode`
        :param test_mode: the initial test mode of this hardware factory
        :type test_mode: :py:class:`~ska_tango_base.control_model.TestMode`
        :param logger: the logger to be used by this hardware manager.
        :type logger: :py:class:`logging.Logger`
        :param tpm_ip: the IP address of the tile
        :type tpm_ip: str
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :type tpm_cpld_port: int
        """
        self._logger = logger
        self._tpm_ip = tpm_ip
        self._tpm_cpld_port = tpm_cpld_port
        super().__init__(simulation_mode, test_mode=test_mode)

    def _create_driver(self):
        """
        Returns a hardware driver.

        :return: a hardware driver for the tile
        :rtype: :py:class:`ska_low_mccs.tile.tpm_driver.TpmDriver`
        """
        return TpmDriver(self._logger, self._tpm_ip, self._tpm_cpld_port)

    def _create_dynamic_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`ska_low_mccs.tile.dynamic_tpm_simulator.DynamicTpmSimulator`
        """
        return DynamicTpmSimulator(self._logger)

    def _create_static_simulator(self):
        """
        Returns a hardware simulator.

        :return: a hardware simulator for the tile
        :rtype:
            :py:class:`ska_low_mccs.tile.static_tpm_simulator.StaticTpmSimulator`
        """
        return StaticTpmSimulator(self._logger)


class TileHardwareManager(SimulableHardwareManager):
    """
    This class manages tile hardware.
    """

    def __init__(
        self, simulation_mode, test_mode, logger, tpm_ip, tpm_cpld_port, _factory=None
    ):
        """
        Initialise a new TileHardwareManager instance.

        :param simulation_mode: the initial simulation mode for this
            tile hardware manager
        :type simulation_mode:
            :py:class:`~ska_tango_base.control_model.SimulationMode`
        :param test_mode: the initial test mode for this tile hardware
            manager
        :type test_mode:
            :py:class:`~ska_tango_base.control_model.TestMode`
        :param logger: a logger for this hardware manager to use
        :type logger: :py:class:`logging.Logger`
        :param tpm_ip: IP address of TPM board
        :type tpm_ip: str
        :param tpm_cpld_port: port address of TPM board control port
        :type tpm_cpld_port: int
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`.TileHardwareFactory`
        """
        hardware_factory = _factory or TileHardwareFactory(
            simulation_mode == SimulationMode.TRUE,
            test_mode == TestMode.TEST,
            logger,
            tpm_ip,
            tpm_cpld_port,
        )
        super().__init__(hardware_factory, TileHardwareHealthEvaluator())

    @property
    def firmware_available(self):
        """
        Return specifications of the firmware loaded on the hardware and
        available for use.

        :return: specifications of the firmware stored on the hardware
        :rtype: dict
        """
        return self._factory.hardware.firmware_available

    @property
    def firmware_name(self):
        """
        Return the name of the firmware running on the hardware.

        :return: the name of the firmware
        :rtype: str
        """
        return self._factory.hardware.firmware_name

    @property
    def hardware_version(self):
        """
        Returns the version of the hardware running on the hardware.

        :return: the version of the hardware (e.g. 120 for 1.2)
        :rtype: int
        """
        return self._factory.hardware.hardware_version

    @property
    def firmware_version(self):
        """
        Returns the version of the firmware running on the hardware.

        :return: the version of the firmware
        :rtype: str
        """
        return self._factory.hardware.firmware_version

    def download_firmware(self, bitfile):
        """
        Download firmware to the board.

        :param bitfile: the bitfile to be downloaded
        :type bitfile: str
        """
        self._factory.hardware.download_firmware(bitfile)

    def cpld_flash_write(self, bitfile):
        """
        Write a program to the CPLD flash.

        :param bitfile: the bitfile to be flashed
        :type bitfile: str
        """
        self._factory.hardware.cpld_flash_write(bitfile)

    @property
    def tile_id(self):
        """
        Tile ID
        :return: assigned tile Id value
        :rtype: int
        """
        return self._factory.hardware.tile_id

    @tile_id.setter
    def tile_id(self, value):
        """
        Set Tile ID.

        :param value: assigned tile Id value
        :type value: int
        """
        self._factory.hardware.tile_id = value

    @property
    def station_id(self):
        """
        Station ID
        :return: assigned station Id value
        :rtype: int
        """
        return self._factory.hardware.station_id

    @station_id.setter
    def station_id(self, value):
        """
        Set Station ID.

        :param value: assigned station Id value
        :type value: int
        """
        self._factory.hardware.station_id = value

    @property
    def voltage(self):
        """
        The voltage of the hardware.

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._factory.hardware.voltage

    @property
    def current(self):
        """
        The current of the hardware.

        :return: the current of the hardware
        :rtype: float
        """
        return self._factory.hardware.current

    @property
    def board_temperature(self):
        """
        The temperature of the main board of the hardware.

        :return: the temperature of the main board of the hardware
        :rtype: float
        """
        return self._factory.hardware.board_temperature

    @property
    def fpga1_temperature(self):
        """
        The temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._factory.hardware.fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        The temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._factory.hardware.fpga2_temperature

    @property
    def fpga1_time(self):
        """
        The FPGA 1 time.

        :return: the FPGA 1 time
        :rtype: int
        """
        return self._factory.hardware.fpga1_time

    @property
    def fpga2_time(self):
        """
        The FPGA 2 time.

        :return: the FPGA 2 time
        :rtype: int
        """
        return self._factory.hardware.fpga2_time

    @property
    def pps_delay(self):
        """
        Returns the PPS delay of the TPM.

        :return: PPS delay
        :rtype: float
        """
        return self._factory.hardware.pps_delay

    @property
    def is_programmed(self):
        """
        Return whether the TPM is programmed or not.

        :return: whether the TPM is programmed of not
        :rtype: bool
        """
        return self._factory.hardware.is_programmed

    @property
    def adc_rms(self):
        """
        Return the RMS power of the TPM's analogue-to-digital converter.

        :return: the RMS power of the TPM's ADC
        :rtype: tuple(float)
        """
        return self._factory.hardware.adc_rms

    @property
    def current_tile_beamformer_frame(self):
        """
        Return the current beamformer frame of the tile.

        :return: the tile's current beamformer frame
        :rtype: int
        """
        return self._factory.hardware.current_tile_beamformer_frame

    @property
    def is_beamformer_running(self):
        """
        Check if beamformer is running.

        :return: whether the beamformer is running
        :rtype: bool
        """
        return self._factory.hardware.is_beamformer_running

    @property
    def test_generator_active(self):
        """
        check if the test generator is active.

        :return: whether the test generator is active
        :rtype: bool
        """
        return self._factory.hardware.test_generator_active

    @test_generator_active.setter
    def test_generator_active(self, active):
        """
        set the test generator active flag.

        :param active: True if the generator has been activated
        :type active: bool
        """
        self._factory.hardware.test_generator_active = active

    def start_beamformer(self, start_time=None, duration=None):
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :type start_time: int, optional
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :type duration: int, optional
        """
        self._factory.hardware.start_beamformer(
            start_time=start_time, duration=duration
        )

    def stop_beamformer(self):
        """
        Stop the beamformer.
        """
        self._factory.hardware.stop_beamformer()

    @property
    def phase_terminal_count(self):
        """
        Get phase terminal count.

        :return: phase terminal count
        :rtype: int
        """
        return self._factory.hardware.phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        :type value: int
        """
        self._factory.hardware.phase_terminal_count = value

    def initialise(self):
        """
        Initialise the TPM.
        """
        self._factory.hardware.initialise()

    @property
    def register_list(self):
        """
        Return a list of registers available on each device.

        :return: list of registers
        :rtype: list(str)
        """
        return self._factory.hardware.register_list

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

        :return: values from the register
        :rtype: list
        """
        return self._factory.hardware.read_register(
            register_name, nb_read, offset, device
        )

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
        self._factory.hardware.write_register(register_name, values, offset, device)

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
        return self._factory.hardware.read_address(address, nvalues)

    def write_address(self, address, values):
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :type address: int
        :param values: values to write
        :type values: list(int)
        """
        self._factory.hardware.write_address(address, values)

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
        self._factory.hardware.configure_40g_core(
            core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
        )

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
        return self._factory.hardware.get_40g_configuration(core_id)

    def set_lmc_download(
        self,
        mode,
        payload_length=None,
        dst_ip=None,
        src_port=None,
        dst_port=None,
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
        """
        self._factory.hardware.set_lmc_download(
            mode,
            payload_length=payload_length,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            lmc_mac=lmc_mac,
        )

    def set_channeliser_truncation(self, array):
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: an N * M array, where N is the number of input
            channels, and M is the number of frequency channels. This is
            encoded as a list comprising N, then M, then the flattened
            array
        :type array: list(int)
        """
        self._factory.hardware.set_channeliser_truncation(array)

    def set_beamformer_regions(self, regions):
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 16 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0
            and 7)
        :type regions: list(int)
        """
        self._factory.hardware.set_beamformer_regions(regions)

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
        self._factory.hardware.initialise_beamformer(
            start_channel, nof_channels, is_first, is_last
        )

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
        self._factory.hardware.load_calibration_coefficients(
            antenna, calibration_coefficients
        )

    def load_calibration_curve(self, antenna, beam, calibration_coefficients):
        """
        Load calibration curve. This is the frequency dependent response
        for a single antenna and beam, as a function of frequency. It
        will be combined together with tapering coefficients and beam
        angles by ComputeCalibrationCoefficients, which will also make
        them active like SwitchCalibrationBank. The calibration
        coefficients do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :type antenna: int
        :param beam: the beam to which the coefficients apply
        :type beam: int
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        :type calibration_coefficients: list(int)
        """
        self._factory.hardware.load_calibration_curve(
            antenna, beam, calibration_coefficients
        )

    def load_beam_angle(self, angle_coefficients):
        """
        Load the beam angle.

        :param angle_coefficients: list containing angle coefficients for each beam
        :type angle_coefficients: list(float)
        """
        self._factory.hardware.load_beam_angle(angle_coefficients)

    def load_antenna_tapering(self, beam, tapering_coefficients):
        """
        Loat the antenna tapering coefficients.

        :param beam: beam index
        :type beam: int
        :param tapering_coefficients: list of tapering coefficients for each
            antenna
        :type tapering_coefficients: list(float)
        """
        self._factory.hardware.load_antenna_tapering(beam, tapering_coefficients)

    def switch_calibration_bank(self, switch_time=None):
        """
        Switch the calibration bank (i.e. apply the calibration
        coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        :type switch_time: int, optional
        """
        self._factory.hardware.switch_calibration_bank(switch_time=switch_time)

    def compute_calibration_coefficients(self):
        """
        Compute the calibration coefficients from previously specified
        gain curves, tapering weights and beam angles, load them in the
        hardware.

        It must be followed by switch_calibration_bank() to make these
        active
        """
        self._factory.hardware.compute_calibration_coefficients()

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
        """
        self._factory.hardware.set_pointing_delay(delay_array, beam_index)

    def load_pointing_delay(self, load_time):
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        :type load_time: int
        """
        self._factory.hardware.load_pointing_delay(load_time)

    def configure_integrated_channel_data(self, integration_time=None):
        """
        Configure the transmission of integrated channel data with the
        provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        """
        self._factory.hardware.configure_integrated_channel_data(
            integration_time=integration_time
        )

    def configure_integrated_beam_data(self, integration_time=None):
        """
        Configure the transmission of integrated beam data with the
        provided integration time.

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        """
        self._factory.hardware.configure_integrated_beam_data(
            integration_time=integration_time
        )

    def send_raw_data(self, sync=False, timestamp=None, seconds=None):
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :type sync: bool, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_raw_data(
            sync=sync,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_channelised_data(
        self,
        number_of_samples=None,
        first_channel=None,
        last_channel=None,
        timestamp=None,
        seconds=None,
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
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_channelised_data(
            number_of_samples=number_of_samples,
            first_channel=first_channel,
            last_channel=last_channel,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_channelised_data_continuous(
        self,
        channel_id,
        number_of_samples=None,
        wait_seconds=None,
        timestamp=None,
        seconds=None,
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
        """
        self._factory.hardware.send_channelised_data_continuous(
            channel_id,
            number_of_samples=number_of_samples,
            wait_seconds=wait_seconds,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_beam_data(self, timestamp=None, seconds=None):
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_beam_data(timestamp=timestamp, seconds=seconds)

    def stop_data_transmission(self):
        """
        Stop data transmission.
        """
        self._factory.hardware.stop_data_transmission()

    def start_acquisition(self, start_time=None, delay=None):
        """
        Start data acquisitiong.

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :type start_time: int, optional
        :param delay: delay start, defaults to 2
        :type delay: int, optional
        """
        self._factory.hardware.start_acquisition(start_time=start_time, delay=delay)

    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in samples, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        :type delays: int
        """
        self._factory.hardware.set_time_delays(delays)

    def set_csp_rounding(self, rounding):
        """
        Set output rounding for CSP.

        :param rounding: the output rounding
        :type rounding: float
        """
        self._factory.hardware.set_csp_rounding(rounding)

    def set_lmc_integrated_download(
        self,
        mode,
        channel_payload_length,
        beam_payload_length,
        dst_ip=None,
        src_port=None,
        dst_port=None,
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
        """
        self._factory.hardware.set_lmc_integrated_download(
            mode,
            channel_payload_length,
            beam_payload_length,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            lmc_mac=lmc_mac,
        )

    def check_pending_data_requests(self):
        """
        Check the TPM for pending data requests.

        :return: whether the TPM has pending data requests
        :rtype: bool
        """
        return self._factory.hardware.check_pending_data_requests()

    def send_channelised_data_narrowband(
        self,
        frequency,
        round_bits,
        number_of_samples=None,
        wait_seconds=None,
        timestamp=None,
        seconds=None,
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
        """
        self._factory.hardware.send_channelised_data_narrowband(
            frequency,
            round_bits,
            number_of_samples=number_of_samples,
            wait_seconds=wait_seconds,
            timestamp=timestamp,
            seconds=seconds,
        )

    def tweak_transceivers(self):
        """
        Tweak the transceivers.
        """
        self._factory.hardware.tweak_transceivers()

    @property
    def phase_terminal_count(self):
        """
        Return the phase terminal count.

        :return: the phase terminal count
        :rtype: int
        """
        return self._factory.hardware._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        :type value: int
        """
        self._factory.hardware.phase_terminal_count = value

    def post_synchronisation(self):
        """
        Perform post tile configuration synchronization.
        """
        self._factory.hardware.post_synchronisation()

    def sync_fpgas(self):
        """
        Synchronise the FPGAs.
        """
        self._factory.hardware.sync_fpgas()

    def calculate_delay(self, current_delay, current_tc, ref_lo, ref_hi):
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
        """
        self._factory.hardware.calculate_delay(
            current_delay, current_tc, ref_lo, ref_hi
        )

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
        :param load_time: Time to start the generator.
        :type load_time: int
        """
        self._factory.hardware.configure_test_generator(
            frequency0,
            amplitude0,
            frequency1,
            amplitude1,
            amplitude_noise,
            pulse_code,
            amplitude_pulse,
            load_time,
        )

    def test_generator_input_select(self, inputs):
        """
        Specify ADC inputs which are substitute to test signal.
        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        :type inputs: int
        """
        self._factory.hardware.test_generator_input_select(inputs)
