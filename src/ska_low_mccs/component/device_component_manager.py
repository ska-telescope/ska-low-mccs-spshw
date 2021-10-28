# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements an abstract component manager for simple object components."""
from __future__ import annotations  # allow forward references in type hints

import logging
from typing import Callable, Optional

import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode, HealthState, ObsState, PowerMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.component import (
    CommunicationStatus,
    check_communicating,
    MccsComponentManager,
)


__all__ = ["DeviceComponentManager", "ObsDeviceComponentManager"]


class DeviceComponentManager(MccsComponentManager):
    """An abstract component manager for a Tango device component."""

    def __init__(
        self: DeviceComponentManager,
        fqdn: str,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Optional[Callable[[PowerMode], None]],
        component_fault_callback: Optional[Callable[[bool], None]],
        health_changed_callback: Optional[
            Callable[[Optional[HealthState]], None]
        ] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
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
        """
        self._fqdn: str = fqdn
        self._proxy: Optional[MccsDeviceProxy] = None
        self._logger = logger

        self._health: Optional[HealthState] = None
        self._device_health_state = HealthState.UNKNOWN
        self._device_admin_mode = AdminMode.OFFLINE
        self._health_changed_callback = health_changed_callback

        super().__init__(
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
        )

    def start_communicating(self: DeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This is a public method that enqueues the work to be done.
        """
        super().start_communicating()
        self._connect_to_device()

    def _connect_to_device(self: DeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.

        :raises ConnectionError: if the attempt to establish
            communication with the channel fails.
        """
        self._proxy = MccsDeviceProxy(self._fqdn, self._logger, connect=False)
        try:
            self._proxy.connect()
        except tango.DevFailed as dev_failed:
            self._proxy = None
            raise ConnectionError(
                f"Could not connect to '{self._fqdn}'"
            ) from dev_failed

        self.update_communication_status(CommunicationStatus.ESTABLISHED)
        self._proxy.add_change_event_callback("state", self._device_state_changed)

        if self._health_changed_callback is not None:
            self._proxy.add_change_event_callback(
                "healthState", self._device_health_state_changed
            )
            self._proxy.add_change_event_callback(
                "adminMode", self._device_admin_mode_changed
            )

    def stop_communicating(self: DeviceComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        # TODO: Presumably, unsubscriptions occur before the underlying
        # tango.DeviceProxy is deleted. But we should really do this
        # explicitly.
        self._proxy = None

    @check_communicating
    def off(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerMode.OFF:
            return None  # already off
        return self._off()

    def _off(self: DeviceComponentManager) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.Off()
        return result_code

    @check_communicating
    def standby(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerMode.STANDBY:
            return None  # already standby
        return self._standby()

    def _standby(self: DeviceComponentManager) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.Standby()
        return result_code

    @check_communicating
    def on(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device on.

        :return: a result code, or None if there was nothing to do.
        """
        if self.power_mode == PowerMode.ON:
            return None  # already on
        return self._on()

    def _on(self: DeviceComponentManager) -> ResultCode:
        try:
            assert self._proxy is not None  # for the type checker
            ([result_code], _) = self._proxy.On()
        except TypeError as type_error:
            raise TypeError(f"FQDN is {self._fqdn}") from type_error
        return result_code

    @check_communicating
    def reset(self: DeviceComponentManager) -> ResultCode | None:
        """
        Turn the device off.

        :return: a result code, or None if there was nothing to do.
        """
        if self._faulty:
            return None  # no point resetting a device that isn't faulty.
        return self._reset()

    def _reset(self: DeviceComponentManager) -> ResultCode:
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

        if event_value == tango.DevState.OFF:
            self.update_component_power_mode(PowerMode.OFF)
        elif event_value == tango.DevState.STANDBY:
            self.update_component_power_mode(PowerMode.STANDBY)
        elif event_value == tango.DevState.ON:
            self.update_component_power_mode(PowerMode.ON)
        else:  # INIT, DISABLE, UNKNOWN, FAULT
            self.update_component_power_mode(PowerMode.UNKNOWN)

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
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Optional[Callable[[PowerMode], None]],
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
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            health_changed_callback,
        )

    def _connect_to_device(self: ObsDeviceComponentManager) -> None:
        """
        Establish communication with the component, then start monitoring.

        This contains the actual communication logic that is enqueued to
        be run asynchronously.
        """
        super()._connect_to_device()
        assert self._proxy is not None  # for the type checker
        self._proxy.add_change_event_callback("obsState", self._obs_state_changed)

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
