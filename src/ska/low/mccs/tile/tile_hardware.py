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
management of hardware
"""
__all__ = ["TileHardwareHealthEvaluator", "TileHardwareManager"]

from ska.base.control_model import SimulationMode
from ska.low.mccs.hardware import (
    HardwareHealthEvaluator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska.low.mccs.tile import TpmSimulator


class TileHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    A very rudimentary stub
    :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
    for tile hardware.

    At present this returns
    * FAILED if the connection to the TPM has been lost
    * OK otherwise.
    """

    pass


class TileHardwareFactory(SimulableHardwareFactory):
    """
    A hardware factory for tile hardware. At present, this returns a
    :py:class:`~ska.low.mccs.tile.tpm_simulator.TpmSimulator` object
    when in simulation mode, and raises
    :py:exception:`NotImplementedError` if the hardware is sought whilst
    not in simulation mode
    """

    def __init__(self, simulation_mode, logger):
        """
        Create a new factory instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        :param logger: the logger to be used by this hardware manager.
        :type logger: a logger that implements the standard library
            logger interface
        """
        self._logger = logger
        super().__init__(simulation_mode)

    def _create_simulator(self):
        """
        Returns a hardware simulator

        :return: a hardware simulator for the tile
        :rtype: :py:class:`TpmSimulator`
        """
        return TpmSimulator(self._logger)


