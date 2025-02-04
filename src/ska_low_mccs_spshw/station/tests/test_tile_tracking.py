#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for the tile pointing."""
from __future__ import annotations

import json
import time
from datetime import datetime

import numpy as np

from ...tile.tile_data import TileData
from ...tile.time_util import TileTime
from .base_daq_test import BaseDaqTest
from .data_handlers import BeamDataReceivedHandler

__all__ = ["TestTileTracking"]


class TestTileTracking(BaseDaqTest):
    """
    Test the tile beamformer on each TPM.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive beam data from your TPMs.
    2. Send beam data from each TPM with zero delays in the test generator.
    3. Send beam data from each TPM with random delays in the test generator.
    4. Correct the beam data using pointing delays.
    5. Compare the corrected beam data with the reference beam data.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
       common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your TPMs must be synchronised.
    4. You must have a DAQ available.
    """

    def _send_beam_data(self: TestTileTracking) -> None:
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
        self: TestTileTracking, pol: int, channel: int
    ) -> list[complex]:
        """
        Get the beam value for a given pol and channel for all tiles.

        :param pol: the polarisation to get the beam value for.
        :param channel: the channel to get the beam value for.

        :return: the beam value for a given pol and channel for all tiles.
        """
        sample = 0
        assert self._data is not None
        return (
            self._data[:, pol, channel, sample, 0]
            + self._data[:, pol, channel, sample, 1] * 1j
        )

    def _get_data_set(self: TestTileTracking) -> None:
        """Get the beam data for each TPM."""
        self._start_directory_watch()
        self.test_logger.debug("Sending beam data")
        self._send_beam_data()
        assert self._data_created_event.wait(20)
        self._stop_directory_watch()
        self._data_created_event.clear()

    def _set_pointing_delay_rates(self: TestTileTracking) -> None:
        """Set the pointing delays for the TPMs."""
        max_rate = (2**11 - 1) * 1280e-9 / (1024.0 * 1080e-9 * 2**37)
        rates = (np.array(range(16)) - 8) / 8 * max_rate
        time_delays_hw = [0.0]
        for n in range(TileData.ANTENNA_COUNT):
            time_delays_hw.append(0.0)
            # Apply linear delay rate, maximum at extremes.
            time_delays_hw.append(rates[n])
        for tile in self.tile_proxies:
            tile.LoadPointingDelays(time_delays_hw)
            tile.ApplyPointingDelays("")

    def _check_data(
        self: TestTileTracking,
        ref_values_pol_0: list[complex],
        ref_values_pol_1: list[complex],
        corrected_values_pol_0: list[complex],
        corrected_values_pol_1: list[complex],
    ) -> None:
        """
        Compare the beamformed data against the reference values.

        :param ref_values_pol_0: the reference values for polarisation 0.
        :param ref_values_pol_1: the reference values for polarisation 1.
        :param corrected_values_pol_0: the corrected values for polarisation 0.
        :param corrected_values_pol_1: the corrected values for polarisation 1.

        :raises AssertionError: if the beamformed data does not match the
            reference values.
        """

        def values_mismatch(ref: complex, corrected: complex) -> bool:
            return (
                abs(ref.real - corrected.real) > 2 or abs(ref.imag - corrected.imag) > 2
            )

        for tile_no, _ in enumerate(self.tile_proxies):
            if values_mismatch(
                ref_values_pol_0[tile_no], corrected_values_pol_0[tile_no]
            ) or values_mismatch(
                ref_values_pol_1[tile_no], corrected_values_pol_1[tile_no]
            ):
                self.test_logger.error(
                    f"Error in beam pointing for tile {tile_no}:\n"
                    f"Reference value pol0: {ref_values_pol_0[tile_no]}, "
                    f"pol1: {ref_values_pol_1[tile_no]}\n"
                    f"Corrected value pol0: {corrected_values_pol_0[tile_no]}, "
                    f"pol1: {corrected_values_pol_1[tile_no]}"
                )
                raise AssertionError

    def _reset(self: TestTileTracking) -> None:
        self.component_manager.start_adcs()
        self._reset_tpm_calibration(1.0)
        self.component_manager.stop_beamformer()
        self._disable_test_generator()
        super()._reset()

    def test(self: TestTileTracking) -> None:
        """Test to verify HW pointing offsets delays in the test generator."""
        self.test_logger.debug("Testing tile pointing.")
        self.component_manager._set_channeliser_rounding(
            np.full(TileData.NUM_FREQUENCY_CHANNELS, 5)
        )
        self.component_manager.stop_adcs()
        start_freq = 350e6  # Hz, gives exact DC
        self._configure_beamformer(start_freq)
        self._configure_test_generator(
            start_freq, 0.5, delays=[0] * TileData.ADC_CHANNELS
        )
        self._reset_tpm_calibration(1.0)
        self._set_pointing_delay_rates()
        start_time = datetime.strftime(
            datetime.fromtimestamp(int(time.time()) + 2), TileTime.RFC_FORMAT
        )
        self.component_manager.start_beamformer(
            start_time=start_time, duration=-1, subarray_beam_id=-1, scan_id=0
        )
        time.sleep(2)
        self._configure_daq("BEAM_DATA")
        self._data_handler = BeamDataReceivedHandler(
            self.test_logger,
            len(self.tile_proxies),
            8,
            self._data_received_callback,
        )
        iterations = 15
        with self.reset_context():
            for iteration in range(iterations):
                self._get_data_set()

                val = self._get_beam_value(0, int(start_freq / TileData.CHANNEL_WIDTH))
                self.test_logger.debug(
                    f"Reference value iteration {iteration+1}: {val}"
                )
                np.save(f"ref_data_{iteration+1}.npy", val)

                time.sleep(2)

        self.test_logger.info("Test tile tracking passed!")
