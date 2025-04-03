#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for raw data from tiles."""
from __future__ import annotations

import json
from copy import copy

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest
from .data_handlers import RawDataReceivedHandler

__all__ = ["TestRaw"]


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
                    # The pattern should repeat on this cadence
                    if sample % TileData.ADC_FRAME_LENGTH == 0:
                        sample_idx = 0
                    signal_idx = (
                        antenna % TileData.ANTENNA_COUNT
                    ) * TileData.POLS_PER_ANTENNA + polarisation
                    exp = pattern[sample_idx] + adders[signal_idx]
                    if self._signed(exp, "RAW") != data[antenna, polarisation, sample]:
                        self.test_logger.error("Data Error!")
                        self.test_logger.error(f"Antenna: {antenna}")
                        self.test_logger.error(f"Polarization: {polarisation}")
                        self.test_logger.error(f"Sample index: {sample}")
                        self.test_logger.error(
                            f"Expected data: {self._signed(exp, 'RAW')}"
                        )
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
            assert self._data_created_event.wait(100)
            self._data_created_event.clear()
            self._stop_pattern_generator("jesd")
            self._check_raw(raw_data_synchronised=sync)
        self.test_logger.info(f"Test passed for {description} data!")
