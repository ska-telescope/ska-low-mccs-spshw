# -*- coding: utf-8 -*-
#
# This file is part of the ska.low.mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for hardware management in the
MCCS subsystem.

There are three main classes:

* A "Hardware Driver" wraps actual hardware. The hardware provides a
  software-controllable interface, but the possibilities for this are
  extremely diverse: USB, bluetooth, serial line, ethernet, TCP / UDP /
  IP, encodings, encryption, session management, etc etc etc. A
  "Hardware Driver" encapsulates all that, and provides a python
  object interface to the hardware. The `HardwareDriver` class provided
  here is a base class for such classes.
* A "Hardware Simulator" implements the same interface as a "Hardware
  Driver", but provides an all-software simulation of the hardware. It
  might also support additional methods for external events that it can
  simulate. For example, actual hardware can fail, so a simulator might
  simulate failure via methods like `_simulate_cooling_failure` etc. The
  `HardwareSimulator` class provided here is a base class for such
  classes
* A "Hardware Manager" manages hardware on behalf of a device. Two
  important functions are:

  * monitor and report on the health of the hardware
  * implement the simulationMode attribute of the device, allowing for
    switching between Hardware Driver and Hardware Simulator.

  It might happen in future that a device manages multiple items of
  hardware. For now it is assumed that HardwareDriver provides a single
  interface to all hardware, and HardwareSimulator provides a simulation
  of all hardware. This is a tentative design decision that might change
  in future.

"""
__all__ = ["HardwareDriver", "HardwareSimulator", "HardwareManager"]


from ska.base.control_model import HealthState, SimulationMode


class HardwareDriver:
    """
    An abstract base class for hardware drivers. A hardware driver
    provides a python interface to hardware, hiding details of the
    actual control interface of the hardware

    For now it only specifies off/on functionality.
    """

    def off(self):
        """
        Turn the hardware off

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def on(self):
        """
        Turn me on

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError


class HardwareSimulator:
    """
    A base class for hardware simulators.

    At present this base class implements two pieces of functionality:

    1. It implements the interface specified by HardwareDriver. That is,
       it can be turned off and on (as long as it hasn't failed).

    2. It can be put into a failure state. Whilst failed, the off and on
       commands do not work.
    """

    def __init__(self):
        """
        Initialise a new HardwareSimulator instance
        """
        self._is_on = False
        self._is_failed = False

    @property
    def failed(self):
        """
        Whether this hardware has failed or not

        :return: whether this hardware has failed or not
        :rtype: bool
        """
        return self._is_failed

    @failed.setter
    def failed(self, is_failed):
        """
        Set whether this hardware has failed or not

        :param is_failed: whether this hardware has failed or not
        :type is_failed: bool
        """
        self._is_failed = is_failed

    def off(self):
        """
        Turn me off
        """
        if self._is_failed:
            return
        self._is_on = False

    def on(self):
        """
        Turn me on
        """
        if self._is_failed:
            return
        self._is_on = True

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :return: whether I am on or off
        :rtype: bool
        """
        return self._is_on


class HardwareManager:
    """
    A base class for a hardware manager. The hardware manager manages
    hardware on behalf of a device. Two important functions are:

    * monitor and report on the health of the hardware
    * implement the simulationMode attribute of the device, allowing for
        switching between Hardware Driver and Hardware Simulator.

    To subclass this class:

    1. Implement the `_create_driver` method to create a HardwareDriver
       object that can drive your hardware
    2. Implement the `_create_simulator` method to create a
       HardwareSimulator object that can simulate your hardware
    3. Reimplement the `_evaluate_health` method to provide a health
       report for the hardware object (driver or simulator) in use
    4. Update `_poll_hardware` to ensure that hardware values are
       updated
    5. Implement new hardware command methods
    """

    def __init__(self, simulation_mode):
        """
        Initialise a new HardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        # polled hardware attributes
        self._is_on = None
        self._is_failed = None

        self._health = None
        self._health_callbacks = []

        self._driver = None
        self._simulator = None
        self._simulation_mode = None
        self.simulation_mode = simulation_mode  # use property setter

    @property
    def simulation_mode(self):
        """
        Property getter for simulation_mode

        :return: the simulation mode
        :rtype: :py:class:`~ska.base.control_model.SimulationMode`
        """
        return self._simulation_mode

    @simulation_mode.setter
    def simulation_mode(self, mode):
        """
        Property setter for simulation_mode

        :param mode: new value for simulation mode
        :type mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        if self._simulation_mode != mode:
            if mode == SimulationMode.FALSE:
                if self._driver is None:
                    self._driver = self._create_driver()
                self._hardware = self._driver
            else:
                if self._simulator is None:
                    self._simulator = self._create_simulator()
                self._hardware = self._simulator
            self._simulation_mode = mode
            self.poll_hardware()

    def _create_driver(self):
        """
        Helper method to create and return a
        :py:class:`~ska.low.mccs.hardware.HardwareDriver` to drive the
        hardware

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement abstract _create_driver method."
        )

    def _create_simulator(self):
        """
        Helper method to create and return a
        :py:class:`~ska.low.mccs.hardware.HardwareSimulator` to
        simulate the hardware

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        class_name = type(self).__name__
        raise NotImplementedError(
            f"{class_name} does not implement abstract _create_simulator method."
        )

    def off(self):
        """
        Turn the hardware off

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if not self._hardware.is_on:
            return
        self._hardware.off()
        self.poll_hardware()
        return not self.is_on

    def on(self):
        """
        Turn the hardware on

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if self._hardware.is_on:
            return
        self._hardware.on()
        self.poll_hardware()
        return self.is_on

    def poll_hardware(self):
        """
        Poll the hardware and update local attributes with values
        reported by the hardware.
        """
        self._is_on = self._hardware.is_on
        self._is_failed = self._hardware.failed
        self._update_health()

    @property
    def is_on(self):
        """
        Whether the hardware is on or not

        :return: whether the hardware is on or not
        :rtype: boolean
        """
        return self._is_on

    @property
    def health(self):
        """
        Getter for health property; returns the health of the hardware,
        as evaluated by this manager

        :return: the health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self._health

    def _evaluate_health(self):
        """
        Returns an evaluation of the health of the hardware

        :return: the health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if self._is_failed:
            return HealthState.FAILED
        else:
            return HealthState.OK

    def _update_health(self):
        """
        Update the health of this hardware, ensuring that any registered
        callbacks are called
        """
        health = self._evaluate_health()
        if self._health == health:
            return
        self._health = health
        for callback in self._health_callbacks:
            callback(health)

    def register_health_callback(self, callback):
        """
        Register a callback to be called when the health of the hardware
        changes

        :param callback: A callback to be called when the health of the
            hardware changes
        :type callback: callable
        """
        self._health_callbacks.append(callback)
        callback(self._health)
