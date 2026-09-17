#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the prototype subrack client.

Most tests drive an injected fake hardware client. Two run against a real
simulator server over HTTP.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest
from ska_low_mccs_common.component import HardwareClientResponseStatusCodes

from ska_low_mccs_spshw.prototype_subrack import (
    BoardCommandStatus,
    HttpError,
    RequestError,
    Subrack,
    SubrackPollResponse,
    WebHardwareClientWrapper,
)
from ska_low_mccs_spshw.prototype_subrack.constants import BATCH_ATTRIBUTES

from .conftest import FakeHardwareClient, make_subrack


def _ok_response() -> dict[str, Any]:
    """
    Return a client response that succeeded and carries no value.

    :return: the response.
    """
    return {
        "status": HardwareClientResponseStatusCodes.OK.name,
        "info": "",
        "command": "",
        "retvalue": None,
    }


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

    @pytest.mark.usefixtures("simulated_subrack")
    def test_poll_reads_every_batched_attribute(
        self: TestAgainstSimulator,
        responses: queue.SimpleQueue,
        subrack_simulator_config: dict[str, Any],
    ) -> None:
        """
        Every batched attribute must arrive, with the configured values.

        The subrack is already polling, so this only waits for a response.

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

        The command runs on the thread that calls it, so polling carries on
        around it.

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

    def test_a_poll_says_what_it_is_doing(
        self: TestWhatTheClientAsksTheBoard,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        A poll must tell the board what the read is for.

        The board reports a slow read against this, which is what makes a stall
        attributable to the poll rather than to a command.

        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        board = mock.Mock()
        board.read.return_value = ({}, {"get_health_status": _ok_response()})
        subrack = make_subrack(board, logger, derived)

        subrack.poll(())

        assert board.read.call_args.kwargs["context"] == "poll sweep"


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
        faked_board: WebHardwareClientWrapper,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        A failed poll must clear the state that spans polls.

        A board we cannot reach has no known fan history, so the state that
        spans polls is dropped. What that state is, and what dropping it does,
        is covered in ``test_derived_values``.

        :param faked_board: the board it reads.
        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        subrack = make_subrack(faked_board, logger, derived)

        subrack.poll_failed(RequestError("gone"))

        derived.clear.assert_called_once_with()

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

        The abort event is what the wait sleeps on, so a stub for it drives the
        loop with no clock at all. It allows the three probes this needs and
        then asks to abort, so a wait that never ends returns ``ABORTED`` in
        milliseconds instead of running to the command timeout.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        """
        abort = mock.Mock()
        abort.wait.side_effect = [False, False, False, True]
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

        (result, message, _) = faked_subrack.run_board_command(
            "turn_on_tpms", "", abort
        )

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
    def test_an_error_while_awaiting_completion_fails_with_its_details(
        self: TestErrorBranches,
        faked_subrack: Subrack,
        fake_client: FakeHardwareClient,
        status: str,
        info: str,
    ) -> None:
        """
        An error from ``command_completed`` must fail with what the board said.

        The status and the detail the board reported both reach the caller, and
        the wait ends at once rather than running to the timeout.

        The abort event is what the wait sleeps on, so a stub for it drives the
        loop with no clock at all. It allows one probe and then asks to abort,
        so an error that failed to end the wait returns ``ABORTED`` in
        milliseconds instead of running to the command timeout.

        :param faked_subrack: the client under test.
        :param fake_client: the fake hardware client.
        :param status: the status the board reports while completing.
        :param info: the detail the board reports with it.
        """
        abort = mock.Mock()
        abort.wait.side_effect = [False, True]
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

        (result, message, _) = faked_subrack.run_board_command(
            "turn_on_tpms", "", abort
        )

        assert result == BoardCommandStatus.FAILED
        assert info in message, message
        assert abort.wait.call_count == 1, "the wait should end on the first probe"


