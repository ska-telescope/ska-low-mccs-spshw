# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains an implementation of a simulator for APIU hardware.

Since access to antennas is via physical cables from the APIU, it is
assumed impossible for a real APIU to work with a simulated antenna, or
a simulated APIU with real antennas. Therefore this module simulates an
APIU and its antennas together.
"""

from ska.low.mccs.hardware import OnOffHardwareSimulator


class AntennaHardwareSimulator(OnOffHardwareSimulator):
    """
    A simulator of the APIU-managed aspects of antenna hardware.

    This is part of the apiu module because the physical antenna is not
    directly monitorable, but must rather be monitored (in part) via the
    APIU.
    """

    VOLTAGE = 3.3
    CURRENT = 20.5
    TEMPERATURE = 23.8

    def __init__(self):
        """
        Initialise a new instance.
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        super().__init__()

    def off(self):
        """
        Turn me off.
        """
        super().off()
        self._voltage = None
        self._current = None
        self._temperature = None

    def on(self):
        """
        Turn me on.
        """
        super().on()
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._temperature = self.TEMPERATURE

    @property
    def voltage(self):
        """
        Return my voltage.

        :return: my voltage
        :rtype: float
        """
        self._check_on()
        return self._voltage

    @property
    def current(self):
        """
        Return my current.

        :return: my current
        :rtype: float
        """
        self._check_on()
        return self._current

    @property
    def temperature(self):
        """
        Return my temperature.

        :return: my temperature
        :rtype: float
        """
        self._check_on()
        return self._temperature

    def _check_on(self, error=None):
        """
        Overrides the
        :py:meth:`~ska.low.mccs.hardware.OnOffHardwareSimulator._check_on`
        helper method with a more specific error message

        :param error: the error message for the exception to be raised
            if not connected
        :type error: str
        """
        super()._check_on(error or "Antenna hardware is turned off")

    def simulate_current(self, current):
        """
        Simulate a change in antenna current.

        :param current: the new antenna current value to be simulated
        :type current: float
        """
        self._current = current

    def simulate_voltage(self, voltage):
        """
        Simulate a change in antenna voltage.

        :param voltage: the new antenna voltage value to be simulated
        :type voltage: float
        """
        self._voltage = voltage

    def simulate_temperature(self, temperature):
        """
        Simulate a change in antenna temperature.

        :param temperature: the new antenna temperature value to be simulated
        :type temperature: float
        """
        self._temperature = temperature


class APIUSimulator(OnOffHardwareSimulator):
    """
    A simulator of APIU hardware.
    """

    VOLTAGE = 3.4
    CURRENT = 20.5
    TEMPERATURE = 20.4
    HUMIDITY = 23.9
    NUMBER_OF_ANTENNAS = 2

    def __init__(self):
        """
        Initialise a new APIUSimulator instance.
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None

        self._antennas = [
            AntennaHardwareSimulator() for antenna_id in range(self.NUMBER_OF_ANTENNAS)
        ]
        super().__init__()

    def off(self):
        """
        Turn me off.
        """
        super().off()
        self._voltage = None
        self._current = None
        self._temperature = None
        self._humidity = None

        for antenna in self._antennas:
            antenna.off()

    def on(self):
        """
        Turn me on.
        """
        super().on()
        self._voltage = self.VOLTAGE
        self._current = self.CURRENT
        self._temperature = self.TEMPERATURE
        self._humidity = self.HUMIDITY

        # but don't turn antennas on

    @property
    def voltage(self):
        """
        Return my voltage.

        :return: my voltage
        :rtype: float
        """
        self._check_on()
        return self._voltage

    @property
    def current(self):
        """
        Return my current.

        :return: my current
        :rtype: float
        """
        self._check_on()
        return self._current

    @property
    def temperature(self):
        """
        Return my temperature.

        :return: my temperature
        :rtype: float
        """
        self._check_on()
        return self._temperature

    @property
    def humidity(self):
        """
        Return my humidity.

        :return: my humidity
        :rtype: float
        """
        self._check_on()
        return self._humidity

    def is_antenna_on(self, logical_antenna_id):
        """
        Return whether a specified antenna is turned on.

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int

        :return: whether the antenna is on, or None if the APIU itself
            is off
        :rtype: bool or None
        """
        self._check_on()
        return self._antennas[logical_antenna_id - 1].is_on

    def turn_off_antenna(self, logical_antenna_id):
        """
        Turn off a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned off
        :type logical_antenna_id: int
        """
        self._check_on()
        self._antennas[logical_antenna_id - 1].off()

    def turn_on_antenna(self, logical_antenna_id):
        """
        Turn on a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna to be turned on
        :type logical_antenna_id: int
        """
        self._check_on()
        self._antennas[logical_antenna_id - 1].on()

    def get_antenna_current(self, logical_antenna_id):
        """
        Get the current of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the current is requested
        :type logical_antenna_id: int

        :return: the antenna current
        :rtype: float
        """
        self._check_on()
        return self._antennas[logical_antenna_id - 1].current

    def get_antenna_voltage(self, logical_antenna_id):
        """
        Get the voltage of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the voltage is requested
        :type logical_antenna_id: int

        :return: the antenna voltage
        :rtype: float
        """
        self._check_on()
        return self._antennas[logical_antenna_id - 1].voltage

    def get_antenna_temperature(self, logical_antenna_id):
        """
        Get the temperature of a specified antenna.

        :param logical_antenna_id: this APIU's internal id for the
            antenna for which the temperature is requested
        :type logical_antenna_id: int

        :return: the antenna temperature
        :rtype: float
        """
        self._check_on()
        return self._antennas[logical_antenna_id - 1].temperature

    def _check_on(self, error=None):
        """
        Overrides the
        :py:meth:`~ska.low.mccs.hardware.OnOffHardwareSimulator._check_on`
        helper method with a more specific error message

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str
        """
        super()._check_on(error or "APIU hardware is turned off")
