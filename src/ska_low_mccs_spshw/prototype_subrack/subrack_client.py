#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A polling client for an SPS subrack management board. Holds no Tango code.

:py:class:`Subrack` is the poll model that
:py:class:`ska_tango_base.poller.Poller` drives, and it also runs board
commands. The caller supplies the
:py:class:`~.client_wrapper.WebHardwareClientWrapper` and builds the poller, so
this module constructs neither.

The wrapper serialises the requests. This module decides what to ask for and
what the answers mean, so it holds no lock. A board command runs on the thread
that calls it, so it does not wait for a poll slot.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, cast

from ska_low_mccs_common.component import HardwareClientResponseStatusCodes
from ska_tango_base.poller import Poller, PollModel

from .client_wrapper import WebHardwareClientWrapper
from .constants import (
    BATCH_ATTRIBUTES,
    COMMAND_POLL_INTERVAL,
    COMMAND_TIMEOUT,
    ClientCommand,
    HttpError,
    RequestError,
)
from .derived_values import DerivedValues

__all__ = [
    "BoardCommandStatus",
    "Subrack",
    "SubrackPoller",
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


SubrackPoller = Poller[tuple[str, ...], SubrackPollResponse]
"""The poller that drives a :py:class:`Subrack`.

The caller builds one of these around a subrack, and owns it. A subrack holds
no poller of its own, so the two are built in order rather than at once.
"""


class Subrack(PollModel[tuple[str, ...], SubrackPollResponse]):
    """
    A polling client for an SPS subrack management board.

    A Tango device holds one of these, and a ``SubrackPoller`` built
    around it. The poller owns the thread and its lifetime, and this class
    supplies the work: it answers each poll, and it runs board commands.

    Each poll reads a batch of attributes over HTTP, then the health status. A
    transport failure is raised as :py:class:`RequestError` or
    :py:class:`HttpError`, so the poller routes it to :py:meth:`poll_failed`.
    An error that the board itself reports gives a value of ``None`` instead,
    which the device turns into invalid attribute quality.

    :py:class:`~.derived_values.DerivedValues` supplies the computed values.

    Every callback runs on the one polling thread, so they never overlap.
    Stopping the poller does not block, so a poll already in flight still
    reports back. ``stopped_callback`` runs after that last report, which is
    how a caller settles its own state once polling has really ended.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self: Subrack,
        client: WebHardwareClientWrapper,
        derived: DerivedValues,
        logger: logging.Logger,
        data_callback: Callable[[SubrackPollResponse], None],
        error_callback: Callable[[Exception], None],
        stopped_callback: Callable[[], None],
    ) -> None:
        """
        Initialise a new instance.

        :param client: the client wrapper to reach the management board with.
            The caller builds it and chooses its address, so this class never
            opens a connection of its own. It serialises every access to the
            board, so this class holds no lock.
        :param derived: the values that are computed rather than read. It owns
            all state that spans polls, and every poll hands it the new values.
        :param logger: a logger for this client to use.
        :param data_callback: called with each successful poll response.
        :param error_callback: called with the exception from a failed poll.
        :param stopped_callback: called once polling has stopped, after the
            last poll has reported back.
        """
        self._logger = logger
        self._client = client
        self._derived = derived
        self._data_callback = data_callback
        self._error_callback = error_callback
        self._stopped_callback = stopped_callback

    # ----------------
    # PollModel hooks
    # ----------------
    def get_request(self: Subrack) -> tuple[str, ...]:
        """
        Return the hardware read keys that the next poll should fetch.

        :return: every batched attribute.
        """
        return BATCH_ATTRIBUTES

    def poll(self: Subrack, poll_request: tuple[str, ...]) -> SubrackPollResponse:
        """
        Perform one poll of the subrack over HTTP.

        Every poll also reads the health status. One read covers both, so no
        command lands part way through the sweep.

        :param poll_request: the hardware read keys to fetch.

        :return: the poll response.
        """
        health = ClientCommand.GET_HEALTH_STATUS.value
        (attributes, commands) = self._client.read(
            poll_request, (health,), context="poll sweep"
        )

        values = {
            key: self._value_of(key, attributes[key], "value") for key in poll_request
        }
        # The client types retvalue as str, but get_health_status returns a
        # nested dictionary.
        health_status = cast(
            Optional[dict], self._value_of(health, commands[health], "retvalue")
        )

        self._derived.apply(values, health_status)

        return SubrackPollResponse(
            values=values, health_status=health_status, timestamp=time.time()
        )

    def polling_stopped(self: Subrack) -> None:
        """
        Tell the stopped callback that polling has ended.

        The poller calls this on the polling thread once the polling loop has
        exited, which is after the last poll has reported back.
        """
        self._stopped_callback()

    def poll_succeeded(self: Subrack, poll_response: SubrackPollResponse) -> None:
        """
        Give a successful poll response to the data callback.

        :param poll_response: the response to the poll.
        """
        self._data_callback(poll_response)

    def poll_failed(self: Subrack, exception: Exception) -> None:
        """
        Give a poll failure to the error callback.

        The caches of values that span polls are cleared, because a board we
        cannot reach has no known fan history and no known sample window.

        :param exception: the exception raised by the poll.
        """
        self._derived.clear()
        self._error_callback(exception)

    # ----------------
    # Reads
    # ----------------
    def _value_of(self: Subrack, name: str, response: Any, key: str) -> Any:
        """
        Return the value in one client response, or ``None`` if it has none.

        A board that answers but supplies nothing gives ``None``, which the
        device turns into invalid attribute quality. Only a failure to reach
        the board at all raises, so that the poller routes it to
        :py:meth:`poll_failed` and the device changes operational state.

        :param name: the attribute or command that was asked for, for the log.
        :param response: the response the client gave for it.
        :param key: which field of the response carries the value. An
            attribute read answers in ``value`` and a command in ``retvalue``.

        :raises HttpError: if the board answered with an HTTP error.
        :raises RequestError: if the request never reached the board.
        :raises ValueError: if the client returns an unknown status code.

        :return: the value, or ``None`` when the board did not supply one.
        """
        status = response["status"]
        if status == _OK:
            return response[key]
        if status == _HTTP_ERROR:
            raise HttpError(str(response["info"]))
        if status == _REQUEST_EXCEPTION:
            raise RequestError(str(response["info"]))
        if status in _IN_BAND_ERRORS:
            self._logger.warning(
                "'%s' returned status '%s'. %s",
                name,
                status,
                response["info"],
            )
        elif status not in _BOARD_BUSY:
            raise ValueError(
                f"Unknown status code '{status}' reading '{name}'. "
                "Check the hardware client."
            )
        # An in-band error, or a board too busy to answer. Either way this
        # value is unknown until the next poll.
        return None

    # ----------------
    # Board commands
    # ----------------
    def run_board_command(
        self: Subrack,
        name: str,
        args: str = "",
        abort_event: Optional[threading.Event] = None,
    ) -> tuple[BoardCommandStatus, str, Any]:
        """
        Run one SMB board command and handle the asynchronous handshake.

        An SMB command that reports ``STARTED`` is asynchronous. This then
        probes ``command_completed`` until the command finishes, times out, or
        is aborted. The board is free between those probes, so a poll can run
        in the gaps and read a board that is busy.

        The command runs on the calling thread, so it does not wait for a poll
        slot.

        :param name: the SMB command name.
        :param args: the SMB command argument string.
        :param abort_event: an event that requests an abort when set.

        :return: the status, a message, and the returned value.
        """
        try:
            return self._run_board_command(name, args, abort_event)
        except TimeoutError as busy:
            return (
                BoardCommandStatus.FAILED,
                f"Command '{name}' gave up. {busy}",
                None,
            )

    def _run_board_command(
        self: Subrack,
        name: str,
        args: str,
        abort_event: Optional[threading.Event],
    ) -> tuple[BoardCommandStatus, str, Any]:
        """
        Run one SMB board command, letting a busy board raise.

        :param name: the SMB command name.
        :param args: the SMB command argument string.
        :param abort_event: an event that requests an abort when set.

        :return: the status, a message, and the returned value.
        """
        response = self._client.execute_command(name, args)
        status = response["status"]
        # The board reports both of these either as a status or, when the status
        # is OK, as the returned value.
        retvalue = response["retvalue"] if status == _OK else None

        if _STARTED in (status, retvalue):
            return self._await_command_completion(name, abort_event)
        if status == _BUSY or retvalue == "FAILED":
            return (
                BoardCommandStatus.FAILED,
                f"The board did not accept command '{name}'. It is busy.",
                None,
            )
        if status == _OK:
            return (BoardCommandStatus.COMPLETED, "The command completed.", retvalue)
        return (
            BoardCommandStatus.FAILED,
            f"Command '{name}' failed with status '{status}'. " f"{response['info']}",
            None,
        )

    def _abort_board_command(self: Subrack) -> None:
        """
        Ask the board to abort the command it is running.

        A board that does not accept the abort is logged and not raised.
        """
        response = self._client.execute_command(ClientCommand.ABORT_COMMAND.value)
        if response["status"] != _OK:
            self._logger.error(
                "The board did not accept abort_command. Status '%s'. %s",
                response["status"],
                response["info"],
            )

    def _await_command_completion(
        self: Subrack, name: str, abort_event: Optional[threading.Event]
    ) -> tuple[BoardCommandStatus, str, Any]:
        """
        Probe ``command_completed`` until the board command finishes.

        :param name: the name of the command being awaited, for the message.
        :param abort_event: an event that requests an abort when set.

        :return: the status, a message, and the returned value.
        """
        abort = abort_event or threading.Event()
        deadline = time.monotonic() + COMMAND_TIMEOUT
        while time.monotonic() < deadline:
            # Wait between probes, waking at once if an abort is requested.
            if abort.wait(COMMAND_POLL_INTERVAL):
                self._abort_board_command()
                return (BoardCommandStatus.ABORTED, "The command was aborted.", None)

            response = self._client.execute_command(
                ClientCommand.COMMAND_COMPLETED.value
            )
            status = response["status"]
            if status == _OK:
                if response.get("retvalue"):
                    return (
                        BoardCommandStatus.COMPLETED,
                        "The command completed.",
                        None,
                    )
            elif status in _TRANSPORT_ERRORS:
                return (BoardCommandStatus.FAILED, str(response["info"]), None)
            elif status not in _BOARD_BUSY:
                # Anything else is the board reporting a problem, or a status
                # the client does not know. Waiting would discard the reason and
                # blame the timeout for something that will never finish.
                return (
                    BoardCommandStatus.FAILED,
                    f"Command '{name}' failed while completing, with status "
                    f"'{status}'. {response['info']}",
                    None,
                )

        return (
            BoardCommandStatus.FAILED,
            "Timed out waiting for the command to complete.",
            None,
        )
