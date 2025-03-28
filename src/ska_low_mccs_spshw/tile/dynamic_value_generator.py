#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a dynamic TPM simulator."""

from __future__ import annotations  # allow forward references in type hints

import math
import random
import threading
import time
from typing import Any, Callable

import scipy.stats
import tango


# pylint: disable=too-few-public-methods
class DynamicValuesGenerator:
    """
    A generator of dynamic values with the following properties.

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

    def __init__(
        self: DynamicValuesGenerator,
        soft_min: float,
        soft_max: float,
        window_size: int = 20,
        in_range_rate: float = 0.95,
    ):
        """
        Create a new instance.

        :param soft_min: a "soft" minimum value. For TANGO device
            attributes, this should be the alarm minimum.
        :param soft_max: a "soft" maximum value. For TANGO device
            attributes, this should be the alarm maximum.
        :param window_size: the size of the sliding window to sum over.
            A value of 1 will give uncorrelated values. Increasing the
            value increases correlation -- a graph of how the value
            changes over time will be smoother. The default is 20.
        :param in_range_rate: the proportion of time during which the
            value should remain within the [soft_min, soft_max] range.
            The default is 0.95. Don't change this to 1.0 unless you
            want the variance to collapse: you'll get the mean of the
            range every time.
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
        self._values = [0.0] + [self._uniform() for i in range(window_size - 1)]

    def __next__(self: DynamicValuesGenerator) -> float:
        """
        Get the next value from this generator.

        :return: the next value from this generator
        """
        self._values = self._values[1:] + [self._uniform()]
        return sum(self._values)


class DynamicValuesUpdater:
    """An dynamic updater of values, for use in a dynamic simulator."""

    def __init__(self: DynamicValuesUpdater, update_rate: float = 1.0) -> None:
        """
        Create a new instance.

        :param update_rate: how often, in seconds, the target values
            should be updated. Defaults to 1 second.
        """
        self._targets: list[tuple] = []

        self._update_rate = update_rate
        self._thread_is_running = False
        self._thread = threading.Thread(target=self._update, args=(), daemon=True)

    def start(self: DynamicValuesUpdater) -> None:
        """Start the updater thread."""
        if not self._thread_is_running:
            self._thread.start()

    def stop(self: DynamicValuesUpdater) -> None:
        """Stop the updater thread."""
        self._thread_is_running = False

    def add_target(
        self: DynamicValuesUpdater,
        generator: Any,  # type: ignore[no-untyped-def]
        callback: Callable,
    ) -> None:
        """
        Add a new target to be updated.

        :param generator: the generator of values to be used as updates
        :param callback: the callback to be called with updates
        """
        # call it immediately, in case attribute initialisation depends on the callback
        callback(next(generator))

        self._targets.append((generator, callback))

    def _update(self: DynamicValuesUpdater) -> None:
        """Thread target that loops over the update targets, pushing new values."""
        with tango.EnsureOmniThread():
            self._thread_is_running = True
            while self._thread_is_running:
                for generator, callback in self._targets:
                    callback(next(generator))
                time.sleep(self._update_rate)

    def __del__(self: DynamicValuesUpdater) -> None:
        """Things to do before this object is garbage collected."""
        self.stop()
