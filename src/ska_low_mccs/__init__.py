# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This package implements the Square Kilometre Array (SKA) Low telescope's Monitoring
Control and Calibration Subsystem (MCCS)."""

__all__ = [
    # devices
    "MccsAntenna",
    "MccsAPIU",
    "MccsClusterManagerDevice",
    "MccsController",
    "MccsDevice",
    "MccsGroupDevice",
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
    "subrack",
    "subarray",
    "subarray_beam",
    "tel_state",
    "transient_buffer",
    # non-device modules
    "events",
    "hardware",
    "health",
    "message_queue",
    "pool",
    "utils",
    "resource",
]

from .device import MccsDevice
from .device_proxy import MccsDeviceProxy
from .group_device import MccsGroupDevice

from .apiu import MccsAPIU
from .cluster_manager import MccsClusterManagerDevice
from .controller import MccsController
from .tile import MccsTile

from .antenna import MccsAntenna
from .station import MccsStation
from .station_beam import MccsStationBeam
from .subarray import MccsSubarray
from .subarray_beam import MccsSubarrayBeam
from .subrack import MccsSubrack
from .tel_state import MccsTelState
from .transient_buffer import MccsTransientBuffer
