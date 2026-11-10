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
    "GilLatencyProbe",
    "HealthConfigLoader",
    "start_gil_latency_probe",
    "LockTimeoutError",
    "thread_run_delay_s",
]
Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


class LockTimeoutError(TimeoutError):
    """
    Raised when a lock could not be acquired in time.

    Distinct from other TimeoutErrors (e.g. socket timeouts talking to
    hardware): this means another thread is busy, not that the hardware
    is unreachable.
    """


# Set False after the first failed read of schedstat, so polls on systems
# without it (non-Linux, no /proc, schedstats disabled) don't retry every time.
_SCHEDSTAT_AVAILABLE = True


def thread_run_delay_s() -> float | None:
    """
    Return the calling thread's cumulative run-queue delay, in seconds.

    This is the time the thread was runnable but waiting for a CPU, taken from
    the second field of ``/proc/self/task/<tid>/schedstat``. Comparing two
    readings shows how much of an interval was lost to CPU contention on the
    node, as opposed to the thread running (CPU time) or being blocked
    (waiting for the GIL, or on I/O).

    :return: the cumulative run-queue delay in seconds, or None if it can't
        be read on this system.
    """
    global _SCHEDSTAT_AVAILABLE  # pylint: disable=global-statement
    if not _SCHEDSTAT_AVAILABLE:
        return None
    try:
        with open(
            f"/proc/self/task/{threading.get_native_id()}/schedstat",
            encoding="ascii",
        ) as schedstat:
            # Fields: time on CPU (ns), time waiting on run queue (ns), timeslices
            return int(schedstat.read().split()[1]) / 1e9
    except (OSError, IndexError, ValueError):
        _SCHEDSTAT_AVAILABLE = False
        return None


class GilLatencyProbe:
    """
    Measure how long a thread waits for the GIL after its I/O completes.

    A daemon thread repeatedly sleeps for ``period`` and measures how late it
    wakes. Sleeping releases the GIL and waking needs it back, so this wait is
    the same one every I/O-bound thread (e.g. a poll waiting for a TPM reply)
    pays on each I/O. The thread does no work of its own, so its lateness has
    only two causes:

    * run-queue delay: no CPU was available (node contention or CFS
      throttling against the container CPU limit). Read from schedstat.
    * GIL wait: another thread in this process was running Python. This is
      the lateness that the run-queue delay does not account for.

    Results are collected over ``window`` seconds. A window is only logged,
    as a ``GIL_PROBE`` warning, if one wake was later than ``threshold``, so
    an idle process logs nothing.

    The GIL is shared by every device in the process, so only one probe per
    process is needed: see :py:func:`start_gil_latency_probe`.
    """

    def __init__(
        self: GilLatencyProbe,
        logger: Logger,
        period: float = 0.01,
        window: float = 1.0,
        threshold: float = 0.02,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: logger to report slow windows to.
        :param period: how long each sleep lasts, in seconds. Each wake takes
            the GIL briefly, so a very short period adds GIL contention.
        :param window: how long results are collected before they are
            reported, in seconds.
        :param threshold: log a window if any wake in it was later than
            this, in seconds. The default switch interval is 5 ms, so a
            single GIL handoff can be that late without anything being wrong.
        """
        self._logger = logger
        self._period = period
        self._window = window
        self._threshold = threshold
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self: GilLatencyProbe) -> None:
        """Start the probe thread, if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="GIL probe", daemon=True)
        self._thread.start()

    def stop(self: GilLatencyProbe, timeout: float | None = None) -> None:
        """
        Stop the probe thread.

        :param timeout: how long to wait for the thread to exit, in seconds.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self: GilLatencyProbe) -> None:
        window_start = time.perf_counter()
        runq_start = thread_run_delay_s()
        samples = 0
        late_total = 0.0
        late_max = 0.0
        while True:
            before = time.perf_counter()
            # Event.wait releases the GIL while waiting; it must get the GIL
            # back before perf_counter below can run. That wait is what we
            # measure.
            if self._stop_event.wait(self._period):
                return
            now = time.perf_counter()
            late = max(now - before - self._period, 0.0)
            samples += 1
            late_total += late
            late_max = max(late_max, late)

            if now - window_start < self._window:
                continue
            runq_end = thread_run_delay_s()
            if late_max > self._threshold:
                self._report(
                    now - window_start,
                    samples,
                    late_total,
                    late_max,
                    (
                        None
                        if runq_start is None or runq_end is None
                        else runq_end - runq_start
                    ),
                )
            window_start = now
            runq_start = runq_end
            samples = 0
            late_total = 0.0
            late_max = 0.0

    # pylint: disable=too-many-arguments
    def _report(
        self: GilLatencyProbe,
        window: float,
        samples: int,
        late_total: float,
        late_max: float,
        runqueue: float | None,
    ) -> None:
        """
        Log a slow window.

        :param window: actual length of the window, in seconds.
        :param samples: number of wakes in the window.
        :param late_total: total lateness of all wakes in the window.
        :param late_max: lateness of the latest wake in the window.
        :param runqueue: run-queue delay of the probe thread over the
            window, or None if unavailable on this system.
        """
        if runqueue is None:
            runqueue_str = "n/a"
            gil_str = "n/a"
        else:
            runqueue_str = f"{runqueue:.3f}"
            # Run-queue delay can only happen while late, so this is the
            # part of the lateness spent waiting for the GIL (plus a few
            # microseconds of timer slack per wake).
            gil_str = f"{max(late_total - runqueue, 0.0):.3f}"
        self._logger.warning(
            f"GIL_PROBE window={window:.3f} samples={samples} "
            f"late_max={late_max:.3f} late_total={late_total:.3f} "
            f"runqueue={runqueue_str} gil={gil_str}"
        )


_gil_probe: GilLatencyProbe | None = None
_gil_probe_lock = threading.Lock()


def start_gil_latency_probe(
    logger: Logger, period: float = 0.01
) -> GilLatencyProbe | None:
    """
    Start the process-wide GIL latency probe, if not already started.

    Every device in a device server process shares one GIL, so the first
    device to call this starts the probe and later calls do nothing. The probe
    keeps running until the process exits, since other devices still rely
    on it after one device is deleted.

    :param logger: logger the probe reports to. Only the first caller's
        logger is used.
    :param period: how long each probe sleep lasts, in seconds. 0 or less
        disables the probe.

    :return: the running probe, or None if disabled.
    """
    global _gil_probe  # pylint: disable=global-statement
    if period <= 0:
        return None
    with _gil_probe_lock:
        if _gil_probe is None:
            _gil_probe = GilLatencyProbe(logger, period=period)
            _gil_probe.start()
            logger.info(f"Started process-wide GIL latency probe, period {period}s")
        return _gil_probe


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

    :raises LockTimeoutError: if raise_exception is True and the lock
        isn't acquired
    """
    if isinstance(lock, LogLock):
        acquired = lock.acquire(timeout=timeout, context=context)
    else:
        acquired = lock.acquire(timeout=timeout)
    if raise_exception and not acquired:
        raise LockTimeoutError(f"lock not acquired in {timeout:.3f}s")
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
