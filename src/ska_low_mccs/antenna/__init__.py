# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This subpackage implements antenna functionality for MCCS."""

__all__ = [
    "MccsAntenna",
    "antenna_device",
    "demo_antenna_device",
]

from .antenna_device import MccsAntenna  # type: ignore[attr-defined]
