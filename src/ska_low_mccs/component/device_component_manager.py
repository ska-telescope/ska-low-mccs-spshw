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

import tango
from ska_tango_base.commands import ResultCode, SlowCommand
from ska_tango_base.control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    ObsState,
    PowerState,
)

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import MccsComponentManager, check_communicating

__all__ = ["DeviceComponentManager", "ObsDeviceComponentManager"]


class DeviceComponentManager(MccsComponentManager):
    """An abstract component manager for a Tango device component."""

    def __init__(
        self: DeviceComponentManager,
        fqdn: str,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Optional[Callable[[Any], None]],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
        :param push_change_event: mechanism to inform the base classes
            what method to call; typically device.push_change_event.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
            When the health state of the device changes, the value it is called
            with will normally be a HealthState, but may be None if the
            admin mode of the device indicates that the device's health
            should not be included in upstream health rollup.
        """
        self._fqdn: str = fqdn
        self._proxy: Optional[MccsDeviceProxy] = None
        self._logger = logger

        self._health: Optional[HealthState] = None
        self._device_health_state = HealthState.UNKNOWN
        self._device_admin_mode = AdminMode.OFFLINE
        self._component_state_changed_callback = component_state_changed_callback

        super().__init__(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: DeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This is a public method that enqueues the work to be done.
        """
        super().start_communicating()
        connect_command = self.ConnectToDevice(target=self)
        # Enqueue the connect command
        # _ = self.enqueue(connect_command)

    class ConnectToDeviceBase(SlowCommand):
        """Base command class for connection to be enqueued."""

        def do(  # type: ignore[override]
            self: DeviceComponentManager.ConnectToDeviceBase,
        ) -> tuple[ResultCode, str]:
            """
            Establish communication with the component, then start monitoring.

            This contains the actual communication logic that is enqueued to
            be run asynchronously.

            :raises ConnectionError: if the attempt to establish
                communication with the channel fails.
            :return: a result code and message
            """
            target = self.target
            target._proxy = MccsDeviceProxy(target._fqdn, target._logger, connect=False)
            try:
                target._proxy.connect()
            except tango.DevFailed as dev_failed:
                target._proxy = None
                raise ConnectionError(
                    f"Could not connect to '{target._fqdn}'"
                ) from dev_failed

            target.update_communication_status(CommunicationStatus.ESTABLISHED)
            target._proxy.add_change_event_callback(
                "state", target._device_state_changed
            )

            if target._health_changed_callback is not None:
                target._proxy.add_change_event_callback(
                    "healthState", target._device_health_state_changed
                )
                target._proxy.add_change_event_callback(
                    "adminMode", target._device_admin_mode_changed
                )
            return ResultCode.OK, f"Connected to '{target._fqdn}'"

    class ConnectToDevice(ConnectToDeviceBase):
        """
        General connection command class.

        Class that can be overridden by a derived class or instantiated
        at the DeviceComponentManager level.
        """

        pass

    def stop_communicating(self: DeviceComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        # TODO: Presumably, unsubscriptions occur before the underlying
        # tango.DeviceProxy is deleted. But we should really do this
        # explicitly.
        self._proxy = None

    @check_communicating
    def on(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device on.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerState.ON:
            return None  # already on
        on_command = self.DeviceProxyOnCommand(target=self)
        # Enqueue the on command.
        # This is a fire and forget command, so we don't need to keep unique ID.
        # _, result_code = self.enqueue(on_command)
        return result_code

    class DeviceProxyOnCommand(SlowCommand):
        """Base command class for the on command to be enqueued."""

        def do(  # type: ignore[override]
            self: DeviceComponentManager.DeviceProxyOnCommand,
        ) -> ResultCode:
            """
            On command implementation that simply calls On, on its proxy.

            :return: a result code.
            """
            try:
                assert self.target._proxy is not None  # for the type checker
                ([result_code], _) = self.target._proxy.On()  # Fire and forget
            except TypeError as type_error:
                self.target._logger.fatal(
                    f"Typeerror: FQDN is {self.target._fqdn}, type_error={type_error}"
                )
                result_code = ResultCode.FAILED
            return result_code

    @check_communicating
    def off(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerState.OFF:
            return None  # already off
        off_command = self.DeviceProxyOffCommand(target=self)
        # Enqueue the off command.
        # This is a fire and forget command, so we don't need to keep unique ID.
        _, result_code = self.enqueue(off_command)
        return result_code

    class DeviceProxyOffCommand(SlowCommand):
        """Base command class for the off command to be enqueued."""

        def do(  # type: ignore[override]
            self: DeviceComponentManager.DeviceProxyOffCommand,
        ) -> ResultCode:
            """
            Off command implementation that simply calls Off, on its proxy.

            :return: a result code.
            """
            try:
                assert self.target._proxy is not None  # for the type checker
                (
                    [result_code],
                    _,
                ) = self.target._proxy.Off()  # Fire and forget
            except TypeError as type_error:
                self.target._logger.fatal(
                    f"Typeerror: FQDN is {self.target._fqdn}, type_error={type_error}"
                )
                result_code = ResultCode.FAILED
            return result_code

    @check_communicating
    def standby(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerState.STANDBY:
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

        if event_value == tango.DevState.FAULT and not self.faulty:
            self.update_component_fault(True)
        elif event_value != tango.DevState.FAULT and self.faulty:
            self.update_component_fault(False)

        with self._power_mode_lock:
            if event_value == tango.DevState.OFF:
                self.update_component_power_mode(PowerState.OFF)
            elif event_value == tango.DevState.STANDBY:
                self.update_component_power_mode(PowerState.STANDBY)
            elif event_value == tango.DevState.ON:
                self.update_component_power_mode(PowerState.ON)
            else:  # INIT, DISABLE, UNKNOWN, FAULT
                self.update_component_power_mode(PowerState.UNKNOWN)

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
            if self._health_changed_callback is not None:
                self._health_changed_callback(self._health)


class ObsDeviceComponentManager(DeviceComponentManager):
    """An abstract component manager for a Tango observation device component."""

    def __init__(
        self: ObsDeviceComponentManager,
        fqdn: str,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Optional[Callable[[PowerState], None]],
        component_fault_callback: Optional[Callable[[bool], None]],
        health_changed_callback: Optional[
            Callable[[Optional[HealthState]], None]
        ] = None,
        obs_state_changed_callback: Optional[Callable[[ObsState], None]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
        :param push_change_event: mechanism to inform the base classes
            what method to call; typically device.push_change_event.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param health_changed_callback: callback to be called when the
            health state of the device changes. The value it is called
            with will normally be a HealthState, but may be None if the
            admin mode of the device indicates that the device's health
            should not be included in upstream health rollup.
        :param obs_state_changed_callback: callback to be called when
            the observation state of the device changes.
        """
        self._obs_state_changed_callback = obs_state_changed_callback
        super().__init__(
            fqdn,
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            health_changed_callback,
        )

    class ConnectToDevice(DeviceComponentManager.ConnectToDeviceBase):
        """
        General connection command class.

        Class that can be overridden by a derived class or instantiated
        at the DeviceComponentManager level.
        """

        def do(  # type: ignore[override]
            self: ObsDeviceComponentManager.ConnectToDevice,
        ) -> tuple[ResultCode, str]:
            """
            Establish communication with the component, then start monitoring.

            This contains the actual communication logic that is enqueued to
            be run asynchronously.

            :return: a result code and message
            """
            result_code, message = super().do()
            assert self.target._proxy is not None  # for the type checker
            self.target._proxy.add_change_event_callback(
                "obsState", self.target._obs_state_changed
            )
            return result_code, message

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
            self._obs_state_changed_callback(event_value)
