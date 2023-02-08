#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A collection of utility methods."""

from __future__ import annotations  # allow forward references in type hints

import threading
from collections.abc import Generator
from contextlib import contextmanager

__all__ = [
    "acquire_timeout",
    "int2ip",
]


@contextmanager
def acquire_timeout(
    lock: threading.Lock, timeout: float
) -> Generator[bool, None, None]:
    """
    Create an implementation of a lock context manager with timeout.

    :param lock: the thread lock instance
    :param timeout: timeout before giving up on acquiring the lock

    :yields: a context manager
    """
    result = lock.acquire(timeout=timeout)
    try:
        yield result
    finally:
        if result:
            lock.release()


def int2ip(addr: int) -> str:
    """
    Convert integer IPV4 into formatted dot address.

    :param addr: Integer IPV4 address
    :return: dot formatted IPV4 address
    """
    # If parameter is already a string, just return it. No checking
    if isinstance(addr, str):
        return addr
    ip = [0, 0, 0, 0]
    for i in range(4):
        ip[i] = addr & 0xFF
        addr = addr >> 8
    return f"{ip[3]}.{ip[2]}.{ip[1]}.{ip[0]}"
