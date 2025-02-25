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

__version__ = "1.3.0"
__version_info__ = (
    "ska-low-mccs-spshw",
    __version__,
    "This package implements SKA Low's MCCS SPSHW subsystem.",
)

__all__ = [
    "MccsDaqReceiver",
    "MccsSubrack",
    "MccsTile",
    "SpsStation",
    "MccsPdu",
    "version",
]

import tango.server

from .daq_receiver import MccsDaqReceiver
from .pdu import MccsPdu
from .station import SpsStation
from .subrack import MccsSubrack
from .tile import MccsTile
from .version import version_info

__version__ = version_info["version"]


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return tango.server.run(
        classes=(MccsDaqReceiver, MccsPdu, MccsSubrack, MccsTile, SpsStation),
        args=args or None,
        **kwargs
    )


if __name__ == "__main__":
    print(__version__)
