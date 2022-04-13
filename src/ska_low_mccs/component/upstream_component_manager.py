# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains classes for interacting with upstream devices."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.component import (
    MccsComponentManager,
    MccsComponentManagerProtocol,
    ObjectComponent,
    ObjectComponentManager,
    check_communicating,
)
from ska_low_mccs.utils import threadsafe

__all__ = ["PowerSupplyProxySimulator"]


class PowerSupplyProxyComponentManager(MccsComponentManager):
    def __init__(
        self: PowerSupplyProxyComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._supplied_power_state: Optional[PowerState] = None
        self._supplied_power_state_changed_callback = component_state_changed_callback
        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
            *args,
            **kwargs,
        )

    def stop_communicating(self: PowerSupplyProxyComponentManager) -> None:
        """Break off communication with the component."""
        super().stop_communicating()
        self._supplied_power_state = None

    @property
    def supplied_power_state(
        self: PowerSupplyProxyComponentManager,
    ) -> Optional[PowerState]:
        """
        Return the power mode of the APIU.

        :return: the power mode of the APIU.
        """
        return self._supplied_power_state

    def power_off(self: PowerSupplyProxyComponentManager) -> ResultCode | None:
        raise NotImplementedError("PowerSupplyComponentManager is abstract")

    def power_on(self: PowerSupplyProxyComponentManager) -> ResultCode | None:
        raise NotImplementedError("PowerSupplyComponentManager is abstract")

    def update_supplied_power_state(
        self: PowerSupplyProxyComponentManager,
        supplied_power_state: Optional[PowerState],
    ) -> None:
        if self._supplied_power_state != supplied_power_state:
            self._supplied_power_state = supplied_power_state
            if self._supplied_power_state is not None:
                self._supplied_power_state_changed_callback(
                    {"power_state": self._supplied_power_state}
                )