class TileHardwareManager(SimulableHardwareManager):
    """
    This class manages tile hardware.
    """

    def __init__(self, simulation_mode, logger, _factory=None):
        """
        Initialise a new TileHardwareManager instance

        :param simulation_mode: the initial simulation mode for this
            tile hardware manager
        :type simulation_mode:
            :py:class:`~ska.base.control_model.SimulationMode`
        :param logger: a logger for this hardware manager to use
        :type logger: :py:class:`logging.Logger`
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`TileHardwareFactory`
        """
        hardware_factory = _factory or TileHardwareFactory(
            simulation_mode == SimulationMode.TRUE, logger
        )
        super().__init__(hardware_factory, TileHardwareHealthEvaluator())

    @property
    def firmware_available(self):
        """
        Return specifications of the firmware stored on the hardware and
        available for use

        :return: specifications of the firmware stored on the hardware
        :rtype: dict
        """
        return self._factory.hardware.firmware_available

    @property
    def firmware_name(self):
        """
        Return the name of the firmware running on the hardware

        :return: the name of the firmware
        :rtype: str
        """
        return self._factory.hardware.firmware_name

    @property
    def firmware_version(self):
        """
        Returns the name of the firmware running on the hardware

        :return: the name of the firmware
        :rtype: str
        """
        return self._factory.hardware.firmware_version

    def download_firmware(self, bitfile):
        """
        Download firmware to the board

        :param bitfile: the bitfile to be downloaded
        :type bitfile: str
        """
        self._factory.hardware.download_firmware(bitfile)

    def cpld_flash_write(self, bitfile):
        """
        Write a program to the CPLD flash

        :param bitfile: the bitfile to be flashed
        :type bitfile: str
        """
        self._factory.hardware.cpld_flash_write(bitfile)

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._factory.hardware.voltage

    @property
    def current(self):
        """
        The current of the hardware

        :return: the current of the hardware
        :rtype: float
        """
        return self._factory.hardware.current

    @property
    def board_temperature(self):
        """
        The temperature of the main board of the hardware

        :return: the temperature of the main board of the hardware
        :rtype: float
        """
        return self._factory.hardware.board_temperature

    @property
    def fpga1_temperature(self):
        """
        The temperature of FPGA 1

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._factory.hardware.fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        The temperature of FPGA 2

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._factory.hardware.fpga2_temperature

    @property
    def fpga1_time(self):
        """
        The FPGA 1 time

        :return: the FPGA 1 time
        :rtype: int
        """
        return self._factory.hardware.fpga1_time

    @property
    def fpga2_time(self):
        """
        The FPGA 2 time

        :return: the FPGA 2 time
        :rtype: int
        """
        return self._factory.hardware.fpga2_time

    @property
    def pps_delay(self):
        """
        Returns the PPS delay of the TPM

        :return: PPS delay
        :rtype: float
        """
        return self._factory.hardware.pps_delay

    @property
    def is_programmed(self):
        """
        Return whether the TPM is programmed or not

        :return: whether the TPM is programmed of not
        :rtype: bool
        """
        return self._factory.hardware.is_programmed

    @property
    def adc_rms(self):
        """
        Return the RMS power of the TPM's analogue-to-digital converter

        :return: the RMS power of the TPM's ADC
        :rtype: tuple of float
        """
        return self._factory.hardware.adc_rms

    @property
    def current_tile_beamformer_frame(self):
        """
        Return the current beamformer frame of the tile

        :return: the tile's current beamformer frame
        :rtype: int
        """
        return self._factory.hardware.current_tile_beamformer_frame

    @property
    def is_beamformer_running(self):
        """
        Check if beamformer is running

        :return: whether the beamformer is running
        :rtype: boolean
        """
        return self._factory.hardware.is_beamformer_running

    def start_beamformer(self, start_time=None, duration=None):
        """
        Start the beamformer at the specified time

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
        Stop the beamformer
        """
        self._factory.hardware.stop_beamformer()

    @property
    def phase_terminal_count(self):
        """
        Get phase terminal count

        :return: phase terminal count
        :rtype: int
        """
        return self._factory.hardware.phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count

        :param value: the phase terminal count
        :type value: int
        """
        self._factory.hardware.phase_terminal_count = value

    def initialise(self):
        """
        Initialise the TPM
        """
        self._factory.hardware.initialise()

    @property
    def register_list(self):
        """
        Return a list of registers available on each device

        :return: list of registers
        :rtype: list of str
        """
        return self._factory.hardware.register_list

    def read_register(self, register_name, nb_read, offset, device):
        """
        Read the values in a register

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
        Read the values in a register

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
        Returns a list of values from a given address

        :param address: address of start of read
        :type address: int
        :param nvalues: number of values to read
        :type nvalues: int

        :return: values at the address
        :rtype: list of int
        """
        return self._factory.hardware.read_address(address, nvalues)

    def write_address(self, address, values):
        """
        Write a list of values to a given address

        :param address: address of start of read
        :type address: int
        :param values: values to write
        :type values: list of int
        """
        self._factory.hardware.write_address(address, values)

    def configure_40G_core(
        self, core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
    ):
        """
        Configure the 40G code

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
        self._factory.hardware.configure_40G_core(
            core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
        )

    def get_40G_configuration(self, core_id=-1):
        """
        Return a 40G configuration

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned, defaults to -1
        :type core_id: int, optional

        :return: core configuration or list of core configurations
        :rtype: dict or list of dict
        """
        return self._factory.hardware.get_40G_configuration(core_id)

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
        networks

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
        Set the channeliser coefficients to modify the bandpass

        :param array: an N * M array, where N is the number of input
            channels, and M is the number of frequency channels. This is
            encoded as a list comprising N, then M, then the flattened
            array
        :type array: list of int
        """
        self._factory.hardware.set_channeliser_truncation(array)

    def set_beamformer_regions(self, regions):
        """
        Set the frequency regions to be beamformed into a single beam

        :param regions: a list encoding up to 16 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0
            and 7)
        :type regions: list of int
        """
        self._factory.hardware.set_beamformer_regions(regions)

    def initialise_beamformer(self, start_channel, nof_channels, is_first, is_last):
        """
        Initialise the beamformer

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

    def load_calibration_coefficients(self, antenna, calibration_coeffs):
        """
        Load calibration coefficients. These may include any rotation
        matrix (e.g. the parallactic angle), but do not include the
        geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :type antenna: int
        :param calibration_coeffs: a bidirectional complex array of
            coefficients, flattened into a list
        :type calibration_coeffs: list of int
        """
        self._factory.hardware.load_calibration_coefficients(
            antenna, calibration_coeffs
        )

    def load_beam_angle(self, angle_coeffs):
        """
        Load the beam angle

        :param angle_coeffs: list containing angle coefficients for each
            beam
        :type angle_coeffs: list of double
        """
        self._factory.hardware.load_beam_angle(angle_coeffs)

    def load_antenna_tapering(self, tapering_coeffs):
        """
        Loat the antenna tapering coefficients

        :param tapering_coeffs: list of tapering coefficients for each
            antenna
        :type tapering_coeffs: list of double
        """
        self._factory.hardware.load_antenna_tapering(tapering_coeffs)

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

    def set_pointing_delay(self, delay_array, beam_index):
        """
        Specifies the delay in seconds and the delay rate in seconds/second.
        The delay_array specifies the delay and delay rate for each antenna.
        beam_index specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :type delay_array: list of float
        :param beam_index: the beam to which the pointing delay should
            be applied
        :type beam_index: int
        """
        self._factory.hardware.set_pointing_delay(delay_array, beam_index)

    def load_pointing_delay(self, load_time):
        """
        Load the pointing delay at a specified time

        :param load_time: time at which to load the pointing delay
        :type load_time: int
        """
        self._factory.hardware.load_pointing_delay(load_time)

    def configure_integrated_channel_data(self, integration_time=None):
        """
        Configure the transmission of integrated channel data with the
        provided integration time

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        """
        self._factory.hardware.configure_integrated_channel_data(
            integration_time=integration_time
        )

    def configure_integrated_beam_data(self, integration_time=None):
        """
        Configure the transmission of integrated beam data with the provided
        integration time

        :param integration_time: integration time in seconds, defaults to 0.5
        :type integration_time: float, optional
        """
        self._factory.hardware.configure_integrated_beam_data(
            integration_time=integration_time
        )

    def send_raw_data(
        self, sync=False, period=None, timeout=None, timestamp=None, seconds=None
    ):
        """
        Transmit a snapshot containing raw antenna data

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
        """
        self._factory.hardware.send_raw_data(
            sync=sync,
            period=period,
            timeout=timeout,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_channelised_data(
        self,
        number_of_samples=None,
        first_channel=None,
        last_channel=None,
        period=None,
        timeout=None,
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
        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_channelised_data(
            number_of_samples=number_of_samples,
            first_channel=first_channel,
            last_channel=last_channel,
            period=period,
            timeout=timeout,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_channelised_data_continuous(
        self,
        channel_id,
        number_of_samples=None,
        wait_seconds=None,
        timeout=None,
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
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_channelised_data_continuous(
            channel_id,
            number_of_samples=number_of_samples,
            wait_seconds=wait_seconds,
            timeout=timeout,
            timestamp=timestamp,
            seconds=seconds,
        )

    def send_beam_data(self, period=None, timeout=None, timestamp=None, seconds=None):
        """
        Transmit a snapshot containing beamformed data

        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: wqhen to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_beam_data(
            period=period, timeout=timeout, timestamp=timestamp, seconds=seconds
        )

    def stop_data_transmission(self):
        """
        Stop data transmission
        """
        self._factory.hardware.stop_data_transmission()

    def compute_calibration_coefficients(self):
        """
        Compute the calibration coefficients and load them into the
        hardware.
        """
        self._factory.hardware.compute_calibration_coefficients()

    def start_acquisition(self, start_time=None, delay=None):
        """
        Start data acquisitiong

        :param start_time: the time at which to start data acquisition,
            defaults to None
        :type start_time: int, optional
        :param delay: delay start, defaults to 2
        :type delay: int, optional
        """
        self._factory.hardware.start_acquisition(start_time=start_time, delay=delay)

    def set_time_delays(self, delays):
        """
        Set coarse zenith delay for input ADC streams

        :param delays: the delay in samples, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        :type delays: int
        """
        self._factory.hardware.set_time_delays(delays)

    def set_csp_rounding(self, rounding):
        """
        Set output rounding for CSP

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
        Configure link and size of control data

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

    def send_raw_data_synchronised(
        self, period=None, timeout=None, timestamp=None, seconds=None
    ):
        """
        Send synchronised raw data

        :param period: period of time in seconds, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        """
        self._factory.hardware.send_raw_data_synchronised(
            period=period, timeout=timeout, timestamp=timestamp, seconds=seconds
        )

    def check_pending_data_requests(self):
        """
        Check the TPM for pending data requests

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
        timeout=None,
        timestamp=None,
        seconds=None,
    ):
        """
        Continuously send channelised data from a single channel

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
        """
        self._factory.hardware.send_channelised_data_narrowband(
            frequency,
            round_bits,
            number_of_samples=number_of_samples,
            wait_seconds=wait_seconds,
            timeout=timeout,
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
        Return the phase terminal count

        :return: the phase terminal count
        :rtype: int
        """
        return self._factory.hardware._phase_terminal_count

    @phase_terminal_count.setter
    def phase_terminal_count(self, value):
        """
        Set the phase terminal count

        :param value: the phase terminal count
        :type value: int
        """
        self._factory.hardware.phase_terminal_count = value

    def post_synchronisation(self):
        """
        Perform post tile configuration synchronization
        """
        self._factory.hardware.post_synchronisation()

    def sync_fpgas(self):
        """
        Synchronise the FPGAs
        """
        self._factory.hardware.sync_fpgas()

    def calculate_delay(self, current_delay, current_tc, ref_lo, ref_hi):
        """
        Calculate the delay

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