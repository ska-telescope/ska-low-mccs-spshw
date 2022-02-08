# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for subracks."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, cast

from ska_tango_base.base.task_queue_manager import QueueManager
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode, SimulationMode

from ska_low_mccs.component import (
    CommunicationStatus,
    ComponentManagerWithUpstreamPowerSupply,
    ExtendedPowerMode,
    ObjectComponentManager,
    PowerSupplyProxySimulator,
    SwitchingComponentManager,
    check_communicating,
    check_on,
)
from ska_low_mccs.subrack import SubrackData, SubrackDriver, SubrackSimulator

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
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Callable[[list[ExtendedPowerMode]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_simulator: a subrack simulator object to use
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_progress_changed_callback: callback to be called when the
            component command progress values changes
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of an tpm changes
        """
        super().__init__(
            subrack_simulator,
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            component_fault_callback,
        )
        self._tpm_power_modes = [ExtendedPowerMode.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        self._component_tpm_power_changed_callback = component_tpm_power_changed_callback
        self._component_tpm_power_changed_callback(self._tpm_power_modes)

        self._component_progress_changed_callback = component_progress_changed_callback

    def start_communicating(self: BaseSubrackSimulatorComponentManager) -> None:
        """Establish communication with the subrack simulator."""
        if self.communication_status != CommunicationStatus.DISABLED:
            return

        super().start_communicating()
        cast(SubrackSimulator, self._component).set_are_tpms_on_changed_callback(self._are_tpms_on_changed)
        cast(SubrackSimulator, self._component).set_progress_changed_callback(
            self._component_progress_changed_callback
        )

    def stop_communicating(self: BaseSubrackSimulatorComponentManager) -> None:
        """Break off communication with the subrack simulator."""
        if self.communication_status == CommunicationStatus.DISABLED:
            return

        cast(SubrackSimulator, self._component).set_are_tpms_on_changed_callback(None)
        cast(SubrackSimulator, self._component).set_progress_changed_callback(None)
        super().stop_communicating()

    def _are_tpms_on_changed(self: BaseSubrackSimulatorComponentManager, are_tpms_on: list[bool]) -> None:
        tpm_power_modes = [
            ExtendedPowerMode.ON if is_tpm_on else ExtendedPowerMode.OFF for is_tpm_on in are_tpms_on
        ]
        # if self._tpm_power_modes == tpm_power_modes:
        #     return
        # Report anyway. Let upper levels decide if information is redundant
        self._tpm_power_modes = tpm_power_modes
        self._component_tpm_power_changed_callback(tpm_power_modes)

    @property
    def tpm_power_modes(
        self: BaseSubrackSimulatorComponentManager,
    ) -> list[ExtendedPowerMode]:
        """
        Return the power modes of the TPMs.

        :return: the power modes of each TPM.
        """
        return list(self._tpm_power_modes)

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
            "turn_off_tpm",
            "turn_on_tpm",
            "turn_on_tpms",
            "turn_off_tpms",
            "check_tpm_power_modes",
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

    @check_communicating
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
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Callable[[list[ExtendedPowerMode]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_progress_changed_callback: callback to be called when the
            component command progress values changes
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of an tpm changes
        """
        super().__init__(
            SubrackSimulator(),
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )


class SwitchingSubrackComponentManager(SwitchingComponentManager):
    """A component manager that switches between subrack simulator(x2) and a driver."""

    def __init__(
        self: SwitchingSubrackComponentManager,
        initial_simulation_mode: SimulationMode,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        subrack_ip: str,
        subrack_port: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Callable[[list[ExtendedPowerMode]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_progress_changed_callback: callback to be called when the
            component command progress values changes
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of an tpm changes
        """
        subrack_driver = SubrackDriver(
            logger,
            push_change_event,
            subrack_ip,
            subrack_port,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )
        subrack_simulator = SubrackSimulatorComponentManager(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )
        super().__init__(
            {
                (SimulationMode.FALSE): subrack_driver,
                (SimulationMode.TRUE): subrack_simulator,
            },
            (initial_simulation_mode),
        )

    @property
    def simulation_mode(self: SwitchingSubrackComponentManager) -> SimulationMode:
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

    def create_queue_manager(self: SubrackComponentManager) -> QueueManager:
        """
        Create a QueueManager.

        Overwrite the creation of the queue manger specifying the
        required max queue size and number of workers.

        :return: The queue manager.
        """
        return QueueManager(
            max_queue_size=8,  # 8 PowerOnTpm commands
            num_workers=1,
            logger=self.logger,
            push_change_event=self._push_change_event,
        )

    def __init__(
        self: SubrackComponentManager,
        initial_simulation_mode: SimulationMode,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        subrack_ip: str,
        subrack_port: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        tpm_power_changed_callback: Callable[[list[ExtendedPowerMode]], None],
        _initial_power_mode: PowerMode = PowerMode.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param logger: a logger for this object to use
        :param push_change_event: method to call when the base classes
            want to send an event
        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_progress_changed_callback: callback to be called when the
            component command progress values changes
        :param tpm_power_changed_callback: callback to be called when
            the power mode of an tpm changes
        :param _initial_power_mode: the initial power mode of the power
            supply proxy simulator. For testing only, to be removed when
            we start connecting to the real upstream power supply
            device.
        """
        self._tpm_power_modes = [ExtendedPowerMode.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        self._tpm_power_changed_callback = tpm_power_changed_callback
        self._tpm_power_changed_callback(self._tpm_power_modes)

        hardware_component_manager = SwitchingSubrackComponentManager(
            initial_simulation_mode,
            logger,
            push_change_event,
            subrack_ip,
            subrack_port,
            self._hardware_communication_status_changed,
            self.component_fault_changed,
            self.component_progress_changed,
            self._tpm_power_changed,
        )

        power_supply_component_manager = PowerSupplyProxySimulator(
            logger,
            push_change_event,
            self._power_supply_communication_status_changed,
            self.component_power_mode_changed,
            _initial_power_mode,
        )
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
        )

    @property
    def tpm_power_modes(self: SubrackComponentManager) -> list[ExtendedPowerMode]:
        """
        Return the power modes of the TPMs.

        :return: the power modes of each TPM.
        """
        return list(self._tpm_power_modes)

    def _tpm_power_changed(self: SubrackComponentManager, tpm_power_modes: list[ExtendedPowerMode]) -> None:
        """
        Handle change in TPM power.

        This is a callback, provided to the underlying hardware
        component manager, to be called whenever the power mode of any
        TPM changes.

        :param tpm_power_modes: the power modes of all TPMs
        """
        self._update_tpm_power_modes(tpm_power_modes)

    def _update_tpm_power_modes(
        self: SubrackComponentManager, tpm_power_modes: list[ExtendedPowerMode]
    ) -> None:
        """
        Update the power modes of the TPMs, ensuring that the callback is called.

        This is a helper method, responsible for updating this component
        manager's record of the TPM power modes, and ensuring that the
        callback is called as required.

        :param tpm_power_modes: the power mode of each TPM
        """
        #
        # Here can safely check fo redundancy, as extended power modes
        # (NO_SUPPLY, UNKNOWN) have already been included in the attribute
        if self._tpm_power_modes == tpm_power_modes:
            return
        self._tpm_power_modes = list(tpm_power_modes)
        self._tpm_power_changed_callback(tpm_power_modes)

    def _power_supply_communication_status_changed(
        self: SubrackComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the hardware.

        :param communication_status: the status of communication with
            the hardware.
        """
        super()._power_supply_communication_status_changed(communication_status)
        if communication_status == CommunicationStatus.DISABLED:
            self._update_tpm_power_modes([ExtendedPowerMode.UNKNOWN] * SubrackData.TPM_BAY_COUNT)

    def component_power_mode_changed(self: SubrackComponentManager, power_mode: PowerMode) -> None:
        """
        Handle a change in power mode of the hardware.

        :param power_mode: the power mode of the hardware
        """
        if power_mode == PowerMode.UNKNOWN:
            self._update_tpm_power_modes([ExtendedPowerMode.UNKNOWN] * SubrackData.TPM_BAY_COUNT)
        elif power_mode == PowerMode.OFF:
            self._update_tpm_power_modes([ExtendedPowerMode.NO_SUPPLY] * SubrackData.TPM_BAY_COUNT)

        super().component_power_mode_changed(power_mode)

    @property
    def simulation_mode(self: SubrackComponentManager) -> SimulationMode:
        """
        Return the simulation mode of this component manager.

        :return: the simulation mode of this component manager.
        """
        return cast(SwitchingSubrackComponentManager, self._hardware_component_manager).simulation_mode

    @simulation_mode.setter
    def simulation_mode(self: SubrackComponentManager, mode: SimulationMode) -> None:
        """
        Set the simulation mode of this component manager.

        :param mode: the new simulation mode of this component manager
        """
        cast(SwitchingSubrackComponentManager, self._hardware_component_manager).simulation_mode = mode

    def off(self: SubrackComponentManager) -> ResultCode | None:
        """
        Tell the subrack simulator to turn off.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the subrack hardware off. Here we
        overrule it so that, should the subrack hardware be turned on
        again, the tpms will be turned off.

        :return: a result code, or None if there was nothing to do.
        """
        cast(SwitchingSubrackComponentManager, self._hardware_component_manager).turn_off_tpms()
        result_code = super().off()
        return result_code

    @check_communicating
    def turn_off_tpm(self: SubrackComponentManager, logical_tpm_id: int) -> bool | None:
        """
        Turn off a TPM.

        TODO: This method is implemented with a temporary measure to
        handle a common race condition. When ``MccsController.Off()`` is
        called, both ``MccsTile`` and ``MccsSubrack`` may end up being
        told to turn off at roughly the same time. This can result in
        ``MccsTile`` telling its subrack to turn off its TPM when the
        subrack has itself just been turned off. For now, we handle this
        by accepting the command (and doing nothing) when the subrack is
        off. In future, we should review this behaviour in case there is
        a better way to handle it.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off

        :return: whether successful, or None if there was nothing to do

        :raises ConnectionError: if the subrack is neither off not on
            (when on, we can turn the TPM off, when off, there's nothing
            to do here.)
        """
        if self.power_mode == PowerMode.OFF:
            return None
        elif self.power_mode == PowerMode.ON:
            return cast(SwitchingSubrackComponentManager, self._hardware_component_manager).turn_off_tpm(
                logical_tpm_id
            )
        else:
            raise ConnectionError("Component is not turned on.")

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
            "turn_on_tpm",
            "turn_on_tpms",
            "turn_off_tpms",
            "check_tpm_power_modes",
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
