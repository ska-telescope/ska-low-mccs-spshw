#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for tiles."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union, cast

import tango
from pyaavs.tile import Tile as Tile12
from pyaavs.tile_wrapper import Tile as HwTile
from pyfabil.base.definitions import BoardError, LibraryError
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    ResultCode,
    SimulationMode,
    TaskStatus,
    TestMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.component import MccsBaseComponentManager
from ska_low_mccs_common.component.command_proxy import MccsCommandProxy
from ska_tango_base.base import check_communicating, check_on
from ska_tango_base.poller import PollingComponentManager

from .base_tpm_simulator import BaseTpmSimulator
from .tile_poll_management import TileRequestProvider
from .tile_simulator import DynamicTileSimulator, TileSimulator
from .tpm_driver import TpmDriver
from .tpm_status import TpmStatus

__all__ = ["TileComponentManager", "TileRequest", "TileResponse"]


class TileRequest:
    """
    Class representing an action to be performed by a poll.

    This is initialised with a command object, args and kwargs and also a flag
    'publish' to represent if the result of this request should be published.
    """

    def __init__(
        self: TileRequest,
        name: str,
        command_object: Any,
        *args: Any,
        publish: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new request for execution in a poll.

        :param name: Name of the command to excute
        :param command_object: The object to call
        :param args: optional arguments to pass
        :param publish: Whether to publish the results of
            poll to the TANGO device on poll_success
        :param kwargs: Optional kwargs
        """
        self.name = name
        self.publish = publish
        self._command_object = command_object
        self._args = args
        self._kwargs = kwargs

    def abort(self: TileRequest) -> None:
        """Abort a Long running Command."""
        if "task_callback" in self._kwargs:
            self._kwargs["task_callback"](
                status=TaskStatus.ABORTED,
                result=(ResultCode.ABORTED, "Command aborted"),
            )

    def __call__(self: TileRequest) -> Any:
        """
        Execute the command object.

        If the command object is callable we will call it with args and kwargs
        else we will get the value.

        :return: the returned value from the command
        """
        if callable(self._command_object):
            result = self._command_object(*self._args, **self._kwargs)
        else:
            result = self._command_object
        return result


@dataclass
class TileResponse:
    """
    Class representing the result of a poll.

    It comprises the command name, the return data and a flag to represent
    if the result is to be published.
    """

    command: str | None
    data: Any
    publish: bool


# pylint: disable=too-many-instance-attributes, too-many-lines
class TileComponentManager(MccsBaseComponentManager, PollingComponentManager):
    """A component manager for a TPM (simulator or driver) and its power supply."""

    # pylint: disable=too-many-arguments
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
        subrack_fqdn: str,
        subrack_tpm_id: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        # tile_device_state_callback: Callable[..., None],
        _tpm_driver: Optional[Union[TpmDriver, BaseTpmSimulator]] = None,
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
        :param subrack_fqdn: FQDN of the subrack that controls power to
            this tile
        :param subrack_tpm_id: This tile's position in its subrack
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param _tpm_driver: a optional TpmDriver to inject for testing.
        """
        self._subrack_fqdn = subrack_fqdn
        self._subrack_says_tpm_power: PowerState = PowerState.UNKNOWN
        self._subrack_tpm_id = subrack_tpm_id
        self._power_state_lock = threading.RLock()
        self._subrack_proxy: Optional[MccsDeviceProxy] = None
        self._subrack_communication_state = CommunicationStatus.DISABLED
        self.power_state: PowerState = PowerState.UNKNOWN
        self._tpm_communication_state = CommunicationStatus.DISABLED
        self._simulation_mode = simulation_mode
        self._pps_delay_correction: int = 0
        if tpm_version not in ["tpm_v1_2", "tpm_v1_6"]:
            self.logger.warning(
                "TPM version "
                + tpm_version
                + " not valid. Trying to read version from board, which must be on"
            )
            tpm_version = ""
        self._request_provider: Optional[TileRequestProvider] = None
        if simulation_mode == SimulationMode.TRUE:
            if test_mode == TestMode.TEST:
                tile = TileSimulator(logger)
            else:
                tile = DynamicTileSimulator(logger)
        else:
            tile = cast(
                Tile12,
                HwTile(
                    ip=tpm_ip,
                    port=tpm_cpld_port,
                    logger=logger,
                    tpm_version=tpm_version,
                ),
            )

        self._tpm_driver = _tpm_driver or TpmDriver(
            logger,
            tile_id,
            station_id,
            tile,
            tpm_version,
            self._tpm_communication_state_changed,
            self._update_component_state,
        )

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            poll_rate=poll_rate,
            adc_rms=None,
            tile_health_structure=None,
            pll_locked=None,
            global_status_alarms=None,
            programming_state=TpmStatus.UNKNOWN.pretty_name(),
            pps_delay_corrected=0,
            pps_delay=None,
            csp_rounding=None,
            preadu_levels=None,
            static_delays=None,
            channeliser_rounding=None,
            # fndh_status=None,
        )

    def get_request(  # type: ignore[override]
        self: TileComponentManager,
    ) -> Optional[TileRequest]:
        """
        Return the action/s to be taken in the next poll.

        :raises AssertionError: if an unrecognosed poll option is
            returned by the provider

        :return: attributes to be read and commands to be executed in
            the next poll.
        """
        if not self._request_provider:
            raise AssertionError(
                "The request provider is None, unable to get next request"
            )
        self.logger.info(f"\n{'New Poll':-^20}")
        tpm_status: TpmStatus = self.tpm_status
        self.logger.info(f"Getting request for state {TpmStatus(tpm_status).name:-^40}")
        self._update_component_state(programming_state=tpm_status.pretty_name())

        request_spec = self._request_provider.get_request(tpm_status)

        # If already a request simply return.
        if isinstance(request_spec, TileRequest):
            return request_spec

        if request_spec is None:
            self.logger.warning("Request provider returned None.")
            return None

        match request_spec:
            case ("CHECK_CPLD_COMMS", None):
                self.logger.error("get check_global_status_alarms")
                request = TileRequest(
                    "global_status_alarms",
                    self._tpm_driver.check_global_status_alarms,
                    publish=True,
                )
            case ("CONNECT", None):
                error_flag = False
                try:
                    self._tpm_driver.ping()
                    # pylint: disable=broad-except
                except Exception as e:
                    # polling attempt was unsuccessful
                    self.logger.warning(f"Connection to tpm lost! : {e}")
                    error_flag = True
                if error_flag:
                    request = TileRequest("connect", self._tpm_driver.connect)
                else:
                    request = TileRequest(
                        "global_status_alarms",
                        self._tpm_driver.check_global_status_alarms,
                        publish=True,
                    )
            case ("IS_PROGRAMMED", request):
                request = TileRequest("is_programmed", self._tpm_driver.is_programmed)
            case ("HEALTH_STATUS", None):
                request = TileRequest(
                    "tile_health_structure",
                    self._tpm_driver.get_health_status,
                    publish=True,
                )
            case ("ADC_RMS", None):
                request = TileRequest("adc_rms", self._tpm_driver.adc_rms, publish=True)
            case ("PLL_LOCKED", None):
                request = TileRequest(
                    "pll_locked", self._tpm_driver.pll_locked, publish=True
                )
            case ("PENDING_DATA_REQUESTS", None):
                request = TileRequest(
                    "pending_data_requests",
                    self._tpm_driver.pending_data_requests,
                    publish=False,
                )
            case ("PPS_DELAY", None):
                request = TileRequest(
                    "pps_delay",
                    self._tpm_driver.pps_delay,
                    publish=True,
                )
            case ("PPS_DELAY_CORRECTION", None):
                request = TileRequest(
                    "pps_delay_corrected",
                    command_object=self._tpm_driver.pps_delay_correction,
                    publish=True,
                )
            case ("IS_BEAMFORMER_RUNNING", None):
                request = TileRequest(
                    "beamformer_running", self._tpm_driver.is_beamformer_running
                )
            case ("PHASE_TERMINAL_COUNT", None):
                request = TileRequest(
                    "phase_terminal_count",
                    self._tpm_driver.phase_terminal_count,
                )
            case ("PREADU_LEVELS", None):
                request = TileRequest(
                    "preadu_levels", self._tpm_driver.preadu_levels, publish=True
                )
            case ("STATIC_DELAYS", None):
                request = TileRequest(
                    "static_delays", self._tpm_driver.static_delays, publish=True
                )
            case ("STATION_ID", None):
                request = TileRequest("station_id", self._tpm_driver.get_station_id)
            case ("TILE_ID", None):
                request = TileRequest("tile_id", self._tpm_driver.tile_id)
            case ("CSP_ROUNDING", None):
                request = TileRequest(
                    "csp_rounding", self._tpm_driver.csp_rounding, publish=True
                )
            case ("CHANNELISER_ROUNDING", None):
                request = TileRequest(
                    "channeliser_rounding",
                    self._tpm_driver.channeliser_truncation,
                    publish=True,
                )
            case ("BEAMFORMER_TABLE", None):
                request = TileRequest(
                    "beamformer_table", self._tpm_driver.beamformer_table
                )
            case ("FPGA_REFERENCE_TIME", None):
                request = TileRequest(
                    "fpga_reference_time",
                    self._tpm_driver.formatted_fpga_reference_time,
                )

            case _:
                message = f"Unrecognised poll request {repr(request_spec)}"
                self.logger.error(message)
                raise AssertionError(message)
        return request

    def poll(self: TileComponentManager, poll_request: TileRequest) -> TileResponse:
        """
        Poll request for TpmDriver.

        Execute a command or read some values.

        :param poll_request: specification of the actions to be taken in
            this poll.

        :return: responses to queries in this poll
        """
        self.logger.info(f"Executing request {poll_request.name}")
        return TileResponse(poll_request.name, poll_request(), poll_request.publish)

    def poll_failed(self: TileComponentManager, exception: Exception) -> None:
        """
        Handle a failed poll.

        This is a hook called by the poller when an exception was raised during a
        poll.

        SUBRACK_SAY_TPM_UNKNOWN     ->  PowerState.UNKNOWN
        SUBRACK_SAY_TPM_OFF         ->  PowerState.OFF
        SUBRACK_SAY_TPM_ON          ->  PowerState.ON
        SUBRACK_SAY_TPM_NO_SUPPLY   ->  PowerState.NO_SUPPLY

        :param exception: exception code raised from poll.
        """
        self.logger.debug(f"Failed poll with exception : {exception}")

        self.power_state = self._subrack_says_tpm_power
        self._update_component_state(power=self._subrack_says_tpm_power)

        match exception:
            case ConnectionError():
                self.logger.warning(f"ConnectionError found {exception}")
            case LibraryError():
                self.logger.warning(
                    f"LibraryError raised from poll {exception}, "
                    "check the cpld communications"
                )
                if self._request_provider is not None:
                    # Check the connection
                    self._request_provider.desire_connection()
            case BoardError():
                # TODO: This could be a overheating of the FPGA??
                self.logger.error("BoardError: check global status alarms")
                if self._request_provider is not None:
                    # Check the connection
                    self._request_provider.desire_connection()
            case _:
                self.logger.error(f"Unexpected error found: {repr(exception)}")

    def poll_succeeded(self: TileComponentManager, poll_response: TileResponse) -> None:
        """
        Handle the receipt of new polling values.

        This is a hook called by the poller when values have been read
        during a poll.

        SUBRACK_SAY_TPM_UNKNOWN     ->  PowerState.ON
        SUBRACK_SAY_TPM_OFF         ->  PowerState.ON
        SUBRACK_SAY_TPM_ON          ->  PowerState.ON
        SUBRACK_SAY_TPM_NO_SUPPLY   ->  PowerState.ON

        :param poll_response: response to the pool, including any values
            read.
        """
        if self._subrack_says_tpm_power != PowerState.ON:
            # TODO: this should result in some ALARM or warning raised.
            # fault = True ? (inconsistent state)
            self.logger.error(
                "poll_success but subrack says power is "
                f"{PowerState(self._subrack_says_tpm_power).name}"
            )
        # We managed to poll hardware therefore we are PowerState.ON.
        # DevState and HealthState is to be determined by the attribute value reported
        self.power_state = PowerState.ON

        # Publish all responses to TANGO interface.
        if poll_response.publish:
            self._update_component_state(  # type: ignore[misc]
                **{poll_response.command: poll_response.data},
            )
        super().poll_succeeded(poll_response)
        self._update_component_state(power=PowerState.ON)

    def polling_started(self: TileComponentManager) -> None:
        """Define actions to be taken when polling starts."""
        self._request_provider = TileRequestProvider()
        self._request_provider.desire_connection()
        self._start_communicating_with_subrack_poller()

    def polling_stopped(self: TileComponentManager) -> None:
        """Define actions to be taken when polling stops."""
        self._request_provider = None
        super().polling_stopped()
        self._update_component_state(programming_state=TpmStatus.UNKNOWN.pretty_name())

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

        :raises ConnectionError: Connection issues
        """
        if self._request_provider is None:
            if task_callback:
                task_callback(
                    status=TaskStatus.REJECTED,
                    result=(ResultCode.REJECTED, "No request provider"),
                )
            raise ConnectionError(
                "Cannot execute 'TileComponentManager.start_acquisition'. "
                "Communication with component is not established."
            )
        subrack_on_command_proxy = MccsCommandProxy(
            self._subrack_fqdn, "PowerOnTpm", self.logger
        )
        # Do not pass the task_callback to command_proxy.
        # The on command is completed when initialisation has completed.
        subrack_on_command_proxy(self._subrack_tpm_id)

        if task_callback:
            task_callback(status=TaskStatus.STAGING)
        request = TileRequest(
            name="initialise",
            command_object=self._tpm_driver.initialise,
            program_fpga=True,
            pps_delay_correction=self._pps_delay_correction,
            task_callback=task_callback,
        )
        self.logger.info("Initialise command placed in poll QUEUE")
        self._request_provider.desire_initialise(request)
        return TaskStatus.QUEUED, "Task staged"

    def _start_communicating_with_subrack_poller(self: TileComponentManager) -> None:
        """
        Establish communication with the subrack, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.

        :raises ConnectionError: Connection to subrack failed
        """
        # Don't set comms NOT_ESTABLISHED here. It should already have been handled
        # synchronously by the orchestator.
        # Check if it was already connected.
        unconnected = self._subrack_proxy is None
        if unconnected:
            self.logger.debug("Starting subrack proxy creation")
            self._subrack_proxy = MccsDeviceProxy(
                self._subrack_fqdn, self.logger, connect=False
            )
            self.logger.error("Connecting to the subrack")
            try:
                self._subrack_proxy.connect()
            except tango.DevFailed as dev_failed:
                self._subrack_proxy = None
                raise ConnectionError(
                    f"Could not connect to '{self._subrack_fqdn}'"
                ) from dev_failed

        cast(MccsDeviceProxy, self._subrack_proxy).add_change_event_callback(
            f"tpm{self._subrack_tpm_id}PowerState",
            self._subrack_says_tpm_power_changed,
        )

    def _subrack_says_tpm_power_changed(
        self: TileComponentManager,
        event_name: str,
        event_value: PowerState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in tpm power states.

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
        # NOTE: This is not something we really want in production code.
        # However the Subrack Simulator is not wired up to the TileSimulator
        # Therefore this is a workaraound
        if self._simulation_mode == SimulationMode.TRUE:
            if event_value == PowerState.ON:
                self.logger.warning("Mocking tpm on")
                self._tpm_driver.mock_on()
            if event_value == PowerState.OFF:
                self.logger.warning("Mocking tpm off")
                self._tpm_driver.mock_off()

        self.logger.info(f"subrack says power is {PowerState(event_value).name}")
        self._subrack_says_tpm_power = event_value

    def _tpm_communication_state_changed(
        self: TileComponentManager, communication_state: CommunicationStatus
    ) -> None:
        """
        Handle a change in status of communication with the tpm.

        :param communication_state: the status of communication with
            the tpm.
        """
        self.logger.error("Not Implemented.")

    @property
    def tpm_status(self: TileComponentManager) -> TpmStatus:
        """
        Return the TPM status.

        :return: the TPM status
        """
        if self.power_state == PowerState.UNKNOWN:
            status = TpmStatus.UNKNOWN
        elif self.power_state != PowerState.ON:
            status = TpmStatus.OFF
        else:
            status = self._tpm_driver.tpm_status
        return status

    #
    # Timed commands. Convert time to frame number
    #
    @check_communicating
    def apply_calibration(self: TileComponentManager, load_time: str = "") -> None:
        """
        Load the calibration coefficients at the specified time delay.

        :param load_time: switch time as ISO formatted time

        :raises ValueError: invalid time
        """
        if load_time == "":
            load_frame = 0
        elif isinstance(load_time, int):  # added for backward compatibility
            load_frame = load_time
        else:
            load_frame = self._tpm_driver.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error(f"apply_calibration: Invalid time {load_time}")
                raise ValueError(f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error("apply_calibration: time not enough in the future")
                raise ValueError("Time too early")
        self._tpm_driver.apply_calibration(load_frame)

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
            load_frame = self._tpm_driver.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error(f"apply_pointing_delays: Invalid time {load_time}")
                raise ValueError(f"Invalid time {load_time}")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "apply_pointing_delays: time not enough in the future"
                )
                raise ValueError("Time too early")
        self._tpm_driver.apply_pointing_delays(load_frame)

    @check_communicating
    def start_beamformer(
        self: TileComponentManager,
        start_time: Optional[str] = None,
        duration: int = -1,
        subarray_beam_id: int = -1,
        scan_id: int = 0,
    ) -> None:
        """
        Start beamforming on a specific subset of the beamformed channels.

        Current firmware version does not support channel mask and scan ID,
        these are ignored

        :param start_time: Start time as ISO formatted time
        :param duration: Scan duration, in frames, default "forever"
        :param subarray_beam_id: Subarray beam ID of the channels to be started
                Command affects only beamformed channels for given subarray ID
                Default -1: all channels
        :param scan_id: ID of the scan to be started. Default 0

        :raises ValueError: invalid time specified
        """
        if start_time is None:
            start_frame: int = 0
        elif isinstance(start_time, int):  # added for backward compatibility
            start_frame = start_time
        else:
            start_frame = self._tpm_driver.frame_from_utc_time(start_time)
            if start_frame < 0:
                self.logger.error(f"start_beamformer: Invalid time {start_time}")
                raise ValueError(f"Invalid time {start_time}")
            if (start_frame - self.fpga_current_frame) < 20:
                self.logger.error("start_beamformer: time not enough in the future")
                raise ValueError("Time too early")
        self._tpm_driver.start_beamformer(
            start_frame, duration, subarray_beam_id, scan_id
        )

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
        :param load_time: Time to start the generator. in UTC ISO formatted string.

        :raises ValueError: invalid time specified
        """
        if load_time is None:
            load_frame = 0
        else:
            load_frame = self._tpm_driver.frame_from_utc_time(load_time)
            if load_frame < 0:
                self.logger.error("configure_test_generator: Invalid time")
                raise ValueError("Invalid time")
            if (load_frame - self.fpga_current_frame) < 20:
                self.logger.error(
                    "configure_test_generator: time not enough in the future"
                )
                raise ValueError("Time too early")
        self._tpm_driver.configure_test_generator(
            frequency0,
            amplitude0,
            frequency1,
            amplitude1,
            amplitude_noise,
            pulse_code,
            amplitude_pulse,
            load_frame,
        )

    # pylint: disable=too-many-arguments
    @check_communicating
    def send_data_samples(
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
        if self.pending_data_requests:
            time.sleep(0.2)
            if self.pending_data_requests:
                self.logger.error("Another send operation is active")
                raise ValueError("Cannot send data, another send operation active")
        # Check for type of data to be sent to LMC
        if start_time is None:
            timestamp = 0
            seconds = params.get("seconds", 0.2)
        elif self._tpm_driver.formatted_fpga_reference_time == 0:
            self.logger.error("Cannot send data, acquisition not started")
            raise ValueError("Cannot send data, acquisition not started")
        else:
            timestamp = self._tpm_driver.frame_from_utc_time(start_time)
            if timestamp < 0:
                self.logger.error(f"Invalid time: {start_time}")
                raise ValueError(f"Invalid time: {start_time}")
            seconds = 0.0

        self._tpm_driver.send_data_samples(
            data_type,
            timestamp,
            seconds,
            n_samples,
            sync,
            first_channel,
            last_channel,
            channel_id,
            frequency,
            round_bits,
        )

    __PASSTHROUGH = [
        "adc_rms",
        "fpga_time",
        "arp_table",
        "beamformer_table",
        "formatted_fpga_reference_time",
        "pps_delay_correction",
        "board_temperature",
        "channeliser_truncation",
        "pending_data_requests",
        "clock_present",
        "configure_40g_core",
        "configure_integrated_beam_data",
        "configure_integrated_channel_data",
        "csp_rounding",
        "current_tile_beamformer_frame",
        "erase_fpga",
        "firmware_available",
        "firmware_name",
        "firmware_version",
        "fpga1_temperature",
        "fpga2_temperature",
        "fpgas_time",
        "fpga_current_frame",
        "fpga_frame_time",
        "get_40g_configuration",
        "voltages",
        "temperatures",
        "currents",
        "timing",
        "io",
        "dsp",
        "hardware_version",
        "initialise_beamformer",
        "is_beamformer_running",
        "is_programmed",
        "load_calibration_coefficients",
        "load_pointing_delays",
        "phase_terminal_count",
        "pll_locked",
        "pps_delay",
        "pps_present",
        "preadu_levels",
        "read_address",
        "read_register",
        "register_list",
        # "send_data_samples",
        "set_beamformer_regions",
        "set_lmc_download",
        "set_lmc_integrated_download",
        "static_delays",
        "stop_beamformer",
        "stop_data_transmission",
        "stop_integrated_data",
        "sync_fpgas",
        "sysref_present",
        "test_generator_active",
        "test_generator_input_select",
        "tile_id",
        "station_id",
        "tpm_status",
        "voltage_mon",
        "write_address",
        "write_register",
    ]

    def __getattr__(self: TileComponentManager, name: str) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute

        :return: the requested attribute
        :raises AttributeError: if the attribute is not a passthrough attribute
        """
        if name in self.__PASSTHROUGH:
            return self._get_from_hardware(name)
        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")

    @check_communicating
    @check_on
    def _get_from_hardware(self: TileComponentManager, name: str) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._tpm_driver, name)

    def __setattr__(self: TileComponentManager, name: str, value: Any) -> None:
        """
        Set an attribute on this tile component manager.

        This is implemented to pass writes to certain attributes to the
        underlying hardware component manager.

        :param name: name of the attribute for which the value is to be
            set
        :param value: new value of the attribute
        """
        if name in self.__PASSTHROUGH:
            self._set_in_hardware(name, value)
        else:
            super().__setattr__(name, value)

    @check_communicating
    @check_on
    def _set_in_hardware(self: TileComponentManager, name: str, value: Any) -> None:
        """
        Set an attribute in the component (if we are communicating with it).

        :param name: name of the attribute to set.
        :param value: new value for the attribute
        """
        # This one-liner is only a method so that we can decorate it.
        setattr(self._tpm_driver, name, value)

    def set_pps_delay_correction(
        self: TileComponentManager,
        correction: int,
    ) -> None:
        """
        Set the ppsDelay correction.

        :param correction: the correction to set
        """
        self._pps_delay_correction = correction

    #
    # Long running commands
    #
    def initialise(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        program_fpga: bool = True,
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit the initialise slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None
        :param program_fpga: Force FPGA reprogramming, for complete initialisation

        :returns: A tuple containing a task status and a unique id string to
            identify the command

        :raises ConnectionError: if we are not connected to the TPM.
        """
        if self.communication_state != CommunicationStatus.ESTABLISHED:
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result=(ResultCode.ABORTED, "Aborted")
                )
            raise ConnectionError(
                "Cannot execute 'TileComponentManager.initialise'. "
                "Communication with component is not established."
            )
        return self._tpm_driver.initialise(
            program_fpga=program_fpga,
            pps_delay_correction=self._pps_delay_correction,
            task_callback=task_callback,
        )

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
        :raises ConnectionError: if we are not connected to the TPM.
        """
        if self.communication_state != CommunicationStatus.ESTABLISHED:
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result=(ResultCode.ABORTED, "Aborted")
                )
            raise ConnectionError(
                "Cannot execute 'TileComponentManager.download_firmware'. "
                "Communication with component is not established."
            )
        return self._tpm_driver.download_firmware(
            bitfile=argin,
            task_callback=task_callback,
        )

    def start_acquisition(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        *,
        start_time: Optional[str] = None,
        delay: int = 2,
    ) -> tuple[TaskStatus, str] | None:
        """
        Submit the start_acquisition slow task.

        :param task_callback: Update task state, defaults to None
        :param start_time: the acquisition start time
        :param delay: a delay to the acquisition start

        :return: A tuple containing a task status and a unique id string to
            identify the command

        :raises ConnectionError: if we are not connected to the TPM.
        """
        if self.communication_state != CommunicationStatus.ESTABLISHED:
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result=(ResultCode.ABORTED, "Aborted")
                )
            raise ConnectionError(
                "Cannot execute 'TileComponentManager.start_acquisition'. "
                "Communication with component is not established."
            )
        return self._tpm_driver.start_acquisition(
            start_time=start_time, delay=delay, task_callback=task_callback
        )

    def post_synchronisation(
        self: TileComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the post_synchronisation slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        return self.submit_task(self._post_synchronisation, task_callback=task_callback)

    @check_communicating
    def _post_synchronisation(
        self: TileComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Post synchronisation using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises NotImplementedError: Command not implemented
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._tpm_driver.post_synchronisation()
        except NotImplementedError:
            raise
        # pylint: disable-next=broad-except
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED,
                    result="Post synchronisation task aborted",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Post synchronisation has completed"
            )
            return
