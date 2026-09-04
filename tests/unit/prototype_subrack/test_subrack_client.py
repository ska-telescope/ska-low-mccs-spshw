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

The good path and the asynchronous command handshake run against a real
simulator server over HTTP. The error branches run against a fake hardware
client, because a simulator cannot report a transport level failure on demand.
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
    SubrackPollRequest,
    SubrackPollResponse,
    subrack_client,
)
from ska_low_mccs_spshw.prototype_subrack.constants import BATCH_ATTRIBUTES
from ska_low_mccs_spshw.tile.utils import LogLock, acquire_timeout

from .conftest import FakeHardwareClient


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


def _make_subrack(
    client: FakeHardwareClient,
    logger: logging.Logger,
    lock: LogLock | None = None,
    **kwargs: Any,
) -> Subrack:
    """
    Return a subrack wired to a fake hardware client, with polling stopped.

    :param client: the fake hardware client.
    :param logger: a logger.
    :param lock: the client lock, defaulting to a fresh one.
    :param kwargs: overrides passed to the subrack.

    :return: a subrack client.
    """
    options: dict[str, Any] = {
        "poll_rate": 60.0,
        "command_update_rate": 1000.0,
        "data_callback": lambda _: None,
    }
    options.update(kwargs)
    return Subrack(
        "no-such-host",
        0,
        logger,
        _client=client,  # type: ignore[arg-type]
        _lock=lock,
        **options,
    )


class TestPollRequest:
    """Tests of the poll request."""

    def test_request_with_work_is_truthy(self: TestPollRequest) -> None:
        """A request that asks for something must not be skipped by the poller."""
        assert SubrackPollRequest(attribute_keys=("board_info",), fetch_health=False)
        assert SubrackPollRequest(attribute_keys=(), fetch_health=True)

    def test_empty_request_is_falsy(self: TestPollRequest) -> None:
        """A request that asks for nothing lets the poller skip the poll."""
        assert not SubrackPollRequest(attribute_keys=(), fetch_health=False)


