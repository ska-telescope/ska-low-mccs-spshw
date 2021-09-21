"""This module contains tests of the message_queue_component_manager module."""
from __future__ import annotations

from contextlib import nullcontext
import logging
import queue
import threading
import time
from typing import Any, Callable, Optional
from typing_extensions import Protocol
import unittest.mock

import pytest

from ska_tango_base.commands import ResultCode

from ska_low_mccs.component import (
    MessageQueue,
    MessageQueueComponentManager,
    enqueue,
)

from ska_low_mccs.testing.mock import MockCallable


class TestMessageQueue:
    """This class contains tests of the MessageQueue."""

    class SlowTaskProtocol(Protocol):
        """
        Protocol of the function returned by the ``slow_task`` fixture.

        This is purely for the benefit of the type checker. One cannot
        express optional arguments using ``Callable`` so we have to
        specify a ``Protocol`` instead.
        """

        def __call__(
            self: TestMessageQueue.SlowTaskProtocol,
            sleep_time: int,
            completed_callback: Optional[Callable[[], None]] = None,
            lock: Optional[threading.Lock] = None,
        ) -> None:
            """
            Calling interface for this protocol.

            :param sleep_time: the amount of time this call should
                sleep, in simulation of a slow task.
            :param completed_callback: an optional callback to be called
                just before this call returns
            :param lock: a lock to be acquired and held by this call
            """
            ...

    @pytest.fixture()
    def slow_task(self: TestMessageQueue) -> SlowTaskProtocol:
        """
        Return a slow method to be used in testing.

        This is an example of a method that we would want to execute via
        a message queue because it is slow.

        See :py:class:``TestMessageQueue.SlowTaskProtocol`` for the
        signature of the function returned. (The function takes
        arguments that could have been set up in this fixture. We
        deliberately leave them to be passed as arguments at runtime,
        because this allows us to test the ``MessageQueue``'s handling
        of args and kwargs.)

        :return: a slow method to be used in testing.
        """

        def slow_task_impl(
            sleep_time: int,
            completed_callback: Optional[Callable[[], None]] = None,
            lock: Optional[threading.Lock] = None,
        ) -> None:
            with lock or nullcontext():
                time.sleep(sleep_time)
                if completed_callback is not None:
                    completed_callback()

        return slow_task_impl

    @pytest.fixture()
    def task_complete_callback(self: TestMessageQueue) -> Callable[[], None]:
        """
        Return a callback to be called when a task is completed.

        :return: a callback to be called when a task is completed.
        """
        return MockCallable()

    def test_message_queue_no_workers(
        self: TestMessageQueue,
        logger: logging.Logger,
    ) -> None:
        """
        Test that an exception is raised if we create a message queue with no workers.

        :param logger: a logger for the message queue to use.
        """
        with pytest.raises(ValueError, match="MessageQueue needs at least one worker!"):
            _ = MessageQueue(logger, 0, 0)

    @pytest.mark.parametrize("max_queue_size", [5])
    def test_message_queue_size(
        self: TestMessageQueue,
        max_queue_size: int,
        logger: logging.Logger,
        slow_task: TestMessageQueue.SlowTaskProtocol,
        message_queue_size_callback: MockCallable,
        task_complete_callback: MockCallable,
    ) -> None:
        """
        Test message queue size management functionality.

        Specifically, test that the message queue knows what its size is, reports any
        changes to its size by calling the provided callback, and raises an exception if
        we exceed the maximum queue size.

        :param max_queue_size: the maximum size of the queue.
        :param logger: a logger for the message queue to use
        :param slow_task: a slow method to be executed via the message
            queue
        :param message_queue_size_callback: a callback to be called when the
            queue size changes
        :param task_complete_callback: a callback to be called when
            execution of the slow method finishes.
        """
        lock = threading.Lock()
        message_queue = MessageQueue(
            logger, max_queue_size, 1, message_queue_size_callback
        )

        # check initial conditions
        task_complete_callback.assert_not_called()
        message_queue_size_callback.assert_not_called()
        assert len(message_queue) == 0

        with lock:
            # enqueue a message.
            message_queue.enqueue(
                slow_task,
                0.1,
                completed_callback=task_complete_callback,
                lock=lock,
            )
            message_queue_size_callback.assert_next_call(1)

            # The worker thread will pull the task and start executing it,
            # which means the queue will be empty again
            message_queue_size_callback.assert_next_call(0)
            assert len(message_queue) == 0

            # but the worker cannot completed the task because we are holding the lock
            task_complete_callback.assert_not_called()

            for size in range(1, max_queue_size + 1):
                message_queue.enqueue(
                    slow_task,
                    0.1,
                    completed_callback=task_complete_callback,
                )
                message_queue_size_callback.assert_next_call(size)

            # Because there's only one worker thread, and we are holding a lock that it
            # needs to complete its task, no other tasks can be pulled, so the queue has
            # filled to capacity
            assert len(message_queue) == max_queue_size
            task_complete_callback.assert_not_called()

            with pytest.raises(queue.Full):
                message_queue.enqueue(
                    slow_task,
                    0.1,
                    completed_callback=task_complete_callback,
                    lock=lock,
                )

        # release the lock and watch the worker thread work through the queue of tasks
        task_complete_callback.assert_next_call()
        for size in reversed(range(max_queue_size)):
            message_queue_size_callback.assert_next_call(size)
            task_complete_callback.assert_next_call()


