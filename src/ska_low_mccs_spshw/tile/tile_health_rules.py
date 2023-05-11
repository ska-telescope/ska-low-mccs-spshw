#  -*- coding: utf-8 -*
# pylint: disable=arguments-differ
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A file to store health transition rules for tile."""
from __future__ import annotations

from typing import Any

from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthRules

from .tile_data import TileData


class TileHealthRules(HealthRules):
    """A class to handle transition rules for tile."""

    def unknown_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
    ) -> bool:
        """
        Test whether UNKNOWN is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if UNKNOWN is a valid state
        """
        return HealthState.UNKNOWN in intermediate_healths.values()

    def failed_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
    ) -> bool:
        """
        Test whether FAILED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if FAILED is a valid state
        """
        return HealthState.FAILED in intermediate_healths.values()

    def degraded_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
    ) -> bool:
        """
        Test whether DEGRADED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if DEGRADED is a valid state
        """
        return HealthState.DEGRADED in intermediate_healths.values()

    def healthy_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
    ) -> bool:
        """
        Test whether OK is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if OK is a valid state
        """
        return HealthState.OK in intermediate_healths.values()

    @property
    def default_thresholds(self: HealthRules) -> dict[str, Any]:
        """
        Get the default thresholds for tile.

        :return: the default thresholds
        """
        return TileData.MIN_MAX_MONITORING_POINTS
