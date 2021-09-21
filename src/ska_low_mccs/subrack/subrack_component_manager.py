# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for subracks."""
from __future__ import annotations

import logging
from typing import Any, Callable, cast, Optional, Tuple

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode, SimulationMode, TestMode

from ska_low_mccs.subrack import (
    SubrackDriver,
    SubrackSimulator,
    TestingSubrackSimulator,
)
from ska_low_mccs.component import (
    check_communicating,
    check_on,
    CommunicationStatus,
    ComponentManagerWithUpstreamPowerSupply,
    SwitchingComponentManager,
    MessageQueue,
    ObjectComponentManager,
    PowerSupplyProxySimulator,
)


__all__ = [
    "BaseSubrackSimulatorComponentManager",
    "SubrackSimulatorComponentManager",
    "TestingSubrackSimulatorComponentManager",
    "SubrackComponentManager",
]


class BaseSubrackSimulatorComponentManager(ObjectComponentManager):
    """A base component manager for a subrack simulator."""

    def __init__(
        self: BaseSubrackSimulatorComponentManager,
        subrack_simulator: SubrackSimulator,
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_simulator: a subrack simulator object to use
        :param message_queue: the message queue to be used by this
            component manager
        :param logger: a logger for this object to use
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
            message_queue,
            logger,
            communication_status_changed_callback,
            None,
            component_fault_callback,
        )
        self._component_tpm_power_changed_callback = (
            component_tpm_power_changed_callback
        )
        self._component_progress_changed_callback = component_progress_changed_callback

    def start_communicating(self: BaseSubrackSimulatorComponentManager) -> None:
        """Establish communication with the subrack simulator."""
        super().start_communicating()
        cast(SubrackSimulator, self._component).set_tpm_power_changed_callback(
            self._component_tpm_power_changed_callback
        )
        cast(SubrackSimulator, self._component).set_progress_changed_callback(
            self._component_progress_changed_callback
        )

    def stop_communicating(self: BaseSubrackSimulatorComponentManager) -> None:
        """Break off communication with the subrack simulator."""
        super().stop_communicating()
        cast(SubrackSimulator, self._component).set_tpm_power_changed_callback(None)
        cast(SubrackSimulator, self._component).set_progress_changed_callback(None)

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
            "are_tpms_on",
            "turn_off_tpm",
            "turn_on_tpm",
            "turn_on_tpms",
            "turn_off_tpms",
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
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param message_queue: the message queue to be used by this
            component manager
        :param logger: a logger for this object to use
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
            message_queue,
            logger,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )


class TestingSubrackSimulatorComponentManager(BaseSubrackSimulatorComponentManager):
    """A component manager for a subrack simulator."""

    def __init__(
        self: TestingSubrackSimulatorComponentManager,
        message_queue: MessageQueue,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param message_queue: the message queue to be used by this
            component manager
        :param logger: a logger for this object to use
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
            TestingSubrackSimulator(),
            message_queue,
            logger,
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
        initial_test_mode: TestMode,
        message_queue: MessageQueue,
        logger: logging.Logger,
        subrack_ip: str,
        subrack_port: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the simulation mode that the component
            should start in
        :param message_queue: the message queue to be used by this
            component manager
        :param logger: a logger for this object to use
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
            message_queue,
            logger,
            subrack_ip,
            subrack_port,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )
        subrack_simulator = SubrackSimulatorComponentManager(
            message_queue,
            logger,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )
        testing_subrack_simulator = TestingSubrackSimulatorComponentManager(
            message_queue,
            logger,
            communication_status_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
            component_tpm_power_changed_callback,
        )
        super().__init__(
            {
                (SimulationMode.FALSE, TestMode.NONE): subrack_driver,
                (SimulationMode.FALSE, TestMode.TEST): subrack_driver,
                (
                    SimulationMode.TRUE,
                    TestMode.NONE,
                ): subrack_simulator,
                (
                    SimulationMode.TRUE,
                    TestMode.TEST,
                ): testing_subrack_simulator,
            },
            (initial_simulation_mode, initial_test_mode),
        )

    @property
    def simulation_mode(self: SwitchingSubrackComponentManager) -> SimulationMode:
        """
        Return the simulation mode.

        :return: the simulation mode
        """
        simulation_mode: SimulationMode  # typehint only

        (simulation_mode, _) = cast(Tuple[SimulationMode, TestMode], self.switcher_mode)
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
        test_mode: TestMode  # typehints only

        (simulation_mode, test_mode) = cast(
            Tuple[SimulationMode, TestMode], self.switcher_mode
        )
        if simulation_mode != required_simulation_mode:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = (required_simulation_mode, test_mode)
            if communicating:
                self.start_communicating()

    @property
    def test_mode(self: SwitchingSubrackComponentManager) -> TestMode:
        """
        Return the test mode.

        :return: the test mode
        """
        test_mode: TestMode  # typehint only
        (_, test_mode) = cast(Tuple[SimulationMode, TestMode], self.switcher_mode)
        return cast(TestMode, test_mode)

    @test_mode.setter
    def test_mode(
        self: SwitchingSubrackComponentManager,
        required_test_mode: TestMode,
    ) -> None:
        """
        Set the test mode.

        :param required_test_mode: the new value for the test mode.
        """
        simulation_mode: SimulationMode  # typehint only
        test_mode: TestMode  # typehint only

        (simulation_mode, test_mode) = cast(
            Tuple[SimulationMode, TestMode], self.switcher_mode
        )

        if test_mode != required_test_mode:
            communicating = self.is_communicating
            if communicating:
                self.stop_communicating()
            self.switcher_mode = (simulation_mode, required_test_mode)
            if communicating:
                self.start_communicating()


