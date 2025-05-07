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

import pytest

from ska_low_mccs_spshw.tile.utils import LogLock


@pytest.fixture(name="logger")
def logger_fixture() -> logging.Logger:
    """
    Fixture to create a logger for testing.

    :return: A logger instance.
    """
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    return logger


def test_loglock_acquire_and_release(logger: logging.Logger) -> None:
    """
    Test acquiring and releasing the LogLock.

    :param logger: The logger instance.
    """
    lock = LogLock("test_lock", logger)

    assert not lock.locked(), "Lock should initially be unlocked"

    acquired = lock.acquire()
    assert acquired, "Lock should be acquired successfully"
    assert lock.locked(), "Lock should be locked after acquisition"

    lock.release()
    assert not lock.locked(), "Lock should be unlocked after release"


def test_loglock_acquire_timeout(logger: logging.Logger) -> None:
    """
    Test acquiring the LogLock with a timeout.

    :param logger: The logger instance.
    """
    lock = LogLock("test_lock", logger)

    lock.acquire()
    assert lock.locked(), "Lock should be locked after acquisition"

    start_time = time.time()
    acquired = lock.acquire(timeout=0.5)
    elapsed_time = time.time() - start_time

    assert not acquired, "Lock should not be acquired when already locked"
    assert elapsed_time >= 0.5, "Timeout should be respected"

    lock.release()


def test_loglock_context_manager(logger: logging.Logger) -> None:
    """
    Test using LogLock as a context manager.

    :param logger: The logger instance.
    """
    lock = LogLock("test_lock", logger)

    with lock:
        assert lock.locked(), "Lock should be locked inside context manager"

    assert not lock.locked(), "Lock should be unlocked after context manager"


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
