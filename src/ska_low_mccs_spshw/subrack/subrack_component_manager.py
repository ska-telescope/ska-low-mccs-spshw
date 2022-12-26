# type: ignore
# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for subracks."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_control_model import (
    CommunicationStatus,
    PowerState,
    SimulationMode,
    TaskStatus,
)
from ska_low_mccs_common.component import (
    ComponentManagerWithUpstreamPowerSupply,
    MccsComponentManagerProtocol,
    ObjectComponentManager,
    PowerSupplyProxySimulator,
    SwitchingComponentManager,
    check_communicating,
    check_on,
)

from .internal_subrack_simulator import SubrackSimulator
from .subrack_data import SubrackData
from .subrack_driver import SubrackDriver

__all__ = [
    "BaseSubrackSimulatorComponentManager",
    "SubrackSimulatorComponentManager",
    "SubrackComponentManager",
]


class BaseSubrackSimulatorComponentManager(ObjectComponentManager):
    """A base component manager for a subrack simulator."""

    def __init__(
        self: BaseSubrackSimulatorComponentManager,
        subrack_simulator: SubrackSimulator,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_simulator: a subrack simulator object to use
        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            subrack_simulator,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        self._component_state_changed_callback = component_state_changed_callback
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

    def start_communicating(
        self: BaseSubrackSimulatorComponentManager,
    ) -> None:
        """Establish communication with the subrack simulator."""
        if self.communication_state != CommunicationStatus.DISABLED:
            return

        super().start_communicating()
        cast(SubrackSimulator, self._component).set_are_tpms_on_changed_callback(
            self._are_tpms_on_changed
        )
        cast(SubrackSimulator, self._component).set_progress_changed_callback(
            self._component_state_changed_callback
        )

    def stop_communicating(self: BaseSubrackSimulatorComponentManager) -> None:
        """Break off communication with the subrack simulator."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return
        # cast(SubrackSimulator, self._component).set_are_tpms_on_changed_callback(None)
        cast(SubrackSimulator, self._component).set_progress_changed_callback(None)
        super().stop_communicating()

    def _are_tpms_on_changed(
        self: BaseSubrackSimulatorComponentManager, are_tpms_on: list[bool]
    ) -> None:
        tpm_power_states = [
            PowerState.ON if is_tpm_on else PowerState.OFF for is_tpm_on in are_tpms_on
        ]
        # if self._tpm_power_states == tpm_power_states:
        #     return
        # Report anyway. Let upper levels decide if information is redundant
        self._tpm_power_states = tpm_power_states
        self._component_state_changed_callback({"tpm_power_states": tpm_power_states})

    @property
    def tpm_power_states(
        self: BaseSubrackSimulatorComponentManager,
    ) -> list[PowerState]:
        """
        Return the power states of the TPMs.

        :return: the power states of each TPM.
        """
        return list(self._tpm_power_states)

    def __getattr__(
        self: BaseSubrackSimulatorComponentManager,
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
            "backplane_temperatures",
            "simulate_backplane_temperatures",
            "board_temperatures",
            "simulate_board_temperatures",
            "board_current",
            "simulate_board_current",
            "subrack_fan_speeds",
            "simulate_subrack_fan_speeds",
            "subrack_fan_speeds_percent",
            "subrack_fan_modes",
            "bay_count",
            "tpm_count",
            "tpm_temperatures",
            "simulate_tpm_temperatures",
            "tpm_currents",
            "simulate_tpm_currents",
            "tpm_powers",
            "simulate_tpm_powers",
            "tpm_voltages",
            "simulate_tpm_voltages",
            "power_supply_fan_speeds",
            "simulate_power_supply_fan_speeds",
            "power_supply_currents",
            "simulate_power_supply_currents",
            "power_supply_powers",
            "simulate_power_supply_powers",
            "power_supply_voltages",
            "simulate_power_supply_voltages",
            "tpm_present",
            "tpm_supply_fault",
            "is_tpm_on",
            "turn_on_tpms",
            "turn_off_tpms",
            "turn_on_tpm",
            "turn_off_tpm",
            "check_tpm_power_states",
            "set_subrack_fan_speed",
            "set_subrack_fan_modes",
            "set_power_supply_fan_speed",
            "current",
            "humidity",
            "temperature",
            "voltage",
            "tpm_count",
            "get_tpm_current",
            "get_tpm_temperature",
            "get_tpm_voltage",
            "simulate_tpm_current",
            "simulate_tpm_temperature",
            "simulate_tpm_voltage",
            "simulate_current",
            "simulate_humidity",
            "simulate_temperature",
            "simulate_voltage",
        ]:
            return self._get_from_component(name)
        return default_value

    # @check_communicating
    def _get_from_component(
        self: BaseSubrackSimulatorComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)


class SubrackSimulatorComponentManager(BaseSubrackSimulatorComponentManager):
    """A component manager for a subrack simulator."""

    def __init__(
        self: SubrackSimulatorComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param max_workers: Nos of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            SubrackSimulator(component_state_changed_callback),
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )


class SwitchingSubrackComponentManager(SwitchingComponentManager):
    """A component manager that switches between subrack simulator(x2) and a driver."""

    def __init__(
        self: SwitchingSubrackComponentManager,
        initial_simulation_mode: SimulationMode,
        logger: logging.Logger,
        max_workers: int,
        subrack_ip: str,
        subrack_port: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param logger: a logger for this object to use
        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param max_workers: Nos. of worker threads for async commands.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        subrack_driver = SubrackDriver(
            logger,
            max_workers,
            subrack_ip,
            subrack_port,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        subrack_simulator = SubrackSimulatorComponentManager(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        super().__init__(
            {
                SimulationMode.FALSE: subrack_driver,
                SimulationMode.TRUE: subrack_simulator,
            },
            initial_simulation_mode,
        )

    @property
    def simulation_mode(
        self: SwitchingSubrackComponentManager,
    ) -> SimulationMode:
        """
        Return the simulation mode.

        :return: the simulation mode
        """
        simulation_mode: SimulationMode  # typehint only

        simulation_mode = cast(SimulationMode, self.switcher_mode)
        return simulation_mode

    @simulation_mode.setter
    def simulation_mode(
        self: SwitchingSubrackComponentManager,
        required_simulation_mode: SimulationMode,
    ) -> None:
        """
        Set the simulation mode.

        :param required_simulation_mode: the new value for the simulation mode.
        """
        simulation_mode: SimulationMode  # typehints only

        (simulation_mode) = cast(SimulationMode, self.switcher_mode)
        if simulation_mode != required_simulation_mode:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = required_simulation_mode
            if communicating:
                self.start_communicating()


class SubrackComponentManager(ComponentManagerWithUpstreamPowerSupply):
    """A component manager for an subrack (simulator or driver) and its power supply."""

    def __init__(
        self: SubrackComponentManager,
        initial_simulation_mode: SimulationMode,
        logger: logging.Logger,
        max_workers: int,
        subrack_ip: str,
        subrack_port: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        _initial_power_state: PowerState = PowerState.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param logger: a logger for this object to use
        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param max_workers: nos. of worker threads
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param _initial_power_state: the initial power mode of the power
            supply proxy simulator. For testing only, to be removed when
            we start connecting to the real upstream power supply
            device.
        """
        self._tpm_power_states_lock = threading.Lock()
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        self._component_state_changed_callback = component_state_changed_callback

        hardware_component_manager = SwitchingSubrackComponentManager(
            initial_simulation_mode,
            logger,
            max_workers,
            subrack_ip,
            subrack_port,
            self._hardware_communication_state_changed,
            component_state_changed_callback,
            # self._tpm_power_changed,
        )
        power_supply_component_manager = PowerSupplyProxySimulator(
            logger,
            max_workers,
            self._power_supply_communication_state_changed,
            component_state_changed_callback,
            _initial_power_state,
            self.component_power_state_changed,
        )
        super().__init__(
            cast(MccsComponentManagerProtocol, hardware_component_manager),
            power_supply_component_manager,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    @property
    def tpm_power_states(
        self: SubrackComponentManager,
    ) -> list[PowerState]:
        """
        Return the power states of the TPMs.

        :return: the power states of each TPM.
        """
        return list(self._tpm_power_states)

    def _tpm_power_changed(
        self: SubrackComponentManager,
        tpm_power_states: list[PowerState],
    ) -> None:
        """
        Handle change in TPM power.

        This is a callback, provided to the underlying hardware
        component manager, to be called whenever the power mode of any
        TPM changes.

        :param tpm_power_states: the power states of all TPMs
        """
        self._update_tpm_power_states(tpm_power_states)

    def _update_tpm_power_states(
        self: SubrackComponentManager,
        tpm_power_states: list[PowerState],
    ) -> None:
        """
        Update the power states of the TPMs, ensuring that the callback is called.

        This is a helper method, responsible for updating this component
        manager's record of the TPM power states, and ensuring that the
        callback is called as required.

        :param tpm_power_states: the power mode of each TPM
        """
        #
        # Here can safely check fo redundancy, as extended power states
        # (NO_SUPPLY, UNKNOWN) have already been included in the attribute
        if self._tpm_power_states == tpm_power_states:
            return
        self._tpm_power_states = list(tpm_power_states)
        self._component_state_changed_callback({"tpm_power_states": tpm_power_states})

    def _power_supply_communication_state_changed(
        self: SubrackComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the hardware.

        :param communication_state: the status of communication with
            the hardware.
        """
        super()._power_supply_communication_state_changed(communication_state)
        if communication_state == CommunicationStatus.DISABLED:
            self._update_tpm_power_states(
                [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
            )

    def component_power_state_changed(
        self: SubrackComponentManager, power_state: PowerState
    ) -> None:
        """
        Handle a change in power state of the hardware.

        :param power_state: the power state of the hardware
        """
        if power_state == PowerState.UNKNOWN:
            self._update_tpm_power_states(
                [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
            )
        elif power_state == PowerState.OFF:
            self._update_tpm_power_states(
                [PowerState.NO_SUPPLY] * SubrackData.TPM_BAY_COUNT
            )

        super().component_power_state_changed(power_state)

    @property
    def simulation_mode(self: SubrackComponentManager) -> SimulationMode:
        """
        Return the simulation mode of this component manager.

        :return: the simulation mode of this component manager.
        """
        return cast(
            SwitchingSubrackComponentManager, self._hardware_component_manager
        ).simulation_mode

    @simulation_mode.setter
    def simulation_mode(self: SubrackComponentManager, mode: SimulationMode) -> None:
        """
        Set the simulation mode of this component manager.

        :param mode: the new simulation mode of this component manager
        """
        cast(
            SwitchingSubrackComponentManager, self._hardware_component_manager
        ).simulation_mode = mode

    def on(
        self: SubrackComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the on slow task.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None

        :returns: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(self._on, task_callback=task_callback)

    def _on(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Tell the upstream power supply proxy to turn the hardware on.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            super().on()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="On command has been aborted"
                )
            return
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="On command has completed"
            )

    def off(
        self: SubrackComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the off slow task.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None

        :returns: task status and message
        """
        return self.submit_task(self._off, task_callback=task_callback)

    def _off(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Tell the subrack simulator to turn off.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the subrack hardware off. Here we
        overrule it so that, should the subrack hardware be turned on
        again, the tpms will be turned off.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingSubrackComponentManager,
                self._hardware_component_manager,
            ).turn_off_tpms()
            super().off()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="Off command has been aborted"
                )
            return

        if task_callback:
            task_callback(status=TaskStatus.COMPLETED, result="Off command completed")

    def __getattr__(
        self: SubrackComponentManager,
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
            "backplane_temperatures",
            "simulate_backplane_temperatures",
            "board_temperatures",
            "simulate_board_temperatures",
            "board_current",
            "simulate_board_current",
            "subrack_fan_speeds",
            "simulate_subrack_fan_speeds",
            "subrack_fan_speeds_percent",
            "subrack_fan_modes",
            "bay_count",
            "tpm_count",
            "tpm_temperatures",
            "simulate_tpm_temperatures",
            "tpm_currents",
            "simulate_tpm_currents",
            "tpm_powers",
            "simulate_tpm_powers",
            "tpm_voltages",
            "simulate_tpm_voltages",
            "power_supply_fan_speeds",
            "simulate_power_supply_fan_speeds",
            "power_supply_currents",
            "simulate_power_supply_currents",
            "power_supply_powers",
            "simulate_power_supply_powers",
            "power_supply_voltages",
            "simulate_power_supply_voltages",
            "tpm_present",
            "tpm_supply_fault",
            "is_tpm_on",
            "turn_on_tpms",
            "turn_off_tpms",
            "turn_on_tpm",
            "turn_off_tpm",
            "check_tpm_power_states",
            "set_subrack_fan_speed",
            "set_subrack_fan_modes",
            "set_power_supply_fan_speed",
            "current",
            "humidity",
            "temperature",
            "voltage",
            "tpm_count",
            "get_tpm_current",
            "get_tpm_temperature",
            "get_tpm_voltage",
            "simulate_tpm_current",
            "simulate_tpm_temperature",
            "simulate_tpm_voltage",
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
        self: SubrackComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._hardware_component_manager, name)

    def set_power_state(self: SubrackComponentManager, power_state: PowerState) -> None:
        """
        Set the power state of the subrack.

        :param power_state: The desired power state
        """
        with self._tpm_power_states_lock:
            self.power_state = power_state

    def turn_on_tpm(
        self: SubrackComponentManager,
        tpm_id: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the turn_on_tpm slow task.

        This method returns immediately after it is submitted for execution.

        :param tpm_id: the tpm to turn on
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a TaskStatus and a response message
        """
        return self.submit_task(
            self._turn_on_tpm, args=[tpm_id], task_callback=task_callback
        )

    def _turn_on_tpm(
        self: SubrackComponentManager,
        tpm_id: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on the tpm using slow command.

        :param tpm_id: id of antenna to turn on
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingSubrackComponentManager,
                self._hardware_component_manager,
            ).turn_on_tpm(tpm_id)
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The turn tpm on task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=f"Subrack TPM {tpm_id} turn on tpm task has completed",
            )
            return

    def turn_on_tpms(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the turn_on_tpms slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to
            identify the command
        """
        return self.submit_task(self._turn_on_tpms, task_callback=task_callback)

    def _turn_on_tpms(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn on the tpm using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingSubrackComponentManager,
                self._hardware_component_manager,
            ).turn_on_tpms()
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The turn tpms on task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The turn tpms on task has completed",
            )
            return

    def turn_off_tpm(
        self: SubrackComponentManager,
        tpm_id: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the turn_off_tpm slow task.

        This method returns immediately after it is submitted for execution.

        :param tpm_id: the tpm to turn on
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing TaskStatus and a response message
        """
        return self.submit_task(
            self._turn_off_tpm, args=[tpm_id], task_callback=task_callback
        )

    def _turn_off_tpm(
        self: SubrackComponentManager,
        tpm_id: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        " Turn on the tpm using slow command.

        TODO: This method is implemented with a temporary measure to
        handle a common race condition. When ``MccsController.Off()`` is
        called, both ``MccsTile`` and ``MccsSubrack`` may end up being
        told to turn off at roughly the same time. This can result in
        ``MccsTile`` telling its subrack to turn off its TPM when the
        subrack has itself just been turned off. For now, we handle this
        by accepting the command (and doing nothing) when the subrack is
        off. In future, we should review this behaviour in case there is
        a better way to handle it.

        :param tpm_id: id of antenna to turn on
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if self.power_state == PowerState.OFF:
            return
        elif self.power_state == PowerState.ON:
            if task_callback:
                task_callback(status=TaskStatus.IN_PROGRESS)
            try:
                cast(
                    SwitchingSubrackComponentManager,
                    self._hardware_component_manager,
                ).turn_off_tpm(tpm_id)
            except Exception as ex:
                self.logger.error(f"error {ex}")
                if task_callback:
                    task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
                return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The turn tpm off task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=f"Subrack TPM {tpm_id} turn off tpm task has completed",
            )
            return

    def turn_off_tpms(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the turn_off_tpms slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a TaskStatus and a response message
        """
        return self.submit_task(self._turn_off_tpms, task_callback=task_callback)

    def _turn_off_tpms(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn off the tpm using slow command.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            cast(
                SwitchingSubrackComponentManager,
                self._hardware_component_manager,
            ).turn_off_tpms()
        except Exception as ex:
            self.logger.error(f"error {ex}")
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The turn tpms off task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The turn tpms off task has completed",
            )
            return
