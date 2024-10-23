#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

import json
import logging
from copy import copy
from typing import Callable

import numpy as np
from pydaq.persisters import BeamFormatFileManager  # type: ignore
from ska_low_mccs_common.device_proxy import MccsDeviceProxy

from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

__all__ = ["TestBeam"]


class BeamDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: BeamDataReceivedHandler,
        logger: logging.Logger,
        nof_tiles: int,
        data_created_callback: Callable,
    ):
        """
        Initialise a new instance.

        :param logger: logger for the handler
        :param nof_tiles: number of tiles to expect data from
        :param data_created_callback: callback to call when data received
        """
        self._nof_antennas_per_tile = 16
        self._polarisations_per_antenna = 2
        self._nof_samples = 32
        self._nof_channels = 384
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: BeamDataReceivedHandler) -> None:
        """Handle the reading of beam data."""
        raw_file = BeamFormatFileManager(root_path=self._base_path)
        tile_data, timestamps = raw_file.read_data(
            channels=range(self._nof_channels),
            polarizations=[0, 1],
            n_samples=self._nof_samples,
            tile_id=self._tile_id,
        )
        self.data[self._tile_id, :, :, :, 0] = tile_data["real"][:, :, :, 0]
        self.data[self._tile_id, :, :, :, 1] = tile_data["imag"][:, :, :, 0]

    def initialise_data(self: BeamDataReceivedHandler) -> None:
        """Initialise empty beam data struct."""
        self.data = np.zeros(
            (
                self._nof_tiles,
                self._polarisations_per_antenna,
                self._nof_channels,
                self._nof_samples,
                2,  # Real/Imag
            ),
            dtype=np.int16,
        )


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

    def _send_beam_data(self: TestBeam, proxy: MccsDeviceProxy) -> None:
        proxy.SendDataSamples(
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
                    sample_idx = int(channel / 2) * 4 + 2 * polarisation
                    signal_idx = 16 * (channel % 2)
                    exp_re = (pattern[sample_idx] + adders[signal_idx]) * 16
                    exp_im = (pattern[sample_idx + 1] + adders[signal_idx]) * 16
                    expected_data = (
                        self._signed(exp_re, 12, 16),
                        self._signed(exp_im, 12, 16),
                    )

                    for sample in range(samples):
                        received_data_real = data[
                            tile, polarisation, channel, sample, 0
                        ]
                        received_data_imag = data[
                            tile, polarisation, channel, sample, 1
                        ]

                        if (
                            expected_data[0] != received_data_real
                            or expected_data[1] != received_data_imag
                        ):
                            error_message = (
                                f"Data Error!\n"
                                f"Tile: {tile}\n"
                                f"Frequency Channel: {channel}\n"
                                f"Polarization: {polarisation}\n"
                                f"Sample index: {sample}\n"
                                f"Expected data real: {expected_data[0]}\n"
                                f"Received data real: {received_data_real}\n"
                                f"Expected data imag: {expected_data[1]}\n"
                                f"Received data imag: {received_data_imag}"
                            )
                            self.test_logger.error(error_message)
                            raise AssertionError(error_message)

    def test(self: TestBeam) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = BeamDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self._configure_daq("BEAM_DATA")
        self.test_logger.debug("Testing beamformed data.")
        with self.reset_context():
            self._start_directory_watch()
            for tile in self.tile_proxies:
                self.test_logger.debug(f"Sending data for tile {tile.dev_name()}")
                self._configure_and_start_pattern_generator(
                    tile, "beamf", adders=list(range(16)) + list(range(2, 16 + 2))
                )
                self._send_beam_data(tile)
                assert self._data_created_event.wait(20)
                self._data_created_event.clear()
                self._stop_pattern_generator(tile, "beamf")
            self._stop_directory_watch()

            self._check_beam()
        self.test_logger.info("Test passed for beamformed data!")
