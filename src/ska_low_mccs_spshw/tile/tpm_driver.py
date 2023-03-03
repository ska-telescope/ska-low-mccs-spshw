#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
An implementation of a Tile component manager that drives a real TPM.

The class is basically a wrapper around the Tile class, in order to have
a consistent interface for driver and simulator. This is an initial
version. Some methods are still simulated. A warning is issued in this
case, or a NotImplementedError exception raised.
"""

from __future__ import annotations  # allow forward references in type hints

import copy
import logging
import threading
import time
from typing import Any, Callable, Optional, cast

# import numpy as np
from pyaavs.tile import Tile
from pyfabil.base.definitions import Device, LibraryError
from ska_control_model import CommunicationStatus, TaskStatus
from ska_low_mccs_common.component import MccsBaseComponentManager
from ska_tango_base.executor import TaskExecutorComponentManager

from .tpm_status import TpmStatus
from .utils import acquire_timeout, int2ip


# pylint: disable=too-many-lines, too-many-instance-attributes, too-many-public-methods
class TpmDriver(MccsBaseComponentManager, TaskExecutorComponentManager):
    """Hardware driver for a TPM."""

    # TODO Remove all unnecessary variables and constants after
    # all methods are completed and tested
    VOLTAGE = 5.0
    BOARD_TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5
    ADC_RMS = [0.0] * 32
    FPGAS_TIME = [0, 0]
    CURRENT_TILE_BEAMFORMER_FRAME = 0
    FIRMWARE_NAME = {"tpm_v1_2": "itpm_v1_2.bit", "tpm_v1_6": "itpm_v1_6.bit"}
    FIRMWARE_LIST = [
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
        {"design": "tpm_test", "major": 1, "minor": 2, "build": 0, "time": ""},
    ]
    REGISTER_LIST: list[str] = []
    BEAMFORMER_TABLE: list[list[int]] = [
        [0, 0, 0, 0, 0, 0, 0]
    ] * 48  # empty beamformer table
    CHANNELISER_TRUNCATION: list[int] = [3] * 512
    CSP_ROUNDING: list[int] = [2] * 384

    PREADU_SIGNAL_MAP = {
        0: {"preadu_id": 1, "channel": 14},
        1: {"preadu_id": 1, "channel": 15},
        2: {"preadu_id": 1, "channel": 12},
        3: {"preadu_id": 1, "channel": 13},
        4: {"preadu_id": 1, "channel": 10},
        5: {"preadu_id": 1, "channel": 11},
        6: {"preadu_id": 1, "channel": 8},
        7: {"preadu_id": 1, "channel": 9},
        8: {"preadu_id": 0, "channel": 0},
        9: {"preadu_id": 0, "channel": 1},
        10: {"preadu_id": 0, "channel": 2},
        11: {"preadu_id": 0, "channel": 3},
        12: {"preadu_id": 0, "channel": 4},
        13: {"preadu_id": 0, "channel": 5},
        14: {"preadu_id": 0, "channel": 6},
        15: {"preadu_id": 0, "channel": 7},
        16: {"preadu_id": 1, "channel": 6},
        17: {"preadu_id": 1, "channel": 7},
        18: {"preadu_id": 1, "channel": 4},
        19: {"preadu_id": 1, "channel": 5},
        20: {"preadu_id": 1, "channel": 2},
        21: {"preadu_id": 1, "channel": 3},
        22: {"preadu_id": 1, "channel": 0},
        23: {"preadu_id": 1, "channel": 1},
        24: {"preadu_id": 0, "channel": 8},
        25: {"preadu_id": 0, "channel": 9},
        26: {"preadu_id": 0, "channel": 10},
        27: {"preadu_id": 0, "channel": 11},
        28: {"preadu_id": 0, "channel": 12},
        29: {"preadu_id": 0, "channel": 13},
        30: {"preadu_id": 0, "channel": 14},
        31: {"preadu_id": 0, "channel": 15},
    }

    # pylint: disable=too-many-arguments
    def __init__(
        self: TpmDriver,
        logger: logging.Logger,
        tile_id: int,
        tile: Tile,
        tpm_version: str,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new TPM driver instance passing in the Tile object.

        :param logger: a logger for this simulator to use
        :param tile_id: the unique ID for the tile
        :param tile: the tile driven by this TpmDriver
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        self.logger = logger
        self._hardware_lock = threading.Lock()
        self._component_state_changed_callback = component_state_changed_callback
        self._tile_id = tile_id
        self._station_id = 0
        self._firmware_name = self.FIRMWARE_NAME[tpm_version]
        self._firmware_list = copy.deepcopy(self.FIRMWARE_LIST)
        self._tpm_status = TpmStatus.UNKNOWN
        # Configuration table cache
        self._beamformer_table = self.BEAMFORMER_TABLE
        self._channeliser_truncation = self.CHANNELISER_TRUNCATION
        self._csp_rounding: list[int] = self.CSP_ROUNDING
        self._forty_gb_core_list: list = []
        self._preadu_levels: list[int] = [0] * 32
        self._static_delays: list[float] = [0.0] * 32
        # Hardware register cache. Updated by polling thread
        self._is_programmed = False
        self._is_beamformer_running = False
        self._pending_data_requests = False
        self._voltage = 5.0
        self._board_temperature = self.BOARD_TEMPERATURE
        self._fpga1_temperature = self.FPGA1_TEMPERATURE
        self._fpga2_temperature = self.FPGA2_TEMPERATURE
        self._adc_rms: list[float] = list(self.ADC_RMS)
        self._current_tile_beamformer_frame = self.CURRENT_TILE_BEAMFORMER_FRAME
        self._current_frame = 0
        self._pps_delay = 0
        self._test_generator_active = False
        self._arp_table: dict[int, list[int]] = {}
        self._fpgas_time = [0, 0]
        self._fpga_current_frame = 0
        self._fpga_reference_time = 0
        self._phase_terminal_count = 0
        self._pps_present = True
        self._clock_present = True
        self._sysref_present = True
        self._pll_locked = True
        self._register_list = self.REGISTER_LIST
        # Hardware
        self._tpm_version = tpm_version
        self.tile = tile

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            max_workers=1,
            fault=None,
            programming_state=TpmStatus.UNKNOWN,
        )

        self._poll_rate = 2.0
        self._start_polling_event = threading.Event()
        self._stop_polling_event = threading.Event()
        # Update thread
        self._last_update_time_1 = 0.0
        self._last_update_time_2 = 0.0
        self._polling_thread = threading.Thread(
            target=self._polling_loop, name="tpm_polling_thread", daemon=True
        )
        self._polling_thread.start()  # doesn't start polling, only starts the thread

    def start_communicating(self: TpmDriver) -> None:
        """Establish communication with the TPM."""
        self.logger.debug("Start communication with the TPM...")
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
        self._start_polling_event.set()

    def stop_communicating(self: TpmDriver) -> None:
        """
        Stop communicating with the TPM.

        :todo: is there a better way to do this? Should Tile16 have a
            disconnect() method that we can call here?
        """
        self.logger.debug("Stop communication with the TPM...")
        if self.communication_state == CommunicationStatus.DISABLED:
            return
        self._stop_polling_event.set()

    def _polling_loop(self: TpmDriver) -> None:
        while True:
            # block on "start" event
            self._start_polling_event.wait()

            # "start" event received; update state then poll until "stop" event received
            self._stop_polling_event.clear()
            while not self._stop_polling_event.is_set():
                self._poll()
                self._stop_polling_event.wait(self._poll_rate)

            # "stop" event received; update state, then back to top of loop i.e. block
            # on "start" event
            self.tpm_disconnected()
            self._is_programmed = False
            self._start_polling_event.clear()

    def _poll(self: TpmDriver) -> None:
        """
        Monitor tile connection to tpm.

        :return: None
        """
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            error_flag = False
            with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                if acquired:
                    try:
                        self.tile[int(0x30000000)]
                    # pylint: disable=broad-except
                    except Exception as e:
                        # polling attempt was unsuccessful
                        self.logger.warning(f"Connection to tpm lost! : {e}")
                        error_flag = True
                    # polling attempt succeeded
                    if not error_flag:
                        self._update_attributes()
                else:
                    self.logger.debug("Failed to acquire lock")
            if error_flag:
                self.tpm_disconnected()
                # self.update_component_state({"fault": True})
            # wait for a polling_period
            return

        self.start_connection()

    def start_connection(self: TpmDriver) -> None:
        """
        Try to connect tile to tpm.

        :return: None
        """
        while not (
            (self.communication_state == CommunicationStatus.ESTABLISHED)
            | (self._stop_polling_event.is_set())
        ):
            self.logger.debug("Trying to connect to tpm...")
            timeout = 0
            max_time = 5  # 15 seconds
            self._is_programmed = False
            while timeout < max_time:
                with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                    if acquired:
                        self.logger.debug("Lock acquired")
                        try:
                            self.tile.connect()
                        # pylint: disable=broad-except
                        except Exception:
                            self.logger.debug("Failed to communicate with tile")
                    else:
                        self.logger.debug("Failed to acquire lock")
                if self.tile.tpm is None:
                    self._set_tpm_status(TpmStatus.UNCONNECTED)
                else:
                    self.tpm_connected()
                    return
                time.sleep(0.5)
                timeout = timeout + 1
            self.logger.error(
                f"Connection to tile failed after {timeout*3} seconds. Waiting for "
                f"connection..."
            )
            self.logger.debug("Tile disconnected from tpm.")
            time.sleep(10.0)

    def _update_attributes(self: TpmDriver) -> None:
        """Update key hardware attributes."""
        current_time = time.time()
        time_interval_1 = 5.0
        time_interval_2 = 30.0
        try:
            self._is_programmed = self.tile.is_programmed()
            if self._is_programmed:
                self.logger.debug("Updating key hardware attributes...")
                self._voltage = self.tile.get_voltage()
                # slow update parameters
                if (current_time - self._last_update_time_1) > time_interval_1:
                    self._last_update_time_1 = current_time
                    # self._clock_present = method_to_be_written
                    self._pll_locked = self._check_pll_locked()
                    self._fpga1_temperature = self.tile.get_fpga0_temperature()
                    self._fpga2_temperature = self.tile.get_fpga1_temperature()
                    self._board_temperature = self.tile.get_temperature()
                # Commands checked only when initialised
                # Potential crash if polled on a uninitialised board
                if self._tpm_status in (TpmStatus.INITIALISED, TpmStatus.SYNCHRONISED):
                    self._adc_rms = self.tile.get_adc_rms()
                    self._pending_data_requests = (
                        self.tile.check_pending_data_requests()
                    )
                    # very slow update parameters. Should update by set commands
                    if (current_time - self._last_update_time_2) > time_interval_2:
                        self._last_update_time_2 = current_time
                        self._pps_delay = self.tile.get_pps_delay()
                        self._pps_present = self._check_pps_present()
                        self._is_beamformer_running = self.tile.beamformer_is_running()
                        self._fpga_reference_time = self.tile[
                            "fpga1.pps_manager.sync_time_val"
                        ]
                        self._phase_terminal_count = (
                            self.tile.get_phase_terminal_count()
                        )
                        # self._channeliser_truncation = method_to_be_written
                        # self._csp_rounding = method_to_be_written
                        self._preadu_levels = self._get_preadu_levels()
                        self._static_delays = self._get_static_delays()
                        self._station_id = self.tile.get_station_id()
                        self._tile_id = self.tile.get_tile_id()
                        self._beamformer_table = self.tile.tpm.station_beamf[
                            0
                        ].get_channel_table()
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.debug(f"Failed to update key hardware attributes: {e}")

        if not self._is_programmed:
            self._pps_delay = 0
            self._fpga_reference_time = 0
            # self._beamformer_table = self.BEAMFORMER_TABLE
            # self._channeliser_truncation = self.CHANNELISER_TRUNCATION
            # self._csp_rounding = self.CSP_ROUNDING
            # self._preadu_levels = [0] * 32
            # self._static_delays = [0.0] * 32
            self._is_programmed = False
            self._is_beamformer_running = False
            self._test_generator_active = False
            self._pending_data_requests = False
            self._arp_table = {}
            self._fpgas_time = self.FPGAS_TIME
            self._fpga_current_frame = 0
            self._current_tile_beamformer_frame = 0
            self._fpga_reference_time = 0
            self._pps_present = True
            self._clock_present = True
            self._sysref_present = True
            self._pll_locked = True
            self._register_list = self.REGISTER_LIST

    def tpm_connected(self: TpmDriver) -> None:
        """Tile connected to tpm."""
        self._update_communication_state(CommunicationStatus.ESTABLISHED)
        self._update_component_state(fault=False)
        self.logger.debug("Tpm connected to tile.")
        self._is_programmed = False
        self._update_tpm_status()  # generates a callback if status changed
        status = self.tpm_status
        msg = f"tpm status {status}"
        self.logger.debug(msg)
        if status in [TpmStatus.UNPROGRAMMED, TpmStatus.PROGRAMMED]:
            # if self._check_programmed():
            #    self._tpm_status = TpmStatus.PROGRAMMED
            #    self._is_programmed = True
            # if self._is_programmed:
            self.logger.debug("Tpm not initialised. Initialise it.")
            # self._initialise()
        else:
            self.logger.debug("Tpm initialised. Initialisation skipped")

    def tpm_disconnected(self: TpmDriver) -> None:
        """Tile disconnected to tpm."""
        self.logger.debug("Tile disconnecting from tpm.")
        self._set_tpm_status(TpmStatus.UNCONNECTED)
        self.logger.debug("CommunicationStatus.NOT_ESTABLISHED")
        while self.tile.tpm is not None:
            with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                if acquired:
                    self.tile.tpm = None
            self.logger.warning("Failed to acquire hardware lock")
            time.sleep(0.5)
        self.logger.debug("Tile disconnected from tpm.")
        self._update_communication_state(CommunicationStatus.DISABLED)

    @property
    def tpm_status(self: TpmDriver) -> TpmStatus:
        """
        Return the TPM status.

        :return: the TPM status
        """
        if self._tpm_status in [TpmStatus.UNKNOWN, TpmStatus.UNCONNECTED]:
            # The status in unknown, either because it has not been tested or
            # because it comes from an unconnected state.
            # try to determine the status. Successive tests until one fails
            # if self.power_state != PowerState.ON:
            #     self._tpm_status = TpmStatus.OFF
            self._update_tpm_status()
        return self._tpm_status

    @tpm_status.setter
    def tpm_status(self: TpmDriver, new_status: TpmStatus) -> None:
        """
        Set the TPM status local attribute and call the callback if changed.

        :param new_status: the new value for the _tpm_status
        """
        self._set_tpm_status(new_status)

    def _set_tpm_status(self: TpmDriver, new_status: TpmStatus) -> None:
        """
        Set the TPM status local attribute and call the callback if changed.

        :param new_status: the new value for the _tpm_status
        """
        if new_status != self._tpm_status:
            self._tpm_status = new_status
            self._update_component_state(programming_state=new_status)

    def _update_tpm_status(self: TpmDriver) -> None:
        """Update the value of _tpm_status according to hardware state."""
        new_status = self._tpm_status
        if self.communication_state != CommunicationStatus.ESTABLISHED:
            new_status = TpmStatus.UNCONNECTED
        else:
            with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                if acquired:
                    try:
                        self._is_programmed = self.tile.is_programmed()
                        if self._is_programmed is False:
                            new_status = TpmStatus.UNPROGRAMMED
                        elif self._tile_id != self.tile.get_tile_id():
                            new_status = TpmStatus.PROGRAMMED
                        elif self._check_channeliser_started() is False:
                            new_status = TpmStatus.INITIALISED
                        else:
                            new_status = TpmStatus.SYNCHRONISED
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(f"tpm_driver: tpm_status failed: {e}")
                        # TODO This must be handled in the connection loop
                        # when implemented
                        new_status = TpmStatus.UNCONNECTED
                else:
                    self.logger.debug("tpm_driver: tpm_status uses current value")
        self._set_tpm_status(new_status)

    @property
    def hardware_version(self: TpmDriver) -> str:
        """
        Return whether this TPM is 1.2 or 1.6.

        :return: TPM hardware version. 120 or 160
        """
        return self._tpm_version

    def _check_channeliser_started(self: TpmDriver) -> bool:
        """
        Check that the channeliser is correctly generating samples.

        :return: channelised stream data valid flag
        """
        return (
            self.tile["fpga1.dsp_regfile.stream_status.channelizer_vld"] == 1
            and self.tile["fpga2.dsp_regfile.stream_status.channelizer_vld"] == 1
        )

    def get_tile_id(self: TpmDriver) -> int:
        """
        Get the tile ID stored in the FPGA.

        :returns: tile ID
        :raises: LibraryError
        """
        tile_id = 0
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    tile_id = self.tile.get_tile_id()
                except LibraryError:
                    self.logger.warning("TpmDriver: Tile access failed")
            else:
                self.logger.warning("Failed to acquire hardware lock")
        self._tile_id = tile_id
        return tile_id

    @property
    def firmware_available(self: TpmDriver) -> list[dict[str, Any]]:
        """
        Return the list of the firmware loaded in the system.

        :return: the firmware list
        """
        self.logger.debug("TpmDriver: firmware_available")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._firmware_list = self.tile.get_firmware_list()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")
        return copy.deepcopy(self._firmware_list)

    @property
    def firmware_name(self: TpmDriver) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        """
        self.logger.debug("TpmDriver: firmware_name")
        return self._firmware_name

    @property
    def firmware_version(self: TpmDriver) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        """
        self.logger.debug("TpmDriver: firmware_version")
        firmware = self.firmware_available[0]
        return (
            "Ver."
            + str(firmware["major"])
            + "."
            + str(firmware["minor"])
            + " build "
            + str(firmware["build"])
            + ":"
            + str(firmware["time"])
        )

    @property
    def is_programmed(self: TpmDriver) -> bool:
        """
        Return whether this TPM is programmed (i.e. firmware has been downloaded to it).

        :return: whether this TPM is programmed
        """
        return self._is_programmed

    def _check_programmed(self: TpmDriver) -> bool:
        """
        Return whether this TPM is programmed (i.e. firmware has been downloaded to it).

        Actually checks hardware for this, and updates local variables

        :return: whether this TPM is programmed
        """
        if self.tile.tpm is None:
            return False
        with self._hardware_lock:
            self.logger.debug("Lock acquired")
            self._is_programmed = self.tile.is_programmed()
        self.logger.debug("Lock released")
        return self._is_programmed

    def download_firmware(
        self: TpmDriver, bitfile: str, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Download firmware bitfile onto the TPM as a long runnning command.

        :param bitfile: a binary firmware blob
        :param task_callback: Update task state, defaults to None

        :return: TaskStatus and message
        """
        return self.submit_task(
            self._download_firmware, args=[bitfile], task_callback=task_callback
        )

    def _download_firmware(
        self: TpmDriver,
        bitfile: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Download the provided firmware bitfile onto the TPM.

        :param bitfile: a binary firmware blob
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        is_programmed = False
        with self._hardware_lock:
            self.logger.debug("Lock acquired")
            self.logger.debug("TpmDriver: download_firmware")
            self.tile.program_fpgas(bitfile)
            is_programmed = self.tile.is_programmed()
        self.logger.debug("Lock released")
        self._is_programmed = is_programmed
        if is_programmed:
            self._firmware_name = bitfile
            self._set_tpm_status(TpmStatus.PROGRAMMED)

        if task_callback:
            if is_programmed:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The download firmware task has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED,
                    result="The download firmware task has failed",
                )

    def erase_fpga(self: TpmDriver) -> None:
        """Erase FPGA programming to reduce FPGA power consumption."""
        self.logger.debug("TpmDriver: erase_fpga")
        status = self._tpm_status
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.erase_fpga()
                    self._is_programmed = False
                    status = TpmStatus.UNPROGRAMMED
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")
        self._set_tpm_status(status)

    def _initialise(
        self: TpmDriver,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Download firmware, if not already downloaded, and initializes tile.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        #
        # If not programmed, program it.
        # TODO: there is no way to check whether the TPM is already correctly
        # initialised. If it is, re-initialising it is bad.
        #
        prog_status = False
        with self._hardware_lock:
            self.logger.debug("Lock acquired")
            if self.tile.is_programmed() is False:
                self._set_tpm_status(TpmStatus.UNPROGRAMMED)
                self.tile.program_fpgas(self._firmware_name)
            prog_status = self.tile.is_programmed()
        self.logger.debug("Lock released")
        #
        # Initialisation after programming the FPGA
        #
        if prog_status:
            self._is_programmed = True
            self._set_tpm_status(TpmStatus.PROGRAMMED)
            #
            # Base initialisation
            #
            with self._hardware_lock:
                self.logger.debug("Lock acquired")
                self.tile.initialise(
                    tile_id=self._tile_id,
                    pps_delay=self._pps_delay,
                )
                self.tile.set_station_id(0, 0)
            self.logger.debug("Lock released")
            #
            # extra steps required to have it working
            #
            self._reset_and_initialise_beamformer()
            with self._hardware_lock:
                self.logger.debug("Lock acquired")
                # self.tile.post_synchronisation()
                self.tile.set_station_id(self._station_id, self._tile_id)
            self.logger.debug("Lock released")
            self._set_tpm_status(TpmStatus.INITIALISED)
            self.logger.debug("TpmDriver: initialisation completed")
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The initialisation task has completed",
                )
        else:
            self._set_tpm_status(TpmStatus.UNPROGRAMMED)
            self.logger.error("TpmDriver: Cannot initialise board")
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="The initialisation task has failed",
                )

    def initialise(
        self: TpmDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Download firmware, if not already downloaded, and initializes tile.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a message
        """
        return self.submit_task(self._initialise, task_callback=task_callback)

    @property
    def tile_id(self: TpmDriver) -> int:
        """
        Get the Tile ID.

        :return: assigned tile Id value
        """
        return self._tile_id

    @tile_id.setter  # type: ignore[no-redef]
    def tile_id(self: TpmDriver, value: int) -> None:
        """
        Set Tile ID.

        :param value: assigned tile Id value
        """
        if not self._is_programmed:
            self._tile_id = value
            return
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._tile_id = value
                    self.tile.set_station_id(self._station_id, self._tile_id)
                    self.logger.debug(
                        f"TpmDriver: station:{self._station_id}, tile:{self._tile_id}"
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                self._hardware_lock.release()
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def station_id(self: TpmDriver) -> int:
        """
        Get the Station ID.

        :return: assigned station Id value
        """
        return self._station_id

    @station_id.setter  # type: ignore[no-redef]
    def station_id(self: TpmDriver, value: int) -> None:
        """
        Set Station ID.

        :param value: assigned station Id value
        """
        if not self._is_programmed:
            self._station_id = value
            return
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._station_id = value
                    self.tile.set_station_id(self._station_id, self._tile_id)
                    self.logger.debug(
                        f"TpmDriver: station:{self._station_id}, tile:{self._tile_id}"
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def board_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        self.logger.debug("TpmDriver: board_temperature")
        return self._board_temperature

    @property
    def voltage(self: TpmDriver) -> float:
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        """
        self.logger.debug("TpmDriver: voltage")
        return self._voltage

    @property
    def fpga1_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        self.logger.debug("TpmDriver: fpga1_temperature")
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self: TpmDriver) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        self.logger.debug("TpmDriver: fpga2_temperature")
        return self._fpga2_temperature

    @property
    def adc_rms(self: TpmDriver) -> list[float]:
        """
        Return the last measured RMS power of the TPM's analog-to-digital converter.

        :return: the RMS power of the TPM's ADC
        """
        return self._adc_rms

    @property
    def fpgas_time(self: TpmDriver) -> list[int]:
        """
        Return the FPGAs clock time.

        Useful for detecting clock skew, propagation
        delays, contamination delays, etc.

        :return: the FPGAs clock time
        :raises ConnectionError: if communication with tile failed
        """
        self.logger.debug("TpmDriver: fpgas_time")
        if not self._is_programmed:
            self.logger.info("Trying to read time from an unprogrammed FPGA")
            return [0, 0]
        failed = False
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._fpgas_time = [
                        self.tile.get_fpga_time(Device.FPGA_1),
                        self.tile.get_fpga_time(Device.FPGA_2),
                    ]
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                    failed = True
            else:
                self.logger.warning("Failed to acquire hardware lock")
                failed = True
        if failed:
            raise ConnectionError("Cannot read time from FPGA")
        return self._fpgas_time

    @property
    def fpga_reference_time(self: TpmDriver) -> int:
        """
        Return the FPGA reference time.

        Required to map the FPGA timestamps, expressed in frames
        to UTC time

        :return: the FPGA_1 reference time, in Unix seconds
        """
        self.logger.debug("TpmDriver: fpga_reference_time")
        return self._fpga_reference_time

    @property
    def fpga_current_frame(self: TpmDriver) -> int:
        """
        Return the FPGA current frame counter.

        :return: the FPGA_1 current frame counter
        :raises ConnectionError: if communication with tile failed
        """
        self.logger.debug("TpmDriver: fpga_current_frame")
        if not self._is_programmed:
            self.logger.info("Trying to read frame# from an unprogrammed FPGA")
        failed = False
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._fpga_current_frame = self.tile.get_fpga_timestamp()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                    failed = True
            else:
                self.logger.warning("Failed to acquire hardware lock")
                failed = True
        if failed:
            raise ConnectionError("Cannot read time from FPGA")
        return self._fpga_current_frame

    @property
    def pps_delay(self: TpmDriver) -> float:
        """
        Return the last measured PPS delay of the TPM.

        :return: PPS delay correction in nanoseconds. Rounded to 1.25 ns units
        """
        return self._pps_delay

    @pps_delay.setter  # type: ignore[no-redef]
    def pps_delay(self: TpmDriver, value: int) -> None:
        """
        Set PPS delay.

        PPS delay correction, applied during initialisation.
        Must be set before initialise()

        :param value: PPS delay correction (nanoseconds). Rounded to 1.25 ns units
        """
        self._pps_delay = value

    @property
    def register_list(self: TpmDriver) -> list[str]:
        """
        Return a list of registers available on each device.

        :return: list of registers
        """
        return self._register_list

    def _get_register_list(self: TpmDriver) -> None:
        """Update the TPM register list."""
        assert self.tile.tpm is not None  # for the type checker
        self.logger.warning("TpmDriver: register_list too big to be transmitted")
        reglist = []
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    regmap = self.tile.tpm.find_register("")
                    for reg in regmap:
                        reglist.append(reg.name)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                self._register_list = reglist
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def read_register(self: TpmDriver, register_name: str) -> list[int]:
        """
        Read the values in a named register.

        :param register_name: name of the register

        :return: values read from the register
        """
        assert self.tile.tpm is not None  # for the type checker
        if len(self.tile.tpm.find_register(register_name)) == 0:
            self.logger.error("Register '" + register_name + "' not present")
            return []
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    value = self.tile.read_register(register_name)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                    return []
            else:
                self.logger.warning("Failed to acquire hardware lock")
                return []

        if isinstance(value, list):
            lvalue = cast(list, value)
        else:
            lvalue = [value]
        # self.logger.debug(f"Read value: {value} = {hex(value)}")
        return lvalue

    def write_register(
        self: TpmDriver, register_name: str, values: list[Any] | int
    ) -> None:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param values: values to write
        """
        if isinstance(values, int):
            values = [values]
        devname = ""
        regname = devname + register_name
        assert self.tile.tpm is not None  # for the type checker
        if len(self.tile.tpm.find_register(regname)) == 0:
            self.logger.error("Register '" + regname + "' not present")
        else:
            with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                if acquired:
                    try:
                        self.tile.write_register(register_name, values)
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                else:
                    self.logger.warning("Failed to acquire hardware lock")

    def read_address(self: TpmDriver, address: int, nvalues: int) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """
        values = []
        current_address = int(address & 0xFFFFFFFC)
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                self.logger.debug(
                    "Reading address "
                    + str(current_address)
                    + "of type "
                    + str(type(current_address))
                )
                try:
                    values = self.tile.read_address(current_address, nvalues)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

        return values

    def write_address(self: TpmDriver, address: int, values: list[int]) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """
        current_address = int(address & 0xFFFFFFFC)
        if isinstance(values, int):
            values = [values]
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.write_address(current_address, values)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def configure_40g_core(
        self: TpmDriver,
        core_id: int,
        arp_table_entry: int,
        src_mac: int,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
    ) -> None:
        """
        Configure the 40G code.

        :param core_id: id of the core
        :param arp_table_entry: ARP table entry to use
        :param src_mac: MAC address of the source
        :param src_ip: IP address of the source
        :param src_port: port of the source
        :param dst_ip: IP address of the destination
        :param dst_port: port of the destination
        """
        self.logger.debug("TpmDriver: configure_40g_core")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.configure_40g_core(
                        core_id,
                        arp_table_entry,
                        src_mac,
                        src_ip,
                        src_port,
                        dst_ip,
                        dst_port,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def get_40g_configuration(
        self: TpmDriver, core_id: int = -1, arp_table_entry: int = 0
    ) -> list[dict]:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        self.logger.debug(
            f"TpmDriver: get_40g_configuration: core:{core_id} entry:{arp_table_entry}"
        )
        self._forty_gb_core_list = []
        if core_id == -1:
            for icore in range(2):
                for arp_table_entry_id in range(2):
                    dict_to_append = self._get_40g_core_configuration(
                        icore, arp_table_entry_id
                    )
                    if dict_to_append is not None:
                        self._forty_gb_core_list.append(dict_to_append)
        else:
            self._forty_gb_core_list = [
                self._get_40g_core_configuration(core_id, arp_table_entry)
            ]
        # convert in more readable format
        for core in self._forty_gb_core_list:
            core["src_ip"] = int2ip(core["src_ip"])
            core["dst_ip"] = int2ip(core["dst_ip"])
        return self._forty_gb_core_list

    def _get_40g_core_configuration(
        self: TpmDriver, core_id: int, arp_table_entry: int
    ) -> dict:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        return_value = {"core_id": core_id, "arp_table_entry": arp_table_entry}
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    return_value = self.tile.get_40g_core_configuration(
                        core_id,
                        arp_table_entry,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")
        return return_value

    @property
    def arp_table(self: TpmDriver) -> dict[int, list[int]]:
        """
        Check that ARP table has been populated in for all used cores 40G interfaces.

        Use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer, 1 for LMC 10G
        interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: list of core id and arp table populated
        """
        self.logger.debug("TpmDriver: arp_table")
        with self._hardware_lock:
            self._arp_table = self.tile.get_arp_table()
        return self._arp_table

    def set_lmc_download(
        self: TpmDriver,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = 0xF0D0,
        dst_port: Optional[int] = 4660,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1g" or "10g"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self.logger.debug("TpmDriver: set_lmc_download")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_lmc_download(
                        mode, payload_length, dst_ip, src_port, dst_port
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def channeliser_truncation(self: TpmDriver) -> list[int]:
        """
        Read the cached value for the channeliser truncation.

        :return: cached value for the channeliser truncation
        """
        return copy.deepcopy(self._channeliser_truncation)

    @channeliser_truncation.setter
    def channeliser_truncation(self: TpmDriver, truncation: int | list[int]) -> None:
        """
        Set the channeliser truncation.

        :param truncation: number of LS bits discarded after channelisation.
            Either a signle value or a list of one value per physical frequency channel
            0 means no bits discarded, up to 7. 3 is the correct value for a uniform
            white noise.
        """
        if isinstance(truncation, int):
            self._channeliser_truncation = [truncation] * 512
        elif isinstance(truncation, list):
            if len(truncation) == 1:
                self._channeliser_truncation = truncation * 512
            else:
                self._channeliser_truncation = truncation
        self._set_channeliser_truncation(self._channeliser_truncation)

    def _set_channeliser_truncation(self: TpmDriver, array: list[int]) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: list with M values, one for each of the
            frequency channels. Same truncation is applied to the corresponding
            frequency channels in all inputs.
        """
        self.logger.debug(f"TpmDriver: set_channeliser_truncation: {array[0]}")
        nb_freq = len(array)
        trunc = [0] * 512
        trunc[0:nb_freq] = array
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                for chan in range(32):
                    try:
                        self.tile.set_channeliser_truncation(trunc, chan)
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _get_static_delays(self: TpmDriver) -> list[float]:
        """
        Read from hardware the static delays, in nanoseconds.

        Requires to be run inside a thread protected block
        :return: list of static delays, from the hardware, in ns
        """
        self.logger.debug("TpmDriver: get_time_delays")
        delays = []
        try:
            for i in range(16):
                delays.append(
                    (self.tile[f"fpga1.test_generator.delay_{i}"] - 128) * 1.25
                )
            for i in range(16):
                delays.append(
                    (self.tile[f"fpga2.test_generator.delay_{i}"] - 128) * 1.25
                )
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.warning(f"TpmDriver: Tile access failed: {e}")
        return delays

    @property
    def static_delays(self: TpmDriver) -> list[float]:
        """
        Read the cached value for the static delays, in sample.

        :return: static delay, in samples one per TPM input
        """
        return copy.deepcopy(self._static_delays)

    @static_delays.setter  # type: ignore[no-redef, attr-defined]
    def static_delays(self: TpmDriver, delays: list[float]) -> None:
        """
        Set the static delays.

        :param delays: Delay in nanoseconds, nominal = 0, positive delay adds
            delay to the signal stream

        :param delays: Static zenith delays, one per input channel
        """
        self.logger.debug("TpmDriver: static_delays.setter")
        self._set_time_delays(delays)
        self._static_delays = delays

    def _set_time_delays(self: TpmDriver, delays: list[float]) -> None:
        """
        Set coarse zenith delay for input ADC streams.

        :param delays: the delay in input streams, specified in nanoseconds.
            A positive delay adds delay to the signal stream
        """
        self.logger.debug("TpmDriver: set_time_delays")
        # tile.set_time_delays is picky about type
        delays_float = []
        for d in delays:
            delays_float.append(float(d))
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_time_delays(delays_float)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def csp_rounding(self: TpmDriver) -> list[int]:
        """
        Read the cached value for the final rounding in the CSP samples.

        Need to be specfied only for the last tile
        :return: Final rounding for the CSP samples. Up to 384 values
        """
        return copy.deepcopy(self._csp_rounding)

    @csp_rounding.setter
    def csp_rounding(self: TpmDriver, rounding: list[int] | int) -> None:
        """
        Set the final rounding in the CSP samples, one value per beamformer channel.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        """
        if isinstance(rounding, int):
            self._csp_rounding = [rounding] * 384
        elif len(rounding) == 1:
            self._csp_rounding = [rounding[0]] * 384
        else:
            self._csp_rounding = rounding
        self._set_csp_rounding(self._csp_rounding)

    def _set_csp_rounding(self: TpmDriver, rounding: list[int]) -> None:
        """
        Set output rounding for CSP.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        """
        self.logger.debug("TpmDriver: set_csp_rounding")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_csp_rounding(rounding[0])
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def preadu_levels(self: TpmDriver) -> list[int]:
        """
        Get preadu levels in dB.

        :return: cached values of Preadu attenuation level in dB
        """
        return copy.deepcopy(self._preadu_levels)

    @preadu_levels.setter
    def preadu_levels(self: TpmDriver, levels: list[int]) -> None:
        """
        Set preadu levels in dB.

        :param levels: Preadu attenuation levels in dB
        """
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._set_preadu_levels(levels)
                    self._preadu_levels = levels
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _set_preadu_levels(self: TpmDriver, levels: list[int]) -> None:
        """
        Get current preadu settings.

        TODO This should be moved to pyaavs Tile
        :param levels: Preadu attenuation levels in dB
        """
        self.logger.debug("TpmDriver: set_preadu_levels")
        for preadu in self.tile.tpm.tpm_preadu:
            preadu.select_low_passband()
            preadu.read_configuration()

        for channel in list(self.PREADU_SIGNAL_MAP.keys()):
            # Apply attenuation
            pid = self.PREADU_SIGNAL_MAP[channel]["preadu_id"]
            channel = self.PREADU_SIGNAL_MAP[channel]["channel"]
            attenuation = int(round(levels[channel]))
            self.tile.tpm.tpm_preadu[pid].set_attenuation(attenuation, [channel])

        for preadu in self.tile.tpm.tpm_preadu:
            preadu.write_configuration()

    def _get_preadu_levels(self: TpmDriver) -> list[int]:
        """
        Get current preadu settings.

        :return: Preadu attenuation levels in dB
        """
        self.logger.debug("TpmDriver: get_preadu_levels")
        for preadu in self.tile.tpm.tpm_preadu:
            preadu.select_low_passband()
            preadu.read_configuration()

        levels: list[int] = []
        for channel in list(self.PREADU_SIGNAL_MAP.keys()):
            pid = self.PREADU_SIGNAL_MAP[channel]["preadu_id"]
            channel = self.PREADU_SIGNAL_MAP[channel]["channel"]
            attenuation = self.tile.tpm_preadu[pid].channel_filters[channel] >> 3
            levels = levels + [attenuation]
        return levels

    # TODO connect all these with real hardware probes (in poll loop)
    @property
    def pps_present(self: TpmDriver) -> bool:
        """
        Check if PPS signal is present.

        :return: True if PPS is present. Checked in poll loop, cached
        """
        return self._pps_present

    def _check_pps_present(self: TpmDriver) -> bool:
        """
        Check in hardware if PPS is present.

        Requires to be run inside a thread protected code block
        TODO To be moved in pyaavs.Tile
        :return: True if PPS is present and internal PPS locked to it
        """
        if not self._is_programmed:
            return False
        # check PPS detection
        pps_lock = True
        if self.tile.tpm["fpga1.pps_manager.pps_detected"] == 0x1:
            self.logger.debug("FPGA1 is locked to external PPS")
        else:
            self.logger.debug("FPGA1 is not locked to external PPS")
            pps_lock = False
        if self.tile.tpm["fpga2.pps_manager.pps_detected"] == 0x1:
            self.logger.debug("FPGA2 is locked to external PPS")
        else:
            self.logger.debug("FPGA2 is not locked to external PPS")
            pps_lock = False
        self._pps_present = pps_lock
        return pps_lock

    @property
    def clock_present(self: TpmDriver) -> bool:
        """
        Check if 10 MHz clock signal is present.

        :return: True if 10 MHz clock is present. Checked in poll loop, cached
        """
        return self._clock_present

    @property
    def sysref_present(self: TpmDriver) -> bool:
        """
        Check if SYSREF signal is present.

        :return: True if SYSREF is present. Checked in poll loop, cached
        """
        return self._sysref_present

    @property
    def pll_locked(self: TpmDriver) -> bool:
        """
        Check if ADC clock PLL is locked.

        :return: True if PLL is locked. Checked in poll loop, cached
        """
        return self._pll_locked

    def _check_pll_locked(self: TpmDriver) -> bool:
        """
        Check in hardware if PLL is locked.

        Requires to be run inside a thread protected code block
        TODO To be moved in pyaavs.Tile
        :return: True if PPS is locked
        """
        pll_status = self.tile.tpm["pll", 0x508]
        pll_lock = pll_status in [0xF2, 0xE7]
        self._pll_locked = pll_lock
        return pll_lock

    def set_beamformer_regions(self: TpmDriver, regions: list[list[int]]) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        :param regions: a list encoding up to 16 regions, with each
            region containing a start channel, the size of the region
            (which must be a multiple of 8), and a beam index (between 0 and 7)
            and a substation ID (not used)
        """
        self.logger.debug("TpmDriver: set_beamformer_regions")
        # TODO: Remove when interface with station beamformer allows multiple
        # subarrays, stations and apertures
        subarray_id = 0
        substation_id = 0
        aperture_id = 0
        changed = False
        if len(regions[0]) == 8:
            subarray_id = regions[0][3]
            substation_id = regions[0][6]
            aperture_id = regions[0][7]
            for region in regions[1:]:
                if (
                    region[3] != subarray_id
                    or region[6] != substation_id
                    or region[7] != aperture_id
                ):
                    changed = True
                region[3] = subarray_id
                region[6] = substation_id
                region[7] = aperture_id
        if changed:
            self.logger.info(
                "Different subarrays or substations not supported. "
                "Using only first defined"
            )
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_beamformer_regions(regions)
                    self._beamformer_table = self.tile.tpm.station_beamf[
                        0
                    ].get_channel_table()
                    self.tile.define_spead_header(
                        self._station_id,
                        subarray_id,
                        aperture_id,
                        self._fpga_reference_time,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _reset_and_initialise_beamformer(self: TpmDriver) -> None:
        """
        Initialise the beamformer.

        Initial reset of the tile and station beamformer. Resets both
        and sets the beamformer to a default state.
        """
        self.logger.debug("TpmDriver: initialise_beamformer")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.initialise_beamformer(128, 8)
                    self.tile.set_first_last_tile(False, False)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def initialise_beamformer(
        self: TpmDriver,
        start_channel: int,
        nof_channels: int,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Initialise the beamformer.

        :param start_channel: the start channel
        :param nof_channels: number of channels
        :param is_first: whether this is the first (?)
        :param is_last: whether this is the last (?)
        """
        self.logger.debug("TpmDriver: initialise_beamformer")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.tpm.station_beamf[0].define_channel_table(
                        [[start_channel, nof_channels, 0]]
                    )
                    self.tile.tpm.station_beamf[1].define_channel_table(
                        [[start_channel, nof_channels, 0]]
                    )
                    self.tile.set_first_last_tile(is_first, is_last)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def beamformer_table(self: TpmDriver) -> list[list[int]]:
        """
        Fetch internal beamformer table.

        Fetch table used by the hardware beamformer to define beams and logical bands
        :return: bidimensional table, with 48 entries, one every 8 channels

        * start physical channel
        * tile hardware beam
        * subarray ID
        * subarray start logical channel
        * subarray_beam_id - (int) ID of the subarray beam
        * substation_id - (int) Substation
        * aperture_id:  ID of the aperture (station*100+substation?)
        """
        return copy.deepcopy(self._beamformer_table)

    def load_calibration_coefficients(
        self: TpmDriver, antenna: int, calibration_coefficients: list[complex]
    ) -> None:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list
        """
        self.logger.debug("TpmDriver: load_calibration_coefficients")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.load_calibration_coefficients(
                        antenna, calibration_coefficients
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def apply_calibration(self: TpmDriver, switch_time: Optional[int] = 0) -> None:
        """
        Switch the calibration bank.

        (i.e. apply the calibration coefficients previously loaded by
        :py:meth:`load_calibration_coefficients`).

        :param switch_time: an optional time at which to perform the
            switch
        """
        self.logger.debug("TpmDriver: switch_calibration_bank")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.switch_calibration_bank(switch_time=0)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def load_pointing_delays(
        self: TpmDriver, delay_array: list[list[float]], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :param beam_index: the beam to which the pointing delay should
            be applied
        """
        self.logger.debug("TpmDriver: set_pointing_delay")
        nof_items = len(delay_array)
        # 16 values required (16 antennas). Fill with zeros if less are specified
        if nof_items < 16:
            delay_array = delay_array + [[0.0, 0.0]] * (16 - nof_items)
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_pointing_delay(delay_array, beam_index)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def apply_pointing_delays(self: TpmDriver, load_time: int) -> None:
        """
        Load the pointing delay at a specified time.

        :param load_time: time at which to load the pointing delay
        """
        self.logger.debug("TpmDriver: load_pointing_delay")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.load_pointing_delay(load_time)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def start_beamformer(
        self: TpmDriver,
        start_time: int = 0,
        duration: int = -1,
        subarray_beam_id: int = 1,
        scan_id: int = 0,
    ) -> None:
        """
        Start the beamformer at the specified time.

        :param start_time: time at which to start the beamformer,
            defaults to 0
        :param duration: duration for which to run the beamformer,
            defaults to -1 (run forever)
        :param subarray_beam_id: ID of the subarray beam to start. Default = -1, all
        :param scan_id: ID of the scan which is started.
        """
        self.logger.debug(
            f"TpmDriver: Start beamformeri: params {start_time}, {duration}"
        )
        if subarray_beam_id != -1:
            self.logger.warning(
                "start_beamformer: separate start for different subarrays not supported"
            )
        if scan_id != 0:
            self.logger.warning("start_beamformer: scan ID value ignored")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    if self.tile.start_beamformer(start_time, duration):
                        self._is_beamformer_running = True
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def stop_beamformer(self: TpmDriver) -> None:
        """Stop the beamformer."""
        self.logger.debug("TpmDriver: Stop beamformer")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.stop_beamformer()
                    self._is_beamformer_running = False
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def configure_integrated_channel_data(
        self: TpmDriver,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 511,
    ) -> None:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        self.logger.debug("TpmDriver: configure_integrated_channel_data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.configure_integrated_channel_data(
                        integration_time, first_channel, last_channel
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def configure_integrated_beam_data(
        self: TpmDriver,
        integration_time: float = 0.5,
        first_channel: int = 0,
        last_channel: int = 191,
    ) -> None:
        """
        Configure and start the transmission of integrated channel data.

        Configure with the
        provided integration time, first channel and last channel. Data are sent
        continuously until the StopIntegratedData command is run.

        :param integration_time: integration time in seconds, defaults to 0.5
        :param first_channel: first channel
        :param last_channel: last channel
        """
        self.logger.debug("TpmDriver: configure_integrated_beam_data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.configure_integrated_beam_data(
                        integration_time, first_channel, last_channel
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def stop_integrated_data(self: TpmDriver) -> None:
        """Stop the integrated data."""
        self.logger.debug("TpmDriver: Stop integrated data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.stop_integrated_data()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def send_data_samples(
        self: TpmDriver,
        data_type: str = "",
        timestamp: int = 0,
        seconds: float = 0.2,
        n_samples: int = 1024,
        sync: bool = False,
        first_channel: int = 0,
        last_channel: int = 511,
        channel_id: int = 128,
        frequency: float = 150.0e6,
        round_bits: int = 3,
    ) -> None:
        """
        Front end for send_xxx_data methods.

        :param data_type: sample type. "raw", "channel", "channel_continuous",
                "narrowband", "beam"
        :param timestamp: Timestamp for start sending data. Default 0 start now
        :param seconds: Delay if timestamp is not specified. Default 0.2 seconds
        :param n_samples: number of samples to send per packet
        :param sync: (raw) send synchronised antenna samples, vs. round robin
        :param first_channel: (channel) first channel to send, default 0
        :param last_channel: (channel) last channel to send, default 511
        :param channel_id: (channel_continuous) channel to send
        :param frequency: (narrowband) Sky frequency for band centre, in Hz
        :param round_bits: (narrowband) how many bits to round

        :raises ValueError: if values wrong
        """
        # Check for type of data to be sent to LMC

        current_frame = self.fpga_current_frame
        tstamp: Optional[int] = timestamp or None
        if current_frame == 0:
            self.logger.error("Cannot send data before StartAcquisition")
            raise ValueError("Cannot send data before StartAcquisition")
        if timestamp and timestamp < (current_frame + 20):
            self.logger.error("Time is too early")
            raise ValueError("Time is too early")

        if data_type == "raw":
            self._send_raw_data(sync, tstamp, seconds)
        elif data_type == "channel":
            self._send_channelised_data(
                n_samples,
                first_channel,
                last_channel,
                timestamp=tstamp,
                seconds=seconds,
            )
        elif data_type == "channel_continuous":
            self._send_channelised_data_continuous(
                channel_id, n_samples, timestamp=tstamp, seconds=seconds
            )
        elif data_type == "narrowband":
            self._send_channelised_data_narrowband(
                frequency, round_bits, n_samples, timestamp=tstamp, seconds=seconds
            )
        elif data_type == "beam":
            self._send_beam_data(tstamp, seconds)
        else:
            self.logger.error(f"Unknown sample type: {data_type}")
            raise ValueError(f"Unknown sample type: {data_type}")

    def _send_raw_data(
        self: TpmDriver,
        sync: bool = False,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :param timestamp: when to start, defaults to now
        :param seconds: delay with respect to timestamp, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_raw_data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.send_raw_data(
                        sync=sync, timestamp=timestamp, seconds=seconds
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _send_channelised_data(
        self: TpmDriver,
        number_of_samples: int = 1024,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot of channelized data totalling number_of_samples spectra.

        :param number_of_samples: number of spectra to send, defaults to 1024
        :param first_channel: first channel to send, defaults to 0
        :param last_channel: last channel to send, defaults to 511
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.send_channelised_data(
                        number_of_samples=number_of_samples,
                        first_channel=first_channel,
                        last_channel=last_channel,
                        timestamp=timestamp,
                        seconds=seconds,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _send_channelised_data_continuous(
        self: TpmDriver,
        channel_id: int,
        number_of_samples: int = 1024,
        wait_seconds: int = 0,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit data from a channel continuously.

        It can be stopped with stop_data_transmission.

        :param channel_id: index of channel to send
        :param number_of_samples: number of spectra to send, defaults to 1024
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data_continuous")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.send_channelised_data_continuous(
                        channel_id,
                        number_of_samples=number_of_samples,
                        wait_seconds=wait_seconds,
                        timestamp=timestamp,
                        seconds=seconds,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _send_channelised_data_narrowband(
        self: TpmDriver,
        frequency: float,
        round_bits: int,
        number_of_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Continuously send channelised data from a single channel.

        This is a special mode used for UAV campaigns.

        :param frequency: sky frequency to transmit
        :param round_bits: which bits to round
        :param number_of_samples: number of spectra to send, defaults to 128
        :param wait_seconds: wait time before sending data, defaults to 0
        :param timestamp: when to start, defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_channelised_data_narrowband")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.send_channelised_data_narrowband(
                        frequency,
                        round_bits,
                        number_of_samples,
                        wait_seconds,
                        timestamp,
                        seconds,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _send_beam_data(
        self: TpmDriver, timestamp: Optional[int] = None, seconds: float = 0.2
    ) -> None:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TpmDriver: send_beam_data")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.send_beam_data(timestamp=timestamp, seconds=seconds)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def stop_data_transmission(self: TpmDriver) -> None:
        """Stop data transmission for send_channelised_data_continuous."""
        self.logger.debug("TpmDriver: stop_data_transmission")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.stop_data_transmission()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def start_acquisition(
        self: TpmDriver, start_time: Optional[str] = None, delay: Optional[int] = 2
    ) -> bool:
        """
        Start data acquisition.

        This must be run as a long running command

        :param start_time: the time at which to start data acquisition, defaults to None
        :param delay: delay start, defaults to 2

        :returns: if data acquisition started correctly
        """
        started = False
        self.logger.debug(
            f"TpmDriver:Start acquisition: start time: {start_time}, delay: {delay}"
        )
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    # Check if ARP table is populated before starting
                    self.tile.reset_eth_errors()
                    self.tile.check_arp_table()
                    # Start data acquisition on board
                    self.tile.start_acquisition(start_time, delay)
                    started = True
                    self._fpga_reference_time = self.tile[
                        "fpga1.pps_manager.sync_time_val"
                    ]
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

        if not started:
            return False
        self.logger.info("Waiting for start acquisition")
        max_timeout = 60  # Maximum delay, in 0.1 seconds
        started = False
        for i in range(max_timeout):
            time.sleep(0.1)
            with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
                if acquired:
                    try:
                        started = self._check_channeliser_started()
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                else:
                    self.logger.warning("Failed to acquire hardware lock")

            if started:
                self._set_tpm_status(TpmStatus.SYNCHRONISED)
                break
        if not started:
            self.logger.warning(
                f"Acquisition not started after {max_timeout*0.1} seconds"
            )
        return started

    def set_lmc_integrated_download(
        self: TpmDriver,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
    ) -> None:
        """
        Configure link and size of control data.

        :param mode: '1g' or '10g'
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        """
        self.logger.debug("TpmDriver: set_lmc_integrated_download")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.set_lmc_integrated_download(
                        mode,
                        channel_payload_length,
                        beam_payload_length,
                        dst_ip,
                        src_port,
                        dst_port,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    def current_tile_beamformer_frame(self: TpmDriver) -> int:
        """
        Return current tile beamformer frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        """
        self.logger.debug("TpmDriver: current_tile_beamformer_frame")
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self._current_tile_beamformer_frame = (
                        self.tile.current_tile_beamformer_frame()
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")
        return self._current_tile_beamformer_frame

    @property
    def is_beamformer_running(self: TpmDriver) -> bool:
        """
        Whether the beamformer is currently running.

        :return: whether the beamformer is currently running
        """
        return self._is_beamformer_running

    @property
    def pending_data_requests(self: TpmDriver) -> bool:
        """
        Check for pending data requests.

        :return: whether there are pending send data requests
        """
        self.logger.debug("TpmDriver: _pending_data_requests")
        return self._pending_data_requests

    #
    # The synchronisation routine for the current TPM requires that
    # the function below are accessible from the station (where station-level
    # synchronisation is performed), however I am not sure whether the routine
    # for the new TPMs will still required these
    #
    @property
    def phase_terminal_count(self: TpmDriver) -> int:
        """
        Return the phase terminal count.

        :return: the phase terminal count
        """
        self.logger.debug("TpmDriver: get_phase_terminal_count")
        self.logger.debug("TpmDriver: get_phase_terminal_count is simulated")
        return self._phase_terminal_count

    @phase_terminal_count.setter  # type: ignore[no-redef]
    def phase_terminal_count(self: TpmDriver, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        self.logger.debug("TpmDriver: set_phase_terminal_count")
        self.logger.debug("TpmDriver: set_phase_terminal_count is simulated")
        self._phase_terminal_count = value

    def post_synchronisation(self: TpmDriver) -> None:
        """
        Perform post tile configuration synchronization.

        TODO Private method or must be available externally?
        """
        # with self._hardware_lock:
        #    self.tile.post_synchronisation()

    def sync_fpgas(self: TpmDriver) -> None:
        """
        Synchronise the FPGAs.

        TODO Method appears to be mostly internal (private).
        """
        self.logger.debug("TpmDriver: sync_fpgas")
        with self._hardware_lock:
            self.tile.sync_fpgas()

    @property
    def test_generator_active(self: TpmDriver) -> bool:
        """
        Check if the test generator is active.

        :return: whether the test generator is active
        """
        return self._test_generator_active

    @test_generator_active.setter  # type: ignore[no-redef]
    def test_generator_active(self: TpmDriver, active: bool) -> None:
        """
        Set the test generator active flag.

        :param active: True if the generator has been activated
        """
        self._test_generator_active = active

    def configure_test_generator(
        self: TpmDriver,
        frequency0: float,
        amplitude0: float,
        frequency1: float,
        amplitude1: float,
        amplitude_noise: float,
        pulse_code: int,
        amplitude_pulse: float,
        load_time: int = 0,
    ) -> None:
        """
        Test generator setting.

        :param frequency0: Tone frequency in Hz of DDC 0
        :param amplitude0: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param frequency1: Tone frequency in Hz of DDC 1
        :param amplitude1: Tone peak amplitude, normalized to 31.875 ADC units,
            resolution 0.125 ADU
        :param amplitude_noise: Amplitude of pseudorandom noise
            normalized to 26.03 ADC units, resolution 0.102 ADU
        :param pulse_code: Code for pulse frequency.
            Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency
        :param amplitude_pulse: pulse peak amplitude, normalized
            to 127.5 ADC units, resolution 0.5 ADU
        :param load_time: Time to start the generator.
        """
        self.logger.debug(
            "Test generator: set tone 0: "
            + str(frequency0)
            + " Hz"
            + ", tone 1: "
            + str(frequency1)
            + " Hz"
        )
        # If load time not specified, is "now" + 30 ms
        end_time = 0
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    if load_time == 0:
                        load_time = self.tile.get_fpga_timestamp() + 180
                    # Set everything at same time
                    self.tile.test_generator_set_tone(
                        0, frequency0, amplitude0, 0.0, load_time
                    )
                    self.tile.test_generator_set_tone(
                        1, frequency1, amplitude1, 0.0, load_time
                    )
                    self.tile.test_generator_set_noise(amplitude_noise, load_time)
                    self.tile.set_test_generator_pulse(pulse_code, amplitude_pulse)
                    end_time = self.tile.get_fpga_timestamp()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

        if end_time < load_time:
            self.logger.warning("Test generator failed to program in 50 ms")

    def test_generator_input_select(self: TpmDriver, inputs: int = 0) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        """
        self.logger.debug("Test generator: set inputs " + hex(inputs))
        with acquire_timeout(self._hardware_lock, timeout=0.2) as acquired:
            if acquired:
                try:
                    self.tile.test_generator_input_select(inputs)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TpmDriver: Tile access failed: {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")
