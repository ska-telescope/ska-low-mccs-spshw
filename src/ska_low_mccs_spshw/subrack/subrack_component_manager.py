#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for subracks."""
from __future__ import annotations

import functools
import json
import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common.communication_manager import CommunicationManager
from ska_low_mccs_common.component import (
    ComponentManagerWithUpstreamPowerSupply,
    DeviceComponentManager,
    PowerSupplyProxySimulator,
)
from ska_tango_base.base import check_communicating

from .subrack_data import FanMode
from .subrack_driver import SubrackDriver

__all__ = ["SubrackComponentManager"]


class _PowerMarshallerProxy(DeviceComponentManager):
    """A proxy to the power marshaller."""

    def __init__(
        self: _PowerMarshallerProxy,
        trl: str,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param trl: the trl of the device
        :param logger: the logger to be used by this object.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        self.trl = trl
        super().__init__(
            trl,
            logger,
            communication_state_callback,
            component_state_callback,
        )

    def schedule_power(
        self: _PowerMarshallerProxy,
        attached_device_info: str,
        device_trl: str,
        command_str: str,
        on_off: str,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param attached_device_info: details about the attached device.
        :param device_trl: trl of this device.
        :param command_str: name of the command being called.
        :param on_off: args to be called for the command.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        input_dict = {
            "attached_device_info": attached_device_info,
            "device_trl": device_trl,
            "command_str": command_str,
            "command_args": on_off,
        }
        input_str = json.dumps(input_dict)
        self._proxy._device.SchedulePower(input_str)


class _PDUProxy(DeviceComponentManager):
    """A proxy to a PDU, for a subrack to use."""

    def __init__(
        self: _PDUProxy,
        fqdn: str,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        self.fqdn = fqdn
        super().__init__(
            fqdn,
            logger,
            communication_state_callback,
            component_state_callback,
        )

    def _get_health_state(self: _PDUProxy) -> str:
        """
        Get the pdu health.

        :return: health.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        return self._proxy._device.healthState

    def _get_model(self: _PDUProxy) -> str:
        """
        Get the pdu model type.

        :return: model type.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        return self._proxy._device.pduModel

    def _number_of_ports(self: _PDUProxy) -> int:
        """
        Get number of PDU ports.

        :return: number of ports.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        return self._proxy._device.pduNumberOfPorts

    def _pdu_port_on(self: _PDUProxy, port_number: int) -> None:
        """
        Turn on a PDU port.

        :param port_number: the port number to be turned on.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        attr_name = f"pduPort{port_number}OnOff"
        func = getattr(self._proxy._device, attr_name)

        func()

    def _pdu_port_off(self: _PDUProxy, port_number: int) -> None:
        """
        Turn off a PDU port.

        :param port_number: the port number to be turned off.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        attr_name = f"pduPort{port_number}OnOff"
        func = getattr(self._proxy._device, attr_name)

        func()

    def _pdu_port_current(self: _PDUProxy, port_number: int) -> float:
        """
        Get the current for a PDU port.

        :param port_number: the port number to get current for.

        :return: current for port provided.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        attr_name = f"pduPort{port_number}Current"
        func = getattr(self._proxy._device, attr_name)

        return func()

    def _pdu_port_voltage(self: _PDUProxy, port_number: int) -> float:
        """
        Get the voltage for a PDU port.

        :param port_number: the port number to get voltage for.

        :return: voltage for port provided.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        attr_name = f"pduPort{port_number}Voltage"
        func = getattr(self._proxy._device, attr_name)

        return func()

    def _pdu_port_state(self: _PDUProxy, port_number: int) -> int:
        """
        Get the state for a PDU port.

        :param port_number: the port number to get state for.

        :return: state for port provided.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        attr_name = f"pduPort{port_number}State"
        func = getattr(self._proxy._device, attr_name)

        return func()


# pylint: disable = too-many-instance-attributes, too-many-public-methods
class SubrackComponentManager(ComponentManagerWithUpstreamPowerSupply):
    """A component manager for an subrack (simulator or driver) and its power supply."""

    def __init__(  # pylint: disable=too-many-arguments
        self: SubrackComponentManager,
        subrack_ip: str,
        subrack_port: int,
        logger: logging.Logger,
        pdu_trl: str,
        pdu_ports: list[int],
        power_marshaller_trl: str,
        simulated_pdu: bool,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        update_rate: float = 5.0,
        _driver: Optional[SubrackDriver] = None,
        _initial_power_state: PowerState = PowerState.ON,
        _initial_fail: bool = False,
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param logger: a logger for this object to use
        :param pdu_trl: trl for the pdu device
        :param pdu_ports: the ports of the pdu that this subrack is
            plugged into
        :param power_marshaller_trl: trl for the power marshaller device
        :param simulated_pdu: if we are using a simulated pdu or not
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param update_rate: how often updates to attribute values should
            be provided. This is not necessarily the same as the rate at
            which the instrument is polled. For example, the instrument
            may be polled every 0.1 seconds, thus ensuring that any
            invoked commands or writes will be executed promptly.
            However, if the `update_rate` is 5.0, then routine reads of
            instrument values will only occur every 50th poll (i.e.
            every 5 seconds).
        :param _driver: for testing only, we can inject a driver rather
            then letting the component manager create its own. If
            provided, this overrides driver-specific arguments such as
            the IP and port.
        :param _initial_power_state: for testing only, we can set the
            initial power state of the simulated subrack power supply.
            If not provided, the default is ON, since all our current
            facilities with a real hardware subrack do not yet allow it
            to be powered on and off.
        :param _initial_fail: for testing only, we can set the simulated
            subrack power supply to fail.
        """
        self._component_state_changed_callback = component_state_changed_callback

        hardware_component_manager = _driver or SubrackDriver(
            subrack_ip,
            subrack_port,
            logger,
            self._hardware_communication_state_changed,
            component_state_changed_callback,
            update_rate=update_rate,
        )

        self.pdu_trl = pdu_trl
        self.pdu_ports = pdu_ports
        self.simulated_pdu = simulated_pdu
        power_supply_component_manager = PowerSupplyProxySimulator(
            logger,
            None,  # super() call will set the communication_state_changed_callback
            None,  # super() call with set the component_state_changed_callback
            initial_power_state=_initial_power_state,
            initial_fail=_initial_fail,
        )

        # we only need one worker; the heavy lifting is done by the poller in the
        # hardware component manager
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            tpm_present=None,
            tpm_on_off=None,
            backplane_temperatures=None,
            board_temperatures=None,
            board_current=None,
            cpld_pll_locked=None,
            power_supply_currents=None,
            power_supply_fan_speeds=None,
            power_supply_powers=None,
            power_supply_voltages=None,
            subrack_fan_speeds=None,
            subrack_fan_speeds_percent=None,
            subrack_fan_mode=None,
            subrack_pll_locked=None,
            subrack_timestamp=None,
            tpm_currents=None,
            tpm_powers=None,
            # tpm_temperatures=None,  # Not implemented on SMB
            tpm_voltages=None,
            board_info=None,
            health_status=None,
        )
        self.pdu_proxy = (
            None
            if simulated_pdu
            else _PDUProxy(
                pdu_trl,
                logger,
                functools.partial(self._device_communication_state_changed, pdu_trl),
                functools.partial(self._pdu_state_changed, pdu_trl),
            )
        )
        self.proxy_map: dict[str, Any] = {}
        self.power_marshaller_trl = power_marshaller_trl
        self.power_marshaller_proxy = _PowerMarshallerProxy(
            power_marshaller_trl,
            logger,
            functools.partial(self._device_communication_state_changed, pdu_trl),
            functools.partial(self._pdu_state_changed, pdu_trl),
        )
        self.proxy_map[self.power_marshaller_trl] = self.power_marshaller_proxy

        self._communication_manager: CommunicationManager | None = None
        if self.pdu_proxy is not None:
            self.proxy_map[pdu_trl] = self.pdu_proxy

        # TODO: This CommunicationManager does not play well with the
        # ComponentManagerWithUpstreamPowerSupply.
        self._communication_manager = CommunicationManager(
            self._update_communication_state,
            self._update_component_state,
            self.logger,
            self.proxy_map,
        )

    def start_communicating(self: SubrackComponentManager) -> None:
        """Establish communication with the subrack components."""
        super().start_communicating()
        if self._communication_manager is not None:
            self._communication_manager.start_communicating()

    def stop_communicating(self: SubrackComponentManager) -> None:
        """Break off communication with the subrack components."""
        super().stop_communicating()
        if self._communication_manager is not None:
            self._communication_manager.stop_communicating()

    def _device_communication_state_changed(
        self: SubrackComponentManager,
        trl: str,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Subdevice communication state changed.

        :param trl: device trl.
        :param communication_state: communication status
        """
        if self._communication_manager is not None:
            self._communication_manager.update_communication_status(
                trl, communication_state
            )

    def _pdu_state_changed(
        self: SubrackComponentManager,
        fqdn: str,
        power: Optional[PowerState] = None,
        **state_change: Any,
    ) -> None:
        """
        Handle pdu state change.

        :param fqdn: pdu fqdn.
        :param power: pdu power.
        :param state_change: state changes
        """
        self._component_state_changed_callback(pdu=state_change)

    def turn_off_tpm(
        self: SubrackComponentManager,
        tpm_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a TPM off.

        :param tpm_number: (one-based) number of the TPM to turn off.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(SubrackDriver, self._hardware_component_manager).turn_off_tpm(
            tpm_number, task_callback=task_callback
        )

    def turn_on_tpm(
        self: SubrackComponentManager,
        tpm_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a TPM on.

        :param tpm_number: (one-based) number of the TPM to turn on.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(SubrackDriver, self._hardware_component_manager).turn_on_tpm(
            tpm_number, task_callback=task_callback
        )

    def turn_off_tpms(
        self: SubrackComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn all TPMs off.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(SubrackDriver, self._hardware_component_manager).turn_off_tpms(
            task_callback=task_callback
        )

    def turn_on_tpms(
        self: SubrackComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn all TPMs on.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(SubrackDriver, self._hardware_component_manager).turn_on_tpms(
            task_callback=task_callback
        )

    def get_health_status(
        self: SubrackComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Read all the monitoring points available in health status.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(SubrackDriver, self._hardware_component_manager).get_health_status(
            task_callback=task_callback
        )

    def read_health_status(self: SubrackComponentManager) -> dict:
        """
        Read all the monitoring points available in health status.

        :return: monitoring points available in health status.
        """
        return cast(
            SubrackDriver, self._hardware_component_manager
        ).read_health_status()

    @check_communicating
    def pdu_health_state(
        self: SubrackComponentManager,
    ) -> Optional[str]:
        """
        Get PDU health.

        :return: pdu health.
        """
        if self.pdu_proxy is not None:
            return self.pdu_proxy._get_health_state()
        return None

    @check_communicating
    def pdu_model(
        self: SubrackComponentManager,
    ) -> Optional[str]:
        """
        Get PDU model type.

        :return: pdu model type.
        """
        if self.pdu_proxy is not None:
            return self.pdu_proxy._get_model()
        return None

    @check_communicating
    def pdu_number_of_ports(
        self: SubrackComponentManager,
    ) -> Optional[int]:
        """
        Get number of pdu ports .

        :return: number of pdu ports
        """
        if self.pdu_proxy is not None:
            return self.pdu_proxy._number_of_ports()
        return None

    @check_communicating
    def power_pdu_port_on(
        self: SubrackComponentManager,
        port_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a pdu port on.

        :param port_number: the port number
            each channeliser frequency channel.
        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._power_pdu_port_on,
            args=[port_number],
            task_callback=task_callback,
        )

    def _power_pdu_port_on(
        self: SubrackComponentManager,
        port_number: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn a pdu port on.

        :param port_number: (one-based) number of the port to turn on.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if self.pdu_proxy is not None:
            self.pdu_proxy._pdu_port_on(port_number)
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Set port value to ON"),
            )

    @check_communicating
    def power_pdu_port_off(
        self: SubrackComponentManager,
        port_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a pdu port off.

        :param port_number: the port number
            each channeliser frequency channel.
        :param task_callback: Update task state, defaults to None

        :return: a task status and response message
        """
        return self.submit_task(
            self._power_pdu_port_off,
            args=[port_number],
            task_callback=task_callback,
        )

    def _power_pdu_port_off(
        self: SubrackComponentManager,
        port_number: int,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn a pdu port off.

        :param port_number: (one-based) number of the port to turn off.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if self.pdu_proxy is not None:
            self.pdu_proxy._pdu_port_off(port_number)
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result=(ResultCode.OK, "Set port value to OFF"),
            )

    @check_communicating
    def pdu_port_currents(
        self: SubrackComponentManager,
    ) -> Optional[list[float]]:
        """
        Get the currents for a pdu port.

        :return: pdu port currents.
        """
        currents: list[float] = []
        if self.pdu_proxy is not None:
            number_of_ports = self.pdu_proxy._number_of_ports()
            for port_number in range(number_of_ports):
                currents.append(self.pdu_proxy._pdu_port_current(port_number))
            return currents
        return None

    @check_communicating
    def pdu_port_voltages(
        self: SubrackComponentManager,
    ) -> Optional[list[float]]:
        """
        Get the voltages for a pdu port.

        :return: pdu port voltages.
        """
        if self.pdu_proxy is not None:
            voltages: list[float] = []
            number_of_ports = self.pdu_proxy._number_of_ports()
            for port_number in range(number_of_ports):
                voltages.append(self.pdu_proxy._pdu_port_voltage(port_number))
            return voltages
        return None

    @check_communicating
    def pdu_port_states(
        self: SubrackComponentManager,
    ) -> Optional[list[int]]:
        """
        Get the states for a pdu port.

        :return: pdu port statuses.
        """
        if self.pdu_proxy is not None:
            states: list[int] = []
            number_of_ports = self.pdu_proxy._number_of_ports()
            for port_number in range(number_of_ports):
                states.append(self.pdu_proxy._pdu_port_state(port_number))
            return states
        return None

    def schedule_on(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Schedule self on.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self.submit_task(
            self._schedule_on,
            args=[],
            task_callback=task_callback,
        )

    def _schedule_on(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Schedule self on.

        :param task_callback: callback to be called when the status of
            the command changes
        :param task_abort_event: Check for abort, defaults to None
        """
        for port in self.pdu_ports:
            self.power_marshaller_proxy.schedule_power(
                "subrack",
                self.pdu_trl,
                "pduPortOn",
                str(port),
            )

    def schedule_off(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn self off.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self.submit_task(
            self._schedule_off,
            args=[],
            task_callback=task_callback,
        )

    def _schedule_off(
        self: SubrackComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn self off.

        :param task_callback: callback to be called when the status of
            the command changes
        :param task_abort_event: Check for abort, defaults to None
        """
        for port in self.pdu_ports:
            self.power_marshaller_proxy.schedule_power(
                "subrack",
                self.pdu_trl,
                "pduPortOff",
                str(port),
            )

    def set_subrack_fan_speed(
        self: SubrackComponentManager,
        fan_number: int,
        speed: float,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed of a subrack fan.

        :param fan_number: one-based number of the fan to be set.
        :param speed: speed setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(
            SubrackDriver, self._hardware_component_manager
        ).set_subrack_fan_speed(fan_number, speed, task_callback=task_callback)

    def set_subrack_fan_mode(
        self: SubrackComponentManager,
        fan_number: int,
        mode: FanMode,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed mode of a subrack fan.

        :param fan_number: one-based number of the fan to be set.
        :param mode: speed mode setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(
            SubrackDriver, self._hardware_component_manager
        ).set_subrack_fan_mode(fan_number, mode, task_callback=task_callback)

    def set_power_supply_fan_speed(
        self: SubrackComponentManager,
        fan_number: int,
        speed: float,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed of a power supply fan.

        :param fan_number: one-based number of the fan to be set.
        :param speed: speed setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return cast(
            SubrackDriver, self._hardware_component_manager
        ).set_power_supply_fan_speed(fan_number, speed, task_callback=task_callback)
