#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for beamformed data from tiles."""
from __future__ import annotations

import json
from copy import copy

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest
from .data_handlers import BeamDataReceivedHandler

__all__ = ["TestBeam"]


class TestBeam(BaseDaqTest):
    """
    Test we can send beam data from the TPMs to DAQ correctly.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive beam data from your TPMs.
    2. Configure the pattern generator on each TPM to send a basic repeating pattern.
    3. Send data from each of TPM in sequence, collating the data into a single data
        structure.
    4. Verify the data received matches the input repeating pattern.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
        common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your TPMs must be synchronised.
    4. You must have a DAQ available.
    """

    def _send_beam_data(self: TestBeam) -> None:
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "beam",
                    "seconds": 0.2,
                }
            )
        )

    # pylint: disable=too-many-locals
    def _check_beam(self: TestBeam) -> None:
        self.test_logger.debug("Checking received data")
        assert self._data is not None
        assert self._pattern is not None
        assert self._adders is not None
        data = copy(self._data)
        adders = copy(self._adders)
        pattern = copy(self._pattern)
        tiles, polarisations, channels, samples, _ = data.shape
        for tile in range(tiles):
            for channel in range(channels):
                for polarisation in range(polarisations):
                    # Determine indexes for pattern generator based on knowledge
                    # of how data stream is packaged within FPGA
                    sample_idx = (
                        (channel // TileData.POLS_PER_ANTENNA)
                        * TileData.NUM_FPGA
                        * TileData.POLS_PER_ANTENNA
                        + TileData.POLS_PER_ANTENNA * polarisation
                    )
                    signal_idx = TileData.ANTENNA_COUNT * (
                        channel % TileData.POLS_PER_ANTENNA
                    )
                    # Calculate expected data
                    exp_re = (
                        pattern[sample_idx] + adders[signal_idx]
                    ) * 2**TileData.BEAMF_BIT_SHIFT
                    exp_im = (
                        pattern[sample_idx + 1] + adders[signal_idx]
                    ) * 2**TileData.BEAMF_BIT_SHIFT
                    expected_data_real = self._signed(exp_re, "BEAM")
                    expected_data_imag = self._signed(exp_im, "BEAM")
                    for sample in range(samples):
                        received_data_real = data[
                            tile, polarisation, channel, sample, 0
                        ]
                        received_data_imag = data[
                            tile, polarisation, channel, sample, 1
                        ]

                        if (
                            expected_data_real != received_data_real
                            or expected_data_imag != received_data_imag
                        ):
                            error_message = (
                                f"Data Error!\n"
                                f"Tile: {tile}\n"
                                f"Frequency Channel: {channel}\n"
                                f"Polarization: {polarisation}\n"
                                f"Sample index: {sample}\n"
                                f"Expected data real: {expected_data_real}\n"
                                f"Received data real: {received_data_real}\n"
                                f"Expected data imag: {expected_data_imag}\n"
                                f"Received data imag: {received_data_imag}"
                            )
                            self.test_logger.error(error_message)
                            raise AssertionError(error_message)

    def test(self: TestBeam) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = BeamDataReceivedHandler(
            self.test_logger,
            len(self.tile_proxies),
            TileData.ADC_CHANNELS,
            self._data_received_callback,
        )
        self._configure_daq("BEAM_DATA")
        self.test_logger.debug("Testing beamformed data.")
        with self.reset_context():
            self._start_directory_watch()
            self.test_logger.debug("Sending beam data")
            self._configure_and_start_pattern_generator(
                "beamf", adders=list(range(16)) + list(range(2, 16 + 2))
            )
            self._send_beam_data()
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator("beamf")
            self._stop_directory_watch()

            self._check_beam()
        self.test_logger.info("Test passed for beamformed data!")
