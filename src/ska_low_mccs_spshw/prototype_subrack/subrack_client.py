#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A polling client for an SPS subrack management board. Holds no Tango code.

:py:class:`Subrack` owns a
:py:class:`~ska_low_mccs_common.component.WebHardwareClient`, a lock that
serialises every access to it, a :py:class:`SubrackPollModel` and a
:py:class:`ska_tango_base.poller.Poller`.

One lock covers both polls and board commands. A board command takes it on the
thread that calls it, so it does not wait for a poll slot.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, cast

from ska_low_mccs_common.component import (
    HardwareClientResponseStatusCodes,
    WebHardwareClient,
)
from ska_tango_base.poller import Poller, PollModel

from ..tile.utils import LogLock, acquire_timeout
from .constants import (
    BATCH_ATTRIBUTES,
    COMMAND_POLL_INTERVAL,
    COMMAND_TIMEOUT,
    LOCK_TIMEOUT,
    LOCK_WARNING,
    MIN_HEALTH_BIOS_VERSION,
    HttpError,
    RequestError,
)
from .derived_values import DerivedValues

__all__ = [
    "BoardCommandStatus",
    "Subrack",
    "SubrackPollModel",
    "SubrackPollRequest",
    "SubrackPollResponse",
]

_OK = HardwareClientResponseStatusCodes.OK.name
_ERROR = HardwareClientResponseStatusCodes.ERROR.name
_STARTED = HardwareClientResponseStatusCodes.STARTED.name
_BUSY = HardwareClientResponseStatusCodes.BUSY.name
_HTTP_ERROR = HardwareClientResponseStatusCodes.HTTP_ERROR.name
_JSON_DECODE_ERROR = HardwareClientResponseStatusCodes.JSON_DECODE_ERROR.name
_REQUEST_EXCEPTION = HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name

_TRANSPORT_ERRORS = (_HTTP_ERROR, _REQUEST_EXCEPTION)
_IN_BAND_ERRORS = (_ERROR, _JSON_DECODE_ERROR)
_BOARD_BUSY = (_BUSY, _STARTED)


class BoardCommandStatus(Enum):
    """The outcome of a board command run by :py:meth:`Subrack.run_board_command`."""

    COMPLETED = auto()
    FAILED = auto()
    ABORTED = auto()


@dataclass
class SubrackPollRequest:
    """What a single subrack poll should do."""

    attribute_keys: tuple[str, ...]
    """The hardware read keys to fetch this poll."""

    fetch_health: bool
    """Whether this poll should also read the SMB health status."""

    def __bool__(self: SubrackPollRequest) -> bool:
        """
        Report whether this request asks for anything.

        The poller skips a poll when the request is falsy.

        :return: whether this request asks for anything.
        """
        return bool(self.attribute_keys) or self.fetch_health


@dataclass
class SubrackPollResponse:
    """The result of a single subrack poll."""

    values: dict[str, Any] = field(default_factory=dict)
    """Hardware read key to value.

    Every requested key is present. A value is ``None`` when the board could
    not supply it. Derived keys are present alongside the raw reads.
    """

    health_status: Optional[dict] = None
    """The health status, or ``None`` when this poll did not read it."""

    timestamp: float = 0.0
    """The wall clock time at which the poll completed."""


