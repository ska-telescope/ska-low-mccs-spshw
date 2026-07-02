#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a subrack attribute filter class."""

from collections import deque
from typing import Any

import numpy as np
from numpy.typing import NDArray


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
        if filter_type not in [None, "None", "none", "mean", "median"]:
            raise ValueError(f"Unrecognised filter type: '{filter_type}'")

        # Save the filter type
        self._filter_type = filter_type

        # Create the buffer. The deque will gives us a circular buffer with a
        # maximum of 'max_samples' elements
        self._buffer: deque[Any] = deque(maxlen=max_samples)

    def clear(self) -> None:
        """Clear the filter buffer."""
        self._buffer.clear()

    def __call__(
        self, value: float | NDArray[np.floating]
    ) -> float | NDArray[np.floating]:
        """
        Filter and get the value.

        If the attribute is an array, filtering is done over the each element

        :param value: The raw value.

        :returns: The filtered value.

        :raises ValueError: If the filter_tupe is not recognised.

        """
        # If the value is None or there are nans reset the buffer
        if value is None or np.isnan(value).any():
            self._buffer.clear()
            return value

        # Add the value to the buffer
        self._buffer.append(value)

        # Perform an action depending on filter type
        match self._filter_type:
            case None | "None" | "none":
                return value
            case "mean":
                return np.mean(self._buffer, axis=0)
            case "median":
                return np.median(self._buffer, axis=0)
            case _:
                raise ValueError(f"Unrecognised filter type: '{self._filter_type}'")
