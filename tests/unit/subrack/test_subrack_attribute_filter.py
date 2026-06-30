#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides test for the subrack attribute filter class."""

import statistics

import pytest

from ska_low_mccs_spshw.subrack.subrack_attribute_filter import SubrackAttributeFilter


@pytest.mark.parametrize("filter_type", [None, "", "mean", "median"])
def test_subrack_attribute_filter(filter_type: str | None) -> None:
    """
    Test the subrack attribute filter.

    :param filter_type: Test each filter type.

    """
    # Create the filter
    attribute_filter = SubrackAttributeFilter(filter_type, max_samples=5)

    values: list[float] = []
    for x in range(10):
        value = attribute_filter(x)

        # Ensure max of 5 values
        values = values[-4:] + [x]
        assert len(values) <= 5
        assert len(values) == len(attribute_filter._buffer)
        assert all(a == b for a, b in zip(values, attribute_filter._buffer))

        # Check expected result
        match filter_type:
            case None, "":
                assert value == x
            case "mean":
                assert value == statistics.mean(values)
            case "median":
                assert value == statistics.median(values)

    # Check empty
    attribute_filter.clear()
    assert len(attribute_filter._buffer) == 0
