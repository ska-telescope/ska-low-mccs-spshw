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

from math import sqrt
from random import uniform
from threading import Thread
from time import sleep

from scipy.stats import norm
from tango import EnsureOmniThread

from ska_tango_base.control_model import SimulationMode, TestMode
from ska.low.mccs.hardware import (
    ConnectionStatus,
    HardwareDriver,
    HardwareFactory,
    HardwareManager,
)


class DynamicValuesGenerator:
    """
    A generator of dynamic values with the following properties:

    * We want the values to gradually walk around their range rather
      than randomly jumping around. i.e. we want values to be temporally
      correlated. We achieve this by calculating values as a sliding
      window sum of a sequence of independent (uncorrelated) random
      values.
    * The provided range is a "soft" range -- we allow values to walk
      outside this range occasionally. The proportion of time that the
      values should stay within the required range is exposed as an
      argument. This is useful for testing the alarm conditions of TANGO
      attributes: we set the soft range of this generator to the
      attribute's alarm range, and we specify how often the attribute
      should exceed that range and thus start alarming.
    """

    def __init__(self, soft_min, soft_max, window_size=20, in_range_rate=0.95):
        """
        Create a new instance.

        :param soft_min: a "soft" minimum value. For TANGO device
            attributes, this should be the alarm minimum.
        :type soft_min: float
        :param soft_max: a "soft" maximum value. For TANGO device
            attributes, this should be the alarm maximum.
        :type soft_max: float
        :param window_size: the size of the sliding window to sum over.
            A value of 1 will give uncorrelated values. Increasing the
            value increases correlation -- a graph of how the value
            changes over time will be smoother. The default is 20.
        :type window_size: int
        :param in_range_rate: the proportion of time during which the
            value should remain within the [soft_min, soft_max] range.
            The default is 0.95. Don't change this to 1.0 unless you
            want the variance to collapse: you'll get the mean of the
            range every time.
        :type in_range_rate: float
        """

        # For a window size of n, our output values will be the sum of
        # n independent uniformly distributed values. We need to
        # parametrize that uniform distribution so as to get a final
        # distribution that falls between `soft_min` and `soft_max`,
        # `in_range_rate` proportion of the time.
        #
        # The sum of independent random variables drawn from the same
        # uniform distribution has an Irwin-Hall distribution. But this
        # distribution is a PITA to work with. Fortunately, by the
        # central limit theory, it tends to normal as the window size
        # increases, so we can approximate it as normal.
        #
        # First let's calculate the interval into which `in_range_rate`
        # proportion of values will fall, if we were drawing uniform
        # values from the range [-1, 1].
        interval = norm.interval(in_range_rate, scale=sqrt(window_size / 3.0))

        # Now we calculate the scale and offset that will shift that
        # interval to the interval we want: [soft_min, soft_max].
        scale = (soft_max - soft_min) / (2.0 * interval[1])
        offset = (soft_max + soft_min) / (2.0 * window_size)

        # Thus values from this generator, when summed across the window
        # size, will result in values that fall between `soft_min` and
        # `soft_max`, `in_range_rate` proportion of the time.
        self._uniform = lambda: uniform(offset - scale, offset + scale)

        # Generate our initial window of values
        self._values = [None] + [self._uniform() for i in range(window_size - 1)]

    def __next__(self):
        """
        Get the next value from this generator.

        :return: the next value from this generator
        :rtype: float
        """
        self._values = self._values[1:] + [self._uniform()]
        return sum(self._values)


class DynamicValuesUpdater:
    """
    An dynamic updater of values, for use in a dynamic simulator.
    """

    def __init__(self, update_rate=1.0):
        """
        Create a new instance.

        :param update_rate: how often, in seconds, the target values
            should be updated. Defaults to 1 second.
        :type update_rate: float
        """

        self._targets = []

        self._update_rate = update_rate
        self._thread_is_running = False
        self._thread = Thread(target=self._update, args=(), daemon=True)

    def start(self):
        """
        Start the updater thread.
        """
        if not self._thread_is_running:
            self._thread.start()

    def stop(self):
        """
        Stop the updater thread.
        """
        self._thread_is_running = False

    def add_target(self, generator, callback):
        """
        Add a new target to be updated.

        :param generator: the generator of values to be used as updates
        :type generator: :py:class:`.DynamicValuesGenerator`
        :param callback: the callback to be called with updates
        :type callback: callable
        """
        # call it immediately, in case attribute initialisation depends on the callback
        callback(next(generator))

        self._targets.append((generator, callback))

    def _update(self):
        """
        Thread target that loops over the update targets, pushing new
        values.
        """
        with EnsureOmniThread():
            self._thread_is_running = True
            while self._thread_is_running:
                for (generator, callback) in self._targets:
                    callback(next(generator))
                sleep(self._update_rate)

    def __del__(self):
        """
        Things to do before this object is garbage collected.
        """
        self.stop()


