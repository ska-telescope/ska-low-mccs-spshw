# type: ignore
# -*- coding: utf-8 -*-
"""An implementation of a dynamic TPM simulator."""
from __future__ import annotations


import logging
import math
import random
import threading
import time

import scipy.stats
import tango

from ska_low_mccs.tile.base_tpm_simulator import BaseTpmSimulator


class _DynamicValuesGenerator:
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
        interval = scipy.stats.norm.interval(
            in_range_rate, scale=math.sqrt(window_size / 3.0)
        )

        # Now we calculate the scale and offset that will shift that
        # interval to the interval we want: [soft_min, soft_max].
        scale = (soft_max - soft_min) / (2.0 * interval[1])
        offset = (soft_max + soft_min) / (2.0 * window_size)

        # Thus values from this generator, when summed across the window
        # size, will result in values that fall between `soft_min` and
        # `soft_max`, `in_range_rate` proportion of the time.
        self._uniform = lambda: random.uniform(offset - scale, offset + scale)

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


class _DynamicValuesUpdater:
    """An dynamic updater of values, for use in a dynamic simulator."""

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
        self._thread = threading.Thread(target=self._update, args=(), daemon=True)

    def start(self):
        """Start the updater thread."""
        if not self._thread_is_running:
            self._thread.start()

    def stop(self):
        """Stop the updater thread."""
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
        """Thread target that loops over the update targets, pushing new values."""
        with tango.EnsureOmniThread():
            self._thread_is_running = True
            while self._thread_is_running:
                for (generator, callback) in self._targets:
                    callback(next(generator))
                time.sleep(self._update_rate)

    def __del__(self):
        """Things to do before this object is garbage collected."""
        self.stop()


class DynamicTpmSimulator(BaseTpmSimulator):
    """
    A simulator for a TPM, with dynamic value updates to certain attributes.

    This is useful for demoing.
    """

    def __init__(
        self: DynamicTpmSimulator,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new TPM simulator instance.

        :param logger: a logger for this simulator to use
        """
        self._voltage = None
        self._current = None
        self._board_temperature = None
        self._fpga1_temperature = None
        self._fpga2_temperature = None

        self._updater = _DynamicValuesUpdater(1.0)
        self._updater.add_target(
            _DynamicValuesGenerator(4.55, 5.45), self._voltage_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(0.05, 2.95), self._current_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0), self._board_temperature_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0), self._fpga1_temperature_changed
        )
        self._updater.add_target(
            _DynamicValuesGenerator(16.0, 47.0), self._fpga2_temperature_changed
        )
        self._updater.start()

        super().__init__(logger)

    def __del__(self):
        """Garbage-collection hook."""
        self._updater.stop()

    @property
    def board_temperature(self):
        """
        Return the temperature of the TPM.

        :return: the temperature of the TPM
        :rtype: float
        """
        return self._board_temperature

    def _board_temperature_changed(self, board_temperature):
        """
        Callback called when the board temperature changes.

        :param board_temperature: the new board temperature
        :type board_temperature: float
        """
        self._board_temperature = board_temperature

    @property
    def voltage(self):
        """
        Return the voltage of the TPM.

        :return: the voltage of the TPM
        :rtype: float
        """
        return self._voltage

    def _voltage_changed(self, voltage):
        """
        Callback called when the voltage changes.

        :param voltage: the new voltage
        :type voltage: float
        """
        self._voltage = voltage

    @property
    def current(self):
        """
        Return the current of the TPM.

        :return: the current of the TPM
        :rtype: float
        """
        return self._current

    def _current_changed(self, current):
        """
        Callback called when the current changes.

        :param current: the new current
        :type current: float
        """
        self._current = current

    @property
    def fpga1_temperature(self):
        """
        Return the temperature of FPGA 1.

        :return: the temperature of FPGA 1
        :rtype: float
        """
        return self._fpga1_temperature

    def _fpga1_temperature_changed(self, fpga1_temperature):
        """
        Callback called when the FPGA1 temperature changes.

        :param fpga1_temperature: the new FPGA1 temperature
        :type fpga1_temperature: float
        """
        self._fpga1_temperature = fpga1_temperature

    @property
    def fpga2_temperature(self):
        """
        Return the temperature of FPGA 2.

        :return: the temperature of FPGA 2
        :rtype: float
        """
        return self._fpga2_temperature

    def _fpga2_temperature_changed(self, fpga2_temperature):
        """
        Callback called when the FPGA2 temperature changes.

        :param fpga2_temperature: the new FPGA2 temperature
        :type fpga2_temperature: float
        """
        self._fpga2_temperature = fpga2_temperature
