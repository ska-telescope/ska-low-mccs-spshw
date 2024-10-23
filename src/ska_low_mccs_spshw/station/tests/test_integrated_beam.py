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
from pydaq.persisters import BeamFormatFileManager, FileDAQModes  # type: ignore
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.events import FileSystemEvent

from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

__all__ = ["TestIntegratedBeam"]


# pylint: disable=too-many-instance-attributes
class IntegratedBeamDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: IntegratedBeamDataReceivedHandler,
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
        self._polarisations_per_antenna = 2
        self._nof_samples = 1
        self._nof_channels = 384
        self.data = np.zeros(
            (
                self._polarisations_per_antenna,
                self._nof_channels,
                self._nof_tiles,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )

    def on_created(
        self: IntegratedBeamDataReceivedHandler, event: FileSystemEvent
    ) -> None:
        """
        Check every event for newly created files to process.

        :param event: Event to check.
        """
        if not event._src_path.endswith(".hdf5") or event.is_directory:
            return
        base_path = os.path.split(event._src_path)[0]
        try:
            raw_file = BeamFormatFileManager(
                root_path=base_path, daq_mode=FileDAQModes.Integrated
            )
            tile_data, timestamps = raw_file.read_data(
                channels=range(self._nof_channels),
                polarizations=[0, 1],
                n_samples=self._nof_samples,
                tile_id=self._tile_id,
            )
            self.data[:, :, self._tile_id, :] = tile_data[:, :, 0, :]

            self._data_created_callback(
                data=self.data, last_tile=self._tile_id == self._nof_tiles - 1
            )
            self._tile_id += 1

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error(f"Got error in callback: {repr(e)}, {e}")

    def reset(self: IntegratedBeamDataReceivedHandler) -> None:
        """Reset instance variables for re-use."""
        self._tile_id = 0
        self.data = np.zeros(
            (
                self._polarisations_per_antenna,
                self._nof_channels,
                self._nof_tiles,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )


class TestIntegratedBeam(BaseDaqTest):
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

    def _start_integrated_beam_data(
        self: TestIntegratedBeam, proxy: MccsDeviceProxy
    ) -> None:
        proxy.ConfigureIntegratedBeamData(
            json.dumps(
                {
                    "integration_time": 1,
                }
            )
        )

    def _stop_integrated_beam_data(
        self: TestIntegratedBeam, proxy: MccsDeviceProxy
    ) -> None:
        proxy.StopIntegratedData()

    # pylint: disable=too-many-locals
    def _check_integrated_beam(
        self: TestIntegratedBeam,
        integration_length: float,
        accumulator_width: int,
        round_bits: int,
    ) -> None:
        assert self._data is not None
        assert self._pattern is not None
        assert self._adders is not None
        data = copy(self._data)
        pattern = copy(self._pattern)
        adders = copy(self._adders)

        pol, ch, tile, sam = data.shape
        for channel in range(ch):
            for tile_id in range(tile):
                for polarization in range(pol):
                    sample_index = int(channel / 2) * 4 + 2 * polarization
                    signal_index = 16 * (channel % 2)
                    expected_re = (pattern[sample_index] + adders[signal_index]) * 16
                    expected_im = (
                        pattern[sample_index + 1] + adders[signal_index]
                    ) * 16
                    expected_re_sign = self._signed(expected_re, 12, 12)
                    expected_im_sign = self._signed(expected_im, 12, 12)
                    expected = self._integrated_sample_calc(
                        expected_re_sign,
                        expected_im_sign,
                        integration_length,
                        round_bits,
                        accumulator_width,
                    )

                    for sample in range(
                        1
                    ):  # Adjust if multiple samples are considered later
                        if expected != data[polarization, channel, tile_id, sample]:
                            error_message = (
                                f"Data Error!\n"
                                f"Frequency Channel: {channel}\n"
                                f"Tile: {tile_id}\n"
                                f"Polarization: {polarization}\n"
                                f"Sample index: {sample}\n"
                                f"Expected data: {expected}\n"
                                "Expected data re: "
                                f"{expected_re} ({hex(expected_re)})\n"
                                "Expected data im: "
                                f"{expected_im} ({hex(expected_im)})\n"
                                "Received data: "
                                f"{data[polarization, channel, tile_id, sample]}"
                            )
                            self.test_logger.error(error_message)
                            raise AssertionError("Data mismatch detected!")

    def test(self: TestIntegratedBeam) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = IntegratedBeamDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self._configure_daq("INTEGRATED_BEAM_DATA")
        self.test_logger.debug("Testing integrated beam data.")
        with self.reset_context():
            self._start_directory_watch()
            for tile in self.tile_proxies:
                self.test_logger.debug(f"Sending data for tile {tile.dev_name()}")
                self._configure_and_start_pattern_generator(
                    tile, "beamf", adders=list(range(16)) + list(range(2, 16 + 2))
                )
                self._start_integrated_beam_data(tile)
                assert self._data_created_event.wait(20)
                integration_length = self.tile_proxies[0].readregister(
                    "fpga1.lmc_integrated_gen.beamf_integration_length"
                )
                accumulator_width = self.tile_proxies[0].readregister(
                    "fpga1.lmc_integrated_gen.beamf_accumulator_width"
                )
                round_bits = self.tile_proxies[0].readregister(
                    "fpga1.lmc_integrated_gen.beamf_scaling_factor"
                )
                self._data_created_event.clear()
                self._stop_integrated_beam_data(tile)
                self._stop_pattern_generator(tile, "beamf")

            self._check_integrated_beam(
                integration_length, accumulator_width, round_bits
            )
        self.test_logger.info("Test passed for integrated beam data!")
