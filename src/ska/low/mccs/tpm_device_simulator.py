# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
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

from tango.server import Device, attribute
from ska.base.control_model import HealthState

from ska.low.mccs.events import EventManager
from ska.low.mccs.hardware import Hardware, HardwareManager
from ska.low.mccs.health import HealthModel


class TpmHardware(Hardware):
    """
    A stub class to take the place of actual TPM hardware
    """

    VOLTAGE = 3.5
    CURRENT = 0.4
    TEMPERATURE = 36.0
    FPGA1_TEMPERATURE = 38.0
    FPGA2_TEMPERATURE = 37.5

    def __init__(self):
        """
        Initialise a new TpmHardware instance
        """
        super().__init__()
        self._voltage = None
        self._current = None
        self._temperature = None
        self._fpga1_temperature = None
        self._fpga2_temperature = None

    def off(self):
        """
        Turn me off
        """
        self._voltage = None
        self._current = None
        self._temperature = None
        self._fpga1_temperature = None
        self._fpga2_temperature = None
        super().off()

    def on(self):
        """
        Turn me on
        """
        super().on()
        self._voltage = TpmHardware.VOLTAGE
        self._current = TpmHardware.CURRENT
        self._temperature = TpmHardware.TEMPERATURE
        self._fpga1_temperature = TpmHardware.FPGA1_TEMPERATURE
        self._fpga2_temperature = TpmHardware.FPGA2_TEMPERATURE

    @property
    def voltage(self):
        """
        Return my voltage

        :return: my voltage
        :rtype: float
        """
        return self._voltage

    @property
    def current(self):
        """
        Return my current

        :return: my current
        :rtype: float
        """
        return self._current

    @property
    def temperature(self):
        """
        Return my temperature

        :return: my temperature
        :rtype: float
        """
        return self._temperature

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of my FPGA 1

        :return: the temperature of my FPGA 1
        :rtype: float
        """
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of my FPGA 2

        :return: the temperature of my FPGA 2
        :rtype: float
        """
        return self._fpga2_temperature


class TpmHardwareManager(HardwareManager):
    """
    This class manages TPM hardware.

    :todo: So far only voltage, current and the temperature attributes
        have been moved in here. There are lots of other attributes that
        should be.
    :todo: Also, the device properties that deal with how to connect to
        the hardware should be passed to the initialiser for this.
    """

    def __init__(self, hardware=None):
        """
        Initialise a new TpmHardwareManager instance

        At present, hardware is simulated by stub software, and so the
        only argument is an optional "hardware" instance. In future, its
        arguments will allow connection to the actual hardware

        :param hardware: the hardware itself, defaults to None. This only
            exists to facilitate testing.
        :type hardware: :py:class:`TpmHardware`
        """
        # polled hardware attributes
        self._voltage = None
        self._current = None
        self._temperature = None
        self._fpga1_temperature = None
        self._fpga2_temperature = None
        super().__init__(hardware or TpmHardware())

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        self._is_on = self._hardware.is_on
        if self._is_on:
            self._voltage = self._hardware.voltage
            self._current = self._hardware.current
            self._temperature = self._hardware.temperature
            self._fpga1_temperature = self._hardware.fpga1_temperature
            self._fpga2_temperature = self._hardware.fpga2_temperature
        else:
            self._voltage = None
            self._current = None
            self._temperature = None
            self._fpga1_temperature = None
            self._fpga2_temperature = None
        self._update_health()

    @property
    def voltage(self):
        """
        The voltage of the hardware

        :return: the voltage of the hardware
        :rtype: float
        """
        return self._voltage

    @property
    def current(self):
        """
        The current of the hardware

        :return: the current of the hardware
        :rtype: float
        """
        return self._current

    @property
    def temperature(self):
        """
        Return the temperature of the hardware

        :return: the temperature of the hardware
        :rtype: float
        """
        return self._temperature

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._fpga2_temperature

    def _evaluate_health(self):
        """
        Evaluate the health of the hardware

        :return: an evaluation of the health of the managed hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        # TODO: look at the polled hardware values and maybe further
        # poke the hardware to check that it is okay. But for now:
        return HealthState.OK


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

        self.hardware_manager = TpmHardwareManager()
        self.event_manager = EventManager()
        self.health_model = HealthModel(self.hardware_manager, None, self.event_manager)

        self.hardware_manager.on()  # HACK until we have power commands implemented

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
    # redefinition from base classes to turn polling on
    @attribute(
        dtype=HealthState,
        polling_period=1000,
        doc="The health state reported for this device. "
        "It interprets the current device"
        " condition and condition of all managed devices to set this. "
        "Most possibly an aggregate attribute.",
    )
    def healthState(self):
        """
        returns the health of this device; which in this case means the
        rolled-up health of the entire MCCS subsystem

        :return: the rolled-up health of the MCCS subsystem
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self.health_model.health

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

    @attribute(dtype="DevDouble", polling_period=1000)
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
            return self.hardware_manager.voltage

    @attribute(dtype="DevDouble", polling_period=1000)
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
            return self.hardware_manager.current

    @attribute(dtype="DevDouble", polling_period=1000)
    def temperature(self):
        """
        Return the temperature attribute which will be either a fixed
        value or a random value dependent upon the value of the simulate
        attribute

        :return: the temperature
        :rtype: double
        """
        if self._simulate:
            return random.uniform(25.0, 35.0)
        else:
            return self.hardware_manager.temperature

    @attribute(dtype="DevDouble", polling_period=1000)
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
            return self.hardware_manager.fpga1_temperature

    @attribute(dtype="DevDouble", polling_period=1000)
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
            return self.hardware_manager.fpga2_temperature

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