class PowerSupplyProxySimulator(
    PowerSupplyProxyComponentManager, ObjectComponentManager
):
    """
    A component manager that simulates a proxy to an upstream power supply device.

    MCCS manages numerous hardware devices that can't turn turn
    themselves off and on directly. Rather, in order for a tango device
    to turn its hardware off or on, it needs to contact the tango device
    for an upstream device that supplies power to the hardware, and tell
    that tango device to supply/deny power to the hardware.

    However this functionality is largely not implemented yet, so we
    need to "fake" it. Plus, even when it _is_ implemented, there will
    be a need to simulate this when in simulation mode. This class
    provides that simulation pattern.

    :todo: implement standby support when needed
    """

    class _Component(ObjectComponent):
        """A fake component for the component manager to manage."""

        def __init__(
            self: PowerSupplyProxySimulator._Component,
            initial_supplied_power_state: PowerState,
        ) -> None:
            """
            Initialise a new instance.

            :param initial_supplied_power_state: initial supplied power mode of this
                power supply proxy simulator
            """
            self._supplied_power_state = initial_supplied_power_state
            self._supplied_power_state_changed_callback: Optional[
                Callable[[dict[str, Any]], None]
            ] = None

        def set_supplied_power_state_changed_callback(
            self: PowerSupplyProxySimulator._Component,
            component_state_changed_callback: Optional[
                Callable[[dict[str, Any]], None]
            ] = None,
        ) -> None:
            """
            Set the supplied power mode changed callback.

            :param component_state_changed_callback: the callback to be
                called when the component state changes.
            """
            self._supplied_power_state_changed_callback = (
                component_state_changed_callback
            )
            if self._supplied_power_state_changed_callback is not None:
                self._supplied_power_state_changed_callback(
                    {"power_state": self._supplied_power_state}
                )

        def power_off(
            self: PowerSupplyProxySimulator._Component,
        ) -> ResultCode | None:
            """
            Deny power to the downstream device.

            :return: a result code, or None if there was nothing to do.
            """
            if self._supplied_power_state == PowerState.OFF:
                return None

            self._update_supplied_power_state(PowerState.OFF)
            return ResultCode.OK

        def power_on(
            self: PowerSupplyProxySimulator._Component,
        ) -> ResultCode | None:
            """
            Supply power to the downstream device.

            :return: a result code, or None if there was nothing to do.
            """
            if self._supplied_power_state == PowerState.ON:
                return None

            self._update_supplied_power_state(PowerState.ON)
            return ResultCode.OK

        def _update_supplied_power_state(
            self: PowerSupplyProxySimulator._Component,
            supplied_power_state: PowerState,
        ) -> None:
            """
            Update the supplied power mode, ensuring callbacks are called.

            :param supplied_power_state: the new supplied power mode of
                the downstream device.
            """
            if self._supplied_power_state != supplied_power_state:
                self._supplied_power_state = supplied_power_state
                if self._supplied_power_state_changed_callback is not None:
                    self._supplied_power_state_changed_callback(
                        {"power_state": supplied_power_state}
                    )

    def __init__(
        self: PowerSupplyProxySimulator,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Optional(
            Callable[[dict[str, Any]], None]
        ) = None,
        initial_supplied_power_state: PowerState = PowerState.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param max_workers: nos of worker threads for async commands
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the state of the component changes
        :param initial_supplied_power_state: the initial supplied power
            mode of the simulated component
        """
        super().__init__(
            self._Component(initial_supplied_power_state),
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(self: PowerSupplyProxySimulator) -> None:
        """Establish communication with the component, then start monitoring."""
        super().start_communicating()
        cast(
            PowerSupplyProxySimulator._Component, self._component
        ).set_supplied_power_state_changed_callback(self._supplied_power_state_changed)

    def stop_communicating(self: PowerSupplyProxySimulator) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        cast(
            PowerSupplyProxySimulator._Component, self._component
        ).set_supplied_power_state_changed_callback(None)
        self.update_supplied_power_state(None)

    @check_communicating
    def power_off(self: PowerSupplyProxySimulator) -> ResultCode | None:
        """
        Turn off supply of power to the downstream device.

        :return: a resultcode, or None if there was nothing to do.
        """
        return cast(PowerSupplyProxySimulator._Component, self._component).power_off()

    @check_communicating
    def power_on(self: PowerSupplyProxySimulator) -> ResultCode | None:
        """
        Turn on supply of power to the downstream device.

        :return: a resultcode, or None if there was nothing to do.
        """
        return cast(PowerSupplyProxySimulator._Component, self._component).power_on()

    def _supplied_power_state_changed(
        self: PowerSupplyProxySimulator,
        supplied_power_state: PowerState,
    ) -> None:
        self.update_supplied_power_state(supplied_power_state)


class ComponentManagerWithUpstreamPowerSupply(MccsComponentManager):
    """
    A component manager for managing a component and a separate upstream power supply.

    MCCS manages numerous hardware devices that can't turn turn
    themselves off and on directly. Rather, in order for a Tango device
    to turn its hardware off or on, it needs to contact the Tango device
    for an upstream device that supplies power to the hardware, and tell
    that tango device to supply/deny power to the hardware.

    This class implements a pattern for this common situation.
    """

    def __init__(
        self: ComponentManagerWithUpstreamPowerSupply,
        hardware_component_manager: MccsComponentManagerProtocol,
        power_supply_component_manager: PowerSupplyProxyComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Optional[Callable[[dict[str, Any]], None]],
    ) -> None:
        """
        Initialise a new instance.

        :param hardware_component_manager: the component manager that
            manages the hardware (when it is turned on).
        :param power_supply_component_manager: the component
            manager that manages supply of power to the hardware.
        :param logger: a logger for this object to use
        :param max_workers: nos of worker threads for async commands
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._target_power_state: Optional[PowerState] = None
        self._power_state_lock = threading.RLock()

        self._power_supply_communication_status = CommunicationStatus.DISABLED
        self._hardware_communication_status = CommunicationStatus.DISABLED

        self._power_supply_component_manager = power_supply_component_manager
        self._hardware_component_manager = hardware_component_manager

        super().__init__(
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )

    def start_communicating(
        self: ComponentManagerWithUpstreamPowerSupply,
    ) -> None:
        """Establish communication with the hardware and the upstream power supply."""
        super().start_communicating()

        if (
            self._power_supply_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        ):
            self._hardware_component_manager.start_communicating()
        else:
            self._power_supply_component_manager.start_communicating()

    def stop_communicating(
        self: ComponentManagerWithUpstreamPowerSupply,
    ) -> None:
        """Establish communication with the hardware and the upstream power supply."""
        super().stop_communicating()
        self._hardware_component_manager.stop_communicating()
        self._power_supply_component_manager.stop_communicating()

    def _power_supply_communication_status_changed(
        self: ComponentManagerWithUpstreamPowerSupply,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the APIU.

        :param communication_status: the status of communication with
            the antenna via the APIU.
        """
        self._power_supply_communication_status = communication_status
        self._evaluate_communication_status()

    def _hardware_communication_status_changed(
        self: ComponentManagerWithUpstreamPowerSupply,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the hardware.

        :param communication_status: the status of communication with
            the hardware.
        """
        self._hardware_communication_status = communication_status
        self._evaluate_communication_status()

    def _evaluate_communication_status(
        self: ComponentManagerWithUpstreamPowerSupply,
    ) -> None:
        if self._power_supply_communication_status == CommunicationStatus.ESTABLISHED:
            if self._hardware_communication_status == CommunicationStatus.DISABLED:
                self.update_communication_status(CommunicationStatus.ESTABLISHED)
            else:
                self.update_communication_status(self._hardware_communication_status)
        else:
            self.update_communication_status(self._power_supply_communication_status)

    def component_progress_changed(
        self: ComponentManagerWithUpstreamPowerSupply, progress: int
    ) -> None:
        """
        Handle notification that the component's progress value has changed.

        This is a callback hook, to be passed to the managed component.

        :param progress: The progress percentage of the long-running command
        """
        if self._component_state_changed_callback is not None:
            self._component_state_changed_callback({"progress": progress})

    def component_power_state_changed(
        self: ComponentManagerWithUpstreamPowerSupply,
        power_state: PowerState,
    ) -> None:
        """
        Handle a change in power state of the hardware.

        :param power_state: the power state of the hardware
        """
        if power_state == PowerState.OFF:
            self._hardware_component_manager.stop_communicating()
        elif power_state == PowerState.ON:
            # TODO: if the hardware component manager is synchronous, we get a state
            # wobble here.
            # Ideally we would go from OFF to ON. It is acceptable / inevitable that we
            # will go from OFF to UNKNOWN to ON.
            # But here, if the hardware component manager handles start_communicating()
            # synchronously and returns immediately, we go from OFF to UNKNOWN to OFF to
            # ON. Probably the solution is not to have synchronous hardware component
            # managers. Even when they are do-nothing placeholders, they should still
            # behave asynchronously.
            self._hardware_component_manager.start_communicating()
        super().component_state_changed_callback({"power_state": power_state})
        self._review_power()

    @check_communicating
    def off(
        self: ComponentManagerWithUpstreamPowerSupply, argin: Any = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the hardware off.

        :return: a task status and message.
        """
        with self._power_state_lock:
            self._target_power_state = PowerState.OFF
        rc = self._review_power()
        # TODO sort out rc
        return TaskStatus.COMPLETED, "Ignore return code for now"

    # @check_communicating
    def on(
        self: ComponentManagerWithUpstreamPowerSupply, argin: Any = None
    ) -> tuple[TaskStatus, str]:
        """
        Tell the upstream power supply proxy to turn the hardware off.

        :return: a task status and message.
        """
        with self._power_state_lock:
            self._target_power_state = PowerState.ON
        rc = self._review_power()
        # TODO sort out rc
        return TaskStatus.COMPLETED, "Ignore return code for now"

    @threadsafe
    def _review_power(
        self: ComponentManagerWithUpstreamPowerSupply,
    ) -> ResultCode | None:
        with self._power_state_lock:
            if self._target_power_state is None:
                return None
            if self.power_state == self._target_power_state:
                self._target_power_state = None  # attained without any action needed
                return None
            if (
                self.power_state == PowerState.OFF
                and self._target_power_state == PowerState.ON
            ):
                result_code = self._power_supply_component_manager.power_on()
                self._target_power_state = None
                return result_code
            if (
                self.power_state == PowerState.ON
                and self._target_power_state == PowerState.OFF
            ):
                result_code = self._power_supply_component_manager.power_off()
                self._target_power_state = None
                return result_code
            return ResultCode.QUEUED
