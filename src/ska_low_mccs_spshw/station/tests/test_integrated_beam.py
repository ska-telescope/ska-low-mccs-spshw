#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for integrated beamformed data from tiles."""
from __future__ import annotations

import time
from copy import copy

from .base_daq_test import BaseDaqTest
from .data_handlers import IntegratedBeamDataReceivedHandler

__all__ = ["TestIntegratedBeam"]


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
        self: TestIntegratedBeam, integration_time: int
    ) -> None:
        self.component_manager.configure_integrated_beam_data(
            integration_time=integration_time, first_channel=0, last_channel=511
        )

    def _stop_integrated_data(self: TestIntegratedBeam) -> None:
        self.component_manager.stop_integrated_data()

    # pylint: disable=too-many-locals
    def _check_integrated_beam(
        self: TestIntegratedBeam,
        integration_length: int,
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
                    expected_re_sign = self._signed(expected_re, "INT_BEAM")
                    expected_im_sign = self._signed(expected_im, "INT_BEAM")
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

    def _reset(self: TestIntegratedBeam) -> None:
        self.component_manager.stop_integrated_data()
        super()._reset()

    def test(self: TestIntegratedBeam) -> None:
        """A test to show we can stream raw data from each available TPM to DAQ."""
        self._data_handler = IntegratedBeamDataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self.test_logger.debug("Testing integrated beamformed data.")
        with self.reset_context():
            integration_time = 1  # second
            tile = self.tile_proxies[0]
            self._start_integrated_beam_data(integration_time)
            time.sleep(5)
            self._configure_and_start_pattern_generator(
                "beamf", adders=list(range(16)) + list(range(2, 16 + 2))
            )
            self.test_logger.debug(
                f"Sleeping for {integration_time + 0.5} (integration length + 0.5s) sec"
            )
            time.sleep(integration_time + 0.5)
            self._configure_daq(
                "INTEGRATED_BEAM_DATA",
                integrated=True,
                nof_beam_samples=1,
                receiver_frame_size=9000,
            )
            self._start_directory_watch()
            assert self._data_created_event.wait(20)
            integration_length = tile.readregister(
                "fpga1.lmc_integrated_gen.beamf_integration_length"
            )[0]
            accumulator_width = tile.readregister(
                "fpga1.lmc_integrated_gen.beamf_accumulator_width"
            )[0]
            round_bits = tile.readregister(
                "fpga1.lmc_integrated_gen.beamf_scaling_factor"
            )[0]
            self._data_created_event.clear()
            self._stop_integrated_data()
            self._stop_pattern_generator("beamf")
            self._stop_directory_watch()

            self._check_integrated_beam(
                integration_length, accumulator_width, round_bits
            )
        self.test_logger.info("Test passed for integrated beam data!")

    def check_requirements(self: TestIntegratedBeam) -> tuple[bool, str]:
        """
        Skip test due to known bug.

        :returns: False as this test is skipped.
        """
        return False, "This test is skipped due to MCCS-2311"
