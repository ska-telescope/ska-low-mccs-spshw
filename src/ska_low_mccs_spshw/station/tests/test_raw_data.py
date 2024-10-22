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
import os
from copy import copy
from typing import Callable

import numpy as np
from pydaq.persisters import RawFormatFileManager  # type: ignore
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from .base_daq_test import BaseDaqTest

__all__ = ["TestRaw"]


class RawDataReceivedHandler(FileSystemEventHandler):
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
        self._logger: logging.Logger = logger
        self._data_created_callback = data_created_callback
        self._nof_antennas_per_tile = 16
        self._nof_tiles = nof_tiles
        self._tile_id = 0
        self.data = np.zeros(
            (self._nof_tiles * self._nof_antennas_per_tile, 2, 32 * 1024), dtype=np.int8
        )

    def on_created(self: RawDataReceivedHandler, event: FileSystemEvent) -> None:
        """
        Check every event for newly created files to process.

        :param event: Event to check.
        """
        if not event._src_path.endswith(".hdf5") or event.is_directory:
            return
        base_path = os.path.split(event._src_path)[0]
        try:
            raw_file = RawFormatFileManager(root_path=base_path)
            tile_data, timestamps = raw_file.read_data(
                antennas=range(self._nof_antennas_per_tile),
                polarizations=[0, 1],
                n_samples=32 * 1024,
                tile_id=self._tile_id,
            )
            start_idx = self._nof_antennas_per_tile * self._tile_id
            end_idx = self._nof_antennas_per_tile * (self._tile_id + 1)
            self.data[start_idx:end_idx, :, :] = tile_data

            self._data_created_callback(
                data=self.data, last_tile=self._tile_id == self._nof_tiles - 1
            )
            self._tile_id += 1

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error(f"Got error in callback: {repr(e)}, {e}")


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

    def _send_raw_data(self: TestRaw, proxy: MccsDeviceProxy, sync: bool) -> None:
        proxy.SendDataSamples(
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
        self._configure_daq("RAW_DATA")
        self.test_logger.debug("Testing unsynchronised raw data.")
        self._start_directory_watch()
        for tile in self.tile_proxies:
            self.test_logger.debug(f"Sending data for tile {tile.dev_name()}")
            self._configure_and_start_pattern_generator(tile, "jesd")
            self._send_raw_data(tile, sync=False)
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator(tile, "jesd")

        self._check_raw(raw_data_synchronised=False)
        self._data = None
        self.test_logger.info("Test passed for unsynchronised data!")

        self.test_logger.debug("Testing synchronised raw data.")
        for tile in self.tile_proxies:
            self.test_logger.debug(f"Sending data for tile {tile.dev_name()}")
            self._configure_and_start_pattern_generator(tile, "jesd")
            self._send_raw_data(tile, sync=True)
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator(tile, "jesd")

        self._stop_directory_watch()
        self._check_raw(raw_data_synchronised=True)
        self._data = None
        self.test_logger.info("Test passed for synchronised data!")
