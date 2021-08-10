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
from typing import Any, Callable, TypeVar, cast

import tango

from ska_tango_base.commands import ResultCode

from ska_low_mccs.component import MccsComponentManager


__all__ = ["MessageQueueComponentManager", "enqueue"]


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


class MessageQueueComponentManager(MccsComponentManager):
    """A component manager that provides message queue functionality."""

    class _Worker(threading.Thread):
        """A worker thread that takes tasks from the queue and performs them."""

        def __init__(
            self: MessageQueueComponentManager._Worker,
            queue: queue.Queue,
            logger: logging.Logger,
        ) -> None:
            """
            Initialise a new instance.

            :param queue: the queue from which this worker gets its jobs.
            :param logger: a logger for this worer thread to use.
            """
            super().__init__()
            self._queue = queue
            self._logger = logger
            self.setDaemon(True)

        def run(self: MessageQueueComponentManager._Worker) -> None:
            with tango.EnsureOmniThread():
                while True:
                    try:
                        (command, args, kwargs) = self._queue.get()
                        command(*args, **kwargs)
                    except Exception as e:
                        trace = traceback.format_exc()

                        self._logger.error(
                            f"Worker thread discarded task '{command}' as a result of "
                            f"exception: {e}.\ntraceback: {trace}"
                        )
                    finally:
                        self._queue.task_done()

    def __init__(
        self: MessageQueueComponentManager,
        logger: logging.Logger,
        *args: Any,
        max_queue_size: int = 3,
        thread_pool_size: int = 1,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this component manager to use
        :param args: positional arguments to pass to the parent class
        :param max_queue_size: an optional maximum allowed queue size.
            The default value is 1.
        :param thread_pool_size: the number of worker threads servicing
            the queue. The default value is 1.
        :param kwargs: keyword arguments to pass to the parent class.
        """
        self._logger = logger
        self.__queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.__threads = [
            self._Worker(self.__queue, self._logger) for i in range(thread_pool_size)
        ]
        for thread in self.__threads:
            thread.start()
        super().__init__(logger, *args, **kwargs)

    def __del__(self: MessageQueueComponentManager) -> None:
        """Release resources prior to instance deletion."""
        self.__queue.join()

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
            self.__queue.put_nowait((func, args, kwargs))
        except queue.Full:
            self._logger.error(
                f"Could not enqueue '{func}', queue is full. "
                f"Queue contents: {list(self.__queue.queue)}."
            )
            return ResultCode.FAILED
        return ResultCode.QUEUED
