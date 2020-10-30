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

    The only functionality it mandates is the ability to check whether
    this driver is connected to hardware.
    """

    def is_connected(self):
        """
        Returns whether this driver is connected to the hardware. This
        should be implemented to return a bool.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError


class OnOffHardwareDriver(HardwareDriver):
    """
    Adds on() and off() commands to the abstract
    :py:class:`HardwareDriver` class.

    :todo: Once we have standby too, make this a mixin.
    """

    def on(self):
        """
        Turn me on

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def off(self):
        """
        Turn the hardware off

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

    It only implements one piece of functionality: it can be put into a
    failure state, by pretending to have lost connection to the
    hardware.
    """

    def __init__(self, fail_connect=False):
        """
        Initialise a new HardwareSimulator instance

        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        """
        self._is_connected = not fail_connect

    @property
    def is_connected(self):
        """
        Returns whether this simulator is connected to the hardware.
        This should be implemented to return a bool.

        :return: whether the device is connected to the hardware or not
        :rtype: bool
        """
        return self._is_connected

    def check_connected(self, error=None):
        """
        Helper method to check that a connection is in place, and raise
        a suitable error if it is not.

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ConnectionError: if there is no connection to the
            hardware
        """
        if not self._is_connected:
            raise ConnectionError(error or "No connection to hardware")

    def simulate_connection_failure(self, fail):
        """
        Set whether this hardware simulator is simulating failure to
        connect to the hardware

        :param fail: whether or not this hardware simulator should
            simulate failure to connect to the hardware
        :type fail: bool
        """
        self._is_connected = not fail


class OnOffHardwareSimulator(HardwareSimulator):
    """
    Adds on() and off() commands to the :py:class:`HardwareSimulator`
    base class

    :todo: once we have standby too, make this a mixin
    """

    def __init__(self, fail_connect=False, is_on=False):
        """
        Initialise a new OnOffHardwareSimulator instance

        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        :param is_on: whether this simulator should simulate connecting
            to hardware that was already turned on
        :type is_on: bool
        """
        super().__init__(fail_connect)
        self._is_on = is_on

    def off(self):
        """
        Turn me off
        """
        self.check_connected()
        self._is_on = False

    def on(self):
        """
        Turn me on
        """
        self.check_connected()
        self._is_on = True

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :return: whether I am on or off
        :rtype: bool
        """
        self.check_connected()
        return self._is_on

    def check_on(self, error=None):
        """
        Helper method to check that the hardware is turned on, and raise
        a suitable error if it is not.

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ValueError: if the hardware is turned off
        """
        self.check_connected()
        if not self._is_on:
            raise ValueError(error or "Hardware is turned off")


class HardwareHealthEvaluator:
    """
    An simple base class that implements a policy by which a hardware
    manager evaluates the health of its hardware. This evaluator returns
    FAILED if the connection to the hardware is broken, and OK
    otherwise.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the hardware.

        :param hardware: the hardware driver or simulator for which
            health is being evaluated
        :type hardware: :py:class:`HardwareDriver` or
            :py:class:`HardwareSimulator`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not hardware.is_connected:
            return HealthState.FAILED
        return HealthState.OK


class OnOffHardwareHealthEvaluator(HardwareHealthEvaluator):
    """
    Implements a policy that uses the on-off status of the hardware in
    health evaluation. This evaluator returns
    FAILED if the connection to the hardware is broken, UNKNOWN if the
    hardware is turned off, and OK if the hardware is turned on

    :todo: once we have standby too, make this a mixin.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the hardware.

        :param hardware: the hardware driver or simulator for which
            health is being evaluated
        :type hardware: :py:class:`HardwareDriver` or
            :py:class:`HardwareSimulator`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not hardware.is_connected:
            return HealthState.FAILED
        if not hardware.is_on:
            return HealthState.UNKNOWN
        return HealthState.OK


