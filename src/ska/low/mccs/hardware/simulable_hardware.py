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
from scipy.stats import norm

from ska.base.control_model import SimulationMode
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
      window sum of a sequence of random values.
    * The provided range is a "soft" range -- we allow values to walk
      outside this range occasionally. The proportion of time that the
      values should stay within the required range is exposed as an
      argument. This is useful for testing the alarm conditions of TANGO
      attributes: we set the soft range of this generator to the
      attribute's alarm range, and we specify how often the attribute
      should exceed that range and start alarming.
    """

    def __init__(self, softmin, softmax, window_size, in_range_rate=0.9):
        """
        Create a new instance
        """

        # We start by from the assumption that we'll be drawing uniform
        # values from the range [-1, 1]. Our output values will be the
        # sum of these uniform values across the sliding window size.
        # The sum of independent random variables drawn from the same
        # uniform distribution actually has an Irwin-Hall distribution,
        # but by the central limit theory, this tends towards normal as
        # the window_size increases. So we'll approximate it as normal.
        # First let's calculate the interval into which `in_range_rate`
        # proportion of values will fall.
        interval = norm.interval(in_range_rate, scale=sqrt(window_size/3.0))
        print(f"Interval: {interval}")


        # We want to select the range of our uniform values so that the
        # above interval is [softmin, softmax]. So let's scale:
        scale = (softmax-softmin)/(2.0 * interval[1])
        print(f"Scale: {scale}")

        # And now calculate the offset
        offset = (softmax+softmin)/(2.0 * window_size)
        print(f"Offset: {offset}")

        # Values from this generator, when summed across the window
        # size, should generate values that fall between `softmin` and
        # `softmax`, `in_range_rate` proportion of the time.
        bounds = (offset-scale, offset+scale)
        print(f"Bounds: {bounds}")
        self._uniform = lambda: uniform(*bounds)

        # Generate our initial window of values
        self._values = [self._uniform() for i in range(window_size)]

    def __next__(self):
        self._values = self._values[1:] + [self._uniform()]
        return sum(self._values)


class DynamicValuesUpdater:
    def __init__(
        self,
        softmin,
        softmax,
        update_callback,
        update_rate=1.0,
        window_size=10,
        in_range_rate=0.9
    ):
        self._callback = update_callback

        self._generator = DynamicValuesGenerator(
            softmin, softmax, window_size, in_range_rate
        )

        self._interrupted = False
        self._thread = threading.Thread(
            target=self._update, args=()
        )


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
