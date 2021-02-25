# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of a simulator for a subrack
management board.

Some assumptions of this class are:

* For now, the subrack management board can manage its own power mode.
  i.e. it can turn itself off and on. Really, there would be an upstream
  cabinet management board that turns subracks off and on. But we don't
  have a cabinet device yet, so for now we leave this in control of the
  subrack management board.
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

These assumptions are unconfirmed and may need to change in future.
"""

from threading import Lock
from ska.low.mccs.hardware import OnOffHardwareSimulator, PowerMode

__all__ = ["SubrackBaySimulator", "SubrackBoardSimulator"]


class SubrackBaySimulator(OnOffHardwareSimulator):
    """
    A generic simulator for a subrack bay that contains and supplies
    power to some electronic module, such as a TPM. From the subrack's
    point of view, it mostly doesn't care what that module is, so long
    as it can turn it off and on, and monitor its vital signs.

    It is assumed that the bay itself has sensors for temperature and
    current; i.e. it can monitor the temperature and current of the
    equipment without talking to that equipment, and even when it is
    turned off.
    """

    DEFAULT_TEMPERATURE = 40.0
    """
    The default initial simulated temperature for the module contained
    in this subrack bay; this can be overruled in the constructor
    """

    DEFAULT_CURRENT = 0.4
    """
    The default initial simulated current for the module contained in
    this subrack bay; this can be overruled in the constructor
    """

    def __init__(
        self,
        temperature=DEFAULT_TEMPERATURE,
        current=DEFAULT_CURRENT,
        fail_connect=False,
        power_mode=PowerMode.OFF,
    ):
        """
        Initialise a new instance.

        :param temperature: the initial temperature of this module (in celcius)
        :type temperature: float
        :param current: the initial current of this module (in amps)
        :type current: float
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        :param power_mode: the initial power mode of this module
        :type power_mode: :py:class:`ska.low.mccs.hardware.PowerMode`
        """
        self._temperature = temperature
        self._current_when_on = current

        super().__init__(fail_connect=fail_connect, power_mode=power_mode)

    @property
    def temperature(self):
        """
        Return this module's temperature.

        :return: this module's temperature.
        :rtype: float
        """
        return self._temperature

    def simulate_temperature(self, temperature):
        """
        Set the simulated temperature of this module.

        :param temperature: the simulated temperature of this module
        :type temperature: float
        """
        self._temperature = temperature

    @property
    def current(self):
        """
        Return this module's current.

        :return: this module's current.
        :rtype: float
        """
        return self._current_when_on if self.power_mode == PowerMode.ON else 0.0

    def simulate_current(self, current):
        """
        Set the simulated current of this module.

        :param current: the simulated current of this module
        :type current: float
        """
        self._current_when_on = current


class SubrackBoardSimulator(OnOffHardwareSimulator):
    """
    A simulator of a subrack management board.

    :todo: for now we assume that the subrack management board can turn
        itself off and on. Actually, this would be done via the SPS
        cabinet. Once we have an SPS cabinet simulator, we should fix
        this.
    """

    DEFAULT_BACKPLANE_TEMPERATURE = 38.0
    """
    The default initial simulated temperature for the subrack backplane;
    this can be overruled in the constructor
    """

    DEFAULT_BOARD_TEMPERATURE = 39.0
    """
    The default initial simulated temperature for the subrack management
    board itself; this can be overruled in the constructor
    """

    DEFAULT_BOARD_CURRENT = 1.1
    """
    The default initial simulated current for the subrack management
    board itself; this can be overruled in the constructor
    """

    DEFAULT_FAN_SPEED = 4999.0
    """
    The default initial simulated fan speed for the subrack; this can be
    overruled in the constructor
    """

    def __init__(
        self,
        tpm_count,
        backplane_temperature=DEFAULT_BACKPLANE_TEMPERATURE,
        board_temperature=DEFAULT_BOARD_TEMPERATURE,
        board_current=DEFAULT_BOARD_CURRENT,
        fan_speed=DEFAULT_FAN_SPEED,
        fail_connect=False,
        power_mode=PowerMode.OFF,
        _bays=None,
    ):
        """
        Initialise a new instance.

        :param tpm_count: number of TPMs that are attached to
            this subrack simulator
        :type tpm_count: int
        :param backplane_temperature: the initial temperature of the
            subrack backplane
        :type backplane_temperature: float
        :param board_temperature: the initial temperature of the subrack
            management board
        :type board_temperature: float
        :param board_current: the initial current of the subrack
            management board
        :type board_current: float
        :param fan_speed: the initial fan_speed of the subrack
            management board
        :type fan_speed: float
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        :param power_mode: the initial power_mode of the simulated
            hardware. For example, if the initial mode is ON, then
            this simulator will simulate connecting to hardware and
            finding it to be already powered on.
        :type power_mode: :py:class:`~ska.low.mccs.hardware.PowerMode`
        :param _bays: optional list of subrack bay simulators to be
            used. This is for testing purposes only, allowing us to
            inject our own bays instead of letting this simulator create
            them.
        :type _bays: list(:py:class:`.SubrackBaySimulator`)
        """
        self._backplane_temperature = backplane_temperature
        self._board_temperature = board_temperature
        self._board_current = board_current
        self._fan_speed = fan_speed

        self._bays = _bays or [SubrackBaySimulator() for i in range(tpm_count)]
        self._bay_lock = Lock()

        super().__init__(fail_connect=fail_connect, power_mode=power_mode)

    def off(self):
        """
        Turn me off.

        :todo: for now we assume that the subrack management board can
            turn itself off and on. Actually, this would be done via the
            SPS cabinet. Once we have an SPS cabinet simulator, we
            should delete this method.
        """
        super().off()

        # If we turn the subrack off, any housed equipment will lose power
        with self._bay_lock:
            for module in self._bays:
                module.off()

    def on(self):
        """
        Turn me on.

        :todo: for now we assume that the subrack management board can
            turn itself off and on. Actually, this would be done via the
            SPS cabinet. Once we have an SPS cabinet simulator, we
            should delete this method.
        """
        super().on()

    @property
    def backplane_temperature(self):
        """
        Return the subrack backplane temperature.

        :return: the subrack backplane temperature
        :rtype: float
        """
        self.check_power_mode(PowerMode.ON)
        return self._backplane_temperature

    def simulate_backplane_temperature(self, backplane_temperature):
        """
        Set the simulated backplane temperature for this subrack
        simulator.

        :param backplane_temperature: the simulated backplane
            temperature for this subrack simulator.
        :type backplane_temperature: float
        """
        self._backplane_temperature = backplane_temperature

    @property
    def board_temperature(self):
        """
        Return the subrack management board temperature.

        :return: the subrack management board temperature
        :rtype: float
        """
        self.check_power_mode(PowerMode.ON)
        return self._board_temperature

    def simulate_board_temperature(self, board_temperature):
        """
        Set the simulated board temperature for this subrack simulator.

        :param board_temperature: the simulated board temperature for
            this subrack simulator.
        :type board_temperature: float
        """
        self._board_temperature = board_temperature

    @property
    def board_current(self):
        """
        Return the subrack management board current.

        :return: the subrack management board current
        :rtype: float
        """
        self.check_power_mode(PowerMode.ON)
        return self._board_current

    def simulate_board_current(self, board_current):
        """
        Set the simulated board current for this subrack simulator.

        :param board_current: the simulated board current for this subrack simulator.
        :type board_current: float
        """
        self._board_current = board_current

    @property
    def fan_speed(self):
        """
        Return the subrack fan speed (in RPMs).

        :return: the subrack fan speed (RPMs)
        :rtype: float
        """
        self.check_power_mode(PowerMode.ON)
        return self._fan_speed

    def simulate_fan_speed(self, fan_speed):
        """
        Set the simulated fan speed for this subrack simulator.

        :param fan_speed: the simulated fan speed for this subrack simulator.
        :type fan_speed: float
        """
        self._fan_speed = fan_speed

    @property
    def tpm_count(self):
        """
        Return the number of TPMs housed in this subrack.

        :return: the number of TPMs housed in this subrack
        :rtype: int
        """
        return len(self._bays)

    def _check_tpm_id(self, logical_tpm_id):
        """
        Helper method to check that a TPM id passed as an argument is
        within range.

        :param logical_tpm_id: the id to check
        :type logical_tpm_id: int

        :raises ValueError: if the tpm id is out of range for this
            subrack
        """
        if logical_tpm_id < 1 or logical_tpm_id > self.tpm_count:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; "
                f"this subrack has {self.tpm_count} antennas."
            )

    @property
    def tpm_temperatures(self):
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        :rtype: list(float)
        """
        self.check_power_mode(PowerMode.ON)
        with self._bay_lock:
            return [bay.temperature for bay in self._bays]

    def simulate_tpm_temperatures(self, tpm_temperatures):
        """
        Set the simulated temperatures for all TPMs housed in this
        subrack simulator.

        :param tpm_temperatures: the simulated TPM temperatures.
        :type tpm_temperatures: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_temperatures) != self.tpm_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._bay_lock:
            for (bay, temperature) in zip(self._bays, tpm_temperatures):
                bay.simulate_temperature(temperature)

    @property
    def tpm_currents(self):
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        :rtype: list(float)
        """
        self.check_power_mode(PowerMode.ON)
        with self._bay_lock:
            return [bay.current for bay in self._bays]

    def simulate_tpm_currents(self, tpm_currents):
        """
        Set the simulated currents for all TPMs housed in this subrack
        simulator.

        :param tpm_currents: the simulated TPM currents.
        :type tpm_currents: list(float)

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_currents) != self.tpm_count:
            raise ValueError("Argument does not match number of TPMs")

        with self._bay_lock:
            for (bay, current) in zip(self._bays, tpm_currents):
                bay.simulate_current(current)

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
        if self.power_mode != PowerMode.ON:
            return None
        with self._bay_lock:
            return self._bays[logical_tpm_id - 1].power_mode == PowerMode.ON

    def are_tpms_on(self):
        """
        Returns whether each TPM is powered or not. Or None if the
        subrack itself is turned off.

        :return: whether each TPM is powered or not.
        :rtype: list(bool) or None
        """
        if self.power_mode != PowerMode.ON:
            return None
        with self._bay_lock:
            return [bay.power_mode == PowerMode.ON for bay in self._bays]

    def turn_off_tpm(self, logical_tpm_id):
        """
        Turn off a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off
        :type logical_tpm_id: int
        """
        self.check_power_mode(PowerMode.ON)
        self._check_tpm_id(logical_tpm_id)
        with self._bay_lock:
            self._bays[logical_tpm_id - 1].off()

    def turn_on_tpm(self, logical_tpm_id):
        """
        Turn on a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned on
        :type logical_tpm_id: int
        """
        self.check_power_mode(PowerMode.ON)
        self._check_tpm_id(logical_tpm_id)
        with self._bay_lock:
            self._bays[logical_tpm_id - 1].on()

    def turn_on_tpms(self):
        """
        Turn on all TPMs.
        """
        self.check_power_mode(PowerMode.ON)
        with self._bay_lock:
            for bay in self._bays:
                bay.on()

    def turn_off_tpms(self):
        """
        Turn off all TPMs.
        """
        self.check_power_mode(PowerMode.ON)
        with self._bay_lock:
            for bay in self._bays:
                bay.off()

    def check_power_mode(self, power_mode, error=None):
        """
        Overrides the
        :py:meth:`~ska.low.mccs.hardware.BasePowerModeHardwareDriver.check_power_mode`
        helper method with a more specific error message

        :param power_mode: the asserted power mode
        :type power_mode: :py:class:`ska.low.mccs.hardware.PowerMode`
        :param error: the error message for the exception to be raise if
            not connected
        :type error: str
        """
        super().check_power_mode(
            power_mode, error or f"Subrack is not {power_mode.name}."
        )
