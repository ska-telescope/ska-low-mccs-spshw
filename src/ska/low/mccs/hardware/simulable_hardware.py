# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements simulation functionality for hardware in the MCCS
subsystem.
"""
__all__ = ["HardwareSimulator", "SimulableHardwareFactory", "SimulableHardwareManager"]

from ska.base.control_model import SimulationMode

from ska.low.mccs.hardware import HardwareDriver, HardwareFactory, HardwareManager


class HardwareSimulator(HardwareDriver):
    """
    A base class for hardware simulators.

    It provdes a concreate implementation of
    :py:meth:`HardwareDriver.is_connected`, and can be put into a
    failure state via a :py:meth:`simulate_connection_failure` method.
    """

    def __init__(self, fail_connect=False):
        """
        Initialise a new instance.

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
        connect to the hardware.

        :param fail: whether or not this hardware simulator should
            simulate failure to connect to the hardware
        :type fail: bool
        """
        self._is_connected = not fail


class SimulableHardwareFactory(HardwareFactory):
    """
    A hardware factory for hardware that is simulable.

    It returns either a :py:class:`.HardwareDriver` or a
    :py:class:`.HardwareSimulator`, depending on the simulation mode.
    """

    def __init__(self, simulation_mode, _driver=None, _simulator=None):
        """
        Create a new instance.

        :param simulation_mode: the initial simulation mode of this
            hardware factory
        :type simulation_mode: bool
        :param _driver: For testing purposes, a driver to be returned by
            this factory when not in simulation mode (rather than this
            factory creating one itself)
        :type _driver:
            :py:class:`.HardwareDriver`
        :param _simulator: For testing purposes, a simulator to be
            returned by this factory when in simulation mode (rather
            than this factory creating one itself)
        :type _simulator:
            :py:class:`.HardwareSimulator`
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
        Return the hardware created by this factory.

        :return: the hardware created by this factory
        :rtype: :py:class:`.HardwareDriver`
        """
        return self._hardware

    @property
    def simulation_mode(self):
        """
        Return the simulation mode.

        :return: the simulation mode
        :rtype: bool
        """
        return self._simulation_mode

    @simulation_mode.setter
    def simulation_mode(self, mode):
        """
        Set the simulation mode.

        :param mode: the new simulation mode
        :type mode: bool
        """
        self._simulation_mode = mode
        self._hardware = self._get_simulator() if mode else self._get_driver()

    def _get_driver(self):
        """
        Helper method to return a :py:class:`.HardwareDriver` to drive
        the hardware.

        :return: a hardware driver to driver the hardware
        :rtype: :py:class:`.HardwareDriver`
        """
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def _create_driver(self):
        """
        Helper method to create a :py:class:`.HardwareDriver` to drive
        the hardware.

        :raises NotImplementedError: because this method needs to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_driver method not implemented."
        )

    def _get_simulator(self):
        """
        Helper method to return a :py:class:`.HardwareSimulator` to
        simulate the hardware.

        :return: the simulator, just created, to be used by this
            :py:class:`.HardwareManager`
        :rtype: :py:class:`.HardwareSimulator`
        """
        if self._simulator is None:
            self._simulator = self._create_simulator()
        return self._simulator

    def _create_simulator(self):
        """
        Helper method to create a :py:class:`.HardwareSimulator` to
        drive the hardware.

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
        Property getter for simulation_mode.

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
        Property setter for simulation_mode.

        :param mode: new value for simulation mode
        :type mode: :py:class:`~ska.base.control_model.SimulationMode`
        """
        self._factory.simulation_mode = mode == SimulationMode.TRUE
        self._update_health()

    def simulate_connection_failure(self, is_fail):
        """
        Tell the hardware whether or not to simulate connection failure.

        :param is_fail: whether to simulate connection failure
        :type is_fail: bool

        :raises ValueError: if not in simulation mode
        """
        if not self._factory.simulation_mode:
            raise ValueError("Cannot simulate failure when not in simulation mode")
        self._factory.hardware.simulate_connection_failure(is_fail)
