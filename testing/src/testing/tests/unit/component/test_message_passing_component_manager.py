"""This module contains tests of the switching_component_manager module."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable
import unittest.mock

import pytest

from ska_tango_base.commands import ResultCode

from ska_low_mccs.component import (
    MessageQueueComponentManager,
    enqueue,
)

from testing.harness.mock import MockCallable


class ExampleMessageQueueComponentManager(MessageQueueComponentManager):
    """A example component manager that uses the message queue component manager."""

    def __init__(
        self: ExampleMessageQueueComponentManager,
        command_complete_callback: MockCallable,
        *args: Any,
        task_duration: float = 0.2,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param command_complete_callback: a callback to be called when
            the command completes.
        :param args: positional args to pass down to the superclass
        :param task_duration: how long the example task takes to run.
        :param kwargs: keyword args to pass down to the superclass.
        """
        self._command_complete_callback = command_complete_callback
        self._task_duration = task_duration
        super().__init__(*args, **kwargs)

    def run_synchronously(self: ExampleMessageQueueComponentManager) -> ResultCode:
        """
        Run the example task synchronously.

        :return: a result code
        """
        return self._slow_stuff("foo", fake_kwarg="bah")

    def enqueue_via_method(self: ExampleMessageQueueComponentManager) -> ResultCode:
        """
        Enqueue the example task.

        :return: a result code
        """
        return self.enqueue(self._slow_stuff, "foo", fake_kwarg="bah")

    @enqueue
    def enqueue_via_decorator(self: ExampleMessageQueueComponentManager) -> ResultCode:
        """
        Enqueue the example task using the decorator.

        :return: a result code
        """
        return self._slow_stuff("foo", fake_kwarg="bah")

    def _slow_stuff(
        self: ExampleMessageQueueComponentManager, fake_arg: Any, *, fake_kwarg: Any
    ) -> ResultCode:
        """
        Run a slow task.

        :param fake_arg: a fake positional argument
        :param fake_kwarg: a fake keyword argument

        :return: a result code
        """
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
    def message_queue_component_manager(
        self: TestMessageQueueComponentManager,
        task_duration: float,
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
            command_complete_callback,
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            task_duration=task_duration,
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
