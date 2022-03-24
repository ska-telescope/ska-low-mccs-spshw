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
from typing import Any, Callable, Optional, cast

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState, SimulationMode

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
        component_state_changed_callback: Callable[[dict[str,Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param antenna_count: the number of antennas managed by this
            APIU
        :param logger: a logger for this object to use
        :param push_change_event: mechanism to inform the base classes
            what method to call; typically device.push_change_event.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_antenna_power_changed_callback: callback to be
            called when the power mode of an antenna changes
        """
        super().__init__(
            ApiuSimulator(antenna_count),
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
        ]:
            return self._get_from_component(name)
        return default_value

    @check_communicating
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
        max_workers,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str,Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param antenna_count: number of antennas managed by this APIU
        :param logger: a logger for this object to use
        :param push_change_event: mechanism to inform the base classes
            what method to call; typically device.push_change_event.
        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_antenna_power_changed_callback: callback to be
            called when the power mode of an antenna changes
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
        component_state_changed_callback: Callable[[dict[str,Any]], None],
        _initial_power_mode: PowerState = PowerState.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param antenna_count: the number of antennas managed by this
            APIU
        :param logger: a logger for this object to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param max_workers: nos. of worker threads
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
            self.component_state_changed_callback,
        )

        power_supply_component_manager = PowerSupplyProxySimulator(
            logger,
            self._power_supply_communication_status_changed,
            self.component_state_changed_callback,
            _initial_power_mode,
        )
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            max_workers,
            communication_status_changed_callback,
            self.component_state_changed_callback,
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

    def off(self: ApiuComponentManager) -> ResultCode | None:
        """
        Tell the APIU simulator to turn off.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the APIU hardware off. Here we
        overrule it so that, should the APIU hardware be turned on
        again, the antennas will be turned off.

        :return: a result code, or None if there was nothing to do.
        """
        cast(
            SwitchingApiuComponentManager, self._hardware_component_manager
        ).turn_off_antennas()
        return super().off()

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

    def turn_on_antenna(self, antenna: int, task_callback: Optional[Callable] = None):
        """
        Submit the turn_on_antenna slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None
        """
        task_status, response = self.submit_task(
            self._turn_on_antenna, args=[antenna], task_callback=task_callback
        )
        return task_status, response

    def turn_off_antenna(self, task_callback: Optional[Callable] = None):
        """
        Submit the turn_off_antenna slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None
        """
        task_status, response = self.submit_task(
            self._turn_off_antenna, args=[], task_callback=task_callback
        )
        return task_status, response

    def turn_on_antennas(self, task_callback: Optional[Callable] = None):
        """
        Submit the turn_on_antennas slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None
        """
        task_status, response = self.submit_task(
            self._turn_on_antennas, args=[], task_callback=task_callback
        )
        return task_status, response

    def turn_off_antennas(self, task_callback: Optional[Callable] = None):
        """
        Submit the turn_off_antennas slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None
        """
        task_status, response = self.submit_task(
            self._turn_off_antennas, args=[], task_callback=task_callback
        )
        return task_status, response
