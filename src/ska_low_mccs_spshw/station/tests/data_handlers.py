#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements data handlers for the test data received."""
from __future__ import annotations

import abc
import logging
import os
import threading
import traceback
from typing import Callable

import numpy as np
from ska_low_mccs_daq.pydaq.persisters import (  # type: ignore
    BeamFormatFileManager,
    ChannelFormatFileManager,
    FileDAQModes,
    RawFormatFileManager,
)
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from ...tile.tile_data import TileData


class BaseDataReceivedHandler(FileSystemEventHandler, abc.ABC):
    """Base class for the data received handler."""

    def __init__(
        self: BaseDataReceivedHandler,
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
        self._nof_tiles = nof_tiles
        self._base_path = ""
        self._tile_id = 0
        self.data: np.ndarray
        self._callback_lock = threading.Lock()
        self.initialise_data()

    @abc.abstractmethod
    def initialise_data(self: BaseDataReceivedHandler) -> None:
        """Initialise empty data structure for file type.."""

    @abc.abstractmethod
    def handle_data(self: BaseDataReceivedHandler) -> None:
        """Handle reading the data from received HDF5."""

    def on_created(self: BaseDataReceivedHandler, event: FileSystemEvent) -> None:
        """
        Check every event for newly created files to process.

        :param event: Event to check.
        """
        with self._callback_lock:
            if not event._src_path.endswith(".hdf5") or event.is_directory:
                return
            self._tile_id += 1
            if self._tile_id < self._nof_tiles:
                self._logger.debug(f"Got {self._tile_id} files so far.")
                return
            self._logger.debug("Got data for all tiles, gathering data.")
            self._base_path = os.path.split(event._src_path)[0]
            try:
                self.handle_data()
                self._data_created_callback(data=self.data)
                self.reset()
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error(f"Got error in callback: {repr(e)}, {e}")
                self._logger.error(traceback.format_exc())

    def reset(self: BaseDataReceivedHandler) -> None:
        """Reset instance variables for re-use."""
        self._tile_id = 0
        self.initialise_data()


class RawDataReceivedHandler(BaseDataReceivedHandler):
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
        self._nof_samples = 32 * 1024  # Raw ADC: 32KB per polarisation
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: RawDataReceivedHandler) -> None:
        """Handle the reading of raw data."""
        raw_file = RawFormatFileManager(root_path=self._base_path)
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                antennas=range(TileData.ANTENNA_COUNT),
                polarizations=[0, 1],
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            start_idx = TileData.ANTENNA_COUNT * tile_id
            end_idx = TileData.ANTENNA_COUNT * (tile_id + 1)
            self.data[start_idx:end_idx, :, :] = tile_data

    def initialise_data(self: RawDataReceivedHandler) -> None:
        """Initialise empty raw data struct."""
        self.data = np.zeros(
            (
                self._nof_tiles * TileData.ANTENNA_COUNT,
                TileData.POLS_PER_ANTENNA,
                self._nof_samples,
            ),
            dtype=np.int8,
        )


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
        self._nof_samples = 128
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: ChannelDataReceivedHandler) -> None:
        """Handle the reading of channel data."""
        raw_file = ChannelFormatFileManager(root_path=self._base_path)
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                channels=range(TileData.NUM_FREQUENCY_CHANNELS),
                antennas=range(TileData.ANTENNA_COUNT),
                polarizations=list(range(TileData.POLS_PER_ANTENNA)),
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            start_idx = TileData.ANTENNA_COUNT * tile_id
            end_idx = TileData.ANTENNA_COUNT * (tile_id + 1)
            self.data[:, start_idx:end_idx, :, :, 0] = tile_data["real"]
            self.data[:, start_idx:end_idx, :, :, 1] = tile_data["imag"]

    def initialise_data(self: ChannelDataReceivedHandler) -> None:
        """Initialise empty channel data struct."""
        self.data = np.zeros(
            (
                TileData.NUM_FREQUENCY_CHANNELS,
                self._nof_tiles * TileData.ANTENNA_COUNT,
                TileData.POLS_PER_ANTENNA,
                self._nof_samples,
                2,  # Real/Imag
            ),
            dtype=np.int8,
        )


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
        self._nof_samples = TileData.ADC_CHANNELS
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
        self._nof_samples = 1
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: IntegratedChannelDataReceivedHandler) -> None:
        """Handle the reading of integrated channel data."""
        raw_file = ChannelFormatFileManager(
            root_path=self._base_path, daq_mode=FileDAQModes.Integrated
        )
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                antennas=range(TileData.ANTENNA_COUNT),
                polarizations=list(range(TileData.POLS_PER_ANTENNA)),
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            start_idx = TileData.ANTENNA_COUNT * tile_id
            end_idx = TileData.ANTENNA_COUNT * (tile_id + 1)
            self.data[:, start_idx:end_idx, :, :] = tile_data

    def initialise_data(self: IntegratedChannelDataReceivedHandler) -> None:
        """Initialise empty integrated channel data struct."""
        self.data = np.zeros(
            (
                TileData.NUM_FREQUENCY_CHANNELS,
                self._nof_tiles * TileData.ANTENNA_COUNT,
                TileData.POLS_PER_ANTENNA,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )


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
        self._nof_samples = 1
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: IntegratedBeamDataReceivedHandler) -> None:
        """Handle the reading of integrated beam data."""
        raw_file = BeamFormatFileManager(
            root_path=self._base_path, daq_mode=FileDAQModes.Integrated
        )
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                channels=range(TileData.NUM_BEAMFORMER_CHANNELS),
                polarizations=list(range(TileData.POLS_PER_ANTENNA)),
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            self.data[:, :, tile_id, :] = tile_data[:, :, 0, :]

    def initialise_data(self: IntegratedBeamDataReceivedHandler) -> None:
        """Initialise empty integrated beam data struct."""
        self.data = np.zeros(
            (
                TileData.POLS_PER_ANTENNA,
                TileData.NUM_BEAMFORMER_CHANNELS,
                self._nof_tiles,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )


class AntennaBufferDataHandler(BaseDataReceivedHandler):
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
        self._nof_samples = 1
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: IntegratedBeamDataReceivedHandler) -> None:
        """Handle the reading of antenna buffer data."""
        raw_file = RawFormatFileManager(root_path=self._base_path)
        for tile_id in range(self._nof_tiles):
            tile_data, timestamps = raw_file.read_data(
                antennas=range(TileData.ANTENNA_COUNT),
                polarizations=list(range(TileData.POLS_PER_ANTENNA)),
                n_samples=self._nof_samples,
                tile_id=tile_id,
            )
            self.data[:, :, tile_id, :] = tile_data[:, :, 0, :]

    def initialise_data(self: IntegratedBeamDataReceivedHandler) -> None:
        """Initialise empty antenna buffer data struct.

        This is from my understanding of the original test_antenna_buffer.py
        in aavs.
        """
        self.data = np.zeros(
            (
                TileData.ANTENNA_COUNT * TileData.NUM_FPGA,
                TileData.POLS_PER_ANTENNA,
                self._nof_samples,
            ),
            dtype=np.uint32,
        )
