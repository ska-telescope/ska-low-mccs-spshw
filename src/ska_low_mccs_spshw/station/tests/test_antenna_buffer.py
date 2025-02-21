#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a test for the antenna buffer."""
from __future__ import annotations

from ska_low_mccs_spshw.station.station_component_manager import _TileProxy

# from ...tile.tile_data import TileData
from .base_daq_test import BaseDaqTest

# import json  # noqa
# from pyaavs.tile import Tile  # noqa
# from ska_low_mccs_spshw.tile.tile_device import MccsTile  # noqa
# from .data_handlers import RawDataReceivedHandler  # noqa
# from copy import copy


__all__ = ["TestAntennaBuffer"]


class TestAntennaBuffer(BaseDaqTest):
    """
    Test we can send raw data from the Antenna Buffer to the DAQ correctly.

    ##########
    TEST STEPS
    ##########

    #################
    TEST REQUIREMENTS
    #################


    """

    def test(self: TestAntennaBuffer) -> None:
        """A test to show we can stream raw data from the Antenna Buffer to DAQ."""
        self.logger.info("Test has begun")
        self._test_tile()

    def _test_tile(self: TestAntennaBuffer) -> None:
        """Run the test for a tpm."""
        self.logger.info("Starting the TPM phase")
        # get aavs tiles
        tiles: dict[str, _TileProxy] = self.component_manager._tile_proxies
        aavs_tiles = {}
        self.logger.info("Getting aavs tiles")
        for name, tile in tiles.items():
            aavs_tiles[name] = tile._proxy._component_manager.tile
            self.logger.info(f"Tile acquired: {name}")

        self.logger.info("setting up the antenna buffer")
        for name, aavs_tile in aavs_tiles.items():
            self.logger.info(f"Setting up for tile {name}")
            aavs_tile.set_up_antenna_buffer()
