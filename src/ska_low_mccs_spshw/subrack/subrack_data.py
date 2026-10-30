#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains base data/facts about a subrack."""

from __future__ import annotations  # allow forward references in type hints

import enum

__all__ = ["SubrackData", "FanMode"]


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

    MAX_SUBRACK_FAN_SPEED = 6500.0
    """The maximum fan speed for the subrack.

    This is from the fan's datasheet, at 100% duty cycle, 12V
    """

    FAN_COUNT = 4

    @staticmethod
    def bios_version(board_info: dict) -> list[int]:
        """
        Return the BIOS version reported in the board info.

        :param board_info: the board info reported by the subrack.

        :return: the BIOS version, e.g. [1, 8, 0].
        """
        return [int(x) for x in board_info["SMM"]["bios"].lstrip("v").split(".")]

    @staticmethod
    def supports_tpm_currents(board_info: dict | None) -> bool:
        """
        Return whether the subrack reports TPM currents.

        From API 1.8.0 the SMB no longer reports TPM currents. Until the
        board info has been read, they are assumed to be supported.

        :param board_info: the board info reported by the subrack, if known.

        :return: whether the subrack reports TPM currents.
        """
        return not board_info or SubrackData.bios_version(board_info) < [1, 8, 0]

    @staticmethod
    def supports_power_supply_fan_speed(board_info: dict | None) -> bool:
        """
        Return whether the subrack can set the power supply fan speed.

        API 1.8.0 has no set_power_supply_fan_speed command. Until the
        board info has been read, it is assumed to be supported.

        :param board_info: the board info reported by the subrack, if known.

        :return: whether the subrack can set the power supply fan speed.
        """
        return not board_info or SubrackData.bios_version(board_info) < [1, 8, 0]


class FanMode(enum.IntEnum):
    """Python enumerated type for ``FanMode`` attribute."""

    MANUAL = 0
    """Tango Device accepts commands from all clients."""
    AUTO = 1
