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
from pydaq.persisters import RawFormatFileManager  # type: ignore

from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

__all__ = ["TestRaw"]


class RawDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: RawDataReceivedHandler,
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
        self._nof_samples = 32 * 1024  # Raw ADC: 32KB per polarisation
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: RawDataReceivedHandler) -> None:
        """Handle the reading of raw data."""
        raw_file = RawFormatFileManager(root_path=self._base_path)
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                antennas=range(self._nof_antennas_per_tile),
                polarizations=[0, 1],
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            start_idx = self._nof_antennas_per_tile * tile_id
            end_idx = self._nof_antennas_per_tile * (tile_id + 1)
            self.data[start_idx:end_idx, :, :] = tile_data

    def initialise_data(self: RawDataReceivedHandler) -> None:
        """Initialise empty raw data struct."""
        self.data = np.zeros(
            (
                self._nof_tiles * self._nof_antennas_per_tile,
                self._polarisations_per_antenna,
                self._nof_samples,
            ),
            dtype=np.int8,
        )


class TestRaw(BaseDaqTest):
    """
    Test we can send raw data from the TPMs to DAQ correctly.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive raw data from your TPMs.
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

    def _send_raw_data(self: TestRaw, sync: bool) -> None:
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "raw",
                    "seconds": 1,
                    "sync": sync,
                }
            )
        )

    def _check_raw(self: TestRaw, raw_data_synchronised: bool = False) -> None:
        self.test_logger.debug("Checking received data")
        assert self._data is not None
        assert self._pattern is not None
        assert self._adders is not None
        data = copy(self._data)
        adders = copy(self._adders)
        pattern = copy(self._pattern)
        ant, pol, sam = data.shape
        if raw_data_synchronised:
            sam = int(sam / 8)
        for antenna in range(ant):
            for polarisation in range(pol):
                for sample in range(sam):
                    if sample % 864 == 0:  # Oversampling factor, 32 * 27
                        sample_idx = 0
                    signal_idx = (antenna % 16) * 2 + polarisation
                    exp = pattern[sample_idx] + adders[signal_idx]
                    if self._signed(exp) != data[antenna, polarisation, sample]:
                        self.test_logger.error("Data Error!")
                        self.test_logger.error(f"Antenna: {antenna}")
                        self.test_logger.error(f"Polarization: {polarisation}")
                        self.test_logger.error(f"Sample index: {sample}")
                        self.test_logger.error(f"Expected data: {self._signed(exp)}")
                        self.test_logger.error(
                            f"Received data: {data[antenna, polarisation, sample]}"
                        )
                        raise AssertionError
                    sample_idx += 1

    def test(self: TestRaw) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = RawDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self._test_raw_data(sync=False, description="unsynchronised")
        self._test_raw_data(sync=True, description="synchronised")

    def _test_raw_data(self: TestRaw, sync: bool, description: str) -> None:
        self.test_logger.debug(f"Testing {description} raw data.")

        self._configure_daq("RAW_DATA")
        with self.reset_context():
            self._start_directory_watch()
            self.test_logger.debug("Sending raw data")
            self._configure_and_start_pattern_generator("jesd")
            self._send_raw_data(sync=sync)
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator("jesd")
            self._check_raw(raw_data_synchronised=sync)
        self.test_logger.info(f"Test passed for {description} data!")
