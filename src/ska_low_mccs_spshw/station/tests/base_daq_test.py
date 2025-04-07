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
import shutil
import string
import time
from contextlib import contextmanager
from threading import Event
from typing import TYPE_CHECKING, Any, Iterator

import numpy as np
from ska_control_model import AdminMode
from ska_low_mccs_common.device_proxy import MccsDeviceProxy
from watchdog.observers import Observer
from watchdog.observers.inotify import InotifyObserver

from ...tile.tile_data import TileData
from .base_tpm_test import TpmSelfCheckTest
from .data_handlers import BaseDataReceivedHandler

if TYPE_CHECKING:
    from ..station_component_manager import SpsStationComponentManager

__all__ = ["BaseDaqTest"]

DATA_TYPE_TO_BITWIDTH = {
    "RAW": (8, 8),
    "BEAM": (12, 16),
    "CHANNEL": (8, 8),
    "INT_BEAM": (12, 12),
    "INT_CHANNEL": (8, 8),
}


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
        self._data: np.ndarray | None = None
        self._observer: InotifyObserver
        self._data_handler: BaseDataReceivedHandler | None = None
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
        self.daq_proxy.Stop()
        time.sleep(1)
        daq_config.update(
            {
                "directory": "/",
                "nof_tiles": len(self.tile_proxies),
                "nof_antennas": TileData.ANTENNA_COUNT * len(self.tile_proxies),
                "description": "self-check data",
            }
        )
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

    def _configure_csp_ingest(self: BaseDaqTest) -> None:
        assert self.daq_proxy is not None
        daq_status = json.loads(self.daq_proxy.DaqStatus())
        self.component_manager.set_csp_ingest(
            daq_status["Receiver IP"][0],
            0xF0D0,
            daq_status["Receiver Ports"][0],
        )

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

    def _configure_test_generator(
        self: BaseDaqTest,
        frequency: float,
        amplitude: float,
        delays: list[int] | None = None,
        adc_channels: list | None = None,
    ) -> None:
        json_arg: dict[str, float | list] = {
            "tone_frequency": frequency,
            "tone_amplitude": amplitude,
        }
        if adc_channels is not None:
            json_arg.update({"adc_channels": adc_channels})
        if delays is not None:
            json_arg.update({"delays": delays})
        self.component_manager.configure_test_generator(json.dumps(json_arg))

    def _disable_test_generator(self: BaseDaqTest) -> None:
        self.component_manager.configure_test_generator("{}")

    def _configure_beamformer(self: BaseDaqTest, frequency: float) -> None:
        region = [[int(frequency / TileData.CHANNEL_WIDTH), 0, 1, 0, 0, 0, 256]]
        self.component_manager.set_beamformer_table(region)

    def _clear_pointing_delays(self: BaseDaqTest) -> None:
        for tile in self.tile_proxies:
            tile.LoadPointingDelays([0.0] * (TileData.ANTENNA_COUNT * 2 + 1))
            tile.ApplyPointingDelays("")

    def _reset_calibration_coefficients(
        self: BaseDaqTest, tile: MccsDeviceProxy, gain: float = 1.0
    ) -> None:
        """
        Reset the calibration coefficients for the TPMs to given gain.

        :param tile: the tile to reset the calibration coefficients for.
        :param gain: the gain to reset the calibration coefficients to.
        """
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

    def _reset_tpm_calibration(self: BaseDaqTest, gain: float = 1.0) -> None:
        """
        Reset the calibration coefficients for all TPMs.

        :param gain: the gain to reset the calibration coefficients to.
        """
        for tile in self.tile_proxies:
            self._reset_calibration_coefficients(tile, gain)

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
    def _signed(cls, data: int, data_type: str) -> int:
        """
        Truncate the input data to a specified number of "bits".

        The reserved value (negative most value) is preserved by sign extending
        to "ext_bits" number of bits.

        TODO: Why doesn't this method sign extend all values to "ext_bits"
        currently only sign extension of the reserved value is handled.

        :param data: the data to truncate.
        :param data_type: the type of the data, this is used to get bitwidth.

        :returns: the truncated data.
        """
        bits, ext_bits = DATA_TYPE_TO_BITWIDTH[data_type]
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
        data_re: int,
        data_im: int,
        integration_length: int,
        round_bits: int,
        max_width: int,
    ) -> int:
        """
        Calculate the average power of the signal.

        :param data_re: real component of data.
        :param data_im: imag component of data.
        :param integration_length: the integration length, in units of 1.08e-6 seconds.
        :param round_bits: the size of available data, scales with integration length.
        :param max_width: the maximum size the data can be.

        :returns: the average power of the signal, independent of integration length.
        """
        sample_power = data_re**2 + data_im**2
        total_power = sample_power * integration_length
        average_power = cls._shift_round(total_power, round_bits, max_width)
        return average_power

    @classmethod
    def _shift_round(cls, data: int, bits: int, max_width: int = 32) -> int:
        """
        Shift given input by 2^bits, then round away from 0.

        :param data: data to shift.
        :param bits: number of bits to shift by.
        :param max_width: the maximum size the data can be.

        :returns: the shifted and rounded data.
        """
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
        if self.daq_proxy is not None:
            self.daq_proxy.Stop()
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
            if self._data_handler is not None:
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
