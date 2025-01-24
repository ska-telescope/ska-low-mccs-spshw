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
import random
import time
from datetime import datetime
from typing import TYPE_CHECKING, Callable

import numpy as np
from pydaq.persisters import BeamFormatFileManager  # type: ignore

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager
__all__ = ["TestTilePointing"]

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class BeamDataReceivedHandler(BaseDataReceivedHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: BeamDataReceivedHandler,
        logger: logging.Logger,
        nof_tiles: int,
        nof_channels: int,
        data_created_callback: Callable,
    ):
        """
        Initialise a new instance.

        :param logger: logger for the handler
        :param nof_tiles: number of tiles to expect data from
        :param nof_channels: number of channels used in the test
        :param data_created_callback: callback to call when data received
        """
        self._nof_samples = 32
        self._nof_channels = nof_channels
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: BeamDataReceivedHandler) -> None:
        """Handle the reading of beam data."""
        raw_file = BeamFormatFileManager(root_path=self._base_path)
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                channels=range(self._nof_channels),
                polarizations=list(range(TileData.POLS_PER_ANTENNA)),
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            self.data[tile_id, :, :, :, 0] = tile_data["real"][:, :, :, 0]
            self.data[tile_id, :, :, :, 1] = tile_data["imag"][:, :, :, 0]

    def initialise_data(self: BeamDataReceivedHandler) -> None:
        """Initialise empty beam data struct."""
        self.data = np.zeros(
            (
                self._nof_tiles,
                TileData.POLS_PER_ANTENNA,
                self._nof_channels,
                self._nof_samples,
                2,  # Real/Imag
            ),
            dtype=np.int16,
        )


class TestTilePointing(BaseDaqTest):
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

    # pylint: disable=too-many-arguments
    def __init__(
        self: TestTilePointing,
        component_manager: SpsStationComponentManager,
        logger: logging.Logger,
        tile_trls: list[str],
        subrack_trls: list[str],
        daq_trl: str,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use.
        :param tile_trls: trls of tiles the station has.
        :param subrack_trls: trls of subracks the station has.
        :param daq_trl: trl of the daq the station has.
        :param component_manager: SpsStation component manager under test.
        """
        # Random seed for repeatability
        random.seed(0)
        # Random set of delays to apply to the test generator, we make it here to we can
        # use the same random delays each time.
        self._delays = [
            random.randrange(-32, 32, 1) for _ in range(TileData.ADC_CHANNELS)
        ]
        # Choose a random antenna/polarisation to be the reference
        self._ref_antenna = random.randrange(0, TileData.ANTENNA_COUNT, 1)
        self._ref_pol = random.randrange(0, TileData.POLS_PER_ANTENNA, 1)

        self._start_freq = 156.25e6
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _send_beam_data(self: TestTilePointing) -> None:
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
        self: TestTilePointing, tile_no: int, pol: int, channel: int
    ) -> complex:
        """
        Get the beam value for a given tile, pol and channel.

        :param tile_no: the tile number to get the beam value for.
        :param pol: the polarisation to get the beam value for.
        :param channel: the channel to get the beam value for.

        :return: the beam value for the given tile, pol and channel.
        """
        sample = 0
        assert self._data is not None
        return (
            self._data[tile_no, pol, channel, sample, 0]
            + self._data[tile_no, pol, channel, sample, 1] * 1j
        )

    def _get_data_set(self: TestTilePointing, channel: int, zero_delays: bool) -> None:
        """
        Get the beam data for each TPM.

        :param channel: the channel to get the beam data for.
        :param zero_delays: whether to zero the delays in the test generator.
        """
        self._start_directory_watch()
        self.test_logger.debug("Sending beam data for all antennas")
        frequency = self._start_freq + (channel * TileData.CHANNEL_WIDTH)
        if zero_delays:
            delays = [0] * TileData.ADC_CHANNELS
        else:
            delays = self._delays
        self._configure_test_generator(
            frequency,
            0.5,
            delays=delays,
        )
        self._send_beam_data()
        assert self._data_created_event.wait(20)
        self._data_created_event.clear()
        self._stop_directory_watch()

    def _set_pointing_delays(self: TestTilePointing) -> None:
        """Set the pointing delays for the TPMs."""
        for tile in self.tile_proxies:
            time_delays_hw = []
            for n in range(TileData.ANTENNA_COUNT):
                time_delays_hw.append(float(self._delays[2 * n]) * 1.25 * 1e-9)
                time_delays_hw.append(0.0)
            time_delays_hw.insert(0, 0.0)
            tile.LoadPointingDelays(time_delays_hw)
            tile.ApplyPointingDelays("")

    def _check_data(
        self: TestTilePointing,
        ref_values_pol_0: list[complex],
        ref_values_pol_1: list[complex],
        corrected_values_pol_0: list[complex],
        corrected_values_pol_1: list[complex],
        channel: int,
    ) -> None:
        """
        Compare the beamformed data against the reference values.

        :param ref_values_pol_0: the reference values for polarisation 0.
        :param ref_values_pol_1: the reference values for polarisation 1.
        :param corrected_values_pol_0: the corrected values for polarisation 0.
        :param corrected_values_pol_1: the corrected values for polarisation 1.
        :param channel: the channel to check the beamformed data for.

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

    def _reset(self: TestTilePointing) -> None:
        self.component_manager.start_adcs()
        self._reset_tpm_calibration(1.0)
        self.component_manager.stop_beamformer()
        self._disable_test_generator()
        super()._reset()

    def test(self: TestTilePointing) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self.test_logger.debug("Testing beamformed data.")
        test_channels = range(7 + 1)
        self.component_manager._set_channeliser_rounding(np.full(512, 5))
        self.component_manager.stop_adcs()
        self._configure_beamformer(self._start_freq)
        self._reset_tpm_calibration(1.0)
        self._clear_pointing_delays()
        start_time = datetime.strftime(
            datetime.fromtimestamp(int(time.time()) + 2), RFC_FORMAT
        )
        self.component_manager.start_beamformer(
            start_time=start_time, duration=-1, subarray_beam_id=-1, scan_id=0
        )
        time.sleep(2)
        self._configure_daq("BEAM_DATA")
        self._data_handler = BeamDataReceivedHandler(
            self.test_logger,
            len(self.tile_proxies),
            len(test_channels),
            self._data_received_callback,
        )
        with self.reset_context():
            for channel in test_channels:
                self._get_data_set(channel, zero_delays=True)

                ref_values_pol_0 = [
                    self._get_beam_value(tile_no, 0, channel)
                    for tile_no in range(len(self.tile_proxies))
                ]
                ref_values_pol_1 = [
                    self._get_beam_value(tile_no, 1, channel)
                    for tile_no in range(len(self.tile_proxies))
                ]

                self._get_data_set(channel, zero_delays=False)

                self._set_pointing_delays()

                self._get_data_set(channel, zero_delays=False)

                corrected_values_pol_0 = [
                    self._get_beam_value(tile_no, 0, channel)
                    for tile_no in range(len(self.tile_proxies))
                ]
                corrected_values_pol_1 = [
                    self._get_beam_value(tile_no, 1, channel)
                    for tile_no in range(len(self.tile_proxies))
                ]

                self._check_data(
                    ref_values_pol_0,
                    ref_values_pol_1,
                    corrected_values_pol_0,
                    corrected_values_pol_1,
                    channel,
                )

        self.test_logger.info("Test passed for beamformed data!")
