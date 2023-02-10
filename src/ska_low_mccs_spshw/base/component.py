#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module is a temporary local re-implementation of ObjectComponentManager.

It needs to be upstreamed to -common.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import tango
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    TaskStatus,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.component import MccsBaseComponentManager, check_communicating
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = [
    "ObjectComponent",
    "ObjectComponentManager",
]


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
        fault_callback: Optional[Callable[..., None]],
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
            fault_callback(fault=False)

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
        power_mode_changed_callback: Optional[Callable[..., None]],
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
            power_mode_changed_callback(power=PowerState.ON)

    def off(
        self: ObjectComponent, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component off.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def standby(
        self: ObjectComponent, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the component into low-power standby mode.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def on(
        self: ObjectComponent, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component on.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("This is an always-on component.")

    def reset(
        self: ObjectComponent, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the component (from fault state).

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this class is abstract.
        """
        raise NotImplementedError("ObjectComponent is abstract.")


class ObjectComponentManager(MccsBaseComponentManager):
    """Temporary local re-implementation of ObjectComponentManager."""

    def __init__(
        self: ObjectComponentManager,
        component: ObjectComponent,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param component: the component managed by this component
            manager
        :param logger: a logger for this object to use
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called
            when the component state changes.
        """
        self._component = component
        self._fail_communicate = False

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            fault=None,
            power=PowerState.UNKNOWN,
        )

    def start_communicating(self: ObjectComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        :raises ConnectionError: if the attempt to establish
            communication with the channel fails.
        """
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        if self._fail_communicate:
            raise ConnectionError("Failed to connect")

        self._update_communication_state(CommunicationStatus.ESTABLISHED)

        self._component.set_power_mode_changed_callback(self._update_component_state)
        self._component.set_fault_callback(self._update_component_state)

    def stop_communicating(self: ObjectComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        self._component.set_fault_callback(None)
        self._component.set_power_mode_changed_callback(None)

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)

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
            self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

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
        Reset the component.

        :param task_callback: Update task state, defaults to None

        :return: a taskstatus and message
        """
        return self._component.reset(task_callback)


# pylint: disable=too-many-instance-attributes
class DeviceComponentManager(TaskExecutorComponentManager):
    """An abstract component manager for a Tango device component."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: DeviceComponentManager,
        name: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param name: the name of the device
        :param logger: the logger to be used by this object.
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._name: str = name
        self._proxy: Optional[MccsDeviceProxy] = None
        self._logger = logger

        self._power_state: Optional[PowerState] = None
        self._faulty: Optional[bool] = None
        self._health: Optional[HealthState] = None
        self._device_health_state = HealthState.UNKNOWN
        self._device_admin_mode = AdminMode.OFFLINE
        self._component_state_changed_callback = component_state_changed_callback
        self._event_callbacks = {
            "healthState": self._device_health_state_changed,
            "adminMode": self._device_admin_mode_changed,
            "state": self._device_state_changed,
        }

        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            max_workers=max_workers,
            power=PowerState.UNKNOWN,
            fault=None,
        )

    def start_communicating(self: DeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This is a public method that enqueues the work to be done.
        """
        task_status, response = self.submit_task(
            self._connect_to_device, args=[self._event_callbacks], task_callback=None
        )

    def _connect_to_device(
        self: DeviceComponentManager,
        event_callbacks: dict[str, Callable],
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Establish communication with the component, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.

        :param event_callbacks: a dictionary of event callbacks
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None

        :raises ConnectionError: if the attempt to establish
            communication with the channel fails.
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        self._proxy = MccsDeviceProxy(self._name, self._logger, connect=False)
        try:
            self._proxy.connect()
        except tango.DevFailed as dev_failed:
            self._proxy = None
            raise ConnectionError(
                f"Could not connect to '{self._name}'"
            ) from dev_failed
        self._update_communication_state(CommunicationStatus.ESTABLISHED)

        # TODO: Determine if we need this IF
        # if self._health_changed_callback is not None:
        for event, callback in event_callbacks.items():
            self._proxy.add_change_event_callback(event, callback)

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result=f"Connected to '{self._name}'"
            )

    def stop_communicating(self: DeviceComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        # TODO: Presumably, unsubscriptions occur before the underlying
        # tango.DeviceProxy is deleted. But we should really do this
        # explicitly.
        self._proxy = None

    @check_communicating
    def on(
        self: DeviceComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the device on.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: a result code and message
        """
        return self.submit_task(self._on, task_callback=None)

    def _on(
        self: DeviceComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        On command implementation that simply calls On, on its proxy.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        if self._power_state == PowerState.ON:
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED, result="PowerState already on"
                )
        else:
            assert self._proxy is not None  # for the type checker
            self._proxy.On()  # Fire and forget
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED, result="PowerState on completed"
                )

    @check_communicating
    def off(
        self: DeviceComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the device off.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: a result code & message
        """
        return self.submit_task(self._off, task_callback=None)

    def _off(
        self: DeviceComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Off command implementation that simply calls Off, on its proxy.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        if self._power_state == PowerState.OFF:
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED, result="PowerState already off"
                )
        else:
            assert self._proxy is not None  # for the type checker
            self._proxy.Off()  # Fire and forget
            if task_callback:
                task_callback(
                    status=TaskStatus.COMPLETED, result="PowerState off completed"
                )

    @check_communicating
    def standby(
        self: DeviceComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the device to standby.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: a result code, or None if there was nothing to do.
        """
        if self._power_state == PowerState.STANDBY:
            return (TaskStatus.COMPLETED, "Device was already in standby mode")

        return self.submit_task(self._standby, task_callback=None)

    def _standby(
        self: DeviceComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Standby command implementation that simply calls Standby, on its proxy.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        assert self._proxy is not None  # for the type checker
        self._proxy.Standby()  # Fire and forget
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="PowerState standby completed"
            )

    @check_communicating
    def reset(
        self: DeviceComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the device.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: a result code, or None if there was nothing to do.
        """
        return self.submit_task(self._reset, task_callback=None)

    def _reset(
        self: DeviceComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Reset command implementation that simply calls Reset, on its proxy.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        assert self._proxy is not None  # for the type checker
        self._proxy.Reset()  # Fire and forget
        if task_callback:
            task_callback(status=TaskStatus.COMPLETED, result="Reset completed")

    @property
    def health(self: DeviceComponentManager) -> Optional[HealthState]:
        """
        Return the evaluated health state of the device.

        This will be either the health state that the device reports, or
        None if the device is in an admin mode that indicates that its
        health should not be rolled up.

        :return: the evaluated health state of the device.
        """
        return self._health

    def _device_state_changed(
        self: DeviceComponentManager,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle an change event on device state.

        :param event_name: name of the event; will always be
            "state" for this callback
        :param event_value: the new state
        :param event_quality: the quality of the change event
        """
        if event_value == tango.DevState.FAULT:
            self._update_component_state(fault=True)
            return

        power_map = {
            tango.DevState.OFF: PowerState.OFF,
            tango.DevState.STANDBY: PowerState.STANDBY,
            tango.DevState.ON: PowerState.ON,
        }
        power = power_map.get(event_value, PowerState.UNKNOWN)
        self._update_component_state(power=power)

    def _device_health_state_changed(
        self: DeviceComponentManager,
        event_name: str,
        event_value: HealthState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle an change event on device health state.

        :param event_name: name of the event; will always be
            "healthState" for this callback
        :param event_value: the new health state
        :param event_quality: the quality of the change event
        """
        self._device_health_state = event_value
        self._update_health()

    def _device_admin_mode_changed(
        self: DeviceComponentManager,
        event_name: str,
        event_value: AdminMode,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle an change event on device admin mode.

        :param event_name: name of the event; will always be
            "adminMode" for this callback
        :param event_value: the new admin mode
        :param event_quality: the quality of the change event
        """
        self._device_admin_mode = event_value
        self._update_health()

    def _update_health(
        self: DeviceComponentManager,
    ) -> None:
        health = (
            self._device_health_state
            if self._device_admin_mode in [AdminMode.MAINTENANCE, AdminMode.ONLINE]
            else None
        )
        if self._health != health:
            self._health = health
            if self._component_state_changed_callback is not None:
                self._component_state_changed_callback(health=self._health)
