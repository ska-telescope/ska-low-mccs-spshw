#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for the station beam data rate."""
from __future__ import annotations

import math
import time
from datetime import datetime

from ...tile.tile_data import TileData
from ...tile.time_util import TileTime
from .base_daq_test import BaseDaqTest

__all__ = ["TestStationBeamDataRate"]


class TestStationBeamDataRate(BaseDaqTest):
    """
    Test the station beam data rate.

    ##########
    TEST STEPS
    ##########

    1. Configure the beamformer table for your TPMs to be for the full bandwidth
    2. Start the beamformer.
    3. Measure the data rate from DAQ for 1 min, comparing to expected rate.
    4. Repeat for n iterations.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
       common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your TPMs must be synchronised.
    4. You must have a DAQ available.
    """

    def _configure_beamformer_all_regions(self: TestStationBeamDataRate) -> None:
        """Configure the beamformer table on each TPM to be for the full bandwidth."""
        beamformer_table: list[list[int]] = []
        total_chan = 0
        region = [
            TileData.FIRST_BEAMFORMER_CHANNEL,
            TileData.NUM_BEAMFORMER_CHANNELS,
            0,
            0,
            0,
            3,  # arbitrary non-zero
            1,  # arbirary non-zero
            101,  # arbitrary non-zero
        ]
        start_channel = region[0]
        nchannels = region[1]
        total_chan += nchannels
        subarray_logical_channel = region[4]
        for channel_0 in range(start_channel, start_channel + nchannels, 8):
            entry = [channel_0] + region[2:8]
            entry[3] = subarray_logical_channel
            subarray_logical_channel = subarray_logical_channel + 8
            beamformer_table.append(entry)
        self.component_manager.set_beamformer_table(beamformer_table)

    def _reset(self: TestStationBeamDataRate) -> None:
        self.component_manager.stop_beamformer()
        if self.daq_proxy is not None:
            self.daq_proxy.StopDataRateMonitor()

    def test(self: TestStationBeamDataRate) -> None:
        """
        Test to verify station beam data rate for a number of iterations.

        :raises AssertionError: if the data rate is not as expected.
        """
        self.test_logger.debug("Testing station beam data rate.")
        test_iterations = range(5)  # To be made configurable
        data_rate_check_length = 60  # seconds, to be made configurable
        self._configure_beamformer_all_regions()
        assert self.daq_proxy is not None
        self.daq_proxy.StartDataRateMonitor(1)

        with self.reset_context():
            for iteration in test_iterations:
                beamformer_start_time = datetime.strftime(
                    datetime.fromtimestamp(int(time.time()) + 2), TileTime.RFC_FORMAT
                )
                self.component_manager.start_beamformer(
                    start_time=beamformer_start_time,
                    duration=-1,
                    subarray_beam_id=-1,
                    scan_id=0,
                )
                time.sleep(3)

                assert self.component_manager.is_beamformer_running

                data_rate_start_time = time.time()

                while True:
                    elapsed_time = time.time() - data_rate_start_time

                    current_data_rate = self.daq_proxy.dataRate
                    if not math.isclose(
                        current_data_rate,
                        TileData.FULL_STATION_BEAM_DATA_RATE / 1024**3,  # to gb/s
                        rel_tol=0.1,
                    ):
                        self.test_logger.error(
                            f"Data rate is not as expected: {current_data_rate}"
                        )
                        raise AssertionError("Data rate is not as expected")

                    if elapsed_time > data_rate_check_length:
                        break

                    time.sleep(1)

                self.test_logger.info(f"Test passed for iteration {iteration + 1}")
                self.component_manager.stop_beamformer()

        self.test_logger.info("Test station beamformer data rate passed!")
