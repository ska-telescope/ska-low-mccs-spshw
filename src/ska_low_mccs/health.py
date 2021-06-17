# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements infrastructure for health management in the MCCS subsystem."""

from __future__ import annotations  # allow forward references in type hints

__all__ = [
    "DeviceHealthPolicy",
    "DeviceHealthRollupPolicy",
    "DeviceHealthMonitor",
    "HealthMonitor",
    "HealthModel",
    "MutableHealthMonitor",
    "MutableHealthModel",
]

from collections import Counter
from functools import partial
import logging
from typing import Callable, Iterable, Optional, Type, Union

from tango import AttrQuality

from ska_tango_base.control_model import AdminMode, HealthState

from ska_low_mccs.device_proxy import MccsDeviceProxy
from ska_low_mccs.hardware import HardwareManager  # type: ignore[attr-defined]


class DeviceHealthPolicy:
    """
    This class implements a policy for evaluating the health of a device.

    It is used by supervising devices to evaluate the health of a
    subservient device, on the basis of its self-reported health state
    and on its admin mode (a device's admin mode determines whether its
    health should be taken into account or ignored).
    """

    @classmethod
    def compute_health(
        cls: Type[DeviceHealthPolicy], admin_mode: AdminMode, health_state: HealthState
    ) -> Optional[HealthState]:
        """
        Computes the health of the device, based on the device's admin mode and self-
        reported health state.

        :param admin_mode: the value of the adminMode attribute of the
            device
        :param health_state: the value of the healthState attribute of
            the device
        :return: the evaluated health of the device or None
            if the health should be ignored.
        """
        if admin_mode is None:
            return HealthState.UNKNOWN
        elif admin_mode in (
            AdminMode.NOT_FITTED,
            AdminMode.RESERVED,
            AdminMode.OFFLINE,
        ):
            return None
        elif health_state is None:
            return HealthState.UNKNOWN
        else:
            return health_state


class DeviceHealthRollupPolicy:
    """
    The DeviceHealthRollupPolicy class implements a policy by which a device should
    determine its own health, on the basis of the health of its hardware (if any) and of
    the devices that it supervises (if any).

    This is a very simple but flexible policy:

    * If all devices are OK, it reports OK
    * If any devices have UNKNOWN health, it reports UNKNOWN.
    * Otherwise it computes the weighted sum of degraded and failed
      devices, and reports FAILED if the sum is greater than one, else
      DEGRADED.
    """

    def __init__(
        self: DeviceHealthRollupPolicy,
        degraded_weight: float = 1.0,
        failed_weight: float = 1.0,
    ) -> None:
        """
        Create a new instances.

        :param degraded_weight: the weight to give to devices with
            DEGRADED health, defaults to 1.0
        :param failed_weight: the weight to give to devices with FAILED
            health, defaults to 1.0
        """
        self._degraded_weight = degraded_weight
        self._failed_weight = failed_weight

    def _compute_device_health(
        self: DeviceHealthRollupPolicy,
        device_healths: Optional[list[HealthState]] = None,
    ) -> HealthState:
        """
        Helper method to roll up device healths into a single device health.

        :param device_healths: sequence of healths of subservient
            devices

        :return: a rolled up health state
        """
        if device_healths is None:
            return HealthState.OK
        device_healths = [health for health in device_healths if health is not None]
        if device_healths == []:
            return HealthState.OK
        if HealthState.UNKNOWN in device_healths:
            return HealthState.UNKNOWN

        counter = Counter(device_healths)
        score = (
            self._failed_weight * counter[HealthState.FAILED]
            + self._degraded_weight * counter[HealthState.DEGRADED]
        )
        if score > 1.0:
            return HealthState.FAILED
        if score > 0.0:
            return HealthState.DEGRADED
        return HealthState.OK

    def compute_health(
        self: DeviceHealthRollupPolicy,
        hardware_health: Optional[HealthState],
        device_healths: Optional[list[HealthState]] = None,
    ) -> HealthState:
        """
        Compute this devices health, given the health of its hardware and the health of
        the devices that it supervises.

        This currently has a very simple implementation: the device
        takes as its health the "maximum" health of its hardware and
        supervised devices, where UNKNOWN > FAILED > DEGRADED > OK.

        :param hardware_health: the health of the hardware, if any
            (optional)
        :param device_healths: the healths of supervised devices: a
            list, where each value is either a
            :py:class:`~ska_tango_base.control_model.HealthState`, or None if
            the device's health should be ignored.

        :return: the health of this device
        """
        rolled_up_device_health = self._compute_device_health(device_healths)

        if hardware_health is None:
            hardware_health = HealthState.OK

        # return worst health, where FAILED > UNKNOWN > DEGRADED > OK
        if hardware_health == HealthState.FAILED:
            return HealthState.FAILED
        if rolled_up_device_health == HealthState.FAILED:
            return HealthState.FAILED
        return max(hardware_health, rolled_up_device_health)


