# -*- coding: utf-8 -*-
#
# This file is part of the TpmSimulator project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MccsTpmSimulator class
"""

__all__ = ["MccsTpmSimulator", "main"]

import random

from tango.server import Device
from tango.server import attribute


class MccsTpmSimulator(Device):

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the TpmSimulator."""
        super().init_device()
        self._simulate = False
        self._voltage = 4.7
        self._current = 0.4
        self._temperature = 36.0
        self._fpga1_temperature = 38.0
        self._fpga2_temperature = 37.5

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        pass

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevBoolean")
    def simulate(self):
        return self._simulate

    @simulate.write
    def simulate(self, value):
        print("simulate value", value)
        self._simulate = value

    @attribute(dtype="DevDouble")
    def voltage(self):
        """Return the voltage attribute."""
        if self._simulate:
            return random.uniform(4.5, 5.5)
        else:
            print("reading voltage ****************************", self._voltage)
            return self._voltage

    @voltage.write
    def voltage(self, value):
        """Set the voltage attribute."""
        if not self._simulate:
            self._voltage = value

    @attribute(dtype="DevDouble")
    def current(self):
        """Return the current attribute."""
        if self._simulate:
            return random.uniform(0.0, 3.0)
        else:
            return self._current

    @current.write
    def current(self, value):
        """Set the current attribute."""
        if not self._simulate:
            self._current = value

    @attribute(dtype="DevDouble")
    def temperature(self):
        if self._simulate:
            return random.uniform(25.0, 40.0)
        else:
            return self._temperature

    @temperature.write
    def temperature(self, value):
        if not self._simulate:
            self._temperature = value

    @attribute(dtype="DevDouble")
    def fpga1_temperature(self):
        if self._simulate:
            return random.uniform(25.0, 40.0)
        else:
            return self._fpga1_temperature

    @fpga1_temperature.write
    def fpga1_temperature(self, value):
        if not self._simulate:
            self._fpga1_temperature = value

    @attribute(dtype="DevDouble")
    def fpga2_temperature(self):
        if self._simulate:
            return random.uniform(25.0, 40.0)
        else:
            return self._fpga2_temperature

    @fpga2_temperature.write
    def fpga2_temperature(self, value):
        if not self._simulate:
            self._fpga2_temperature = value

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsTpmSimulator module."""

    return MccsTpmSimulator.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
