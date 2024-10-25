#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

import logging
import time
from copy import copy
from typing import Callable

import numpy as np
from pydaq.persisters import ChannelFormatFileManager, FileDAQModes  # type: ignore

from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

__all__ = ["TestIntegratedChannel"]


class IntegratedChannelDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: IntegratedChannelDataReceivedHandler,
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
        self._nof_samples = 1
        self._nof_channels = 512
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: IntegratedChannelDataReceivedHandler) -> None:
        """Handle the reading of integrated channel data."""
        raw_file = ChannelFormatFileManager(
            root_path=self._base_path, daq_mode=FileDAQModes.Integrated
        )
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                antennas=range(self._nof_antennas_per_tile),
                polarizations=[0, 1],
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            start_idx = self._nof_antennas_per_tile * tile_id
            end_idx = self._nof_antennas_per_tile * (tile_id + 1)
            self.data[:, start_idx:end_idx, :, :] = tile_data

    def initialise_data(self: IntegratedChannelDataReceivedHandler) -> None:
        """Initialise empty integrated channel data struct."""
        self.data = np.zeros(
            (
                self._nof_channels,
                self._nof_tiles * self._nof_antennas_per_tile,
                self._polarisations_per_antenna,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )


class TestIntegratedChannel(BaseDaqTest):
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

    def _start_integrated_channel_data(self: TestIntegratedChannel) -> None:
        self.component_manager.configure_integrated_channel_data(
            integration_time=1, first_channel=0, last_channel=511
        )

    def _stop_integrated_channel_data(self: TestIntegratedChannel) -> None:
        self.component_manager.stop_integrated_data()

    # pylint: disable=too-many-locals
    def _check_integrated_channel(
        self: TestIntegratedChannel,
        integration_length: float,
        accumulator_width: int,
        round_bits: int,
    ) -> None:
        self.test_logger.debug("Checking received data")
        assert self._data is not None
        assert self._pattern is not None
        assert self._adders is not None
        data = copy(self._data)
        pattern = copy(self._pattern)
        adders = copy(self._adders)

        channels, antennas, polarizations, samples = data.shape
        for channel in range(channels):
            for antenna in range(antennas):
                for polarization in range(polarizations):
                    sample_index = 2 * channel
                    signal_index = (antenna % 16) * 2 + polarization
                    expected_re = pattern[sample_index] + adders[signal_index]
                    expected_im = pattern[sample_index + 1] + adders[signal_index]
                    expected = self._integrated_sample_calc(
                        self._signed(expected_re),
                        self._signed(expected_im),
                        integration_length,
                        round_bits,
                        accumulator_width,
                    )

                    for sample in range(samples):
                        if expected != data[channel, antenna, polarization, sample]:
                            error_message = (
                                f"Data Error!\n"
                                f"Frequency Channel: {channel}\n"
                                f"Antenna: {antenna}\n"
                                f"Polarization: {polarization}\n"
                                f"Sample index: {sample}\n"
                                f"Expected data: {expected}\n"
                                f"Expected data re: {self._signed(expected_re)}\n"
                                f"Expected data im: {self._signed(expected_im)}\n"
                                "Received data: "
                                f"{data[channel, antenna, polarization, sample]}"
                            )
                            self.test_logger.error(error_message)
                            raise AssertionError("Data mismatch detected!")

    def _reset(self: TestIntegratedChannel) -> None:
        self.component_manager.stop_integrated_data()
        super()._reset()

    def test(self: TestIntegratedChannel) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = IntegratedChannelDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self.test_logger.debug("Testing integrated channelised data.")
        with self.reset_context():
            tile = self.tile_proxies[0]
            self._start_integrated_channel_data()
            time.sleep(30)
            self._configure_and_start_pattern_generator("channel")
            self._configure_and_start_pattern_generator(
                "beamf", adders=list(range(16)) + list(range(2, 16 + 2))
            )
            self.test_logger.debug(
                f"Sleeping for {1 + 0.5} (integration length + 0.5s) seconds"
            )
            time.sleep(3 + 0.5)
            self._configure_daq("INTEGRATED_CHANNEL_DATA")
            self._start_directory_watch()
            assert self._data_created_event.wait(20)
            integration_length = tile.readregister(
                "fpga1.lmc_integrated_gen.channel_integration_length"
            )
            accumulator_width = tile.readregister(
                "fpga1.lmc_integrated_gen.channel_accumulator_width"
            )
            round_bits = tile.readregister(
                "fpga1.lmc_integrated_gen.channel_scaling_factor"
            )
            self._data_created_event.clear()
            self._stop_integrated_channel_data()
            self._stop_pattern_generator("channel")
            self._stop_directory_watch()

            self._check_integrated_channel(
                integration_length, accumulator_width, round_bits
            )
        self.test_logger.info("Test passed for integrated channelised data!")