class DeviceHealthMonitor:
    """Class that monitors the health of a single device."""

    def __init__(
        self: DeviceHealthMonitor,
        fqdn: str,
        logger: logging.Logger,
        initial_callback: Optional[Callable[[HealthState], None]] = None,
    ) -> None:
        """
        Initialise a new DeviceHealthMonitor instance.

        :param fqdn: the name of the device for which health is to be
            monitored
        :param logger: a logger for the MutableHealthMonitor instance
        :param initial_callback: an optional function handle to be
            called if device health changes, defaults to None
        """
        self._fqdn = fqdn

        self._device_admin_mode = None
        self._device_health_state = None
        self._interpreted_health = None
        self._callbacks: list[Callable[[HealthState], None]] = []

        self._compute_health()

        if initial_callback is not None:
            self.register_callback(initial_callback)

        self._proxy = MccsDeviceProxy(fqdn, logger)
        self._proxy.add_change_event_callback("healthState", self._health_state_changed)
        self._proxy.add_change_event_callback("adminMode", self._admin_mode_changed)

    def register_callback(
        self: DeviceHealthMonitor, callback: Callable[[HealthState], None]
    ) -> None:
        """
        Register a callback to be called when device health changes.

        :param callback: callback to be called when device health changes
        """
        self._callbacks.append(callback)
        callback(self._interpreted_health)

    def _health_state_changed(
        self: DeviceHealthMonitor,
        event_name: str,
        event_value: HealthState,
        event_quality: AttrQuality,
    ) -> None:
        """
        Callback that this device registers with the event manager, so that it is
        informed when the device's healthState attribute changes.

        :param event_name: name of the event; will always be
            "healthState" for this callback
        :param event_value: the new healthState value
        :param event_quality: the quality of the change event
        """
        assert (
            event_name.lower() == "healthstate"
        ), f"healthState changed callback called but event_name is {event_name}"
        self._device_health_state = event_value
        self._compute_health()

    def _admin_mode_changed(
        self: DeviceHealthMonitor,
        event_name: str,
        event_value: AdminMode,
        event_quality: AttrQuality,
    ) -> None:
        """
        Callback that this device registers with the event manager, so that it is
        informed when the device's adminMode attribute changes.

        :param event_name: name of the event; will always be "adminMode"
            for this callback
        :param event_value: the new adminMode value
        :param event_quality: the quality of the change event

        :raises AssertionError: if the event name is not
            "adminMode"
        """
        assert event_name.lower() == "adminmode"
        self._device_admin_mode = event_value
        self._compute_health()

    def _compute_health(self: DeviceHealthMonitor) -> None:
        """Re-evaluate the health of this device using DeviceHealthPolicy."""
        interpreted_health = DeviceHealthPolicy.compute_health(
            self._device_admin_mode, self._device_health_state
        )
        self._update_health(interpreted_health)

    def _update_health(
        self: DeviceHealthMonitor, interpreted_health: HealthState
    ) -> None:
        """
        Update this instances health value, ensuring that any registered callbacks are
        called.

        :param interpreted_health: the interpreted health of the device,
            or None if the device's health should be ignored
        """
        if self._interpreted_health == interpreted_health:
            return
        self._interpreted_health = interpreted_health
        for callback in self._callbacks:
            callback(interpreted_health)


