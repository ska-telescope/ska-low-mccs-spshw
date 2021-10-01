# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
A simulator for a testing subrack management board.

To be used specifically in a K8s deployment.

This class will override certain methods to emulate delays that real
hardware would introduce, thus providing a way to test the software
without real hardware.
"""

from __future__ import annotations  # allow forward references in type hints

from ska_low_mccs.subrack import SubrackSimulator
from time import sleep

__all__ = ["TestingSubrackSimulator"]


class TestingSubrackSimulator(SubrackSimulator):
    """A simulator of a testing subrack management board."""

    def _emulate_hardware_delay(self: TestingSubrackSimulator) -> None:
        """Specialist implementation to emulate a real hardware delay."""
        for i in range(1, 5):
            if self._component_progress_changed_callback:
                self._component_progress_changed_callback(i * 20)
            sleep(1.0)
