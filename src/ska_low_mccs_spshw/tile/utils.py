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
import sys
import threading
import time
from collections import namedtuple
from contextlib import contextmanager
from itertools import dropwhile, islice
from logging import Logger
from types import FrameType, TracebackType
from typing import Any, Callable, Iterator, TypeVar, cast

import yaml
from ska_control_model import ResultCode, TaskStatus
from yaml.nodes import SequenceNode

__all__ = [
    "acquire_timeout",
    "abort_task_on_exception",
    "HealthConfigLoader",
]
Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])

_FrameInfo = namedtuple("_FrameInfo", ["frame", "filename", "lineno", "function"])


class HealthConfigLoader(yaml.SafeLoader):  # pylint: disable=too-many-ancestors
    """
    A yaml.SafeLoader that also understands the "!!python/tuple" tag.

    Health config yaml files use "!!python/tuple" for values that must
    compare equal to a tuple read back from the TPM. Loading them with
    yaml.Loader/UnsafeLoader would allow construction of arbitrary
    Python objects from the yaml content, so this loader only adds
    back the one tag we need on top of the safe tag set.
    """


def _construct_python_tuple(
    loader: HealthConfigLoader,
    node: SequenceNode,
) -> tuple[object, ...]:
    return tuple(loader.construct_sequence(node))


HealthConfigLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    _construct_python_tuple,
)


def _iterate_stack() -> Iterator[_FrameInfo]:
    """
    Generate a fast, lazy subset of inspect.stack() that doesn't access the filesystem.

    :yield: an inspect.FrameInfo-like namedtuple for each frame on the stack
    """
    frame: FrameType | None = sys._getframe()
    while frame:
        yield _FrameInfo(
            frame, frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name
        )
        frame = frame.f_back


class LogLock:
    """A logging lock."""

    def __init__(self, name: str, log: Logger, timeout_warning: float = 0.1) -> None:
        self.name = name
        self.log = log
        self.lock = threading.RLock()
        self.last_acquired_at = float("inf")
        self.last_acquired_by = ""
        self.last_acquired_context = ""
        self._timeout_warning = timeout_warning

    def acquire(
        self, blocking: bool = True, timeout: float = -1, context: str = ""
    ) -> bool:
        """
        Attempt to acquire the lock.

        :param blocking: same as threading.Lock's blocking argument.
        :param timeout: same as threading.Lock's timeout argument.
        :param context: optional description of the operation being
            performed while the lock is held (e.g. the name of the poll
            request), reported alongside the caller if the lock is held
            for a long time. The call stack alone often can't distinguish
            between operations, since many different requests are
            executed from the same generic wrapper code.

        :return: True if the lock was acquired, False if it was not.
        """
        caller = self._caller()
        # Some debug logs have been commented out as they're a bit spammy.
        # self.log.debug(f"lock {self.name} requested by {caller}")

        acquire_start = time.time()
        # pylint: disable=consider-using-with
        acquired = self.lock.acquire(blocking, timeout)
        acquire_time = time.time() - acquire_start

        if acquired:
            self.last_acquired_at = time.time()
            self.last_acquired_by = caller
            self.last_acquired_context = context
            # self.log.debug(
            #     f"lock {self.name} acquired after {acquire_time:.3f}s by {caller}"
            # )
        else:
            time_since_acquired = time.time() - self.last_acquired_at
            held_by = (
                f"{self.last_acquired_by} ({self.last_acquired_context})"
                if (self.last_acquired_context)
                else self.last_acquired_by
            )
            self.log.error(
                f"lock {self.name} not acquired after {acquire_time:.3f}s by {caller} "
                f"- held for {time_since_acquired:.3f}s by {held_by}"
            )
        return acquired

    @staticmethod
    def _caller(depth: int = 3) -> str:
        """
        Return a stringified call stack, with callers joined by "->".

        Specifically, return the last `depth` interesting frames on the call stack,
        by starting from the first call outside this file.

        This filters out code within this class and other util functions that
        we generally aren't interested in for logging purposes.

        :param depth: how many frames to include

        :return: the last three callers' function names, joined by "->"
        """
        stack = _iterate_stack()
        interesting_frames = islice(
            dropwhile(lambda x: x.filename == __file__, stack), depth
        )
        return ">".join(reversed([frame.function for frame in interesting_frames]))

    def release(self) -> None:
        """Release the lock."""
        elapsed = time.time() - self.last_acquired_at
        caller = self._caller()

        # self.log.debug(f"lock {self.name} released after {elapsed:.3f}s by {caller}")
        if elapsed > self._timeout_warning:
            context = (
                f" ({self.last_acquired_context})" if self.last_acquired_context else ""
            )
            self.log.warning(
                f"lock {self.name} held for {elapsed:.3f}s by {caller}{context}"
            )
        self.lock.release()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()


@contextmanager
def acquire_timeout(
    lock: LogLock | threading.Lock,
    timeout: float,
    raise_exception: bool = False,
    context: str = "",
) -> Iterator[bool]:
    """
    Create an implementation of a lock context manager with timeout.

    :param lock: the thread lock instance
    :param timeout: timeout before giving up on acquiring the lock
    :param raise_exception: if True, raise exception on timeout
    :param context: optional description of the operation being performed
        while the lock is held, e.g. the name of the poll request. Only
        used when ``lock`` is a :py:class:`LogLock`; reported alongside
        the caller if the lock is held for a long time, to identify what
        was actually running when it timed out.

    :yields: a context manager

    :raises TimeoutError: if raise_exception is True and the lock isn't acquired
    """
    if isinstance(lock, LogLock):
        acquired = lock.acquire(timeout=timeout, context=context)
    else:
        acquired = lock.acquire(timeout=timeout)
    if raise_exception and not acquired:
        raise TimeoutError(f"lock not acquired in {timeout:.3f}s")
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


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
