# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a functionality for component managers in MCCS."""
from __future__ import annotations  # allow forward references in type hints

import enum
import logging
import threading
from typing import Any, Callable, Optional

from ska_tango_base.base import BaseComponentManager
from ska_tango_base.base.task_queue_manager import QueueManager
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerState
from typing_extensions import Protocol

from ska_low_mccs.utils import ThreadsafeCheckingMeta, threadsafe

__all__ = [
    "MccsComponentManager",
    "MccsComponentManagerProtocol",
]


class MccsComponentManagerProtocol(Protocol):
    """
    Specification of the interface of an MCCS component manager (for type-checking).

    Classes that provide this interface are considered to be an MCCS
    component manager even if they don't inherit from
    MccsComponentManager. (e.g. the SwitchingComponentManager implements
    a passthrough mechanism that makes it an MCCS component manager even
    though it doesn't inherit from MccsComponentManager).
    """

    @property
    def communication_status(
        self: MccsComponentManagerProtocol,
    ) -> CommunicationStatus:
        """Return the status of communication with the component."""
        ...

    def start_communicating(self: MccsComponentManagerProtocol) -> None:
        """Establish communication with the component."""
        ...

    def stop_communicating(self: MccsComponentManagerProtocol) -> None:
        """Break off communicating with the component."""
        ...

    def off(self: MccsComponentManagerProtocol) -> ResultCode | None:
        """Turn off the component."""
        ...

    def standby(self: MccsComponentManagerProtocol) -> ResultCode | None:
        """Put the component into standby mode."""
        ...

    def on(self: MccsComponentManagerProtocol) -> ResultCode | None:
        """Turn on the component."""
        ...

    def reset(self: MccsComponentManagerProtocol) -> ResultCode | None:
        """Reset the component."""
        ...


class MccsComponentManager(TaskExecutorComponentManager, metaclass=ThreadsafeCheckingMeta):
    """
    A base component manager for MCCS.

    This class exists to modify the interface of the
    :py:class:`ska_tango_base.base.component_manager.BaseComponentManager`.
    The ``BaseComponentManager`` accepts an ``op_state_model` argument,
    and is expected to interact directly with it. This is not a very
    good design decision. It is better to leave the ``op_state_model``
    behind in the device, and drive it indirectly through callbacks.

    Therefore this class accepts three callback arguments: one for when
    communication with the component changes, one for when the power
    mode of the component changes, and one for when the component fault
    status changes. In the last two cases, callback hooks are provided
    so that the component can indicate the change to this component
    manager.
    """

    def __init__(
        self: MccsComponentManager,
        logger: logging.Logger,
        communication_status_changed_callback: Optional[
            Callable[[CommunicationStatus], None]
        ],
        component_state_changed_callback: Optional[Callable],
        *args: Any,
        **kwargs: Any,
    ):
        """
        Initialise a new instance.

        :param logger: a logger for this instance to use
        :param communication_status_changed_callback: callback to be
            called when the status of communications between the
            component manager and its component changes.
        :param component_state_changed_callback: callback to be
            called when the power mode of the component changes.
        :param args: other positional args
        :param kwargs: other keyword args
        """
        self.logger = logger

        self.__communication_lock = threading.Lock()
        self._communication_status = CommunicationStatus.DISABLED
        self._communication_status_changed_callback = (
            communication_status_changed_callback
        )

        self._power_state_lock = threading.RLock()
        self._power_state: Optional[PowerState] = None

        self._component_state_changed_callback = (
            component_state_changed_callback
        )

        self._faulty: Optional[bool] = None

        super().__init__(None, *args, **kwargs)

    def start_communicating(self: MccsComponentManager) -> None:
        """Start communicating with the component."""
        if self.communication_status == CommunicationStatus.ESTABLISHED:
            return
        if self.communication_status == CommunicationStatus.DISABLED:
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)
        # It's up to subclasses to set communication status to ESTABLISHED via a call
        # to update_communication_status()

    def stop_communicating(self: MccsComponentManager) -> None:
        """Break off communicating with the component."""
        if self.communication_status == CommunicationStatus.DISABLED:
            return

        self.update_communication_status(CommunicationStatus.DISABLED)
        self.component_state_changed(None)

    @threadsafe
    def update_communication_status(
        self: MccsComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in communication status.

        This is a helper method for use by subclasses.

        :param communication_status: the new communication status of the
            component manager.
        """
        if self._communication_status != communication_status:
            with self.__communication_lock:
                self._communication_status = communication_status
                if self._communication_status_changed_callback is not None:
                    self._communication_status_changed_callback(communication_status)

    @property
    def is_communicating(self: MccsComponentManager) -> bool:
        """
        Return communication with the component is established.

        MCCS uses the more expressive :py:attr:`communication_status`
        for this, but this is still needed as a base classes hook.

        :return: whether communication with the component is
            established.
        """
        return self.communication_status == CommunicationStatus.ESTABLISHED

    @property
    def communication_status(
        self: MccsComponentManager,
    ) -> CommunicationStatus:
        """
        Return the communication status of this component manager.

        This is implemented as a replacement for the
        ``is_communicating`` property, which should be deprecated.

        :return: status of the communication channel with the component.
        """
        return self._communication_status

    def component_state_changed(
        self: MccsComponentManager, power_state: PowerState
    ) -> None:
        """
        Handle notification that the component's power mode has changed.

        This is a callback hook, to be passed to the managed component.

        :param power_state: the new power mode of the component
        """
        # TODO merge into one call
        with self._power_state_lock:
            self.update_component_power_mode(power_state)

        self.update_component_fault(faulty)

    @threadsafe
    def update_component_power_mode(
        self: MccsComponentManager, power_state: Optional[PowerState]
    ) -> None:
        """
        Update the power mode, calling callbacks as required.

        This is a helper method for use by subclasses.

        :param power_state: the new power mode of the component. This can
            be None, in which case the internal value is updated but no
            callback is called. This is useful to ensure that the
            callback is called next time a real value is pushed.
        """
        if self._power_state != power_state:
            self._power_state = power_state
            if (
                self._component_state_changed_callback is not None
                and power_state is not None
            ):
                self._component_state_changed_callback({"power": power_state})

    def update_component_fault(
        self: MccsComponentManager, faulty: Optional[bool]
    ) -> None:
        """
        Update the component fault status, calling callbacks as required.

        This is a helper method for use by subclasses.

        :param faulty: whether the component has faulted. If ``False``,
            then this is a notification that the component has
            *recovered* from a fault.
        """
        if self._faulty != faulty:
            self._faulty = faulty
            if self._component_state_changed_callback is not None and faulty is not None:
                self._component_state_changed_callback({"fault": faulty})

    @property
    def power_state(self: MccsComponentManager) -> Optional[PowerState]:
        """
        Return the power mode of this component manager.

        :return: the power mode of this component manager.
        """
        return self._power_state

    @property
    def faulty(self: MccsComponentManager) -> Optional[bool]:
        """
        Return whether this component manager is currently experiencing a fault.

        :return: whether this component manager is currently
            experiencing a fault.
        """
        return self._faulty
