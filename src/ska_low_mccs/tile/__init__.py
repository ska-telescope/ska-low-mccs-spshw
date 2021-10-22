# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This subpackage implement tile functionality for the MCCS.

It includes an operational Tango device, a demonstrator Tango device,
modules for driving and simulating TPM hardware, and a CLI.
"""


__all__ = [
    "MccsTile",
    "TileComponentManager",
    "TileHealthModel",
    "BaseTpmSimulator",
    "DemoTile",
    "DynamicTpmSimulator",
    "StaticTpmSimulator",
    "SwitchingTpmComponentManager",
    "DynamicTpmSimulatorComponentManager",
    "StaticTpmSimulatorComponentManager",
    "TpmDriver",
#    "HwTile",
#    "Tile12",
#    "Tile16",
#    "TpmTestFirmware",
    "demo_tile_device",
    "plugins",
]

#from .tile_1_2 import Tile12
#from .tile_1_6 import Tile16
#from .tile_wrapper import HwTile
from .base_tpm_simulator import BaseTpmSimulator
from .dynamic_tpm_simulator import DynamicTpmSimulator
from .static_tpm_simulator import StaticTpmSimulator
from .tpm_driver import TpmDriver
from .tile_component_manager import (
    DynamicTpmSimulatorComponentManager,
    StaticTpmSimulatorComponentManager,
    SwitchingTpmComponentManager,
    TileComponentManager,
)
from .tile_health_model import TileHealthModel
from .tile_device import MccsTile
from .demo_tile_device import DemoTile
