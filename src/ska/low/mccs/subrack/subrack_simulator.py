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

        :param temperature: the initial temperature of this module (in celsius)
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

    NUMBER_OF_BAYS = 8
    """
    The number of bays in this subrack.
    """
    DEFAULT_BACKPLANE_TEMPERATURE = list[38.0, 39.0]
    """
    The default initial simulated temperature for the subrack backplane;
    this can be overruled in the constructor
    """
    DEFAULT_BOARD_TEMPERATURE = list[39.0, 40.0]
    """
    The default initial simulated temperature for the subrack management
    board itself; this can be overruled in the constructor
    """
    DEFAULT_BOARD_CURRENT = 1.1
    """
    The default initial simulated current for the subrack management
    board itself; this can be overruled in the constructor
    """
    DEFAULT_FAN_SPEED = list[4999.0, 5000.0, 5001.0, 5002.0]
    """
    The default initial simulated fan speed for the subrack; this can be
    overruled using the set_subrack_fan_speed method
    """
    DEFAULT_FAN_MODE = list[0, 0, 0, 0]
    """
    The default initial simulated fan mode for the subrack; this can be
    overruled using the set_fan_mode method
    """
    DEFAULT_TPM_ON_OFF = list[0, 0, 0, 0, 0, 0, 0, 0]
    """
        The default initial simulated Power On/Off status of inserted tpm; this can be
        overruled in the constructor
    """
    DEFAULT_TPM_PRESENT = list[1, 1, 1, 1, 1, 1, 1, 1]
    """
        The default initial simulated tpm present in the subrack;
    """
    DEFAULT_PS_POWER = list[50, 60, 70]
    """
        The default initial simulated PS power; this can be
        overruled in the constructor
    """
    DEFAULT_PS_FAN_SPEED = list[70, 71, 72, 73]
    """
        The default initial simulated power supply fan speed in percent; this can be
        overruled using the set_ps_fan speed function
    """

    def __init__(
        self,
        backplane_temperature=DEFAULT_BACKPLANE_TEMPERATURE,
        board_temperature=DEFAULT_BOARD_TEMPERATURE,
        board_current=DEFAULT_BOARD_CURRENT,
        fan_speed=DEFAULT_FAN_SPEED,
        fan_mode=DEFAULT_FAN_MODE,
        ps_power=DEFAULT_PS_POWER,
        ps_fan_speed=DEFAULT_PS_FAN_SPEED,
        tpm_on_off=DEFAULT_TPM_ON_OFF,
        tpm_present=DEFAULT_TPM_PRESENT,
        fail_connect=False,
        power_mode=PowerMode.OFF,
        _bays=None,
    ):
        """
        Initialise a new instance.

        :param backplane_temperature: the initial temperature of the
            subrack backplane from sensor 1 and 2
        :type backplane_temperature: list of float
        :param board_temperature: the initial temperature of the subrack
            management board from sensor 1 and 2
        :type board_temperature: list of float
        :param board_current: the initial current of the subrack
            management board
        :type board_current: float
        :param fan_speed: the initial fan_speed of the subrack backplane
            management board
        :type fan_speed: list of float
        :param fan_mode: the initial fan mode of the subrack backplane
        :type fan_mode: list of int
        :param ps_power: the initial power for the 3 power supply in the subrack
        :type ps_power: list of float
        :param: ps_fan_speed: the initial fan speed in percent for the 3 power supply
            in the subrack
        :type ps_fan_speed: list of float
        :param tpm_on_off: the initial Power On/Off status of inserted tpm
        :type tpm_on_off: list of int
        :param tpm_present: the initial TPM board present on subrack
        :type tpm_present: list of int
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
        :type _bays: list of :py:class:`.SubrackBaySimulator`

        """
        self._backplane_temperature = backplane_temperature
        self._board_temperature = board_temperature
        self._board_current = board_current
        self._fan_speed = fan_speed
        self._fan_mode = fan_mode
        self._ps_power = ps_power
        self._ps_fan_speed = ps_fan_speed
        self._tpm_on_off = tpm_on_off
        self._tpm_present = tpm_present

        self._bays = _bays or [
            SubrackBaySimulator() for count in range(self.NUMBER_OF_BAYS)
        ]

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
        Return the subrack backplane temperature from sensor 1 and 2

        :return: the subrack backplane temperature
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return self._backplane_temperature

    def simulate_backplane_temperature(self, backplane_temperature):
        """
        Set the simulated backplane temperature for this subrack
        simulator.

        :param backplane_temperature: the simulated backplane
            temperature for this subrack simulator.
        :type backplane_temperature: list of float

        """
        self._backplane_temperature = backplane_temperature

    @property
    def board_temperature(self):
        """
        Return the subrack management board temperature from sensor 1 and 2

        :return: the board temperature, in degrees celsius
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return self._board_temperature

    def simulate_board_temperature(self, board_temperature):
        """
        Set the simulated board temperature for this subrack simulator.

        :param board_temperature: the simulated board temperature for
            this subrack simulator.
        :type board_temperature: list of float

        """
        self._board_temperature = board_temperature

    @property
    def board_current(self):
        """
        Return the current of this subrack's management board bays
        (hence the currents of the TPMs housed in those bays).

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
        Return the subrack backplane fan speed (in RPMs).

        :return: the subrack fan speed (RPMs)
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return self._fan_speed

    def simulate_fan_speed(self, fan_speed):
        """
        Set the simulated fan speed for this subrack simulator.

        :param fan_speed: the simulated fan speed for this subrack simulator.
        :type fan_speed: list of 4 float

        """
        self._fan_speed = fan_speed

    @property
    def fan_speed_perc(self):
        """
        Return the subrack backplane fan speed in percent

        :return: the fan speed, in percent
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return self._fan_speed_perc

    @property
    def subrack_fan_mode(self):
        """
        Return the subrack fan Mode.
        :return: subrack fan mode  1 AUTO or 0 MANUAL
        :rtype:list of int
        """
        self.check_power_mode(PowerMode.ON)
        return self._subrack_fan_mode

    @property
    def tpm_count(self):
        """
        Return the number of TPMs housed in this subrack.

        :return: the number of TPMs housed in this subrack
        :rtype: int

        """
        return len(self._bays)

    @property
    def tpm_temperatures(self):
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return [bay.temperature for bay in self._bays]

    def simulate_tpm_temperatures(self, tpm_temperatures):
        """
        Set the simulated temperatures for all TPMs housed in this
        subrack simulator.

        :param tpm_temperatures: the simulated TPM temperatures.
        :type tpm_temperatures: list of float

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_temperatures) != self.tpm_count:
            raise ValueError("Argument does not match number of TPMs")

        for (bay, temperature) in zip(self._bays, tpm_temperatures):
            bay.simulate_temperature(temperature)

    @property
    def tpm_power(self):
        """
        Return a list of bay powers for this subrack.

        :return: a list of bay powers, in Watt
        :rtype: list of float

        """
        return self._tpm_power

    @property
    def tpm_voltage(self):
        """
        Return a list of bay voltages for this subrack.

        :return: a list of bay voltages, in volt
        :rtype: list of float

        """
        return self._tpm_voltage

    @property
    def ps_fanspeed(self):
        """
        Return the ps fan speed for this subrack.

        :return: the ps fan speed
        :rtype: list of float

        """
        return self._ps_fanspeed

    @property
    def ps_current(self):
        """
        Return the ps current for this subrack.

        :return: the ps current
        :rtype: list of float
        """
        return self._ps_current

    @property
    def ps_power(self):
        """
        Return the pps power for this subrack.

        :return: the ps power
        :rtype: list of float
        """
        return self._ps_power

    def simulate_ps_power(self, ps_power):
        """
        Set the the pps power for this subrack.

        :param ps_power: the simulated  ps power
        :type ps_power: list of 3 float

        """
        self._ps_power = ps_power

    @property
    def ps_voltage(self):
        """
        Return the ps voltage for this subrack.

        :return: the ps voltages
        :rtype: list of float
        """
        return self._ps_voltage

    @property
    def tpm_on_off(self):
        """
        Check whether the tpm are on or off

        :return: list of tpm on or off in the subrack
        :rtype: list of int
        """
        return self._tpm_on_off

    @property
    def tpm_present(self):
        """
        Return the tpm detected in the subrack

        :return: list of tpm detected
        :rtype: list of int
        """
        return self._tpm_present

    @property
    def tpm_supply_fault(self):
        """
        Return info about about TPM supply fault status.

        :return: the TPM supply fault status
        :rtype: list of int
        """
        return self._tpm_supply_fault

    @property
    def tpm_currents(self):
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        :rtype: list of float

        """
        self.check_power_mode(PowerMode.ON)
        return [bay.current for bay in self._bays]

    def simulate_tpm_currents(self, tpm_currents):
        """
        Set the simulated currents for all TPMs housed in this subrack
        simulator.

        :param tpm_currents: the simulated TPM currents.
        :type tpm_currents: list of float

        :raises ValueError: If the argument doesn't match the number of
            TPMs in this subrack
        """
        if len(tpm_currents) != self.tpm_count:
            raise ValueError("Argument does not match number of TPMs")

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
        self.check_power_mode(PowerMode.ON)
        return self._bays[logical_tpm_id - 1].power_mode == PowerMode.ON

    def turn_off_tpm(self, logical_tpm_id):
        """
        Turn off a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off
        :type logical_tpm_id: int

        """
        self.check_power_mode(PowerMode.ON)
        self._bays[logical_tpm_id - 1].off()
        self._tpm_on_off[logical_tpm_id - 1] = 0

    def turn_on_tpm(self, logical_tpm_id):
        """
        Turn on a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned on
        :type logical_tpm_id: int

        """
        self.check_power_mode(PowerMode.ON)
        self._bays[logical_tpm_id - 1].on()
        self._tpm_on_off[logical_tpm_id - 1] = 1

    def turn_on_tpms(self):
        """
        Turn on all TPMs.
        """
        self.check_power_mode(PowerMode.ON)
        self._tpm_on_off = list[1, 1, 1, 1, 1, 1, 1, 1]
        for bay in self._bays:
            bay.on()

    def turn_off_tpms(self):
        """
        Turn off all TPMs.
        """
        self.check_power_mode(PowerMode.ON)
        self._tpm_on_off = list[0, 0, 0, 0, 0, 0, 0, 0]
        for bay in self._bays:
            bay.off()

    def set_subrack_fan_speed(self, fan_id, speed_pwm_perc):
        """
        Set the subrack backplane fan speed

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param speed_pwm_perc: percentage value of fan RPM  (MIN 0=0% - MAX 100=100%)
        :type speed_pwm_perc: float

        """
        self.check_power_mode(PowerMode.ON)
        self._fan_speed[fan_id - 1] = speed_pwm_perc

    def set_fan_mode(self, fan_id, mode):
        """
        Set Fan Operational Mode for the subrack's fan

        :param fan_id: id of the selected fan accepted value: 1-4
        :type fan_id: int
        :param mode:  1 AUTO, 0 MANUAL
        :type mode: int

        """
        self.check_power_mode(PowerMode.ON)
        self._fan_mode[fan_id - 1] = mode

    def set_ps_fan_speed(self, ps_fan_id, speed_per):
        """
        Set the power supply  fan speed

        :param ps_fan_id: power supply id from 0 to 2
        :type ps_fan_id: int
        :param speed_per: fan speed in percent (MIN 0=0% - MAX 100=100%)
        :type speed_per: float

        """
        self.check_power_mode(PowerMode.ON)
        self._ps_fan_speed[ps_fan_id - 1] = speed_per

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
