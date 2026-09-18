#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the client wrapper that reaches one management board.

The board fails every request while a command is active, so only one operation
may reach it at a time. These tests cover the lock that enforces that, which
the wrapper takes for the whole of each operation it offers.

The command handshake is covered through
:py:meth:`~ska_low_mccs_spshw.prototype_subrack.Subrack.run_board_command` in
``test_subrack_client``, which is the caller that runs commands.
"""

from __future__ import annotations

import logging
import threading
from typing import Any
from unittest import mock

import pytest
from ska_low_mccs_common.component import HardwareClient

from ska_low_mccs_spshw.tile.utils import LogLock

from .conftest import make_client_wrapper


def _read_one_attribute(board: HardwareClient) -> Any:
    """
    Read a single attribute, as something for a hold to be taken around.

    :param board: the hardware client, held for the whole of this.

    :return: whatever the client answered.
    """
    return board.get_attribute("tpm_present")


@pytest.fixture(name="events")
def events_fixture() -> list[str]:
    """
    Return the list that records what reached the board, and when.

    The lock and the client write to the one list, so a test can assert that
    every request falls between the hold being taken and freed. That is the
    property these tests are about, and in this form it is the order of the
    list itself.

    :return: the events so far.
    """
    return []


@pytest.fixture(name="client")
def client_fixture(events: list[str]) -> mock.Mock:
    """
    Return the hardware client that the wrapper passes calls to.

    Each call is recorded and then answered as normal, because the side
    effects return ``mock.DEFAULT``.

    :param events: the list to record the requests in.

    :return: a mock hardware client.
    """
    client = mock.Mock(name="client")
    client.execute_command.return_value = {
        "status": "OK",
        "info": "",
        "command": "",
        "retvalue": "",
    }

    def record_read(name: str) -> Any:
        events.append(f"read {name}")
        return mock.DEFAULT

    def record_command(name: str, parameters: str = "") -> Any:
        events.append(f"command {name}")
        return mock.DEFAULT

    client.get_attribute.side_effect = record_read
    client.execute_command.side_effect = record_command
    return client


@pytest.fixture(name="lock")
def lock_fixture(events: list[str]) -> mock.Mock:
    """
    Return a stand-in for the client lock, which records when it is held.

    A stand-in rather than a real lock, because what these tests assert is
    that the wrapper takes the hold once and frees it, not that a
    :py:class:`~ska_low_mccs_spshw.tile.utils.LogLock` excludes anybody. That
    is the lock's own business. It is specced, so
    :py:func:`~ska_low_mccs_spshw.tile.utils.acquire_timeout` still treats it
    as the real class.

    :param events: the list to record the hold in.

    :return: a mock lock, which grants every acquire.
    """
    lock = mock.Mock(spec=LogLock)

    def take(timeout: float, context: str) -> bool:
        events.append(f"held for {context}")
        return True

    lock.acquire.side_effect = take
    lock.release.side_effect = lambda: events.append("freed")
    return lock


class TestSerialisesAccess:
    """
    Tests that only one operation reaches the board at a time.

    Every operation the wrapper offers takes the lock for the whole of itself,
    so a caller has nothing to hold. Most of these drive a stand-in lock and
    assert the order of what it recorded, which needs no thread and no clock.
    The last one runs a real lock against a second thread, because a stand-in
    can show that the wrapper asked for the hold but not that the hold works.
    """

    def test_an_operation_is_one_hold_around_every_request(
        self: TestSerialisesAccess,
        client: mock.Mock,
        lock: mock.Mock,
        logger: logging.Logger,
        events: list[str],
    ) -> None:
        """
        An operation must take the hold once, however many requests it makes.

        Taking it per request would free the board between them, which is what
        the handshake after an asynchronous command must not allow.

        :param client: the mock hardware client.
        :param lock: the stand-in client lock.
        :param logger: a logger.
        :param events: what reached the board, in order.
        """
        wrapper = make_client_wrapper(client, logger, lock=lock)

        def handshake(board: HardwareClient) -> None:
            board.execute_command("turn_on_tpms", "")
            board.execute_command("command_completed", "")

        wrapper.run_exclusively("command turn_on_tpms", handshake)

        assert events == [
            "held for command turn_on_tpms",
            "command turn_on_tpms",
            "command command_completed",
            "freed",
        ]

    def test_a_board_that_is_not_free_is_never_reached(
        self: TestSerialisesAccess,
        client: mock.Mock,
        lock: mock.Mock,
        logger: logging.Logger,
        events: list[str],
    ) -> None:
        """
        A hold that does not come free must raise, having made no request.

        The poller routes the exception to ``poll_failed``, which the device
        turns into ``UNKNOWN``. A request that went ahead anyway would report a
        value the board never gave.

        :param client: the mock hardware client.
        :param lock: the stand-in client lock.
        :param logger: a logger.
        :param events: what reached the board, in order.
        """
        # A lock that never comes free, without anything having to hold it.
        lock.acquire.side_effect = None
        lock.acquire.return_value = False
        wrapper = make_client_wrapper(client, logger, lock=lock)

        with pytest.raises(TimeoutError):
            wrapper.run_exclusively("poll sweep", _read_one_attribute)

        assert events == []
        lock.release.assert_not_called()

    def test_the_board_is_freed_when_an_operation_raises(
        self: TestSerialisesAccess,
        client: mock.Mock,
        lock: mock.Mock,
        logger: logging.Logger,
        events: list[str],
    ) -> None:
        """
        An operation must free the board even when it raises.

        A client that raises must not strand the hold, or every later poll
        would time out against a board that is perfectly healthy.

        :param client: the mock hardware client.
        :param lock: the stand-in client lock.
        :param logger: a logger.
        :param events: what reached the board, in order.
        """
        client.get_attribute.side_effect = ValueError("the client gave up")
        wrapper = make_client_wrapper(client, logger, lock=lock)

        with pytest.raises(ValueError):
            wrapper.run_exclusively("poll sweep", _read_one_attribute)

        assert events == ["held for poll sweep", "freed"]

    def test_another_thread_really_is_shut_out(
        self: TestSerialisesAccess,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A second thread must be refused for the whole of a hold.

        This one uses the real lock, because the others prove only that the
        wrapper asks for a hold. Whether the hold shuts anybody out is what
        this asserts, and nothing but a second thread can show it. The wait is
        driven from inside the operation, so it happens while the hold is on.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger, lock_timeout=0.01)
        outcome: list[Any] = []

        def poll_from_another_thread() -> None:
            try:
                outcome.append(
                    wrapper.run_exclusively("poll sweep", _read_one_attribute)
                )
            except TimeoutError as busy:
                outcome.append(busy)

        def wait_for_it_while_the_board_is_held(_: Any) -> None:
            thread = threading.Thread(target=poll_from_another_thread, daemon=True)
            thread.start()
            thread.join(5.0)

        wrapper.run_exclusively(
            "command turn_on_tpms", wait_for_it_while_the_board_is_held
        )

        assert isinstance(outcome[0], TimeoutError)
        client.get_attribute.assert_not_called()
