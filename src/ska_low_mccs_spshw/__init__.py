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

__all__ = [
    "MccsSubrack",
    "MccsTile",
    "SpsStation",
    "MccsStationCalibrator",
    "version",
]

from .calibration_store import MccsCalibrationStore
from .station import SpsStation
from .station_calibrator import MccsStationCalibrator
from .subrack import MccsSubrack
from .tile import MccsTile
from .version import version_info

__version__ = version_info["version"]


if __name__ == "__main__":
    print(__version__)
