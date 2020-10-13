# -*- coding: utf-8 -*-
#
# This file is part of the TpmSimulator project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MccsTpmDeviceSimulator class
"""

__all__ = ["MccsTpmDeviceSimulator", "main"]

import random

from tango.server import Device
from tango.server import attribute


class MccsTpmDeviceSimulator(Device):
    """
    The Tpm Device simulator represents the TANGO interface to the hardware aspects
    of a Tile (TPM) unit.

    This class is a subclass of :py:class:`tango.server.Device`.
    """

    def init_device(self):
        """
        Initialises the device and sets the initial value
        of the attributes
        """
        super().init_device()
        self._simulate = False
        self._voltage = 4.7
        self._current = 0.4
        self._temperature = 36.0
        self._fpga1_temperature = 38.0
        self._fpga2_temperature = 37.5

    def delete_device(self):
        """
        Hook to delete resources allocated in
        :py:meth:`~ska.low.mccs.tpm_device_simulator.MccsTpmDeviceSimulator.init_device`.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.tpm_device_simulator.MccsTpmDeviceSimulator.init_device`
        method to be released. This method is called by the device destructor, and by
        :py:meth:`~ska.low.mccs.tpm_device_simulator.MccsTpmDeviceSimulator.init_device`
        when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevBoolean")
    def simulate(self):
        """
        Return the simulate attribute. If True the value
        of the attributes within this class return is randomly
        generated values.

        :return: the simulate flag
        :rtype: boolean
        """
        return self._simulate

    @simulate.write
    def simulate(self, value):
        """
        Toggle the simulate attribute.

        :param value: true sets randomised attribute values
        :type value: boolean
        """
        self._simulate = value

    @attribute(dtype="DevDouble")
    def voltage(self):
        """
        Return the voltage attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the current
        :rtype: double
        """
        if self._simulate:
            return random.uniform(4.8, 5.5)
        else:
            return self._voltage

    @voltage.write
    def voltage(self, value):
        """
        Set the fixed voltage attribute value.
        It has no effect if the device is in simulate mode

        :param value: the voltage to set
        :type value: double
        """
        if not self._simulate:
            self._voltage = value

    @attribute(dtype="DevDouble")
    def current(self):
        """
        Return the current attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the current
        :rtype: double
        """
        if self._simulate:
            return random.uniform(0.5, 3.0)
        else:
            return self._current

    @current.write
    def current(self, value):
        """
        Set the fixed current attribute value.
        It has no effect if the device is in simulate mode

        :param value: the current to set
        :type value: double
        """
        if not self._simulate:
            self._current = value

    @attribute(dtype="DevDouble")
    def temperature(self):
        """
        Return the temperature attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the board temperature
        :rtype: double
        """
        if self._simulate:
            return random.uniform(25.0, 35.0)
        else:
            return self._temperature

    @temperature.write
    def temperature(self, value):
        """
        Set the fixed temperature attribute value.
        It has no effect if the device is in simulate mode

        :param value: the temperature to set
        :type value: double
        """
        if not self._simulate:
            self._temperature = value

    @attribute(dtype="DevDouble")
    def fpga1_temperature(self):
        """
        Return the fpga1_temperature attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the fpga1 temperature
        :rtype: double
        """
        if self._simulate:
            return random.uniform(25.0, 35.0)
        else:
            return self._fpga1_temperature

    @fpga1_temperature.write
    def fpga1_temperature(self, value):
        """
        Set the fixed fpga1_temperature attribute value.
        It has no effect if the device is in simulate mode

        :param value: the temperature to set
        :type value: double
        """
        if not self._simulate:
            self._fpga1_temperature = value

    @attribute(dtype="DevDouble")
    def fpga2_temperature(self):
        """
        Return the fpga2_temperature attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the fpga2 temperature
        :rtype: double
        """
        if self._simulate:
            return random.uniform(25.0, 35.0)
        else:
            return self._fpga2_temperature

    @fpga2_temperature.write
    def fpga2_temperature(self, value):
        """
        Set the fixed fpga2_temperature attribute value.
        It has no effect if the device is in simulate mode

        :param value: the temperature to set
        :type value: double
        """
        if not self._simulate:
            self._fpga2_temperature = value

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.tpm_device_simulator`
    module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsTpmDeviceSimulator.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
