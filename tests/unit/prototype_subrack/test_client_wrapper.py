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

import contextlib
import logging
import threading
from typing import Any, Iterator
from unittest import mock

import pytest

from ska_low_mccs_spshw.tile.utils import LogLock, acquire_timeout

from .conftest import make_client_wrapper


@pytest.fixture(name="client")
def client_fixture() -> mock.Mock:
    """
    Return the hardware client that the wrapper passes calls to.

    :return: a mock hardware client.
    """
    client = mock.Mock(name="client")
    client.execute_command.return_value = {
        "status": "OK",
        "info": "",
        "command": "",
        "retvalue": "",
    }
    return client


@contextlib.contextmanager
def held(lock: LogLock) -> Iterator[None]:
    """
    Hold the lock on another thread for the duration of the block.

    The lock is reentrant, so a second thread is needed to hold it against the
    caller. Events carry the handshake in both directions.

    :param lock: the lock to hold.

    :yields: once the other thread holds the lock.
    """
    holding = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with acquire_timeout(lock, 5.0, context="stalled operation"):
            holding.set()
            release.wait(5.0)

    thread = threading.Thread(target=hold, daemon=True)
    thread.start()
    assert holding.wait(5.0), "the holder thread never acquired the lock"
    try:
        yield
    finally:
        release.set()
        thread.join(5.0)


class TestPassesCallsThrough:
    """Tests that the wrapper gives the client every call unchanged."""

    def test_a_command_reaches_the_client(
        self: TestPassesCallsThrough,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A command must reach the client, arguments and all.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger)

        wrapper.execute_command("turn_on_tpm", "1")

        client.execute_command.assert_called_once_with("turn_on_tpm", "1")

    def test_a_command_defaults_to_no_arguments(
        self: TestPassesCallsThrough,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A command given no arguments must still reach the client with a string.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger)

        wrapper.execute_command("command_completed")

        client.execute_command.assert_called_once_with("command_completed", "")


class TestReadsABatch:
    """Tests of the batch read that a poll sweep is made of."""

    def test_it_reads_every_name_in_order(
        self: TestReadsABatch,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch must read every attribute, then run every command.

        The order matters, because the board answers a command with the state
        that the attribute reads have already reported.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger)

        wrapper.read(("tpm_present", "board_current"), ("get_health_status",), "sweep")

        assert client.get_attribute.call_args_list == [
            mock.call("tpm_present"),
            mock.call("board_current"),
        ]
        client.execute_command.assert_called_once_with("get_health_status", "")

    def test_it_returns_a_response_for_every_name(
        self: TestReadsABatch,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch must answer every name it was given, under that name.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger)

        (attributes, commands) = wrapper.read(
            ("tpm_present", "board_current"), ("get_health_status",), "sweep"
        )

        assert sorted(attributes) == ["board_current", "tpm_present"]
        assert list(commands) == ["get_health_status"]
        assert attributes["tpm_present"] is client.get_attribute.return_value

    def test_an_empty_batch_reaches_the_board_for_nothing(
        self: TestReadsABatch,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch of no names must make no request at all.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger)

        (attributes, commands) = wrapper.read((), (), "sweep")

        assert not attributes
        assert not commands
        client.get_attribute.assert_not_called()
        client.execute_command.assert_not_called()


class TestSerialisesAccess:
    """
    Tests that only one operation reaches the board at a time.

    Every operation the wrapper offers takes the lock for the whole of itself.
    A caller has nothing to hold, so these drive each operation against a lock
    that another thread already holds.
    """

    def test_a_batch_read_takes_the_lock(
        self: TestSerialisesAccess,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch read must take the lock, so no command lands part way through.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        lock = LogLock("busy", logger)
        wrapper = make_client_wrapper(client, logger, lock=lock, lock_timeout=0.01)

        with held(lock):
            with pytest.raises(TimeoutError):
                wrapper.read(("tpm_present",), (), "poll sweep")

        client.get_attribute.assert_not_called()

    def test_the_lock_is_taken_once_for_a_whole_batch(
        self: TestSerialisesAccess,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch must take the lock once, not once per name.

        Taking it again would overwrite the holder that the batch recorded, so
        the log would name the last read rather than the sweep that stalled.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        lock = LogLock("sweep", logger)
        # Counts acquires while still taking the real lock. The bound method is
        # read before the attribute shadows it, so the side effect is the
        # original.
        acquire = mock.Mock(side_effect=lock.acquire)
        lock.acquire = acquire  # type: ignore[method-assign]
        wrapper = make_client_wrapper(client, logger, lock=lock)

        wrapper.read(
            ("tpm_present", "board_current"), ("get_health_status",), "poll sweep"
        )

        assert acquire.call_count == 1
        assert acquire.call_args.kwargs["context"] == "poll sweep"

    def test_the_lock_is_freed_when_a_read_raises(
        self: TestSerialisesAccess,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A batch must free the lock even when a read raises.

        A client that raises must not strand the lock, or every later poll
        would time out against a board that is perfectly healthy.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger, lock_timeout=0.01)
        client.get_attribute.side_effect = ValueError("the client gave up")

        with pytest.raises(ValueError):
            wrapper.read(("tpm_present",), (), "poll sweep")

        client.get_attribute.side_effect = None
        assert wrapper.read(("tpm_present",), (), "poll sweep")[0]

    def test_another_thread_waits_for_a_batch_read(
        self: TestSerialisesAccess,
        client: mock.Mock,
        logger: logging.Logger,
    ) -> None:
        """
        A command on another thread must be refused while a batch read runs.

        The batch is held over the calls the client makes, so the wait is
        driven from inside the client rather than around the wrapper.

        :param client: the mock hardware client.
        :param logger: a logger.
        """
        wrapper = make_client_wrapper(client, logger, lock_timeout=0.01)
        outcome: list[Any] = []

        def run_a_command_from_another_thread(_: str) -> Any:
            def call_it() -> None:
                try:
                    outcome.append(wrapper.execute_command("turn_on_tpm", "1"))
                except TimeoutError as busy:
                    outcome.append(busy)

            thread = threading.Thread(target=call_it, daemon=True)
            thread.start()
            thread.join(5.0)
            return mock.DEFAULT

        client.get_attribute.side_effect = run_a_command_from_another_thread

        wrapper.read(("tpm_present",), (), "poll sweep")

        assert isinstance(outcome[0], TimeoutError)
        client.execute_command.assert_not_called()
