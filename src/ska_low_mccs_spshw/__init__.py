#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This package implements SKA Low's MCCS SPSHW subsystem.

The Monitoring Control and Calibration (MCCS) subsystem is responsible
for, amongst other things, monitoring and control of LFAA.
"""

__version__ = "18.1.0"
__version_info__ = str(
    (
        "ska-low-mccs-spshw",
        __version__,
        "This package implements SKA Low's MCCS SPSHW subsystem.",
    )
).replace("'", "")

__all__ = [
    "MccsPrototypeSubrack",
    "MccsSubrack",  # pylint: disable=undefined-all-variable
    "MccsTile",
    "SpsStation",
    "MccsPdu",
    "PowerMarshaller",
    "SUBRACK_IMPLEMENTATION_ENV_VAR",
    "server_classes",
    "subrack_class",
    "version",
]

import os
from typing import Any

import tango.server

from .pdu import MccsPdu
from .power_marshaller import PowerMarshaller
from .prototype_subrack import MccsPrototypeSubrack
from .prototype_subrack.prototype_subrack_device import subrack_factory
from .station import SpsStation
from .subrack import MccsSubrack as _LegacyMccsSubrack
from .tile import MccsTile
from .version import version_info

__version__ = version_info["version"]

SUBRACK_IMPLEMENTATION_ENV_VAR = "MCCS_SUBRACK_IMPLEMENTATION"
"""The environment variable that selects the subrack implementation."""


def subrack_class() -> type[tango.server.Device]:
    """
    Return the class to serve under the Tango class name ``MccsSubrack``.

    The ``MCCS_SUBRACK_IMPLEMENTATION`` environment variable selects the class.
    With ``legacy``, or with the variable not set, this is
    :py:class:`ska_low_mccs_spshw.subrack.MccsSubrack`. With ``prototype``, it
    is :py:class:`~.MccsPrototypeSubrack`. The Tango class name, the Tango DB
    rows, the class properties and the EDA configuration are the same in both
    cases.

    The package attribute ``ska_low_mccs_spshw.MccsSubrack`` returns this
    class too. So the switch applies to the ``spshw`` command, and to a device
    server that names ``ska_low_mccs_spshw.MccsSubrack`` as an entry point.

    :raises ValueError: if the environment variable has an unknown value. A
        typo must stop the server, rather than silently select the old
        subrack.

    :return: the subrack device class to serve.
    """
    implementation = os.environ.get(SUBRACK_IMPLEMENTATION_ENV_VAR, "legacy")
    match implementation:
        case "legacy":
            return _LegacyMccsSubrack
        case "prototype":
            return subrack_factory(class_name="MccsSubrack")
        case _:
            raise ValueError(
                f"{SUBRACK_IMPLEMENTATION_ENV_VAR} is {implementation!r}. "
                "Use 'legacy' or 'prototype'."
            )


def __getattr__(name: str) -> Any:
    """
    Return the subrack class that the environment selects.

    A device server entry point imports ``ska_low_mccs_spshw.MccsSubrack`` by
    name, so this attribute must give the same class as
    :py:func:`server_classes`.

    :param name: the name of the attribute.

    :raises AttributeError: if the package has no attribute with this name.

    :return: the attribute.
    """
    if name == "MccsSubrack":
        return subrack_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def server_classes() -> tuple[type[tango.server.Device], ...]:
    """
    Return the device classes that the spshw server registers.

    :return: the device classes to serve.
    """
    return (
        MccsPdu,
        PowerMarshaller,
        subrack_factory(),
        subrack_class(),
        MccsTile,
        SpsStation,
    )


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return tango.server.run(
        classes=server_classes(),
        args=args or None,
        **kwargs,
    )


if __name__ == "__main__":
    print(__version__)
