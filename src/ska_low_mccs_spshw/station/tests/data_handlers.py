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
import json
import logging
import os
import threading
import time
import traceback
from typing import Callable

import h5py  # type: ignore[import-untyped]
import numpy as np
from tango import AttrQuality

from ...tile.tile_data import TileData


class BaseDataReceivedHandler(abc.ABC):
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
        self._tile_files: dict[int, str] = {}
        self.data: np.ndarray
        self._callback_lock = threading.Lock()
        self.ignore_next_event = False
        self.initialise_data()

    @abc.abstractmethod
    def initialise_data(self: BaseDataReceivedHandler) -> None:
        """Initialise empty data structure for file type.."""

    @abc.abstractmethod
    def handle_data(self: BaseDataReceivedHandler) -> None:
        """Handle reading the data from received HDF5."""

    def _handle_data_with_backoff(self: BaseDataReceivedHandler) -> None:
        deadline = time.monotonic() + 5
        delay = 0.25
        while True:
            try:
                self.handle_data()
                return
            except Exception as e:  # pylint: disable=broad-exception-caught
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                self._logger.warning(
                    f"handle_data failed, retrying in {delay:.2f}s: {repr(e)}"
                )
                time.sleep(min(delay, remaining))
                delay = min(delay * 2, remaining)

    def on_created(
        self: BaseDataReceivedHandler, name: str, value: list[str], quality: AttrQuality
    ) -> None:
        """
        Check every event for newly created files to process.

        :param name: name of the event, should always be datareceivedresult.
        :param value: value of the data received event.
        :param quality: the tango.AttrQuality of the event.
        """
        self._logger.debug(f"Got event: {name}, {value}, {quality}")
        if self.ignore_next_event:
            self.ignore_next_event = False
            return
        if quality != AttrQuality.ATTR_VALID:
            return
        with self._callback_lock:
            assert name.lower() == "datareceivedresult"
            file = json.loads(value[1])["file_name"]
            if file in self._tile_files.values():
                self._logger.debug(f"Already received file {file}, ignoring.")
                return
            tile_id = int(os.path.basename(file).split("_")[2])
            self._tile_files[tile_id] = file
            if len(self._tile_files) < self._nof_tiles:
                self._logger.debug(f"Got {len(self._tile_files)} files so far.")
                return
            self._logger.info("Got data for all tiles, gathering data.")
            try:
                time.sleep(1)
                self._handle_data_with_backoff()
                self._logger.debug("Handled data, calling back.")
                self._data_created_callback(data=self.data)
                self.reset()
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error(f"Got error in callback: {repr(e)}, {e}")
                self._logger.error(traceback.format_exc())

    def reset(self: BaseDataReceivedHandler) -> None:
        """Reset instance variables for re-use."""
        self._tile_files = {}
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
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                n_pols = int(f["root"].attrs["n_pols"])
                # shape: (n_antennas * n_pols, n_samples), row = antenna * n_pols + pol
                raw = f["raw_"]["data"][:, : self._nof_samples]
            tile_data = raw.reshape(TileData.ANTENNA_COUNT, n_pols, self._nof_samples)
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
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                n_chans = int(f["root"].attrs["n_chans"])
                n_pols = int(f["root"].attrs["n_pols"])
                # shape: (n_samples, n_chans * n_antennas * n_pols)
                # col = chan * (n_antennas * n_pols) + antenna * n_pols + pol
                raw = f["chan_"]["data"][: self._nof_samples, :]
            reshaped = raw.reshape(
                self._nof_samples, n_chans, TileData.ANTENNA_COUNT, n_pols
            )
            # → (n_chans, n_antennas, n_pols, n_samples)
            real = reshaped["real"].transpose(1, 2, 3, 0)
            imag = reshaped["imag"].transpose(1, 2, 3, 0)
            start_idx = TileData.ANTENNA_COUNT * tile_id
            end_idx = TileData.ANTENNA_COUNT * (tile_id + 1)
            self.data[:, start_idx:end_idx, :, :, 0] = real
            self.data[:, start_idx:end_idx, :, :, 1] = imag

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
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                # shape: (n_samples, n_chans, n_beams), dtype complex16
                pol0 = f["polarization_0"]["data"][
                    : self._nof_samples, : self._nof_channels, :
                ]
                pol1 = f["polarization_1"]["data"][
                    : self._nof_samples, : self._nof_channels, :
                ]
            # pol["real"][:, :, 0] → (n_samples, n_chans) → .T → (n_chans, n_samples)
            self.data[tile_id, 0, :, :, 0] = pol0["real"][:, :, 0].T
            self.data[tile_id, 0, :, :, 1] = pol0["imag"][:, :, 0].T
            self.data[tile_id, 1, :, :, 0] = pol1["real"][:, :, 0].T
            self.data[tile_id, 1, :, :, 1] = pol1["imag"][:, :, 0].T

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
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                n_chans = int(f["root"].attrs["n_chans"])
                n_pols = int(f["root"].attrs["n_pols"])
                raw = f["chan_"]["data"][: self._nof_samples, :]
            # → (n_chans, n_antennas, n_pols, n_samples)
            tile_data = raw.reshape(
                self._nof_samples, n_chans, TileData.ANTENNA_COUNT, n_pols
            ).transpose(1, 2, 3, 0)
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
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                # shape: (n_samples, n_chans, n_beams), dtype uint32
                pol0 = f["polarization_0"]["data"][: self._nof_samples, :, :]
                pol1 = f["polarization_1"]["data"][: self._nof_samples, :, :]
            # pol0[:, :, 0] → (n_samples, n_chans) → .T → (n_chans, n_samples)
            self.data[0, :, tile_id, :] = pol0[:, :, 0].T
            self.data[1, :, tile_id, :] = pol1[:, :, 0].T

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
        self: AntennaBufferDataHandler,
        logger: logging.Logger,
        nof_tiles: int,
        nof_antennas: int,
        data_created_callback: Callable,
    ):
        """
        Initialise a new instance.

        :param logger: logger for the handler
        :param nof_tiles: number of tiles to expect data from
        :param nof_antennas: number of antennas
        :param data_created_callback: callback to call when data received
        """
        self._nof_samples = 16588800
        self._nof_antennas = nof_antennas
        super().__init__(logger, nof_tiles, data_created_callback)

    def handle_data(self: AntennaBufferDataHandler) -> None:
        """Handle the reading of antenna buffer data."""
        # TODO: Understand this behaviour. Seems without a sleep
        # the file lock is claimed by another process.
        time.sleep(10)

        self._logger.info("+=+= Handle data for tile")
        for tile_id in range(self._nof_tiles):
            with h5py.File(self._tile_files[tile_id], "r") as f:
                n_pols = int(f["root"].attrs["n_pols"])
                raw = f["raw_"]["data"][:, : self._nof_samples]
            tile_data = raw.reshape(TileData.ANTENNA_COUNT, n_pols, self._nof_samples)
            start_idx = TileData.ANTENNA_COUNT * tile_id
            end_idx = TileData.ANTENNA_COUNT * (tile_id + 1)
            self.data[start_idx:end_idx, :, :] = tile_data

    def set_nof_samples(self: AntennaBufferDataHandler, nof_samples: int) -> None:
        """
        Reconfigure the number of samples.

        :param nof_samples: the new number of samples.
        """
        self._nof_samples = nof_samples
        self.initialise_data()

    def initialise_data(self: AntennaBufferDataHandler) -> None:
        """Initialise empty antenna buffer data struct.

        This is from my understanding of the original test_antenna_buffer.py
        in aavs.
        """
        self._logger.info("+=+= Data initialiased")
        self.data = np.zeros(
            (
                self._nof_antennas,
                TileData.POLS_PER_ANTENNA,
                self._nof_samples,
            ),
            dtype=np.int8,
        )