class TestAgainstSimulator:
    """
    Tests of the client against a simulator server over HTTP.

    These use the real
    :py:class:`~ska_low_mccs_common.component.WebHardwareClient` over a socket,
    and run a command while the poll loop is running.
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
        simulated_subrack.start_polling()
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
        simulated_subrack.start_polling()
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
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        One poll must read each batched attribute exactly once, in order.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(value=None)
        subrack = _make_subrack(fake_client, logger)

        subrack.poll(subrack.get_request())

        assert fake_client.get_attribute.call_args_list == [
            mock.call(key) for key in BATCH_ATTRIBUTES
        ]

    def test_a_poll_runs_no_command_but_the_health_read(
        self: TestWhatTheClientAsksTheBoard,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A poll must not run board commands of its own.

        Commands go through ``run_board_command`` on the caller's thread. The
        only command a poll issues is the health status read.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(value=None)
        subrack = _make_subrack(fake_client, logger, command_update_rate=1000.0)

        subrack.poll(subrack.get_request())

        assert fake_client.execute_command.call_args_list == []

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


class TestHealthCadence:
    """
    Tests of when the health status is read.

    The health read is the one thing on a slower cadence than the attribute
    sweep, and it is gated on the SMB BIOS version.
    """

    @staticmethod
    def _board_info(version: str) -> dict[str, Any]:
        """
        Return a board info response body reporting the given BIOS version.

        :param version: the BIOS version string.

        :return: a board info value.
        """
        return {"SMM": {"bios": version}}

    def _subrack_with_bios(
        self: TestHealthCadence,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
        version: str | None,
        **kwargs: Any,
    ) -> Subrack:
        """
        Return a subrack whose fake board reports the given BIOS version.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        :param version: the BIOS version string, or ``None`` for no board info.
        :param kwargs: overrides passed to the subrack.

        :return: a poll subrack.
        """
        fake_client.set_attribute_response(value=None)
        if version is not None:
            fake_client.attribute_responses["board_info"] = {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "attribute": "board_info",
                "value": self._board_info(version),
            }
        fake_client.set_command_responses(
            "get_health_status",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "get_health_status",
                "retvalue": {"psus": {}},
            },
        )
        return _make_subrack(fake_client, logger, **kwargs)

    def test_health_is_read_once_per_cadence(
        self: TestHealthCadence,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A second poll inside the cadence must not read the health status again.

        The health read is the most expensive call the board serves, so it must
        not happen on every sweep.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = self._subrack_with_bios(
            fake_client, logger, "v1.6.0", command_update_rate=1000.0
        )

        assert subrack.poll(subrack.get_request()).health_status is not None
        assert subrack.poll(subrack.get_request()).health_status is None

        health_calls = [
            c for c in fake_client.command_calls if c[0] == "get_health_status"
        ]
        assert len(health_calls) == 1

    def test_old_bios_disables_the_health_read(
        self: TestHealthCadence,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A board whose BIOS is too old must never be asked for health status.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = self._subrack_with_bios(fake_client, logger, "v1.5.0")

        assert subrack.poll(subrack.get_request()).health_status is None

        assert not [c for c in fake_client.command_calls if c[0] == "get_health_status"]

    def test_unreadable_board_info_disables_the_health_read(
        self: TestHealthCadence,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A board info value we cannot parse must disable the health read.

        The gate is checked once, so an unparseable value must not leave the
        client retrying the version check on every poll.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        subrack = self._subrack_with_bios(fake_client, logger, "not-a-version")

        assert subrack.poll(subrack.get_request()).health_status is None

        assert not [c for c in fake_client.command_calls if c[0] == "get_health_status"]


class TestErrorBranches:
    """Tests of the branches a simulator cannot reach."""

    def test_request_exception_raises_request_error(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A request that never reaches the board must raise ``RequestError``.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(
            status=HardwareClientResponseStatusCodes.REQUEST_EXCEPTION.name,
            info="Connection refused",
        )
        subrack = _make_subrack(fake_client, logger)

        with pytest.raises(RequestError, match="Connection refused"):
            subrack.poll(subrack.get_request())

    def test_http_error_raises_http_error(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        An HTTP error status must raise ``HttpError``.

        The two exceptions stay distinct because the device maps them to
        different operational states.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(
            status=HardwareClientResponseStatusCodes.HTTP_ERROR.name,
            info="HTML status 500",
        )
        subrack = _make_subrack(fake_client, logger)

        with pytest.raises(HttpError, match="500"):
            subrack.poll(subrack.get_request())

    def test_in_band_error_gives_a_none_value(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        An error the board reports must give ``None`` and not raise.

        The device turns ``None`` into invalid attribute quality, which is the
        correct outcome for a board that answered but could not supply a value.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(
            status=HardwareClientResponseStatusCodes.ERROR.name,
            info="No such attribute",
        )
        subrack = _make_subrack(fake_client, logger)

        response = subrack.poll(subrack.get_request())

        for key in BATCH_ATTRIBUTES:
            assert response.values[key] is None

    def test_busy_board_leaves_values_unknown(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        A busy board must give ``None`` and not raise.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(
            status=HardwareClientResponseStatusCodes.BUSY.name,
            info="Board busy",
        )
        subrack = _make_subrack(fake_client, logger)

        response = subrack.poll(subrack.get_request())

        assert response.values["board_current"] is None

    def test_unknown_status_raises_value_error(
        self: TestErrorBranches,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        An unrecognised status code must raise.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        fake_client.set_attribute_response(status="NOT_A_REAL_STATUS")
        subrack = _make_subrack(fake_client, logger)

        with pytest.raises(ValueError, match="NOT_A_REAL_STATUS"):
            subrack.poll(subrack.get_request())

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
        subrack = _make_subrack(fake_client, logger, max_fan_errors=1)

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
        subrack = _make_subrack(fake_client, logger, error_callback=seen.append)
        exception = HttpError("boom")

        subrack.poll_failed(exception)

        assert seen == [exception]

    def test_command_on_a_busy_board_fails(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A board that reports busy must fail the command and not hang.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpm",
            {
                "status": HardwareClientResponseStatusCodes.BUSY.name,
                "info": "Board busy",
                "command": "turn_on_tpm",
                "retvalue": "",
            },
        )

        (status, message, _) = faked_subrack.run_board_command("turn_on_tpm", "1")

        assert status == BoardCommandStatus.FAILED
        assert "busy" in message

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

        ``BUSY`` and ``STARTED`` continue the wait. Every other status ends it.

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
            (HardwareClientResponseStatusCodes.JSON_DECODE_ERROR.name, "bad json"),
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

    def test_command_rejected_by_the_board(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
    ) -> None:
        """
        A board that answers ``FAILED`` must fail the command.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        fake_client.set_command_responses(
            "turn_on_tpm",
            {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": "turn_on_tpm",
                "retvalue": "FAILED",
            },
        )

        (status, message, _) = faked_subrack.run_board_command("turn_on_tpm", "1")

        assert status == BoardCommandStatus.FAILED
        assert "busy" in message


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
        subrack = _make_subrack(fake_client, logger, max_fan_errors=0)

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
        subrack = _make_subrack(
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
        subrack = _make_subrack(fake_client, logger, lock=lock, lock_timeout=0.01)

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
        subrack = _make_subrack(fake_client, logger, lock_timeout=0.01)

        with self._held(subrack._client_lock):
            (status, message, _) = subrack.run_board_command("turn_on_tpm", "1")

        assert status == BoardCommandStatus.FAILED
        assert "busy with another operation" in message
        subrack.cleanup()

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
        subrack = _make_subrack(fake_client, logger, lock=lock)
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
        subrack = _make_subrack(fake_client, logger, lock_warning=0.0)

        with caplog.at_level(logging.WARNING, logger=logger.name):
            subrack.run_board_command("turn_on_tpm", "1")

        assert "held for" in caplog.text
        assert "command turn_on_tpm" in caplog.text
        subrack.cleanup()


# pylint: disable-next=too-few-public-methods
class TestPollingThread:
    """
    Tests of the polling thread's lifetime.

    Stopping polling leaves the thread alive, and only ``cleanup`` ends it.
    """

    @staticmethod
    def _polling_threads() -> set[threading.Thread]:
        """
        Return the live polling threads.

        :return: the live polling threads.
        """
        return {t for t in threading.enumerate() if "Polling" in t.name}

    def test_cleanup_ends_the_thread(
        self: TestPollingThread,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
    ) -> None:
        """
        ``cleanup`` must end the thread, not merely stop polling.

        Stopping polling leaves the thread waiting to be asked again, so a
        client that is finished with has to be cleaned up or its thread
        outlives it. That is what the device teardown relies on.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        """
        before = self._polling_threads()
        subrack = _make_subrack(fake_client, logger)
        (thread,) = self._polling_threads() - before
        subrack.start_polling()
        subrack.stop_polling()
        assert thread.is_alive(), "stopping polling must not end the thread"

        subrack.cleanup()

        assert not thread.is_alive()
        assert self._polling_threads() == before


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
