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
from pydaq.persisters import ChannelFormatFileManager  # type: ignore
from ska_low_mccs_common.device_proxy import MccsDeviceProxy

from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

__all__ = ["TestChannel"]


class ChannelDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: ChannelDataReceivedHandler,
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
        self._nof_tiles = nof_tiles
        self._polarisations_per_antenna = 2
        self._nof_samples = 128
        self._nof_channels = 512
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: ChannelDataReceivedHandler) -> None:
        """Handle the reading of channel data."""
        raw_file = ChannelFormatFileManager(root_path=self._base_path)
        tile_data, timestamps = raw_file.read_data(
            channels=range(self._nof_channels),
            antennas=range(self._nof_antennas_per_tile),
            polarizations=[0, 1],
            n_samples=self._nof_samples,
            tile_id=self._tile_id,
        )
        start_idx = self._nof_antennas_per_tile * self._tile_id
        end_idx = self._nof_antennas_per_tile * (self._tile_id + 1)
        self.data[:, start_idx:end_idx, :, :, 0] = tile_data["real"]
        self.data[:, start_idx:end_idx, :, :, 1] = tile_data["imag"]

    def initialise_data(self: ChannelDataReceivedHandler) -> None:
        """Initialise empty channel data struct."""
        self.data = np.zeros(
            (
                self._nof_channels,
                self._nof_tiles * self._nof_antennas_per_tile,
                self._polarisations_per_antenna,
                self._nof_samples,
                2,  # Real/Imag
            ),
            dtype=np.int8,
        )


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

    def _send_channel_data(self: TestChannel, proxy: MccsDeviceProxy) -> None:
        proxy.SendDataSamples(
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
                    sample_idx = 2 * channel
                    signal_idx = (antenna % 16) * 2 + polarisation
                    exp_re = pattern[sample_idx] + adders[signal_idx]
                    exp_im = pattern[sample_idx + 1] + adders[signal_idx]
                    exp = (self._signed(exp_re), self._signed(exp_im))
                    for i in range(samples):
                        if (
                            exp[0] != data[channel, antenna, polarisation, i, 0]
                            or exp[1] != data[channel, antenna, polarisation, i, 1]
                        ):
                            self.test_logger.error("Data Error!")
                            self.test_logger.error(f"Frequency Channel: {channel}")
                            self.test_logger.error(f"Antenna: {antenna}")
                            self.test_logger.error(f"Polarization: {polarisation}")
                            self.test_logger.error(f"Sample index: {i}")
                            self.test_logger.error(f"Expected data: {exp}")
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
            for tile in self.tile_proxies:
                self.test_logger.debug(f"Sending data for tile {tile.dev_name()}")
                self._configure_and_start_pattern_generator(tile, "channel")
                self._send_channel_data(tile)
                assert self._data_created_event.wait(20)
                self._data_created_event.clear()
                self._stop_pattern_generator(tile, "channel")

            self._check_channel()
        self.test_logger.info("Test passed for channelised data!")

    def check_requirements(self: TestChannel) -> tuple[bool, str]:
        """
        Skip test for the moment.

        :returns: False
        """
        return False, "Test currently skipped"
