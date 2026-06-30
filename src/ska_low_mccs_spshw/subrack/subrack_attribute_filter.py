#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a subrack attribute filter class."""

from collections import deque

import numpy as np


class SubrackAttributeFilter:
    """The subrack attribute filter."""

    def __init__(self, filter_type: str | None = None, max_samples: int = 5) -> None:
        """
        Initialise the subrack attribute filter.

        :param filter_type: The filter type.
        :param max_samples: The number of samples

        :raises ValueError: If the filter_tupe is not recognised.

        """
        # Check the filter type input
        if filter_type not in [None, "", "mean", "median"]:
            raise ValueError(f"Unrecognised filter type: {filter_type}")

        # Save the filter type
        self._filter_type = filter_type

        # Create the buffer. The deque will gives us a circular buffer with a
        # maximum of 'max_samples' elements
        self._buffer: deque[float] = deque(maxlen=max_samples)

    def clear(self) -> None:
        """Clear the filter buffer."""
        self._buffer.clear()

    def __call__(self, value: float) -> float:
        """
        Filter and get the value.

        :param value: The raw value.

        :returns: The filtered value.

        :raises ValueError: If the filter_tupe is not recognised.

        """
        # Add the value to the buffer
        self._buffer.append(value)

        # Perform an action depending on filter type
        match self._filter_type:
            case None | "":
                return value
            case "mean":
                return float(np.mean(self._buffer))
            case "median":
                return float(np.median(self._buffer))
            case _:
                raise ValueError(f"Unrecognised filter type: {self._filter_type}")
