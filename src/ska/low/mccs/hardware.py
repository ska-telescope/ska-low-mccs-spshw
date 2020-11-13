# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for hardware management in the
MCCS subsystem.

Conceptually, the model comprises:

* Hardware drivers. These wraps actual hardware. The hardware provides a
  software-controllable interface, but the possibilities for this are
  diverse: USB, bluetooth, serial line, ethernet, TCP / UDP / IP,
  encodings, encryption, session management, etc etc etc. A hardware
  driver encapsulates all that, and provides a python object interface
  to the hardware.

* Hardware simulators. These implement the interface of the
   corresponding hardware driver, but in software. That is, a hardware
   simulator pretends to be a hardware driver, but it does not wrap
   actual hardware. In addition to implementing the driver interface,
   a simulator may expose methods for external events that it can
   simulate. For example, actual hardware can fail, so a simulator might
   simulate failure via methods like `_simulate_cooling_failure` etc.

* Hardware factories. These create and provide access to hardware
  drivers / simulators. For example, in a device that can switch between
  hardware driver and hardware simulator, the hardware factory is
  responsible for the switching, and all other components of the system
  do not distinguish between the two.

* Hardware health evaluators. These interrogate the hardware, evaluate
  its health in accordance with some policy, and report that health to
  other components.

* Hardware managers. These manage hardware on behalf of a device.
  Specifically, they manage a device's simulation mode (if relevant),
  monitor hardware health, and provide access to the hardware interface.


The classes fall into three groups:

* The "base" classes comprise:

  * :py:class:`HardwareDriver`: a base class for hardware drivers. The
    only functionality it specifies is an
    :py:meth:`~HardwareDriver.is_connected` property, which captures
    whether or not the hardware driver has established a connection to
    the hardware.

  * :py:class:`HardwareFactory`: a base class for hardware factories.

  * :py:class:`HardwareHealthEvaluator`: a base class for hardware
    health evaluators. The policy implemented determines health solely
    on the basis of whether there is a connection to the hardware.

  * :py:class:`HardwareManager`: a base class for hardware managers. Its
    main function is to ensure that the hardware health evaluator is
    regularly polled.

* The "simulator" group of classes extend the above to handle switching
  between an actual hardware driver and a hardware simulator. They
  comprise:

  * :py:class:`HardwareSimulator`: a base class for hardware simulators.
    This implements the :py:meth:`~HardwareSimulator.is_connected`
    property, and provides a
    :py:meth:`~HardwareSimulator.simulate_connection_failure` method by
    which failure of the connection to the hardware can be simulated.

  * :py:class:`SimulableHardwareFactory`: a hardware factory that can
    switch between returning a hardware driver or a hardware simulator,
    depending on its simulation mode

  * :py:class:`SimulableHardwareManager`: a hardware manager that
    manages a device's
    :py:class:`~ska.base.SKABaseDevice.simulationMode` attribute,
    allowing switching between hardware driver and hardware simulator

* The "on/off" group of classes extend the base classes to handle the
  common case of hardware that can be turned off and on. They comprise

  * :py:class:`OnOffHardwareDriver`: extends the hardware driver
    interface with :py:meth:`~OnOffHardwareDriver.off` and
    :py:meth:`~OnOffHardwareDriver.on` methods, and an
    :py:meth:`~OnOffHardwareDriver.is_on` property.

  * :py:class:`OnOffHardwareSimulator`: provides
    a software implementation of the
    :py:meth:`~OnOffHardwareSimulator.off` and
    :py:meth:`~OnOffHardwareSimulator.on` methods, and the
    :py:meth:`~OnOffHardwareSimulator.is_on` property

  * :py:class:`OnOffHardwareManager`: extends the hardware manager to
    allow access to the :py:meth:`~OnOffHardwareManager.off` and
    :py:meth:`~OnOffHardwareManager.on` methods, and the
    :py:meth:`~OnOffHardwareManager.is_on` property.
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

    def _check_connected(self, error=None):
        """
        Helper method to check that a connection is in place, and raise
        a suitable error if it is not.

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ConnectionError: if there is no connection to the
            hardware
        """
        if not self.is_connected:
            raise ConnectionError(error or "No connection to hardware")


