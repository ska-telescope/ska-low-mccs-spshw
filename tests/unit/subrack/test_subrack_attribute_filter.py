#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides test for the subrack attribute filter class."""

import statistics

import numpy as np
import pytest

from ska_low_mccs_spshw.subrack.subrack_attribute_filter import SubrackAttributeFilter


@pytest.mark.parametrize("filter_type", [None, "", "mean", "median"])
def test_subrack_attribute_filter_with_scalars(filter_type: str | None) -> None:
    """
    Test the subrack attribute filter.

    :param filter_type: Test each filter type.

    """
    # Create the filter
    attribute_filter = SubrackAttributeFilter(filter_type, max_samples=5)

    # Test with float values
    values: list[float] = []
    for x in range(10):
        value = attribute_filter(x)

        # Ensure max of 5 values
        values = values[-4:] + [x]
        assert len(values) <= 5
        assert len(values) == len(attribute_filter._buffer)
        assert pytest.approx(values) == attribute_filter._buffer

        # Check expected result
        match filter_type:
            case None, "":
                assert pytest.approx(value) == x
            case "mean":
                assert pytest.approx(value) == statistics.mean(values)
            case "median":
                assert pytest.approx(value) == statistics.median(values)

    # Check empty
    attribute_filter.clear()
    assert len(attribute_filter._buffer) == 0


@pytest.mark.parametrize("filter_type", [None, "", "none", "mean", "median"])
def test_subrack_attribute_filter_with_arrays(filter_type: str | None) -> None:
    """
    Test the subrack attribute filter.

    :param filter_type: Test each filter type.

    """
    # Create the filter
    attribute_filter = SubrackAttributeFilter(filter_type, max_samples=5)

    # Test with a list of float values
    values: list[list[float]] = []
    for x in range(10):
        value = attribute_filter(np.array([x for i in range(8)]))

        # Ensure max of 5 values
        values = values[-4:] + [[x for i in range(8)]]
        assert len(values) <= 5
        assert len(values) == len(attribute_filter._buffer)
        for a, b in zip(values, attribute_filter._buffer):
            assert pytest.approx(a) == b

        # Check expected result
        match filter_type:
            case None | "" | "none":
                assert pytest.approx(value) == x
            case "mean":
                assert pytest.approx(value) == [
                    statistics.mean(v) for v in zip(*values)
                ]
            case "median":
                assert pytest.approx(value) == [
                    statistics.median(v) for v in zip(*values)
                ]

    # Check empty
    attribute_filter.clear()
    assert len(attribute_filter._buffer) == 0