class HardwareManager:
    """
    A base class for a hardware manager. The hardware manager manages
    hardware on behalf of a device. Important functions include:

    * monitoring and reporting on hardware health
    * management of simulation mode

    To subclass this class:

    1. Implement the `_create_driver` method to create a HardwareDriver
       object that can drive your hardware

    2. Implement the `_create_simulator` method to create a
       HardwareSimulator object that can simulate your hardware

    4. Update `poll` to do anything that you MUST do on the polling
       loop, such as re-evaluate hardware health

    5. Implement any new hardware command methods
    """

    def __init__(self, simulation_mode, health_evaluator=HardwareHealthEvaluator()):
        """
        Initialise a new HardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        :param health_evaluator: a class that implements a policy for
            deciding on hardware health, defaults to
            :py:class:`HardwareHealthEvaluator`
        :type health_evaluator: :py:class:`HardwareHealthEvaluator`
        """
        self._driver = None
        self._simulator = None
        self._simulation_mode = None

        self._health = None
        self._health_callbacks = []
        self._health_evaluator = health_evaluator

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
        if self._simulation_mode == mode:
            return

        if mode == SimulationMode.FALSE:
            if self._driver is None:
                self._driver = self._create_driver()
            self._hardware = self._driver
        else:
            if self._simulator is None:
                self._simulator = self._create_simulator()
            self._hardware = self._simulator

        self._simulation_mode = mode

        self._update_health()

    def _create_driver(self):
        """
        Helper method to create and return a
        :py:class:`~ska.low.mccs.hardware.HardwareDriver` to drive the
        hardware

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_driver method not implemented."
        )

    def _create_simulator(self):
        """
        Helper method to create and return a
        :py:class:`~ska.low.mccs.hardware.HardwareSimulator` to
        simulate the hardware

        :return: the simulator, just created, to be used by this
            :py:class:`~ska.low.mccs.hardware.HardwareManager`
        :rtype: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
        """
        return HardwareSimulator()

    def poll(self):
        """
        Poll the hardware and respond to external events/changes
        """
        self._update_health()

    @property
    def health(self):
        """
        Getter for health property; returns the health of the hardware,
        as evaluated by this manager

        :return: the health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self._health

    def _update_health(self):
        """
        Update the health of this hardware, ensuring that any registered
        callbacks are called
        """
        health = self._health_evaluator.evaluate_health(self._hardware)
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


class OnOffHardwareManager(HardwareManager):
    """
    Add on and off commands to :py:class:`HardwareManager` base class
    """

    def __init__(
        self, simulation_mode, health_evaluator=OnOffHardwareHealthEvaluator()
    ):
        """
        Initialise a new HardwareManager instance

        :param simulation_mode: the initial simulation mode of this
            hardware manager
        :type simulation_mode: :py:class:`~ska.base.control_model.SimulationMode`
        :param health_evaluator: a class that implements a policy for
            deciding on hardware health, defaults to
            :py:class:`OnOffHardwareHealthEvaluator`
        :type health_evaluator: :py:class:`OnOffHardwareHealthEvaluator`
        """
        super().__init__(simulation_mode, health_evaluator)

    def _create_simulator(self):
        """
        Helper method to create and return a
        :py:class:`~OnOffHardwareSimulator` to simulate the hardware

        :return: the simulator, just created, to be used by this
            :py:class:`OnOffHardwareManager`
        :rtype: :py:class:`OnOffHardwareSimulator`
        """
        return OnOffHardwareSimulator()

    def off(self):
        """
        Turn the hardware off

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if not self._hardware.is_on:
            return
        self._hardware.off()

        self._update_health()
        return not self._hardware.is_on

    def on(self):
        """
        Turn the hardware on

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if self._hardware.is_on:
            return
        self._hardware.on()

        self._update_health()
        return self._hardware.is_on

    @property
    def is_on(self):
        """
        Whether the hardware is on or not

        :return: whether the hardware is on or not
        :rtype: boolean
        """
        return self._hardware.is_on
