# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module contains base data/facts about a subrack."""


from __future__ import annotations  # allow forward references in type hints


__all__ = ["SubrackData"]


class SubrackData:
    """
    This class contain data/facts about a subrack that are needed by multiple classes.

    For example, the fact that a subrack contains 8 TPM bays is
    something that a subrack driver may need to know, a subrack Tango
    device may need to know, and a subrack simulator certainly needs to
    know. So rather than store this fact in three separate places, we
    store it here.
    """

    TPM_BAY_COUNT = 8
    """The number of TPM bays (some bays may be empty)"""

    MAX_SUBRACK_FAN_SPEED = 8000.0
    """The maximum fan speed for the subrack."""
