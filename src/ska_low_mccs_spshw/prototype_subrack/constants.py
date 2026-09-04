#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Constants and exceptions shared by the prototype subrack modules."""

from __future__ import annotations

from typing import Final

__all__ = [
    "BATCH_ATTRIBUTES",
    "COMMAND_POLL_INTERVAL",
    "COMMAND_TIMEOUT",
    "FILTERED_ATTRIBUTES",
    "HttpError",
    "LOCK_TIMEOUT",
    "LOCK_WARNING",
    "MIN_HEALTH_BIOS_VERSION",
    "MIN_PWM_DUTY_FRACTION",
    "RequestError",
]


class HttpError(Exception):
    """The board answered, but with an HTTP error status."""


class RequestError(Exception):
    """The request never reached the board."""


BATCH_ATTRIBUTES: Final[tuple[str, ...]] = (
    "tpm_present",
    "tpm_on_off",
    "backplane_temperatures",
    "board_temperatures",
    "board_current",
    "cpld_pll_locked",
    "power_supply_currents",
    "power_supply_fan_speeds",
    "power_supply_powers",
    "power_supply_voltages",
    "subrack_fan_speeds",
    "subrack_fan_speeds_percent",
    "subrack_fan_mode",
    "subrack_pll_locked",
    "subrack_timestamp",
    "tpm_currents",
    "tpm_powers",
    "tpm_voltages",
    "board_info",
)
"""The hardware read keys fetched on every poll.

``tpm_temperatures`` is absent because the SMB does not implement it.
"""

FILTERED_ATTRIBUTES: Final[tuple[str, ...]] = (
    "tpm_currents",
    "tpm_powers",
    "tpm_voltages",
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

MIN_HEALTH_BIOS_VERSION: Final = (1, 6, 0)
"""The lowest SMB BIOS version that supports ``get_health_status``."""

MIN_PWM_DUTY_FRACTION: Final = 0.1
"""The floor applied to pwm duty when the fan rpm estimate scales up.

A 0% pwm duty still turns the fans at about 1200 rpm.
"""
