#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This subpackage implements a prototype SPS subrack Tango device."""

__all__ = [
    "MccsSubrackPrototype",
    "main",
]

from .prototype_subrack_device import MccsSubrackPrototype, main
