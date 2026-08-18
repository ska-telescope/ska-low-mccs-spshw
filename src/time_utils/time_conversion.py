#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Simple functions to convert from-to unix epoch time.

Re-usuable code that likely needs to be imported into
tests as well to ensure consistent conversion from
epoch to string and back again.
"""

import math
from datetime import datetime, timezone

__all__ = [
    "float_epoch_from_str_utc_time",
    "integer_epoch_from_str_utc_time",
    "str_from_integer_epoch_utc_time",
    "str_from_float_epoch_utc_time",
]

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def float_epoch_from_str_utc_time(utc_time: str) -> float:
    """
    Return the (sub-second precision) Unix epoch of the specified time.

    Does not account for leap seconds, utc_time must avoid them.

    :param utc_time: Utc Time in standard rfc3339 format
    :return: Unix epoch of the specified time. -1.0 if error
    """
    try:
        dt = datetime.strptime(utc_time, RFC_FORMAT)
        timestamp = dt.replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return -1.0

    # TODO: I think this should raise an exception since it's not
    # TODO: valid data for the SKAO system
    if timestamp < 0:
        return -1.0

    return timestamp


def integer_epoch_from_str_utc_time(utc_time: str) -> int:
    """
    Return first timestamp (Unix) second after specified time.

    Does not account for leap seconds, utc_time must avoid them.

    :param utc_time: Utc Time in standard rfc3339 format
    :return: Unix timestamp equal or after specified time. -1 if error
    """
    timestamp = float_epoch_from_str_utc_time(utc_time)

    if timestamp < 0:
        return -1

    return math.ceil(timestamp)


def str_from_integer_epoch_utc_time(timestamp: int) -> str:
    """
    Format a time expressed as an integer epoch value into ISO-8601.

    Format a time expressed as an interger epoch value into a properly
    formatted ISO-8601 (RFC3339) string, e.g. 2021-03-02T12:34.56.789000Z.

    :param timestamp: Unix timestamp of the (integer) reference time
    :return: ISO-8601 formatted time
    :rtype: str
    :raises ValueError: if the timestamp is invalid
    """
    if timestamp < 0:
        raise ValueError()

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(RFC_FORMAT)


def str_from_float_epoch_utc_time(timestamp: float) -> str:
    """
    Format a time expressed as a frame count into ISO-8601.

    Format a time expressed as a frame count into a properly formatted ISO-8601
    (RFC3339) string, e.g. 2021-03-02T12:34.56.789000Z.

    :param timestamp: Unix timestamp of the (integer) reference time
    :return: ISO-8601 formatted time
    :rtype: str
    :raises ValueError: if the timestamp is invalid
    """
    if timestamp < 0:
        raise ValueError()

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(RFC_FORMAT)
