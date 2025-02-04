#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for channelised data from tiles."""
from __future__ import annotations

import json
from copy import copy

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest
from .data_handlers import ChannelDataReceivedHandler

__all__ = ["TestChannel"]


class TestChannel(BaseDaqTest):
    """
    Test we can send channel data from the TPMs to DAQ correctly.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive channel data from your TPMs.
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

    def _send_channel_data(self: TestChannel) -> None:
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "channel",
                    "n_samples": 1024,
                }
            )
        )

    # pylint: disable=too-many-locals
    def _check_channel(self: TestChannel) -> None:
        self.test_logger.debug("Checking received data")
        assert self._data is not None
        assert self._pattern is not None
        assert self._adders is not None
        data = copy(self._data)
        adders = copy(self._adders)
        pattern = copy(self._pattern)
        channels, antennas, polarisations, samples, _ = data.shape
        for channel in range(channels):
            for antenna in range(antennas):
                for polarisation in range(polarisations):
                    sample_idx = TileData.POLS_PER_ANTENNA * channel
                    signal_idx = (
                        antenna % TileData.ANTENNA_COUNT
                    ) * TileData.POLS_PER_ANTENNA + polarisation
                    exp_re = pattern[sample_idx] + adders[signal_idx]
                    exp_im = pattern[sample_idx + 1] + adders[signal_idx]
                    expected_data_real = self._signed(exp_re, "CHANNEL")
                    expected_data_imag = self._signed(exp_im, "CHANNEL")
                    for i in range(samples):
                        if (
                            expected_data_real
                            != data[channel, antenna, polarisation, i, 0]
                            or expected_data_imag
                            != data[channel, antenna, polarisation, i, 1]
                        ):
                            self.test_logger.error("Data Error!")
                            self.test_logger.error(f"Frequency Channel: {channel}")
                            self.test_logger.error(f"Antenna: {antenna}")
                            self.test_logger.error(f"Polarization: {polarisation}")
                            self.test_logger.error(f"Sample index: {i}")
                            self.test_logger.error(
                                f"Expected data real: {expected_data_real}"
                            )
                            self.test_logger.error(
                                f"Expected data imag: {expected_data_real}"
                            )
                            self.test_logger.error(
                                "Received data: "
                                f"{data[channel, antenna, polarisation, i, :]}"
                            )
                            raise AssertionError

    def test(self: TestChannel) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = ChannelDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self._configure_daq("CHANNEL_DATA")
        self.test_logger.debug("Testing channelised data.")
        with self.reset_context():
            self._start_directory_watch()
            self.test_logger.debug("Sending channel data")
            self._configure_and_start_pattern_generator("channel")
            self._send_channel_data()
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator("channel")
            self._stop_directory_watch()

            self._check_channel()
        self.test_logger.info("Test passed for channelised data!")

    # def check_requirements(self: TestChannel) -> tuple[bool, str]:
    #     """
    #     Skip test for the moment.

    #     :returns: False
    #     """
    #     return False, "Test currently skipped"
