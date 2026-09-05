#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Constants and exceptions shared by the prototype subrack modules."""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = [
    "BATCH_ATTRIBUTES",
    "COMMAND_POLL_INTERVAL",
    "COMMAND_TIMEOUT",
    "ClientCommand",
    "DerivedKey",
    "FILTERED_ATTRIBUTES",
    "HttpError",
    "LOCK_TIMEOUT",
    "LOCK_WARNING",
    "MIN_PWM_DUTY_FRACTION",
    "ReadKey",
    "RequestError",
]


class HttpError(Exception):
    """The board answered, but with an HTTP error status."""


class RequestError(Exception):
    """The request never reached the board."""


class ReadKey(str, Enum):
    """
    The hardware read keys the SMB understands, in the order they are polled.

    A member is a ``str``, so it indexes a poll response and reaches the board
    unchanged. ``tpm_temperatures`` is absent because the SMB does not
    implement it.
    """

    TPM_PRESENT = "tpm_present"
    TPM_ON_OFF = "tpm_on_off"
    BACKPLANE_TEMPERATURES = "backplane_temperatures"
    BOARD_TEMPERATURES = "board_temperatures"
    BOARD_CURRENT = "board_current"
    CPLD_PLL_LOCKED = "cpld_pll_locked"
    POWER_SUPPLY_CURRENTS = "power_supply_currents"
    POWER_SUPPLY_FAN_SPEEDS = "power_supply_fan_speeds"
    POWER_SUPPLY_POWERS = "power_supply_powers"
    POWER_SUPPLY_VOLTAGES = "power_supply_voltages"
    SUBRACK_FAN_SPEEDS = "subrack_fan_speeds"
    SUBRACK_FAN_SPEEDS_PERCENT = "subrack_fan_speeds_percent"
    SUBRACK_FAN_MODE = "subrack_fan_mode"
    SUBRACK_PLL_LOCKED = "subrack_pll_locked"
    SUBRACK_TIMESTAMP = "subrack_timestamp"
    TPM_CURRENTS = "tpm_currents"
    TPM_POWERS = "tpm_powers"
    TPM_VOLTAGES = "tpm_voltages"
    BOARD_INFO = "board_info"


class DerivedKey(str, Enum):
    """The keys computed from a poll rather than read from the board."""

    SUBRACK_MAX_FAN_SPEEDS = "subrack_max_fan_speeds"


class ClientCommand(str, Enum):
    """
    The board commands this client issues on its own behalf.

    A device passes any other command straight through, so this is not the
    full set the board accepts.
    """

    GET_HEALTH_STATUS = "get_health_status"
    COMMAND_COMPLETED = "command_completed"
    ABORT_COMMAND = "abort_command"


BATCH_ATTRIBUTES: Final[tuple[str, ...]] = tuple(key.value for key in ReadKey)
"""The hardware read keys fetched on every poll."""

FILTERED_ATTRIBUTES: Final[tuple[str, ...]] = (
    ReadKey.TPM_CURRENTS.value,
    ReadKey.TPM_POWERS.value,
    ReadKey.TPM_VOLTAGES.value,
)
"""The read keys that pass through the noise filter."""

COMMAND_TIMEOUT: Final = 30.0
"""How long, in seconds, to wait for an asynchronous board command."""

LOCK_TIMEOUT: Final = 60.0
"""How long, in seconds, to wait for the client lock before giving up.

Longer than ``COMMAND_TIMEOUT``, so a legitimate asynchronous command never
causes a poll to time out. A wait this long means the board has stalled.
"""

LOCK_WARNING: Final = 5.0
"""How long, in seconds, a client lock hold must exceed to be logged.

Longer than a healthy attribute sweep, which is about one second against a
board on a normal network, and far shorter than a stall.
"""

COMMAND_POLL_INTERVAL: Final = 0.1
"""How long, in seconds, between ``command_completed`` probes."""

MIN_PWM_DUTY_FRACTION: Final = 0.1
"""The floor applied to pwm duty when the fan rpm estimate scales up.

A 0% pwm duty still turns the fans at about 1200 rpm.
"""