class SubrackComponentManager(ComponentManagerWithUpstreamPowerSupply):
    """A component manager for an subrack (simulator or driver) and its power supply."""

    def __init__(
        self: SubrackComponentManager,
        initial_simulation_mode: SimulationMode,
        initial_test_mode: TestMode,
        logger: logging.Logger,
        subrack_ip: str,
        subrack_port: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Callable[[bool], None],
        component_progress_changed_callback: Callable[[int], None],
        message_queue_size_callback: Callable[[int], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
        _initial_power_mode: PowerMode = PowerMode.OFF,
    ) -> None:
        """
        Initialise a new instance.

        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param initial_test_mode: the simulation mode that the component
            should start in
        :param logger: a logger for this object to use
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
        :param message_queue_size_callback: callback to be called when
            the size of the message queue changes
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of an tpm changes
        :param _initial_power_mode: the initial power mode of the power
            supply proxy simulator. For testing only, to be removed when
            we start connecting to the real upstream power supply
            device.
        """
        self._message_queue = MessageQueue(
            logger,
            queue_size_callback=message_queue_size_callback,
        )

        hardware_component_manager = SwitchingSubrackComponentManager(
            initial_simulation_mode,
            initial_test_mode,
            self._message_queue,
            logger,
            subrack_ip,
            subrack_port,
            self._hardware_communication_status_changed,
            self.component_fault_changed,
            self.component_progress_changed,
            component_tpm_power_changed_callback,
        )

        power_supply_component_manager = PowerSupplyProxySimulator(
            self._message_queue,
            logger,
            self._power_supply_communication_status_changed,
            self.component_power_mode_changed,
            _initial_power_mode,
        )
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            component_progress_changed_callback,
        )

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

    @property
    def test_mode(self: SubrackComponentManager) -> TestMode:
        """
        Return the test mode of this component manager.

        :return: the test mode of this component manager.
        """
        return cast(
            SwitchingSubrackComponentManager, self._hardware_component_manager
        ).test_mode

    @test_mode.setter
    def test_mode(self: SubrackComponentManager, mode: TestMode) -> None:
        """
        Set the test mode of this component manager.

        :param mode: the new test mode of this component manager
        """
        cast(
            SwitchingSubrackComponentManager, self._hardware_component_manager
        ).test_mode = mode

    def off(self: SubrackComponentManager) -> ResultCode | None:
        """
        Tell the subrack simulator to turn off.

        This is implemented in the super-class to tell the upstream
        power supply proxy to turn the subrack hardware off. Here we
        overrule it so that, should the subrack hardware be turned on
        again, the tpms will be turned off.

        :return: a result code, or None if there was nothing to do.
        """
        cast(
            SwitchingSubrackComponentManager, self._hardware_component_manager
        ).turn_off_tpms()
        return super().off()

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
            "are_tpms_on",
            "turn_off_tpm",
            "turn_on_tpm",
            "turn_on_tpms",
            "turn_off_tpms",
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
