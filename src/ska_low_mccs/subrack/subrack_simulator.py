# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

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
from __future__ import annotations

from typing import Any, Callable, Optional

from ska_tango_base.control_model import PowerMode
from ska_low_mccs.component import ControlMode, ObjectComponent


__all__ = ["SubrackSimulator"]


class SubrackSimulator(ObjectComponent):
    """A simulator of a subrack management board."""

    DEFAULT_TPM_TEMPERATURE = 40.0
    """The default temperature for a module contained in a subrack bay."""

    DEFAULT_TPM_CURRENT = 0.4
    """The default current for a module contained in a subrack bay"""

    DEFAULT_TPM_VOLTAGE = 12.0
    """The default voltage for a module contained in a subrack bay."""

    DEFAULT_TPM_POWER = DEFAULT_TPM_CURRENT * DEFAULT_TPM_VOLTAGE
    """The default power for a module contained in a subrack bay."""

    DEFAULT_BACKPLANE_TEMPERATURE = [38.0, 39.0]
    """The default temperature for the subrack backplane."""

    DEFAULT_BOARD_TEMPERATURE = [39.0, 40.0]
    """The default temperature for the subrack management board."""

    DEFAULT_BOARD_CURRENT = 1.1
    """The default current for the subrack management board."""

    DEFAULT_SUBRACK_FAN_SPEEDS = [4999.0, 5000.0, 5001.0, 5002.0]
    """
    The default fan speeds for the subrack.

    This can be overruled using the set_subrack_fan_speed method.
    """

    MAX_SUBRACK_FAN_SPEED = 8000.0
    """The maximum fan speed for the subrack."""

    DEFAULT_SUBRACK_FAN_MODE = [ControlMode.AUTO] * 4
    """
    The default fan mode for the subrack.

    This can be overruled using the set_fan_mode method.
    """

    DEFAULT_TPM_POWER_MODES = [PowerMode.OFF] * 8
    """The default on/off status of the housed TPMs."""

    DEFAULT_TPM_PRESENT = [True] * 8
    """Whether each TPM is present in the subrack by default."""

    DEFAULT_POWER_SUPPLY_POWER = [50.0, 70.0]
    """The default power supply power."""

    DEFAULT_POWER_SUPPLY_VOLTAGE = [12.0, 12.1]
    """The default power supply voltage."""

    DEFAULT_POWER_SUPPLY_CURRENT = [50.0 / 12.0, 70.0 / 12.1]
    """The default power supply current."""

    DEFAULT_POWER_SUPPLY_FAN_SPEEDS = [90.0, 100.0]
    """The default power supply fan speeds."""

    def __init__(
        self,
        backplane_temperatures=DEFAULT_BACKPLANE_TEMPERATURE,
        board_temperatures=DEFAULT_BOARD_TEMPERATURE,
        board_current=DEFAULT_BOARD_CURRENT,
        subrack_fan_speeds=DEFAULT_SUBRACK_FAN_SPEEDS,
        subrack_fan_mode: ControlMode = DEFAULT_SUBRACK_FAN_MODE,
        power_supply_currents=DEFAULT_POWER_SUPPLY_CURRENT,
        power_supply_voltages=DEFAULT_POWER_SUPPLY_VOLTAGE,
        power_supply_fan_speeds=DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
        tpm_power_modes: list[PowerMode] = DEFAULT_TPM_POWER_MODES,
        tpm_present=DEFAULT_TPM_PRESENT,
        _tpm_data: Optional[list[dict[str, Any]]] = None,
    ):
        """
        Initialise a new instance.

        :param backplane_temperatures: the initial temperature of the subrack
            backplane from sensor 1 and 2
        :type backplane_temperatures: list(float)
        :param board_temperatures: the initial temperature of the subrack management
            board from sensor 1 and 2
        :type board_temperatures: list(float)
        :param board_current: the initial current of the subrack management board
        :type board_current: float
        :param subrack_fan_speeds: the initial fan_speeds of the subrack backplane
            management board
        :type subrack_fan_speeds: list(float)
        :param subrack_fan_mode: the initial fan mode of the subrack backplane
        :param power_supply_currents: the initial currents for the 2 power supply in the
            subrack
        :type power_supply_currents: list(float)
        :param power_supply_voltages: the initial voltages for the 2 power supply in the
            subrack
        :type power_supply_voltages: list(float)
        :param: power_supply_fan_speeds: the initial fan speeds in percent for the 2
            power supply in the subrack
        :type power_supply_fan_speeds: list(float)
        :param tpm_power_modes: the initial power modes of the TPMs
        :param tpm_present: the initial TPM board present on subrack
        :type tpm_present: list(bool)
        :param _tpm_data: optional list of subrack bay simulators to be
            used. This is for testing purposes only, allowing us to
            inject our own bays instead of letting this simulator create
            them.
        """
        self._backplane_temperatures = backplane_temperatures
        self._board_temperatures = board_temperatures
        self._board_current = board_current
        self._subrack_fan_speeds = subrack_fan_speeds
        self._subrack_fan_mode = subrack_fan_mode
        self._power_supply_currents = power_supply_currents
        self._power_supply_voltages = power_supply_voltages
        self._power_supply_fan_speeds = power_supply_fan_speeds

        self._tpm_data = _tpm_data or [
            {
                "power_mode": tpm_power_modes[i],
                "voltage": self.DEFAULT_TPM_VOLTAGE,
                "current": self.DEFAULT_TPM_CURRENT,
                "temperature": self.DEFAULT_TPM_TEMPERATURE,
                "power": self.DEFAULT_TPM_POWER,
            }
            for i in range(len(tpm_power_modes))
        ]

        self._bay_count = len(self._tpm_data)
        self._tpm_present = tpm_present[0 : self._bay_count]
        self._tpm_supply_fault = [0] * self._bay_count

        self._tpm_power_changed_callback: Optional[Callable[[list[bool]], None]] = None

    def set_tpm_power_changed_callback(
        self: SubrackSimulator,
        tpm_power_changed_callback: Callable[[list[bool], None]],
    ) -> None:
        """
        Set the callback to be called when the power mode of a TPM changes.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param tpm_power_changed_callback: the callback to be called
            when the power mode of an antenna changes
        """
        self._tpm_power_changed_callback = tpm_power_changed_callback
        self._tpm_power_changed()

    def _tpm_power_changed(self: SubrackSimulator) -> None:
        """
        Handle a change in TPM power.

        This is a helper method that calls the callback if it exists.
        """
        if self._tpm_power_changed_callback is not None:
            self._tpm_power_changed_callback(self.are_tpms_on())

    @property
    def backplane_temperatures(self):
        """
        Return the subrack backplane temperatures.

        :return: the subrack backplane temperatures
        :rtype: list(float)
        """
        return self._backplane_temperatures

    def simulate_backplane_temperatures(self, backplane_temperatures):
        """
        Set the simulated backplane temperatures for this subrack simulator.

        :param backplane_temperatures: the simulated backplane
            temperature for this subrack simulator.

        :type backplane_temperatures: list(float)
        """
        self._backplane_temperatures = backplane_temperatures

    @property
    def board_temperatures(self):
        """
        Return the subrack management board temperatures.

        :return: the board temperatures, in degrees celsius
        :rtype: list(float)
        """
        return self._board_temperatures

    def simulate_board_temperatures(self, board_temperatures):
        """
        Set the simulated board temperatures for this subrack simulator.

        :param board_temperatures: the simulated board temperature for
            this subrack simulator.

        :type board_temperatures: list(float)
        """
        self._board_temperatures = board_temperatures

    @property
    def board_current(self):
        """
        Return the subrack management board current.

        :return: the subrack management board current
        :rtype: float
        """
        return self._board_current

    def simulate_board_current(self, board_current):
        """
        Set the simulated board current for this subrack simulator.

        :param board_current: the simulated board current for this subrack simulator.
        :type board_current: float
        """
        self._board_current = board_current

    @property
    def subrack_fan_speeds(self):
        """
        Return the subrack backplane fan speeds (in RPMs).

        :return: the subrack fan speeds (RPMs)
        :rtype: list(float)
        """
        return self._subrack_fan_speeds

    def simulate_subrack_fan_speeds(self, subrack_fan_speeds):
        """
        Set the simulated fan speed for this subrack simulator.

        :param subrack_fan_speeds: the simulated fan speed for this subrack simulator.
        :type subrack_fan_speeds: list(float)
        """
        self._subrack_fan_speeds = subrack_fan_speeds

    @property
    def subrack_fan_speeds_percent(self):
        """
        Return the subrack backplane fan speeds in percent.

        :return: the fan speed, in percent
        :rtype: list(float)
        """
        return [
            speed * 100.0 / SubrackSimulator.MAX_SUBRACK_FAN_SPEED
            for speed in self._subrack_fan_speeds
        ]

    @property
    def subrack_fan_mode(self) -> ControlMode:
        """
        Return the subrack fan Mode.

        :return: subrack fan mode AUTO or  MANUAL
        """
        return self._subrack_fan_mode

    @property
    def bay_count(self):
        """
        Return the number of TPM bays housed in this subrack.

        :return: the number of TPM bays housed in this subrack
        :rtype: int
        """
        return self._bay_count

    @property
    def tpm_count(self):
        """
        Return the number of TPMs housed in this subrack.

        :return: the number of TPMs housed in this subrack
        :rtype: int
        """
        return self._tpm_present.count(True)

    def _check_tpm_id(self, logical_tpm_id):
        """
        Helper method to check that a TPM id passed as an argument is within range.

        :param logical_tpm_id: the id to check
        :type logical_tpm_id: int

        :raises ValueError: if the tpm id is out of range for this
            subrack or the TPM is not installed
        """
        if logical_tpm_id < 1 or logical_tpm_id > self.bay_count:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; "
                f"this subrack has {self.bay_count} TPM bays."
            )
        if self._tpm_present[logical_tpm_id - 1] is False:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; TPM not present in this bay"
            )

    @property
    def tpm_temperatures(self):
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        :rtype: list(float)
        """
        return [tpm_data["temperature"] for tpm_data in self._tpm_data]

    def simulate_tpm_temperatures(self, tpm_temperatures):
        """
        Set the simulated temperatures for all TPMs housed in this subrack simulator.

        :param tpm_temperatures: the simulated TPM temperatures.
        :type tpm_temperatures: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_temperatures) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        for (tpm_data, temperature) in zip(self._tpm_data, tpm_temperatures):
            tpm_data["temperature"] = temperature

    @property
    def tpm_currents(self):
        """
        Return the currents of the TPMs housed in this subrack.

        :return: the currents of the TPMs housed in this subrack
        :rtype: list(float)
        """
        return [tpm_data["current"] for tpm_data in self._tpm_data]

    def simulate_tpm_currents(self, tpm_currents):
        """
        Set the simulated currents for all TPMs housed in this subrack simulator.

        :param tpm_currents: the simulated TPM currents.
        :type tpm_currents: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_currents) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        for (tpm_data, current) in zip(self._tpm_data, tpm_currents):
            tpm_data["simulate_current"] = current

    @property
    def tpm_powers(self):
        """
        Return the powers of the TPMs housed in this subrack.

        :return: the powers of the TPMs housed in this subrack
        :rtype: list(float)
        """
        return [tpm_data["power"] for tpm_data in self._tpm_data]

    def simulate_tpm_powers(self, tpm_powers):
        """
        Set the simulated powers for all TPMs housed in this subrack simulator.

        :param tpm_powers: the simulated TPM currents.
        :type tpm_powers: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_powers) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        for (tpm_data, power) in zip(self._tpm_data, tpm_powers):
            tpm_data["power"] = power

    @property
    def tpm_voltages(self):
        """
        Return the voltages of the TPMs housed in this subrack.

        :return: the voltages of the TPMs housed in this subrack
        :rtype: list(float)
        """
        return [tpm_data["voltage"] for tpm_data in self._tpm_data]

    def simulate_tpm_voltages(self, tpm_voltages):
        """
        Set the simulated voltages for all TPMs housed in this subrack simulator.

        :param tpm_voltages: the simulated TPM currents.
        :type tpm_voltages: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_voltages) != self.bay_count:
            raise ValueError("Argument does not match number of TPMs")

        for (tpm_data, voltage) in zip(self._tpm_data, tpm_voltages):
            tpm_data["voltage"] = voltage

    @property
    def power_supply_fan_speeds(self):
        """
        Return the power supply fan speeds for this subrack.

        :return: the power supply fan speed
        :rtype: list(float)
        """
        return self._power_supply_fan_speeds

    def simulate_power_supply_fan_speeds(self, power_supply_fan_speeds):
        """
        Set the power supply fan_speeds for this subrack.

        :param power_supply_fan_speeds: the simulated  power supply fan_speeds
        :type power_supply_fan_speeds: list(float)
        """
        self._power_supply_fan_speeds = power_supply_fan_speeds

    @property
    def power_supply_currents(self):
        """
        Return the power supply currents for this subrack.

        :return: the power supply current
        :rtype: list(float)
        """
        return self._power_supply_currents

    def simulate_power_supply_currents(self, power_supply_currents):
        """
        Set the power supply current for this subrack.

        :param power_supply_currents: the simulated  power supply current
        :type power_supply_currents: list(float)
        """
        self._power_supply_currents = power_supply_currents

    @property
    def power_supply_powers(self):
        """
        Return the power supply power for this subrack.

        :return: the power supply power
        :rtype: list(float)
        """
        powers = [
            self._power_supply_currents[i] * self._power_supply_voltages[i]
            for i in range(len(self._power_supply_currents))
        ]
        return powers

    def simulate_power_supply_powers(self, power_supply_powers):
        """
        Set the power supply power for this subrack.

        :param power_supply_powers: the simulated  power supply power
        :type power_supply_powers: list(float)
        """
        self._power_supply_currents = [
            power_supply_powers[i] / self._power_supply_voltages[i]
            for i in range(len(self._power_supply_currents))
        ]

    @property
    def power_supply_voltages(self):
        """
        Return the power supply voltages for this subrack.

        :return: the power supply voltages
        :rtype: list(float)
        """
        return self._power_supply_voltages

    def simulate_power_supply_voltages(self, power_supply_voltages):
        """
        Set the power supply voltage for this subrack.

        :param power_supply_voltages: the simulated  power supply voltage
        :type power_supply_voltages: list(float)
        """
        self._power_supply_voltages = power_supply_voltages

    @property
    def tpm_present(self):
        """
        Return the tpm detected in the subrack.

        :return: list of tpm detected
        :rtype: list(bool)
        """
        return self._tpm_present

    @property
    def tpm_supply_fault(self):
        """
        Return info about about TPM supply fault status.

        :return: the TPM supply fault status
        :rtype: list(int)
        """
        return self._tpm_supply_fault

    def is_tpm_on(self, logical_tpm_id):
        """
        Return whether a specified TPM is turned on.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be checked
        :type logical_tpm_id: int

        :return: whether the TPM is on, or None if the subrack itself
            is off
        :rtype: bool or None
        """
        self._check_tpm_id(logical_tpm_id)
        return self._tpm_data[logical_tpm_id - 1]["power_mode"] == PowerMode.ON

    def are_tpms_on(self):
        """
        Returns whether each TPM is powered or not. Or None if the subrack itself is
        turned off.

        :return: whether each TPM is powered or not.
        :rtype: list(bool) or None
        """
        return [tpm_data["power_mode"] == PowerMode.ON for tpm_data in self._tpm_data]

    def turn_off_tpm(self, logical_tpm_id):
        """
        Turn off a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off
        :type logical_tpm_id: int
        :return: whether successful, or None if there was nothing to do
        """
        self._check_tpm_id(logical_tpm_id)
        tpm_data = self._tpm_data[logical_tpm_id - 1]
        if tpm_data["power_mode"] == PowerMode.ON:
            tpm_data["power_mode"] = PowerMode.OFF
            self._tpm_power_changed()
            return True
        return None

    def turn_on_tpm(self, logical_tpm_id):
        """
        Turn on a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned on
        :type logical_tpm_id: int

        :return: whether successful, or None if there was nothing to do
        """
        self._check_tpm_id(logical_tpm_id)
        tpm_data = self._tpm_data[logical_tpm_id - 1]
        if tpm_data["power_mode"] == PowerMode.OFF:
            tpm_data["power_mode"] = PowerMode.ON
            self._tpm_power_changed()
            return True
        return None

    def turn_on_tpms(self):
        """
        Turn on all TPMs that are present in the subrack.

        :return: whether successful, or None if there was nothing to do
        """
        changed = False
        for (tpm_data, present) in zip(self._tpm_data, self._tpm_present):
            if present and tpm_data["power_mode"] == PowerMode.OFF:
                tpm_data["power_mode"] = PowerMode.ON
                changed = True
        if changed:
            self._tpm_power_changed()
            return True
        return None

    def turn_off_tpms(self):
        """
        Turn off all TPMs.

        :return: whether successful, or None if there was nothing to do
        """
        changed = False
        for (tpm_data, present) in zip(self._tpm_data, self._tpm_present):
            if present and tpm_data["power_mode"] == PowerMode.ON:
                tpm_data["power_mode"] = PowerMode.OFF
                changed = True
        if changed:
            self._tpm_power_changed()
            return True
        return None

    def set_subrack_fan_speed(self, fan_id, speed_percent):
        """
        Set the subrack backplane fan speed in percent.

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param speed_percent: percentage value of fan RPM  (MIN 0=0% - MAX 100=100%)
        :type speed_percent: float
        """
        self._subrack_fan_speeds[fan_id - 1] = (
            speed_percent / 100.0 * SubrackSimulator.MAX_SUBRACK_FAN_SPEED
        )

    def set_subrack_fan_mode(self, fan_id, mode: ControlMode):
        """
        Set Fan Operational Mode for the subrack's fan.

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param mode: AUTO or MANUAL
        """
        self.subrack_fan_mode[fan_id - 1] = mode

    def set_power_supply_fan_speed(self, power_supply_fan_id, speed_percent):
        """
        Set the power supply  fan speed.

        :param power_supply_fan_id: power supply id from 0 to 2
        :type power_supply_fan_id: int
        :param speed_percent: fan speed in percent
        :type speed_percent: float
        """
        self._power_supply_fan_speeds[power_supply_fan_id - 1] = speed_percent
