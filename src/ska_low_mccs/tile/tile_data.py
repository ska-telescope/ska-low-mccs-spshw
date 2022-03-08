# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains base data/facts about a tile."""


from __future__ import annotations  # allow forward references in type hints

__all__ = ["TileData"]


class TileData:
    """
    This class contain data/facts about a tile needed by multiple classes.

    For example the channelized sample and beamformer frame period, the
    number of antennas per tile. So rather than store this fact in
    separate places, we store it here.
    """

    SAMPLE_PERIOD = 1.08e-6
    FRAME_PERIOD = 1.08e-6 * 256
    CSP_FRAME_PERIOD = 1.08e-6 * 2048
    ANTENNA_COUNT = 16