class ExampleMessageQueueComponentManager(MessageQueueComponentManager):
    """A example component manager that uses the message queue component manager."""

    def __init__(
        self: ExampleMessageQueueComponentManager,
        message_queue: MessageQueue,
        logger: logging.Logger,
        command_complete_callback: MockCallable,
        *args: Any,
        task_duration: float = 0.2,
        lock: Optional[threading.Lock] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param message_queue: the message queue to be used by the
            message queue component manager
        :param logger: a logger to be used by this component manager
        :param command_complete_callback: a callback to be called when
            the command completes.
        :param args: positional args to pass down to the superclass
        :param task_duration: how long the example task takes to run.
        :param lock: a lock that the component manager needs to hold
            when doing its work
        :param kwargs: keyword args to pass down to the superclass.
        """
        self._command_complete_callback = command_complete_callback
        self._task_duration = task_duration
        self._lock = lock
        super().__init__(message_queue, logger, *args, **kwargs)

    def run_synchronously(
        self: ExampleMessageQueueComponentManager,
    ) -> ResultCode:
        """
        Run the example task synchronously.

        :return: a result code
        """
        return self._slow_stuff("foo", fake_kwarg="bah")

    def enqueue_via_method(
        self: ExampleMessageQueueComponentManager,
    ) -> ResultCode:
        """
        Enqueue the example task.

        :return: a result code
        """
        return self.enqueue(self._slow_stuff, "foo", fake_kwarg="bah")

    @enqueue
    def enqueue_via_decorator(
        self: ExampleMessageQueueComponentManager,
    ) -> ResultCode:
        """
        Enqueue the example task using the decorator.

        :return: a result code
        """
        return self._slow_stuff("foo", fake_kwarg="bah")

    def _slow_stuff(
        self: ExampleMessageQueueComponentManager,
        fake_arg: Any,
        *,
        fake_kwarg: Any,
    ) -> ResultCode:
        """
        Run a slow task.

        :param fake_arg: a fake positional argument
        :param fake_kwarg: a fake keyword argument

        :return: a result code
        """
        with self._lock or nullcontext():
            time.sleep(self._task_duration)
            self._command_complete_callback()
            return ResultCode.OK


class TestMessageQueueComponentManager:
    """Tests of the message passing component manager."""

    @pytest.fixture()
    def task_duration(
        self: TestMessageQueueComponentManager,
    ) -> float:
        """
        Return the duration of the task to be queued.

        :return: the duration of the task to be queued.
        """
        return 1.1

    @pytest.fixture()
    def command_complete_callback(
        self: TestMessageQueueComponentManager,
        mock_callback_factory: Callable[[], unittest.mock.Mock],
    ) -> unittest.mock.Mock:
        """
        Return a callback to be called when the command completes.

        :param mock_callback_factory: fixture that provides a mock
            callback factory (i.e. an object that returns mock callbacks
            when called).

        :return: a callback to be called when the command completes.
        """
        return mock_callback_factory()

    @pytest.fixture()
    def lock(self: TestMessageQueueComponentManager) -> threading.Lock:
        """
        Return a lock to be passed to the message queue component manager under test.

        :return: a lock to be passed to the message queue component
            manager under test.
        """
        return threading.Lock()

    @pytest.fixture()
    def message_queue(
        self: TestMessageQueueComponentManager,
        logger: logging.Logger,
        message_queue_size_callback: MockCallable,
    ) -> MessageQueue:
        """
        Return a message queue for the message queue component manager to use.

        This message queue will have a maximum size of 1, and a single
        worker thread.

        :param logger: a logger for the message queue to use.
        :param message_queue_size_callback: a callback to be called when
            the size of the message queue changes.

        :return: a message queue for the message queue component manager
            under test to use.
        """
        return MessageQueue(logger, 1, 1, message_queue_size_callback)

    @pytest.fixture()
    def message_queue_component_manager(
        self: TestMessageQueueComponentManager,
        message_queue: MessageQueue,
        task_duration: float,
        lock: threading.Lock,
        command_complete_callback: MockCallable,
        logger: logging.Logger,
        communication_status_changed_callback: MockCallable,
        component_power_mode_changed_callback: MockCallable,
        component_fault_callback: MockCallable,
    ) -> ExampleMessageQueueComponentManager:
        """
        Return a message passing component manager for testing.

        It has a single private slow routine, and two public methods for
        invoking that slow routine: one runs it directly, the other runs
        it via a message queue.

        :param message_queue: the message queue to be used by the
            message queue component manager
        :param lock: a lock that the component manager needs to hold
            when doing its work
        :param task_duration: how long to wait for the task to complete
        :param command_complete_callback: a callback to be called when
            the command completes.
        :param logger: a logger for this object to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)

        :return: a message passing component manager for testing.
        """
        return ExampleMessageQueueComponentManager(
            message_queue,
            logger,
            command_complete_callback,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            task_duration=task_duration,
            lock=lock,
        )

    def test_run(
        self: TestMessageQueueComponentManager,
        message_queue_component_manager: ExampleMessageQueueComponentManager,
        command_complete_callback: MockCallable,
    ) -> None:
        """
        Test commands that run directly.

        :param message_queue_component_manager: the message queue
            component manager under test
        :param command_complete_callback: a callback to be called when
            the command completes.
        """
        result_code = message_queue_component_manager.run_synchronously()
        assert result_code == ResultCode.OK
        command_complete_callback.assert_next_call()

    @pytest.mark.parametrize(
        "command_name", ["enqueue_via_method", "enqueue_via_decorator"]
    )
    def test_enqueue(
        self: TestMessageQueueComponentManager,
        message_queue_component_manager: ExampleMessageQueueComponentManager,
        command_name: str,
        task_duration: float,
        command_complete_callback: MockCallable,
    ) -> None:
        """
        Test commands that run via a queue.

        :param message_queue_component_manager: the message queue
            component manager under test
        :param command_name: name of the command to run
        :param task_duration: how long to wait for the task to complete
        :param command_complete_callback: a callback to be called when
            the command completes.
        """
        command = getattr(message_queue_component_manager, command_name)
        result_code = command()
        assert result_code == ResultCode.QUEUED
        command_complete_callback.assert_not_called(timeout=task_duration * 0.9)
        command_complete_callback.assert_next_call()

    def test_full(
        self: TestMessageQueueComponentManager,
        message_queue_component_manager: ExampleMessageQueueComponentManager,
        lock: threading.Lock,
        message_queue_size_callback: MockCallable,
    ) -> None:
        """
        Test that the message queue returns failed once it is full.

        :param message_queue_component_manager: the message queue
            component manager under test
        :param lock: a lock that the component manager needs to hold
            when doing its work
        :param message_queue_size_callback: a callback to be called when
            the size of the message queue changes.
        """
        with lock:
            result_code = message_queue_component_manager.enqueue_via_method()
            assert result_code == ResultCode.QUEUED
            message_queue_size_callback.assert_next_call(1)
            # this task will be pulled from the queue and commenced, but cannot finish
            # because we hold the lock.
            message_queue_size_callback.assert_next_call(0)

            result_code = message_queue_component_manager.enqueue_via_method()
            assert result_code == ResultCode.QUEUED
            message_queue_size_callback.assert_next_call(1)
            # this task won't be pulled from the queue because there's only one worker
            # thread, and it is busy with the previous task.
            message_queue_size_callback.assert_not_called()

            # the max queue size is 1, so the queue is now full. If we try to enqueue
            # another task it will fail
            result_code = message_queue_component_manager.enqueue_via_method()
            assert result_code == ResultCode.FAILED
            message_queue_size_callback.assert_not_called()
