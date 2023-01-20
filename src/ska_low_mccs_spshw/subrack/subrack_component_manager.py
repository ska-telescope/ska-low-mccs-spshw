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
from typing import Callable, Optional, cast

from ska_control_model import CommunicationStatus, PowerState, TaskStatus
from ska_low_mccs_common.component import (
    ComponentManagerWithUpstreamPowerSupply,
    PowerSupplyProxySimulator,
)

from .new_subrack_driver import NewSubrackDriver
from .subrack_data import FanMode, SubrackData

__all__ = ["SubrackComponentManager"]


class SubrackComponentManager(ComponentManagerWithUpstreamPowerSupply):
    """A component manager for an subrack (simulator or driver) and its power supply."""

    def __init__(  # pylint: disable=too-many-arguments
        self: SubrackComponentManager,
        subrack_ip: str,
        subrack_port: int,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[..., None],
        update_rate: float = 5.0,
        _driver: Optional[NewSubrackDriver] = None,
        _initial_power_state: PowerState = PowerState.OFF,
        _initial_fail: bool = False,
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_ip: the IP address of the subrack
        :param subrack_port: the subrack port
        :param logger: a logger for this object to use
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
        """
        self._tpm_power_states_lock = threading.Lock()
        self._tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        self._component_state_changed_callback = component_state_changed_callback

        hardware_component_manager = _driver or NewSubrackDriver(
            subrack_ip,
            subrack_port,
            logger,
            self._hardware_communication_state_changed,
            component_state_changed_callback,
            update_rate=update_rate,
        )
        power_supply_component_manager = PowerSupplyProxySimulator(
            logger, initial_power_state=_initial_power_state, initial_fail=_initial_fail
        )

        # we only need one worker; the heavy lifting is done by the poller in the
        # hardware component manager
        super().__init__(
            hardware_component_manager,
            power_supply_component_manager,
            logger,
            1,
            communication_state_changed_callback,
            component_state_changed_callback,
            tpm_present=None,
            tpm_on_off=None,
            backplane_temperatures=None,
            board_temperatures=None,
            board_current=None,
            power_supply_currents=None,
            power_supply_fan_speeds=None,
            power_supply_powers=None,
            power_supply_voltages=None,
            subrack_fan_speeds=None,
            subrack_fan_speeds_percent=None,
            subrack_fan_modes=None,
            tpm_currents=None,
            tpm_powers=None,
            tpm_temperatures=None,
            tpm_voltages=None,
        )

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
        return cast(NewSubrackDriver, self._hardware_component_manager).turn_off_tpm(
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
        return cast(NewSubrackDriver, self._hardware_component_manager).turn_on_tpm(
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
        return cast(NewSubrackDriver, self._hardware_component_manager).turn_off_tpms(
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
        return cast(NewSubrackDriver, self._hardware_component_manager).turn_on_tpms(
            task_callback=task_callback
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
            NewSubrackDriver, self._hardware_component_manager
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
            NewSubrackDriver, self._hardware_component_manager
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
            NewSubrackDriver, self._hardware_component_manager
        ).set_power_supply_fan_speed(fan_number, speed, task_callback=task_callback)
