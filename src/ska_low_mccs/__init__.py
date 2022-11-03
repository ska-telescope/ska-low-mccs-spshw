# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This package implements SKA Low's MCCS subsystem.

The Monitoring Control and Calibration (MCCS) subsystem is responsible
for, amongst other things, monitoring and control of LFAA.
"""

__all__ = [
    # devices
    "MccsAntenna",
    "MccsAPIU",
    "MccsController",
    "MccsStation",
    "MccsStationBeam",
    "MccsSubarray",
    "MccsSubarrayBeam",
    "MccsSubrack",
    "MccsTelState",
    "MccsTile",
    "MccsTransientBuffer",
    # device subpackages
    "antenna",
    "apiu",
    "controller",
    "station",
    "station_beam",
    "subrack",
    "subarray",
    "subarray_beam",
    "tel_state",
    "tile",
    "transient_buffer",
]

from .antenna import MccsAntenna
from .apiu import MccsAPIU

from .controller import MccsController
from .station import MccsStation

from .station_beam import MccsStationBeam
from .subarray import MccsSubarray

from .subarray_beam import MccsSubarrayBeam
from .subrack import MccsSubrack

from .tel_state import MccsTelState
from .tile import MccsTile
from .transient_buffer import MccsTransientBuffer
