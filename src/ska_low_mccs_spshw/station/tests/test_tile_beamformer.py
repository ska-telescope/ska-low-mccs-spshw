#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for the tile beamformer."""
from __future__ import annotations

import itertools
import json
import logging
import random
import time
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from ska_low_mccs_common.device_proxy import MccsDeviceProxy

from ...tile.tile_data import TileData
from ...tile.time_util import TileTime
from .base_daq_test import BaseDaqTest
from .data_handlers import BeamDataReceivedHandler

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager
__all__ = ["TestTileBeamformer"]


class TestTileBeamformer(BaseDaqTest):
    """
    Test the tile beamformer on each TPM.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive beam data from your TPMs.
    2. Send beam data for each antenna in sequence.
    3. Collate the data into a single data structure.
    4. Choose a random reference antenna and polarisation.
    5. Calibrate the TPMs to phase all antennas to the reference antenna.
    6. Resend the beam data for each antenna in sequence.
    7. Collate the data into a single data structure.
    8. Verify the data is now aligned with the reference antenna.
    9. Send beam data for all antennas at the same time.
    10. Collate the data into a single data structure.
    11. Verify the data is now 16 times stronger than for just 1 antenna.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
       common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your TPMs must be synchronised.
    4. You must have a DAQ available.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self: TestTileBeamformer,
        component_manager: SpsStationComponentManager,
        logger: logging.Logger,
        tile_trls: list[str],
        subrack_trls: list[str],
        daq_trl: str,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use.
        :param tile_trls: trls of tiles the station has.
        :param subrack_trls: trls of subracks the station has.
        :param daq_trl: trl of the daq the station has.
        :param component_manager: SpsStation component manager under test.
        """
        # Random seed for repeatability
        randomiser = random.Random(0)
        # Random set of delays to apply to the test generator, we make it here to we can
        # use the same random delays each time.
        self._delays = [
            randomiser.randrange(-32, 32, 1) for _ in range(TileData.ADC_CHANNELS)
        ]
        # Choose a random antenna/polarisation to be the reference
        self._ref_antenna = randomiser.randrange(0, TileData.ANTENNA_COUNT, 1)
        self._ref_pol = randomiser.randrange(0, TileData.POLS_PER_ANTENNA, 1)

        self._start_freq = 156.25e6  # Hz
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _send_beam_data(self: TestTileBeamformer) -> None:
        """Send beam data to the DAQ."""
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "beam",
                    "seconds": 0.2,
                }
            )
        )

    def _get_beam_value(
        self: TestTileBeamformer, tile_no: int, pol: int, channel: int
    ) -> complex:
        """
        Get the beam value for a given tile, pol and channel.

        :param tile_no: the tile number to get the beam value for.
        :param pol: the polarisation to get the beam value for.
        :param channel: the channel to get the beam value for.

        :return: the beam value for the given tile, pol and channel.
        """
        sample = 0
        assert self._data is not None
        return (
            self._data[tile_no, pol, channel, sample, 0]
            + self._data[tile_no, pol, channel, sample, 1] * 1j
        )

    def _get_single_antenna_data_set(
        self: TestTileBeamformer, channel: int
    ) -> np.ndarray:
        """
        Get the beam data for a single antenna on each TPM.

        :param channel: the channel to get the beam data for.

        :return: the beam data for a single antenna on each TPM.
        """
        single_input_data = np.zeros(
            (len(self.tile_proxies), TileData.POLS_PER_ANTENNA, TileData.ANTENNA_COUNT),
            dtype="complex",
        )
        for antenna_no in range(TileData.ANTENNA_COUNT):
            self._start_directory_watch()
            self.test_logger.debug(f"Sending beam data for {antenna_no=}")
            frequency = self._start_freq + (channel * TileData.CHANNEL_WIDTH)
            self._configure_test_generator(
                frequency,
                0.5,
                adc_channels=[
                    antenna_no * TileData.POLS_PER_ANTENNA,
                    antenna_no * TileData.POLS_PER_ANTENNA + 1,
                ],
                delays=self._delays,
            )
            self._send_beam_data()
            assert self._data_created_event.wait(20)
            for tile_no in range(len(self.tile_proxies)):
                single_input_data[tile_no][0][antenna_no] = self._get_beam_value(
                    tile_no, 0, channel
                )
                single_input_data[tile_no][1][antenna_no] = self._get_beam_value(
                    tile_no, 1, channel
                )
            self._stop_directory_watch()
            self._data_created_event.clear()
        return single_input_data

    def _get_all_antenna_data_set(self: TestTileBeamformer, channel: int) -> None:
        """
        Get the beam data for all antennas on each TPM.

        :param channel: the channel to get the beam data for.
        """
        self._start_directory_watch()
        self.test_logger.debug("Sending beam data for all antennas")
        frequency = self._start_freq + (channel * TileData.CHANNEL_WIDTH)
        self._configure_test_generator(
            frequency,
            0.5,
            delays=self._delays,
        )
        self._send_beam_data()
        assert self._data_created_event.wait(20)
        self._stop_directory_watch()
        self._data_created_event.clear()

    def _calibrate_tpms(
        self: TestTileBeamformer,
        channel: int,
        ref_values: np.ndarray,
        single_input_data: np.ndarray,
        gain: float = 2.0,
    ) -> None:
        """
        Calibrate the TPMs to phase all antennas to the reference antenna.

        :param channel: the channel to calibrate the TPMs for.
        :param ref_values: the reference values for each tile.
        :param single_input_data: the input data for each tile.
        :param gain: the gain to apply to the calibration coefficients.
        """
        self.test_logger.debug("Calibrating TPMs")
        coeffs = np.zeros(
            (len(self.tile_proxies), TileData.POLS_PER_ANTENNA, TileData.ANTENNA_COUNT),
            dtype="complex",
        )
        for tile_no, tile in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                for antenna in range(TileData.ANTENNA_COUNT):
                    coeffs[tile_no][pol][antenna] = (
                        gain
                        * ref_values[tile_no]
                        / single_input_data[tile_no][pol][antenna]
                    )
            self.test_logger.debug(
                f"Calibration coeffs for tile {tile_no} : {coeffs[tile_no]}"
            )
            self._load_calibration_coefficients(tile, channel, coeffs[tile_no])

    def _load_calibration_coefficients(
        self: TestTileBeamformer,
        tile: MccsDeviceProxy,
        channel: int,
        coeffs: np.ndarray,
    ) -> None:
        """
        Load the calibration coefficients into the TPMs.

        :param tile: the tile to load the calibration coefficients into.
        :param channel: the channel to load the calibration coefficients for.
        :param coeffs: the calibration coefficients to load.
        """
        complex_coefficients = [
            [complex(0.0), complex(0.0), complex(0.0), complex(0.0)]
        ] * TileData.NUM_BEAMFORMER_CHANNELS
        for antenna in range(TileData.ANTENNA_COUNT):
            complex_coefficients[channel] = [
                coeffs[0][antenna],  # pure X polarisation
                complex(0.0),  # ignore cross terms
                complex(0.0),  # ignore cross terms
                coeffs[1][antenna],  # pure Y polarisation
            ]
            inp = list(itertools.chain.from_iterable(complex_coefficients))
            out = [[v.real, v.imag] for v in inp]
            coefficients = list(itertools.chain.from_iterable(out))
            coefficients.insert(0, float(antenna))
            tile.LoadCalibrationCoefficients(coefficients)
        tile.ApplyCalibration("")

    def _check_single_antenna_data(
        self: TestTileBeamformer,
        ref_values: np.ndarray,
        single_input_data: np.ndarray,
    ) -> None:
        """
        Compare the beamformed data against the reference values.

        :param ref_values: the reference values for each tile.
        :param single_input_data: the input data for each tile.

        :raises AssertionError: if the beamformed data does not match the
            reference values.
        """
        for tile_no, _ in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                for antenna in range(TileData.ANTENNA_COUNT):
                    exp_val = ref_values[tile_no]
                    rcv_val = single_input_data[tile_no][pol][antenna]
                    if (
                        abs(exp_val.real - rcv_val.real) > 2
                        or abs(exp_val.imag - rcv_val.imag) > 2
                    ):
                        self.test_logger.error("Error in beamformed values!")
                        self.test_logger.error("Reference Antenna:")
                        self.test_logger.error(ref_values[tile_no])
                        self.test_logger.error("Received values:")
                        self.test_logger.error(rcv_val)
                        raise AssertionError
                    self.test_logger.debug(
                        f"Passed assertion: {tile_no=}, {pol=}, {antenna=}"
                    )

    def _check_all_antenna_data(
        self: TestTileBeamformer,
        ref_values: np.ndarray,
        channel: int,
    ) -> None:
        """
        Compare the beamformed data against the reference values.

        :param ref_values: the reference values for each tile.
        :param channel: the channel to check the beamformed data for.

        :raises AssertionError: if the beamformed data does not match the
            reference values.
        """
        for tile_no, _ in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                exp_val = ref_values[tile_no]
                rcv_val = self._get_beam_value(tile_no, pol, channel)
                if (
                    abs(exp_val.real - rcv_val.real / TileData.ANTENNA_COUNT) > 2
                    or abs(exp_val.imag - rcv_val.imag / TileData.ANTENNA_COUNT) > 2
                ):
                    self.test_logger.error("Error in beam sum!")
                    self.test_logger.error("Reference Antenna:")
                    self.test_logger.error(ref_values[tile_no])
                    self.test_logger.error("Received values:")
                    self.test_logger.error(rcv_val)
                    raise AssertionError
                self.test_logger.debug(f"Passed assertion: {tile_no=}, {pol=}")

    def _reset(self: TestTileBeamformer) -> None:
        self.component_manager.start_adcs()
        self._reset_tpm_calibration()
        self.component_manager.stop_beamformer()
        self._disable_test_generator()
        super()._reset()

    def test(self: TestTileBeamformer) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self.test_logger.debug("Testing beamformed data.")
        test_channels = range(8)  # Test 8 channels
        self.component_manager._set_channeliser_rounding(
            np.full(TileData.NUM_FREQUENCY_CHANNELS, 5)
        )
        self.component_manager.stop_adcs()
        self._configure_beamformer(self._start_freq)
        self._clear_pointing_delays()
        start_time = datetime.strftime(
            datetime.fromtimestamp(int(time.time()) + 5), TileTime.RFC_FORMAT
        )
        self.component_manager.start_beamformer(
            start_time=start_time, duration=-1, scan_id=0
        )
        time.sleep(5)
        self._configure_daq("BEAM_DATA")
        self._data_handler = BeamDataReceivedHandler(
            self.test_logger,
            len(self.tile_proxies),
            len(test_channels),
            self._data_received_callback,
        )
        with self.reset_context():
            for channel in test_channels:
                # Reset all TPM calibration with expected initial gain
                self._reset_tpm_calibration(gain=2.0)

                # The first dataset we get should be uncalibrated
                single_input_data = self._get_single_antenna_data_set(channel)

                # Grab the reference data for each antenna/pol on each tile
                ref_values = single_input_data[:, self._ref_pol, self._ref_antenna]

                # Calculate the calibration coefficients to phase all antennas to
                # the reference antenna for each TPM
                self._calibrate_tpms(channel, ref_values, single_input_data)

                # This dataset should now be calibrated
                single_input_data = self._get_single_antenna_data_set(channel)

                # Check the data against the reference values
                self._check_single_antenna_data(ref_values, single_input_data)

                # Send data for all antennas at the same time
                self._get_all_antenna_data_set(channel)

                # This data should be 16 times stronger than for just 1 antenna
                self._check_all_antenna_data(ref_values, channel)

        self.test_logger.info("Test passed for beamformed data!")