class HardwareHealthEvaluator:
    """
    An simple base class that implements a policy by which a hardware
    manager evaluates the health of its hardware. This evaluator treads
    the hardware as failed if the connection to the hardware is broken,
    and OK otherwise.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the hardware.

        :param hardware: the hardware driver for which health is being
            evaluated
        :type hardware: :py:class:`HardwareDriver`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not hardware.is_connected:
            return HealthState.FAILED
        return HealthState.OK


class HardwareFactory:
    """
    Abstract base class for a hardware factory.
    """

    @property
    def hardware(self):
        """
        Return the hardware

        :raises NotImplementedError: because this method need to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}.hardware property not implemented."
        )


class HardwareManager:
    """
    A base class for a hardware manager. The hardware manager manages
    hardware on behalf of a device.

    This base class supports only monitoring and reporting on hardware
    health. To this end, it allows for:

    * registration of a HardwareHealthEvaluator to evaluate the health
      of hardware

    * a :py:meth:`poll` method that re-evaluates hardware health each
      time it is called.

    * a read-only health property

    * registration of callbacks to be called on health change
    """

    def __init__(self, hardware_factory, health_evaluator):
        """
        Initialise a new HardwareManager instance

        :param hardware_factory: a factory that provides access to the
            hardware
        :type hardware_factory: :py:class:`HardwareFactory`
        :param health_evaluator: a class that implements a policy for
            deciding on hardware health, defaults to
            :py:class:`HardwareHealthEvaluator`
        :type health_evaluator: :py:class:`HardwareHealthEvaluator`
        """
        self._factory = hardware_factory
        self._health = HealthState.UNKNOWN
        self._health_callbacks = []
        self._health_evaluator = health_evaluator
        self._update_health()

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
        health = self._health_evaluator.evaluate_health(self._factory.hardware)
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


