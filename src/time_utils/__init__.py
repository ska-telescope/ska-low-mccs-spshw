#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Collection of time conversion functions.

Common time conversion functions that can be used in code
and tests to ensure consistent conversion between time
formats.
"""


__all__ = [
    "float_epoch_from_str_utc_time",
    "str_from_float_epoch_utc_time",
]

from .time_conversion import (
    float_epoch_from_str_utc_time,
    str_from_float_epoch_utc_time,
)
