# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This subpackage implements MCCS controller functionality.

It includes a controller Tango device and a CLI.
"""


__all__ = [
    "MccsController",
    "ControllerResourceManager",
    "controller_device",
    "demo_controller_device",
]

from .controller_device import (  # type: ignore[attr-defined]
    MccsController,
    ControllerResourceManager,
)
