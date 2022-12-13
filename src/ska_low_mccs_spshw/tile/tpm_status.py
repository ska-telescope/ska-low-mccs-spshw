# type: ignore
# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements custom types for tiles."""

from __future__ import annotations

import enum

__all__ = ["TpmStatus"]


class TpmStatus(enum.IntEnum):
    """
    Enumerated type for tile status.

    Used in initialisation to know what long running commands have been
    issued
    """

    UNKNOWN = 0
    """ The status is not known """

    OFF = 1
    """ The TPM is not powered """

    UNCONNECTED = 2
    """ The TPM is not connected """

    UNPROGRAMMED = 3
    """ The TPM is powered on but FPGAS are not programmed """

    PROGRAMMED = 4
    """ The TPM is powered on and FPGAS are programmed """

    INITIALISED = 5
    """ Initialise command has been issued """

    SYNCHRONISED = 6
    """ Time has been synchronised with UTC, timestamp is valid """

    """ TODO: More status values to come, for complete configuration in station """