class HardwareSimulator(HardwareDriver):
    """
    A base class for hardware simulators.

    It provides a concrete implementation of
    :py:meth:`HardwareDriver.connection_status`, and can be put into a
    failure state via a :py:meth:`simulate_connection_failure` method.
    """

    def __init__(self, is_connectible=True, fail_connect=False):
        """
        Initialise a new instance.

        :param is_connectible: whether it ought to be possible,
            initially, to connect to the hardware being simulation. For
            example, if the hardware we are simulating is not yet
            powered on, then we would not expect to be able to connect
            to the hardware, and failure to do so would not be an error.
        :type is_connectible: bool
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        """
        self._simulate_connection_failure = fail_connect
        super().__init__(is_connectible)

    def _connect(self):
        """
        Establish a connection to the hardware.

        :return: whether successful, or None if already connected
        :rtype: bool
        """
        if self.connection_status == ConnectionStatus.CONNECTED:
            return None
        if self.connection_status == ConnectionStatus.NOT_CONNECTIBLE:
            return False
        return not self._simulate_connection_failure

    def simulate_connection_failure(self, fail):
        """
        Set whether this hardware simulator is simulating failure to
        connect to the hardware.

        :param fail: whether or not this hardware simulator should
            simulate failure to connect to the hardware
        :type fail: bool
        """
        self._simulate_connection_failure = fail
        if self._connection_status != ConnectionStatus.NOT_CONNECTIBLE:
            self._connection_status = (
                ConnectionStatus.NOT_CONNECTED if fail else ConnectionStatus.CONNECTED
            )


class SimulableHardwareFactory(HardwareFactory):
    """
    A hardware factory for hardware that is simulable.

    It returns either a :py:class:`.HardwareDriver` or a
    :py:class:`.HardwareSimulator`, depending on the simulation mode.
    """

    def __init__(
        self,
        simulation_mode,
        test_mode=True,
        _driver=None,
        _static_simulator=None,
        _dynamic_simulator=None,
    ):
        """
        Create a new instance.

        :param simulation_mode: the initial simulation mode of this
            hardware factory
        :type simulation_mode: bool
        :param test_mode: the initial test mode of this
            hardware factory
        :type test_mode: bool
        :param _driver: For testing purposes, a driver to be returned by
            this factory when not in simulation mode (rather than this
            factory creating one itself)
        :type _driver:
            :py:class:`.HardwareDriver`
        :param _static_simulator: For testing purposes, a simulator to
            be returned by this factory when in simulation mode and test
            mode (rather than this factory creating one itself)
        :type _static_simulator:
            :py:class:`.HardwareSimulator`
        :param _dynamic_simulator: For testing purposes, a simulator to
            be returned by this factory when in simulation mode but not
            in test mode (rather than this factory creating one itself)
        :type _dynamic_simulator:
            :py:class:`.HardwareSimulator`
        """
        self._simulation_mode = simulation_mode
        self._test_mode = test_mode

        self._driver = _driver
        self._static_simulator = _static_simulator
        self._dynamic_simulator = _dynamic_simulator

        self._update_hardware()

    def _update_hardware(self):
        """
        Update what this factory returns when asked for its hardware,
        according to the simulation and test modes.
        """
        if self._simulation_mode:
            if self._test_mode:
                self._hardware = self._get_static_simulator()
            else:
                self._hardware = self._get_dynamic_simulator()
        else:
            self._hardware = self._get_driver()

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
        self._update_hardware()

    @property
    def test_mode(self):
        """
        Return the simulation mode.

        :return: the simulation mode
        :rtype: bool
        """
        return self._test_mode

    @test_mode.setter
    def test_mode(self, mode):
        """
        Set the test mode.

        :param mode: the new simulation mode
        :type mode: bool
        """
        self._test_mode = mode
        self._update_hardware()

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

    def _get_static_simulator(self):
        """
        Helper method to return a static :py:class:`.HardwareSimulator`
        to simulate the hardware.

        :return: the simulator, just created, to be used by this
            :py:class:`.HardwareManager`
        :rtype: :py:class:`.HardwareSimulator`
        """
        if self._static_simulator is None:
            self._static_simulator = self._create_static_simulator()
        return self._static_simulator

    def _create_static_simulator(self):
        """
        Helper method to create a static :py:class:`.HardwareSimulator`
        to drive the hardware.

        :raises NotImplementedError: because this method needs to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_static_simulator method not implemented."
        )

    def _get_dynamic_simulator(self):
        """
        Helper method to return a dynamic :py:class:`.HardwareSimulator`
        to simulate the hardware.

        :return: the simulator, just created, to be used by this
            :py:class:`.HardwareManager`
        :rtype: :py:class:`.HardwareSimulator`
        """
        if self._dynamic_simulator is None:
            self._dynamic_simulator = self._create_dynamic_simulator()
        return self._dynamic_simulator

    def _create_dynamic_simulator(self):
        """
        Helper method to create a dynamic :py:class:`.HardwareSimulator`
        to drive the hardware.

        :raises NotImplementedError: because this method needs to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}._create_dynamic_simulator method not implemented."
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
        :rtype: :py:class:`~ska_tango_base.control_model.SimulationMode`
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
        :type mode: :py:class:`~ska_tango_base.control_model.SimulationMode`
        """
        self._factory.simulation_mode = mode == SimulationMode.TRUE
        self._update_health()

    @property
    def test_mode(self):
        """
        Property getter for test_mode.

        :return: the test mode
        :rtype: :py:class:`~ska_tango_base.control_model.TestMode`
        """
        return TestMode.TEST if self._factory.test_mode else TestMode.NONE

    @test_mode.setter
    def test_mode(self, mode):
        """
        Property setter for test_mode.

        :param mode: new value for test mode
        :type mode: :py:class:`~ska_tango_base.control_model.TestMode`
        """
        self._factory.test_mode = mode == TestMode.TEST
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
