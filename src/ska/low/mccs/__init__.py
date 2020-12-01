# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This package implements the Square Kilometre Array (SKA) Low telescope's
Monitoring Control and Calibration Subsystem (MCCS).
"""

__all__ = [
    "MccsAntenna",
    "MccsAPIU",
    "MccsClusterManagerDevice",
    "MccsController",
    "MccsDevice",
    "MccsGroupDevice",
    "MccsStation",
    "MccsStationBeam",
    "MccsSubarray",
    "MccsTelState",
    "MccsTile",
    "MccsTransientBuffer",
    # abstract device modules
    "device",
    "group_device",
    # concrete device subpackages
    "apiu",
    "cluster_manager",
    "controller",
    "tile",
    # concrete devices modules
    "antenna",
    "station",
    "station_beam",
    "subarray",
    "tel_state",
    "transient_buffer",
    # non-device modules
    "events",
    "hardware",
    "health",
    "power",
    "utils",
]

from .device import MccsDevice
from .group_device import MccsGroupDevice

from .apiu import MccsAPIU
from .cluster_manager import MccsClusterManagerDevice
from .controller import MccsController
from .tile import MccsTile

from .antenna import MccsAntenna
from .station import MccsStation
from .station_beam import MccsStationBeam
from .subarray import MccsSubarray
from .tel_state import MccsTelState
from .transient_buffer import MccsTransientBuffer
