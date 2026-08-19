# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Tests for time conversion functions."""
import pytest

from time_utils.time_conversion import (
    float_epoch_from_str_utc_time,
    str_from_float_epoch_utc_time,
    str_from_integer_epoch_utc_time,
)

TEST_VALID_EPOCH_INT = 1785862384
TEST_VALID_EPOCH_FLOAT = 1785862384.0668576
# Some precision is lost in conversion to a string
TEST_VALID_EPOCH_FLOAT_LOST_PRECISION = 1785862384.066858

TEST_VALID_EPOCH_STRING_INT = "2026-08-04T16:53:04.000000Z"
TEST_VALID_EPOCH_STRING_FLOAT = "2026-08-04T16:53:04.066858Z"
TEST_PRE_1970_EPOCH_STRING = "1969-12-31T23:59:59.000000Z"


def test_epoch_from_string_garbage() -> None:
    """Cause the parsing to fail with a bad string."""
    assert float_epoch_from_str_utc_time("wibble") == -1


def test_epoch_from_string_valid_string_int() -> None:
    """Parse a valid integer time string."""
    assert (
        float_epoch_from_str_utc_time(TEST_VALID_EPOCH_STRING_INT)
        == TEST_VALID_EPOCH_INT
    )


def test_epoch_from_string_valid_string_float() -> None:
    """Parse a valid float time string."""
    assert (
        float_epoch_from_str_utc_time(TEST_VALID_EPOCH_STRING_FLOAT)
        == TEST_VALID_EPOCH_FLOAT_LOST_PRECISION
    )


def test_epoch_from_pre_1970_string() -> None:
    """Check pre 1970 string."""
    assert float_epoch_from_str_utc_time(TEST_PRE_1970_EPOCH_STRING) == -1


def test_string_from_epoch_invalid_number() -> None:
    """Negative epoch raises an error."""
    with pytest.raises(ValueError):
        str_from_integer_epoch_utc_time(-1)


def test_string_from_epoch_valid_int() -> None:
    """Valid epoch value."""
    assert (
        str_from_integer_epoch_utc_time(TEST_VALID_EPOCH_INT)
        == TEST_VALID_EPOCH_STRING_INT
    )


def test_round_trip_from_int() -> None:
    """Check conversion to string and then back again works."""
    epoch_to_string = str_from_integer_epoch_utc_time(TEST_VALID_EPOCH_INT)
    epoch_from_string = float_epoch_from_str_utc_time(epoch_to_string)
    assert epoch_from_string == TEST_VALID_EPOCH_INT


def test_string_from_float_invalid_number() -> None:
    """Negative float epoch value raises an error."""
    with pytest.raises(ValueError):
        str_from_float_epoch_utc_time(-1.0)


def test_string_from_epoch_valid_float() -> None:
    """Valid float epoch value."""
    assert (
        str_from_float_epoch_utc_time(TEST_VALID_EPOCH_FLOAT)
        == TEST_VALID_EPOCH_STRING_FLOAT
    )


def test_round_trip_from_float() -> None:
    """Check conversion to string and then back again works."""
    epoch_to_string = str_from_float_epoch_utc_time(TEST_VALID_EPOCH_FLOAT)
    epoch_from_string = float_epoch_from_str_utc_time(epoch_to_string)
    assert epoch_from_string == TEST_VALID_EPOCH_FLOAT_LOST_PRECISION
