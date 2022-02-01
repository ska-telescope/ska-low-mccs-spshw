# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
A simulator for a testing subrack management board.

For unit testing purposes, we don't want any emulated delays to increase
our testing time. This class is here to allow certain methods to be
overwritten for use in the unit testing environment.
"""

from __future__ import annotations  # allow forward references in type hints

from ska_low_mccs.subrack import SubrackSimulator

__all__ = ["TestingSubrackSimulator"]


class TestingSubrackSimulator(SubrackSimulator):
    """A simulator of a testing subrack management board."""

    def _emulate_hardware_delay(self: TestingSubrackSimulator) -> None:
        """Overwritten method so we don't emulate any hardware delay."""
        pass
