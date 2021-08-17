# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This package implements SKA Low's MCCS subsystem.

The Monitoring Control and Calibration (MCCS) subsystem is responsible
for, amongst other things, monitoring and control of LFAA.
"""

__all__ = [
    # devices
    "MccsAntenna",
    "MccsAPIU",
    "MccsClusterManagerDevice",
    "MccsController",
    "MccsStation",
    "MccsStationBeam",
    "MccsSubarray",
    "MccsSubarrayBeam",
    "MccsSubrack",
    "MccsTelState",
    "MccsTile",
    "MccsTransientBuffer",
    # proxies
    "MccsDeviceProxy",
    # device subpackages
    "antenna",
    "apiu",
    "cluster_manager",
    "controller",
    "tile",
    # concrete devices modules
    "antenna",
    "station",
    "station_beam",
    "subrack",
    "subarray",
    "subarray_beam",
    "tel_state",
    "transient_buffer",
    # non-device modules
    "component",
    "health",
    "release",
    "utils",
    "resource_manager",
]

from .device_proxy import MccsDeviceProxy

from .apiu import MccsAPIU  # type: ignore[attr-defined]
from .cluster_manager import MccsClusterManagerDevice  # type: ignore[attr-defined]
from .controller import MccsController  # type: ignore[attr-defined]
from .tile import MccsTile  # type: ignore[attr-defined]

from .antenna import MccsAntenna  # type: ignore[attr-defined]
from .station import MccsStation  # type: ignore[attr-defined]
from .station_beam import MccsStationBeam  # type: ignore[attr-defined]
from .subarray import MccsSubarray  # type: ignore[attr-defined]
from .subarray_beam import MccsSubarrayBeam  # type: ignore[attr-defined]
from .subrack import MccsSubrack  # type: ignore[attr-defined]
from .tel_state import MccsTelState  # type: ignore[attr-defined]
from .transient_buffer import MccsTransientBuffer  # type: ignore[attr-defined]
