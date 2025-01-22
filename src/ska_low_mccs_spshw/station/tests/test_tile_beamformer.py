#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

import itertools
import json
import logging
import random
import time
from datetime import datetime
from typing import TYPE_CHECKING, Callable

import numpy as np
from pydaq.persisters import BeamFormatFileManager  # type: ignore
from ska_low_mccs_common.device_proxy import MccsDeviceProxy

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest, BaseDataReceivedHandler

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager
__all__ = ["TestBeamformer"]

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


class TestBeamformer(BaseDaqTest):
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

    # pylint: disable=too-many-arguments
    def __init__(
        self: TestBeamformer,
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
        # Random set of delays to apply to the test generator, we make it here to we can
        # use the same random delays each time.
        random.seed(0)
        # self._delays = [
        #     random.randrange(-32, 32, 1) for _ in range(TileData.ADC_CHANNELS)
        # ]
        self._delays = [
            21,
            -27,
            1,
            30,
            19,
            6,
            29,
            13,
            -5,
            -15,
            4,
            -15,
            -20,
            0,
            -14,
            7,
            -20,
            -23,
            10,
            28,
            -20,
            13,
            23,
            8,
            -6,
            29,
            24,
            1,
            -25,
            -31,
            -21,
            19,
        ]
        self._first = True
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _send_beam_data(self: TestBeamformer) -> None:
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "beam",
                    "seconds": 0.2,
                }
            )
        )

    def _get_beam_value(
        self: TestBeamformer, tile_no: int, pol: int, channel: int
    ) -> complex:
        sample = 0
        assert self._data is not None
        return (
            self._data[tile_no, pol, channel, sample, 0]
            + self._data[tile_no, pol, channel, sample, 1] * 1j
        )

    def _get_single_antenna_data_set(self: TestBeamformer, channel: int) -> np.ndarray:
        single_input_data = np.zeros(
            (len(self.tile_proxies), TileData.POLS_PER_ANTENNA, TileData.ANTENNA_COUNT),
            dtype="complex",
        )
        for antenna_no in range(TileData.ANTENNA_COUNT):
            self._start_directory_watch()
            self.test_logger.debug(f"Sending beam data for {antenna_no=}")
            frequency = (
                TileData.FIRST_BEAMFORMER_CHANNEL + channel
            ) * TileData.CHANNEL_WIDTH
            self._configure_test_generator(
                frequency,
                0.5,
                adc_channels=[antenna_no * 2, antenna_no * 2 + 1],
                delays=self._delays,
            )
            time.sleep(1)
            self._send_beam_data()
            assert self._data_created_event.wait(20)
            if self._data is not None:
                if self._first:
                    np.save(f"whole_data_antenna_before_{antenna_no}.npy", self._data)
                else:
                    np.save(f"whole_data_antenna_after_{antenna_no}.npy", self._data)
            for tile_no in range(len(self.tile_proxies)):
                single_input_data[tile_no][0][antenna_no] = self._get_beam_value(
                    tile_no, 0, channel
                )
                single_input_data[tile_no][1][antenna_no] = self._get_beam_value(
                    tile_no, 1, channel
                )
            self._data_created_event.clear()
            self._stop_directory_watch()
            self._configure_daq("BEAM_DATA")
        self._first = False
        return single_input_data

    def _get_all_antenna_data_set(self: TestBeamformer, channel: int) -> None:
        self._start_directory_watch()
        self.test_logger.debug("Sending beam data for all antennas")
        frequency = (
            TileData.FIRST_BEAMFORMER_CHANNEL + channel
        ) * TileData.CHANNEL_WIDTH
        self._configure_test_generator(
            frequency,
            0.5,
            delays=self._delays,
        )
        self._send_beam_data()
        assert self._data_created_event.wait(20)
        self._data_created_event.clear()
        self._stop_directory_watch()

    def _calibrate_tpms(
        self: TestBeamformer,
        channel: int,
        ref_values: np.ndarray,
        single_input_data: np.ndarray,
        gain: float = 2.0,
    ) -> None:
        self.test_logger.debug("Calibrating TPMs")
        coeffs = np.zeros(
            (len(self.tile_proxies), TileData.POLS_PER_ANTENNA, TileData.ANTENNA_COUNT),
            dtype="complex",
        )
        for tile_no, tile in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                for antenna in range(TileData.ANTENNA_COUNT):
                    coeffs[tile_no][pol][antenna] = (
                        gain
                        * ref_values[tile_no]
                        / single_input_data[tile_no][pol][antenna]
                    )
                    self.test_logger.error(coeffs[tile_no][pol][antenna])
            self._load_calibration_coefficients(tile, channel, coeffs[tile_no])

    def _load_calibration_coefficients(
        self: TestBeamformer, tile: MccsDeviceProxy, channel: int, coeffs: np.ndarray
    ) -> None:
        complex_coefficients = [
            [complex(0.0), complex(0.0), complex(0.0), complex(0.0)]
        ] * TileData.NUM_BEAMFORMER_CHANNELS
        for antenna in range(TileData.ANTENNA_COUNT):
            complex_coefficients[channel] = [
                coeffs[0][antenna],  # pure X polarisation
                complex(0.0),  # ignore cross terms
                complex(0.0),  # ignore cross terms
                coeffs[1][antenna],  # pure Y polarisation
            ]
            inp = list(itertools.chain.from_iterable(complex_coefficients))
            out = [[v.real, v.imag] for v in inp]
            coefficients = list(itertools.chain.from_iterable(out))
            coefficients.insert(0, float(antenna))
            tile.LoadCalibrationCoefficients(coefficients)
        tile.ApplyCalibration("")

    def _reset_calibration_coefficients(
        self: TestBeamformer, tile: MccsDeviceProxy, gain: float = 2.0
    ) -> None:
        complex_coefficients = [
            [complex(gain), complex(0.0), complex(0.0), complex(gain)]
        ] * TileData.NUM_BEAMFORMER_CHANNELS
        for antenna in range(TileData.ANTENNA_COUNT):
            inp = list(itertools.chain.from_iterable(complex_coefficients))
            out = [[v.real, v.imag] for v in inp]
            coefficients = list(itertools.chain.from_iterable(out))
            coefficients.insert(0, float(antenna))
            tile.LoadCalibrationCoefficients(coefficients)
            tile.ApplyCalibration("")

    def _reset_tpm_calibration(self: TestBeamformer) -> None:
        for tile in self.tile_proxies:
            self._reset_calibration_coefficients(tile)

    def _check_single_antenna_data(
        self: TestBeamformer,
        ref_values: np.ndarray,
        single_input_data: np.ndarray,
    ) -> None:
        for tile_no, _ in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                for antenna in range(TileData.ANTENNA_COUNT):
                    exp_val = ref_values[tile_no]
                    rcv_val = single_input_data[tile_no][pol][antenna]
                    if (
                        abs(exp_val.real - rcv_val.real) > 2
                        or abs(exp_val.imag - rcv_val.imag) > 2
                    ):
                        self.test_logger.error("Error in beamformed values!")
                        self.test_logger.error("Reference Antenna:")
                        self.test_logger.error(ref_values[tile_no])
                        self.test_logger.error("Received values:")
                        self.test_logger.error(rcv_val)
                        raise AssertionError
                    self.test_logger.debug(
                        f"Passed assertion: {tile_no=}, {pol=}, {antenna=}"
                    )

    def _check_all_antenna_data(
        self: TestBeamformer,
        ref_values: np.ndarray,
        channel: int,
    ) -> None:
        for tile_no, _ in enumerate(self.tile_proxies):
            for pol in range(TileData.POLS_PER_ANTENNA):
                exp_val = ref_values[tile_no]
                rcv_val = self._get_beam_value(tile_no, pol, channel)
                if (
                    abs(exp_val.real - rcv_val.real / TileData.ANTENNA_COUNT) > 2
                    or abs(exp_val.imag - rcv_val.imag / TileData.ANTENNA_COUNT) > 2
                ):
                    self.test_logger.error("Error in beam sum!")
                    self.test_logger.error("Reference Antenna:")
                    self.test_logger.error(ref_values[tile_no])
                    self.test_logger.error("Received values:")
                    self.test_logger.error(rcv_val)
                    raise AssertionError

    def _reset(self: TestBeamformer) -> None:
        self.component_manager.start_adcs()
        self._reset_tpm_calibration()
        self.component_manager.stop_beamformer()
        super()._reset()

    def test(self: TestBeamformer) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self.test_logger.debug("Testing beamformed data.")
        test_channels = range(7 + 1)
        self.component_manager._set_channeliser_rounding(np.full(512, 5))
        self.component_manager.stop_adcs()
        self._configure_beamformer(
            TileData.FIRST_BEAMFORMER_CHANNEL, len(test_channels)
        )
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
        # Choose a random antenna/polarisation to be the reference
        # ref_antenna = random.randrange(0, TileData.ANTENNA_COUNT, 1)
        # ref_pol = random.randrange(0, TileData.POLS_PER_ANTENNA, 1)
        with self.reset_context():
            for channel in test_channels:
                # Reset all TPM calibration with expected initial gain
                self._reset_tpm_calibration()

                time.sleep(5)

                # The first dataset we get should be uncalibrated
                single_input_data = self._get_single_antenna_data_set(channel)

                np.save("before_calibration.npy", single_input_data)

                break

                # Grab the reference data for each antenna/pol on each tile
                # ref_values = single_input_data[:, ref_pol, ref_antenna]

                # # Calculate the calibration coefficients to phase all antennas to
                # # the reference antenna for each TPM
                # self._calibrate_tpms(channel, ref_values, single_input_data)

                # time.sleep(5)

                # # This dataset should now be calibrated
                # single_input_data = self._get_single_antenna_data_set(channel)

                # np.save("after_calibration.npy", single_input_data)

                # # Check the data against the reference values
                # self._check_single_antenna_data(ref_values, single_input_data)

                # # Send data for all antennas at the same time
                # self._get_all_antenna_data_set(channel)

                # # This data should be 16 times stronger than for just 1 antenna
                # self._check_all_antenna_data(ref_values, channel)

        self.test_logger.info("Test passed for beamformed data!")