class HardwareSimulator(HardwareDriver):
    """
    A base class for hardware simulators.

    It provdes a concreate implementation of
    :py:meth:`HardwareDriver.is_connected`, and can be put into a
    failure state via a :py:meth:`simulate_connection_failure` method.
    """

    def __init__(self, fail_connect=False):
        """
        Initialise a new instance

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

    def simulate_connection_failure(self, fail):
        """
        Set whether this hardware simulator is simulating failure to
        connect to the hardware

        :param fail: whether or not this hardware simulator should
            simulate failure to connect to the hardware
        :type fail: bool
        """
        self._is_connected = not fail


class SimulableHardwareFactory(HardwareFactory):
    """
    A hardware factory for hardware that is simulable. It returns either
    a :py:class:`HardwareDriver` or a :py:class:`HardwareSimulator`,
    depending on the simulation mode.
    """

    def __init__(self, simulation_mode, _driver=None, _simulator=None):
        """
        Create a new instance

        :param simulation_mode: the initial simulation mode of this
            hardware factory
        :type simulation_mode: bool
        :param _driver: For testing purposes, a driver to be returned by
            this factory when not in simulation mode (rather than this
            factory creating one itself)
        :type _driver:
            :py:class:`HardwareDriver`
        :param _simulator: For testing purposes, a simulator to be
            returned by this factory when in simulation mode (rather
            than this factory creating one itself)
        :type _simulator:
            :py:class:`HardwareSimulator`
        """
        self._simulation_mode = simulation_mode
        self._driver = _driver
        self._simulator = _simulator
        self._hardware = (
            self._get_simulator() if simulation_mode else self._get_driver()
        )

    @property
    def hardware(self):
        """
        Return the hardware created by this factory

        :return: the hardware created by this factory
        :rtype: :py:class:`HardwareDriver`
        """
        return self._hardware

    @property
    def simulation_mode(self):
        """
        Return the simulation mode

        :return: the simulation mode
        :rtype: bool
        """
        return self._simulation_mode

    @simulation_mode.setter
    def simulation_mode(self, mode):
        """
        Set the simulation mode

        :param mode: the new simulation mode
        :type mode: bool
        """
        self._simulation_mode = mode
        self._hardware = self._get_simulator() if mode else self._get_driver()

    def _get_driver(self):
        """
        Helper method to return a :py:class:`HardwareDriver` to drive
        the hardware

        :return: a hardware driver to driver the hardware
        :rtype: :py:class:`HardwareDriver`
        """
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def _create_driver(self):
        """
        Helper method to create a :py:class:`HardwareDriver` to drive
        the hardware

        :raises NotImplementedError: because this method needs to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_driver method not implemented."
        )

    def _get_simulator(self):
        """
        Helper method to return a :py:class:`HardwareSimulator` to
        simulate the hardware

        :return: the simulator, just created, to be used by this
            :py:class:`HardwareManager`
        :rtype: :py:class:`HardwareSimulator`
        """
        if self._simulator is None:
            self._simulator = self._create_simulator()
        return self._simulator

    def _create_simulator(self):
        """
        Helper method to create a :py:class:`HardwareSimulator` to drive
        the hardware

        :raises NotImplementedError: because this method needs to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_simulator method not implemented."
        )


class SimulableHardwareManager(HardwareManager):
    """
    A hardware manager mixin for simulable hardware.
    """

    @property
    def simulation_mode(self):
        """
        Property getter for simulation_mode

        :return: the simulation mode
        :rtype: :py:class:`~ska.base.control_model.SimulationMode`
        """
        if self._factory.simulation_mode:
            return SimulationMode.TRUE
        else:
            return SimulationMode.FALSE

    @simulation_mode.setter
    def simulation_mode(self, mode):
        """
        Property setter for simulation_mode

        :param mode: new value for simulation mode
        :type mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        self._factory.simulation_mode = mode == SimulationMode.TRUE
        self._update_health()

    def simulate_connection_failure(self, is_fail):
        """
        Tell the hardware whether or not to simulate connection failure

        :param is_fail: whether to simulate connection failure
        :type is_fail: bool

        :raises ValueError: if not in simulation mode
        """
        if not self._factory.simulation_mode:
            raise ValueError("Cannot simulate failure when not in simulation mode")
        self._factory.hardware.simulate_connection_failure(is_fail)


class OnOffHardwareDriver(HardwareDriver):
    """
    A mixin that adds on() and off() commands to the abstract
    :py:class:`HardwareDriver` class.
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

    def _check_on(self, error=None):
        """
        Helper method to check that the hardware is turned on, and raise
        a suitable error if it is not.

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ValueError: if the hardware is turned off
        """
        self._check_connected()
        if not self.is_on:
            raise ValueError(error or "Hardware is turned off")


class OnOffHardwareSimulator(HardwareSimulator, OnOffHardwareDriver):
    """
    Adds on() and off() commands to the :py:class:`HardwareSimulator`
    base class
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
        self._check_connected()
        self._is_on = False

    def on(self):
        """
        Turn me on
        """
        self._check_connected()
        self._is_on = True

    @property
    def is_on(self):
        """
        Return whether I am on or off

        :return: whether I am on or off
        :rtype: bool
        """
        self._check_connected()
        return self._is_on


class OnOffHardwareManager(HardwareManager):
    """
    A :py:class:`HardwareManager` mixin that adds on() and off()
    commands
    """

    def off(self):
        """
        Turn the hardware off

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if not self._factory.hardware.is_on:
            return
        self._factory.hardware.off()

        self._update_health()
        return not self._factory.hardware.is_on

    def on(self):
        """
        Turn the hardware on

        :return: whether successful
        :rtype: boolean, or None if there was nothing to do.
        """
        if self._factory.hardware.is_on:
            return
        self._factory.hardware.on()

        self._update_health()
        return self._factory.hardware.is_on

    @property
    def is_on(self):
        """
        Whether the hardware is on or not

        :return: whether the hardware is on or not
        :rtype: boolean
        """
        return self._factory.hardware.is_on
