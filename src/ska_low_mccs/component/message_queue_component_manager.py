# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements message passing functionality for component manager."""
from __future__ import annotations  # allow forward references in type hints

import functools
import logging
import queue
import threading
import traceback
from typing import Any, Callable, Optional, TypeVar, cast

import tango

from ska_tango_base.commands import ResultCode

from ska_low_mccs.component import MccsComponentManager


__all__ = ["Message", "MessageQueue", "MessageQueueComponentManager", "enqueue"]


Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


def enqueue(func: Wrapped) -> Wrapped:
    """
    Return a function that executes the wrapped function via the queue.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @enqueue
        def assign(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        component_manager: MessageQueueComponentManager,  # i.e. self
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check for component communication before calling the function.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param component_manager: the component manager to check
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :return: whatever the wrapped function returns
        """
        return component_manager.enqueue(
            functools.partial(func, component_manager), *args, **kwargs
        )

    return cast(Wrapped, _wrapper)


# TODO: This class wants to be a @dataclass, but Sphinx chokes on the
# type annotations because https://bugs.python.org/issue34776
class Message:
    """A task that can be put on the MessageQueue, pulled off, and executed."""

    def __init__(
        self: Message,
        command: Callable[..., None],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """
        Initialise a new instance.

        :param command: the command to be run
        :param args: positional arguments to the command
        :param kwargs: keyword arguments to the command
        """
        self.command = command
        self.args = args
        self.kwargs = kwargs

    def __call__(self: Message) -> None:
        """Execute the task."""
        self.command(*self.args, **self.kwargs)


class _Worker(threading.Thread):
    """A worker thread that takes tasks from the queue and performs them."""

    def __init__(
        self: _Worker,
        message_queue: MessageQueue,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new instance.

        :param message_queue: the queue from which this worker gets
            its jobs.
        :param logger: a logger for this worer thread to use.
        """
        super().__init__()
        self._message_queue = message_queue
        self._logger = logger
        self.setDaemon(True)

    def run(self: _Worker) -> None:
        """Run the thread: continually pull tasks from the queue and execute them."""
        with tango.EnsureOmniThread():
            while True:
                task = self._message_queue.get()
                try:
                    task()
                except Exception as e:
                    trace = traceback.format_exc()
                    self._logger.error(
                        f"Worker thread discarded task '{task.command}' as a result of "
                        f"exception: {e}.\ntraceback: {trace}"
                    )
                finally:
                    self._message_queue.task_done()


class MessageQueue:
    """
    A message-passing queue for asynchronous tasking.

    To call a method asynchronously, just put onto the queue a triple
    consisting of the method to be called, the args, and the kwargs. A
    worker queue will pull the task off the queue and execute it.
    """

    def __init__(
        self: MessageQueue,
        logger: logging.Logger,
        max_size: int = 0,
        num_workers: int = 1,
        queue_size_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for the message queue to use
        :param max_size: an optional maximum allowed queue size. The
            default value is 0, which is a special case signifying no
            queue size limit.
        :param num_workers: the number of worker threads servicing
            the queue. The default value is 1. An exception is raised if
            the value provided is less than 1.
        :param queue_size_callback: optional callback to be called when
            the size of the queue changes.

        :raises ValueError: if num_workers argument is not at least 1.
        """
        if num_workers < 1:
            raise ValueError("MessageQueue needs at least one worker!")

        self._logger = logger
        self._queue_size_callback = queue_size_callback
        self._queue: queue.Queue = queue.Queue(maxsize=max_size)

        self._threads = [_Worker(self, self._logger) for i in range(num_workers)]
        for thread in self._threads:
            thread.start()

    def __del__(self: MessageQueue) -> None:
        """Release resources prior to instance deletion."""
        self._queue.join()

    def __len__(self: MessageQueue) -> int:
        """
        Return the length of this queue.

        Note that the underlying queue only offers an approximate
        length.

        :return: the approximate length of this queue.
        """
        return self._queue.qsize()

    def enqueue(
        self: MessageQueue,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Put a method call onto the queue.

        :param func: the method to be called.
        :param args: positional arguments to the method
        :param kwargs: keyword arguments to the method
        """
        self._queue.put_nowait(Message(func, args, kwargs))
        self._queue_size_changed()

    def get(self: MessageQueue) -> Message:
        """
        Get the next task from the queue, blocking until one arrives.

        :return: a task
        """
        task = self._queue.get()
        self._queue_size_changed()
        return task

    def task_done(self: MessageQueue) -> None:
        """
        Handle notification that a thread has completed a task.

        This is a hook that is called by threads whenever they complete
        a task.
        """
        self._queue.task_done()

    def _queue_size_changed(self: MessageQueue) -> None:
        """Handle change in queue size, by calling the callback if provided."""
        if self._queue_size_callback is not None:
            self._queue_size_callback(len(self))


class MessageQueueComponentManager(MccsComponentManager):
    """A component manager that provides message queue functionality."""

    def __init__(
        self: MessageQueueComponentManager,
        message_queue: MessageQueue,
        logger: logging.Logger,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param message_queue: a message queue for this component manager to use
        :param logger: a logger for this component manager to use
        :param args: positional arguments to pass to the parent class
        :param kwargs: keyword arguments to pass to the parent class.
        """
        self._message_queue = message_queue
        super().__init__(logger, *args, **kwargs)

    def enqueue(
        self: MessageQueueComponentManager,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> ResultCode:
        """
        Put a method call onto the queue.

        :param func: the method to be called.
        :param args: positional arguments to the method
        :param kwargs: keyword arguments to the method

        :return: a result code
        """
        try:
            self._message_queue.enqueue(func, *args, **kwargs)
        except queue.Full:
            self.logger.error(f"Could not enqueue '{func}', queue is full.")
            return ResultCode.FAILED
        return ResultCode.QUEUED
