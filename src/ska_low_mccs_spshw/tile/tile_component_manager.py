#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for tiles."""
from __future__ import annotations

import ipaddress
import json
import logging
import threading
import time
from typing import Any, Callable, Final, List, NoReturn, Optional, cast

import numpy as np
import tango
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_low_mccs_common import EventSerialiser, MccsDeviceProxy
from ska_low_mccs_common.component import MccsBaseComponentManager
from ska_low_mccs_common.component.command_proxy import MccsCommandProxy
from ska_low_sps_tpm_api.base.definitions import (
    BoardError,
    Device,
    LibraryError,
    RegisterInfo,
)
from ska_low_sps_tpm_api.tile import Tile
from ska_tango_base.base import TaskCallbackType, check_communicating
from ska_tango_base.executor import TaskExecutor
from ska_tango_base.poller import PollingComponentManager

from .exception_codes import HardwareVerificationError
from .tile_poll_management import (
    TileLRCRequest,
    TileRequest,
    TileRequestProvider,
    TileResponse,
)
from .tile_simulator import DynamicTileSimulator, TileSimulator
from .time_util import TileTime
from .tpm_status import TpmStatus
from .utils import LogLock, abort_task_on_exception, acquire_timeout

__all__ = ["TileComponentManager"]

# TODO MCCS-2295: Why does the TileRequestProvider, MccsTile and
# TileComponentManager have different names for things? It seems clearer for them
# all to use the name in ska_low_sps_tpm_api.Tile. Multiple maps like this increase
# the risk of mapping errors.
_ATTRIBUTE_MAP: Final = {
    "HEALTH_STATUS": "tile_health_structure",
    "PREADU_LEVELS": "preadu_levels",
    "PLL_LOCKED": "pll_locked",
    "CHECK_BOARD_TEMPERATURE": "board_temperature",
    "PPS_DELAY_CORRECTION": "pps_delay_correction",
    "IS_BEAMFORMER_RUNNING": "beamformer_running",
    "FPGA_REFERENCE_TIME": "fpga_reference_time",
    "TILE_ID": "tile_id",
    "STATION_ID": "station_id",
    "PHASE_TERMINAL_COUNT": "phase_terminal_count",
    "PPS_DELAY": "pps_delay",
    "PPS_DRIFT": "pps_drift",
    "ADC_RMS": "adc_rms",
    "CHANNELISER_ROUNDING": "channeliser_rounding",
    "IS_PROGRAMMED": "is_programmed",
    "CSP_ROUNDING": "csp_rounding",
    "STATIC_DELAYS": "static_delays",
    "PENDING_DATA_REQUESTS": "pending_data_requests",
    "BEAMFORMER_TABLE": "beamformer_table",
    "CHECK_CPLD_COMMS": "global_status_alarms",
    "ARP_TABLE": "arp_table",
    "TILE_BEAMFORMER_FRAME": "tile_beamformer_frame",
    "RFI_COUNT": "rfi_count",
}


class TaskCompleteWaiter(TaskCallbackType):
    """Wait for task to complete."""

    def __init__(self: TaskCompleteWaiter) -> None:
        """Initialise a new instance."""
        self._expected_status = TaskStatus.COMPLETED
        self._status: TaskStatus | None = None
        self._progress = 0
        self._result = None
        self._exception: Exception | None = None
        self._condition = threading.Condition()

    def __call__(
        self: TaskCompleteWaiter,
        status: TaskStatus | None = None,
        progress: int | None = None,
        result: Any = None,
        exception: Exception | None = None,
    ) -> None:
        # Update the internal state based on callback inputs
        if status is not None:
            self._status = status
        if progress is not None:
            self._progress = progress
        if result is not None:
            self._result = result
        if exception is not None:
            self._exception = exception

        # Notify that the task has updated its status
        with self._condition:
            self._condition.notify_all()

    def wait(self: TaskCompleteWaiter, timeout: float) -> bool:
        """
        Wait until the task reaches the expected status or the timeout is reached.

        :param timeout: timeout in seconds.

        :return: True if we arrived at TaskStatus.COMPLETED.
        """
        with self._condition:
            start_time = time.time()
            while (
                self._status != self._expected_status
                and time.time() - start_time < timeout
            ):
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time > 0:
                    self._condition.wait(timeout=remaining_time)
                else:
                    return False
            return self._status == self._expected_status


