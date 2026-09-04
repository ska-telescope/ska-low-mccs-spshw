#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
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

import pytest
from ska_low_mccs_common.component import HardwareClientResponseStatusCodes

from ska_low_mccs_spshw.prototype_subrack import (
    BoardCommandStatus,
    HttpError,
    RequestError,
    Subrack,
    SubrackPollModel,
    SubrackPollRequest,
    SubrackPollResponse,
)
from ska_low_mccs_spshw.prototype_subrack.constants import (
    BATCH_ATTRIBUTES,
    LOCK_TIMEOUT,
)
from ska_low_mccs_spshw.subrack.subrack_data import SubrackData
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


def _make_model(
    client: FakeHardwareClient,
    logger: logging.Logger,
    lock: LogLock | None = None,
    **kwargs: Any,
) -> SubrackPollModel:
    """
    Return a poll model wired to a fake client, with no poller attached.

    :param client: the fake hardware client.
    :param logger: a logger.
    :param lock: the client lock, defaulting to a fresh one.
    :param kwargs: overrides passed to the model.

    :return: a poll model.
    """
    options: dict[str, Any] = {
        "command_update_rate": 1000.0,
        "lock_timeout": LOCK_TIMEOUT,
        "data_callback": lambda _: None,
        "error_callback": None,
    }
    options.update(kwargs)
    return SubrackPollModel(
        client,  # type: ignore[arg-type]
        lock or LogLock("test", logger),
        logger,
        **options,
    )


