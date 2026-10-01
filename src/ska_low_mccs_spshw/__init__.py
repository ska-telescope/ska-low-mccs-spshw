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

__version__ = "15.1.0"
__version_info__ = str(
    (
        "ska-low-mccs-spshw",
        __version__,
        "This package implements SKA Low's MCCS SPSHW subsystem.",
    )
).replace("'", "")

__all__ = [
    "MccsPrototypeSubrack",
    "MccsSubrack",
    "MccsTile",
    "SpsStation",
    "MccsPdu",
    "PowerMarshaller",
    "SUBRACK_IMPLEMENTATION_ENV_VAR",
    "server_classes",
    "version",
]

import os

import tango.server

from .pdu import MccsPdu
from .power_marshaller import PowerMarshaller
from .prototype_subrack import MccsPrototypeSubrack
from .prototype_subrack.prototype_subrack_device import subrack_factory
from .station import SpsStation
from .subrack import MccsSubrack
from .tile import MccsTile
from .version import version_info

__version__ = version_info["version"]

SUBRACK_IMPLEMENTATION_ENV_VAR = "MCCS_SUBRACK_IMPLEMENTATION"
"""The environment variable that selects the subrack implementation."""


def server_classes() -> tuple[type[tango.server.Device], ...]:
    """
    Return the device classes that the spshw server registers.

    The ``MCCS_SUBRACK_IMPLEMENTATION`` environment variable selects the class
    that is served under the Tango class name ``MccsSubrack``. With ``legacy``,
    or with the variable not set, this is :py:class:`~.MccsSubrack`. With
    ``prototype``, it is :py:class:`~.MccsPrototypeSubrack`. The Tango DB rows
    for the subrack devices are the same in both cases.

    :raises ValueError: if the environment variable has an unknown value. A
        typo must stop the server, rather than silently select the old
        subrack.

    :return: the device classes to serve.
    """
    implementation = os.environ.get(SUBRACK_IMPLEMENTATION_ENV_VAR, "legacy")
    if implementation == "legacy":
        subrack_class: type[tango.server.Device] = MccsSubrack
    elif implementation == "prototype":
        subrack_class = subrack_factory(class_name="MccsSubrack")
    else:
        raise ValueError(
            f"{SUBRACK_IMPLEMENTATION_ENV_VAR} is {implementation!r}. "
            "Use 'legacy' or 'prototype'."
        )
    # Printed because the Tango class name is MccsSubrack either way, and
    # device logging does not exist yet.
    print(
        f"Serving the {implementation} subrack implementation as Tango class "
        "MccsSubrack.",
        flush=True,
    )
    return (
        MccsPdu,
        PowerMarshaller,
        subrack_factory(),
        subrack_class,
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
