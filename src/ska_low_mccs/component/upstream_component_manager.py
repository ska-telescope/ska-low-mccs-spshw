"""This module contains classes for interacting with upstream devices."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    MccsComponentManager,
    MccsComponentManagerProtocol,
    ObjectComponent,
    ObjectComponentManager,
    check_communicating,
    enqueue,
)
from ska_low_mccs.utils import threadsafe


__all__ = ["PowerSupplyProxySimulator"]


class PowerSupplyProxyComponentManager(MccsComponentManager):
    def __init__(
        self: PowerSupplyProxyComponentManager,
        *args: Any,
        supplied_power_mode_changed_callback: Callable[[PowerMode], None],
        **kwargs: Any,
    ) -> None:
        self._supplied_power_mode: Optional[PowerMode] = None
        self._supplied_power_mode_changed_callback = (
            supplied_power_mode_changed_callback
        )
        super().__init__(*args, **kwargs)

    def stop_communicating(self: PowerSupplyProxyComponentManager) -> None:
        """Break off communication with the component."""
        super().stop_communicating()
        self._supplied_power_mode = None

    @property
    def supplied_power_mode(
        self: PowerSupplyProxyComponentManager,
    ) -> Optional[PowerMode]:
        """
        Return the power mode of the APIU.

        :return: the power mode of the APIU.
        """
        return self._supplied_power_mode

    def power_off(self: PowerSupplyProxyComponentManager) -> ResultCode | None:
        raise NotImplementedError("PowerSupplyComponentManager is abstract")

    def power_on(self: PowerSupplyProxyComponentManager) -> ResultCode | None:
        raise NotImplementedError("PowerSupplyComponentManager is abstract")

    def update_supplied_power_mode(
        self: PowerSupplyProxyComponentManager,
        supplied_power_mode: Optional[PowerMode],
    ) -> None:
        if self._supplied_power_mode != supplied_power_mode:
            self._supplied_power_mode = supplied_power_mode
            if self._supplied_power_mode is not None:
                self._supplied_power_mode_changed_callback(self._supplied_power_mode)


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
            initial_supplied_power_mode: PowerMode,
        ) -> None:
            """
            Initialise a new instance.

            :param initial_supplied_power_mode: initial supplied power mode of this
                power supply proxy simulator
            """
            self._supplied_power_mode = initial_supplied_power_mode
            self._supplied_power_mode_changed_callback: Optional[
                Callable[[PowerMode], None]
            ] = None

        def set_supplied_power_mode_changed_callback(
            self: PowerSupplyProxySimulator._Component,
            supplied_power_mode_changed_callback: Optional[Callable[[PowerMode], None]],
        ) -> None:
            """
            Set the supplied power mode changed callback.

            :param supplied_power_mode_changed_callback: the callback to be
                called when the power mode changes.
            """
            self._supplied_power_mode_changed_callback = (
                supplied_power_mode_changed_callback
            )
            if supplied_power_mode_changed_callback is not None:
                supplied_power_mode_changed_callback(self._supplied_power_mode)

        def power_off(
            self: PowerSupplyProxySimulator._Component,
        ) -> ResultCode | None:
            """
            Deny power to the downstream device.

            :return: a result code, or None if there was nothing to do.
            """
            if self._supplied_power_mode == PowerMode.OFF:
                return None

            self._update_supplied_power_mode(PowerMode.OFF)
            return ResultCode.OK

        def power_on(self: PowerSupplyProxySimulator._Component) -> ResultCode | None:
            """
            Supply power to the downstream device.

            :return: a result code, or None if there was nothing to do.
            """
            if self._supplied_power_mode == PowerMode.ON:
                return None

            self._update_supplied_power_mode(PowerMode.ON)
            return ResultCode.OK

        def _update_supplied_power_mode(
            self: PowerSupplyProxySimulator._Component, supplied_power_mode: PowerMode
        ) -> None:
            """
            Update the supplied power mode, ensuring callbacks are called.

            :param supplied_power_mode: the new supplied power mode of
                the downstream device.
            """
            if self._supplied_power_mode != supplied_power_mode:
                self._supplied_power_mode = supplied_power_mode
                if self._supplied_power_mode_changed_callback is not None:
                    self._supplied_power_mode_changed_callback(supplied_power_mode)

    def __init__(
        self: PowerSupplyProxySimulator,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        supplied_power_mode_changed_callback: Callable[[PowerMode], None],
        initial_supplied_power_mode: PowerMode = PowerMode.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param supplied_power_mode_changed_callback: callback to be
            called when the supplied power mode changes
        :param initial_supplied_power_mode: the initial supplied power
            mode of the simulated component
        """
        super().__init__(
            self._Component(initial_supplied_power_mode),
            logger,
            communication_status_changed_callback,
            None,
            None,
            supplied_power_mode_changed_callback=supplied_power_mode_changed_callback,
        )

    def start_communicating(self: PowerSupplyProxySimulator) -> None:
        """Establish communication with the component, then start monitoring."""
        super().start_communicating()
        cast(
            PowerSupplyProxySimulator._Component, self._component
        ).set_supplied_power_mode_changed_callback(self._supplied_power_mode_changed)

    def stop_communicating(self: PowerSupplyProxySimulator) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        cast(
            PowerSupplyProxySimulator._Component, self._component
        ).set_supplied_power_mode_changed_callback(None)
        self.update_supplied_power_mode(None)

    @check_communicating
    @enqueue
    def power_off(self: PowerSupplyProxySimulator) -> ResultCode | None:
        """
        Turn off supply of power to the downstream device.

        :return: a resultcode, or None if there was nothing to do.
        """
        return cast(PowerSupplyProxySimulator._Component, self._component).power_off()

    @check_communicating
    @enqueue
    def power_on(self: PowerSupplyProxySimulator) -> ResultCode | None:
        """
        Turn on supply of power to the downstream device.

        :return: a resultcode, or None if there was nothing to do.
        """
        return cast(PowerSupplyProxySimulator._Component, self._component).power_on()

    def _supplied_power_mode_changed(
        self: PowerSupplyProxySimulator,
        supplied_power_mode: PowerMode,
    ) -> None:
        self.update_supplied_power_mode(supplied_power_mode)


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
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Optional[Callable[[PowerMode], None]],
        component_fault_callback: Optional[Callable[[bool], None]],
    ) -> None:
        """
        Initialise a new instance.

        :param hardware_component_manager: the component manager that
            manages the hardware (when it is turned on).
        :param power_supply_component_manager: the component
            manager that manages supply of power to the hardware.
        :param logger: a logger for this object to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        self.__power_mode_lock = threading.Lock()
        self._target_power_mode: Optional[PowerMode] = None

        self._power_supply_communication_status = CommunicationStatus.DISABLED
        self._hardware_communication_status = CommunicationStatus.DISABLED

        self._power_supply_component_manager = power_supply_component_manager
        self._hardware_component_manager = hardware_component_manager

        super().__init__(
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
        )

    def start_communicating(self: ComponentManagerWithUpstreamPowerSupply) -> None:
        """Establish communication with the hardware and the upstream power supply."""
        super().start_communicating()

        if (
            self._power_supply_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        ):
            self._hardware_component_manager.start_communicating()
        else:
            self._power_supply_component_manager.start_communicating()

    def stop_communicating(self: ComponentManagerWithUpstreamPowerSupply) -> None:
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

    def component_power_mode_changed(
        self: ComponentManagerWithUpstreamPowerSupply,
        power_mode: PowerMode,
    ) -> None:
        """
        Handle a change in power mode of the hardware.

        :param power_mode: the power mode of the hardware
        """
        if power_mode == PowerMode.OFF:
            self._hardware_component_manager.stop_communicating()
        elif power_mode == PowerMode.ON:
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
        super().component_power_mode_changed(power_mode)
        self._review_power()

    @check_communicating
    def off(self: ComponentManagerWithUpstreamPowerSupply) -> ResultCode | None:
        """
        Tell the upstream power supply proxy to turn the hardware off.

        :return: a result code, or None if there was nothing to do.
        """
        self._target_power_mode = PowerMode.OFF
        return self._review_power()

    @check_communicating
    def on(self: ComponentManagerWithUpstreamPowerSupply) -> ResultCode | None:
        """
        Tell the upstream power supply proxy to turn the hardware off.

        :return: a result code, or None if there was nothing to do.
        """
        self._target_power_mode = PowerMode.ON
        return self._review_power()

    @threadsafe
    def _review_power(
        self: ComponentManagerWithUpstreamPowerSupply,
    ) -> ResultCode | None:
        with self.__power_mode_lock:
            if self._target_power_mode is None:
                return None
            if self.power_mode == self._target_power_mode:
                self._target_power_mode = None  # attained without any action needed
                return None
            if (
                self.power_mode == PowerMode.OFF
                and self._target_power_mode == PowerMode.ON
            ):
                result_code = self._power_supply_component_manager.power_on()
                self._target_power_mode = None
                return result_code
            if (
                self.power_mode == PowerMode.ON
                and self._target_power_mode == PowerMode.OFF
            ):
                result_code = self._power_supply_component_manager.power_off()
                self._target_power_mode = None
                return result_code
            return ResultCode.QUEUED
