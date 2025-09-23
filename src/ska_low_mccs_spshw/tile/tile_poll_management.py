# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements polling management for a TileComponentManager."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ska_control_model import ResultCode, TaskStatus

from .tpm_status import TpmStatus

__all__ = [
    "TileRequestProvider",
    "TileLRCRequest",
    "TileRequest",
    "TileResponse",
    "RequestIterator",
]


# pylint: disable=too-few-public-methods
class TileRequest:
    """Class representing an action to be performed by a poll."""

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

        :param name: Name of the command.
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


class TileLRCRequest(TileRequest):
    """Class handling a Long Running Command request."""

    def __init__(
        self: TileLRCRequest,
        name: str,
        command_object: Any,
        *args: Any,
        publish: bool = False,
        task_callback: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new LRC request for execution in a poll.

        :param name: Name of the command.
        :param command_object: The object to call
        :param args: optional arguments to pass
        :param publish: Whether to publish the results of
            poll to the TANGO device on poll_success
        :param task_callback: An optional callback to update
            with command status.
        :param kwargs: Optional kwargs
        """
        self.task_callback = task_callback
        super().__init__(name, command_object, *args, publish=publish, **kwargs)

    def notify_queued(self: TileLRCRequest) -> None:
        """Notify task callback that this command is QUEUED."""
        if self.task_callback:
            self.task_callback(
                status=TaskStatus.QUEUED,
            )

    def notify_completed(self: TileLRCRequest) -> None:
        """Notify task callback that this command has COMPLETED."""
        if self.task_callback:
            self.task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Command executed to completion."),
            )

    def notify_failed(self: TileLRCRequest, message: str = "") -> None:
        """
        Notify task callback that this command is FAILED.

        :param message: an optional message to report to the
            task callback.
        """
        if self.task_callback:
            self.task_callback(
                status=TaskStatus.FAILED,
                result=(ResultCode.FAILED, message),
            )

    def notify_in_progress(self: TileLRCRequest) -> None:
        """Notify task callback that this command is IN_PROGRESS."""
        if self.task_callback:
            self.task_callback(
                status=TaskStatus.IN_PROGRESS,
            )

    def notify_removed_from_queue(self: TileLRCRequest) -> None:
        """
        Notify task callback that this command has been removed.

        NOTE: Since we have just wiped this request
        it will never be picked up during a poll,
        we must abort the command. The client to the LRC will
        then see QUEUED -> ABORTED, and the command will never be
        executed.
        """
        if self.task_callback:
            self.task_callback(
                status=TaskStatus.ABORTED,
                result=(ResultCode.ABORTED, "Command aborted"),
            )


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


class RequestIterator:
    """A class that returns attributes allowed given a TpmStatus."""

    UNCONNECTED_POLLED_ATTRIBUTES = ["CONNECT", "CHECK_CPLD_COMMS"]
    OFF_POLLED_ATTRIBUTES = ["CONNECT"]
    UNKNOWN_POLLED_ATTRIBUTES = ["CONNECT", "CHECK_CPLD_COMMS"]
    UNPROGRAMMED_POLLED_ATTRIBUTES = ["CHECK_CPLD_COMMS"]
    PROGRAMMED_POLLED_ATTRIBUTES = [
        "CHECK_CPLD_COMMS",
        "CSP_ROUNDING",
        "CHANNELISER_ROUNDING",
        "IS_PROGRAMMED",
        "CHECK_BOARD_TEMPERATURE",
        "HEALTH_STATUS",
        "PLL_LOCKED",
    ]
    INITIALISED_POLLED_ATTRIBUTES = [
        "CHECK_CPLD_COMMS",
        "CSP_ROUNDING",
        "STATION_ID",
        "CHANNELISER_ROUNDING",
        "IS_PROGRAMMED",
        "HEALTH_STATUS",
        "STATION_ID",
        "PLL_LOCKED",
        "CHECK_BOARD_TEMPERATURE",
        "HEALTH_STATUS",
        "STATION_ID",
        "ADC_RMS",
        "PLL_LOCKED",
        "STATION_ID",
        "PENDING_DATA_REQUESTS",
        "PPS_DELAY",
        "PPS_DRIFT",
        "PPS_DELAY_CORRECTION",
        "IS_BEAMFORMER_RUNNING",
        "STATION_ID",
        "FPGA_REFERENCE_TIME",
        "PHASE_TERMINAL_COUNT",
        "PREADU_LEVELS",
        "STATIC_DELAYS",
        "STATION_ID",
        "TILE_ID",
        "BEAMFORMER_TABLE",
    ]

    SYNCHRONISED_POLLED_ATTRIBUTES = [
        "CHECK_CPLD_COMMS",
        "CSP_ROUNDING",
        "STATION_ID",
        "CHANNELISER_ROUNDING",
        "IS_PROGRAMMED",
        "HEALTH_STATUS",
        "PLL_LOCKED",
        "CHECK_BOARD_TEMPERATURE",
        "HEALTH_STATUS",
        "STATION_ID",
        "ADC_RMS",
        "PLL_LOCKED",
        "PENDING_DATA_REQUESTS",
        "PPS_DELAY",
        "PPS_DRIFT",
        "PPS_DELAY_CORRECTION",
        "STATION_ID",
        "IS_BEAMFORMER_RUNNING",
        "FPGA_REFERENCE_TIME",
        "PHASE_TERMINAL_COUNT",
        "PREADU_LEVELS",
        "STATIC_DELAYS",
        "STATION_ID",
        "TILE_ID",
        "BEAMFORMER_TABLE",
        "TILE_BEAMFORMER_FRAME",
        "RFI_COUNT",
    ]

    def __init__(self: RequestIterator):
        """Construct a instance of RequestIterator."""
        self.idx = 0
        self._state = TpmStatus.UNKNOWN
        self.allowed_attributes = {
            TpmStatus.OFF: self.OFF_POLLED_ATTRIBUTES,
            TpmStatus.UNKNOWN: self.UNKNOWN_POLLED_ATTRIBUTES,
            TpmStatus.UNPROGRAMMED: self.UNPROGRAMMED_POLLED_ATTRIBUTES,
            TpmStatus.UNCONNECTED: self.UNCONNECTED_POLLED_ATTRIBUTES,
            TpmStatus.PROGRAMMED: self.PROGRAMMED_POLLED_ATTRIBUTES,
            TpmStatus.INITIALISED: self.INITIALISED_POLLED_ATTRIBUTES,
            TpmStatus.SYNCHRONISED: self.SYNCHRONISED_POLLED_ATTRIBUTES,
        }

    def calculate_stale_attributes(
        self: RequestIterator, new_status: TpmStatus | None
    ) -> set[Any]:
        """
        Return a set of attribute that will no longer be polled.

        :param new_status: the new TpmStatus

        :return: a set of attribute that will no longer be polled.
        """
        if new_status is None:
            return set(self.allowed_attributes[self.state])
        return set(self.allowed_attributes[self.state]) - set(
            self.allowed_attributes[new_status]
        )

    @property
    def state(self: RequestIterator) -> TpmStatus:
        """
        Return the TpmStatus.

        :return: the TpmStatus
        """
        return self._state

    @state.setter
    def state(self: RequestIterator, new_state: TpmStatus) -> None:
        """
        Set the new TpmStatus.

        :param new_state: the new TpmStatus.
        """
        if new_state != self._state:
            # reset index to zero.
            self.idx = 0
            self._state = new_state

    def __iter__(self: RequestIterator) -> RequestIterator:
        """
        Implement iter method.

        :return: self.
        """
        return self

    def __next__(self: RequestIterator) -> str:
        """
        Iterate over attributes allowed given current TpmStatus.

        :raises AttributeError: when there are no attributes allowed in state.
        :return: the next item.
        """
        allowed_attributes = self.allowed_attributes.get(self.state)
        if allowed_attributes is None:
            raise AttributeError(f"No attributes allowed in state {self.state}")

        index = self.idx % len(allowed_attributes)
        item = allowed_attributes[index]

        self.idx += 1
        return item


# pylint: disable=too-many-instance-attributes
class TileRequestProvider:
    """
    A class that manages requests for the Tile.

    It ensures that:

    * commands get executed as promptly as possible

    * only attributes allowed to be polled given a TpmStatus are returned.
    """

    def __init__(
        self,
        stale_attribute_callback: Callable | None = None,
        _request_iterator: RequestIterator | None = None,
    ) -> None:
        """
        Initialise a new instance.

        :param stale_attribute_callback: an optional callback to
            call with attributes no longer being updated.
        :param _request_iterator: an optional RequestIterator to supply for
            testing.
        """
        self._stale_attribute_callback = stale_attribute_callback
        self.request_iterator = _request_iterator or RequestIterator()
        self.initialise_request: Optional[TileLRCRequest] = None
        self.download_firmware_request: Optional[TileLRCRequest] = None
        self.start_acquisition_request: Optional[TileLRCRequest] = None
        self.start_antenna_buffer_rqst: Optional[TileLRCRequest] = None
        self.read_antenna_buffer_request: Optional[TileLRCRequest] = None
        self._desire_connection = False
        self.command_wipe_time: dict[str, float] = {}

    def desire_connection(self) -> None:
        """Register a request to connect with the TPM."""
        self._desire_connection = True

    def desire_initialise(
        self, request: TileLRCRequest, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to initialize a device.

        :param request: The initialise request to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        # Remove download firmware and startacquisition command if exist.
        if self.download_firmware_request:
            self.download_firmware_request.notify_removed_from_queue()
            self.download_firmware_request = None
        if self.start_acquisition_request:
            self.start_acquisition_request.notify_removed_from_queue()
            self.start_acquisition_request = None
        if self.initialise_request:
            self.initialise_request.notify_removed_from_queue()
            self.initialise_request = None
        self.initialise_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["initialise"] = wipe_time
        self.initialise_request.notify_queued()

    def desire_download_firmware(
        self, request: TileLRCRequest, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to download new firmware to a device.

        :param request: The download firmware request to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        if self.download_firmware_request:
            self.download_firmware_request.notify_removed_from_queue()
            self.download_firmware_request = None
        self.download_firmware_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["download_firmware"] = wipe_time
        self.download_firmware_request.notify_queued()

    def desire_start_acquisition(
        self, request: TileLRCRequest, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to download new firmware to a device.

        :param request: The start acquisition request to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        if self.start_acquisition_request:
            self.start_acquisition_request.notify_removed_from_queue()
            self.start_acquisition_request = None
        self.start_acquisition_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["start_acquisition"] = wipe_time
        self.start_acquisition_request.notify_queued()

    def desire_start_antenna_buffer(
        self, request: TileLRCRequest, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to start the antenna buffer.

        :param request: The start acquisition request to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        if self.start_antenna_buffer_rqst:
            self.start_antenna_buffer_rqst.notify_removed_from_queue()
            self.start_antenna_buffer_rqst = None
        self.start_antenna_buffer_rqst = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["start_antenna_buffer"] = wipe_time
        self.start_antenna_buffer_rqst.notify_queued()

    def desire_read_antenna_buffer(
        self, request: TileLRCRequest, wipe_time: Optional[float] = None
    ) -> None:
        """
        Register a request to start the antenna buffer.

        :param request: The start acquisition request to execute on
            a poll.
        :param wipe_time: the approx time at which to wipe this command.
        """
        if self.read_antenna_buffer_request:
            self.read_antenna_buffer_request.notify_removed_from_queue()
            self.read_antenna_buffer_request = None
        self.read_antenna_buffer_request = request
        if wipe_time is None:
            wipe_time = time.time() + 60
        self.command_wipe_time["read_antenna_buffer"] = wipe_time
        self.read_antenna_buffer_request.notify_queued()

    def _wipe_old_long_running_commands(self) -> None:
        """Remove old commands."""
        # Check if the initialise LRC need to be aborted.
        for command, wipe_time in self.command_wipe_time.items():
            if time.time() > wipe_time:
                match command:
                    case "initialise":
                        if self.initialise_request:
                            self.initialise_request.notify_removed_from_queue()
                            self.initialise_request = None
                    case "download_firmware":
                        if self.download_firmware_request:
                            self.download_firmware_request.notify_removed_from_queue()
                            self.download_firmware_request = None
                    case "start_acquisition":
                        if self.start_acquisition_request:
                            self.start_acquisition_request.notify_removed_from_queue()
                            self.start_acquisition_request = None
                    case "start_antenna_buffer":
                        if self.start_antenna_buffer_rqst:
                            self.start_antenna_buffer_rqst.notify_removed_from_queue()
                            self.start_antenna_buffer_rqst = None
                    case "read_antenna_buffer":
                        if self.read_antenna_buffer_request:
                            self.read_antenna_buffer_request.notify_removed_from_queue()
                            self.read_antenna_buffer_request = None

    def __del__(self) -> None:
        """Clean up and notify callbacks."""
        stale_attributes = self.request_iterator.calculate_stale_attributes(None)
        self.request_iterator.state = TpmStatus.UNKNOWN
        if stale_attributes:
            if self._stale_attribute_callback is not None:
                self._stale_attribute_callback(stale_attributes)

    def get_request(  # pylint: disable=too-many-return-statements
        self, tpm_status: TpmStatus
    ) -> str | TileRequest | None:
        """
        Get the next request to execute on the Tile.

        :param tpm_status: the tpm_status at the time of the request.

        :return: the next request to execute on the Tile.
        """
        self._wipe_old_long_running_commands()
        # Calculate attributes no longer being polled, and call a callback with them
        # If a callback is available.
        stale_attributes = self.request_iterator.calculate_stale_attributes(tpm_status)
        self.request_iterator.state = tpm_status
        if stale_attributes:
            if self._stale_attribute_callback is not None:
                self._stale_attribute_callback(stale_attributes)
        # Key connection commands come first
        if self._desire_connection:
            self._desire_connection = False
            return "CONNECT"

        # Check for any commands.
        match tpm_status:
            case TpmStatus.UNPROGRAMMED | TpmStatus.PROGRAMMED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
                    return request
            case TpmStatus.INITIALISED | TpmStatus.SYNCHRONISED:
                if self.initialise_request:
                    request = self.initialise_request
                    self.initialise_request = None
                    return request
                if self.download_firmware_request:
                    request = self.download_firmware_request
                    self.download_firmware_request = None
                    return request
                if self.start_acquisition_request:
                    request = self.start_acquisition_request
                    self.start_acquisition_request = None
                    return request
                if self.start_antenna_buffer_rqst:
                    request = self.start_antenna_buffer_rqst
                    self.start_antenna_buffer_rqst = None
                    return request
                if self.read_antenna_buffer_request:
                    request = self.read_antenna_buffer_request
                    self.read_antenna_buffer_request = None
                    return request

        # return next item to poll
        return next(self.request_iterator)
