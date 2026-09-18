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

The lock is private, so a caller never names it or releases it. Anything that
must reach the board without interruption, whether a poll sweep or the
handshake that follows an asynchronous command, is handed to
:py:meth:`~WebHardwareClientWrapper.run_exclusively`, which holds the board for
the whole of it.

No caller ever acquires or releases anything. Every hold begins and ends inside
this class, so no other layer has to get the concurrency right.

Nothing here reads a response, or decides how many requests an operation is
worth making. The caller writes the operation, so what a status means, and when
one makes carrying on pointless, stay with the code that already understands
them.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional, TypeVar

from ska_low_mccs_common.component import HardwareClient

from ..tile.utils import LogLock, acquire_timeout
from .constants import LOCK_TIMEOUT, LOCK_WARNING

__all__ = ["WebHardwareClientWrapper"]

T = TypeVar("T")


# One public method is the whole of it. This class owns the lock, and what to do
# while the board is held belongs to the caller.
class WebHardwareClientWrapper:  # pylint: disable=too-few-public-methods
    """
    A hardware client wrapper that serialises every access to one board.

    :py:meth:`run_exclusively` takes the lock for the whole of the operation it
    is given, so a caller has nothing to hold and nothing to release. One
    operation covers a whole poll sweep, which is what keeps a command from
    landing part way through it, and equally covers a command that no single
    request completes, so a poll cannot land part way through that either.

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
