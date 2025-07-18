#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""ATest the data transmission from the antenna_buffer to the DAQ."""
from __future__ import annotations

import json
from copy import copy
from typing import Optional

import numpy as np
from ska_low_mccs_common.component.command_proxy import MccsCommandProxy

from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest
from .data_handlers import AntennaBufferDataHandler

__all__ = ["TestAntennaBuffer"]


# pylint: disable=too-many-arguments
class TestAntennaBuffer(BaseDaqTest):
    """
    Test we can read data from the Antenna Buffer to the DAQ correctly.

    ##########
    TEST STEPS
    ##########

    1. Configure data to read from the antenna buffer.
    2. Set up the antenna buffer.
    3. Start recording to the buffer.
    4. Read from the buffer.
    5. Verify that the data is correct.

    #################
    TEST REQUIREMENTS
    #################

    1. Every SPS device in your station must be in adminmode.ENGINEERING, this is
        common for all tests.
    2. Your station must have at least 1 TPM.
    3. Your TPMs must be synchronised.
    4. You must have a DAQ available.
    """

    def test(self: TestAntennaBuffer) -> None:
        """Test the data transmission from the Antenna Buffer to the DAQ."""
        self._data_handler: AntennaBufferDataHandler = AntennaBufferDataHandler(
            self.test_logger, 1, 4, self._data_received_callback
        )
        for fpga in range(TileData.NUM_FPGA):
            self.test_fpga(fpga_id=fpga)
        self.test_logger.info("Test passed for AntennaBuffer data!")

    def test_fpga(
        self: TestAntennaBuffer,
        fpga_id: int = 0,
        tile_ids: Optional[list] = None,
        start_address: int = 512 * 1024 * 1024,
        timestamp_capture_duration: int = 75,
    ) -> None:
        """Test data stream from the Antenna Buffer to DAQ.

        :param fpga_id: FPGA ID to test (default is 0)
        :param tile_ids: a list of Tile IDs to test (default is [0])
        :param start_address: Starting address for data transfer
        :param timestamp_capture_duration: time duration in timestamps.
        """
        if tile_ids is None:
            tile_ids = [0]
        elif len(tile_ids) > 1:
            self.test_logger.error(
                "Currently the Antenna buffer test can only use one tile per test run"
            )
        self.test_logger.info(
            (f"Executing test for fpga_id: {fpga_id} and tile_ids: {tile_ids}")
        )
        self.test_logger.info(f"{start_address =}")
        self.test_logger.info(f"{timestamp_capture_duration =}")

        if fpga_id == 0:
            antenna_ids = [0, 1]
        else:
            antenna_ids = [8, 9]

        tx_mode = "SDN"
        receiver_frame_size = 8320

        self.test_logger.info(f"{antenna_ids =}")
        self.test_logger.info(f"{tx_mode =}")
        self.test_logger.info(f"{receiver_frame_size =}")

        tiles = []
        for tile_id in tile_ids:
            tiles.append(self.tile_proxies[tile_id])

        daq_config = {
            "nof_beam_channels": 384,
            "nof_beam_samples": 32,
            "nof_tiles": len(tiles),
            "nof_antennas": 4,
            "receiver_frame_size": receiver_frame_size,
            "max_filesize": 8,
        }
        with self.reset_context():
            self.test_logger.debug("Starting directory watch")
            self._start_directory_watch()
            self.test_logger.debug("Set up pattern generator")
            self._configure_and_start_pattern_generator(
                "jesd",
                pattern=list(range(1024)),
                adders=[0] * 32,
                ramp1={"polarisation": 0},
                ramp2={"polarisation": 1},
            )
            self._set_up_antenna_buffer(
                tiles=tiles,
                mode=tx_mode,
                ddr_start_byte_address=start_address,
                max_ddr_byte_size=None,
            )

            daq_nof_raw_samples = self._start_antenna_buffer(
                tiles=tiles,
                antenna_ids=antenna_ids,
                start_time=-1,  # Start writting to buffer as soon as possible.
                timestamp_capture_duration=timestamp_capture_duration,
                continuous_mode=False,
            )
            daq_config.update(
                {
                    "nof_raw_samples": int(daq_nof_raw_samples),
                }
            )
            self._configure_daq(
                daq_mode="ANTENNA_BUFFER", integrated=False, **daq_config
            )
            self._read_antenna_buffer(
                tiles=tiles,
            )
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()
            self._stop_pattern_generator("jesd")
            self._check_data(fpga_id)

    def _set_up_antenna_buffer(
        self: TestAntennaBuffer,
        tiles: list,
        mode: str,
        ddr_start_byte_address: int,
        max_ddr_byte_size: Optional[int] = None,
    ) -> None:
        """Set up the antenna buffer.

        :param tiles: set of tiles to set up
        :param mode: network to transmit antenna buffer data to. Options: 'SDN'
                (Science Data Network) and 'NSDN' (Non-Science Data Network)
        :param ddr_start_byte_address: first address in the DDR for antenna buffer
                data to be written in (in bytes).
        :param max_ddr_byte_size: last address for writing antenna buffer data
                (in bytes). If 'None' is chosen, the method will assume the last
                address to be the final address of the DDR chip

        """
        self.test_logger.info("Setting up antenna buffer for all tiles")
        for tile in tiles:
            self.test_logger.info(f"Set up antenna buffer for {tile}")
            return_code, message = tile.SetUpAntennaBuffer(
                json.dumps(
                    {
                        "mode": mode,
                        "DDR_start_address": ddr_start_byte_address,
                        "max_DDR_byte_size": max_ddr_byte_size,
                    }
                )
            )
            self.test_logger.info(f"{return_code =} | {message =}")

    def _start_antenna_buffer(
        self: TestAntennaBuffer,
        tiles: list,
        antenna_ids: list[int],
        start_time: int,
        timestamp_capture_duration: int,
        continuous_mode: bool = False,
    ) -> int:
        """Start the antenna buffer.

        :param tiles: set of tiles to start recording
        :param antenna_ids: List of antenna IDs.
        :param start_time: Start time in seconds since epoch.
        :param timestamp_capture_duration: capture duration in timestamps.
        :param continuous_mode: Whether to run in continuous mode or not.

        :return: daq number of raw samples.
        """
        self.test_logger.info("Starting antenna buffer for all tiles")
        ddr_write_size: list = []

        for tile in tiles:
            self.test_logger.info(f"Start antenna buffer for {tile.dev_name()}")
            start_buffer_args = json.dumps(
                {
                    "antennas": antenna_ids,
                    "start_time": start_time,
                    "timestamp_capture_duration": timestamp_capture_duration,
                    "continuous_mode": continuous_mode,
                }
            )
            start_buffer = MccsCommandProxy(
                tile.dev_name(), "StartAntennaBuffer", self.test_logger
            )

            return_code, message = start_buffer(
                arg=start_buffer_args, run_in_thread=False
            )

            self.test_logger.info(f"{return_code =} | {message =}")

            ddr_write_size.append(tile.ddr_write_size)
        # calculate actual DAQ buffer size in number of raw samples
        # In theory they should all be the same, so we can use the first one
        total_nof_samples = ddr_write_size[0] // 4
        self._data_handler.set_nof_samples(total_nof_samples)
        nof_callback = np.ceil(total_nof_samples / (8 * 1024 * 1024))
        nof_callback = max(nof_callback, 1)
        nof_callback = 2 ** int(np.log2(nof_callback))
        daq_nof_raw_samples = total_nof_samples / nof_callback
        self.test_logger.info(f"{ddr_write_size =}")
        self.test_logger.info(f"{nof_callback =}")
        self.test_logger.info(f"{total_nof_samples =}")
        self.test_logger.info(f"{daq_nof_raw_samples =}")

        return daq_nof_raw_samples

    def _read_antenna_buffer(
        self: TestAntennaBuffer,
        tiles: list,
    ) -> None:
        """Read from the antenna buffer.

        :param tiles: set of tiles to read from
        """
        self.test_logger.info("Reading antenna buffer for all tiles")
        for tile in tiles:
            self.test_logger.info(f"Reading antenna buffer for {tile.dev_name()}")

            read_buffer = MccsCommandProxy(
                tile.dev_name(), "ReadAntennaBuffer", self.test_logger
            )

            return_code, message = read_buffer(run_in_thread=False)

            self.test_logger.info(f"{return_code =} | {message =}")

    def _send_raw_data(self: TestAntennaBuffer, sync: bool) -> None:
        self.test_logger.info("Sending raw data samples (testing)")
        self.component_manager.send_data_samples(
            json.dumps(
                {
                    "data_type": "raw",
                    "seconds": 1,
                    "sync": sync,
                }
            )
        )

    def _check_data(self: TestAntennaBuffer, fpga_id: int) -> None:
        """Check that DAQ data is as expected.

        :param fpga_id: the ID of the fpga to check.

        :raises AssertionError: if the data is not as expected.
        """
        self.test_logger.debug("Checking received data")
        assert self._data is not None
        data = copy(self._data)
        self.test_logger.info(
            f"Unpacking data shape {data.shape} "
            "---> (antenna, polarisation, nof_samples). "
        )
        _, polarisations, nof_samples = data.shape
        for antenna in range(2):
            for polarisation in range(polarisations):
                self.test_logger.info(
                    f"fpga_id: {fpga_id}, antenna: {antenna},"
                    + f" polarisation: {polarisation}"
                )

                signal_data = (
                    np.reshape(
                        data[antenna + fpga_id * 2, polarisation], (nof_samples // 4, 4)
                    )
                    .astype(np.uint8)
                    .astype(np.uint32)
                )
                decoded_signal_data = (
                    (signal_data[:, 0] & 0xFF)
                    | (signal_data[:, 1] << 8)
                    | (signal_data[:, 2] << 16)
                    | (signal_data[:, 3] << 24)
                )

                if polarisation % 2 == 0:
                    seed = decoded_signal_data[0]
                else:
                    seed += 1233
                self.test_logger.info(
                    "Checking incremental 32 bit pattern for "
                    f"antenna {antenna}, pol {polarisation}"
                )
                for sample in range(nof_samples // 4):
                    # exp_value = (seed + sample) & 0xFFFFFFFF
                    exp_value = np.uint32(seed + sample)
                    if exp_value != decoded_signal_data[sample]:
                        self.test_logger.error("Error detected, ramp pattern")
                        self.test_logger.error(f"Antenna index: {str(antenna)}")
                        self.test_logger.error(f"Buffer position: {str(sample)}")
                        self.test_logger.error(f"Expected value: {str(exp_value)}")
                        self.test_logger.error(
                            f"Received value: {str(decoded_signal_data[sample])}"
                        )
                        lo = max(sample - 128, 0)
                        hi = min(sample + 128, nof_samples // 4)
                        self.test_logger.error(decoded_signal_data[lo:hi])
                        self.test_logger.error("ANTENNA BUFFER TEST FAILED!")

                        raise AssertionError

                self.test_logger.info("Data check passed")
