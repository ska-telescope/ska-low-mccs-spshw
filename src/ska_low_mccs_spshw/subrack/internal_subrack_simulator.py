# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains an implementation of a simulator for a subrack management board.

Some assumptions of this class are:

* The subrack management board supplies power to various modules, such
  as TPMs. The subrack can deny or supply power to these modules; i.e.
  turn them off and on. If a module supports a low-power standby mode,
  then you have to talk to the module itself in order to switch it
  between standby and on.
* The subrack management board has its own sensors for module bay
  temperature, current, etc. For example, it can measure the temperature
  of a TPM even when the TPM is turned off, by measuring the bay
  temperature for the bay in which the TPM is installed. It doesn't need
  to turn the TPM on and query it in order to find out what its
  temperature is.

These assumptions may need to change in future.
"""

from __future__ import annotations  # allow forward references in type hints

import os
import threading
from time import sleep
from typing import Any, Callable, Optional

from ska_control_model import PowerState
from ska_low_mccs_common.component import ObjectComponent

from .subrack_data import FanMode, SubrackData

__all__ = ["InternalSubrackSimulator"]


class InternalSubrackSimulator(ObjectComponent):
    """A simulator of a subrack management board."""

    DEFAULT_TPM_TEMPERATURE = 40.0
    """The default temperature for a module contained in a subrack bay."""

    DEFAULT_TPM_CURRENT = 0.4
    """The default current for a module contained in a subrack bay."""

    DEFAULT_TPM_VOLTAGE = 12.0
    """The default voltage for a module contained in a subrack bay."""

    DEFAULT_TPM_POWER = DEFAULT_TPM_CURRENT * DEFAULT_TPM_VOLTAGE
    """The default power for a module contained in a subrack bay."""

    DEFAULT_BACKPLANE_TEMPERATURES = [38.0, 39.0]
    """The default temperature for the subrack backplane."""

    DEFAULT_BOARD_TEMPERATURES = [39.0, 40.0]
    """The default temperature for the subrack management board."""

    DEFAULT_BOARD_CURRENT = 1.1
    """The default current for the subrack management board."""

    DEFAULT_SUBRACK_FAN_SPEEDS = [4999.0, 5000.0, 5001.0, 5002.0]
    """
    The default fan speeds for the subrack.

    This can be overruled using the set_subrack_fan_speed method.
    """

    DEFAULT_SUBRACK_FAN_MODES = [FanMode.AUTO] * 4
    """
    The default fan mode for the subrack.

    This can be overruled using the set_fan_mode method.
    """

    DEFAULT_ARE_TPMS_ON = [False] * SubrackData.TPM_BAY_COUNT
    """The default on/off status of the housed TPMs."""

    DEFAULT_TPM_PRESENT = [True] * SubrackData.TPM_BAY_COUNT
    """Whether each TPM is present in the subrack by default."""

    DEFAULT_POWER_SUPPLY_POWERS = [50.0, 70.0]
    """The default power supply power."""

    DEFAULT_POWER_SUPPLY_VOLTAGES = [12.0, 12.1]
    """The default power supply voltage."""

    DEFAULT_POWER_SUPPLY_CURRENTS = [50.0 / 12.0, 70.0 / 12.1]
    """The default power supply current."""

    DEFAULT_POWER_SUPPLY_FAN_SPEEDS = [90.0, 100.0]
    """The default power supply fan speeds."""

    def __init__(
        self: InternalSubrackSimulator,
        component_state_changed_callback: Callable[[dict[str, Any]], None],
        backplane_temperatures: list[float] = DEFAULT_BACKPLANE_TEMPERATURES,
        board_temperatures: list[float] = DEFAULT_BOARD_TEMPERATURES,
        board_current: float = DEFAULT_BOARD_CURRENT,
        subrack_fan_speeds: list[float] = DEFAULT_SUBRACK_FAN_SPEEDS,
        subrack_fan_modes: list[FanMode] = DEFAULT_SUBRACK_FAN_MODES,
        power_supply_currents: list[float] = DEFAULT_POWER_SUPPLY_CURRENTS,
        power_supply_voltages: list[float] = DEFAULT_POWER_SUPPLY_VOLTAGES,
        power_supply_fan_speeds: list[float] = DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
        initial_are_tpms_on: list[bool] = DEFAULT_ARE_TPMS_ON,
        tpm_present: list[bool] = DEFAULT_TPM_PRESENT,
        _tpm_data: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param backplane_temperatures: the initial temperature of the subrack
            backplane from sensor 1 and 2
        :param board_temperatures: the initial temperature of the subrack management
            board from sensor 1 and 2
        :param board_current: the initial current of the subrack management board
        :param subrack_fan_speeds: the initial fan_speeds of the subrack backplane
            management board
        :param subrack_fan_modes: the initial fan modes of the subrack backplane
        :param power_supply_currents: the initial currents for the 2 power supply in the
            subrack
        :param power_supply_voltages: the initial voltages for the 2 power supply in the
            subrack
        :param power_supply_fan_speeds: the initial fan speeds in percent for the 2
            power supply in the subrack
        :param initial_are_tpms_on: the initial power state of each TPM
        :param tpm_present: the initial TPM board present on subrack
        :param _tpm_data: optional list of subrack bay simulators to be
            used. This is for testing purposes only, allowing us to
            inject our own bays instead of letting this simulator create
            them.
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        self._backplane_temperatures = list(backplane_temperatures)
        self._board_temperatures = list(board_temperatures)
        self._board_current = board_current
        self._subrack_fan_speeds = list(subrack_fan_speeds)
        self._subrack_fan_modes = list(subrack_fan_modes)
        self._power_supply_currents = list(power_supply_currents)
        self._power_supply_voltages = list(power_supply_voltages)
        self._power_supply_fan_speeds = list(power_supply_fan_speeds)
        self._tpm_data_lock = threading.RLock()
        with self._tpm_data_lock:
            self._tpm_data = _tpm_data or [
                {
                    "is_on": is_on,
                    "voltage": self.DEFAULT_TPM_VOLTAGE,
                    "current": self.DEFAULT_TPM_CURRENT,
                    "temperature": self.DEFAULT_TPM_TEMPERATURE,
                    "power": self.DEFAULT_TPM_POWER,
                }
                for is_on in initial_are_tpms_on
            ]

        self._bay_count = len(self._tpm_data)
        self._tpm_present = tpm_present[0 : self._bay_count]
        self._tpm_supply_fault = [0] * self._bay_count

        self._are_tpms_on_changed_callback: Optional[Callable] = None
        self._component_state_changed_callback: Optional[
            Callable
        ] = component_state_changed_callback

    def set_are_tpms_on_changed_callback(
        self: InternalSubrackSimulator,
        are_tpms_on_changed_callback: Optional[Callable] = None,
    ) -> None:
        """
        Set the callback to be called when the power mode of a TPM changes.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param are_tpms_on_changed_callback: the callback to be called
            whenever any TPM its turned off or on
        """
        self._are_tpms_on_changed_callback = are_tpms_on_changed_callback
        self._are_tpms_on_changed()

    def set_progress_changed_callback(
        self: InternalSubrackSimulator,
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Set the callback to be called when the progress value changes.

        :param component_state_changed_callback: callback to be called when the
            component command progress values changes
        """
        self._component_state_changed_callback = component_state_changed_callback

    def check_tpm_power_states(self: InternalSubrackSimulator) -> None:
        """Check TPM power states, calling the relevant callback."""
        self._are_tpms_on_changed()

    def _are_tpms_on_changed(self: InternalSubrackSimulator) -> None:
        """
        Handle a change in TPM power.

        This is a helper method that calls the callback if it exists.
        """
        tpm_power_states = [
            PowerState.ON if tpm_data["is_on"] else PowerState.OFF
            for tpm_data in self._tpm_data
        ]
        with self._tpm_data_lock:
            if self._component_state_changed_callback is not None:
                self._component_state_changed_callback(
                    {"tpm_power_states": tpm_power_states}
                )
        if self._are_tpms_on_changed_callback is not None:
            self._are_tpms_on_changed_callback(self.are_tpms_on)

    @property
    def backplane_temperatures(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the subrack backplane temperatures.

        :return: the subrack backplane temperatures
        """
        return self._backplane_temperatures

    def simulate_backplane_temperatures(
        self: InternalSubrackSimulator, backplane_temperatures: list[float]
    ) -> None:
        """
        Set the simulated backplane temperatures for this subrack simulator.

        :param backplane_temperatures: the simulated backplane
            temperature for this subrack simulator.
        """
        self._backplane_temperatures = backplane_temperatures

    @property
    def board_temperatures(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the subrack management board temperatures.

        :return: the board temperatures, in degrees celsius
        """
        return self._board_temperatures

    def simulate_board_temperatures(
        self: InternalSubrackSimulator, board_temperatures: list[float]
    ) -> None:
        """
        Set the simulated board temperatures for this subrack simulator.

        :param board_temperatures: the simulated board temperature for
            this subrack simulator.
        """
        self._board_temperatures = board_temperatures

    @property
    def board_current(self: InternalSubrackSimulator) -> float:
        """
        Return the subrack management board current.

        :return: the subrack management board current
        """
        return self._board_current

    def simulate_board_current(
        self: InternalSubrackSimulator, board_current: float
    ) -> None:
        """
        Set the simulated board current for this subrack simulator.

        :param board_current: the simulated board current for this subrack simulator.
        """
        self._board_current = board_current

    @property
    def subrack_fan_speeds(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the subrack backplane fan speeds (in RPMs).

        :return: the subrack fan speeds (RPMs)
        """
        return self._subrack_fan_speeds

    def simulate_subrack_fan_speeds(
        self: InternalSubrackSimulator, subrack_fan_speeds: list[float]
    ) -> None:
        """
        Set the simulated fan speed for this subrack simulator.

        :param subrack_fan_speeds: the simulated fan speed for this subrack simulator.
        """
        self._subrack_fan_speeds = subrack_fan_speeds

    @property
    def subrack_fan_speeds_percent(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the subrack backplane fan speeds in percent.

        :return: the fan speed, in percent
        """
        return [
            speed * 100.0 / SubrackData.MAX_SUBRACK_FAN_SPEED
            for speed in self._subrack_fan_speeds
        ]

    @property
    def subrack_fan_modes(self: InternalSubrackSimulator) -> list[FanMode]:
        """
        Return the subrack fan Mode.

        :return: subrack fan mode AUTO or  MANUAL
        """
        return self._subrack_fan_modes

    @property
    def bay_count(self: InternalSubrackSimulator) -> int:
        """
        Return the number of TPM bays housed in this subrack.

        :return: the number of TPM bays housed in this subrack
        """
        return self._bay_count

    @property
    def tpm_count(self: InternalSubrackSimulator) -> int:
        """
        Return the number of TPMs housed in this subrack.

        :return: the number of TPMs housed in this subrack
        """
        return self._tpm_present.count(True)

    def _check_tpm_id(self: InternalSubrackSimulator, logical_tpm_id: int) -> None:
        """
        Check that a TPM id passed as an argument is within range.

        :param logical_tpm_id: the id to check

        :raises ValueError: if the tpm id is out of range for this
            subrack or the TPM is not installed
        """
        if logical_tpm_id < 1 or logical_tpm_id > self.bay_count:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; "
                f"this subrack has {self.bay_count} TPM bays."
            )
        if not self._tpm_present[logical_tpm_id - 1]:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; TPM not present in this bay"
            )

    @property
    def tpm_temperatures(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        """
        with self._tpm_data_lock:
            return [tpm_data["temperature"] for tpm_data in self._tpm_data]

    def simulate_tpm_temperatures(
        self: InternalSubrackSimulator, tpm_temperatures: list[float]
    ) -> None:
        """
        Set the simulated temperatures for all TPMs housed in this subrack simulator.

        :param tpm_temperatures: the simulated TPM temperatures.

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_temperatures) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._tpm_data_lock:
            for (tpm_data, temperature) in zip(self._tpm_data, tpm_temperatures):
                tpm_data["temperature"] = temperature

    @property
    def tpm_currents(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the currents of the TPMs housed in this subrack.

        :return: the currents of the TPMs housed in this subrack
        """
        with self._tpm_data_lock:
            return [tpm_data["current"] for tpm_data in self._tpm_data]

    def simulate_tpm_currents(
        self: InternalSubrackSimulator, tpm_currents: list[float]
    ) -> None:
        """
        Set the simulated currents for all TPMs housed in this subrack simulator.

        :param tpm_currents: the simulated TPM currents.

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_currents) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._tpm_data_lock:
            for (tpm_data, current) in zip(self._tpm_data, tpm_currents):
                tpm_data["simulate_current"] = current

    @property
    def tpm_powers(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the powers of the TPMs housed in this subrack.

        :return: the powers of the TPMs housed in this subrack
        """
        with self._tpm_data_lock:
            return [tpm_data["power"] for tpm_data in self._tpm_data]

    def simulate_tpm_powers(
        self: InternalSubrackSimulator, tpm_powers: list[float]
    ) -> None:
        """
        Set the simulated powers for all TPMs housed in this subrack simulator.

        :param tpm_powers: the simulated TPM currents.

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_powers) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._tpm_data_lock:
            for (tpm_data, power) in zip(self._tpm_data, tpm_powers):
                tpm_data["power"] = power

    @property
    def tpm_voltages(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the voltages of theControl TPMs housed in this subrack.

        :return: the voltages of the TPMs housed in this subrack
        """
        with self._tpm_data_lock:
            return [tpm_data["voltage"] for tpm_data in self._tpm_data]

    def simulate_tpm_voltages(
        self: InternalSubrackSimulator, tpm_voltages: list[float]
    ) -> None:
        """
        Set the simulated voltages for all TPMs housed in this subrack simulator.

        :param tpm_voltages: the simulated TPM currents.

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_voltages) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._tpm_data_lock:
            for (tpm_data, voltage) in zip(self._tpm_data, tpm_voltages):
                tpm_data["voltage"] = voltage

    @property
    def power_supply_fan_speeds(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the power supply fan speeds for this subrack.

        :return: the power supply fan speed
        """
        return self._power_supply_fan_speeds

    def simulate_power_supply_fan_speeds(
        self: InternalSubrackSimulator, power_supply_fan_speeds: list[float]
    ) -> None:
        """
        Set the power supply fan_speeds for this subrack.

        :param power_supply_fan_speeds: the simulated  power supply fan_speeds
        """
        self._power_supply_fan_speeds = power_supply_fan_speeds

    @property
    def power_supply_currents(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the power supply currents for this subrack.

        :return: the power supply current
        """
        return self._power_supply_currents

    def simulate_power_supply_currents(
        self: InternalSubrackSimulator, power_supply_currents: list[float]
    ) -> None:
        """
        Set the power supply current for this subrack.

        :param power_supply_currents: the simulated  power supply current
        """
        self._power_supply_currents = power_supply_currents

    @property
    def power_supply_powers(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the power supply power for this subrack.

        :return: the power supply power
        """
        return [
            i * v
            for i, v in zip(self._power_supply_currents, self._power_supply_voltages)
        ]

    def simulate_power_supply_powers(
        self: InternalSubrackSimulator, power_supply_powers: list[float]
    ) -> None:
        """
        Set the power supply power for this subrack.

        :param power_supply_powers: the simulated  power supply power
        """
        self._power_supply_currents = [
            power_supply_powers[i] / self._power_supply_voltages[i]
            for i in range(len(self._power_supply_currents))
        ]

    @property
    def power_supply_voltages(self: InternalSubrackSimulator) -> list[float]:
        """
        Return the power supply voltages for this subrack.

        :return: the power supply voltages
        """
        return self._power_supply_voltages

    def simulate_power_supply_voltages(
        self: InternalSubrackSimulator, power_supply_voltages: list[float]
    ) -> None:
        """
        Set the power supply voltage for this subrack.

        :param power_supply_voltages: the simulated  power supply voltage
        """
        self._power_supply_voltages = power_supply_voltages

    @property
    def tpm_present(self: InternalSubrackSimulator) -> list[bool]:
        """
        Return the tpm detected in the subrack.

        :return: list of tpm detected
        """
        return self._tpm_present

    @property
    def tpm_supply_fault(self: InternalSubrackSimulator) -> list[int]:
        """
        Return info about about TPM supply fault status.

        :return: the TPM supply fault status
        """
        return self._tpm_supply_fault

    def is_tpm_on(
        self: InternalSubrackSimulator, logical_tpm_id: int
    ) -> Optional[bool]:
        """
        Return whether a specified TPM is turned on.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be checked

        :return: whether the TPM is on, or None if the subrack itself
            is off
        """
        self._check_tpm_id(logical_tpm_id)
        with self._tpm_data_lock:
            return self._tpm_data[logical_tpm_id - 1]["is_on"]

    @property
    def are_tpms_on(self: InternalSubrackSimulator) -> list[bool]:
        """
        Return whether each TPM is on.

        :return: whether each TPM is on
        """
        return [tpm_data["is_on"] for tpm_data in self._tpm_data]

    def turn_off_tpm(
        self: InternalSubrackSimulator, logical_tpm_id: int
    ) -> bool | None:
        """
        Turn off a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off

        :return: whether successful, or None if there was nothing to do
        """
        self._check_tpm_id(logical_tpm_id)
        with self._tpm_data_lock:
            tpm_data = self._tpm_data[logical_tpm_id - 1]
            if tpm_data["is_on"]:
                tpm_data["is_on"] = False
                self._are_tpms_on_changed()
                return True
            return None

    def _emulate_hardware_delay(self: InternalSubrackSimulator) -> None:
        """
        Specialist implementation to emulate a real hardware delay.

        To be used specifically in a K8s deployment i.e. TestMode.NONE.
        """
        # Safeguard against deployment in unit testing environment
        if "PYTEST_CURRENT_TEST" in os.environ:
            return

        for i in range(1, 5):
            if self._component_state_changed_callback:
                self._component_state_changed_callback({"progress": (i * 20)})
            sleep(1.0)

    def turn_on_tpm(self: InternalSubrackSimulator, logical_tpm_id: int) -> bool | None:
        """
        Turn on a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned on

        :return: whether successful, or None if there was nothing to do
        """
        self._check_tpm_id(logical_tpm_id)
        with self._tpm_data_lock:
            tpm_data = self._tpm_data[logical_tpm_id - 1]
            if not tpm_data["is_on"]:
                if self._component_state_changed_callback:
                    self._component_state_changed_callback({"progress": 0})
                    self._emulate_hardware_delay()  # TODO: we're still holding the lock
                    self._component_state_changed_callback({"progress": 100})
                tpm_data["is_on"] = True
                self._are_tpms_on_changed()
                return True
            return None

    def turn_on_tpms(self: InternalSubrackSimulator) -> bool | None:
        """
        Turn on all TPMs that are present in the subrack.

        :return: whether successful, or None if there was nothing to do
        """
        changed = False
        with self._tpm_data_lock:
            for (tpm_data, present) in zip(self._tpm_data, self._tpm_present):
                if present and not tpm_data["is_on"]:
                    tpm_data["is_on"] = True
                    changed = True
            if changed:
                self._are_tpms_on_changed()
                return True
            return None

    def turn_off_tpms(self: InternalSubrackSimulator) -> bool | None:
        """
        Turn off all TPMs.

        :return: whether successful, or None if there was nothing to do
        """
        changed = False
        with self._tpm_data_lock:
            for (tpm_data, present) in zip(self._tpm_data, self._tpm_present):
                if present and tpm_data["is_on"]:
                    tpm_data["is_on"] = False
                    changed = True
            if changed:
                self._are_tpms_on_changed()
                return True
            return None

    def set_subrack_fan_speed(
        self: InternalSubrackSimulator, fan_id: int, speed_percent: float
    ) -> None:
        """
        Set the subrack backplane fan speed in percent.

        :param fan_id: id of the selected fan accepted value: 1-4
        :param speed_percent: percentage value of fan RPM  (MIN 0=0% - MAX 100=100%)
        """
        self._subrack_fan_speeds[fan_id - 1] = (
            speed_percent / 100.0 * SubrackData.MAX_SUBRACK_FAN_SPEED
        )

    def set_subrack_fan_modes(
        self: InternalSubrackSimulator, fan_id: int, mode: FanMode
    ) -> None:
        """
        Set Fan Operational Mode for the subrack's fan.

        :param fan_id: id of the selected fan accepted value: 1-4
        :param mode: AUTO or MANUAL
        """
        self.subrack_fan_modes[fan_id - 1] = mode

    def set_power_supply_fan_speed(
        self: InternalSubrackSimulator, power_supply_fan_id: int, speed_percent: float
    ) -> None:
        """
        Set the power supply  fan speed.

        :param power_supply_fan_id: power supply id from 0 to 2
        :param speed_percent: fan speed in percent
        """
        self._power_supply_fan_speeds[power_supply_fan_id - 1] = speed_percent
