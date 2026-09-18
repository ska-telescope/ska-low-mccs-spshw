#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests that the subrack holds the board for the whole of each operation.

The SMB fails every request while a command is active, so what reaches the
board must not interleave. A poll sweep and the handshake after an asynchronous
command are each one operation, however many requests they take.

These assert what the subrack asks for, by driving a stand-in wrapper and
recording the hold and the requests in one list, so the property is the order of
that list itself. How the hold is enforced is the wrapper's own business,
covered in ``test_client_wrapper``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from unittest import mock

from ska_low_mccs_common.component import HardwareClientResponseStatusCodes

from ska_low_mccs_spshw.prototype_subrack import BoardCommandStatus

from .conftest import make_subrack


def _command_response(
    command: str,
    retvalue: Any,
    status: str = HardwareClientResponseStatusCodes.OK.name,
) -> dict[str, Any]:
    """
    Return a client response to a command.

    :param command: the command it answers.
    :param retvalue: the value the board returned with it.
    :param status: the status the client reports, ``OK`` unless given.

    :return: the response.
    """
    return {"status": status, "info": "", "command": command, "retvalue": retvalue}


class TestAPollHoldsTheBoard:  # pylint: disable=too-few-public-methods
    """Tests that a poll sweep reaches the board under one hold."""

    def test_a_poll_sweep_is_one_hold_around_every_request(
        self: TestAPollHoldsTheBoard,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        A poll must make every request of its sweep inside one hold.

        A hold taken per request would free the board between the reads, so a
        command could land part way through the sweep and the values either
        side of it would describe two different moments.

        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        events: list[str] = []
        board = mock.Mock(name="board")

        def read(name: str) -> dict[str, Any]:
            events.append(f"read {name}")
            return {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "attribute": name,
                "value": None,
            }

        def run(name: str, _: str = "") -> dict[str, Any]:
            events.append(f"command {name}")
            return _command_response(name, None)

        board.get_attribute.side_effect = read
        board.execute_command.side_effect = run

        def hold(context: str, operation: Callable[[mock.Mock], Any]) -> Any:
            events.append(f"held for {context}")
            try:
                return operation(board)
            finally:
                events.append("released")

        board_wrapper = mock.Mock(name="wrapper")
        board_wrapper.run_exclusively.side_effect = hold
        subrack = make_subrack(board_wrapper, logger, derived)

        subrack.poll(("tpm_present", "board_current"))

        assert events == [
            "held for poll sweep",
            "read tpm_present",
            "read board_current",
            "command get_health_status",
            "released",
        ]


class TestACommandHoldsTheBoard:
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
        busy = HardwareClientResponseStatusCodes.BUSY.name
        started = HardwareClientResponseStatusCodes.STARTED.name
        replies: dict[str, list[dict[str, Any]]] = {
            "turn_on_tpms": [_command_response("turn_on_tpms", started)],
            "command_completed": [
                _command_response("command_completed", "", status=busy),
                _command_response("command_completed", "", status=busy),
                _command_response("command_completed", True),
            ],
        }
        board = mock.Mock(name="held_board")

        def answer(name: str, *_: Any) -> Any:
            events.append(f"request {name}")
            return replies[name].pop(0)

        board.execute_command.side_effect = answer

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

    def test_the_board_is_given_the_command_verbatim(
        self: TestACommandHoldsTheBoard,
        logger: logging.Logger,
        derived: mock.Mock,
    ) -> None:
        """
        A command must reach the board with its arguments unchanged.

        The board parses the argument string itself, so anything this layer
        drops or reshapes is a command that quietly does something else. The
        assertion is on what the board received inside the hold, because
        ``run_exclusively`` is the only path a command takes to it.

        :param logger: a logger.
        :param derived: a stand-in for the computed values.
        """
        board = mock.Mock(name="board")
        board.execute_command.side_effect = [
            _command_response(
                "set_subrack_fan_speed",
                HardwareClientResponseStatusCodes.STARTED.name,
            ),
            _command_response("command_completed", True),
        ]
        board_wrapper = mock.Mock(name="wrapper")
        board_wrapper.run_exclusively.side_effect = (
            lambda context, operation: operation(board)
        )
        subrack = make_subrack(board_wrapper, logger, derived)
        # Mock the abort event so we don't wait for a real timeout.
        abort = mock.Mock()
        abort.wait.return_value = False

        (result, message, _) = subrack.run_board_command(
            "set_subrack_fan_speed", "2,55", abort
        )

        assert result == BoardCommandStatus.COMPLETED, message
        assert board.execute_command.call_args_list[0] == mock.call(
            "set_subrack_fan_speed", "2,55"
        )
