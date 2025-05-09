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
