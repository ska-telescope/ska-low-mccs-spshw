# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements an abstract object component."""
from __future__ import annotations  # allow forward references in type hints

from typing import Any, Callable, Optional

from ska_tango_base.control_model import PowerState
from ska_tango_base.executor import TaskStatus

__all__ = ["ObjectComponent"]


class ObjectComponent:
    """
    An abstract component that is an object in this process.

    The concept of a "component" covers anything that a component
    manager might manage, including

    * hardware
    * software services such as databases or compute servers
    * groups of Tango devices
    * software running in its own process or thread
    * software objects in the current process.

    This class defines an interface for the last of these -- a component
    that is simply a python object running in the current process. An
    example of such a component is a simple simulator or stub that
    pretends to be a more substantial component.
    """

    @property
    def faulty(self: ObjectComponent) -> bool:
        """
        Return whether this component is faulty.

        Detecting component faults is a shared responsibility between
        component and component manager. In some cases, a component may
        be able to ability to self-diagnose a fault. In other cases, it
        will be update to the component manager to diagnose a fault from
        the component behaviour.

        This property is implemented here to return False. Thus, if a
        subclass does not override this method, it is assumed to have no
        self-diagnosis capability.

        :return: whether this component is faulty; defaulting here to
            ``False``.
        """
        return False

    def set_fault_callback(
        self: ObjectComponent,
        fault_callback: Optional[Callable[[dict[str, Any]], None]],
    ) -> None:
        """
        Set the fault callback.

        Here we implement a default functionality for components that
        lack the ability to detect and raise a fault. This method calls
        the callback once with False, and doesn't register the callback,
        thus the fault status of the component will be False
        forevermore.

        :param fault_callback: the callback to be called when the
            component changes.
        """
        if fault_callback is not None:
            fault_callback({"fault": False})

    @property
    def power_mode(self: ObjectComponent) -> PowerState:
        """
        Return the power mode of the component.

        Here we implement a default functionality for components that do
        not manage their own power mode. From their own point of view
        they are always-on devices, though there may be an upstream
        power supply device that supplies/denies them power.

        :return: the power mode of the component.
        """
        return PowerState.ON

    def set_power_mode_changed_callback(
        self: ObjectComponent,
        power_mode_changed_callback: Optional[Callable[[dict[str, Any]], None]],
    ) -> None:
        """
        Set the callback to be called when the power mode of the component changes.

        Here we implement a default functionality for components that do
        not manage their own power mode. From their own point of view
        they are always-on devices, though there may be an upstream
        power supply device that supplies/denies them power. Thus, this
        method calls the callback once with PowerState.ON, and doesn't
        register the callback, so the power mode of the component will
        be ON forevermore.

        :param power_mode_changed_callback: the callback to be called
            when the component changes.
        """
        if power_mode_changed_callback is not None:
            power_mode_changed_callback({"power_state": PowerState.ON})

    def off(self: ObjectComponent) -> tuple[TaskStatus, str]:
        """
        Turn the component off.

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def standby(self: ObjectComponent) -> tuple[TaskStatus, str]:
        """
        Put the component into low-power standby mode.

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def on(self: ObjectComponent) -> tuple[TaskStatus, str]:
        """
        Turn the component on.

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def reset(self: ObjectComponent) -> tuple[TaskStatus, str]:
        """
        Reset the component (from fault state).

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("ObjectComponent is abstract.")