def _make_subrack(
    client: FakeHardwareClient,
    logger: logging.Logger,
    **kwargs: Any,
) -> Subrack:
    """
    Return a client wired to a fake hardware client, with polling stopped.

    :param client: the fake hardware client.
    :param logger: a logger.
    :param kwargs: overrides passed to the client.

    :return: a subrack client.
    """
    options: dict[str, Any] = {
        "poll_rate": 60.0,
        "command_update_rate": 60.0,
        "data_callback": lambda _: None,
    }
    options.update(kwargs)
    return Subrack(
        "no-such-host",
        0,
        logger,
        _client=client,  # type: ignore[arg-type]
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
    """Tests that run against a real simulator server over HTTP."""

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

    def test_poll_adds_the_derived_fan_speeds(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
        responses: queue.SimpleQueue,
    ) -> None:
        """
        The derived fan speeds must arrive alongside the raw reads.

        Presence and shape only. The simulator's fans scale to exactly the
        maximum fan speed, which is also what the replacement rule substitutes,
        so a value assertion here would hold either way. ``TestDerivedValues``
        covers the value.

        :param simulated_subrack: the client under test.
        :param responses: the queue that the callbacks feed.
        """
        simulated_subrack.start_polling()
        response = _next_poll(responses)

        estimates = response.values["subrack_max_fan_speeds"]
        assert estimates is not None
        assert len(estimates) == SubrackData.FAN_COUNT

    def test_health_status_arrives_on_the_first_poll(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
        responses: queue.SimpleQueue,
    ) -> None:
        """
        The health status must arrive on the first poll.

        ``board_info`` is in the same batch as everything else, so the BIOS gate
        opens before the health read of that same poll.

        :param simulated_subrack: the client under test.
        :param responses: the queue that the callbacks feed.
        """
        simulated_subrack.start_polling()

        health_status = _next_poll(responses).health_status

        assert health_status is not None
        assert "temperatures" in health_status
        assert "psus" in health_status

    def test_synchronous_board_command(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
    ) -> None:
        """
        A synchronous board command must complete and return its value.

        :param simulated_subrack: the client under test.
        """
        (status, _, retvalue) = simulated_subrack.run_board_command(
            "get_health_status", ""
        )

        assert status == BoardCommandStatus.COMPLETED
        assert isinstance(retvalue, dict)

    def test_asynchronous_board_command_handshake(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
    ) -> None:
        """
        An asynchronous board command must be awaited to completion.

        The simulator answers ``turn_on_tpm`` with ``STARTED``, so this
        exercises the ``command_completed`` probe loop.

        :param simulated_subrack: the client under test.
        """
        (status, message, _) = simulated_subrack.run_board_command("turn_on_tpm", "2")

        assert status == BoardCommandStatus.COMPLETED, message

    def test_board_command_runs_while_polling(
        self: TestAgainstSimulator,
        simulated_subrack: Subrack,
        responses: queue.SimpleQueue,
    ) -> None:
        """
        A board command must not wait for a poll slot.

        This is the behaviour that lets the design drop the command queue.

        :param simulated_subrack: the client under test.
        :param responses: the queue that the callbacks feed.
        """
        simulated_subrack.start_polling()
        _next_poll(responses)

        (status, message, _) = simulated_subrack.run_board_command("turn_on_tpm", "5")
        assert status == BoardCommandStatus.COMPLETED, message

        # Polling must survive the command.
        assert _next_poll(responses).values["tpm_present"] is not None


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

    def _model_with_bios(
        self: TestHealthCadence,
        fake_client: FakeHardwareClient,
        logger: logging.Logger,
        version: str | None,
        **kwargs: Any,
    ) -> SubrackPollModel:
        """
        Return a poll model whose fake board reports the given BIOS version.

        :param fake_client: the fake hardware client.
        :param logger: a logger.
        :param version: the BIOS version string, or ``None`` for no board info.
        :param kwargs: overrides passed to the model.

        :return: a poll model.
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
        return _make_model(fake_client, logger, **kwargs)

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
        model = self._model_with_bios(
            fake_client, logger, "v1.6.0", command_update_rate=1000.0
        )

        assert model.poll(model.get_request()).health_status is not None
        assert model.poll(model.get_request()).health_status is None

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
        model = self._model_with_bios(fake_client, logger, "v1.5.0")

        assert model.poll(model.get_request()).health_status is None

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
        model = self._model_with_bios(fake_client, logger, "not-a-version")

        assert model.poll(model.get_request()).health_status is None

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
        model = _make_model(fake_client, logger)

        with pytest.raises(RequestError, match="Connection refused"):
            model.poll(model.get_request())

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
        model = _make_model(fake_client, logger)

        with pytest.raises(HttpError, match="500"):
            model.poll(model.get_request())

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
        model = _make_model(fake_client, logger)

        response = model.poll(model.get_request())

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
        model = _make_model(fake_client, logger)

        response = model.poll(model.get_request())

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
        model = _make_model(fake_client, logger)

        with pytest.raises(ValueError, match="NOT_A_REAL_STATUS"):
            model.poll(model.get_request())

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
        model = _make_model(fake_client, logger, max_fan_errors=1)

        # Use up the single allowed replacement.
        model.derived.estimate_max_fan_rpm([0.0] * 4, [100.0] * 4)
        assert model.derived.fan_error_counts == [1, 1, 1, 1]

        model.poll_failed(RequestError("gone"))
        assert model.derived.fan_error_counts == [0, 0, 0, 0]

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
        model = _make_model(fake_client, logger, error_callback=seen.append)
        exception = HttpError("boom")

        model.poll_failed(exception)

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

        A command runs on the caller's thread, so an exception here would
        escape into a long running command rather than into ``poll_failed``.

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
    """
    Tests that a poll response carries the derived values.

    ``TestDerivedValues`` covers the computation itself.
    """

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
        model = _make_model(fake_client, logger, max_fan_errors=0)

        response = model.poll(model.get_request())

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
        model = _make_model(
            fake_client,
            logger,
            attribute_filter_type="mean",
            attribute_filter_max_samples=2,
        )

        fake_client.set_attribute_response(value=[0.0, 10.0])
        model.poll(model.get_request())
        fake_client.set_attribute_response(value=[10.0, 20.0])
        response = model.poll(model.get_request())

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

        A second thread is needed because the lock is reentrant, so the calling
        thread would simply acquire it again. The handshake uses events, so the
        test does not wait on a clock.

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
        model = _make_model(fake_client, logger, lock=lock, lock_timeout=0.01)

        with self._held(lock):
            with pytest.raises(RequestError, match="still holds the client"):
                model.poll(model.get_request())

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
        model = _make_model(fake_client, logger, lock=lock)
        fake_client.set_attribute_response(value=None)

        with caplog.at_level(logging.WARNING, logger=logger.name):
            model.poll(model.get_request())

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
    Tests that the client disposes of its polling thread.

    ``cleanup`` is one line, delegating to the poller. This covers that line,
    and in doing so pins a contract of ``ska-tango-base`` that the design
    depends on, which is that stopping polling leaves the thread alive and only
    ``kill_polling_thread`` ends it. An upgrade that changed either would fail
    here.
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
