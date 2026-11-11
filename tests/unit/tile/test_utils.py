# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the Tile utilss."""
import logging
import threading
import time
import unittest.mock

import pytest

from ska_low_mccs_spshw.tile.utils import LogLock, acquire_timeout


@pytest.fixture(name="logger")
def logger_fixture() -> logging.Logger:
    """
    Fixture to create a logger for testing.

    :return: A logger instance.
    """
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger


def test_loglock_release_without_acquire(logger: logging.Logger) -> None:
    """
    Test releasing the LogLock without acquiring it.

    :param logger: The logger instance.
    """
    lock = LogLock("test_lock", logger)

    with pytest.raises(RuntimeError):
        lock.release()


def test_loglock_multiple_threads(logger: logging.Logger) -> None:
    """
    Test LogLock with multiple threads.

    :param logger: The logger instance.
    """
    lock = LogLock("test_lock", logger)
    results: list[bool] = []

    def worker(lock: LogLock, results: list[bool]) -> None:
        if lock.acquire(timeout=0.5):
            results.append(True)
            time.sleep(1)
            lock.release()
        else:
            results.append(False)

    threads = [threading.Thread(target=worker, args=(lock, results)) for _ in range(5)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert sum(results) == 1, "Only one thread should acquire the lock at a time"


@pytest.mark.parametrize(("threshold", "expect_log"), [(0.0, True), (1000.0, False)])
def test_loglock_slow_release_logs_timing(
    threshold: float, expect_log: bool
) -> None:
    """
    Test holding the lock past the threshold warns with a timing breakdown.

    :param threshold: the lock's warning threshold, in seconds.
    :param expect_log: whether a "held for" warning is expected.
    """
    logger = unittest.mock.Mock()
    lock = LogLock("test_lock", logger, timeout_warning=threshold)

    with lock:
        time.sleep(0.01)

    if not expect_log:
        logger.warning.assert_not_called()
        return
    logger.warning.assert_called_once()
    message = logger.warning.call_args.args[0]
    assert "lock test_lock held for" in message
    for field in ("cpu=", "runqueue=", "blocked=", "lock_wait="):
        assert field in message


def test_loglock_slow_release_logs_timing_on_exception() -> None:
    """Test a slow hold that raises is still reported with its timing."""
    logger = unittest.mock.Mock()
    lock = LogLock("test_lock", logger, timeout_warning=0.0)

    with pytest.raises(ConnectionError), acquire_timeout(lock, 1.0, context="dummy"):
        raise ConnectionError("boom")

    message = logger.warning.call_args.args[0]
    assert "(dummy)" in message
    assert "cpu=" in message
