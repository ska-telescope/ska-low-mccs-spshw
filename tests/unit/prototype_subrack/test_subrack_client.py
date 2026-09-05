#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
# pylint: disable=too-many-lines
"""
Tests of the prototype subrack client.

Most tests drive an injected fake hardware client. Two run against a real
simulator server over HTTP, and three assert that the fake answers in the same
shape as the real client.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
from typing import Any, Iterator
from unittest import mock

import pytest
from ska_low_mccs_common.component import (
    HardwareClientResponseStatusCodes,
    WebHardwareClient,
)

from ska_low_mccs_spshw.prototype_subrack import (
    BoardCommandStatus,
    HttpError,
    RequestError,
    Subrack,
    SubrackPollResponse,
    subrack_client,
)
from ska_low_mccs_spshw.prototype_subrack.constants import BATCH_ATTRIBUTES
from ska_low_mccs_spshw.tile.utils import LogLock, acquire_timeout

from .conftest import FakeHardwareClient, make_subrack


def _next_response(
    responses: queue.SimpleQueue, timeout: float = 10.0
) -> SubrackPollResponse | Exception:
    """
    Return the next thing the client gave to a callback.

    :param responses: the queue that the callbacks feed.
    :param timeout: how long, in seconds, to wait.

    :raises AssertionError: if no callback arrives in time.

    :return: a poll response or an exception.
    """
    try:
        return responses.get(timeout=timeout)
    except queue.Empty as empty:
        raise AssertionError(f"No callback within {timeout} seconds.") from empty


def _next_poll(
    responses: queue.SimpleQueue, timeout: float = 10.0
) -> SubrackPollResponse:
    """
    Return the next successful poll response.

    :param responses: the queue that the callbacks feed.
    :param timeout: how long, in seconds, to wait.

    :return: a poll response.
    """
    result = _next_response(responses, timeout)
    assert isinstance(result, SubrackPollResponse), f"Expected a response, got {result}"
    return result


class TestAgainstSimulator:
    """
    Tests of the client against a simulator server over HTTP.

    These use the real
    :py:class:`~ska_low_mccs_common.component.WebHardwareClient` over a socket.
    """

    def test_poll_reads_every_batched_attribute(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
        responses: queue.SimpleQueue,
        subrack_simulator_config: dict[str, Any],
    ) -> None:
        """
        Every batched attribute must arrive, with the configured values.

        :param simulated_subrack: the client under test.
        :param responses: the queue that the callbacks feed.
        :param subrack_simulator_config: the simulator configuration.
        """
        response = _next_poll(responses)

        for key in BATCH_ATTRIBUTES:
            assert key in response.values, f"'{key}' missing from the poll response"

        assert response.values["tpm_present"] == subrack_simulator_config["tpm_present"]
        assert (
            response.values["backplane_temperatures"]
            == subrack_simulator_config["backplane_temperatures"]
        )
        assert response.timestamp > 0.0

    def test_board_command_runs_while_polling(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
        responses: queue.SimpleQueue,
    ) -> None:
        """
        A board command must not wait for a poll slot.

        The command and the poll loop share one lock, and the command takes it
        on the thread that calls it.

        :param simulated_subrack: the client under test.
        :param responses: the queue that the callbacks feed.
        """
        _next_poll(responses)

        (status, message, _) = simulated_subrack.run_board_command("turn_on_tpm", "5")
        assert status == BoardCommandStatus.COMPLETED, message

        # Polling must survive the command.
        assert _next_poll(responses).values["tpm_present"] is not None


class TestWhatTheClientAsksTheBoard:
    """
    Tests of the calls the client makes to the board.

    The fake records through mocks, so the sequence of calls can be asserted
    as well as the response the client builds from them.
    """

    def test_a_poll_reads_every_batched_attribute_once_in_order(
        self: TestWhatTheClientAsksTheBoard,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        One poll must read each batched attribute exactly once, in order.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_attribute_response(value=None)

        faked_subrack.poll(faked_subrack.get_request())

        assert fake_client.get_attribute.call_args_list == [
            mock.call(key) for key in BATCH_ATTRIBUTES
        ]

    def test_a_poll_runs_no_command_but_the_health_read(
        self: TestWhatTheClientAsksTheBoard,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A poll must not run board commands of its own.

        Commands go through ``run_board_command`` on the caller's thread. The
        only command a poll issues is the health status read.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_attribute_response(value=None)

        faked_subrack.poll(faked_subrack.get_request())

        assert fake_client.command_calls == [("get_health_status", "")]

    def test_a_command_is_passed_through_verbatim(
        self: TestWhatTheClientAsksTheBoard,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A command and its argument must reach the board unchanged.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        faked_subrack.run_board_command("set_subrack_fan_speed", "2,55")

        fake_client.execute_command.assert_any_call("set_subrack_fan_speed", "2,55")


class TestHealthRead:
    """
    Tests of the health status read.

    The health read is the only board command a poll issues, and every poll
    issues it.
    """

    def test_every_poll_reads_the_health_status(
        self: TestHealthRead,
        healthy_faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        Each poll must read the health status and carry what the board gave.

        :param healthy_faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        request = healthy_faked_subrack.get_request()

        for _ in range(2):
            response = healthy_faked_subrack.poll(request)
            assert response.health_status == {"psus": {}}

        health_reads = [
            c for c in fake_client.command_calls if c[0] == "get_health_status"
        ]
        assert len(health_reads) == 2

    @pytest.mark.parametrize(
        "status",
        [
            HardwareClientResponseStatusCodes.ERROR.name,
            HardwareClientResponseStatusCodes.JSON_DECODE_ERROR.name,
            HardwareClientResponseStatusCodes.BUSY.name,
            HardwareClientResponseStatusCodes.STARTED.name,
        ],
    )
    def test_a_health_status_the_board_cannot_supply_is_unknown(
        self: TestHealthRead,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
    ) -> None:
        """
        A board that answers but supplies no health status must give ``None``.

        The poll still succeeds, so the read is retried on the next poll.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the status the board reports for the health read.
        """
        fake_client.set_command_responses(
            "get_health_status",
            {
                "status": status,
                "info": "No health status",
                "command": "get_health_status",
                "retvalue": "",
            },
        )

        assert faked_subrack.poll(faked_subrack.get_request()).health_status is None

    @pytest.mark.parametrize(
        ("status", "info", "expected"),
        [
            (
                HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
                "Connection refused",
                RequestError,
            ),
            (
                HardwareClientResponseStatusCodes.HTTP_ERROR.name,
                "HTML status 500",
                HttpError,
            ),
        ],
    )
    # pylint: disable-next=too-many-arguments
    def test_a_transport_failure_fails_the_whole_poll(
        self: TestHealthRead,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
        info: str,
        expected: type[Exception],
    ) -> None:
        """
        A transport failure on the health read must fail the poll.

        The attribute sweep succeeded, but a board we can no longer reach is
        not a board with a partial answer, so the poller must route this to
        ``poll_failed`` rather than report a poll with no health status.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the transport status the client reports.
        :param info: the detail the client reports with it.
        :param expected: the exception the poll must raise.
        """
        fake_client.set_command_responses(
            "get_health_status",
            {
                "status": status,
                "info": info,
                "command": "get_health_status",
                "retvalue": "",
            },
        )

        with pytest.raises(expected, match=info):
            faked_subrack.poll(faked_subrack.get_request())

    def test_an_unknown_status_raises_value_error(
        self: TestHealthRead,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        An unrecognised status from the health read must raise.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "get_health_status",
            {
                "status": "NOT_A_REAL_STATUS",
                "info": "who knows",
                "command": "get_health_status",
                "retvalue": "",
            },
        )

        with pytest.raises(ValueError, match="NOT_A_REAL_STATUS"):
            faked_subrack.poll(faked_subrack.get_request())


class TestErrorBranches:
    """Tests of the failure paths of a poll and of a board command."""

    @pytest.mark.parametrize(
        ("status", "info", "expected"),
        [
            (
                HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
                "Connection refused",
                RequestError,
            ),
            (
                HardwareClientResponseStatusCodes.HTTP_ERROR.name,
                "HTML status 500",
                HttpError,
            ),
        ],
    )
    # pylint: disable-next=too-many-arguments
    def test_a_transport_failure_raises_the_matching_exception(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
        info: str,
        expected: type[Exception],
    ) -> None:
        """
        A transport failure must raise, and carry what the client reported.

        The two exceptions stay distinct because the device maps them to
        different operational states. A request that never reached the board
        gives ``RequestError``, and a board that answered with an HTTP error
        gives ``HttpError``.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the transport status the client reports.
        :param info: the detail the client reports with it.
        :param expected: the exception the poll must raise.
        """
        fake_client.set_attribute_response(status=status, info=info)

        with pytest.raises(expected, match=info):
            faked_subrack.poll(faked_subrack.get_request())

    @pytest.mark.parametrize(
        "status",
        [
            HardwareClientResponseStatusCodes.ERROR.name,
            HardwareClientResponseStatusCodes.JSON_DECODE_ERROR.name,
            HardwareClientResponseStatusCodes.BUSY.name,
            HardwareClientResponseStatusCodes.STARTED.name,
        ],
    )
    def test_a_value_the_board_cannot_supply_is_unknown(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
    ) -> None:
        """
        A board that answers but supplies no value must give ``None``.

        The device turns ``None`` into invalid attribute quality, which is the
        correct outcome whether the board reported an error or was busy. Only
        a transport failure raises.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the status the board reports for every attribute.
        """
        fake_client.set_attribute_response(status=status, info="No value")

        response = faked_subrack.poll(faked_subrack.get_request())

        for key in BATCH_ATTRIBUTES:
            assert response.values[key] is None

    def test_unknown_status_raises_value_error(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        An unrecognised status code must raise.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_attribute_response(status="NOT_A_REAL_STATUS")

        with pytest.raises(ValueError, match="NOT_A_REAL_STATUS"):
            faked_subrack.poll(faked_subrack.get_request())

    def test_poll_failure_clears_the_caches(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A failed poll must clear the state that spans polls.

        A board we cannot reach has no known fan history, so the next good poll
        must start counting fan errors again from zero.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = make_subrack(fake_client, logger, max_fan_errors=1)

        # Use up the single allowed replacement.
        subrack.derived.estimate_max_fan_rpm([0.0] * 4, [100.0] * 4)
        assert subrack.derived.fan_error_counts == [1, 1, 1, 1]

        subrack.poll_failed(RequestError("gone"))
        assert subrack.derived.fan_error_counts == [0, 0, 0, 0]

    def test_error_callback_receives_the_exception(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        The error callback must receive the exception from a failed poll.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        seen: list[Exception] = []
        subrack = make_subrack(fake_client, logger, error_callback=seen.append)
        exception = HttpError("boom")

        subrack.poll_failed(exception)

        assert seen == [exception]

    @pytest.mark.parametrize(
        ("status", "retvalue"),
        [
            (HardwareClientResponseStatusCodes.BUSY.name, ""),
            (HardwareClientResponseStatusCodes.OK.name, "FAILED"),
        ],
    )
    def test_a_command_the_board_refuses_fails(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
        retvalue: str,
    ) -> None:
        """
        A command the board refuses must fail, and not hang.

        The board refuses either by reporting busy or by answering ``FAILED``,
        and both mean the command never started.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the status the board reports.
        :param retvalue: the value the board returns with it.
        """
        fake_client.set_command_responses(
            "turn_on_tpm",
            {
                "status": status,
                "info": "Board busy",
                "command": "turn_on_tpm",
                "retvalue": retvalue,
            },
        )

        (status_out, message, _) = faked_subrack.run_board_command("turn_on_tpm", "1")

        assert status_out == BoardCommandStatus.FAILED
        assert "did not accept" in message

    def test_command_transport_failure_is_reported(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A transport failure during a command must be reported, not raised.

        A command runs on the caller's thread, so the failure comes back in the
        returned status rather than as an exception.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpm",
            {
                "status": HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
                "info": "Connection refused",
                "command": "turn_on_tpm",
                "retvalue": "",
            },
        )

        (status, message, _) = faked_subrack.run_board_command("turn_on_tpm", "1")

        assert status == BoardCommandStatus.FAILED
        assert "Connection refused" in message

    def test_command_abort(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        An asynchronous command must stop when its abort event is set.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpms",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "turn_on_tpms",
                "retvalue": HardwareClientResponseStatusCodes.STARTED.name,
            },
        )
        # command_completed always reports "still running".
        fake_client.set_command_responses(
            "command_completed",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "command_completed",
                "retvalue": False,
            },
        )
        abort_event = threading.Event()
        abort_event.set()

        (status, _, _) = faked_subrack.run_board_command(
            "turn_on_tpms", "", abort_event
        )

        assert status == BoardCommandStatus.ABORTED

    def test_aborting_tells_the_board_to_abort(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        Aborting must send ``abort_command`` to the board.

        The board is the only thing that can stop the operation. Reporting the
        command aborted without telling the board leaves the operation running,
        so it still takes effect, and the board stays busy and rejects the next
        command until it finishes.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpms",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "turn_on_tpms",
                "retvalue": HardwareClientResponseStatusCodes.STARTED.name,
            },
        )
        abort_event = threading.Event()
        abort_event.set()

        faked_subrack.run_board_command("turn_on_tpms", "", abort_event)

        assert "abort_command" in [name for (name, _) in fake_client.command_calls]

    def test_a_busy_board_is_waited_for(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A board that reports busy while completing must still be waited for.

        ``BUSY`` and ``STARTED`` continue the wait, as does ``OK`` with no
        returned value. Every other status ends it.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpms",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "turn_on_tpms",
                "retvalue": HardwareClientResponseStatusCodes.STARTED.name,
            },
        )
        busy = {
            "status": HardwareClientResponseStatusCodes.BUSY.name,
            "info": "",
            "command": "command_completed",
            "retvalue": "",
        }
        done = {
            "status": HardwareClientResponseStatusCodes.OK.name,
            "info": "",
            "command": "command_completed",
            "retvalue": True,
        }
        fake_client.set_command_responses("command_completed", busy, busy, done)

        (result, message, _) = faked_subrack.run_board_command("turn_on_tpms", "")

        assert result == BoardCommandStatus.COMPLETED, message
        completions = [
            c for c in fake_client.command_calls if c[0] == "command_completed"
        ]
        assert len(completions) == 3, "it should have waited through both busy replies"

    @pytest.mark.parametrize(
        ("status", "info"),
        [
            (HardwareClientResponseStatusCodes.ERROR.name, "board fault"),
            ("NOT_A_REAL_STATUS", "who knows"),
        ],
    )
    # pylint: disable-next=too-many-arguments
    def test_an_error_while_awaiting_completion_fails_with_its_details(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        monkeypatch: pytest.MonkeyPatch,
        status: str,
        info: str,
    ) -> None:
        """
        An error from ``command_completed`` must fail with what the board said.

        The status and the detail the board reported both reach the caller, and
        the wait ends at once rather than running to the timeout.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param monkeypatch: the pytest monkeypatch fixture.
        :param status: the status the board reports while completing.
        :param info: the detail the board reports with it.
        """
        # Short, so the test does not sit through the whole timeout.
        monkeypatch.setattr(subrack_client, "COMMAND_TIMEOUT", 2.0)
        fake_client.set_command_responses(
            "turn_on_tpms",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "turn_on_tpms",
                "retvalue": HardwareClientResponseStatusCodes.STARTED.name,
            },
        )
        fake_client.set_command_responses(
            "command_completed",
            {
                "status": status,
                "info": info,
                "command": "command_completed",
                "retvalue": "",
            },
        )

        (result, message, _) = faked_subrack.run_board_command("turn_on_tpms", "")

        assert result == BoardCommandStatus.FAILED
        assert info in message, message
        assert "Timed out" not in message, message


class TestDerivedValuesWiring:
    """Tests that a poll response carries the derived values."""

    def test_the_derived_fan_speeds_reach_the_poll_response(
        self: TestDerivedValuesWiring,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A poll response must carry the estimated fan speeds.

        The board never reports this key.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(value=None)
        for key, value in [
            ("subrack_fan_speeds", [2600.0] * 4),
            ("subrack_fan_speeds_percent", [50.0] * 4),
        ]:
            fake_client.attribute_responses[key] = {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "attribute": key,
                "value": value,
            }
        subrack = make_subrack(fake_client, logger, max_fan_errors=0)

        response = subrack.poll(subrack.get_request())

        assert response.values["subrack_max_fan_speeds"] == pytest.approx([5200.0] * 4)

    def test_the_filter_is_applied_to_the_poll_values(
        self: TestDerivedValuesWiring,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A configured filter must reach the values in the poll response.

        A mean is asserted because a mean is observable.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = make_subrack(
            fake_client,
            logger,
            attribute_filter_type="mean",
            attribute_filter_max_samples=2,
        )

        fake_client.set_attribute_response(value=[0.0, 10.0])
        subrack.poll(subrack.get_request())
        fake_client.set_attribute_response(value=[10.0, 20.0])
        response = subrack.poll(subrack.get_request())

        assert response.values["tpm_currents"] == pytest.approx([5.0, 15.0])


class TestLockContention:
    """
    Tests of what happens when the client lock is not free.

    The board fails every request while a command is active, so polls and
    commands share one lock. These tests cover a lock that another operation
    still holds.
    """

    @staticmethod
    @contextlib.contextmanager
    def _held(lock: LogLock) -> Iterator[None]:
        """
        Hold the lock on another thread for the duration of the block.

        The lock is reentrant, so a second thread is needed to hold it against
        the caller. Events carry the handshake in both directions.

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

    def test_a_poll_that_cannot_get_the_lock_raises(
        self: TestLockContention,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A poll must raise when the lock stays busy.

        The poller routes the exception to ``poll_failed``, which the device
        turns into ``UNKNOWN``.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        lock = LogLock("busy", logger)
        subrack = make_subrack(fake_client, logger, lock=lock, lock_timeout=0.01)

        with self._held(lock):
            with pytest.raises(RequestError, match="still holds the client"):
                subrack.poll(subrack.get_request())

    def test_a_command_that_cannot_get_the_lock_fails(
        self: TestLockContention,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A command must fail rather than block its worker thread.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = make_subrack(fake_client, logger, lock_timeout=0.01)

        with self._held(subrack._client_lock):
            (status, message, _) = subrack.run_board_command("turn_on_tpm", "1")

        assert status == BoardCommandStatus.FAILED
        assert "busy with another operation" in message

    def test_a_poll_reports_how_long_it_held_the_lock(
        self: TestLockContention,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        A poll must report its lock hold, naming itself as the holder.

        The name is what makes a stalled board attributable to the poll rather
        than to a command. A threshold of zero reports every hold, so the test
        needs no delay.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        :param caplog: the pytest log capture fixture.
        """
        lock = LogLock("slow", logger, timeout_warning=0.0)
        subrack = make_subrack(fake_client, logger, lock=lock)
        fake_client.set_attribute_response(value=None)

        with caplog.at_level(logging.WARNING, logger=logger.name):
            subrack.poll(subrack.get_request())

        assert "lock slow held for" in caplog.text
        assert "poll sweep" in caplog.text

    def test_a_command_reports_how_long_it_held_the_lock(
        self: TestLockContention,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        A command must report its lock hold, naming the command.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        :param caplog: the pytest log capture fixture.
        """
        subrack = make_subrack(fake_client, logger, lock_warning=0.0)

        with caplog.at_level(logging.WARNING, logger=logger.name):
            subrack.run_board_command("turn_on_tpm", "1")

        assert "held for" in caplog.text
        assert "command turn_on_tpm" in caplog.text


class TestTheFakeMatchesTheRealClient:
    """
    Tests that the fake answers in the same shape as the real client.

    The fields of a fake response match those of
    :py:class:`~ska_low_mccs_common.component.WebHardwareClient`, and every
    status name the client branches on is a member of
    :py:class:`~ska_low_mccs_common.component.HardwareClientResponseStatusCodes`.
    """

    def test_the_attribute_response_shape_matches(
        self: TestTheFakeMatchesTheRealClient,
        simulator_address: tuple[str, int],
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        An attribute read must come back with the same fields either way.

        :param simulator_address: the host and port of the simulator server.
        :param fake_client: the fake hardware client.
        """
        (host, port) = simulator_address
        real = WebHardwareClient(host, port).get_attribute("board_current")

        fake = fake_client.get_attribute("board_current")

        assert sorted(fake) == sorted(real)

    def test_the_command_response_shape_matches(
        self: TestTheFakeMatchesTheRealClient,
        simulator_address: tuple[str, int],
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A command must come back with the same fields either way.

        :param simulator_address: the host and port of the simulator server.
        :param fake_client: the fake hardware client.
        """
        (host, port) = simulator_address
        real = WebHardwareClient(host, port).execute_command("command_completed", "")

        fake = fake_client.execute_command("command_completed", "")

        assert sorted(fake) == sorted(real)

    def test_the_status_codes_the_client_branches_on_all_exist(
        self: TestTheFakeMatchesTheRealClient,
    ) -> None:
        """
        Every status the client branches on must be a real status code.

        The client compares against the names of the shared enumeration's
        members.
        """
        names = {member.name for member in HardwareClientResponseStatusCodes}

        for group in (
            subrack_client._TRANSPORT_ERRORS,
            subrack_client._IN_BAND_ERRORS,
            subrack_client._BOARD_BUSY,
        ):
            assert set(group) <= names, group
        assert subrack_client._OK in names
