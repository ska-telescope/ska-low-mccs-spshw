#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A collection of utility methods."""

from __future__ import annotations  # allow forward references in type hints

import functools
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar, cast

from ska_control_model import ResultCode, TaskStatus

__all__ = ["acquire_timeout", "int2ip", "abort_task_on_exception"]
Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


@contextmanager
def acquire_timeout(lock: threading.Lock, timeout: float) -> Iterator[bool]:
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


def check_hardware_lock_claimed(func: Wrapped) -> Wrapped:
    """
    Return a function that checks the hardware lock is claimed before executing.

    The component needs to have claimed a lock, in order for
    the function to be called.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @check_hardware_lock_claimed
        def initialise(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(component: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Check that the component has its hardware lock claimed before execution.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param component: the component to check
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises AssertionError: when hardware lock has is not claimed.

        :return: whatever the wrapped function returns
        """
        if not component._hardware_lock.locked():
            raise AssertionError("Lock has not been acquired, cannot execute command.")
        return func(component, *args, **kwargs)

    return cast(Wrapped, _wrapper)


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


def abort_task_on_exception(func: Wrapped) -> Wrapped:
    """
    Return a function that notify the task_status of aborted command upon exception.

    The component manager needs to call back the task_status with abort upon a
    exception being raised.

    This function is intended to be used as a decorator on LongRunningCommands:

    .. code-block:: python

        @abort_task_on_exception
        def initialise(self, task_status):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        component_manager: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Notify task_status of aborted command upon exception.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param component_manager: the component manager to check
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises Exception: if an uncaught exception was raised in the function call.
        :return: whatever the wrapped function returns
        """
        try:
            return func(component_manager, *args, **kwargs)
        except Exception as e:
            for arg in args:
                if isinstance(arg, functools.partial):
                    try:
                        arg(
                            status=TaskStatus.ABORTED,
                            result=(ResultCode.ABORTED, "Aborted"),
                        )
                    except Exception as ex:
                        print("Failed to abort")
                        raise ex
            raise e

    return cast(Wrapped, _wrapper)
