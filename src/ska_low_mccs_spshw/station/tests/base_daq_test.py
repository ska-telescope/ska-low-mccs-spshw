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
import random
import time
from contextlib import contextmanager
from threading import Event
from typing import TYPE_CHECKING, Any, Iterator

import numpy as np
from pydaq.persisters import AAVSFileManager  # type: ignore
from ska_control_model import AdminMode
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.inotify import InotifyObserver

from .base_tpm_test import TpmSelfCheckTest

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager

__all__ = ["BaseDaqTest"]


class BaseDataReceivedHandler(FileSystemEventHandler, abc.ABC):
    """Base class for the data received handler."""

    @abc.abstractmethod
    def reset(self: BaseDataReceivedHandler) -> None:
        """Reset method for subclasses to implement."""


class BaseDaqTest(TpmSelfCheckTest):
    """
    Test we can send raw data from the TPMs to DAQ correctly.

    ##########
    TEST STEPS
    ##########

    1. Configure DAQ to be ready to receive raw data from your TPMs.
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
        super().__init__(component_manager, logger, tile_trls, subrack_trls, daq_trl)

    def _data_received_callback(self: BaseDaqTest, data: Any, last_tile: bool) -> None:
        if last_tile:
            self._data = data
        self._data_created_event.set()

    def _configure_daq(self: BaseDaqTest, daq_mode: str) -> None:
        assert self.daq_proxy is not None
        self.test_logger.debug("Configuring DAQ")
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
                }
            )
        )
        time.sleep(1)
        self.daq_proxy.Start(json.dumps({"modes_to_start": daq_mode}))
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
        self: BaseDaqTest,
        proxy: MccsDeviceProxy,
        stage: str,
        i: int = 0,
        pattern: list | None = None,
        adders: list | None = None,
    ) -> None:
        self.test_logger.debug("Configuring and starting pattern generator")
        if pattern is None:
            pattern = [
                n if i % 2 == 0 else random.randrange(0, 255) for n in range(1024)
            ]
        if adders is None:
            adders = list(range(32))
        self._pattern = pattern
        self._adders = adders
        proxy.StopPatternGenerator(stage)
        proxy.ConfigurePatternGenerator(
            json.dumps({"stage": stage, "pattern": pattern, "adders": adders})
        )
        proxy.StartPatternGenerator(stage)

    def _stop_pattern_generator(
        self: BaseDaqTest, proxy: MccsDeviceProxy, stage: str
    ) -> None:
        proxy.StopPatternGenerator(stage)

    def _start_directory_watch(self: BaseDaqTest) -> None:
        self.test_logger.debug("Starting directory watch")
        self._observer = Observer()  # type: ignore
        self._observer.schedule(self._data_handler, "/product", recursive=True)
        self._observer.start()

    def _stop_directory_watch(self: BaseDaqTest) -> None:
        self.test_logger.debug("Stopping directory watch")
        self._observer.stop()
        self._observer.join()

    @classmethod
    def _signed(cls, data: Any, bits: int = 8, ext_bits: int = 8) -> Any:
        data = data % 2**bits
        if data >= 2 ** (bits - 1):
            data -= 2**bits
        if ext_bits > bits:
            if data == -(2 ** (bits - 1)):
                data = -(2 ** (ext_bits - 1))
        return data

    def _reset(self: BaseDaqTest) -> None:
        self._data = None
        self._data_created_event.clear()
        self._adders = None
        self._pattern = None

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
