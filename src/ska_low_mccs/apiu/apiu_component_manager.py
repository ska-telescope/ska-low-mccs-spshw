# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for APIUs."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState, SimulationMode
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.apiu import ApiuSimulator
from ska_low_mccs.component import (
    ComponentManagerWithUpstreamPowerSupply,
    DriverSimulatorSwitchingComponentManager,
    ObjectComponentManager,
    PowerSupplyProxySimulator,
    check_communicating,
    check_on,
)

__all__ = ["ApiuSimulatorComponentManager", "ApiuComponentManager"]


class ApiuSimulatorComponentManager(ObjectComponentManager):
    """A component manager for an APIU simulator."""

    def __init__(
        self: ApiuSimulatorComponentManager,
        antenna_count: int,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param antenna_count: the number of antennas managed by this APIU
        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            ApiuSimulator(antenna_count, component_state_changed_callback),
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )
        self._component_state_changed_callback = component_state_changed_callback

    def start_communicating(self: ApiuSimulatorComponentManager) -> None:
        """Establish communication with the APIU simulator."""
        super().start_communicating()
        cast(ApiuSimulator, self._component).set_antenna_power_changed_callback(
            self._component_state_changed_callback
        )

    def stop_communicating(self: ApiuSimulatorComponentManager) -> None:
        """Break off communication with the APIU simulator."""
        super().stop_communicating()
        cast(ApiuSimulator, self._component).set_antenna_power_changed_callback(None)

    def __getattr__(
        self: ApiuSimulatorComponentManager,
        name: str,
        default_value: Any = None,
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in [
            "current",
            "humidity",
            "temperature",
            "voltage",
            "antenna_count",
            "are_antennas_on",
            "get_antenna_current",
            "get_antenna_temperature",
            "get_antenna_voltage",
            "is_antenna_on",
            "simulate_antenna_current",
            "simulate_antenna_temperature",
            "simulate_antenna_voltage",
            "simulate_current",
            "simulate_humidity",
            "simulate_temperature",
            "simulate_voltage",
            "turn_off_antenna",
            "turn_on_antenna",
            "turn_off_antennas",
            "turn_on_antennas",
        ]:
            return self._get_from_component(name)
        return default_value

    # @check_communicating
    def _get_from_component(
        self: ApiuSimulatorComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)


class SwitchingApiuComponentManager(DriverSimulatorSwitchingComponentManager):
    """A component manager that switches between APIU simulator and driver."""

    def __init__(
        self: SwitchingApiuComponentManager,
        initial_simulation_mode: SimulationMode,
        antenna_count: int,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param antenna_count: number of antennas managed by this APIU
        :param logger: a logger for this object to use
        :param max_workers: Nos. of worker threads for async commands.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        apiu_simulator = ApiuSimulatorComponentManager(
            antenna_count,
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )
        super().__init__(None, apiu_simulator, initial_simulation_mode)


class ApiuComponentManager(ComponentManagerWithUpstreamPowerSupply):
    """A component manager for an APIU (simulator or driver) and its power supply."""

    def __init__(
        self: ApiuComponentManager,
        initial_simulation_mode: SimulationMode,
        antenna_count: int,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        _initial_power_mode: PowerState = PowerState.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param antenna_count: the number of antennas managed by this
            APIU
        :param logger: a logger for this object to use
        :param max_workers: nos. of worker threads
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param _initial_power_mode: the initial power mode of the power
            supply proxy simulator. For testing only, to be removed when
            we start connecting to the real upstream power supply
            device.
        """
        hardware_component_manager = SwitchingApiuComponentManager(
            initial_simulation_mode,
            antenna_count,
            logger,
            max_workers,
            self._hardware_communication_status_changed,
            component_state_changed_callback,
        )
        power_supply_component_manager = PowerSupplyProxySimulator(
            logger,
            max_workers,
            self._power_supply_communication_status_changed,
            component_state_changed_callback,
            _initial_power_mode,
        )
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )

    @property
    def simulation_mode(self: ApiuComponentManager) -> SimulationMode:
        """
        Return the simulation mode of this component manager.

        :return: the simulation mode of this component manager.
        """
        return cast(
            SwitchingApiuComponentManager, self._hardware_component_manager
        ).simulation_mode

    @simulation_mode.setter
    def simulation_mode(self: ApiuComponentManager, mode: SimulationMode) -> None:
        """
        Set the simulation mode of this component manager.

        :param mode: the new simulation mode of this component manager
        """
        cast(
            SwitchingApiuComponentManager, self._hardware_component_manager
        ).simulation_mode = mode

    def __getattr__(
        self: ApiuComponentManager,
        name: str,
        default_value: Any = None,
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in [
            "current",
            "humidity",
            "temperature",
            "voltage",
            "antenna_count",
            "are_antennas_on",
            "get_antenna_current",
            "get_antenna_temperature",
            "get_antenna_voltage",
            "is_antenna_on",
            "simulate_antenna_current",
            "simulate_antenna_temperature",
            "simulate_antenna_voltage",
            "simulate_current",
            "simulate_humidity",
            "simulate_temperature",
            "simulate_voltage",
            "turn_off_antenna",
            "turn_on_antenna",
            "turn_off_antennas",
            "turn_on_antennas",
        ]:
            return self._get_from_hardware(name)
        return default_value

    @check_communicating
    @check_on
    def _get_from_hardware(
        self: ApiuComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._hardware_component_manager, name)

    def on(
        self: ApiuComponentManager,
        task_callback: Callable = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the on slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(self._on, task_callback=task_callback)

    def _on(
        self: ApiuComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Tell the APIU simulator to turn on.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the APIU hardware off. Here we
        overrule it so that, should the APIU hardware be turned on
        again, the antennas will be turned off.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: abort callback
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            super().on()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(status=TaskStatus.ABORTED, result="This task aborted")
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Off command has completed"
            )

    def off(
        self: ApiuComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the off slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(self._off, task_callback=task_callback)

    def _off(
        self: ApiuComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Tell the APIU simulator to turn off.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the APIU hardware off. Here we
        overrule it so that, should the APIU hardware be turned on
        again, the antennas will be turned off.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: abort callback
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingApiuComponentManager, self._hardware_component_manager
            ).turn_off_antennas()
            super().off()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(status=TaskStatus.ABORTED, result="This task aborted")
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="Off command has completed"
            )

    def power_up_antenna(
        self: ApiuComponentManager,
        antenna: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[ResultCode, str]:
        """
        Submit the turn_on_antenna slow task.

        This method returns immediately after it is submitted for execution.

        :param antenna: the antenna to turn on
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._turn_on_antenna, args=[antenna], task_callback=task_callback
        )

    def power_down_antenna(
        self: ApiuComponentManager,
        antenna: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[ResultCode, str]:
        """
        Submit the turn_off_antenna slow task.

        This method returns immediately after it is submitted for execution.

        :param antenna: the antenna to turn off
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._turn_off_antenna, args=[antenna], task_callback=task_callback
        )

    def power_up(
        self: ApiuComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[ResultCode, str]:
        """
        Submit the turn_on_antennas slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(self._turn_on_antennas, task_callback=task_callback)

    def power_down(
        self: ApiuComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[ResultCode, str]:
        """
        Submit the turn_off_antennas slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(self._turn_off_antennas, task_callback=task_callback)

    def _turn_on_antenna(
        self: ApiuComponentManager,
        antenna: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on the antenna using slow command.

        :param antenna: id of antenna to turn on
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._hardware_component_manager.turn_on_antenna(antenna)
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The antenna on task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="The antenna on task has completed"
            )

    def _turn_off_antenna(
        self: ApiuComponentManager,
        antenna: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn off the antenna using slow command.

        :param antenna: id of antenna to turn on
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._hardware_component_manager.turn_off_antenna(antenna)
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The antenna off task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="The antenna off task has completed"
            )

    def _turn_on_antennas(
        self: ApiuComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on all antennas using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self._hardware_component_manager.turn_on_antennas()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The antenna all on task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The antenna all on task has completed",
            )

    def _turn_off_antennas(
        self: ApiuComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn off all antennas using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        self._hardware_component_manager.turn_off_antennas()

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The antenna all off task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The antenna all off task has completed",
            )