# pylint: disable-next=too-many-instance-attributes
class SubrackPollModel(PollModel[SubrackPollRequest, SubrackPollResponse]):
    """
    The polling model for a subrack management board.

    Each poll reads a batch of attributes over HTTP. On a slower cadence it also
    reads the health status. Every access to the client happens under a shared
    lock, so a poll never overlaps a board command.

    A transport failure is raised as :py:class:`RequestError` or
    :py:class:`HttpError`, so the poller routes it to :py:meth:`poll_failed`. An
    error that the board itself reports gives a value of ``None`` instead, which
    the device turns into invalid attribute quality.

    :py:class:`~.derived_values.DerivedValues` supplies the computed values.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self: SubrackPollModel,
        client: WebHardwareClient,
        client_lock: LogLock,
        logger: logging.Logger,
        command_update_rate: float,
        lock_timeout: float,
        data_callback: Callable[[SubrackPollResponse], None],
        error_callback: Callable[[Exception], None] | None = None,
        max_fan_errors: int = 5,
        max_fan_rpm_delta: float = 25.0,
        attribute_filter_type: str | None = None,
        attribute_filter_max_samples: int = 5,
    ) -> None:
        """
        Initialise a new instance.

        :param client: the HTTP hardware client.
        :param client_lock: the lock that serialises access to ``client``.
        :param lock_timeout: how long, in seconds, to wait for the lock.
        :param logger: a logger for this model to use.
        :param command_update_rate: the shortest interval, in seconds, between
            health status reads.
        :param data_callback: called with each successful poll response.
        :param error_callback: called with the exception from a failed poll.
        :param max_fan_errors: how many consecutive bad fan rpm estimates to
            replace, per fan, before the estimate is reported as read.
        :param max_fan_rpm_delta: the tolerance, as a percentage of the maximum
            fan speed, outside which a fan rpm estimate counts as bad.
        :param attribute_filter_type: the noise filter to apply to the TPM
            current, power and voltage readings.
        :param attribute_filter_max_samples: the filter sample window.
        """
        self._client = client
        self._client_lock = client_lock
        self._logger = logger
        self._command_update_rate = command_update_rate
        self._lock_timeout = lock_timeout
        self._data_callback = data_callback
        self._error_callback = error_callback

        # Health status bookkeeping. Touched on the poll thread only.
        self._last_health_fetch = 0.0
        self._checked_bios = False
        self._health_supported = False

        # The values that are computed rather than read. This object owns all
        # state that spans polls, other than the health status bookkeeping.
        self.derived = DerivedValues(
            logger,
            max_fan_errors=max_fan_errors,
            max_fan_rpm_delta=max_fan_rpm_delta,
            attribute_filter_type=attribute_filter_type,
            attribute_filter_max_samples=attribute_filter_max_samples,
        )

    # ----------------
    # PollModel hooks
    # ----------------
    def get_request(self: SubrackPollModel) -> SubrackPollRequest:
        """
        Return what the next poll should do.

        :return: every batched attribute, and a health status read when the
            health cadence has elapsed.
        """
        elapsed = time.monotonic() - self._last_health_fetch
        return SubrackPollRequest(
            attribute_keys=BATCH_ATTRIBUTES,
            fetch_health=elapsed >= self._command_update_rate,
        )

    def poll(
        self: SubrackPollModel, poll_request: SubrackPollRequest
    ) -> SubrackPollResponse:
        """
        Perform one poll of the subrack over HTTP.

        :param poll_request: what to read this poll.

        :raises RequestError: if the client lock is not free in time.

        :return: the poll response.
        """
        with acquire_timeout(
            self._client_lock, self._lock_timeout, context="poll sweep"
        ) as acquired:
            if not acquired:
                raise RequestError(
                    f"Could not reach the board within {self._lock_timeout}s. "
                    "Another operation still holds the client."
                )
            values = self._fetch_attributes(poll_request.attribute_keys)
            self._update_bios_gate(values.get("board_info"))
            health_status = self._maybe_fetch_health(poll_request.fetch_health)

        self.derived.apply(values)

        return SubrackPollResponse(
            values=values, health_status=health_status, timestamp=time.time()
        )

    def poll_succeeded(
        self: SubrackPollModel, poll_response: SubrackPollResponse
    ) -> None:
        """
        Give a successful poll response to the data callback.

        :param poll_response: the response to the poll.
        """
        self._data_callback(poll_response)

    def poll_failed(self: SubrackPollModel, exception: Exception) -> None:
        """
        Give a poll failure to the error callback.

        The caches of values that span polls are cleared, because a board we
        cannot reach has no known fan history and no known sample window.

        :param exception: the exception raised by the poll.
        """
        self.derived.clear()
        if self._error_callback is not None:
            self._error_callback(exception)

    # ----------------
    # Reads
    # ----------------
    @staticmethod
    def _raise_for_transport_error(response: Any) -> None:
        """
        Raise the exception that matches a transport level failure.

        :param response: a client response whose status is a transport error.

        :raises HttpError: if the board answered with an HTTP error.
        :raises RequestError: if the request never reached the board.
        """
        if response["status"] == _HTTP_ERROR:
            raise HttpError(str(response["info"]))
        raise RequestError(str(response["info"]))

    def _fetch_attributes(
        self: SubrackPollModel, keys: tuple[str, ...]
    ) -> dict[str, Any]:
        """
        Read the given hardware attributes from the subrack over HTTP.

        Every requested key is present in the result. A key whose value the
        board could not supply maps to ``None``.

        :param keys: the hardware read keys to fetch.

        :raises ValueError: if the client returns an unknown status code.

        :return: a mapping of hardware read key to value.
        """
        values: dict[str, Any] = dict.fromkeys(keys)
        for key in keys:
            response = self._client.get_attribute(key)
            status = response["status"]
            if status == _OK:
                values[key] = response["value"]
            elif status in _IN_BAND_ERRORS:
                self._logger.warning(
                    "get_attribute '%s' returned status '%s'. %s",
                    key,
                    status,
                    response.get("info", "No details."),
                )
            elif status in _TRANSPORT_ERRORS:
                # Raised so that the poller routes it to poll_failed, which the
                # device turns into an operational state change.
                self._raise_for_transport_error(response)
            elif status in _BOARD_BUSY:
                # The board is busy. Leave this key unknown for this poll.
                pass
            else:
                raise ValueError(
                    f"Unknown status code '{status}' from get_attribute. "
                    "Check the hardware client."
                )
        return values

    def _update_bios_gate(self: SubrackPollModel, board_info: Any) -> None:
        """
        Enable health status reads once the SMB BIOS is known to support them.

        :param board_info: the board info from this poll, or ``None``.
        """
        if self._checked_bios or not board_info:
            return
        try:
            bios_version = board_info["SMM"]["bios"]
            parsed = tuple(int(part) for part in bios_version.lstrip("v").split("."))
            self._health_supported = parsed >= MIN_HEALTH_BIOS_VERSION
        except (AttributeError, KeyError, TypeError, ValueError):
            self._logger.warning(
                "Could not read the BIOS version from the board info. "
                "Health status reads stay disabled."
            )
        self._checked_bios = True

    def _maybe_fetch_health(
        self: SubrackPollModel, fetch_health: bool
    ) -> Optional[dict]:
        """
        Read the SMB health status, if it is due and the BIOS supports it.

        The caller must hold ``self._client_lock``.

        :param fetch_health: whether the health cadence has elapsed.

        :raises ValueError: if the client returns an unknown status code.

        :return: the health status, or ``None`` if it was not read this poll.
        """
        if not fetch_health:
            return None

        now = time.monotonic()
        if not self._health_supported:
            self._last_health_fetch = now
            return None

        response = self._client.execute_command("get_health_status", "")
        status = response["status"]
        if status == _OK:
            self._last_health_fetch = now
            # The client types retvalue as str, but get_health_status returns a
            # nested dictionary.
            return cast(Optional[dict], response["retvalue"])
        if status in _BOARD_BUSY:
            # The board is busy. Retry next poll without advancing the timer.
            return None
        if status in _TRANSPORT_ERRORS:
            self._raise_for_transport_error(response)
        if status in _IN_BAND_ERRORS:
            self._logger.error(
                "get_health_status returned status '%s'. %s",
                status,
                response.get("info", "No details."),
            )
            self._last_health_fetch = now
            return None
        raise ValueError(
            f"Unknown status code '{status}' from execute_command. "
            "Check the hardware client."
        )


class Subrack:
    """
    A polling client for an SPS subrack management board.

    A Tango device holds one of these. It runs a background poll loop that
    gives each result to the callbacks supplied at construction. It also runs
    board commands, serialised against the poll loop on a shared lock.

    The callbacks fire only while polling is active. A caller must ignore a late
    callback that arrives after :py:meth:`stop_polling`, because that method
    does not block.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self: Subrack,
        host: str,
        port: int,
        logger: logging.Logger,
        poll_rate: float,
        command_update_rate: float,
        data_callback: Callable[[SubrackPollResponse], None],
        error_callback: Callable[[Exception], None] | None = None,
        max_fan_errors: int = 5,
        max_fan_rpm_delta: float = 25.0,
        attribute_filter_type: str | None = None,
        attribute_filter_max_samples: int = 5,
        lock_timeout: float = LOCK_TIMEOUT,
        lock_warning: float = LOCK_WARNING,
        _client: WebHardwareClient | None = None,
    ) -> None:
        """
        Initialise a new instance.

        :param host: the host name or IP address of the management board.
        :param port: the HTTP port of the management board.
        :param logger: a logger for this client to use.
        :param poll_rate: how long, in seconds, to wait after a poll before
            polling again.
        :param command_update_rate: the shortest interval, in seconds, between
            health status reads.
        :param data_callback: called with each successful poll response.
        :param error_callback: called with the exception from a failed poll.
        :param max_fan_errors: how many consecutive bad fan rpm estimates to
            replace, per fan.
        :param max_fan_rpm_delta: the tolerance, as a percentage of the maximum
            fan speed, outside which a fan rpm estimate counts as bad.
        :param attribute_filter_type: the noise filter to apply to the TPM
            current, power and voltage readings.
        :param attribute_filter_max_samples: the filter sample window.
        :param lock_timeout: how long, in seconds, to wait for the client lock
            before giving up. This bounds how long a stalled board can block a
            poll or a command.
        :param lock_warning: how long, in seconds, a lock hold must exceed
            before it is logged.
        :param _client: an alternative hardware client, for testing only.
        """
        self._logger = logger
        self._client = _client or WebHardwareClient(host, port)
        self._lock_timeout = lock_timeout
        # The board fails every request while a command is active, so all access
        # to the client is serialised. A LogLock reports a long hold and names
        # the holder, so a stalled board is visible in the log.
        self._client_lock = LogLock(
            f"subrack-{host}", logger, timeout_warning=lock_warning
        )
        self._poll_model = SubrackPollModel(
            self._client,
            self._client_lock,
            logger,
            command_update_rate,
            lock_timeout,
            data_callback,
            error_callback,
            max_fan_errors=max_fan_errors,
            max_fan_rpm_delta=max_fan_rpm_delta,
            attribute_filter_type=attribute_filter_type,
            attribute_filter_max_samples=attribute_filter_max_samples,
        )
        self._poller = Poller(self._poll_model, poll_rate, logger)

    def start_polling(self: Subrack) -> None:
        """Start polling the subrack."""
        self._poller.start_polling()

    def stop_polling(self: Subrack) -> None:
        """Stop polling the subrack."""
        self._poller.stop_polling()

    def cleanup(self: Subrack) -> None:
        """Kill the polling thread. Do not use the instance afterwards."""
        self._poller.kill_polling_thread()

    # pylint: disable-next=too-many-return-statements
    def run_board_command(
        self: Subrack,
        name: str,
        args: str = "",
        abort_event: Optional[threading.Event] = None,
    ) -> tuple[BoardCommandStatus, str, Any]:
        """
        Run one SMB board command and handle the asynchronous handshake.

        The shared lock is held for the whole command, so board commands are
        serialised against each other and against polling. An SMB command that
        reports ``STARTED`` is asynchronous. This method then probes
        ``command_completed`` until the command finishes, times out, or is
        aborted.

        :param name: the SMB command name.
        :param args: the SMB command argument string.
        :param abort_event: an event that requests an abort when set.

        :return: the status, a message, and the returned value.
        """
        with acquire_timeout(
            self._client_lock, self._lock_timeout, context=f"command {name}"
        ) as acquired:
            if not acquired:
                return (
                    BoardCommandStatus.FAILED,
                    f"Command '{name}' gave up after {self._lock_timeout}s. "
                    "The board is busy with another operation.",
                    None,
                )
            response = self._client.execute_command(name, args)
            status = response["status"]

            if status == _OK:
                retvalue = response["retvalue"]
                if retvalue == _STARTED:
                    return self._await_command_completion(name, abort_event)
                if retvalue == "FAILED":
                    return (
                        BoardCommandStatus.FAILED,
                        f"The board did not accept command '{name}'. It is busy.",
                        None,
                    )
                return (
                    BoardCommandStatus.COMPLETED,
                    "The command completed.",
                    retvalue,
                )
            if status == _STARTED:
                return self._await_command_completion(name, abort_event)
            if status == _BUSY:
                return (
                    BoardCommandStatus.FAILED,
                    f"The board did not accept command '{name}'. It is busy.",
                    None,
                )
            return (
                BoardCommandStatus.FAILED,
                f"Command '{name}' failed with status '{status}'. "
                f"{response.get('info', 'No details.')}",
                None,
            )

    def _abort_board_command(self: Subrack) -> None:
        """
        Ask the board to abort the command it is running.

        A board that does not accept the abort is logged and not raised.

        The caller must hold ``self._client_lock``.
        """
        response = self._client.execute_command("abort_command")
        if response["status"] != _OK:
            self._logger.error(
                "The board did not accept abort_command. Status '%s'. %s",
                response["status"],
                response.get("info", "No details."),
            )

    def _await_command_completion(
        self: Subrack, name: str, abort_event: Optional[threading.Event]
    ) -> tuple[BoardCommandStatus, str, Any]:
        """
        Probe ``command_completed`` until the board command finishes.

        The caller must hold ``self._client_lock``.

        :param name: the name of the command being awaited, for the message.
        :param abort_event: an event that requests an abort when set.

        :return: the status, a message, and the returned value.
        """
        deadline = time.monotonic() + COMMAND_TIMEOUT
        while True:
            if abort_event is not None and abort_event.is_set():
                self._abort_board_command()
                return (BoardCommandStatus.ABORTED, "The command was aborted.", None)
            if time.monotonic() > deadline:
                return (
                    BoardCommandStatus.FAILED,
                    "Timed out waiting for the command to complete.",
                    None,
                )
            time.sleep(COMMAND_POLL_INTERVAL)

            response = self._client.execute_command("command_completed")
            status = response["status"]
            if status == _OK:
                if response.get("retvalue"):
                    return (
                        BoardCommandStatus.COMPLETED,
                        "The command completed.",
                        None,
                    )
                # The command is still running.
                continue
            if status in _TRANSPORT_ERRORS:
                return (
                    BoardCommandStatus.FAILED,
                    str(response["info"]),
                    None,
                )
            if status in _BOARD_BUSY:
                # The board is still working on it, so keep waiting.
                continue
            # Anything else is the board reporting a problem, or a status the
            # client does not know. Waiting would discard the reason and blame
            # the timeout for something that is never going to finish.
            return (
                BoardCommandStatus.FAILED,
                f"Command '{name}' failed while completing, with status "
                f"'{status}'. {response.get('info', 'No details.')}",
                None,
            )
