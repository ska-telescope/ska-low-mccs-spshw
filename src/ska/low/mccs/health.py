# -*- coding: utf-8 -*-
#
# This file is part of the ska.low.mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for health management in the MCCS
subsystem.

"""
__all__ = [
    "DeviceHealthPolicy",
    "DeviceHealthRollupPolicy",
    "DeviceHealthMonitor",
    "HealthMonitor",
    "HealthModel",
]

from functools import partial

from ska.base.control_model import AdminMode, HealthState


class DeviceHealthPolicy:
    """
    The DeviceHealthPolicy class implements a policy by which a
    supervising device evaluates the health of a subservient device, on
    the basis of its self-reported health state and on its admin mode
    (a device's admin mode determines whether its health should be taken
    into account or ignored).
    """

    @classmethod
    def compute_health(cls, admin_mode, health_state):
        """
        Computes the health of the device, based on the device's admin mode
        and self-reported health state.

        :param admin_mode: the value of the adminMode attribute of the device
        :type admin_mode: :py:class:`ska.base.control_model.AdminMode`
        :param health_state: the value of the healthState attribute of
            the device
        :type health_state: :py:class:`ska.base.control_model.HealthState`
        :return: the evaluated health of the device
        :rtype: :py:class:`ska.base.control_model.HealthState`, or None
            if the health should be ignored.
        """
        if admin_mode is None:
            return HealthState.UNKNOWN
        elif admin_mode in (
            AdminMode.NOT_FITTED,
            AdminMode.RESERVED,
            AdminMode.OFFLINE,
        ):
            return
        elif health_state is None:
            return HealthState.UNKNOWN
        else:
            return health_state


class DeviceHealthRollupPolicy:
    """
    The DeviceHealthRollupPolicy class implements a policy by which a
    device should determine its own health, on the basis of the health
    of its hardware (if any) and of the devices that it supervises (if
    any).
    """

    @classmethod
    def compute_health(cls, hardware_health, device_healths):
        """
        Compute this devices health, given the health of its hardware
        and the health of the devices that it supervises.

        This currently has a very simple implementation: the device
        takes as its health the "maximum" health of its hardware and
        supervised devices, where UNKNOWN > FAILED > DEGRADED > OK.

        :param hardware_health: the health of the hardware, if any
        :type hardware_health: :py:class:`ska.base.control_model.HealthState`
            (or None if no hardware)
        :param device_healths: the healths of supervised devices
        :type device_healths: list of device health values, or None if
            the device does not supervise devices. If a list if provided,
            each value must be either a
            :py:class:`ska.base.control_model.HealthState`, or None if
            the device's health should be ignored.
        :return: the health of this device
        :rtype: :py:class:`ska.base.control_model.HealthState`
        """
        if device_healths is None:
            rolled_up_device_health = HealthState.OK
        else:
            device_healths = [
                device_health
                for device_health in device_healths
                if device_health is not None
            ]
            if device_healths:
                rolled_up_device_health = max(device_healths)
            else:
                rolled_up_device_health = HealthState.OK

        if hardware_health is None:
            hardware_health = HealthState.OK

        return max(hardware_health, rolled_up_device_health)


class DeviceHealthMonitor:
    """
    Class that monitors the health of a single device.
    """

    def __init__(self, event_manager, fqdn, initial_callback=None):
        """
        Initialise a new DeviceHealthMonitor instance

        :param event_manager: the event_manager to be used for device
            health event subscriptions
        :type event_manager: :py:class:`ska.low.mccs.events.EventManager`
        :param fqdn: the name of the device for which health is to be
            monitored
        :type fqdn: str
        :param initial_callback: an optional callback to be called if
            device health changes, defaults to None
        :type initial_callback: callable, optional
        """
        self._device_admin_mode = None
        self._device_health_state = None
        self._interpreted_health = None

        self._callbacks = []

        event_manager.register_callback(
            self._health_state_changed, fqdn_spec=fqdn, event_spec="healthState"
        )
        event_manager.register_callback(
            self._admin_mode_changed, fqdn_spec=fqdn, event_spec="adminMode"
        )

        if initial_callback is not None:
            self.register_callback(initial_callback)

    def register_callback(self, callback):
        """
        Register a callback to be called when device health changes

        :param callback: callback to be called when device health changes
        :type callback: callback
        """
        self._callbacks.append(callback)

    def _health_state_changed(self, fqdn, event_name, event_value, event_quality):
        """
        Callback that this device registers with the event manager, so
        that it is informed when the device's healthState attribute
        changes

        :param fqdn: the fqdn for which healthState has changed
        :type fqdn: str
        :param event_name: name of the event; will always be
            "healthState" for this callback
        :type event_name: str; will always be "healthState" for this
            callback
        :param event_value: the new healthState value
        :type event_value: :py:class:`ska.base.control_model.HealthState`
        :param event_quality: the quality of the change event
        :type event_quality: :py:class:`tango.AttrQuality`
        """
        assert event_name == "healthState"
        self._device_health_state = event_value
        self._compute_health()

    def _admin_mode_changed(self, fqdn, event_name, event_value, event_quality):
        """
        Callback that this device registers with the event manager, so
        that it is informed when the device's adminMode attribute
        changes

        :param fqdn: the fqdn for which adminMode has changed
        :type fqdn: str
        :param event_name: name of the event; will always be "adminMode"
            for this callback
        :type event_name: str; will always be "adminMode" for this
            callback
        :param event_value: the new adminMode value
        :type event_value: :py:class:`ska.base.control_model.AdminMode`
        :param event_quality: the quality of the change event
        :type event_quality: :py:class:`tango.AttrQuality`

        :raises AssertionError: if the event name is not
            "adminMode"
        """
        assert event_name == "adminMode"
        self._device_admin_mode = event_value
        self._compute_health()

    def _compute_health(self):
        """
        Re-evaluate the health of this device, on the basis of a
        DeviceHealthPolicy
        """
        interpreted_health = DeviceHealthPolicy.compute_health(
            self._device_admin_mode, self._device_health_state
        )
        self._update_health(interpreted_health)

    def _update_health(self, interpreted_health):
        """
        Update this instances health value, ensuring that any registered
        callbacks are called

        :param interpreted_health: the interpreted health of the device
        :type interpreted_health: :py:class:`ska.base.control_model.HealthState`,
            or None if the device's health should be ignored
        """
        if self._interpreted_health == interpreted_health:
            return
        self._interpreted_health = interpreted_health
        for callback in self._callbacks:
            callback(interpreted_health)


class HealthMonitor:
    """
    Monitors the health of a collection of subservient devices.
    """

    def __init__(self, fqdns, event_manager, initial_callback=None):
        """
        Initialise a new HealthMonitor instance

        :param fqdns: fqdns of the devices for which health is to be
            monitored
        :type fqdns: list of str
        :param event_manager: the event_manager to be used to capture
            health events.
        :type event_manager: :py:class:`ska.low.mccs.events.EventManager`
        :param initial_callback: An initial callback, to be called if the
            health of any device changes
        :type initial_callback: callable, optional
        """
        self._device_health_monitors = {
            fqdn: DeviceHealthMonitor(event_manager, fqdn) for fqdn in fqdns
        }
        if initial_callback is not None:
            self.register_callback(initial_callback)

    def register_callback(self, callback, fqdn_spec=None):
        """
        Register a callback on change to health from one or more fqdns

        :param callback: callable to be called with args (fqdn, name,
            value, quality) whenever the event is received
        :type callback: callable
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.
        :type fqdn_spec: str, or list of str, or None

        :raises ValueError: if an unknown FQDN is passes
        """
        if fqdn_spec is None:
            fqdns = self._device_health_monitors.keys()
        elif isinstance(fqdn_spec, str):
            fqdns = [fqdn_spec]
        else:
            fqdns = fqdn_spec

        for fqdn in fqdns:
            if fqdn not in self._device_health_monitors:
                raise ValueError(f"Unknown FQDN {fqdn}.")

        for fqdn in fqdns:
            self._device_health_monitors[fqdn].register_callback(
                partial(callback, fqdn)
            )


class HealthModel:
    """
    Represents and manages the health of a device
    """

    def __init__(self, hardware, fqdns, event_manager, initial_callback=None):
        """
        Initialise a new HealthModel instance

        :param hardware: the hardware managed by this device
        :type hardware: HardwareManager, or None if the device doesn't
            manage any hardware
        :param fqdns: fqdns of supervised devices
        :type fqdns: list of str, or None if the device doesn't manage
            any other devices
        :param event_manager: the event_manager to be used for keeping
            device health updated
        :type event_manager: :py:class:`ska.low.mccs.events.EventManager`
        :param initial_callback: An initial callback, to be called if the
            health of this device changes
        :type initial_callback: callable, optional
        """
        self.health = HealthState.UNKNOWN

        if hardware is None:
            self._hardware_health = None
        else:
            self._hardware_health = HealthState.UNKNOWN
            hardware.register_health_callback(self._hardware_health_changed)

        if fqdns is None:
            self._device_health = None
        else:
            self._device_health = {fqdn: HealthState.UNKNOWN for fqdn in fqdns}
            self._health_monitor = HealthMonitor(
                fqdns, event_manager, initial_callback=self._device_health_changed
            )

        self._callbacks = []
        if initial_callback is not None:
            self.register_callback(initial_callback)

    def register_callback(self, callback):
        """
        Register a callback for change of this device's health

        :param callback: callback to be called when this device's health
            changes
        :type callback: callable
        """
        self._callbacks.append(callback)

    def _hardware_health_changed(self, health):
        """
        Passed to the hardware manager as a callback to be called when
        the hardware health changes

        :param health: the health of the hardware
        :type health: :py:class:`ska.base.control_model.HealthState`
        """
        self._hardware_health = health
        self._compute_health()

    def _device_health_changed(self, fqdn, health):
        """
        Passed to the HealthMonitor as a callback to be called when a
        device's health changes

        :param fqdn: FQDN of the device whose health has changed
        :type fqdn: str
        :param health: The device's new healthState attribute value
        :type health: :py:class:`ska.base.control_model.HealthState`, or
            None if the device's health is to be ignored
        """
        self._device_health[fqdn] = health
        self._compute_health()

    def _compute_health(self):
        """
        Re-evaluate health of this device, by applying the
        :py:class:`DeviceHealthRollupPolicy` to the current health of
        the hardware (if any) and subservient devices (if any)
        """
        try:
            health = DeviceHealthRollupPolicy.compute_health(
                self._hardware_health,
                None if self._device_health is None else self._device_health.values(),
            )
            self._update_health(health)
        except AttributeError:
            # callbacks may trigger a call to this before init_device has
            # even created the health attributes
            pass

    def _update_health(self, health):
        """
        Update the health of this device, ensuring that any registered
        callbacks are called

        :param health: the new healthState of this device
        :type health: :py:class:`ska.base.control_model.HealthState`
        """
        if self.health == health:
            return
        self.health = health
        for callback in self._callbacks:
            callback(health)
