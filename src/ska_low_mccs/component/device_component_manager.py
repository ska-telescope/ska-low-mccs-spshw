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
import threading
from typing import Any, Callable, Optional

import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    ObsState,
    PowerState,
)
from ska_tango_base.executor import TaskStatus

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import MccsComponentManager, check_communicating

__all__ = ["DeviceComponentManager", "ObsDeviceComponentManager"]


class DeviceComponentManager(MccsComponentManager):
    """An abstract component manager for a Tango device component."""

    def __init__(
        self: DeviceComponentManager,
        fqdn: str,
        logger: logging.Logger,
        max_workers: Optional[int],
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._fqdn: str = fqdn
        self._proxy: Optional[MccsDeviceProxy] = None
        self._logger = logger

        self._health: Optional[HealthState] = None
        self._device_health_state = HealthState.UNKNOWN
        self._device_admin_mode = AdminMode.OFFLINE
        self._component_state_changed_callback = component_state_changed_callback
        self._event_callbacks = {
            "healthState": self._device_health_state_changed,
            "adminMode": self._device_admin_mode_changed,
        }

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: DeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This is a public method that enqueues the work to be done.
        """
        super().start_communicating()
        task_status, response = self.submit_task(
            self._connect_to_device, args=[self._event_callbacks], task_callback=None
        )

    def _connect_to_device(
        self: DeviceComponentManager,
        event_callbacks: dict[str, Callable],
        task_callback: Optional[Callable] = None,
        task_abort_event: threading.Event = None,
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
        self._proxy = MccsDeviceProxy(self._fqdn, self._logger, connect=False)
        try:
            self._proxy.connect()
        except tango.DevFailed as dev_failed:
            self._proxy = None
            raise ConnectionError(
                f"Could not connect to '{self._fqdn}'"
            ) from dev_failed
        self.update_communication_state(CommunicationStatus.ESTABLISHED)

        # TODO: Determine if we need this IF
        # if self._health_changed_callback is not None:
        for event, callback in event_callbacks.items():
            self._proxy.add_change_event_callback(event, callback)

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result=f"Connected to '{self._fqdn}'"
            )

    # class ConnectToDeviceBase(SlowCommand):
    #     """Base command class for connection to be enqueued."""

    #     def do(  # type: ignore[override]
    #         self: DeviceComponentManager.ConnectToDeviceBase,
    #     ) -> tuple[ResultCode, str]:
    #         """
    #         Establish communication with the component, then start monitoring.

    #         This contains the actual communication logic that is enqueued to
    #         be run asynchronously.

    #         :raises ConnectionError: if the attempt to establish
    #             communication with the channel fails.
    #         :return: a result code and message
    #         """
    #         self._proxy = MccsDeviceProxy(self._fqdn, self._logger, connect=False)
    #         try:
    #             self._proxy.connect()
    #         except tango.DevFailed as dev_failed:
    #             self._proxy = None
    #             raise ConnectionError(
    #                 f"Could not connect to '{self._fqdn}'"
    #             ) from dev_failed

    #         self.update_communication_state(CommunicationStatus.ESTABLISHED)
    #         self._proxy.add_change_event_callback("state", self._device_state_changed)

    #         if self._health_changed_callback is not None:
    #             self._proxy.add_change_event_callback(
    #                 "healthState", self._device_health_state_changed
    #             )
    #             self._proxy.add_change_event_callback(
    #                 "adminMode", self._device_admin_mode_changed
    #             )
    #         return ResultCode.OK, f"Connected to '{self._fqdn}'"

    # class ConnectToDevice(ConnectToDeviceBase):
    #     """
    #     General connection command class.

    #     Class that can be overridden by a derived class or instantiated
    #     at the DeviceComponentManager level.
    #     """

    #     pass

    def stop_communicating(self: DeviceComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        # TODO: Presumably, unsubscriptions occur before the underlying
        # tango.DeviceProxy is deleted. But we should really do this
        # explicitly.
        self._proxy = None

    @check_communicating
    def on(self: DeviceComponentManager) -> tuple[ResultCode, str]:
        """
        Turn the device on.

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
        if self.power_state == PowerState.ON:
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
    def off(self: DeviceComponentManager) -> tuple(ResultCode, str):
        """
        Turn the device off.

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
        if self.power_state == PowerState.OFF:
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
    def standby(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_state == PowerState.STANDBY:
            return None  # already standby
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.Standby()
        return result_code

    @check_communicating
    def reset(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self._faulty:
            return None  # no point resetting a device that isn't faulty.
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.Reset()
        return result_code

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
        assert (
            event_name.lower() == "state"
        ), f"state changed callback called but event_name is {event_name}."

        if self._component_state_changed_callback:
            if event_value == tango.DevState.FAULT and not self.faulty:
                self._component_state_changed_callback({"fault": True})
            elif event_value != tango.DevState.FAULT and self.faulty:
                self._component_state_changed_callback({"fault": False})

            with self._power_state_lock:
                if event_value == tango.DevState.OFF:
                    self._component_state_changed_callback(
                        {"power_state": PowerState.OFF}
                    )
                elif event_value == tango.DevState.STANDBY:
                    self._component_state_changed_callback(
                        {"power_state": PowerState.STANDBY}
                    )
                elif event_value == tango.DevState.ON:
                    self._component_state_changed_callback(
                        {"power_state": PowerState.ON}
                    )
                else:  # INIT, DISABLE, UNKNOWN, FAULT
                    self._component_state_changed_callback(
                        {"power_state": PowerState.UNKNOWN}
                    )

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
        assert (
            event_name.lower() == "healthstate"
        ), f"health state changed callback called but event_name is {event_name}."

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
        assert (
            event_name.lower() == "adminmode"
        ), f"admin mode changed callback called but event_name is {event_name}."

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
                self._component_state_changed_callback({"health_state": self._health})


class ObsDeviceComponentManager(DeviceComponentManager):
    """An abstract component manager for a Tango observation device component."""

    def __init__(
        self: ObsDeviceComponentManager,
        fqdn: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device.
        :param logger: the logger to be used by this object.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes.
        :param component_state_changed_callback: callback to be called when the component's state changes.
        :param max_workers: Maximum number of workers in thread pool.
        """
        self._component_state_changed_callback = component_state_changed_callback
        self._obs_state_changed_callback = component_state_changed_callback
        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        self._event_callbacks["obsState"] = self._obs_state_changed

    def _obs_state_changed(
        self: ObsDeviceComponentManager,
        event_name: str,
        event_value: ObsState,
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle an change event on device obs state.

        :param event_name: name of the event; will always be
            "obsState" for this callback
        :param event_value: the new admin mode
        :param event_quality: the quality of the change event
        """
        assert (
            event_name.lower() == "obsstate"
        ), f"obs state changed callback called but event_name is {event_name}."

        if self._obs_state_changed_callback is not None:
            self._obs_state_changed_callback({"obsstate_changed": event_value})
