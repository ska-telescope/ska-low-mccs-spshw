#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A hardware client that lets one operation reach the board at a time.

The SMB fails every request while a command is active, so requests must not
overlap. :py:class:`WebHardwareClientWrapper` owns the lock that enforces that,
and passes each call through to a
:py:class:`~ska_low_mccs_common.component.WebHardwareClient`.

The lock is private, so a caller never names it or releases it. A caller that
needs several reads to reach the board together asks for them in one
:py:meth:`~WebHardwareClientWrapper.read`. A caller whose operation spans
several requests, such as the handshake that follows an asynchronous command,
hands it to :py:meth:`~WebHardwareClientWrapper.run_exclusively`, which holds
the board for the whole of it.

No caller ever acquires or releases anything. Every hold begins and ends inside
this class, so no other layer has to get the concurrency right.

Nothing here reads a response. Every method hands back what the client gave, so
what a status means is the caller's business.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Optional, TypeVar

from ska_low_mccs_common.component import HardwareClient
from ska_low_mccs_common.component.hardware_client import (
    AttributeResponseType,
    CommandResponseType,
)

from ..tile.utils import LogLock, acquire_timeout
from .constants import LOCK_TIMEOUT, LOCK_WARNING

__all__ = ["WebHardwareClientWrapper"]

T = TypeVar("T")


class WebHardwareClientWrapper:
    """
    A hardware client wrapper that serialises every access to one board.

    Each method takes the lock for the whole of itself, so a caller has nothing
    to hold and nothing to release. :py:meth:`read` covers a batch, which is
    what keeps a command from landing part way through a poll sweep.
    :py:meth:`run_exclusively` covers an operation that no single request
    completes, so a poll cannot land part way through that either.

    A lock that does not come free in time raises ``TimeoutError``, because the
    request never reached the board. The poller routes that to ``poll_failed``,
    and a command reports it as a failure.

    The lock is reported through a :py:class:`~...tile.utils.LogLock`, so a long
    hold and the operation that caused it are visible in the log.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self: WebHardwareClientWrapper,
        client: HardwareClient,
        name: str,
        logger: logging.Logger,
        lock_timeout: float = LOCK_TIMEOUT,
        lock_warning: float = LOCK_WARNING,
        _lock: Optional[LogLock] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param client: the hardware client to reach the management board with.
            The caller builds it and chooses its address, so this class never
            opens a connection of its own.
        :param name: what to call this board in the log, such as its host
            name. A lock hold is reported against this name, so it must tell
            one board from another.
        :param logger: a logger for this wrapper to use.
        :param lock_timeout: how long, in seconds, to wait for the lock before
            giving up. This bounds how long a stalled board can block a caller.
        :param lock_warning: how long, in seconds, a lock hold must exceed
            before it is logged.
        :param _lock: an alternative lock, for testing only.
        """
        self._client = client
        self._lock_timeout = lock_timeout
        self._lock = _lock or LogLock(
            f"subrack-{name}", logger, timeout_warning=lock_warning
        )

    def read(
        self: WebHardwareClientWrapper,
        attributes: Sequence[str],
        commands: Sequence[str],
        context: str,
    ) -> tuple[dict[str, AttributeResponseType], dict[str, CommandResponseType]]:
        """
        Read a batch of attributes, then run a batch of read-only commands.

        The board is held for the whole batch, so nothing else reaches it part
        way through. Every name asked for is answered, in the order given.

        :param attributes: the attribute names to read.
        :param commands: the names of the commands to run, each with no
            arguments. These are for commands that only report, such as
            ``get_health_status``.
        :param context: what the caller is doing, reported alongside the holder
            when the hold is long enough to be logged.

        :return: the attribute responses and the command responses, each keyed
            by the name that was asked for.
        """
        with acquire_timeout(
            self._lock, self._lock_timeout, raise_exception=True, context=context
        ):
            return (
                {name: self._client.get_attribute(name) for name in attributes},
                {name: self._client.execute_command(name, "") for name in commands},
            )

    def execute_command(
        self: WebHardwareClientWrapper, command: str, parameters: str = ""
    ) -> CommandResponseType:
        """
        Run one command on the board, holding it for that one request.

        This is for a command the board completes within the request. A command
        the board runs asynchronously is not finished when this returns, and the
        board is free the moment it does, so hand that to
        :py:meth:`run_exclusively` instead.

        :param command: the name of the command to run.
        :param parameters: the command's argument string.

        :return: the client's response.
        """
        with acquire_timeout(
            self._lock,
            self._lock_timeout,
            raise_exception=True,
            context=f"command {command}",
        ):
            return self._client.execute_command(command, parameters)

    def run_exclusively(
        self: WebHardwareClientWrapper,
        context: str,
        operation: Callable[[HardwareClient], T],
    ) -> T:
        """
        Run one operation with the board held for the whole of it.

        The SMB fails every request while a command is active, so an
        asynchronous command owns the board until its handshake ends, not just
        for the request that started it. The operation is called with the
        client this wrapper holds, so every request it makes is covered by the
        one hold.

        The caller hands over the work rather than the other way about, so it
        never acquires or releases anything, and it cannot keep the board past
        the end of the operation. The board is freed however the operation
        ended.

        :param context: what the caller is doing, reported alongside the holder
            when the hold is long enough to be logged.
        :param operation: what to do while the board is held. It is called with
            the hardware client, and whatever it returns is returned.

        :return: whatever the operation returned.
        """
        with acquire_timeout(
            self._lock, self._lock_timeout, raise_exception=True, context=context
        ):
            return operation(self._client)
