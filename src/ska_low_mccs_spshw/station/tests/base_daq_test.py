#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a basic test for a station."""
from __future__ import annotations

import abc
import json
import logging
import os
import random
import shutil
import string
import threading
import time
import traceback
from contextlib import contextmanager
from threading import Event
from typing import TYPE_CHECKING, Any, Callable, Iterator

import numpy as np
from pydaq.persisters import AAVSFileManager  # type: ignore
from ska_control_model import AdminMode
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.inotify import InotifyObserver

from ...tile.tile_data import TileData
from .base_tpm_test import TpmSelfCheckTest

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager

__all__ = ["BaseDaqTest"]


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
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error(f"Got error in callback: {repr(e)}, {e}")
                self._logger.error(traceback.format_exc())

    def reset(self: BaseDataReceivedHandler) -> None:
        """Reset instance variables for re-use."""
        self._tile_id = 0
        self.initialise_data()


# pylint: disable=too-many-instance-attributes
class BaseDaqTest(TpmSelfCheckTest):
    """Base class for a generic DAQ test."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: BaseDaqTest,
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
        self._data: np.ndarray | None
        self._file_manager: AAVSFileManager
        self._observer: InotifyObserver
        self._data_handler: BaseDataReceivedHandler
        self._pattern: list | None = None
        self._adders: list | None = None
        self._data_created_event: Event = Event()
        random_id = "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(24)
        )
        self._test_folder = f"/product/{self.__class__.__name__}_{random_id}/"
        self.keep_data = True
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _data_received_callback(self: BaseDaqTest, data: Any) -> None:
        self._data = data
        self._data_created_event.set()

    def _configure_daq(
        self: BaseDaqTest,
        daq_mode: str,
        integrated: bool = False,
        **daq_config: Any,
    ) -> None:
        assert self.daq_proxy is not None
        self.test_logger.debug("Configuring DAQ")
        self.daq_proxy.adminmode = AdminMode.OFFLINE
        time.sleep(1)
        self.daq_proxy.adminmode = AdminMode.ONLINE
        time.sleep(1)
        self.daq_proxy.adminmode = AdminMode.ENGINEERING
        self.daq_proxy.Stop()
        time.sleep(1)
        daq_config.update({"directory": "/", "nof_tiles": len(self.tile_proxies)})
        self.daq_proxy.Configure(json.dumps(daq_config))
        time.sleep(1)
        self.daq_proxy.Start(json.dumps({"modes_to_start": daq_mode}))
        time.sleep(1)
        daq_status = json.loads(self.daq_proxy.DaqStatus())
        if integrated:
            tpm_config = {
                "mode": "10G",
                "dst_ip": daq_status["Receiver IP"][0],
                "dst_port": daq_status["Receiver Ports"][0],
                "channel_payload_length": 1024,
                "beam_payload_length": 1024,
            }
            self.component_manager.set_lmc_integrated_download(**tpm_config)
        else:
            tpm_config = {
                "mode": "10G",
                "dst_ip": daq_status["Receiver IP"][0],
                "dst_port": daq_status["Receiver Ports"][0],
                "payload_length": 8192,
            }
            self.component_manager.set_lmc_download(**tpm_config)

    def _configure_and_start_pattern_generator(
        self: BaseDaqTest,
        stage: str,
        proxy: MccsDeviceProxy | None = None,
        pattern: list | None = None,
        adders: list | None = None,
    ) -> None:
        self.test_logger.debug("Configuring and starting pattern generator")
        if pattern is None:
            pattern = [random.randrange(0, 255) for _ in range(int(1024))]
        if adders is None:
            adders = list(range(TileData.ANTENNA_COUNT * TileData.POLS_PER_ANTENNA))
        self._pattern = pattern
        self._adders = adders
        if proxy is None:
            tiles = self.tile_proxies
        else:
            tiles = [proxy]
        for tile in tiles:
            tile.StopPatternGenerator(stage)
            tile.ConfigurePatternGenerator(
                json.dumps({"stage": stage, "pattern": pattern, "adders": adders})
            )
            tile.StartPatternGenerator(stage)

    def _stop_pattern_generator(
        self: BaseDaqTest, stage: str, proxy: MccsDeviceProxy | None = None
    ) -> None:
        if proxy is None:
            tiles = self.tile_proxies
        else:
            tiles = [proxy]
        for tile in tiles:
            tile.StopPatternGenerator(stage)

    def _start_directory_watch(self: BaseDaqTest) -> None:
        self.test_logger.debug("Starting directory watch")
        self._observer = Observer()  # type: ignore
        self._observer.schedule(self._data_handler, "/product", recursive=True)
        self._observer.start()

    def _stop_directory_watch(self: BaseDaqTest) -> None:
        self.test_logger.debug("Stopping directory watch")
        self._observer.stop()
        self._observer.join()

    def _delete_data(self: BaseDaqTest) -> None:
        if not self.keep_data:
            self.logger.info(f"Deleting data in {self._test_folder}")
            shutil.rmtree(self._test_folder)

    @classmethod
    def _signed(cls, data: Any, bits: int = 8, ext_bits: int = 8) -> Any:
        data = data % 2**bits
        if data >= 2 ** (bits - 1):
            data -= 2**bits
        if ext_bits > bits:
            if data == -(2 ** (bits - 1)):
                data = -(2 ** (ext_bits - 1))
        return data

    @classmethod
    def _integrated_sample_calc(
        cls,
        data_re: float,
        data_im: float,
        integration_length: float,
        round_bits: int,
        max_width: int,
    ) -> float:
        power = data_re**2 + data_im**2
        accumulator = power * integration_length
        return cls._s_round(accumulator, round_bits, max_width)

    @classmethod
    def _s_round(cls, data: float, bits: int, max_width: int = 32) -> float:
        if bits == 0:
            return data
        if data == -(2 ** (max_width - 1)):
            return data
        c_half = 2 ** (bits - 1)
        if data >= 0:
            data = (data + c_half + 0) >> bits
        else:
            data = (data + c_half - 1) >> bits
        return data

    def _reset(self: BaseDaqTest) -> None:
        self._data = None
        self._data_created_event.clear()
        self._adders = None
        self._pattern = None
        self._stop_directory_watch()
        # self._delete_data()

    @contextmanager
    def reset_context(self: BaseDaqTest) -> Iterator[None]:
        """
        Context manager to ensure reset is called after the test block.

        :yields: control to the block of code inside the `with` statement.
        """
        try:
            yield
        finally:
            self._reset()
            self._data_handler.reset()

    def check_requirements(self: BaseDaqTest) -> tuple[bool, str]:
        """
        Check we have at least one TPM and a DAQ.

        :returns: true if we have at least one TPM and a DAQ.
        """
        if self.daq_proxy is None:
            return (False, "This test requires a DAQ")
        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM")
        if not all(
            programming_state == "Synchronised"
            for programming_state in self.component_manager.tile_programming_state()
        ):
            return (False, "All TPMs must be synchronised.")
        return super().check_requirements()