class TestTheCallbacks:
    """
    Tests that every poll outcome reaches the callback the caller supplied.

    The poller calls these hooks, and the device does its work in the
    callbacks, so a hook that drops one leaves the device with no way to know
    what happened. All three are required arguments, so none can be missing.
    """

    def test_a_successful_poll_reaches_the_data_callback(
        self: TestTheCallbacks,
        faked_board: WebHardwareClientWrapper,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        The data callback must receive the response from a successful poll.

        :param faked_board: the board it reads.
        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        seen: list[SubrackPollResponse] = []
        subrack = make_subrack(faked_board, logger, derived, data_callback=seen.append)
        response = SubrackPollResponse()

        subrack.poll_succeeded(response)

        assert seen == [response]

    def test_a_failed_poll_reaches_the_error_callback(
        self: TestTheCallbacks,
        faked_board: WebHardwareClientWrapper,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        The error callback must receive the exception from a failed poll.

        :param faked_board: the board it reads.
        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        seen: list[Exception] = []
        subrack = make_subrack(faked_board, logger, derived, error_callback=seen.append)
        exception = HttpError("boom")

        subrack.poll_failed(exception)

        assert seen == [exception]

    def test_the_end_of_polling_reaches_the_stopped_callback(
        self: TestTheCallbacks,
        faked_board: WebHardwareClientWrapper,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        The stopped callback must be told once polling has ended.

        This is how a caller settles its own state after the last poll has
        reported back, so a hook that drops it leaves the device waiting.

        :param faked_board: the board it reads.
        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        stopped = mock.Mock()
        subrack = make_subrack(faked_board, logger, derived, stopped_callback=stopped)

        subrack.polling_stopped()

        stopped.assert_called_once_with()


# One test, because there is one thing to say about the wiring.
class TestDerivedValuesWiring:  # pylint: disable=too-few-public-methods
    """Tests that a poll runs the derived values over what it read."""

    def test_a_poll_applies_the_derived_values(
        self: TestDerivedValuesWiring,
        faked_board: WebHardwareClientWrapper,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        A poll must give the derived values what it read, and carry the result.

        What they compute is their own business, covered in
        ``test_derived_values``. A stub that writes one key is enough to show
        that a poll runs them, and that the response carries what they wrote.

        :param faked_board: the board it reads.
        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        derived.apply.side_effect = lambda values, _: values.update({"computed": 42})
        subrack = make_subrack(faked_board, logger, derived)

        response = subrack.poll(subrack.get_request())

        derived.apply.assert_called_once()
        (values, health_status) = derived.apply.call_args.args
        assert values is response.values, "the response dropped what they wrote into"
        assert health_status is response.health_status
        assert response.values["computed"] == 42


# One test, because there is one thing to say about the hold.
class TestACommandHoldsTheBoard:  # pylint: disable=too-few-public-methods
    """Tests that an asynchronous command owns the board until it ends."""

    def test_the_board_is_held_across_the_whole_handshake(
        self: TestACommandHoldsTheBoard,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        An asynchronous command must hold the board until its handshake ends.

        The SMB fails every request while a command is active, so the board is
        not free between the ``command_completed`` probes. A hold taken per
        request would let a poll in, and that poll would read nothing and still
        report the subrack as healthy.

        The wrapper is a stand-in, because which requests the wrapper runs
        under one hold is what this asserts, and that is the whole of what the
        subrack asks of it. How the hold is enforced is the wrapper's own
        business, covered in ``test_client_wrapper``. Recording the hold and
        the requests in one list puts the property in the order of the events
        themselves.

        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        events: list[str] = []
        replies = {
            "turn_on_tpms": [
                {
                    "status": HardwareClientResponseStatusCodes.OK.name,
                    "info": "",
                    "command": "turn_on_tpms",
                    "retvalue": HardwareClientResponseStatusCodes.STARTED.name,
                }
            ],
            "command_completed": [
                {
                    "status": HardwareClientResponseStatusCodes.BUSY.name,
                    "info": "",
                    "command": "command_completed",
                    "retvalue": "",
                },
                {
                    "status": HardwareClientResponseStatusCodes.BUSY.name,
                    "info": "",
                    "command": "command_completed",
                    "retvalue": "",
                },
                {
                    "status": HardwareClientResponseStatusCodes.OK.name,
                    "info": "",
                    "command": "command_completed",
                    "retvalue": True,
                },
            ],
        }
        board = mock.Mock(name="held_board")
        board.execute_command.side_effect = lambda name, *_: (
            events.append(f"request {name}") or replies[name].pop(0)
        )

        def hold(context: str, operation: Callable[[mock.Mock], Any]) -> Any:
            events.append(f"held for {context}")
            try:
                return operation(board)
            finally:
                events.append("released")

        board_wrapper = mock.Mock(name="wrapper")
        board_wrapper.run_exclusively.side_effect = hold
        # A command sent as a request of its own is the regression this guards
        # against, so it fails here rather than further down.
        board_wrapper.execute_command.side_effect = AssertionError(
            "a command must run inside a hold, not as a request of its own"
        )
        subrack = make_subrack(board_wrapper, logger, derived)
        # Mock the abort event so we don't wait for a real timeout.
        abort = mock.Mock()
        abort.wait.return_value = False

        (result, message, _) = subrack.run_board_command("turn_on_tpms", "", abort)

        assert result == BoardCommandStatus.COMPLETED, message
        assert events == [
            "held for command turn_on_tpms",
            "request turn_on_tpms",
            "request command_completed",
            "request command_completed",
            "request command_completed",
            "released",
        ]
