#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a subrack attribute filter class."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

import numpy as np
from numpy.typing import NDArray


class SubrackAttributeFilter:
    """The subrack attribute filter."""

    def __init__(
        self,
        filter_type: str | None = None,
        max_samples: int = 5,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialise the subrack attribute filter.

        :param filter_type: The filter type.
        :param max_samples: The number of samples
        :param logger: The logger object

        """
        # Set the logger
        self.logger = logger or logging.getLogger()

        # Save the filter type
        self.filter_type = str(filter_type)

        # Create the buffer. The deque will gives us a circular buffer with a
        # maximum of 'max_samples' elements
        self._buffer: deque[Any] = deque(maxlen=max_samples)

    @property
    def filter_type(self) -> str:
        """
        Get the filter type.

        :returns: The filter type.

        """
        return self._filter_type

    @filter_type.setter
    def filter_type(self, filter_type: str) -> None:
        """
        Set the filter type.

        If the filter type is not one of the allowed filter types ('', none',
        'mean', 'median') then the filter type is set to 'none' and a warning
        is output to the log.

        :param filter_type: The filter type.

        """
        # The allowed filter types
        allowed_filter_types = ["", "none", "mean", "median"]

        # Check the filter type input. If the filter type is not in the list of
        # allowed filter types, we set it to 'none'. This means that if there
        # is a mis-configuration the filter is set to no filter. We also output
        # a warning to make this visible in the logs.
        if filter_type.casefold() not in allowed_filter_types:
            self.logger.warning(
                f"Expected filter type in {allowed_filter_types}, got "
                f"'{filter_type}'. Setting filter type to 'none'."
            )
            filter_type = "none"

        # Set the filter type
        self._filter_type = filter_type

    def clear(self) -> None:
        """Clear the filter buffer."""
        self._buffer.clear()

    def __call__(
        self, value: float | NDArray[np.floating] | None
    ) -> float | NDArray[np.floating] | None:
        """
        Filter and get the value.

        If the attribute is an array, filtering is done over each element. In
        the subrack, when attributes are none their quality is set to INVALID
        so, in the case that the attribute value is None here, the filter
        buffer cache is cleared.

        :param value: The raw value.

        :returns: The filtered value.

        :raises ValueError: If the filter_type is not recognised.

        """
        # If the value is None reset the buffer
        if value is None:
            self._buffer.clear()
            return value

        # Add the value to the buffer
        self._buffer.append(value)

        # Perform an action depending on filter type. When we have NaNs, we
        # ignore them and try to return a valid number if we can.
        match self._filter_type.casefold():
            case "" | "none":
                return value
            case "mean":
                return np.nanmean(self._buffer, axis=0)
            case "median":
                return np.nanmedian(self._buffer, axis=0)
            case _:
                raise ValueError(f"Unrecognised filter type: '{self._filter_type}'")
