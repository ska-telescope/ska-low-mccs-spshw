# pylint: disable=too-many-lines
#
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of the TPM driver."""
from __future__ import annotations

import logging
import time
import unittest.mock
from typing import Any

import numpy as np
import pytest
from pyfabil.base.definitions import LibraryError
from ska_control_model import CommunicationStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.tile import TileSimulator, TpmDriver
from ska_low_mccs_spshw.tile.tpm_status import TpmStatus


# pylint: disable=too-many-arguments
@pytest.fixture(name="tpm_driver")
def tpm_driver_fixture(
    logger: logging.Logger,
    tile_id: int,
    station_id: int,
    tpm_version: str,
    callbacks: MockCallableGroup,
    tile_simulator: TileSimulator,
) -> TpmDriver:
    """
    Return a TPMDriver using a tile_simulator.

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`
    :param tile_id: the unique ID for the tile
    :param station_id: the ID of the station to which this tile belongs.
    :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
    :param callbacks: dictionary of driver callbacks.
    :param tile_simulator: The tile used by the TpmDriver.

    :return: a TpmDriver driving a simulated tile
    """
    return TpmDriver(
        logger,
        tile_id,
        station_id,
        tile_simulator,
        tpm_version,
        callbacks["communication_status"],
        callbacks["component_state"],
    )


class TestTpmDriver:  # pylint: disable=too-many-public-methods
    """
    Unit test class for the TPMDriver.

    This class contains unit tests designed to validate the
    functionality of the TPMDriver in software environments.

    These unit tests do not require any hardware setup or interaction,
    making them suitable for testing the TPMDriver purely in software-
    based scenarios.
    """

    def test_start_communicating_when_communication_already_established(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the start_communicating method when communication already ESTABLISHED.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: A dictionary used to assert callbacks.
        """
        # Arrange
        tpm_driver._update_communication_state(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        tile_simulator.connect = unittest.mock.Mock()  # type: ignore[assignment]

        # Act
        tpm_driver.start_communicating()

        # Assert
        tile_simulator.connect.assert_not_called()
        callbacks["communication_status"].assert_not_called()

    def test_communication_when_connection_failed(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the start_communication function in failure case.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: A dictionary used to assert callbacks.
        """
        # Arrange
        tpm_driver._update_communication_state(CommunicationStatus.DISABLED)
        tile_simulator.connect = unittest.mock.Mock(  # type: ignore[assignment]
            side_effect=LibraryError("attribute mocked to fail")
        )

        # Act
        tpm_driver.start_communicating()

        # Assert
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_not_called()
        assert tpm_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED
        assert tpm_driver._tpm_status == TpmStatus.UNCONNECTED

    def test_stop_communicating_when_communication_already_disabled(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the stop_communicating method when communication already ESTABLISHED.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: A dictionary used to assert callbacks.
        """
        # Arrange
        assert tpm_driver._communication_state == CommunicationStatus.DISABLED
        tile_simulator.connect = unittest.mock.Mock()  # type: ignore[assignment]

        # Act
        tpm_driver.stop_communicating()

        # Assert
        tile_simulator.connect.assert_not_called()
        callbacks["communication_status"].assert_not_called()

    def test_stop_communicating(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the stop_communicating method when communication is ESTABLISHED.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: A dictionary used to assert callbacks.
        """
        # Arrange
        tpm_driver._update_communication_state(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        tpm_driver._poll = unittest.mock.Mock()  # type: ignore[assignment]

        # Act
        tpm_driver._start_polling_event.set()
        time.sleep(tpm_driver._poll_rate / 1.1)

        # Assert
        tpm_driver._poll.assert_called_once()

        # Act
        tpm_driver.stop_communicating()

        # Assert no more calls after the stop communicating
        time.sleep(tpm_driver._poll_rate * 2 + 1.5)
        tpm_driver._poll.assert_called_once()

    def test_poll_when_not_communicating(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
    ) -> None:
        """
        Test the behavior of the `poll` method when the TPM driver is not communicating.

        :param tpm_driver: The instance of the TPM driver being tested.
        """
        # Arrange
        tpm_driver._update_communication_state(CommunicationStatus.DISABLED)
        tpm_driver.start_connection = unittest.mock.Mock()  # type: ignore[assignment]

        # Act
        tpm_driver._poll()

        # Assert
        tpm_driver.start_connection.assert_called_once()

    def test_poll_with_tile_failure(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
    ) -> None:
        """
        Test the behavior of the `poll` method when there is a tile failure.

        :param tpm_driver: The instance of the TPM driver being tested.
        """
        # Arrange
        tpm_driver._update_communication_state(CommunicationStatus.ESTABLISHED)
        tpm_driver.tpm_disconnected = unittest.mock.Mock()  # type: ignore[assignment]
        tpm_driver.tile = None

        # Act
        tpm_driver._poll()

        # Assert
        tpm_driver.tpm_disconnected.assert_called_once()

    def test_write_register(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the write register function.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock()  # type: ignore

        # Act
        tpm_driver.write_register("fpga1.dsp_regfile.stream_status.channelizer_vld", 2)

        # Assert
        tile_simulator.tpm.write_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [2]
        )

        # Act
        tpm_driver.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [4]
        )

        # Assert
        tile_simulator.tpm.write_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld", [4]
        )

    def test_write_unknown_register(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test writing to a unknown register.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock()  # type: ignore

        # Act
        tpm_driver.write_register("unknown", 17)

        # Assert: We should not be able to write to a incorrect register
        tile_simulator.tpm.write_register.assert_not_called()  # type: ignore

    def test_write_register_failure(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the write register function under a failure.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.write_register = unittest.mock.Mock(  # type: ignore
            side_effect=Exception("Mocked exception")
        )
        # Check that the exception is caught
        tpm_driver.write_register("fpga1.dsp_regfile.stream_status.channelizer_vld", 2)

    def test_read_register(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the read register function.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock(  # type: ignore
            return_value=3
        )

        # Act
        value_read = tpm_driver.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )

        # Assert
        tile_simulator.tpm.read_register.assert_called_with(  # type: ignore
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )
        assert value_read == [3]

    def test_read_unknown_register(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test reading a unknown register.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock()  # type: ignore

        # Act
        value_read = tpm_driver.read_register("unknown")

        # Assert: We should not be able to read to a incorrect register
        tile_simulator.tpm.read_register.assert_not_called()  # type: ignore
        assert value_read == []

    def test_read_register_failure(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the read register function under a failure.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm.read_register = unittest.mock.Mock(  # type: ignore
            side_effect=Exception("Mocked exception")
        )
        # Check that the exception is caught
        tpm_driver.read_register("fpga1.dsp_regfile.stream_status.channelizer_vld")

    def test_write_read_address(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test we can write and read addresses on the tile_simulator.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()

        # Act
        tpm_driver.write_address(4, [2, 3, 4, 5])
        read_value = tpm_driver.read_address(4, 4)

        # Assert
        assert read_value == [2, 3, 4, 5]

        # Check exceptions are caught.
        tile_simulator.tpm = None
        tpm_driver.write_address(4, [2, 3, 4, 5])

    def test_read_tile_attributes(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that tpm_driver can read attributes from tile_simulator.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        assert tile_simulator.tpm is not None
        tile_simulator.tpm._is_programmed = True
        tpm_driver._tpm_status = TpmStatus.INITIALISED
        mocked_sync_time = 2
        tile_simulator.tpm._register_map["fpga1.pps_manager.sync_time_val"] = (
            mocked_sync_time
        )

        # assert the tpm_driver has different values to the simulator
        assert tpm_driver.adc_rms != list(tile_simulator._adc_rms)
        assert tpm_driver.adc_rms != tile_simulator._adc_rms
        assert tpm_driver.pps_delay != tile_simulator._pps_delay
        assert tpm_driver.fpga_reference_time != pytest.approx(mocked_sync_time)

        # update values to read from simulation.
        tpm_driver._update_attributes()

        # Assert values have been updated.
        assert tpm_driver.adc_rms == list(tile_simulator._adc_rms)
        assert tpm_driver.pps_delay == tile_simulator._pps_delay
        assert tpm_driver.fpga_reference_time == pytest.approx(mocked_sync_time)

    def test_dumb_read_tile_attributes(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Dumb test of attribute read.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()
        assert tile_simulator.tpm is not None

        _ = tpm_driver.register_list
        tpm_driver._get_register_list()
        _ = tpm_driver.pps_present
        # _ = tpm_driver._check_pps_present()
        _ = tpm_driver.sysref_present
        _ = tpm_driver.clock_present
        _ = tpm_driver.pll_locked

        assert tpm_driver.is_beamformer_running == tpm_driver._is_beamformer_running
        assert tpm_driver.pending_data_requests == tpm_driver._pending_data_requests
        assert tpm_driver.phase_terminal_count == tpm_driver._phase_terminal_count
        assert tpm_driver.test_generator_active == tpm_driver._test_generator_active

    def test_dumb_write_tile_attributes(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Dumb test of attribute write. Just check that the attributes can be written.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()
        tile_simulator.FPGAS_TIME = [2, 2]
        assert tile_simulator.tpm is not None
        tile_simulator._timestamp = 2

        tpm_driver.channeliser_truncation = [4] * 512
        _ = tpm_driver.channeliser_truncation
        tpm_driver.static_delays = [12.0] * 32
        _ = tpm_driver.static_delays
        tpm_driver.csp_rounding = np.array([2] * 384)
        _ = tpm_driver.csp_rounding
        tpm_driver.preadu_levels = [12.0] * 32
        _ = tpm_driver.preadu_levels

    def test_set_beamformer_regions(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test the set_beamformer_regions command.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()

        tpm_driver.set_beamformer_regions(
            [[64, 32, 1, 0, 0, 0, 0, 0], [128, 8, 0, 2, 32, 1, 1, 1]]
        )
        # check that exceptions are caught.
        tile_simulator.set_beamformer_regions = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("Mocked exception"))
        )

        tpm_driver.set_beamformer_regions(
            [[64, 32, 1, 0, 0, 0, 0, 0], [128, 8, 0, 2, 32, 1, 1, 1]]
        )

    def test_tpm_status(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the tpm status reports as expected.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        assert tpm_driver._tpm_status == TpmStatus.UNKNOWN
        # just used to call update_tpm_status and cover the tpm_status property in test

        assert tpm_driver.tpm_status == TpmStatus.UNCONNECTED

        tile_simulator.connect()
        tile_simulator.tpm._is_programmed = False  # type: ignore
        tpm_driver._update_communication_state(CommunicationStatus.ESTABLISHED)

        tpm_driver._update_tpm_status()
        assert tpm_driver.tpm_status == TpmStatus.UNPROGRAMMED

        tile_simulator.tpm._is_programmed = True  # type: ignore
        tpm_driver._update_communication_state(CommunicationStatus.ESTABLISHED)

        tpm_driver._update_tpm_status()
        assert tpm_driver.tpm_status == TpmStatus.PROGRAMMED

        # This operation is performed by a poll. Done manually here for speed.
        # tpm_driver._tile_id = tile_simulator._tile_id
        tile_simulator.initialise(0, 0, 0, True, False)
        time.sleep(0.1)

        tpm_driver._update_tpm_status()
        assert tpm_driver.tpm_status == TpmStatus.INITIALISED

        tpm_driver._check_channeliser_started = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=True)
        )
        tpm_driver._update_tpm_status()
        assert tpm_driver.tpm_status == TpmStatus.SYNCHRONISED

        # tile_simulator._tile_id = 8
        # tpm_driver._update_tpm_status()
        # assert tpm_driver.tpm_status == TpmStatus.PROGRAMMED

        # mock to fail
        tile_simulator.is_programmed = unittest.mock.Mock(  # type: ignore[assignment]
            side_effect=LibraryError("attribute mocked to fail")
        )
        tpm_driver._update_tpm_status()
        assert tpm_driver._tpm_status == TpmStatus.UNCONNECTED

        tpm_driver.tpm_status = TpmStatus.UNKNOWN
        assert tpm_driver._tpm_status == TpmStatus.UNKNOWN

    @pytest.mark.xfail(
        reason="A exception will reset the tile_id to zero, do we want this?"
    )
    def test_get_tile_id(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test get_tile_id method.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Mock a connection to the TPM.
        tile_simulator.connect()
        assert tile_simulator.tpm

        # check that we can get the tile_id from simulator
        mocked_tile_id = 3
        assert tpm_driver.get_tile_id() != mocked_tile_id
        tile_simulator._tile_id = mocked_tile_id
        assert tpm_driver.get_tile_id() == mocked_tile_id
        assert tpm_driver._tile_id == mocked_tile_id

        # mocked error case
        mock_libraryerror = unittest.mock.Mock(  # type: ignore[assignment]
            side_effect=LibraryError("attribute mocked to fail")
        )
        tile_simulator.get_tile_id = (  # type: ignore[assignment]
            unittest.mock.MagicMock(side_effect=mock_libraryerror)
        )
        assert tpm_driver.get_tile_id() == mocked_tile_id
        assert tpm_driver._tile_id == mocked_tile_id

    def test_download_firmware(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the download firmware function.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: dictionary of driver callbacks.
        """
        # Mock a connection to the TPM.
        tile_simulator.connect()
        tpm_driver._check_programmed()
        assert tpm_driver.is_programmed is False

        tpm_driver.download_firmware("bitfile")
        tpm_driver._check_programmed()
        assert tpm_driver.is_programmed is True

        # Mock a failed download.
        tile_simulator.is_programmed = unittest.mock.Mock(  # type: ignore[assignment]
            return_value=False
        )
        tpm_driver._update_attributes()
        tpm_driver._check_programmed()
        assert tpm_driver.is_programmed is False

        tpm_driver.download_firmware("bitfile")
        tpm_driver._check_programmed()
        assert tpm_driver.is_programmed is False

    def test_set_tile_id(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that we can get the tile_id from the mocked Tile.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Mock a connection to the TPM.
        tile_simulator.connect()

        # Update attributes and check driver updates
        tpm_driver._update_attributes()
        assert tpm_driver._station_id == tile_simulator._station_id
        tpm_driver._tile_id = tile_simulator._tile_id

        # mock programmed state
        tpm_driver._is_programmed = True

        # Set tile_id case
        tpm_driver._station_id = 2
        tpm_driver.tile_id = 5
        assert tile_simulator._station_id == 2
        assert tile_simulator._tile_id == 5

        # Set station_id case
        tpm_driver._tile_id = 2
        tpm_driver.station_id = 5
        assert tile_simulator._station_id == 5
        assert tile_simulator._tile_id == 2

        # Mocked to fail
        initial_tile_id = tpm_driver._tile_id
        initial_station_id = tpm_driver._station_id
        tile_simulator.set_station_id = unittest.mock.Mock(  # type: ignore[assignment]
            side_effect=LibraryError("attribute mocked to fail")
        )
        # set station_id with mocked failure
        tpm_driver._tile_id = initial_tile_id + 1
        tpm_driver.station_id = initial_station_id + 1
        assert tile_simulator._station_id == initial_station_id
        assert tile_simulator._tile_id == initial_tile_id

        # set tile_id with mocked failure
        tpm_driver._station_id = initial_station_id + 1
        tpm_driver.tile_id = initial_tile_id + 1
        assert tile_simulator._station_id == initial_station_id
        assert tile_simulator._tile_id == initial_tile_id

    def test_start_acquisition(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the start acquisition function.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: dictionary of mock callbacks
        """
        # setup mocked tile.
        tile_simulator.connect()
        tpm_driver._is_programmed = True

        # -------------------------
        # First Initialse the Tile.
        # -------------------------
        # check the fpga time is not moving
        initial_time = tpm_driver.fpgas_time
        time.sleep(1.5)
        final_time = tpm_driver.fpgas_time
        assert initial_time == final_time
        assert tpm_driver._tpm_status == TpmStatus.UNKNOWN

        # Act
        tpm_driver.initialise()

        # Assert
        assert tpm_driver._tpm_status == TpmStatus.INITIALISED

        # check the fpga time is moving
        initial_time1 = tpm_driver.fpgas_time
        time.sleep(1.5)
        final_time1 = tpm_driver.fpgas_time
        assert initial_time1 != final_time1

        # check the fpga timestamp is not moving
        initial_time2 = tpm_driver.fpga_current_frame
        time.sleep(1.5)
        final_time2 = tpm_driver.fpga_current_frame
        assert initial_time2 == final_time2
        # ---------------------------------------------------------
        # Call start_acquisition and check fpga_timestamp is moving
        # ---------------------------------------------------------
        start_time = int(time.time() + 4.0)
        assert tpm_driver._tpm_status == TpmStatus.INITIALISED
        tpm_driver.start_acquisition(start_time=start_time, delay=1)

        # check the fpga timestamp is moving
        initial_time3 = tpm_driver.fpga_current_frame
        time.sleep(1.5)
        final_time3 = tpm_driver.fpga_current_frame
        assert initial_time3 != final_time3
        assert tpm_driver._tpm_status == TpmStatus.SYNCHRONISED

        # Check that exceptions are handled.
        tpm_driver._check_channeliser_started = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )
        tpm_driver.start_acquisition(start_time=start_time, delay=1)
        tile_simulator.start_acquisition = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )
        tpm_driver.start_acquisition(start_time=start_time, delay=1)

    def test_load_time_delays(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that we can set the delays to the tile hardware mock.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        # Arrange
        tile_simulator.connect()
        # mocked register return
        expected_delay_written: list[float] = list(range(32))

        programmed_delays = [0.0] * 32
        for i in range(32):
            programmed_delays[i] = expected_delay_written[i] * 1.25
        # No method static_time_delays.
        tpm_driver.static_delays = programmed_delays

        # assert both fpgas have the correct delay
        def check_time_delay(index: int) -> bool:
            if (
                tile_simulator[f"fpga1.test_generator.delay_{index}"]
                == expected_delay_written[index] + 128
                and tile_simulator[f"fpga2.test_generator.delay_{index}"]
                == expected_delay_written[index + 16] + 128
            ):
                return True

            return False

        indexes = list(range(16))
        assert all(map(check_time_delay, indexes)) is True

    def test_read_write_address(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test read write address.

        The TpmDriver can be used to write to an address,
        and read the value written.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()

        # Wait for the tpm_driver to poll
        time.sleep(1)
        assert tile_simulator.tpm

        expected_read = [2, 3, 3, 4]
        tpm_driver.write_address(4, expected_read)
        assert tpm_driver.read_address(4, len(expected_read)) == expected_read

    def test_firmware_avaliable(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the we can get the firmware from the tpm_driver.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        tile_simulator.connect()

        tile_simulator.get_firmware_list = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        _ = tpm_driver.firmware_available
        tile_simulator.get_firmware_list.assert_called_once_with()

        # check that exceptions are caught.
        tile_simulator.get_firmware_list.side_effect = Exception("mocked exception")
        _ = tpm_driver.firmware_available

    def test_check_programmed(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that we can configure the 40G core.

        Test to ensure the tpm_driver can read the _check_programmed() method
        correctly if the mocked TPM is programmed.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        """
        assert tpm_driver._check_programmed() is False
        tile_simulator.connect()
        assert tile_simulator.tpm is not None
        tile_simulator.tpm._is_programmed = True
        assert tpm_driver._check_programmed() is True

    def test_update_attributes(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: unittest.mock.Mock,
    ) -> None:
        """
        Test we can update attributes.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)_simulator
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm._is_programmed = True
        tpm_driver._tpm_status = TpmStatus.SYNCHRONISED

        # Values to be used for assertions later.
        initial_last_update_tile_1 = tpm_driver._last_update_time_1
        initial_last_update_tile_2 = tpm_driver._last_update_time_2
        initial_tile_health_structure = tpm_driver._tile_health_structure
        initial_pps_delay = tpm_driver._reported_pps_delay
        initial_adc_rms = tpm_driver._adc_rms

        # updated values
        adc_rms = [2] * 32
        pps_delay = 32
        fpga1_temp = 2
        fpga2_temp = 32
        board_temp = 4
        voltage = 1
        tile_simulator._tile_health_structure["temperatures"]["FPGA0"] = fpga1_temp
        tile_simulator._tile_health_structure["temperatures"]["FPGA1"] = fpga2_temp
        tile_simulator._tile_health_structure["temperatures"]["board"] = board_temp
        tile_simulator._tile_health_structure["voltages"]["MON_5V0"] = voltage

        # Check these values are different.
        assert initial_tile_health_structure["temperatures"]["FPGA0"] != fpga1_temp
        assert initial_tile_health_structure["temperatures"]["FPGA1"] != fpga2_temp
        assert initial_tile_health_structure["temperatures"]["board"] != board_temp
        assert initial_tile_health_structure["voltages"]["MON_5V0"] != voltage
        assert initial_pps_delay != pps_delay
        assert initial_adc_rms != adc_rms

        # Set them in the simulator.
        tile_simulator._adc_rms = adc_rms
        tile_simulator._pps_delay = pps_delay
        tile_simulator._fpga1_temperature = fpga1_temp
        tile_simulator._fpga2_temperature = fpga2_temp
        tile_simulator._board_temperature = board_temp
        tile_simulator._voltage = voltage

        # Mock a poll event by updating attributes manually.
        tpm_driver._update_attributes()

        # check that they are updated
        assert tpm_driver._tile_health_structure["temperatures"]["FPGA0"] == fpga1_temp
        assert tpm_driver._tile_health_structure["temperatures"]["FPGA1"] == fpga2_temp
        assert tpm_driver._tile_health_structure["temperatures"]["board"] == board_temp
        assert tpm_driver._tile_health_structure["voltages"]["MON_5V0"] == voltage
        assert tpm_driver._reported_pps_delay == pps_delay
        assert tpm_driver._adc_rms == adc_rms

        # Check that the last update time is more recent.
        assert initial_last_update_tile_1 < tpm_driver._last_update_time_1
        assert initial_last_update_tile_2 < tpm_driver._last_update_time_2

        # -------------------------------------------------
        # Test attributes not updated when exception raised
        # -------------------------------------------------

        # Arrange
        tile_simulator._voltage = pytest.approx(2.6)
        tile_simulator.get_health_status = unittest.mock.Mock(
            side_effect=LibraryError("attribute mocked to fail")
        )
        time.sleep(6)  # time waited needs to be more than tpm_driver.time_interval_1

        # Act
        tpm_driver._update_attributes()

        # Assert
        assert (
            tpm_driver._tile_health_structure["voltages"]["MON_5V0"]
            != tile_simulator._voltage
        )

        # ---------------------------------------------------------------
        # Test updating attributes when Tile reports it is not programmed
        # ---------------------------------------------------------------
        # Arrange
        tile_simulator.tpm._is_programmed = False

        # Act
        tpm_driver._update_attributes()

        time.sleep(6)  # time waited needs to be more than tpm_driver.time_interval_1
        # we have polled and the tile is reporting that it is not programmed

        # Assert that the values are reset to what they were initialised to.
        assert initial_pps_delay == tpm_driver._reported_pps_delay

    def test_initialise(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        When we initialise the tpm_driver the mockedTPM gets the correct calls.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)
        :param callbacks: dictionary of mock callbacks

        Test cases:
        * Initialise called on a programmed TPM
        * Initialise called on a unprogrammed TPM
        """
        # setup mocked tile.
        tile_simulator.connect()
        tpm_driver._is_programmed = True

        # check the fpga time is not moving
        initial_time = tpm_driver.fpgas_time
        time.sleep(1.5)
        final_time = tpm_driver.fpgas_time
        assert initial_time == final_time

        # check the fpga timestamp is not moving
        initial_time1 = tpm_driver.fpga_current_frame
        time.sleep(1)
        final_time1 = tpm_driver.fpga_current_frame
        assert initial_time1 == final_time1

        tpm_driver.initialise()

        # Assert
        assert tpm_driver._tpm_status == TpmStatus.INITIALISED

        # check the fpga time is moving
        initial_time2 = tpm_driver.fpgas_time
        time.sleep(1.5)
        final_time2 = tpm_driver.fpgas_time
        assert initial_time2 != final_time2

        # check the fpga timestamp is not moving
        initial_time3 = tpm_driver.fpga_current_frame
        time.sleep(1)
        final_time3 = tpm_driver.fpga_current_frame
        assert initial_time3 == final_time3

        # -----------------------------------------
        # Initialise called with unprogrammable TPM
        # -----------------------------------------
        assert tile_simulator.tpm is not None  # for the type checker
        tile_simulator.tpm._is_programmed = False
        mocked_return = unittest.mock.MagicMock(  # type: ignore[assignment]
            side_effect=Exception("mocked exception")
        )
        tile_simulator.program_fpgas = mocked_return  # type: ignore

        # Act
        with pytest.raises(Exception, match="mocked exception"):
            tpm_driver.initialise()

        # Check TpmStatus is UNPROGRAMMED.
        assert tpm_driver._tpm_status == TpmStatus.UNPROGRAMMED

    @pytest.mark.parametrize(
        "tpm_version_to_test, expected_firmware_name",
        [("tpm_v1_2", "itpm_v1_2.bit"), ("tpm_v1_6", "itpm_v1_6.bit")],
    )
    def test_firmware_version(
        self: TestTpmDriver,
        tpm_version_to_test: str,
        expected_firmware_name: str,
        logger: logging.Logger,
        tile_id: int,
        station_id: int,
        callbacks: MockCallableGroup,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test that the tpm driver will get the correct firmware bitfile.

        :param tpm_version_to_test: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param expected_firmware_name: the expected value of firmware_name
        :param logger: a object that implements the standard logging
            interface of :py:class:`logging.Logger`
        :param tile_id: the unique ID for the tile
        :param station_id: the ID of the station to which the tile belongs.
        :param callbacks: dictionary of driver callbacks.
        :param tile_simulator: The tile used by the TpmDriver.
        """
        driver = TpmDriver(
            logger,
            tile_id,
            station_id,
            tile_simulator,
            tpm_version_to_test,
            callbacks["communication_status"],
            callbacks["component_state"],
        )
        assert driver.firmware_name == expected_firmware_name

    def test_initialise_beamformer_with_invalid_input(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test initialise with a invalid value.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.set_first_last_tile = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        assert tile_simulator.tpm
        start_channel = 1  # This must be multiple of 2
        nof_channels = 8
        is_first = True
        is_last = True

        # Act
        tpm_driver.initialise_beamformer(start_channel, nof_channels, is_first, is_last)

        # Assert values not written
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        for table in station_bf_1._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels
        for table in station_bf_2._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels

        # Arrange
        start_channel = 2
        nof_channels = 9  # This must be multiple of 8
        is_first = True
        is_last = True

        # Act
        tpm_driver.initialise_beamformer(start_channel, nof_channels, is_first, is_last)

        # Assert values not written
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        for table in station_bf_1._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels
        for table in station_bf_2._channel_table:
            assert table[0] != start_channel
            assert table[1] != nof_channels

        tile_simulator.set_first_last_tile.assert_not_called()

    def test_initialise_beamformer(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the initialise_beamformer function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        assert tile_simulator.tpm
        start_channel = 2
        nof_channels = 8
        is_first = True
        is_last = True

        # Act
        tpm_driver.initialise_beamformer(start_channel, nof_channels, is_first, is_last)

        # Assert
        station_bf_1 = tile_simulator.tpm.station_beamf[0]
        station_bf_2 = tile_simulator.tpm.station_beamf[1]

        num_blocks = nof_channels // 8
        for block, table in enumerate(station_bf_1._channel_table[0:num_blocks]):
            assert table == [start_channel + block * 8, 0, 0, block * 8, 0, 0, 0]
            assert len(table) < 8
        for table in station_bf_1._channel_table[num_blocks:]:
            assert table == [0, 0, 0, 0, 0, 0, 0]
        for block, table in enumerate(station_bf_2._channel_table[0:num_blocks]):
            assert table == [start_channel + block * 8, 0, 0, block * 8, 0, 0, 0]
        for table in station_bf_2._channel_table[num_blocks:]:
            assert table == [0, 0, 0, 0, 0, 0, 0]

        assert tile_simulator._is_first == is_first
        assert tile_simulator._is_last == is_last

    @pytest.mark.xfail(reason="Only the first element is sent to the tile.")
    def test_csp_rounding(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the csp_rounding function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        assert tpm_driver.csp_rounding == TpmDriver.CSP_ROUNDING

        # ----------------------
        # Case: set with Integer
        # ----------------------
        tpm_driver.csp_rounding = 3  # type: ignore[assignment]
        assert tile_simulator.csp_rounding == 3

        # ----------------------
        # Case: set with Integer
        # ----------------------
        tpm_driver.csp_rounding = -3  # type: ignore[assignment]
        assert tile_simulator.csp_rounding == 0

    def test_pre_adu_levels(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the pre_adu_levels method.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm
        assert tpm_driver.preadu_levels is None

        # Set preADU levels to 3 for all channels
        tpm_driver.preadu_levels = [3.0] * 32
        # Read PyFABIL software preADU levels for preADU 1, channel 1
        assert tile_simulator.tpm.preadu[1].get_attenuation()[1] == 3.00
        # Check TPM driver preADU levels
        tpm_driver.preadu_levels = [3.0] * 32

        # Try to set more levels (33) than there are channels (32),
        # in order to check that the TPM driver swallows exceptions.
        # Possibly a bad idea?
        tpm_driver.preadu_levels = [3.0] * 33

    def test_load_calibration_coefficients(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the load_calibration_coefficients function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.load_calibration_coefficients = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.load_calibration_coefficients(3, [3, 4, 5])
        tile_simulator.load_calibration_coefficients.assert_called_with(3, [3, 4, 5])

        # Check that thrown exception are caught when thrown.
        tile_simulator.load_calibration_coefficients.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.load_calibration_coefficients(3, [3, 4, 5])

    @pytest.mark.xfail(reason="The parameter passed in is overwritten with 0")
    def test_apply_calibration(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the apply_calibration function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.switch_calibration_bank = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.apply_calibration(45)
        tile_simulator.switch_calibration_bank.assert_called_with(45)

        # Check that thrown exception are caught when thrown.
        tile_simulator.switch_calibration_bank.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.apply_calibration(45)

    @pytest.mark.parametrize(
        "delay_array, beam_index, expected_delay",
        [
            ([[0.0, 0.0]] * 16, 3, [[0.0, 0.0]] * 16),
            ([[0.0, 0.0]] * 10, 4, [[0.0, 0.0]] * 16),
        ],
    )
    def test_load_pointing_delays(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        delay_array: list[list[float]],
        beam_index: int,
        expected_delay: float,
    ) -> None:
        """
        Unit test for the load_pointing_delays function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        :param delay_array: The array of pointing delays.
        :param beam_index: The index of the beam.
        :param expected_delay: The expected delay for the given beam index.
        """
        tile_simulator.connect()
        tile_simulator.set_pointing_delay = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.load_pointing_delays(delay_array, beam_index)
        tile_simulator.set_pointing_delay.assert_called_with(expected_delay, beam_index)

        # Check that thrown exception are caught when thrown.
        tile_simulator.set_pointing_delay.side_effect = Exception("mocked exception")
        tpm_driver.load_pointing_delays(delay_array, beam_index)

    def test_apply_pointing_delays(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the apply_pointing_delays function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.load_pointing_delay = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.apply_pointing_delays(4)
        tile_simulator.load_pointing_delay.assert_called_with(4)

        # Check that thrown exception are caught when thrown.
        tile_simulator.load_pointing_delay.side_effect = Exception("mocked exception")
        tpm_driver.apply_pointing_delays(4)

    def test_start_beamformer(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the start_beamformer function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm
        tile_simulator.tpm._is_programmed = True
        tpm_driver._is_beamformer_running = False

        tpm_driver.start_beamformer(3, 4)
        tpm_driver._update_attributes()

        assert tpm_driver._is_beamformer_running is True

        tile_simulator.start_beamformer = (  # type: ignore[assignment]
            unittest.mock.Mock(side_effect=Exception("mocked exception"))
        )

        tpm_driver.start_beamformer(3, 4)

    def test_stop_beamformer(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_beamformer function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.stop_beamformer = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.stop_beamformer()
        tile_simulator.stop_beamformer.assert_called()

        # Check that thrown exception are caught when thrown.
        tile_simulator.stop_beamformer.side_effect = Exception("mocked exception")
        tpm_driver.stop_beamformer()

    def test_configure_integrated_channel_data(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_integrated_channel_data function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.configure_integrated_channel_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.configure_integrated_channel_data(0.5, 2, 520)
        tile_simulator.configure_integrated_channel_data.assert_called_with(0.5, 2, 520)

        # Check that thrown exception are caught when thrown.
        tile_simulator.configure_integrated_channel_data.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.configure_integrated_channel_data(0.5, 2, 520)

    def test_configure_integrated_beam_data(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_integrated_beam_data function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.configure_integrated_beam_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.configure_integrated_beam_data(0.5, 2, 520)
        tile_simulator.configure_integrated_beam_data.assert_called_with(0.5, 2, 520)

        # Check that thrown exception are caught when thrown.
        tile_simulator.configure_integrated_beam_data.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.configure_integrated_beam_data(0.5, 2, 520)

    def test_stop_integrated_data(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_integrated_data function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.stop_integrated_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.stop_integrated_data()
        tile_simulator.stop_integrated_data.assert_called()

        # This just checks that if a exception is raised it is caught
        tile_simulator.stop_integrated_data.side_effect = Exception("mocked exception")
        tpm_driver.stop_integrated_data()

    @pytest.mark.xfail(reason="Uncaught exception when unknown data_type given.")
    def test_send_data_samples(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the send_data_samples function.

        This function raises an uncaught exception if:
        - start_acquisition has not been called.
        - the timestamp is not far enough in the future.
        - an unknown data type is passed.
        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tpm_driver._is_programmed = True

        mocked_input_params: dict[str, Any] = {
            "timestamp": time.time() + 40,
            "seconds": 0.2,
            "n_samples": 1024,
            "sync": False,
            "first_channel": 0,
            "last_channel": 511,
            "channel_id": 128,
            "frequency": 150.0e6,
            "round_bits": 3,
        }

        tile_simulator.send_raw_data = unittest.mock.Mock()  # type: ignore[assignment]
        tile_simulator.send_channelised_data = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_channelised_data_continuous = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_channelised_data_narrowband = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.send_beam_data = unittest.mock.Mock()  # type: ignore[assignment]

        # we require start_acquisition to have been called before send_data_samples
        with pytest.raises(
            ValueError, match="Cannot send data before StartAcquisition"
        ):
            tpm_driver.send_data_samples("raw", **mocked_input_params)

        start_time = int(time.time() + 3.0)
        tpm_driver.start_acquisition(start_time=start_time, delay=1)

        # we require timestamp to be in future
        with pytest.raises(ValueError, match="Time is too early"):
            tpm_driver.send_data_samples("raw", timestamp=1)

        tpm_driver.send_data_samples("raw", **mocked_input_params)
        tile_simulator.send_raw_data.assert_called_with(
            sync=False,
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tpm_driver.send_data_samples("channel", **mocked_input_params)
        tile_simulator.send_channelised_data.assert_called_with(
            number_of_samples=mocked_input_params["n_samples"],
            first_channel=mocked_input_params["first_channel"],
            last_channel=mocked_input_params["last_channel"],
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tpm_driver.send_data_samples("channel_continuous", **mocked_input_params)
        tile_simulator.send_channelised_data_continuous.assert_called_with(
            mocked_input_params["channel_id"],
            number_of_samples=mocked_input_params["n_samples"],
            wait_seconds=0,
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        tpm_driver.send_data_samples("narrowband", **mocked_input_params)
        tile_simulator.send_channelised_data_narrowband.assert_called_with(
            mocked_input_params["frequency"],
            mocked_input_params["round_bits"],
            mocked_input_params["n_samples"],
            0,
            mocked_input_params["timestamp"],
            mocked_input_params["seconds"],
        )

        tpm_driver.send_data_samples("beam", **mocked_input_params)
        tile_simulator.send_beam_data.assert_called_with(
            timestamp=mocked_input_params["timestamp"],
            seconds=mocked_input_params["seconds"],
        )

        # try to send a unknown data type
        # data_type = "unknown"
        # with pytest.raises(ValueError, match=f"Unknown sample type: {data_type}"):
        tpm_driver.send_data_samples("unknown", **mocked_input_params)

        # Check that exceptions are caught.
        # -------------------------------------
        tile_simulator.send_raw_data.side_effect = Exception("mocked exception")
        tile_simulator.send_channelised_data.side_effect = Exception
        tile_simulator.send_channelised_data_continuous.side_effect = Exception
        tile_simulator.send_channelised_data_narrowband.side_effect = Exception(
            "mocked exception"
        )
        tile_simulator.send_beam_data.side_effect = Exception("mocked exception")

        tpm_driver.send_data_samples("raw")
        tpm_driver.send_data_samples("channel")
        tpm_driver.send_data_samples("channel_continuous")
        tpm_driver.send_data_samples("narrowband")
        tpm_driver.send_data_samples("beam")
        # -------------------------------------

    def test_stop_data_transmission(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the stop_data_transmission function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.stop_data_transmission = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        # Act
        tpm_driver.stop_data_transmission()

        # Assert
        tile_simulator.stop_data_transmission.assert_called()

        # Check that exceptions are caught.
        tile_simulator.stop_data_transmission.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.stop_data_transmission()

    def test_set_lmc_integrated_download(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the set_lmc_integrated_download function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.set_lmc_integrated_download = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        mocked_input_params: dict[str, Any] = {
            "mode": "mode_1",
            "channel_payload_length": 4,
            "beam_payload_length": 1024,
            "dst_ip": "10.0.20.30",
            "src_port": 0,
            "dst_port": 511,
        }

        # Act
        tpm_driver.set_lmc_integrated_download(**mocked_input_params)

        # Assert
        tile_simulator.set_lmc_integrated_download.assert_called_with(
            mocked_input_params["mode"],
            mocked_input_params["channel_payload_length"],
            mocked_input_params["beam_payload_length"],
            mocked_input_params["dst_ip"],
            mocked_input_params["src_port"],
            mocked_input_params["dst_port"],
        )

        # Check that exceptions are caught.
        tile_simulator.set_lmc_integrated_download.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.set_lmc_integrated_download(**mocked_input_params)

    def test_current_tile_beamformer_frame(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the current_tile_beamformer_frame function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.current_tile_beamformer_frame = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=4)
        )

        _ = tpm_driver.current_tile_beamformer_frame

        tile_simulator.current_tile_beamformer_frame.assert_called()
        assert tpm_driver._current_tile_beamformer_frame == 4

        tile_simulator.current_tile_beamformer_frame.side_effect = Exception(
            "mocked exception"
        )
        _ = tpm_driver.current_tile_beamformer_frame

    def test_phase_terminal_count(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the phase_terminal_count function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        initial_phase_terminal_count = tpm_driver._phase_terminal_count
        assert tpm_driver.phase_terminal_count == initial_phase_terminal_count
        tpm_driver.phase_terminal_count = initial_phase_terminal_count + 1
        assert initial_phase_terminal_count != tpm_driver.phase_terminal_count
        assert tpm_driver.phase_terminal_count == initial_phase_terminal_count + 1

    def test_test_generator_active(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the test_generator_active function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        initial_test_generator_active = tpm_driver._test_generator_active
        assert isinstance(tpm_driver._test_generator_active, bool)
        assert tpm_driver.test_generator_active == initial_test_generator_active

        # Act
        set_test_generator_active = not initial_test_generator_active
        tpm_driver.test_generator_active = set_test_generator_active

        # Assert
        assert initial_test_generator_active != tpm_driver.test_generator_active
        assert tpm_driver.test_generator_active == set_test_generator_active

    def test_configure_test_generator(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_test_generator function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        mocked_input_params: dict[str, Any] = {
            "frequency0": 0.4,
            "amplitude0": 0.8,
            "frequency1": 0.8,
            "amplitude1": 0.1,
            "amplitude_noise": 0.9,
            "pulse_code": 2,
            "amplitude_pulse": 0.7,
            "load_time": time.time(),
        }

        tile_simulator.test_generator_set_tone = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.test_generator_set_noise = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tile_simulator.set_test_generator_pulse = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.configure_test_generator(**mocked_input_params)
        tile_simulator.test_generator_set_tone.assert_called_with(
            1,
            mocked_input_params["frequency1"],
            mocked_input_params["amplitude1"],
            0.0,
            mocked_input_params["load_time"],
        )
        tile_simulator.test_generator_set_noise.assert_called_with(
            mocked_input_params["amplitude_noise"], mocked_input_params["load_time"]
        )
        tile_simulator.set_test_generator_pulse.assert_called_with(
            mocked_input_params["pulse_code"], mocked_input_params["amplitude_pulse"]
        )

        # Check that any exceptions thrown are caught.
        tile_simulator.test_generator_set_tone.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.configure_test_generator(**mocked_input_params)

    def test_test_generator_input_select(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the test_generator_input_select function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.test_generator_input_select = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        tpm_driver.test_generator_input_select(5)
        tile_simulator.test_generator_input_select.assert_called_with(5)

        tile_simulator.test_generator_input_select.side_effect = Exception(
            "mocked exception"
        )
        tpm_driver.test_generator_input_select(5)

    @pytest.mark.xfail(reason="Local static delay written when exception fired.")
    def test_static_delays(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the static_delays function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.set_time_delays = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        tpm_driver.static_delays = [12.0] * 32
        tile_simulator.set_time_delays.assert_called_with([12.0] * 32)
        assert tpm_driver._static_delays == [12.0] * 32

        tile_simulator.set_time_delays.side_effect = Exception("Mocked excaption")
        tpm_driver.static_delays = [14.0] * 32
        tile_simulator.set_time_delays.assert_called_with([14.0] * 32)
        # the static delays should not be updated.
        assert tpm_driver._static_delays == [12.0] * 32

    def test_set_lmc_download(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the set_lmc_download function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.set_lmc_download = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )
        mocked_input_params: dict[str, Any] = {
            "mode": "mode_1",
            "payload_length": 1024,
            "dst_ip": "10.2.2.14",
            "src_port": 4660,
            "dst_port": 4660,
        }
        tpm_driver.set_lmc_download(**mocked_input_params)
        tile_simulator.set_lmc_download.assert_called_once_with(
            mocked_input_params["mode"],
            mocked_input_params["payload_length"],
            mocked_input_params["dst_ip"],
            mocked_input_params["src_port"],
            mocked_input_params["dst_port"],
        )

        # Check that a raised exception is caught.
        tile_simulator.set_lmc_download.side_effect = Exception("Mocked exception")
        tpm_driver.set_lmc_download(**mocked_input_params)

    def test_arp_table(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the arp_table function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_arp_table = unittest.mock.Mock()  # type: ignore[assignment]

        _ = tpm_driver.arp_table
        tile_simulator.get_arp_table.assert_called_once()

    def test_fpga_current_frame(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the fpga_current_frame function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_fpga_timestamp = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=4)
        )

        _ = tpm_driver.fpga_current_frame
        tile_simulator.get_fpga_timestamp.assert_called_once()
        assert tpm_driver._fpga_current_frame == 4

        # Check that a exception is not caught.
        # TODO: validate this is expected behaviour
        tile_simulator.get_fpga_timestamp.return_value = 5
        tile_simulator.get_fpga_timestamp.side_effect = Exception("Mocked exception")
        with pytest.raises(ConnectionError, match="Cannot read time from FPGA"):
            _ = tpm_driver.fpga_current_frame

        # check not updated if failed.
        assert tpm_driver._fpga_current_frame != 5

    def test_configure_40g_core(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the configure_40g_core function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # mocked connection to the TPM simuator.
        tile_simulator.connect()

        tile_simulator.configure_40g_core = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        core_dict: dict[str, Any] = {
            "core_id": 0,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
            "rx_port_filter": None,
            "netmask": None,
            "gateway_ip": None,
        }

        tpm_driver.configure_40g_core(**core_dict)
        tile_simulator.configure_40g_core.assert_called_once_with(
            core_dict["core_id"],
            core_dict["arp_table_entry"],
            core_dict["src_mac"],
            core_dict["src_ip"],
            core_dict["src_port"],
            core_dict["dst_ip"],
            core_dict["dst_port"],
            core_dict["rx_port_filter"],
            core_dict["netmask"],
            core_dict["gateway_ip"],
        )
        # Check that exceptions raised are caught.
        tile_simulator.configure_40g_core.side_effect = Exception("Mocked exception")
        tpm_driver.configure_40g_core(**core_dict)

    @pytest.mark.xfail(
        reason="A default dictionary is returned even when exception is thrown"
    )
    def test_get_40g_configuration(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the get_40g_configuration function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        core_dict: dict[str, Any] = {
            "core_id": 0,
            "arp_table_entry": 1,
            "src_mac": 0x14109FD4041A,
            "src_ip": "3221226219",
            "src_port": 8080,
            "dst_ip": "3221226219",
            "dst_port": 9000,
            "rx_port_filter": None,
            "netmask": None,
            "gateway_ip": None,
        }

        tile_simulator.connect()
        tile_simulator.get_40g_core_configuration = (  # type: ignore[assignment]
            unittest.mock.Mock(return_value=core_dict)
        )

        tpm_driver.get_40g_configuration(
            core_id=core_dict["core_id"], arp_table_entry=core_dict["arp_table_entry"]
        )
        tile_simulator.get_40g_core_configuration.assert_called_once_with(
            core_dict["core_id"], core_dict["arp_table_entry"]
        )
        assert tpm_driver._forty_gb_core_list == [core_dict]

        tpm_driver.get_40g_configuration(core_id=-1, arp_table_entry=0)
        # We should get all the configurations for both cores and arp table entries
        # these are all mocked to return same thing.
        assert tpm_driver._forty_gb_core_list == [
            core_dict,
            core_dict,
            core_dict,
            core_dict,
        ]

        # Check that exceptions raised are caught.
        tile_simulator.get_40g_core_configuration.return_value = None
        tile_simulator.get_40g_core_configuration.side_effect = Exception(
            "Mocked exception"
        )

        with pytest.raises(KeyError, match="src_ip"):
            tpm_driver.get_40g_configuration(
                core_id=core_dict["core_id"],
                arp_table_entry=core_dict["arp_table_entry"],
            )

        assert tpm_driver._forty_gb_core_list == [core_dict]

    def test_channeliser_truncation(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the channeliser_truncation function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()
        tile_simulator.set_channeliser_truncation = (  # type: ignore[assignment]
            unittest.mock.Mock()
        )

        # call with a single value.
        tpm_driver.channeliser_truncation = 2  # type: ignore
        assert tpm_driver._channeliser_truncation == [2] * 512
        tile_simulator.set_channeliser_truncation.assert_called_with([2] * 512, 31)

        # call with a single value in a list.
        tpm_driver.channeliser_truncation = [3]
        assert tpm_driver._channeliser_truncation == [3] * 512
        tile_simulator.set_channeliser_truncation.assert_called_with([3] * 512, 31)

        # call with subset of values
        tpm_driver.channeliser_truncation = [3] * 100
        assert tpm_driver._channeliser_truncation == [3] * 100
        tile_simulator.set_channeliser_truncation.assert_called_with(
            [3] * 100 + [0] * 412, 31
        )

        # Check that expections are caught at this level.
        tile_simulator.set_channeliser_truncation.side_effect = Exception(
            "Mocked exception"
        )
        tpm_driver.channeliser_truncation = [3] * 100

    @pytest.mark.xfail(reason="Uncaught exception")
    def test_fpgas_time(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the fpgas_time function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        tile_simulator.connect()

        tile_simulator.get_fpga_time = unittest.mock.Mock()  # type: ignore[assignment]

        # Try to get Fpga time without programmed
        tpm_driver._is_programmed = False
        tile_simulator.get_fpga_time.assert_not_called()
        assert tpm_driver.fpgas_time == [0, 0]

        # Try to get Fpga time when programmed
        tpm_driver._is_programmed = True
        _ = tpm_driver.fpgas_time
        tile_simulator.get_fpga_time.assert_called()

        # Check no exception is thrown.
        tile_simulator.get_fpga_time.side_effect = Exception("Mocked exception")
        _ = tpm_driver.fpgas_time

    def test_erase_fpga(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Unit test for the erase_fpga function.

        :param tpm_driver: The TPM driver instance.
        :param tile_simulator: The tile simulator instance.
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.erase_fpga = unittest.mock.Mock()  # type: ignore[assignment]
        tpm_driver._tpm_status = TpmStatus.PROGRAMMED

        # erase a programmed FPGA.
        tpm_driver.erase_fpga()

        # Assert
        tile_simulator.erase_fpga.assert_called_once()
        tpm_driver._check_programmed()
        assert tpm_driver._is_programmed is False
        assert tpm_driver._tpm_status == TpmStatus.UNPROGRAMMED

        tpm_driver._tpm_status = TpmStatus.PROGRAMMED
        tile_simulator.erase_fpga.side_effect = Exception("Mocked exception")

        tpm_driver.erase_fpga()

        assert tpm_driver._tpm_status == TpmStatus.PROGRAMMED

    def test_communication(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the communication state transitions on the driver.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: The tile simulator instance.
        :param callbacks: A dictionary of driver callbacks used to mock the
                        underlying component's behavior.
        """
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # start communicating initialises a polling loop that should.
        # - start_connection with the component under test.
        # - update attributes in a polling loop.
        tpm_driver.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        time.sleep(3)
        assert tile_simulator.tpm is not None

        # Any subsequent calls to start communicating do not fire a change event
        tpm_driver.start_communicating()
        callbacks["communication_status"].assert_not_called()

        tpm_driver.stop_communicating()
        callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # Any subsequent calls to stop communicating do not fire a change event
        tpm_driver.stop_communicating()
        callbacks["communication_status"].assert_not_called()
        assert tile_simulator.tpm is None

    @pytest.mark.xfail(
        reason="polling mechanism on the TPMDriver is about to be refactored"
    )
    def test_poll_update(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the tpm_driver poller.

        :param tpm_driver: the tpm driver under test.
        :param tile_simulator: An hardware tile_simulator mock
        :param callbacks: dictionary of driver callbacks.
        """
        assert tpm_driver.communication_state == CommunicationStatus.DISABLED

        # start communicating initialises a polling loop that should.
        # - start_connection with the component under test.
        # - update attributes in a polling loop.
        pre_poll_temperature = tpm_driver._tile_health_structure["temperature"]["FPGA0"]

        tpm_driver.start_communicating()
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

        tile_simulator._tile_health_structure["temperature"]["FPGA0"] = 41.0

        poll_time = tpm_driver._poll_rate
        time.sleep(poll_time + 0.5)

        post_poll_temperature = tpm_driver._tile_health_structure["temperature"][
            "FPGA0"
        ]

        # Check that the temperature has changed
        assert pre_poll_temperature != post_poll_temperature

        pre_poll_temperature = tpm_driver._tile_health_structure["temperature"]["FPGA0"]

        # Stop communicating to stop the polling loop, ensuring static values
        tpm_driver.stop_communicating()

        tile_simulator._tile_health_structure["temperature"]["FPGA0"] = (
            tpm_driver._tile_health_structure["temperature"]["FPGA0"] + 1
        )

        time.sleep(poll_time + 0.5)

        post_poll_temperature = tpm_driver._tile_health_structure["temperature"][
            "FPGA0"
        ]

        # Note: A pass in software is sufficient for this final assert.
        assert pre_poll_temperature == post_poll_temperature

    @pytest.mark.parametrize(
        ("attribute"),
        [
            # ("active_40g_port"),
            ("voltages"),
            ("temperatures"),
            ("currents"),
            ("info"),
            ("io"),
            ("dsp"),
            ("board_temperature"),
            ("voltage_mon"),
            ("fpga1_temperature"),
            ("fpga2_temperature"),
            ("register_list"),
            ("timing"),
            ("station_id"),
            ("tile_id"),
            ("is_programmed"),
            ("firmware_version"),
            ("firmware_name"),
            ("firmware_available"),
            ("hardware_version"),
            ("tpm_status"),
            ("adc_rms"),
            ("fpgas_time"),
            ("fpga_reference_time"),
            ("fpga_current_frame"),
            ("pps_delay"),
            ("arp_table"),
            ("channeliser_truncation"),
            ("static_delays"),
            ("csp_rounding"),
            ("preadu_levels"),
            ("pps_present"),
            ("clock_present"),
            ("sysref_present"),
            ("pll_locked"),
            ("beamformer_table"),
            ("current_tile_beamformer_frame"),
            ("is_beamformer_running"),
            ("pending_data_requests"),
            ("phase_terminal_count"),
            ("test_generator_active"),
        ],
    )
    def test_dumb_read(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        attribute: str,
    ) -> None:
        """
        Test the dumb read functionality.

        Validate that it can be called without error.

        :param tpm_driver: The TPM driver instance being tested.
        :param tile_simulator: The mocked tile_simulator
        :param attribute: The attribute to be read.
        """
        tile_simulator.connect()
        _ = getattr(tpm_driver, attribute)

    def test_read_tile_info(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: unittest.mock.Mock,
    ) -> None:
        """
        Test we can read tile info.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: A mock object representing
            a simulated tile (`TileSimulator`)_simulator
        """
        # Arrange
        tile_simulator.connect()
        tile_simulator.tpm._is_programmed = True
        tpm_driver._tpm_status = TpmStatus.SYNCHRONISED

        print(tile_simulator)
        assert False

    def test_write_read_registers(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
    ) -> None:
        """
        Test we can write values to a register.

        Using a tile_simulator to mock the functionality
        of writing to a register

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: The mocked tile_simulator
        """
        # Arrange
        tile_simulator.connect()
        assert tile_simulator.tpm is not None

        tile_simulator.tpm.write_register("fpga1.1", 3)
        tile_simulator.tpm.write_register("fpga2.2", 2)
        tile_simulator.tpm.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld", 2
        )

        # write to fpga1
        # write_register(register_name, values, offset, device)
        tpm_driver.write_register("1", 17)
        read_value = tpm_driver.read_register("1")
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # write to fpga2
        tpm_driver.write_register("2", 17)
        read_value = tpm_driver.read_register("2")
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # write to register with no associated device
        tpm_driver.write_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld",
            17,
        )
        read_value = tpm_driver.read_register(
            "fpga1.dsp_regfile.stream_status.channelizer_vld"
        )
        assert read_value == [17]

        # test write to unknown register
        tpm_driver.write_register("unknown", 17)
        read_value = tpm_driver.read_register("unknown")
        assert read_value == []

        # test register that returns list
        read_value = tpm_driver.read_register("mocked_list")
        assert read_value == []

    def test_update_pending_data_requests(
        self: TestTpmDriver,
        tpm_driver: TpmDriver,
        tile_simulator: TileSimulator,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test stopping data transmission updates the pending data requests.

        :param tpm_driver: The tpm driver under test.
        :param tile_simulator: The mocked tile_simulator
        :param callbacks: dictionary of driver callbacks.
        """
        tile_simulator.connect()
        assert tile_simulator.tpm is not None
        tpm_driver._is_programmed = True
        tpm_driver._tpm_status = TpmStatus.INITIALISED
        tile_simulator.tpm._is_programmed = True
        tile_simulator._is_programmed = True

        assert tpm_driver._pending_data_requests is False

        tile_simulator._pending_data_requests = True

        tpm_driver._update_attributes()

        assert tpm_driver._pending_data_requests is True
        tile_simulator._pending_data_requests = False

        tpm_driver.stop_data_transmission()

        assert tpm_driver._pending_data_requests is False