class HealthMonitor:
    """Monitors the health of a collection of subservient devices."""

    def __init__(
        self: HealthMonitor,
        fqdns: list[str],
        logger: logging.Logger,
        initial_callback: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        """
        Initialise a new HealthMonitor instance.

        :param fqdns: fqdns of the devices for which health is to be
            monitored
        :param logger: a logger for this HealthMonitor instance
        :param initial_callback: A function handle, to be called if the
            health of any device changes
        """
        self._device_health_monitors = {
            fqdn: DeviceHealthMonitor(fqdn, logger) for fqdn in fqdns
        }
        if initial_callback is not None:
            self.register_callback(initial_callback)

    def register_callback(
        self: HealthMonitor,
        callback: Callable[[str, int], None],
        fqdn_spec: Optional[Union[list[str], str]] = None,
    ) -> None:
        """
        Register a callback on change to health from one or more fqdns.

        :param callback: a function handle of the form
            ``callback(fqdn, name, value, quality)``, to be called
            whenever the event is received
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.

        :raises ValueError: if an unknown FQDN is passed
        """
        if fqdn_spec is None:
            fqdns = list(self._device_health_monitors.keys())
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
    """Represents and manages the health of a device."""

    def __init__(
        self: HealthModel,
        hardware_manager: HardwareManager,
        fqdns: Optional[list[str]],
        logger: logging.Logger,
        initial_callback: Optional[Callable[[HealthState], None]] = None,
    ):
        """
        Initialise a new HealthModel instance.

        :param hardware_manager: the hardware managed by this device, or
            None if the device doesn't manage any hardware
        :param fqdns: fqdns of supervised devices (optional)
        :param logger: a logger for this HealthModel instance
        :param initial_callback: A function handle to be called if the
            health of this device changes
        """
        self._logger = logger

        self._device_health_rollup_policy = DeviceHealthRollupPolicy()
        self._health = HealthState.UNKNOWN

        self._callbacks: list[Callable[[HealthState], None]] = []
        if initial_callback is not None:
            self.register_callback(initial_callback)

        self._hardware_manager = hardware_manager
        self._hardware_health = HealthState.UNKNOWN if hardware_manager else None

        if fqdns is None:
            self._device_health = None
            self._health_monitor = None
        else:
            self._device_health = {fqdn: HealthState.UNKNOWN for fqdn in fqdns}
            self._health_monitor = self._init_health_monitor(fqdns)

        if self._hardware_manager is not None:
            self._hardware_manager.register_health_callback(
                self._hardware_health_changed
            )
        if self._health_monitor is not None:
            self._health_monitor.register_callback(self._device_health_changed)

        # For devices that start with neither hardware nor subservient
        # devices, such as an empty subarray, this next is essential to
        # ensure that health gets computed once.
        self._compute_health()

    def _init_health_monitor(self: HealthModel, fqdns: list[str]) -> HealthMonitor:
        """
        Initialise a new HealthMonitor.

        :param fqdns: FQDNs of devices to be monitored

        :return: a health monitor instance
        """
        return HealthMonitor(fqdns, self._logger)

    @property
    def health(self: HealthModel) -> HealthState:
        """
        Returns the health of this HealthModel.

        :return: the health state of this HealthModel
        """
        return self._health

    def register_callback(
        self: HealthModel, callback: Callable[[HealthState], None]
    ) -> None:
        """
        Register a callback for change of this device's health.

        :param callback: a function handle to be called when this
            device's health changes
        """
        self._callbacks.append(callback)
        callback(self._health)

    def _hardware_health_changed(self: HealthModel, health: HealthState) -> None:
        """
        Passed to the hardware manager as a callback to be called when the hardware
        health changes.

        :param health: the health of the hardware
        """
        self._hardware_health = health
        self._compute_health()

    def _device_health_changed(
        self: HealthModel, fqdn: str, health: HealthState
    ) -> None:
        """
        Passed to the HealthMonitor as a callback to be called when a device's health
        changes.

        :param fqdn: FQDN of the device whose health has changed
        :param health: The device's new healthState attribute value, or
            None if the device's health is to be ignored
        """
        if self._device_health is not None:
            self._device_health[fqdn] = health
            self._compute_health()

    def _compute_health(self: HealthModel) -> None:
        """
        Re-evaluate health of this device, by applying the
        :py:class:`.DeviceHealthRollupPolicy` to the current health of
        the hardware (if any) and subservient devices (if any)
        """
        try:
            health = self._device_health_rollup_policy.compute_health(
                self._hardware_health,
                None
                if self._device_health is None
                else list(self._device_health.values()),
            )
            self._update_health(health)
        except AttributeError:
            # callbacks may trigger a call to this before init_device has
            # even created the health attributes
            pass

    def _update_health(self: HealthModel, health: HealthState) -> None:
        """
        Update the health of this device, ensuring that any registered callbacks are
        called.

        :param health: the new healthState of this device
        """
        if self._health == health:
            return
        self._health = health

        for callback in self._callbacks:
            callback(health)


class MutableHealthMonitor(HealthMonitor):
    """A HealthMonitor for which monitored devices can be added and removed."""

    def __init__(
        self: MutableHealthMonitor,
        fqdns: list[str],
        logger: logging.Logger,
        initial_callback: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        """
        Initialise a new MutableHealthMonitor instance.

        :param fqdns: fqdns of the devices for which health is to be
            monitored
        :param logger: a logger for this MutableHealthMonitor instance
        :param initial_callback: An optional function handle to be
            called if the health of any device changes
        """
        self._logger = logger

        # remember callbacks that are registered against all fqdns in the device pool,
        # so that we can register them against fqdns that are added to the pool later
        self._pool_callbacks: list[Callable[[str, int], None]] = list()

        super().__init__(fqdns, logger, initial_callback)

    def register_callback(
        self: MutableHealthMonitor,
        callback: Callable[[str, int], None],
        fqdn_spec: Optional[Union[list[str], str]] = None,
    ) -> None:
        """
        Register a callback on change to health from one or more fqdns.

        :param callback: function handle of the form
            ``callback(fqdn, name, value, quality)``, to be called
            whenever the event is received
        :param fqdn_spec: specification of the devices upon which the
            callback is registered. This specification may be the FQDN
            of a device, or a list of such FQDNs, or None, in which case
            the FQDNs provided at initialisation are used.
        """
        if fqdn_spec is None:
            self._pool_callbacks.append(callback)
        super().register_callback(callback, fqdn_spec)

    def add_devices(self: MutableHealthMonitor, fqdns: Iterable[str]) -> None:
        """
        Add to the list of devices to be monitored.

        :param fqdns: fqdns of devices to be added
        """
        for fqdn in fqdns:
            if fqdn not in self._device_health_monitors:
                self._device_health_monitors[fqdn] = DeviceHealthMonitor(
                    fqdn, self._logger
                )
                for callback in self._pool_callbacks:
                    self.register_callback(callback, fqdn)

    def remove_devices(self: MutableHealthMonitor, fqdns: list[str]) -> None:
        """
        Remove items from the list of devices to be monitored.

        :param fqdns: fqdns of devices to be added
        """
        for fqdn in fqdns:
            del self._device_health_monitors[fqdn]

    def remove_all_devices(self: MutableHealthMonitor) -> None:
        """Remove all items from the list of devices to be monitored."""
        fqdns = list(self._device_health_monitors.keys())
        self.remove_devices(fqdns)


class MutableHealthModel(HealthModel):
    """A HealthModel for which devices can be dynamically added and removed."""

    def __init__(
        self: MutableHealthModel,
        hardware_manager: Optional[HardwareManager],
        fqdns: Optional[list[str]],
        logger: logging.Logger,
        initial_callback: Optional[Callable[[HealthState], None]] = None,
    ) -> None:
        """
        Initialise a new MutableHealthModel instance.

        :param hardware_manager: the hardware managed by this device
            (optional)
        :param fqdns: fqdns of supervised devices (optional)
        :param logger: a logger for this MutableHealthModel instance
        :param initial_callback: An option function handle, to be called
            if the health of this device changes (optional)
        """
        super().__init__(hardware_manager, fqdns, logger, initial_callback)
        self._health_monitor: MutableHealthMonitor  # type hint only

    def _init_health_monitor(
        self: MutableHealthModel, fqdns: list[str]
    ) -> HealthMonitor:
        """
        Initialise a new HealthMonitor.

        :param fqdns: FQDNs of devices to be monitored

        :return: a health monitor instance
        """
        return MutableHealthMonitor(fqdns, self._logger)

    def add_devices(self: MutableHealthModel, fqdns: list[str]) -> None:
        """
        Add to the list of devices to be monitored.

        :param fqdns: fqdns of devices to be added
        """
        if self._health_monitor is None:
            self._health_monitor = self._init_health_monitor(fqdns)
        else:
            self._health_monitor.add_devices(fqdns)

    def remove_devices(self: MutableHealthModel, fqdns: list[str]) -> None:
        """
        Remove items from the list of devices to be monitored.

        :param fqdns: fqdns of devices to be added
        """
        self._health_monitor.remove_devices(fqdns)
