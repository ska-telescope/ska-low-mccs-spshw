#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains exception codes."""
from __future__ import annotations

from typing import Any


class HardwareVerificationError(Exception):
    """Raised when a hardware value does not match the expected value after setting."""

    def __init__(
        self: HardwareVerificationError,
        expected: Any,
        actual: Any,
        message: str | None = None,
    ) -> None:
        """
        Initialise a new HardwareVerificationError message.

        :param expected: the expected value read from hardware.
        :param actual: the actual value read from hardware.
        :param message: a bespoke message to override the default message.
        """
        if message is None:
            message = f"Hardware verification failed: expected {expected}, got {actual}"
        super().__init__(message)
        self.expected = expected
        self.actual = actual
