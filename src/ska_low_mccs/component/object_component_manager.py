# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements an abstract component manager for simple object components."""
from __future__ import annotations  # allow forward references in type hints

import logging
from typing import Any, Callable, Optional

from ska_tango_base.control_model import CommunicationStatus
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.component import (
    MccsComponentManager,
    ObjectComponent,
    check_communicating,
)
from ska_low_mccs.utils import threadsafe

__all__ = ["ObjectComponentManager"]


class ObjectComponentManager(MccsComponentManager):
    """
    An abstract component manager for a component that is an object in this process.

    The base component manager is a very general class that allows for
    management of remote components to which communication may need to
    be established and maintained. In cases where the component is
    simply an object running in the same process as its component
    manager (for example, a simple simulator), such complexity is not
    needed. This class eliminates that complexity, providing a basic
    framework for these simple component managers.
    """

    def __init__(
        self: ObjectComponentManager,
        component: ObjectComponent,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Optional[
            Callable[[CommunicationStatus], None]
        ],
        component_state_changed_callback: Optional[Callable[[dict[str, Any]], None]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param component: the commponent object to be managed by this
            component manager
        :param logger: a logger for this object to use
        :param max_workers: nos of worker threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param args: further positional arguments
        :param kwargs: further keyword arguments
        """
        self._component = component

        self._fail_communicate = False

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: ObjectComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        :raises ConnectionError: if the attempt to establish
            communication with the channel fails.
        """
        super().start_communicating()
        if self._fail_communicate:
            raise ConnectionError("Failed to connect")

        self.update_communication_state(CommunicationStatus.ESTABLISHED)

        self._component.set_power_mode_changed_callback(
            self.component_state_changed_callback
        )
        self._component.set_fault_callback(self.component_state_changed_callback)

    @threadsafe
    def stop_communicating(self: ObjectComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        self._component.set_fault_callback(None)
        self._component.set_power_mode_changed_callback(None)

    def simulate_communication_failure(
        self: ObjectComponentManager, fail_communicate: bool
    ) -> None:
        """
        Simulate (or stop simulating) a failure to communicate with the component.

        :param fail_communicate: whether the connection to the component
            is failing
        """
        self._fail_communicate = fail_communicate
        if (
            fail_communicate
            and self.communication_state == CommunicationStatus.ESTABLISHED
        ):
            self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

    @check_communicating
    def off(
        self: ObjectComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component off.

        :param task_callback: Update task state, defaults to None

        :return: a taskstatus and message.
        """
        return self._component.off(task_callback)

    @check_communicating
    def standby(
        self: ObjectComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the component into low-power standby mode.

        :param task_callback: Update task state, defaults to None

        :return: a taskstatus and message
        """
        return self._component.standby(task_callback)

    @check_communicating
    def on(
        self: ObjectComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component on.

        :param task_callback: Update task state, defaults to None

        :return: a taskstatus and message
        """
        return self._component.on(task_callback)

    @check_communicating
    def reset(
        self: ObjectComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the component (from fault state).

        :param task_callback: Update task state, defaults to None

        :return: a taskstatus and message
        """
        return self._component.reset(task_callback)