# pylint: disable=too-many-instance-attributes, too-many-lines, too-many-public-methods
class TileComponentManager(MccsBaseComponentManager, PollingComponentManager):
    """A component manager for a Tile (simulator or driver) and its power supply."""

    # This firmware name is generic to versions supported by
    # ska-low-sps-tpm-api library. Supporting both TPM_1_6 and
    # TPM_2_0 for example.
    FIRMWARE_NAME: str = "tpm_firmware.bit"
    CSP_ROUNDING: list[int] = [2] * 384
    CHANNELISER_TRUNCATION: list[int] = [3] * 512

    # pylint: disable=too-many-arguments, too-many-locals, too-many-statements
    def __init__(
        self: TileComponentManager,
        simulation_mode: SimulationMode,
        test_mode: TestMode,
        logger: logging.Logger,
        poll_rate: float,
        tile_id: int,
        station_id: int,
        tpm_ip: str,
        tpm_cpld_port: int,
        tpm_version: str,
        preadu_levels: list[float] | None,
        static_time_delays: list[float],
        subrack_fqdn: str,
        subrack_tpm_id: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        update_attribute_callback: Callable[..., None],
        _tile: Optional[TileSimulator] = None,
        event_serialiser: Optional[EventSerialiser] = None,
        default_lock_timeout: float = 0.4,
    ) -> None:
        """
        Initialise a new instance.

        :param simulation_mode: the simulation mode of this component
            manager. If `SimulationMode.TRUE`, then this component
            manager will launch an internal TPM simulator and interact
            with it; if `SimulationMode.FALSE`, this component manager
            will attempt to connect with an external TPM at the
            configured IP address and port.
        :param test_mode: the test mode of this component manager. This
            has no effect when the device is in `SimulationMode.FALSE`.
            But when the simulation mode is `SimulationMode.TRUE`, then
            this determines some properties of the simulator: if the
            test mode is `TestMode.TEST`, then the simulator will
            return static "canned" values that are easy to assert
            against during testing; if `TestMode.NONE`, the simulator
            will return dynamically changing values for attributes such
            as temperatures and voltages, making for a nice demo but not
            so easy to test against.
        :param logger: a logger for this object to use
        :param poll_rate: the poll rate
        :param tile_id: the unique ID for the tile
        :param station_id: the unique ID for the station to which this tile belongs.
        :param tpm_ip: the IP address of the tile
        :param tpm_cpld_port: the port at which the tile is accessed for control
        :param tpm_version: TPM version: "tpm_v1_2" or "tpm_v1_6"
        :param preadu_levels: preADU gain attenuation settings to apply for this TPM.
        :param static_time_delays: Delays in nanoseconds to account
            for static delay missmatches.
        :param subrack_fqdn: FQDN of the subrack that controls power to
            this tile
        :param subrack_tpm_id: This tile's position in its subrack
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param update_attribute_callback: Callback to call when attribute
            is updated.
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param event_serialiser: serialiser for events
        :param _tile: Optional tile to inject.
        :param default_lock_timeout: default timeout for hardware serialisation lock.
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack_says_tpm_power: PowerState = PowerState.UNKNOWN
        self._subrack_tpm_id = subrack_tpm_id
        self._power_state_lock = threading.RLock()
        self._update_attribute_callback = update_attribute_callback
        self.fault_state: Optional[bool] = None

        self._subrack_proxy: Optional[MccsDeviceProxy] = None

        self._simulation_mode = simulation_mode
        self._default_lock_timeout = default_lock_timeout
        self._hardware_lock = LogLock(f"tpm{tile_id:02d}lock", logger)
        # This TaskExecutor is used to check the synchronisation state
        # of the TPM.
        self._synchronised_checker = TaskExecutor(max_workers=1)
        # The callback from subrack will evaluate if the tpm
        # needs to be initialised. There is a rare race condition
        # where the evaluation will attempt initialisation although
        # initialisation is already in progress. This lock is used
        # to ensure this evaluation is correct
        self._initialise_lock = threading.Lock()
        self.power_state: PowerState = PowerState.UNKNOWN
        self.active_request: TileRequest | TileLRCRequest | None = None
        self._request_provider: Optional[TileRequestProvider] = None
        self.src_ip_40g_fpga1: str | None = None
        self.src_ip_40g_fpga2: str | None = None
        self._channeliser_truncation = self.CHANNELISER_TRUNCATION
        self._pps_delay_correction: int = 0
        self._fpga_reference_time = 0
        self._initial_pps_delay: int | None = None
        self._forty_gb_core_list: list = []
        self._fpgas_time: list[int] = []
        self._pending_data_requests = False
        self._tile_time = TileTime(0)
        self._nof_blocks: int = 0
        self._firmware_list: List[dict[str, Any]] = []
        self._station_id = station_id
        self._tile_id = tile_id
        self._tpm_status = TpmStatus.UNKNOWN
        self._csp_rounding = np.array(self.CSP_ROUNDING)
        self._csp_spead_format = "SKA"
        self._global_reference_time: int | None = None
        self._test_generator_active = False
        self.antenna_buffer_mode: str = "Not set"
        self.data_transmission_mode: str = "Not transmitting"
        self.integrated_data_transmission_mode: str = "Not transmitting"
        self._preadu_levels = preadu_levels
        self._static_time_delays: list[float] = static_time_delays
        self._firmware_name: str = self.FIRMWARE_NAME
        self._fpga_current_frame: int = 0
        self.last_pointing_delays: list = [[0.0, 0.0] for _ in range(16)]
        self.ddr_write_size: int = 0

        self._event_serialiser = event_serialiser

        if simulation_mode == SimulationMode.TRUE:
            self.tile = _tile or DynamicTileSimulator(logger)
        else:
            # =============================================
            # TODO: Bug/work needed in ska-low-sps-tpm-api.
            # If _tpm_version == None we have a chance of
            # an unhandled LibraryError. Passing in "" does
            # nothing, we are doing it here to avoid this bug.
            # Bug will be present if TPM is OFF.
            _tpm_version = ""
            # =============================================
            self.tile = Tile(
                ip=tpm_ip,
                port=tpm_cpld_port,
                logger=logger,
                tpm_version=_tpm_version,
            )

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            poll_rate=poll_rate,
        )

    def _submit_lrc_request(
        self: TileComponentManager,
        command_name: str,
        command_object: Callable,
        task_callback: Optional[Callable] = None,
        **kwargs: Any,
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit a LRC request to the polling loop.

        :param command_name: name of the command
        :param command_object: callable object to execute
        :param task_callback: callback to be called when the task is completed
        :param kwargs: additional arguments to be passed to the command object

        :return: a result code and a message
        """
        if not self._request_provider:
            if task_callback:
                task_callback(status=TaskStatus.REJECTED)
            self.logger.error("task REJECTED no request_provider")
            return None
        request = TileLRCRequest(
            name=command_name,
            command_object=command_object,
            task_callback=task_callback,
            **kwargs,
        )
        self._request_provider.enqueue_lrc(request)
        self.logger.info(f"Request {command_name} QUEUED.")
        return TaskStatus.QUEUED, "Task staged"

    def get_request(  # type: ignore[override]
        self: TileComponentManager,
    ) -> Optional[TileRequest | TileLRCRequest]:
        """
        Return the action/s to be taken in the next poll.

        :raises AssertionError: if the request provider is not initialised
            i.e has a None value.

        :return: request to be to be executed in the next poll.
        """
        if not self._request_provider:
            raise AssertionError(
                "The request provider is None, unable to get next request"
            )

        request_spec = self._request_provider.get_request(self._tpm_status)
        # If already a request simply return.
        if isinstance(request_spec, TileRequest):
            return request_spec

        if request_spec is None:
            self.logger.warning("Request provider returned None.")
            return None

        match request_spec:
            case "CHECK_CPLD_COMMS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.check_global_status_alarms,
                    publish=True,
                )
            case "CHECK_BOARD_TEMPERATURE":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_temperature,
                    publish=True,
                )
            case "CONNECT":
                try:
                    self.ping()
                    request = TileRequest(
                        "global_status_alarms",
                        self.tile.check_global_status_alarms,
                        publish=True,
                    )
                    # pylint: disable=broad-except
                except Exception as e:
                    # polling attempt was unsuccessful
                    self.logger.warning(f"Connection to tpm lost! : {e}")
                    request = TileRequest("connect", self.connect)
            case "IS_PROGRAMMED":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.is_programmed,
                    publish=True,
                )
            case "HEALTH_STATUS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_health_status,
                    publish=True,
                )
            case "ADC_RMS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec], self.tile.get_adc_rms, publish=True
                )
            case "PLL_LOCKED":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.check_pll_locked,
                    publish=True,
                )
            case "PENDING_DATA_REQUESTS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.check_pending_data_requests,
                    publish=False,
                )
            case "PPS_DELAY":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_pps_delay,
                    publish=True,
                )
            case "PPS_DRIFT":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self._get_pps_drift,
                    publish=True,
                )
            case "ARP_TABLE":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_arp_table,
                    publish=True,
                )
            case "PPS_DELAY_CORRECTION":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    command_object=self._get_pps_delay_correction,
                    publish=True,
                )
            case "IS_BEAMFORMER_RUNNING":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.beamformer_is_running,
                    publish=True,
                )
            case "PHASE_TERMINAL_COUNT":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_phase_terminal_count,
                    publish=True,
                )
            case "PREADU_LEVELS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_preadu_levels,
                    publish=True,
                )
            case "STATIC_DELAYS":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec], self.get_static_delays, publish=True
                )
            case "STATION_ID":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_station_id,
                    publish=True,
                )
            case "TILE_ID":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec], self.tile.get_tile_id, publish=True
                )
            case "CSP_ROUNDING":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec], self.csp_rounding, publish=True
                )
            case "CHANNELISER_ROUNDING":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self._channeliser_truncation,
                    publish=True,
                )
            case "BEAMFORMER_TABLE":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.get_beamformer_table,
                    publish=True,
                )
            case "FPGA_REFERENCE_TIME":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.formatted_fpga_reference_time,
                )
            case "TILE_BEAMFORMER_FRAME":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.current_tile_beamformer_frame,
                    publish=True,
                )
            case "RFI_COUNT":
                request = TileRequest(
                    _ATTRIBUTE_MAP[request_spec],
                    self.tile.read_broadband_rfi,
                    publish=True,
                )
            case _:
                message = f"Unrecognised poll request {repr(request_spec)}"
                self.logger.error(message)
                return None
        return request

    def poll(
        self: TileComponentManager, poll_request: TileRequest | TileLRCRequest
    ) -> TileResponse:
        """
        Poll request for TileComponentManager.

        Execute a command or read some values.

        :param poll_request: specification of the actions to be taken in
            this poll.

        :return: responses to queries in this poll
        """
        self.logger.debug(f"Executing request {poll_request.name} ...")
        # A callback hook to be updated after command executed.
        self.active_request = poll_request
        if isinstance(self.active_request, TileLRCRequest):
            self.active_request.notify_in_progress()
        # Claim lock before we attempt a request.
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            result = poll_request()
        return TileResponse(
            poll_request.name,
            result,
            poll_request.publish,
        )

    def poll_failed(self: TileComponentManager, exception: Exception) -> None:
        """
        Handle a failed poll.

        This is a hook called by the poller when an exception was raised.

        NOTE: This implementation may be a bit simplistic as of MCCS-1507.
        The exception code can be used to give more information to user.
        And potentially inform the poll prioritisation.

        :param exception: exception code raised from poll.
        """
        # TODO: would be great to formalise and document the exceptions raised
        # from the ska_low_sps_tpm_api.Tile. That way it will allow use to
        # handle exceptions better.
        match exception:
            case ConnectionError():
                self.logger.error(f"ConnectionError found {exception}")
            case LibraryError():
                self.logger.error(
                    f"LibraryError raised from poll {exception}, "
                    "check the cpld communications"
                )
            case BoardError():
                self.logger.error(f"BoardError: {repr(exception)}")
            case _:
                self.logger.error(f"Unexpected error found: {repr(exception)}")

        # We do not evaluate error codes. Connect if not already!
        assert self._request_provider is not None
        self._request_provider.desire_connection()

        # Update command tracker if defined in request.
        if isinstance(self.active_request, TileLRCRequest):
            self.active_request.notify_failed(f"Exception: {repr(exception)}")
            self.active_request = None
        elif isinstance(self.active_request, TileRequest):
            if self.active_request.publish:
                self._update_attribute_callback(
                    mark_invalid=True, **{self.active_request.name: None}
                )

        self.update_fault_state(poll_success=False)
        self.power_state = self._subrack_says_tpm_power

        # ================================================================
        # Update fault before power to allow exit from fault before OFF.
        # "else Action component_no_fault is not allowed in op_state OFF."
        # can occur
        self._update_component_state(fault=self.fault_state)
        # ================================================================
        self._update_component_state(power=self._subrack_says_tpm_power)
        if self._subrack_says_tpm_power == PowerState.UNKNOWN:
            super().poll_failed(exception)

    def update_fault_state(
        self: TileComponentManager,
        poll_success: bool,
        exception_code: Optional[Any] = None,
    ) -> None:
        """
        Update fault state.

        This method will evaluate if the current state if faulty.
        Depending on the previous fault state we will update the fault_state
        to allow navigation of the Opstate machine

        NOTE: As evaluation becomes more complex we may want to refactor
        this method into a class. Currently this is a very simple evaluation,
        only checking for an inconsistent state.

        :param poll_success: a bool representing if the poll was a success
        :param exception_code: the exception code raised in last poll.
        """
        is_faulty: bool = False
        match poll_success:
            case False:
                with acquire_timeout(
                    self._hardware_lock,
                    self._default_lock_timeout,
                    raise_exception=True,
                ):
                    if (
                        not self.is_connected
                        and self._subrack_says_tpm_power == PowerState.ON
                    ):
                        self.logger.error(
                            "Unable to connect to TPM, "
                            "however subrack reports it as ON. "
                        )
                        is_faulty = True
            case True:
                if self._subrack_says_tpm_power != PowerState.ON:
                    # This is an inconsistent state, we can connect with the
                    # TPM but the subrack is NOT reporting the TPM ON.
                    is_faulty = True
                    self.logger.error(
                        "Tpm is connectable but subrack says power is "
                        f"{PowerState(self._subrack_says_tpm_power).name}"
                    )
        if is_faulty:
            self.fault_state = is_faulty
        else:
            if self.fault_state is True:
                # We have stopped experiencing the fault.
                self.fault_state = False
            else:
                self.fault_state = None

    def poll_succeeded(self: TileComponentManager, poll_response: TileResponse) -> None:
        """
        Handle the receipt of new polling values.

        This is a hook called by the poller when values have been read
        during a poll.

        :param poll_response: response to the pool, including any values
            read.
        """
        if isinstance(self.active_request, TileLRCRequest):
            self.active_request.notify_completed()
            self.active_request = None

        self.update_fault_state(poll_success=True)

        # Publish all responses to TANGO interface.
        try:
            if poll_response.publish:
                self._update_attribute_callback(  # type: ignore[misc]
                    **{poll_response.command: poll_response.data},
                )
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(f"Exception raised in attribute callback {e}")
        super().poll_succeeded(poll_response)
        self._update_component_state(power=PowerState.ON, fault=self.fault_state)

    def _on_arrested_attribute(self: TileComponentManager, names: set[str]) -> None:
        """
        Trigger the callback when attributes are no longer provided for polling.

        :param names: a set containing the attributes that will no longer
            be provided for polling.
        """
        while len(names) != 0:
            val = names.pop()
            if _ATTRIBUTE_MAP.get(val) is not None:
                mapped_val = _ATTRIBUTE_MAP[val]
                try:
                    self._update_attribute_callback(
                        mark_invalid=True, **{mapped_val: None}
                    )
                except Exception as e:  # pylint: disable=broad-except
                    self.logger.warning(
                        f"Issue marking attribute {mapped_val} INVALID. {e}"
                    )
                    continue

    def polling_started(self: TileComponentManager) -> None:
        """Initialise the request provider and start connecting."""
        self._request_provider = TileRequestProvider(self._on_arrested_attribute)
        self._request_provider.desire_connection()
        self._start_communicating_with_subrack()

    def polling_stopped(self: TileComponentManager) -> None:
        """Uninitialise the request provider and set state UNKNOWN."""
        self._request_provider = None
        self._tpm_status = TpmStatus.UNKNOWN
        self._update_attribute_callback(
            programming_state=TpmStatus.UNKNOWN.pretty_name()
        )
        self.power_state = PowerState.UNKNOWN
        super().polling_stopped()

    def off(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the tpm off.

        :param task_callback: Update task state, defaults to None

        :return: a result code and a unique_id or message.
        """
        subrack_off_command_proxy = MccsCommandProxy(
            self._subrack_fqdn, "PowerOffTpm", self.logger
        )
        # Pass the task callback to be updated by command proxy.
        subrack_off_command_proxy(self._subrack_tpm_id, task_callback=task_callback)

        return TaskStatus.QUEUED, ""

    def on(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the tpm on.

        :param task_callback: Update task state, defaults to None

        :return: a result code and a unique_id or message.

        :raises AssertionError: request_provider is not yet initialised.
        """
        if self._request_provider is None:
            if task_callback:
                task_callback(
                    status=TaskStatus.REJECTED,
                    result=(ResultCode.REJECTED, "No request provider"),
                )
            raise AssertionError(
                "Cannot execute 'TileComponentManager.on'. "
                "request provider is not yet initialised."
            )
        subrack_on_command_proxy = MccsCommandProxy(
            self._subrack_fqdn, "PowerOnTpm", self.logger
        )
        # Do not pass the task_callback to command_proxy.
        # The on command is completed when initialisation has completed.
        subrack_on_command_proxy(self._subrack_tpm_id)

        request = TileLRCRequest(
            name="initialise",
            command_object=self._execute_initialise,
            task_callback=task_callback,
            force_reprogramming=False,
            pps_delay_correction=self._pps_delay_correction,
        )
        self.logger.info("On command placed initialise in poll QUEUE")
        # Picked up when the TPM is connectable. Or ABORTED after 60 seconds.
        with self._initialise_lock:
            self._request_provider.enqueue_lrc(request, priority=0)
        return TaskStatus.QUEUED, "Task staged"

    def _start_communicating_with_subrack(self: TileComponentManager) -> None:
        """
        Establish communication with the subrack.

        This will form a subscription to the power of the port this Tile is
        configured to be on.

        :raises ConnectionError: Connection to subrack failed
        """
        unconnected = self._subrack_proxy is None
        if unconnected:
            self._subrack_proxy = MccsDeviceProxy(
                self._subrack_fqdn,
                self.logger,
                connect=False,
                event_serialiser=self._event_serialiser,
            )
            self.logger.info("Connecting to the subrack")
            try:
                self._subrack_proxy.connect()
            except tango.DevFailed as dev_failed:
                self.logger.error(f"Failed to connect to subrack {dev_failed}")
                self._subrack_proxy = None
                raise ConnectionError(
                    f"Could not connect to '{self._subrack_fqdn}'"
                ) from dev_failed

            self._subrack_proxy.add_change_event_callback(
                f"tpm{self._subrack_tpm_id}PowerState",
                self._subrack_says_tpm_power_changed,
            )

    @property
    def is_connected(self) -> bool:
        """
        Check the communication with CPLD.

        :return: True if connected, else False.
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            try:
                self.tile[int(0x30000000)]  # pylint: disable=expression-not-assigned
                return True
            except Exception:  # pylint: disable=broad-except
                return False

    def _subrack_says_tpm_power_changed(
        self: TileComponentManager,
        event_name: str,
        event_value: PowerState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in tpm power state, as reported by subrack.

        This is a callback that is triggered by an event subscription
        on the subrack device.

        :param event_name: name of the event; will always be
            "areTpmsOn" for this callback
        :param event_value: the new attribute value
        :param event_quality: the quality of the change event
        """
        assert event_name.lower() == f"tpm{self._subrack_tpm_id}PowerState".lower(), (
            f"subrack 'tpm{self._subrack_tpm_id}PowerState' attribute changed callback "
            f"called but event_name is {event_name}."
        )

        if self._simulation_mode == SimulationMode.TRUE and isinstance(
            self.tile, TileSimulator
        ):
            if event_value == PowerState.ON:
                self.logger.warning("Mocking tpm on")
                self.tile.mock_on()
            if event_value == PowerState.OFF:
                self.logger.warning("Mocking tpm off")
                self.tile.mock_off()

        self.logger.info(f"subrack says power is {PowerState(event_value).name}")
        self._subrack_says_tpm_power = event_value

        self.power_state = event_value
        # Connect if not already.
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            __is_connected = self.is_connected
            # Connect if not already.
            if not __is_connected or self.tile.tpm is None:
                try:
                    self.connect()
                    __is_connected = True
                except Exception:  # pylint: disable=broad-except
                    self.logger.error("Subrack callback failed to connect to hardware.")

        if event_value == PowerState.ON:
            self._tile_time.set_reference_time(self._fpga_reference_time)

            # Attempt reinitialisation if connected
            # and not already initialised/ing.
            if __is_connected and self._tpm_status not in [
                TpmStatus.INITIALISED,
                TpmStatus.SYNCHRONISED,
            ]:
                with self._initialise_lock:
                    if (
                        self._request_provider
                        and not (
                            isinstance(self.active_request, TileLRCRequest)
                            and self.active_request.name.lower() != "initialise"
                        )
                        and not self._request_provider.initialise_queued
                    ):
                        request = TileLRCRequest(
                            name="initialise",
                            command_object=self._execute_initialise,
                            task_callback=None,
                            force_reprogramming=False,
                            pps_delay_correction=self._pps_delay_correction,
                        )
                        self.logger.info(
                            "Subrack has registered that the TPM has power "
                            "but is not yet initialised or synchronised. "
                            "Initialising."
                        )
                        assert self._request_provider is not None

                        self._request_provider.enqueue_lrc(request, priority=0)

        else:
            self._tile_time.set_reference_time(0)

    def tile_info(self: TileComponentManager) -> dict[str, Any]:
        """
        Return information about the tile.

        :return: information relevant to tile.
        """
        with acquire_timeout(self._hardware_lock, timeout=2.4, raise_exception=True):
            return self.tile.info

    @property
    def global_reference_time(self: TileComponentManager) -> str | None:
        """
        Return the Unix time used as global synchronization time.

        :return: Unix time used as global synchronization time
        """
        if self._global_reference_time:
            return self._tile_time.format_time_from_timestamp(
                self._global_reference_time
            )
        return ""

    @global_reference_time.setter
    def global_reference_time(self: TileComponentManager, reference_time: str) -> None:
        """
        Set the Unix time used as global synchronization time.

        :param reference_time: Reference time representing timestamp for frame 0
        """
        if reference_time == "":
            global_reference_time = None
        else:
            global_reference_time = self._tile_time.timestamp_from_utc_time(
                reference_time
            )
        start_time = global_reference_time

        self.logger.info(f"Global reference time set to {start_time}")
        if start_time is None or start_time <= 0:
            self._global_reference_time = None
        else:
            self._global_reference_time = start_time

    def reevaluate_tpm_status(self: TileComponentManager) -> bool:
        """
        Reevaluate the TpmStatus.

        NOTE: This method should not be needed. But can be used as a
        sanity check on the TileProgrammingState

        :return: True is the re-evaluated TpmStatus differs from the
            automated evaluation.
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            _initial_tpm_status = self._tpm_status
            self.__update_tpm_status()
            if _initial_tpm_status != self._tpm_status:
                self.logger.warning(
                    "The reevaluation of the TpmStatus returned "
                    "a different value to the automatic state "
                    "evaluation."
                )
            return _initial_tpm_status != self._tpm_status

    @property
    def tpm_status(self: TileComponentManager) -> TpmStatus:
        """
        Return the TPM status.

        :return: the TPM status
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            core_communication = self.tile.check_communication()
            self._update_attribute_callback(core_communication=core_communication)

            if not any(core_communication.values()):
                # TPM OFF or Network Issue
                if self.power_state == PowerState.UNKNOWN:
                    return TpmStatus.UNKNOWN
                if self.power_state != PowerState.ON:
                    return TpmStatus.OFF
                return TpmStatus.UNCONNECTED

            try:
                # We are connected to at least the CPLD.
                # TPM ON, FPGAs not programmed or TPM overtemperature self shutdown
                status = TpmStatus.UNPROGRAMMED
                if self.tile.is_programmed() is False:
                    status = TpmStatus.UNPROGRAMMED
                elif self._check_initialised() is False:
                    status = TpmStatus.PROGRAMMED
                elif self._check_channeliser_started() is False:
                    status = TpmStatus.INITIALISED
                else:
                    status = TpmStatus.SYNCHRONISED
                return status
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(
                    "Unexpected exception raised when "
                    f"evaluating TileProgrammingState: {e}\n"
                    f"Last known state = {status.pretty_name()}"
                )
                # Return the last know TpmStatus.
                return status

    def ping(self: TileComponentManager) -> None:
        """Check we can communicate with TPM."""
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            self.tile[int(0x30000000)]  # pylint: disable=expression-not-assigned
            self.__update_tpm_status()

    def _check_initialised(self: TileComponentManager) -> bool:
        """
        Return whether this TPM has been correctly initialised.

        Must be run within protected block using self._hardware_lock
        as it acceedes tile hardware registers

        :return: initialisation state
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            _fpgas_time = [
                self.tile.get_fpga_time(Device.FPGA_1),
                self.tile.get_fpga_time(Device.FPGA_2),
            ]
            return (_fpgas_time[0] != 0) and (_fpgas_time[1] != 0)

    def _check_channeliser_started(self: TileComponentManager) -> bool:
        """
        Check that the channeliser is correctly generating samples.

        :return: channelised stream data valid flag
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            return (
                self.tile["fpga1.dsp_regfile.stream_status.channelizer_vld"] == 1
                and self.tile["fpga2.dsp_regfile.stream_status.channelizer_vld"] == 1
            )

    # ----------------------
    # Long running commands.
    # ----------------------
    @abort_task_on_exception
    @check_communicating
    def initialise(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        force_reprogramming: bool = True,
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit the initialise slow task.

        This method returns immediately after it is submitted for polling.

        :param task_callback: Update task state, defaults to None
        :param force_reprogramming: Force FPGA reprogramming,
            for complete initialisation

        :returns: A tuple containing a task status and a unique id string to
            identify the command
        """
        if not self._request_provider:
            if task_callback:
                task_callback(status=TaskStatus.REJECTED)
            self.logger.error("task REJECTED no request_provider")
            return None
        request = TileLRCRequest(
            name="initialise",
            command_object=self._execute_initialise,
            task_callback=task_callback,
            force_reprogramming=force_reprogramming,
            pps_delay_correction=self._pps_delay_correction,
        )
        with self._initialise_lock:
            self._request_provider.enqueue_lrc(request, priority=0)
        self.logger.info("Initialise command placed initialise in poll QUEUE")
        return TaskStatus.QUEUED, "Task staged"

    @check_communicating
    def _execute_initialise(
        self: TileComponentManager,
        force_reprogramming: bool,
        pps_delay_correction: int,
    ) -> None:
        """
        Initialise the TPM.

        :param force_reprogramming: Force FPGA reprogramming,
            for complete initialisation
        :param pps_delay_correction: the delay correction to apply to the
            pps signal.
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            if force_reprogramming:
                self.logger.info("Forcing erasing of FPGA.")
                self.tile.erase_fpgas()
                self._tpm_status = TpmStatus.UNPROGRAMMED
                self._update_attribute_callback(
                    programming_state=TpmStatus.UNPROGRAMMED.pretty_name()
                )
            prog_status = False

            if self.tile.is_programmed() is False:
                self.logger.error(
                    f"Programming tile with firmware {self._firmware_name}"
                )

                self.tile.program_fpgas(self._firmware_name)
            prog_status = self.tile.is_programmed()

            #
            # Initialisation after programming the FPGA
            #
            if prog_status:
                self._tpm_status = TpmStatus.PROGRAMMED
                self._update_attribute_callback(
                    programming_state=TpmStatus.PROGRAMMED.pretty_name()
                )
                #
                # Base initialisation
                #
                self.logger.info(
                    "initialising tile with: \n"
                    f"* tile ID of {self._tile_id} \n"
                    f"* pps correction of {pps_delay_correction} \n"
                    f"* src_ip_fpga1 of {self.src_ip_40g_fpga1} \n"
                    f"* src_ip_fpga2 of {self.src_ip_40g_fpga2} \n"
                    f"* staticTimeDelays of {self._static_time_delays} \n"
                    f"* PreAduLevels of {self._preadu_levels} \n"
                )
                self.tile.initialise(
                    station_id=self._station_id,
                    tile_id=self._tile_id,
                    pps_delay=pps_delay_correction,
                    active_40g_ports_setting="port1-only",
                    src_ip_fpga1=self.src_ip_40g_fpga1,
                    src_ip_fpga2=self.src_ip_40g_fpga2,
                    time_delays=self._static_time_delays,
                )
                #
                # extra steps required to have it working
                #
                self.logger.info(
                    "TileComponentManager: reset_and_initialise_beamformer"
                )
                self.tile.initialise_beamformer(128, 8)

                self.tile.set_first_last_tile(False, False)

                # self.tile.post_synchronisation()

                if self._preadu_levels:
                    self.logger.info(
                        "TileComponentManager: setting PreADU attenuation..."
                    )
                    self.tile.set_preadu_levels(self._preadu_levels)
                    if self.tile.get_preadu_levels() != self._preadu_levels:
                        self.logger.warning(
                            "TileComponentManager: set PreADU attenuation failed"
                        )

                self.logger.info("TileComponentManager: initialisation completed")
                self._tpm_status = TpmStatus.INITIALISED
                self._update_attribute_callback(
                    programming_state=TpmStatus.INITIALISED.pretty_name()
                )
                # The initial pps_delay must be reset after initialisation.
                self._initial_pps_delay = None
                if self._global_reference_time:
                    self.logger.info(
                        "Global reference time specifed, starting acquisition"
                    )
                    self._start_acquisition()

    @abort_task_on_exception
    @check_communicating
    def download_firmware(
        self: TileComponentManager, argin: str, task_callback: Optional[Callable]
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit the download_firmware slow task.

        This method returns immediately after it is submitted for execution.

        :param argin: can either be the design name returned from
            GetFirmwareAvailable command, or a path to a
            file
        :param task_callback: Update task state, defaults to None

        :returns: A tuple containing a task status and a unique id string to
            identify the command
        """
        if not self._request_provider:
            if task_callback:
                task_callback(status=TaskStatus.REJECTED)
            self.logger.error("task REJECTED no request_provider")
            return None
        request = TileLRCRequest(
            name="download_firmware",
            command_object=self._download_firmware,
            task_callback=task_callback,
            bitfile=argin,
        )
        self._request_provider.enqueue_lrc(request, priority=0)
        self.logger.info("Download_firmware command placed in poll QUEUE")
        return TaskStatus.QUEUED, "Task staged"

    @check_communicating
    def _download_firmware(
        self: TileComponentManager,
        bitfile: str,
    ) -> None:
        """
        Download tpm firmware using slow command.

        :param bitfile: can either be the design name returned or a path to a file
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            self.logger.info("Programming fpgas ...")
            self.tile.program_fpgas(bitfile)
            is_programmed = self.tile.is_programmed()

            if is_programmed:
                self._firmware_name = bitfile

    @abort_task_on_exception
    @check_communicating
    def start_acquisition(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        start_time: Optional[str] = None,
        delay: int = 2,
        global_reference_time: Optional[str] = None,
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit the start_acquisition slow task.

        :param task_callback: Update task state, defaults to None
        :param start_time: the acquisition start time
        :param delay: a delay to the acquisition start
        :param global_reference_time: the start time assumed for starting the timestamp

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        if start_time is None:
            start_timestamp = None
        else:
            start_timestamp = self._tile_time.timestamp_from_utc_time(start_time)
            if start_timestamp < 0:
                self.logger.error("Invalid time for start_time")
                start_timestamp = None
            delay = 0

        if global_reference_time is None:
            global_start_timestamp = None
        else:
            global_start_timestamp = self._tile_time.timestamp_from_utc_time(
                global_reference_time
            )
            if global_start_timestamp < 0:
                self.logger.error("Invalid time for global_reference_time")
                global_start_timestamp = None
            delay = 0

        return self._submit_lrc_request(
            command_name="start_acquisition",
            command_object=self._start_acquisition,
            task_callback=task_callback,
            start_time=start_timestamp,
            delay=delay,
            global_reference_time=global_start_timestamp,
        )

    @check_communicating
    def _start_acquisition(
        self: TileComponentManager,
        start_time: Optional[int] = None,
        global_reference_time: Optional[int] = None,
        delay: int = 2,
    ) -> None:
        """
        Start acquisition using slow command.

        :param start_time: the time at which to start data acquisition, defaults to None
        :param delay: delay start, defaults to 2
        :param global_reference_time: the start time assumed for starting the timestamp

        :raises TimeoutError: When unable to abort previous command.
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            # Wait for COMPLETE status.
            task_waiter = TaskCompleteWaiter()
            self._synchronised_checker.abort(task_waiter)
            # An arbitrary 10 seconds hard failure when we are unable to stop
            # the state waiter thread,
            if not task_waiter.wait(timeout=10):
                raise TimeoutError("Unable to abort previous waiter thread in time. ")

            if global_reference_time is None:
                global_reference_time = self._global_reference_time
            else:
                self._global_reference_time = global_reference_time

            self.logger.info(
                f"Start acquisition: start time: {start_time}, delay: {delay}"
            )

            # Check if ARP table is populated before starting
            self.tile.reset_eth_errors()
            self.tile.check_arp_table()
            # Start data acquisition on board
            self.tile.start_acquisition(
                start_time,
                delay,
                global_reference_time,
            )
            self._fpga_reference_time = self.tile["fpga1.pps_manager.sync_time_val"]

            if start_time is None:
                deadline = time.time() + delay
            else:
                deadline = start_time + delay

            # Abort and open new thread without waiting.
            self.logger.info(
                "New request to synchronise. Replacing old monitoring thread with new!"
            )
            self._synchronised_checker.submit(
                self.__wait_for_synchronised, kwargs={"deadline": deadline}
            )

    def __wait_for_synchronised(
        self: TileComponentManager,
        deadline: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Wait for synchronisation until deadline.

        :param deadline: the time to wait until giving up.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """

        def __check_channeliser_started() -> bool:
            started = False
            try:
                with acquire_timeout(
                    self._hardware_lock,
                    self._default_lock_timeout,
                    raise_exception=True,
                ):
                    started = self._check_channeliser_started()
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")
            return started

        while time.time() < deadline + 1:
            if task_abort_event is not None:
                if task_abort_event.is_set():
                    self.logger.info("Waiter thread stopped.")
                    return
            started = __check_channeliser_started()
            if started:
                break
            time.sleep(0.2)
        else:
            started = __check_channeliser_started()
            if not started:
                self.logger.warning("Acquisition not started in time.")
                self._tile_time.set_reference_time(0)
                return

        self._tile_time.set_reference_time(self._fpga_reference_time)
        self._tpm_status = TpmStatus.SYNCHRONISED
        self._update_attribute_callback(
            programming_state=TpmStatus.SYNCHRONISED.pretty_name()
        )

    # --------------------------------
    # Properties
    # --------------------------------

    def __update_tpm_id(
        self: TileComponentManager, station_id: int, tile_id: int
    ) -> None:
        """
        Update the TPM id.

        :param station_id: the station_id to set
        :param tile_id: the tile_id to set.

        :raises HardwareVerificationError: When the readback from a set_value
            has unexpected result.
        """
        # ska-low-sps-tpm-api will return -1 when TPM not programmed.
        # This flag is used to mark the attribute as INVALID.
        error_code = -1

        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.set_station_id(station_id, tile_id)
            self._station_id = self.tile.get_station_id()
            self._tile_id = self.tile.get_tile_id()

        self._update_attribute_callback(
            tile_id=self._tile_id, mark_invalid=self._tile_id == error_code
        )
        self._update_attribute_callback(
            station_id=self._station_id, mark_invalid=self._station_id == error_code
        )
        if self._station_id != station_id:
            raise HardwareVerificationError(
                expected=station_id, actual=self._station_id
            )
        if self._tile_id != tile_id:
            raise HardwareVerificationError(expected=tile_id, actual=self._tile_id)
        self.logger.info(f"set station_id : {station_id}, " f"tile_id : {tile_id}")

    def set_tile_id(self: TileComponentManager, value: int) -> None:
        """
        Set Tile ID.

        :param value: assigned tile Id value
        """
        with acquire_timeout(self._hardware_lock, timeout=2.4, raise_exception=True):
            if not self.tile.is_programmed():
                return

            self.__update_tpm_id(self._station_id, value)

    def set_station_id(self: TileComponentManager, value: int) -> None:
        """
        Set Station ID.

        :param value: assigned station Id value
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            if not self.tile.is_programmed():
                return
            self.__update_tpm_id(value, self._tile_id)

    @property
    def firmware_name(self: TileComponentManager) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware name
        """
        return self._firmware_name

    @property
    @check_communicating
    def firmware_version(self: TileComponentManager) -> str:
        """
        Return the name of the firmware that this TPM simulator is running.

        :return: firmware version (major.minor)
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            _firmware_list = self.tile.get_firmware_list()[0]
            return (
                "Ver."
                + str(_firmware_list["major"])
                + "."
                + str(_firmware_list["minor"])
                + " build "
                + str(_firmware_list["build"])
                + ":"
                + str(_firmware_list["time"])
            )

    @property
    @check_communicating
    def firmware_available(
        self: TileComponentManager,
    ) -> List[dict[str, Any]]:
        """
        Return the list of the firmware loaded in the system.

        :return: the firmware list
        """
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self._firmware_list = list(self.tile.get_firmware_list())
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")
        return self._firmware_list

    @property
    def register_list(self: TileComponentManager) -> list[str]:
        """
        Return a list of registers available on each device.

        :return: list of registers

        :raises ValueError: if the tpm is value None.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            reglist = []
            try:
                if self.tile.tpm is None:
                    raise ValueError("Cannot read register on unconnected TPM.")
                regmap = self.tile.find_register("")
                for reg in regmap:
                    if isinstance(reg, RegisterInfo):
                        reglist.append(reg.name)
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")
            return reglist

    # ---------------------------------------------
    # Timed commands. Convert time to frame number.
    # ---------------------------------------------

    @property
    @check_communicating
    def clock_present(self: TileComponentManager) -> NoReturn:
        """
        Check if 10 MHz clock signal is present.

        :raises NotImplementedError: not implemented in ska-low-sps-tpm-api.
        """
        raise NotImplementedError(
            "methods clock_present not yet implemented in ska-low-sps-tpm-api"
        )

    @property
    @check_communicating
    def sysref_present(self: TileComponentManager) -> NoReturn:
        """
        Check if SYSREF signal is present.

        :raises NotImplementedError: not implemented in ska-low-sps-tpm-api.
        """
        raise NotImplementedError(
            "methods sysref_present not yet implemented in ska-low-sps-tpm-api"
        )

    @property
    @check_communicating
    def fpga_time(self: TileComponentManager) -> str:
        """
        Return FPGA internal time in UTC format.

        :return: FPGA internal time
        """
        return self._tile_time.format_time_from_timestamp(self.fpgas_time[0])

    def frame_from_utc_time(self: TileComponentManager, utc_time: str) -> int:
        """
        Return the frame from utc time.

        :param utc_time: the time in utc format.

        :returns: the frame from utc time.
        """
        return self._tile_time.frame_from_utc_time(utc_time)

    @property
    @check_communicating
    def fpgas_time(self: TileComponentManager) -> list[int]:
        """
        Return the FPGAs clock time.

        Useful for detecting clock skew, propagation
        delays, contamination delays, etc.

        :return: the FPGAs clock time
        :raises ConnectionError: if communication with tile failed
        """
        failed = False
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                if not self.tile.is_programmed():
                    self.logger.info("Trying to read time from an unprogrammed FPGA")
                    return [0, 0]
                try:
                    self._fpgas_time = [
                        self.tile.get_fpga_time(Device.FPGA_1),
                        self.tile.get_fpga_time(Device.FPGA_2),
                    ]
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
                    failed = True
            else:
                self.logger.warning("Failed to acquire hardware lock")
                failed = True
        if failed:
            raise ConnectionError("Cannot read time from FPGA")
        return self._fpgas_time

    @property
    def fpga_reference_time(self: TileComponentManager) -> int:
        """
        Return the FPGA reference time.

        Required to map the FPGA timestamps, expressed in frames
        to UTC time

        :return: the FPGA_1 reference time, in Unix seconds
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile["fpga1.pps_manager.sync_time_val"]

    @property
    def fpga_frame_time(self: TileComponentManager) -> str:
        """
        Return FPGA frame time in UTC format.

        frame time is the timestamp for the current frame being processed.
        Value reported here refers to the ADC frames, but the total processing
        delay is < 1ms and thus irrelevant on the timescales of MCCS response time

        :return: FPGA reference time
        """
        reference_time = self.fpga_reference_time
        self._tile_time.set_reference_time(reference_time)
        return self._tile_time.format_time_from_frame(self.fpga_current_frame)

    @property
    def formatted_fpga_reference_time(self: TileComponentManager) -> str:
        """
        Return FPGA reference time in UTC format.

        Reference time is set as part of start_observation.
        It represents the timestamp  for the first frame

        :return: FPGA reference time
        """
        reference_time = self.fpga_reference_time
        self._tile_time.set_reference_time(reference_time)
        return self._tile_time.format_time_from_timestamp(reference_time)

    @property
    @check_communicating
    def fpga_current_frame(self: TileComponentManager) -> int:
        """
        Return the FPGA current frame counter.

        :return: the FPGA_1 current frame counter
        :raises ConnectionError: if communication with tile failed
        """
        failed = False
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self._fpga_current_frame = self.tile.get_fpga_timestamp()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
                    failed = True
            else:
                self.logger.warning("Failed to acquire hardware lock")
                failed = True
        if failed:
            raise ConnectionError("Cannot read time from FPGA")
        return self._fpga_current_frame

    @property
    @check_communicating
    def current_tile_beamformer_frame(self: TileComponentManager) -> int:
        """
        Return current tile beamformer frame, in units of 256 ADC frames.

        :return: current tile beamformer frame
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.current_tile_beamformer_frame()

    @check_communicating
    def get_tpm_temperature_thresholds(
        self: TileComponentManager,
    ) -> None | dict[str, tuple[float, float]]:
        """
        Return the temperature thresholds in firmware.

        :returns: A dictionary containing the thresholds or
            None if lock could not be acquired in 0.4 seconds.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_tpm_temperature_thresholds()

    @property
    @check_communicating
    def pps_delay(self: TileComponentManager) -> Optional[int]:
        """
        Return the pps delay from the TPM.

        :return: the pps_delay from the TPM.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_pps_delay(enable_correction=False)

    @property
    def csp_spead_format(self: TileComponentManager) -> str:
        """
        Get CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :return: CSP Spead format. AAVS or SKA
        """
        return self._csp_spead_format

    @csp_spead_format.setter
    def csp_spead_format(self: TileComponentManager, spead_format: str) -> None:
        """
        Set CSP SPEAD format.

        CSP format is: AAVS for the format used in AAVS2-AAVS3 system,
        using a reference Unix time specified in the header.
        SKA for the format defined in SPS-CBF ICD, based on TAI2000 epoch.

        :param spead_format: format used in CBF SPEAD header: "AAVS" or "SKA"
        """
        self._csp_spead_format = spead_format
        hw_spead_format = spead_format == "SKA"
        if not self.is_programmed:
            self.logger.warning("speadFormat not set in hardware, tile not connected")
            return
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                if self.tile.spead_ska_format_supported:
                    try:
                        self.tile.set_spead_format(hw_spead_format)
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(f"TpmDriver: Tile access failed: {e}")
                elif hw_spead_format:
                    self.logger.error("SKA SPEAD format not supported in firmware")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    # ----------------------------
    # AntennaBuffer
    # ----------------------------

    @check_communicating
    def set_up_antenna_buffer(
        self: TileComponentManager,
        mode: str,
        ddr_start_byte_address: int,
        max_ddr_byte_size: Optional[int],
    ) -> bool:
        """Set up the antenna buffer.

        :param mode: netwrok to transmit antenna buffer data to. Options: 'SDN'
            (Science Data Network) and 'NSDN' (Non-Science Data Network)
        :param ddr_start_byte_address: first address in the DDR for antenna buffer
            data to be written in (in bytes).
        :param max_ddr_byte_size: last address for writing antenna buffer data
            (in bytes). If 'None' is chosen, the method will assume the last
            address to be the final address of the DDR chip

        :return: True if set up ran succesfully, False if it fails.
        """
        with acquire_timeout(self._hardware_lock, timeout=0.4) as acquired:
            if acquired:
                try:
                    self.antenna_buffer_mode = mode
                    self.tile.set_up_antenna_buffer(
                        mode, ddr_start_byte_address, max_ddr_byte_size
                    )
                except RuntimeError as err:
                    self.logger.error(f"Failed to set up antenna buffer: {err}")
                    return False
                return self.tile._antenna_buffer_tile_attribute.get(
                    "set_up_complete", False
                )
            self.logger.warning("Failed to acquire hardware lock")
            return False

    @abort_task_on_exception
    @check_communicating
    def start_antenna_buffer(
        self: TileComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str] | None:
        """Submit the start antenna buffer method.

        This method returns immediately after it submitted
        `self._start_antenna_buffer` for execution.

        :param argin: can either be the design name returned from
            GetFirmwareAvailable command, or a path to a
            file
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        if not self._request_provider:
            if task_callback:
                task_callback(status=TaskStatus.REJECTED)
            self.logger.error("task REJECTED no request_provider")
            return None
        kwargs = json.loads(argin)
        request = TileLRCRequest(
            name="start_antenna_buffer",
            command_object=self._start_antenna_buffer,
            task_callback=task_callback,
            **kwargs,
        )
        self._request_provider.enqueue_lrc(request)
        return TaskStatus.QUEUED, "Task staged"

    @check_communicating
    def _start_antenna_buffer(
        self: TileComponentManager,
        antennas: list,
        start_time: int,
        timestamp_capture_duration: int,
        continuous_mode: bool,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """Start recording to the antenna buffer.

        :param antennas: a list of antenna IDs to be used by the buffer, from 0 to 15.
            One or two antennas can be used for each FPGA, or 1 to 4 per buffer.
        :param start_time: the first time stamp that will be written into the DDR.
            When set to -1, the buffer will begin writing as soon as possible.
        :param timestamp_capture_duration: the capture duration in timestamps.
            Timestamps are in units of 256 ADC samples (256*1.08us).
        :param continuous_mode: "True" for continous capture. If enabled, time capture
            durations is ignored
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        success = True
        with acquire_timeout(self._hardware_lock, timeout=0.4) as acquired:
            if acquired:
                try:
                    self.ddr_write_size = self.tile.start_antenna_buffer(
                        antennas,
                        start_time,
                        timestamp_capture_duration,
                        continuous_mode,
                    )
                except RuntimeError as err:
                    self.logger.error(f"Failed to start antenna buffer: {err}")
                    success = False

                self.logger.info(
                    f"Started antenna buffer with ddr size: {self.ddr_write_size}"
                )
                success = self.tile._antenna_buffer_tile_attribute.get(
                    "data_capture_initiated", False
                )
            else:
                success = False
                self.logger.warning("Failed to acquire hardware lock")

        if task_callback:
            if success:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="Start acquisition has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result=("Start acquisition task failed")
                )

    def read_antenna_buffer(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str] | None:
        """Read from the antenna buffer.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        if not self._request_provider:
            if task_callback:
                task_callback(status=TaskStatus.REJECTED)
            self.logger.error("task REJECTED no request_provider")
            return None
        request = TileLRCRequest(
            name="read_antenna_buffer",
            command_object=self._read_antenna_buffer,
            task_callback=task_callback,
        )
        self._request_provider.enqueue_lrc(request)
        return TaskStatus.QUEUED, "Task staged"

    @check_communicating
    def _read_antenna_buffer(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """Read from the antenna buffer.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        success = True
        with acquire_timeout(self._hardware_lock, timeout=0.4) as acquired:
            if acquired:
                try:
                    self.tile.read_antenna_buffer()
                except RuntimeError as err:
                    self.logger.error(f"Failed to read antenna buffer: {err}")
                    success = False
            else:
                success = False
                self.logger.warning("Failed to acquire hardware lock")

        if task_callback:
            if success:
                task_callback(
                    status=TaskStatus.COMPLETED,
                    result="Read antenna buffer has completed",
                )
            else:
                task_callback(
                    status=TaskStatus.FAILED, result="Read antenna buffer task failed"
                )
            return

    @check_communicating
    def stop_antenna_buffer(self: TileComponentManager) -> bool:
        """Stop writing to the antenna buffer.

        :return: True if stop ran succesfully, False if it fails.
        """
        with acquire_timeout(self._hardware_lock, timeout=0.4) as acquired:
            if acquired:
                try:
                    self.tile.stop_antenna_buffer()
                    self.antenna_buffer_mode = "Not set"
                except RuntimeError as err:
                    self.logger.error(f"Failed to stop antenna buffer: {err}")
                    return False
                return True
            self.logger.warning("Failed to acquire hardware lock")
            return False

    # -----------------------------
    # FastCommands
    # ----------------------------

    def connect(self: TileComponentManager) -> None:
        """
        Check we can connect to the TPM.

        :raises ConnectionError: when unable to connect to TPM
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            if not self.is_connected or self.tile.tpm is None:
                try:
                    self.logger.debug("Connecting to TPM")
                    self.tile.connect()
                    self.tile[  # pylint: disable=expression-not-assigned
                        int(0x30000000)
                    ]
                except Exception as e:
                    self.logger.error(f"Failed to connect to TPM {e}")
                    self.__update_tpm_status()
                    raise ConnectionError("Failed in connect to TPM") from e
            self.__update_tpm_status()
        self.logger.error("end of connect")

    def __update_tpm_status(self: TileComponentManager) -> None:
        """Update the TpmStatus."""
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            self._tpm_status = self.tpm_status
            self._update_attribute_callback(
                programming_state=self._tpm_status.pretty_name()
            )

    def set_pps_delay_correction(
        self: TileComponentManager,
        correction: int,
    ) -> None:
        """
        Set the ppsDelay correction.

        :param correction: the correction to set
        """
        self._pps_delay_correction = correction

    @check_communicating
    def set_lmc_integrated_download(
        self: TileComponentManager,
        mode: str,
        channel_payload_length: int,
        beam_payload_length: int,
        dst_ip: Optional[str] = None,
        src_port: int = 0xF0D0,
        dst_port: int = 4660,
        netmask_40g: int | None = None,
        gateway_40g: int | None = None,
    ) -> None:
        """
        Configure link and size of control data.

        :param mode: '1G' or '10G'
        :param channel_payload_length: SPEAD payload length for
            integrated channel data
        :param beam_payload_length: SPEAD payload length for integrated
            beam data
        :param dst_ip: Destination IP, defaults to None
        :param src_port: source port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        :param netmask_40g: netmask of the 40g subnet
        :param gateway_40g: IP address of the 40g subnet gateway, if it exists.
        """
        self.logger.debug("TileComponentManager: set_lmc_integrated_download")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.set_lmc_integrated_download(
                    mode,
                    channel_payload_length,
                    beam_payload_length,
                    dst_ip,
                    src_port,
                    dst_port,
                    netmask_40g=netmask_40g,
                    gateway_ip_40g=gateway_40g,
                )
                self.integrated_data_transmission_mode = mode
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    @check_communicating
    def stop_integrated_data(self: TileComponentManager) -> None:
        """Stop the integrated data."""
        self.logger.debug("TileComponentManager: Stop integrated data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.stop_integrated_data()
                self.integrated_data_transmission_mode = "Not transmitting"
                time.sleep(0.2)
                self._pending_data_requests = self.tile.check_pending_data_requests()

            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    def stop_data_transmission(self: TileComponentManager) -> None:
        """Stop data transmission for send_channelised_data_continuous."""
        self.logger.debug("TileComponentManager: stop_data_transmission")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.stop_data_transmission()
                self.data_transmission_mode = "Not transmitting"
                time.sleep(0.2)
                self._pending_data_requests = self.tile.check_pending_data_requests()
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    @check_communicating
    def send_data_samples(  # pylint: disable=too-many-branches
        self: TileComponentManager,
        data_type: str = "",
        start_time: Optional[str] = None,
        seconds: float = 0.2,
        n_samples: int = 1024,
        sync: bool = False,
        first_channel: int = 0,
        last_channel: int = 511,
        channel_id: int = 128,
        frequency: float = 100.0,
        round_bits: int = 3,
        **params: Any,
    ) -> None:
        """
        Front end for send_xxx_data methods.

        :param data_type: sample type. "raw", "channel", "channel_continuous",
                "narrowband", "beam"
        :param start_time: UTC Time for start sending data. Default start now
        :param seconds: Delay if timestamp is not specified. Default 0.2 seconds
        :param n_samples: number of samples to send per packet
        :param sync: (raw) send synchronised antenna samples, vs. round robin
        :param first_channel: (channel) first channel to send, default 0
        :param last_channel: (channel) last channel to send, default 511
        :param channel_id: (channel_continuous) channel to send
        :param frequency: (narrowband) Sky frequency for band centre, in Hz
        :param round_bits: (narrowband) how many bits to round
        :param params: any additional keyword arguments

        :raises ValueError: error in time specification
        """
        self.logger.debug(f"send_data_samples: {data_type}")
        # Check if another operation is pending. Wait at most 0.2 seconds
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            if self.tile.check_pending_data_requests():
                time.sleep(0.2)
                if self.tile.check_pending_data_requests():
                    self.logger.error("Another send operation is active")
                    raise ValueError("Cannot send data, another send operation active")
        # Check for type of data to be sent to LMC
        if start_time is None:
            timestamp = 0
            seconds = params.get("seconds", 0.2)
        elif self.formatted_fpga_reference_time == 0:
            self.logger.error("Cannot send data, acquisition not started")
            raise ValueError("Cannot send data, acquisition not started")
        else:
            timestamp = self.frame_from_utc_time(start_time)
            if timestamp < 0:
                self.logger.error(f"Invalid time: {start_time}")
                raise ValueError(f"Invalid time: {start_time}")
            seconds = 0.0

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
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: send_raw_data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.send_raw_data(sync=sync, timestamp=timestamp, seconds=seconds)

    def _send_channelised_data(
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: send_channelised_data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.send_channelised_data(
                number_of_samples=number_of_samples,
                first_channel=first_channel,
                last_channel=last_channel,
                timestamp=timestamp,
                seconds=seconds,
            )

    def _send_channelised_data_continuous(
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: send_channelised_data_continuous")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.send_channelised_data_continuous(
                channel_id,
                number_of_samples=number_of_samples,
                wait_seconds=wait_seconds,
                timestamp=timestamp,
                seconds=seconds,
            )

    def _send_channelised_data_narrowband(
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: send_channelised_data_narrowband")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.send_channelised_data_narrowband(
                frequency,
                round_bits,
                number_of_samples,
                wait_seconds,
                timestamp,
                seconds,
            )

    def _send_beam_data(
        self: TileComponentManager,
        timestamp: Optional[int] = None,
        seconds: float = 0.2,
    ) -> None:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2
        """
        self.logger.debug("TileComponentManager: send_beam_data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.send_beam_data(timestamp=timestamp, seconds=seconds)

    @check_communicating
    def configure_integrated_beam_data(
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: configure_integrated_beam_data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.configure_integrated_beam_data(
                    integration_time, first_channel, last_channel
                )
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    @check_communicating
    def configure_integrated_channel_data(
        self: TileComponentManager,
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
        self.logger.debug("TileComponentManager: configure_integrated_channel_data")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.configure_integrated_channel_data(
                    integration_time, first_channel, last_channel
                )
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    def stop_beamformer(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        channel_groups: Optional[list[int]] = None,
    ) -> tuple[TaskStatus, str] | None:
        """
        Stop the beamformer.

        :param task_callback: Update task state, defaults to None
        :param channel_groups: Channel groups to be started
                Command affects only beamformed channels for given groups
                Default: all channels

        :return: A tuple containing a task status and a unique id string to

        """
        if channel_groups is None:
            self.logger.info("stop_beamformer: stopping all beams")

        return self._submit_lrc_request(
            command_name="stop_beamformer",
            command_object=self.tile.stop_beamformer,
            task_callback=task_callback,
            channel_groups=channel_groups,
        )

    @check_communicating
    def start_beamformer(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        start_time: Optional[str] = None,
        duration: int = -1,
        channel_groups: Optional[list[int]] = None,
        scan_id: int = 0,
    ) -> tuple[TaskStatus, str] | None:
        """
        Start beamforming on a specific subset of the beamformed channels.

        Current firmware version does not support channel mask and scan ID,
        these are ignored

        :param task_callback: Update task state, defaults to None
        :param start_time: Start time as ISO formatted time
        :param duration: Scan duration, in frames, default "forever"
        :param channel_groups: Channel groups to be started
                Command affects only beamformed channels for given groups
                Default: all channels
        :param scan_id: ID of the scan to be started. Default 0

        :raises ValueError: invalid time specified

        :returns: A tuple containing a task status and a unique id string to
            identify the command
        """
        if start_time is None:
            start_frame: int = 0
        elif isinstance(start_time, int):  # added for backward compatibility
            start_frame = start_time
        else:
            start_frame = self.frame_from_utc_time(start_time)
            if start_frame < 0:
                self.logger.error(f"start_beamformer: Invalid time {start_time}")
                raise ValueError(f"Invalid time {start_time}")
            if (start_frame - self.fpga_current_frame) < 20:
                self.logger.error("start_beamformer: time not enough in the future")
                raise ValueError("Time too early")

        if channel_groups is None:
            self.logger.info("start_beamformer: starting all beams")
        # if scan_id != 0:
        #    self.logger.warning("start_beamformer: scan ID value ignored")

        return self._submit_lrc_request(
            command_name="start_beamformer",
            command_object=self.tile.start_beamformer,
            task_callback=task_callback,
            start_time=start_frame,
            duration=duration,
            scan_id=scan_id,
            channel_groups=channel_groups,
        )

    @check_communicating
    def apply_pointing_delays(self: TileComponentManager, load_time: str = "") -> None:
        """
        Load the pointing delays at the specified time delay.

        :param load_time: switch time as ISO formatted time

        :raises ValueError: invalid time
        """
        if load_time == "":
            load_frame = 0
        elif isinstance(load_time, int):  # added for backward compatibility
            load_frame = load_time
        else:
            load_frame = self._tile_time.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error(f"apply_pointing_delays: Invalid time {load_time}")
                raise ValueError(f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "apply_pointing_delays: time not enough in the future"
                )
                raise ValueError("Time too early")

        self.logger.debug("TileComponentManager: load_pointing_delay")
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            try:
                self.tile.load_pointing_delay(load_frame)
            # pylint: disable=broad-except
            except Exception as e:
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")

    @check_communicating
    def load_pointing_delays(
        self: TileComponentManager, delay_array: list[list[float]], beam_index: int
    ) -> None:
        """
        Specify the delay in seconds and the delay rate in seconds/second.

        The delay_array specifies the delay and delay rate for each antenna. beam_index
        specifies which beam is desired (range 0-7)

        :param delay_array: delay in seconds, and delay rate in seconds/second
        :param beam_index: the beam to which the pointing delay should
            be applied
        """
        self.logger.debug("TileComponentManager: load_pointing_delays")
        nof_items = len(delay_array)
        self.logger.debug(f"Beam: {beam_index} delays: {delay_array}")
        self.last_pointing_delays = delay_array
        # 16 values required (16 antennas). Fill with zeros if less are specified
        if nof_items < 16:
            delay_array.extend([[0.0, 0.0]] * (16 - nof_items))
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self.tile.set_pointing_delay(delay_array, beam_index)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @check_communicating
    def apply_calibration(
        self: TileComponentManager, load_time: str = ""
    ) -> tuple[ResultCode, str]:
        """
        Load the calibration coefficients at the specified time delay.

        :param load_time: switch time as ISO formatted time

        :return: Result code and message.
        """
        if load_time == "":
            load_frame = 0
        elif isinstance(load_time, int):  # added for backward compatibility
            load_frame = load_time
        else:
            load_frame = self._tile_time.frame_from_utc_time(load_time)
            if load_frame < 0:
                return (ResultCode.REJECTED, f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                return (ResultCode.REJECTED, "Time too early")

        self.logger.debug("TileComponentManager: switch_calibration_bank")
        with acquire_timeout(self._hardware_lock, timeout=2) as acquired:
            if acquired:
                try:
                    self.tile.switch_calibration_bank(switch_time=load_frame)
                # pylint: disable=broad-except
                except Exception as e:
                    return (
                        ResultCode.FAILED,
                        f"TileComponentManager: Tile access failed: {e}",
                    )
            else:
                return (ResultCode.FAILED, "Failed to acquire hardware lock")

        return (ResultCode.OK, "ApplyCalibration command completed OK")

    def load_calibration_coefficients(
        self: TileComponentManager,
        antenna: int,
        calibration_coefficients: list[list[complex]],
    ) -> tuple[ResultCode, str]:
        """
        Load calibration coefficients.

        These may include any rotation matrix (e.g. the
        parallactic angle), but do not include the geometric delay.

        :param antenna: the antenna to which the coefficients apply
        :param calibration_coefficients: a bidirectional complex array of
            coefficients, flattened into a list

        :return: Result code and message.
        """
        self.logger.debug("TileComponentManager: load_calibration_coefficients")
        with acquire_timeout(self._hardware_lock, timeout=2) as acquired:
            if acquired:
                try:
                    self.tile.load_calibration_coefficients(
                        antenna, calibration_coefficients
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    return (
                        ResultCode.FAILED,
                        f"TileComponentManager: Tile access failed: {e}",
                    )
            else:
                return (ResultCode.FAILED, "Failed to acquire hardware lock")

        return (ResultCode.OK, "LoadCalibrationCoefficents command completed OK")

    def initialise_beamformer(
        self: TileComponentManager,
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

        :raises ValueError: if the tpm is value None.
        """
        self.logger.debug(
            f"initialise_beamformer for chans {start_channel}:{nof_channels}"
        )
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if self.tile.tpm is None:
                        raise ValueError("Cannot read register on unconnected TPM.")
                    self.tile.set_spead_format(self._csp_spead_format == "SKA")
                    self.tile.define_channel_table(
                        [[start_channel, nof_channels, 0, 0, 0, 0, 0, 0]]
                    )
                    self.tile.set_first_last_tile(is_first, is_last)
                    self._nof_blocks = nof_channels // 8
                    beamformer_table = self.tile.get_beamformer_table()
                    self._update_attribute_callback(beamformer_table=beamformer_table)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def set_beamformer_regions(
        self: TileComponentManager, regions: list[list[int]]
    ) -> None:
        """
        Set the frequency regions to be beamformed into a single beam.

        The input list contains up to 48 blocks which represent
        at most 16 contiguous channel regions.
        Each block has 8 entries which represent:
        - starting physical channel
        - number of channels
        - hardware beam number
        - subarray ID
        - subarray logical channel
        - subarray beam ID
        - substation ID

        :param regions: a list encoding up to 48 regions

        :raises ValueError: if the tpm is value None.
        """
        self.logger.debug("TileComponentManager: set_beamformer_regions")
        # TODO: Remove when interface with station beamformer allows multiple
        # subarrays, stations and apertures
        subarray_id = 0
        aperture_id = 0
        # substation_id = 0
        # changed = False
        if len(regions[0]) == 8:
            subarray_id = regions[0][3]
            aperture_id = regions[0][7]
        collapsed_regions = self._collapse_regions(regions)
        nof_blocks = 0
        for region in collapsed_regions:
            nof_blocks += region[1] // 8
        self._nof_blocks = nof_blocks
        self.logger.info(f"Setting beamformer table for {self._nof_blocks} blocks")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if nof_blocks > 0:
                        self.tile.set_beamformer_regions(collapsed_regions)
                    else:
                        self.logger.error("No valid beamformer regions specified")
                    if self.tile.tpm is None:
                        raise ValueError("Cannot read register on unconnected TPM.")
                    beamformer_table = self.tile.get_beamformer_table()
                    self._update_attribute_callback(beamformer_table=beamformer_table)
                    self.tile.define_spead_header(
                        station_id=self._station_id,
                        subarray_id=subarray_id,
                        nof_antennas=aperture_id,
                        ref_epoch=self._fpga_reference_time,
                        ska_spead_header_format=self._csp_spead_format == "SKA",
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def _collapse_regions(
        self: TileComponentManager, regions: list[list[int]]
    ) -> list[list[int]]:
        """
        Collapse the frequency regions if they are contiguous.

        This is temporarily required as the tile beamformer accepts at most
        16 regions and the current allocation/configuration structure
        allocates individually 48 blocks of 8 channels.
        TODO The function is not required anymore when the tile beamformer
        firmware will accept 48 individual channel blocks.

        The input list contains up to 48 blocks which represent
        at most 16 contiguous channel regions.
        Each block has 8 entries which represent:
        - starting physical channel
        - number of channels
        - hardware beam number
        - subarray ID
        - subarray logical channel
        - subarray beam ID
        - substation ID
        - aperture ID
        Output blocks (up to 16) describe the same information but with
        contiguous blocks collapsed together.

        :param regions: a list encoding up to 48 blocks for up to 16 regions

        :return: a list encoding up to 16 regions
        """
        region_collapsed = []
        old_region = [0] * 8
        for region in regions:
            # find if the new record continues the previous one
            if (
                region[0] > 0
                and region[0] == (old_region[0] + old_region[1])
                and region[1] > 0
                and region[2] == old_region[2]
                and region[4] == (old_region[4] + old_region[1])
            ):
                old_region[1] += region[1]
            else:  # not a continuation.
                if old_region[0] > 0:
                    region_collapsed.append(old_region)
                old_region = region
        # append last incomplete region if it exists
        if old_region[0] > 0:
            region_collapsed.append(old_region)
        return region_collapsed

    @property
    @check_communicating
    def csp_rounding(self: TileComponentManager) -> list[int]:
        """
        Read the cached value for the final rounding in the CSP samples.

        Need to be specfied only for the last tile
        :return: Final rounding for the CSP samples. Up to 384 values
        """
        return self._csp_rounding.tolist()

    @csp_rounding.setter
    def csp_rounding(self: TileComponentManager, rounding: np.ndarray | int) -> None:
        """
        Set the final rounding in the CSP samples, one value per beamformer channel.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        """
        if isinstance(rounding, int):
            desired_csp_rounding = np.array([rounding] * 384)
        elif len(rounding) == 1:
            desired_csp_rounding = np.array([rounding[0]] * 384)
        else:
            desired_csp_rounding = np.array(rounding)
        self._set_csp_rounding(desired_csp_rounding)

    def _set_csp_rounding(self: TileComponentManager, rounding: np.ndarray) -> None:
        """
        Set output rounding for CSP.

        :param rounding: Number of bits rounded in final 8 bit requantization to CSP
        """
        self.logger.debug("TileComponentManager: set_csp_rounding")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    write_successful = self.tile.set_csp_rounding(rounding[0])
                    if write_successful:
                        self._csp_rounding = rounding
                        self._update_attribute_callback(
                            csp_rounding=self._csp_rounding.tolist()
                        )
                    else:
                        self.logger.warning("Setting the cspRounding failed ")

                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @check_communicating
    def get_static_delays(self: TileComponentManager) -> list[float]:
        """
        Read the cached value for the static delays, in sample.

        :return: static delay, in nanoseconds one per TPM input
        """
        delays = []
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
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
                self.logger.warning(f"TileComponentManager: Tile access failed: {e}")
        return delays

    def set_static_delays(self: TileComponentManager, delays: list[float]) -> None:
        """
        Set the static delays.

        :param delays: Static zenith delays, one per input channel,
            in nanoseconds, nominal = 0, positive delay adds
            delay to the signal stream
        """
        self.logger.debug("TileComponentManager: set_static_delays")
        delays_float = [float(d) for d in delays]
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if not self.tile.set_time_delays(delays_float):
                        self.logger.warning("Failed to set static time delays.")
                    static_delays = self.get_static_delays()
                    self._update_attribute_callback(static_delays=static_delays)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @property
    @check_communicating
    def channeliser_truncation(self: TileComponentManager) -> Optional[list[int]]:
        """
        Read the cached value for the channeliser truncation.

        :return: cached value for the channeliser truncation
        """
        return list(self._channeliser_truncation)

    @channeliser_truncation.setter
    def channeliser_truncation(
        self: TileComponentManager, truncation: int | list[int]
    ) -> None:
        """
        Set the channeliser truncation.

        :param truncation: number of LS bits discarded after channelisation.
            Either a signle value or a list of one value per physical frequency channel
            0 means no bits discarded, up to 7. 3 is the correct value for a uniform
            white noise.
        """
        if isinstance(truncation, int):
            self._channeliser_truncation = [truncation] * 512

        elif len(truncation) == 1:
            self._channeliser_truncation = [truncation[0]] * 512
        else:
            if isinstance(truncation, np.ndarray):
                self._channeliser_truncation = truncation.tolist()
            else:
                self._channeliser_truncation = list(truncation)
        self._set_channeliser_truncation(self._channeliser_truncation)

    def _set_channeliser_truncation(
        self: TileComponentManager, array: list[int]
    ) -> None:
        """
        Set the channeliser coefficients to modify the bandpass.

        :param array: list with M values, one for each of the
            frequency channels. Same truncation is applied to the corresponding
            frequency channels in all inputs.
        """
        self.logger.debug(
            f"TileComponentManager: set_channeliser_truncation: {array[0]}"
        )
        nb_freq = len(array)
        trunc = [0] * 512
        trunc[0:nb_freq] = array
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                for chan in range(32):
                    try:
                        self.tile.set_channeliser_truncation(trunc, chan)
                        self._update_attribute_callback(
                            channeliser_rounding=list(trunc)
                        )
                    # pylint: disable=broad-except
                    except Exception as e:
                        self.logger.warning(
                            f"TileComponentManager: Tile access failed: {e}"
                        )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    @check_communicating
    def set_lmc_download(
        self: TileComponentManager,
        mode: str,
        payload_length: int = 1024,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = 0xF0D0,
        dst_port: Optional[int] = 4660,
        netmask_40g: int | None = None,
        gateway_40g: int | None = None,
    ) -> None:
        """
        Specify whether control data will be transmitted over 1G or 40G networks.

        :param mode: "1G" or "10G"
        :param payload_length: SPEAD payload length for integrated
            channel data, defaults to 1024
        :param dst_ip: destination IP, defaults to None
        :param src_port: sourced port, defaults to 0xF0D0
        :param dst_port: destination port, defaults to 4660
        :param netmask_40g: netmask of the 40g subnet
        :param gateway_40g: IP address of the 40g subnet gateway, if it exists.
        """
        self.logger.debug("TileComponentManager: set_lmc_download")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self.tile.set_lmc_download(
                        mode,
                        payload_length,
                        dst_ip,
                        src_port,
                        dst_port,
                        netmask_40g=netmask_40g,
                        gateway_ip_40g=gateway_40g,
                    )
                    self.data_transmission_mode = mode
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def get_40g_configuration(
        self: TileComponentManager, core_id: int = -1, arp_table_entry: int = 0
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
            f"get_40g_configuration: core:{core_id} entry:{arp_table_entry}"
        )
        self._forty_gb_core_list = []
        if core_id == -1 or core_id is None:
            for icore in range(2):
                for arp_table_entry_id in range(4):
                    dict_to_append = self._get_40g_core_configuration(
                        icore, arp_table_entry_id
                    )
                    if dict_to_append is not None:
                        self._forty_gb_core_list.append(dict_to_append)
        else:
            if self._get_40g_core_configuration(core_id, arp_table_entry):
                self._forty_gb_core_list = [
                    self._get_40g_core_configuration(core_id, arp_table_entry)
                ]
        # convert in more readable format
        for core in self._forty_gb_core_list:
            self.logger.info(f"{core}")
            core["src_ip"] = str(ipaddress.IPv4Address(core["src_ip"]))
            core["dst_ip"] = str(ipaddress.IPv4Address(core["dst_ip"]))
        return self._forty_gb_core_list

    def _get_40g_core_configuration(
        self: TileComponentManager, core_id: int, arp_table_entry: int
    ) -> dict[str, Any] | list[dict] | None:
        """
        Return a 40G configuration.

        :param core_id: id of the core for which a configuration is to
            be return. Defaults to -1, in which case all cores
            configurations are returned
        :param arp_table_entry: ARP table entry to use

        :return: core configuration or list of core configurations
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_40g_core_configuration(
                core_id,
                arp_table_entry,
            )

    def configure_40g_core(
        self: TileComponentManager,
        core_id: int = 0,
        arp_table_entry: int = 0,
        source_mac: Optional[int] = None,
        source_ip: Optional[str] = None,
        source_port: Optional[int] = None,
        destination_ip: Optional[str] = None,
        destination_port: Optional[int] = None,
        rx_port_filter: Optional[int] = None,
        netmask: Optional[int] = None,
        gateway_ip: Optional[int] = None,
    ) -> None:
        """
        Configure the 40G code.

        :param core_id: id of the core
        :param arp_table_entry: ARP table entry to use
        :param source_mac: MAC address of the source
        :param source_ip: IP address of the source
        :param source_port: port of the source
        :param destination_ip: IP address of the destination
        :param destination_port: port of the destination
        :param rx_port_filter: Filter for incoming packets
        :param netmask: Netmask
        :param gateway_ip: Gateway IP
        """
        self.logger.debug("TileComponentManager: configure_40g_core")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self.tile.configure_40g_core(
                        core_id,
                        arp_table_entry,
                        source_mac,
                        source_ip,
                        source_port,
                        destination_ip,
                        destination_port,
                        rx_port_filter,
                        netmask,
                        gateway_ip,
                    )
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def write_address(
        self: TileComponentManager, address: int, values: list[int]
    ) -> None:
        """
        Write a list of values to a given address.

        :param address: address of start of read
        :param values: values to write
        """
        current_address = int(address & 0xFFFFFFFC)
        if isinstance(values, int):
            values = [values]
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self.tile.write_address(current_address, values)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(f"TileComponentManager: Tile access failed {e}")
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def read_register(self: TileComponentManager, register_name: str) -> list[int]:
        """
        Read the values in a named register.

        :param register_name: name of the register

        :return: values read from the register

        :raises ValueError: if the tpm is value None.
        """
        if self.tile.tpm is None:
            raise ValueError("Cannot read register on unconnected TPM.")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if len(self.tile.find_register(register_name)) == 0:
                        self.logger.error(
                            "Register '" + register_name + "' not present"
                        )
                        return []
                    value = self.tile.read_register(register_name)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
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
        self: TileComponentManager, register_name: str, values: list[Any] | int
    ) -> None:
        """
        Read the values in a register.

        :param register_name: name of the register
        :param values: values to write

        :raises ValueError: if the tpm is value None.
        """
        if isinstance(values, int):
            values = [values]
        devname = ""
        regname = devname + register_name
        if self.tile.tpm is None:
            raise ValueError("Cannot read register on unconnected TPM.")
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if len(self.tile.find_register(regname)) == 0:
                        self.logger.error("Register '" + regname + "' not present")
                        return
                    self.tile.write_register(register_name, values)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

    def read_address(
        self: TileComponentManager, address: int, nvalues: int
    ) -> list[int]:
        """
        Return a list of values from a given address.

        :param address: address of start of read
        :param nvalues: number of values to read

        :return: values at the address
        """
        values = []
        current_address = int(address & 0xFFFFFFFC)
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                self.logger.info(
                    "Reading address "
                    + str(current_address)
                    + "of type "
                    + str(type(current_address))
                )
                try:
                    values = self.tile.read_address(current_address, nvalues)
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")

        return values

    def _get_pps_delay_correction(self: TileComponentManager) -> Optional[int]:
        """
        Return last measured ppsdelay correction.

        :return: PPS delay correction. Units: 1.25 ns
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            return self.tile.get_pps_delay(
                enable_correction=True
            ) - self.tile.get_pps_delay(enable_correction=False)

    def _get_pps_drift(self: TileComponentManager) -> int:
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            if self._initial_pps_delay is None:
                self._initial_pps_delay = self.tile.get_pps_delay()
            return self.tile.get_pps_delay() - self._initial_pps_delay

    def set_preadu_levels(self: TileComponentManager, levels: list[float]) -> None:
        """
        Set preadu levels in dB.

        :param levels: Preadu attenuation levels in dB

        :raises ValueError: When attempting to set preaduLevels with
            a list of length not equal to 32 (i.e 32 ADC channels).
        :raises HardwareVerificationError: When the readback from hardware is
            unexpected.
        """
        if len(levels) != 32:
            raise ValueError(
                f"length must be 32. Attempting to set with length {len(levels)}"
            )

        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.set_preadu_levels(levels)
            _preadu_levels = self.tile.get_preadu_levels()

        self._update_attribute_callback(preadu_levels=_preadu_levels)

        if _preadu_levels != levels:
            raise HardwareVerificationError(expected=levels, actual=_preadu_levels)

    def set_phase_terminal_count(self: TileComponentManager, value: int) -> None:
        """
        Set the phase terminal count.

        :param value: the phase terminal count
        """
        with acquire_timeout(self._hardware_lock, timeout=0.8, raise_exception=True):
            self.tile.set_phase_terminal_count(value)
            read_value = self.tile.get_phase_terminal_count()
            self._update_attribute_callback(phase_terminal_count=read_value)

    @property
    @check_communicating
    def is_beamformer_running(self: TileComponentManager) -> Optional[bool]:
        """
        Check if the beamformer is running.

        :return: True if the beamformer is running
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.beamformer_is_running()

    @check_communicating
    def beamformer_running_for_channels(
        self: TileComponentManager,
        channel_groups: list[int] | None,
    ) -> bool:
        """
        Check if the beamformer is running in a list of channel blocks.

        :param channel_groups: List of channel blocks to check

        :return: True if the beamformer is running
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.beamformer_is_running(channel_groups=channel_groups)

    @property
    @check_communicating
    def running_beams(self: TileComponentManager) -> list[bool]:
        """
        List hardware beams currently running.

        :return: list of hardware beam running states
        """
        subarray_beams = [False] * 48
        # if self.tpm_status != TpmStatus.INITIALISED:
        #     return subarray_beams
        for beam in range(48):
            with acquire_timeout(
                self._hardware_lock,
                timeout=self._default_lock_timeout,
                raise_exception=True,
            ):
                subarray_beams[beam] = self.tile.beamformer_is_running(beam=beam)
        return subarray_beams

    @property
    @check_communicating
    def arp_table(self: TileComponentManager) -> Optional[dict[int, list[int]]]:
        """
        Check that ARP table has been populated in for all used cores 40G interfaces.

        Use cores 0 (fpga0) and 1(fpga1) and ARP ID 0 for beamformer, 1 for LMC 10G
        interfaces use cores 0,1 (fpga0) and 4,5 (fpga1) for beamforming, and 2, 6 for
        LMC with only one ARP.

        :return: list of core id and arp table populated
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_arp_table()

    @property
    @check_communicating
    def pending_data_requests(self: TileComponentManager) -> Optional[bool]:
        """
        Check for pending data requests.

        :return: whether there are pending send data requests
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.check_pending_data_requests()

    @property
    @check_communicating
    def pps_present(self: TileComponentManager) -> bool:
        """
        Check if PPS signal is present.

        :return: True if PPS is present. Checked in poll loop, cached
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["timing"]["pps"]["status"]

    @property
    @check_communicating
    def voltage_mon(self: TileComponentManager) -> float:
        """
        Return the internal 5V supply of the TPM.

        :return: the internal 5V supply of the TPM
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["voltages"]["MON_5V0"]

    @property
    @check_communicating
    def flagged_packets(self: TileComponentManager) -> dict:
        """
        Return the total number of flagged packets by the TPM.

        :return: the total number of flagged packets by the TPM
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["dsp"]["station_beamf"][
                "discarded_or_flagged_packet_count"
            ]

    @property
    @check_communicating
    def data_router_status(self: TileComponentManager) -> dict:
        """
        Return the data router values.

        :return: The status of both FPGAs
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["io"]["data_router"]

    @property
    @check_communicating
    def data_router_discarded_packets(self: TileComponentManager) -> dict:
        """
        Return the data router values.

        :return: The number of discarded packets
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["io"]["data_router"]

    @property
    @check_communicating
    def fpga1_temperature(self: TileComponentManager) -> float:
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["temperatures"]["FPGA0"]

    @property
    @check_communicating
    def fpga2_temperature(self: TileComponentManager) -> float:
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["temperatures"]["FPGA1"]

    @property
    @check_communicating
    def board_temperature(self: TileComponentManager) -> float:
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["temperatures"]["board"]

    @property
    @check_communicating
    def adcs(self: TileComponentManager) -> dict[str, Any]:
        """
        Return the ADC status in the TPM.

        :return: ADC status in the TPM
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["adcs"]

    @property
    @check_communicating
    def alarms(self: TileComponentManager) -> dict[str, Any]:
        """
        Return the alarms status in the TPM.

        :return: alarms status in the TPM
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.get_health_status()["alarms"]

    @property
    def is_programmed(self: TileComponentManager) -> bool:
        """
        Return whether this TPM is programmed (i.e. firmware has been downloaded to it).

        :return: whether this TPM is programmed
        """
        if not self.tile:  # Tile unconnected
            return False
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            return self.tile.is_programmed()

    @check_communicating
    def set_tpm_temperature_thresholds(
        self: TileComponentManager,
        board_alarm_threshold: tuple[float, float] | None = None,
        fpga1_alarm_threshold: tuple[float, float] | None = None,
        fpga2_alarm_threshold: tuple[float, float] | None = None,
    ) -> tuple[ResultCode, str]:
        """
        Set the temperature thresholds.

        NOTE: Warning this method can configure the shutdown temperature of
        components and must be used with care. This method is capped to a minimum
        of 20 and maximum of 50 (unit: Degree Celsius). And is ONLY supported in tpm1_6.

        :param board_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the board (unit: Degree Celsius)
        :param fpga1_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the fpga1 (unit: Degree Celsius)
        :param fpga2_alarm_threshold: A tuple containing the minimum and
            maximum alarm thresholds for the fpga2 (unit: Degree Celsius)

        :return: a tuple containing a ``ResultCode`` and string with information about
            the execution outcome.
        """
        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    self.tile.set_tpm_temperature_thresholds(
                        board_alarm_threshold=board_alarm_threshold,
                        fpga1_alarm_threshold=fpga1_alarm_threshold,
                        fpga2_alarm_threshold=fpga2_alarm_threshold,
                    )
                except ValueError as ve:
                    value_error_message = (
                        f"Failed to set the tpm temperature thresholds {ve}"
                    )
                    self.logger.error(value_error_message)
                    return (ResultCode.FAILED, value_error_message)
                except Exception as e:  # pylint: disable=broad-except
                    message = f"Unexpected exception raised {repr(e)}"
                    self.logger.error(message)
                    return (ResultCode.FAILED, message)

            else:
                lock_failed_message = (
                    "Failed to acquire lock for set_tpm_temperature_thresholds."
                )
                self.logger.warning(lock_failed_message)
                return (ResultCode.FAILED, lock_failed_message)

        return (ResultCode.OK, "Command executed.")

    # -----------------------------
    # Test generator methods
    # -----------------------------
    # pylint: disable=too-many-arguments
    @check_communicating
    def configure_test_generator(
        self: TileComponentManager,
        frequency0: float,
        amplitude0: float,
        frequency1: float,
        amplitude1: float,
        amplitude_noise: float,
        pulse_code: int,
        amplitude_pulse: float,
        delays: list[float] | None = None,
        load_time: Optional[str] = None,
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
        :param delays: delays to load into the test generator, list of 32 floats.
        :param load_time: Time to start the generator. in UTC ISO formatted string.

        :raises ValueError: invalid time specified
        :raises ValueError: if the tpm is value None.
        """
        if load_time is None:
            load_frame = 0
        else:
            load_frame = self.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error("configure_test_generator: Invalid time")
                raise ValueError("Invalid time")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "configure_test_generator: time not enough in the future"
                )
                raise ValueError("Time too early")

        self.logger.info(
            "Test generator: set tone 0: "
            + str(frequency0)
            + " Hz"
            + ", tone 1: "
            + str(frequency1)
            + " Hz"
        )
        # If load time not specified, is "now" + 30 ms
        end_time: int = 0
        if load_frame == 0:
            with acquire_timeout(
                self._hardware_lock,
                timeout=self._default_lock_timeout,
                raise_exception=True,
            ):
                load_frame = self.tile.get_fpga_timestamp() + 180
            self.logger.info(f"Tile generator uses asynchronous timestamp {load_frame}")
        else:
            self.logger.info(f"Test generator load time: {load_frame}")

        with acquire_timeout(
            self._hardware_lock, timeout=self._default_lock_timeout
        ) as acquired:
            if acquired:
                try:
                    if self.tile.tpm is None:
                        raise ValueError("Cannot read register on unconnected TPM.")
                    # Set everything at same time
                    self.tile.test_generator_set_tone(
                        0, frequency0, amplitude0, 0.0, load_frame
                    )
                    self.tile.test_generator_set_tone(
                        1, frequency1, amplitude1, 0.0, load_frame
                    )
                    self.tile.test_generator_set_noise(amplitude_noise, load_frame)
                    self.tile.set_test_generator_pulse(pulse_code, amplitude_pulse)
                    if delays is not None:
                        self.tile.test_generator_set_delay(delays)
                    self.tile["fpga1.test_generator.control.load_dds0"] = 1
                    self.tile["fpga2.test_generator.control.load_dds0"] = 1
                    end_time = self.tile.get_fpga_timestamp()
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.warning(
                        f"TileComponentManager: Tile access failed: {e}"
                    )
            else:
                self.logger.warning("Failed to acquire hardware lock")
        self.logger.info(f"Time after programming: {end_time}")
        if end_time > load_frame:
            self.logger.warning("Test generator failed to program before start time")

    def test_generator_input_select(
        self: TileComponentManager, inputs: int = 0
    ) -> None:
        """
        Specify ADC inputs which are substitute to test signal.

        Specified using a 32 bit mask, with LSB for ADC input 0.

        :param inputs: Bit mask of inputs using test signal
        """
        self.logger.info("Test generator: set inputs " + hex(inputs))
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.test_generator_input_select(inputs)

    @property
    def test_generator_active(self: TileComponentManager) -> bool:
        """
        Check if the test generator is active.

        :return: whether the test generator is active
        """
        return self._test_generator_active

    @test_generator_active.setter  # type: ignore[no-redef]
    def test_generator_active(self: TileComponentManager, active: bool) -> None:
        """
        Set the test generator active flag.

        :param active: True if the generator has been activated
        """
        self._test_generator_active = active

    def configure_pattern_generator(
        self: TileComponentManager,
        stage: str,
        pattern: list[int],
        adders: list[int],
        start: bool = False,
        shift: int = 0,
        zero: int = 0,
        ramp1: dict[str, int] | None = None,
        ramp2: dict[str, int] | None = None,
    ) -> None:
        """
        Configure the TPM pattern generator.

        :param stage: The stage in the signal chain where the pattern is injected.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer) or 'all' for all stages.
        :param pattern: The data pattern in time order. This must be a list of integers
            with a length between 1 and 1024. The pattern represents values
            in time order (not antennas or polarizations).
        :param adders: A list of 32 integers that expands the pattern to cover 16
            antennas and 2 polarizations in hardware. This list maps the pattern to the
            corresponding signals for the antennas and polarizations.
        :param start: Boolean flag indicating whether to start the pattern immediately.
            If False, the pattern will need to be started manually later.
        :param shift: Optional bit shift (divides the pattern by 2^shift). This must not
            be used in the 'beamf' stage, where it is always overridden to 4.
            The default value is 0.
        :param zero: An integer (0-65535) used as a mask to disable the pattern on
            specific antennas and polarizations. The same mask is applied to both FPGAs,
            supporting up to 8 antennas and 2 polarizations. The default value is 0.
        :param ramp1: if defined a ramp will be applied for ramp1 after
            the pattern is set.
            A mandatory kwarg polarisation is used a configuration.
            This must be 0, 1 or -1 to use all stages.
        :param ramp2: if defined a ramp will be applied for ramp2 after
            the pattern is set.
            A mandatory kwarg polarisation is used a configuration.
            This must be 0, 1 or -1 to use all stages.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.set_pattern(stage, pattern, adders, start, shift, zero)

            if ramp1 is not None:
                self.tile.configure_ramp_pattern(
                    stage=stage, polarisation=ramp1["polarisation"], ramp="ramp1"
                )
            if ramp2 is not None:
                self.tile.configure_ramp_pattern(
                    stage=stage, polarisation=ramp2["polarisation"], ramp="ramp2"
                )

    def stop_pattern_generator(self: TileComponentManager, stage: str) -> None:
        """
        Stop the pattern generator.

        :param stage: The stage in the signal chain where the pattern was injected.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer) or 'all' for all stages.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.stop_pattern(stage)

    def start_pattern_generator(self: TileComponentManager, stage: str) -> None:
        """
        Start the pattern generator.

        :param stage: The stage in the signal chain where the pattern was injected.
            Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer),
            or 'beamf' (output of tile beamformer) or 'all' for all stages.
        """
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.start_pattern(stage)

    def start_adcs(self: TileComponentManager) -> None:
        """Start the ADCs."""
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.enable_all_adcs()

    def stop_adcs(self: TileComponentManager) -> None:
        """Stop the ADCs."""
        with acquire_timeout(
            self._hardware_lock,
            timeout=self._default_lock_timeout,
            raise_exception=True,
        ):
            self.tile.disable_all_adcs()

    def enable_station_beam_flagging(self: TileComponentManager) -> None:
        """Enable station beam flagging."""
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            self.tile.enable_station_beam_flagging()

    def disable_station_beam_flagging(self: TileComponentManager) -> None:
        """Disable station beam flagging."""
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            self.tile.disable_station_beam_flagging()

    @property
    @check_communicating
    def is_station_beam_flagging_enabled(self: TileComponentManager) -> list:
        """
        Return station beam data flagging state for each fpga.

        :return: a list of bool values corresponding to the fpgas
        """
        with acquire_timeout(
            self._hardware_lock, self._default_lock_timeout, raise_exception=True
        ):
            return self.tile.is_station_beam_flagging_enabled()
