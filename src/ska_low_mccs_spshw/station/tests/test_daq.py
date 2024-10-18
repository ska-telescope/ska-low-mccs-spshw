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
import random
import time
from copy import copy
from threading import Event
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
from pydaq.persisters import AAVSFileManager, RawFormatFileManager  # type: ignore
from ska_control_model import AdminMode
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.inotify import InotifyObserver

from .base_tpm_test import TpmSelfCheckTest

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager

__all__ = ["TestDaq"]


class DataReceivedHandler(FileSystemEventHandler):
    """Detect files created in the data directory."""

    def __init__(
        self: DataReceivedHandler,
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
        self.data = np.zeros(
            (self._nof_tiles * self._nof_antennas_per_tile, 2, 32 * 1024), dtype=np.int8
        )
        self._logger.error("Made the DataReceivedHandler")

    def on_created(self: DataReceivedHandler, event: FileSystemEvent) -> None:
        """
        Check every event for newly created files to process.

        :param event: Event to check.
        """
        if not event._src_path.endswith(".hdf5") or event.is_directory:
            return
        self._logger.error(f"Got event: {event.event_type=}, {event._src_path=}")
        base_path = os.path.split(event._src_path)[0]
        self._logger.error(f"{base_path=}")
        self._logger.error(f"{os.listdir(base_path)=}")
        self._logger.error("The event was not a directory.")

        try:
            self._logger.error("Making file manager")
            raw_file = RawFormatFileManager(root_path=base_path)
            self._logger.error("Made file manager, reading data")
            tile_data, timestamps = raw_file.read_data(
                antennas=range(self._nof_antennas_per_tile),
                polarizations=[0, 1],
                n_samples=32 * 1024,
                tile_id=self._tile_id,
            )
            # self._logger.error(f"Read data: {tile_data=}")
            self._logger.error(f"Tile data shape: {tile_data.shape}")
            start_idx = self._nof_antennas_per_tile * self._tile_id
            end_idx = self._nof_antennas_per_tile * (self._tile_id + 1)

            self._logger.error(f"Slicing data from {start_idx} to {end_idx}")

            self.data[start_idx:end_idx, :, :] = tile_data

            self._data_created_callback(
                data=self.data, last_tile=self._tile_id == self._nof_tiles - 1
            )
            self._tile_id += 1

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error(f"Got error: {repr(e)}, {e}")


class TestDaq(TpmSelfCheckTest):
    """A basic test to show we can connect to proxies."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: TestDaq,
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
        self._data: Any
        self._file_manager: AAVSFileManager
        self._observer: InotifyObserver
        self._pattern: list
        self._adders: list
        self._data_created_event: Event = Event()
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _data_received_callback(self: TestDaq, data: Any, last_tile: bool) -> None:
        self.test_logger.error(f"Called callback with {data=}")
        self.test_logger.error(f"Called callback with {last_tile=}")
        if last_tile:
            self._data = data
        self._data_created_event.set()

    def _configure_daq(self: TestDaq) -> None:
        assert self.daq_proxy is not None
        self.daq_proxy.adminmode = AdminMode.OFFLINE
        time.sleep(1)
        self.daq_proxy.adminmode = AdminMode.ONLINE
        time.sleep(1)
        self.daq_proxy.adminmode = AdminMode.ENGINEERING
        self.daq_proxy.Stop()
        time.sleep(1)
        self.daq_proxy.Configure(
            json.dumps(
                {
                    "directory": "/",
                    "nof_tiles": len(self.tile_proxies),
                    "nof_correlator_channels": 1,
                }
            )
        )
        time.sleep(1)
        self.daq_proxy.Start(json.dumps({"modes_to_start": "RAW_DATA"}))
        time.sleep(1)
        daq_status = json.loads(self.daq_proxy.DaqStatus())
        tpm_config = {
            "mode": "10G",
            "dst_ip": daq_status["Receiver IP"][0],
            "dst_port": daq_status["Receiver Ports"][0],
            "payload_length": 8192,
        }
        self.component_manager.set_lmc_download(**tpm_config)

    def _configure_and_start_pattern_generator(
        self: TestDaq, proxy: MccsDeviceProxy, i: int = 0
    ) -> None:
        test_pattern = [
            n if i % 2 == 0 else random.randrange(0, 255) for n in range(1024)
        ]
        test_adders = list(range(32))
        self._pattern = test_pattern
        self._adders = test_adders
        proxy.StopPatternGenerator("jesd")
        proxy.ConfigurePatternGenerator(
            json.dumps(
                {"stage": "jesd", "pattern": test_pattern, "adders": test_adders}
            )
        )
        proxy.StartPatternGenerator("jesd")

    def _send_raw_data(self: TestDaq, proxy: MccsDeviceProxy, sync: bool) -> None:
        proxy.SendDataSamples(
            json.dumps(
                {
                    "data_type": "raw",
                    "seconds": 1,
                    "sync": sync,
                }
            )
        )

    def _start_directory_watch(self: TestDaq) -> None:
        self._observer = Observer()  # type: ignore
        data_handler = DataReceivedHandler(
            self.test_logger, len(self.tile_proxies), self._data_received_callback
        )
        self._observer.schedule(data_handler, "/product", recursive=True)
        self._observer.start()

    def _stop_directory_watch(self: TestDaq) -> None:
        self._observer.stop()
        self._observer.join()

    def _check_raw(self: TestDaq, raw_data_synchronised: bool = False) -> None:
        data = copy(self._data)
        adders = copy(self._adders)
        pattern = copy(self._pattern)
        ant, pol, sam = data.shape
        if raw_data_synchronised == 1:
            sam = int(sam / 8)
        for a in range(ant):
            for p in range(pol):
                for i in range(sam):
                    if i % 864 == 0:
                        sample_idx = 0
                    signal_idx = (a % 16) * 2 + p
                    exp = pattern[sample_idx] + adders[signal_idx]
                    if self._signed(exp) != data[a, p, i]:
                        self.test_logger.error("Data Error!")
                        self.test_logger.error(f"Antenna: {a}")
                        self.test_logger.error(f"Polarization: {p}")
                        self.test_logger.error(f"Sample index: {i}")
                        self.test_logger.error(f"Expected data: {self._signed(exp)}")
                        self.test_logger.error(f"Received data: {data[a, p, i]}")
                        raise AssertionError
                    sample_idx += 1

    @classmethod
    def _signed(cls, data: Any, bits: int = 8, ext_bits: int = 8) -> Any:
        data = data % 2**bits
        if data >= 2 ** (bits - 1):
            data -= 2**bits
        if ext_bits > bits:
            if data == -(2 ** (bits - 1)):
                data = -(2 ** (ext_bits - 1))
        return data

    def test(self: TestDaq) -> None:
        """A basic test to show we can connect to proxies."""
        self._configure_daq()
        self._start_directory_watch()
        for tile in self.tile_proxies:
            self.logger.error(f"Testing {tile.dev_name()}")
            self._configure_and_start_pattern_generator(tile)
            self._send_raw_data(tile, sync=False)
            assert self._data_created_event.wait(20)
            self._data_created_event.clear()

        self._stop_directory_watch()
        self._check_raw()

    def check_requirements(self: TestDaq) -> tuple[bool, str]:
        """
        Check we have at least one TPM.

        :returns: true if we have at least one TPM.
        """
        if len(self.tile_trls) < 1:
            return (False, "This test requires at least one TPM")
        return super().check_requirements()
