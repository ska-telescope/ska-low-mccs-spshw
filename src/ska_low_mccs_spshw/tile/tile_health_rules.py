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
        tile_health: HealthState,
    ) -> bool:
        """
        Test whether UNKNOWN is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_health: the tile's computed health from it's communication and fault
            states, among others. Does not include monitoring points.
        :return: True if UNKNOWN is a valid state
        """
        return (
            HealthState.UNKNOWN in intermediate_healths.values()
            or tile_health == HealthState.UNKNOWN
        )

    def failed_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
        tile_health: HealthState,
    ) -> bool:
        """
        Test whether FAILED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_health: the tile's computed health from it's communication and fault
            states, among others. Does not include monitoring points.
        :return: True if FAILED is a valid state
        """
        return (
            HealthState.FAILED in intermediate_healths.values()
            or tile_health == HealthState.FAILED
        )

    def degraded_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
        tile_health: HealthState,
    ) -> bool:
        """
        Test whether DEGRADED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_health: the tile's computed health from it's communication and fault
            states, among others. Does not include monitoring points.
        :return: True if DEGRADED is a valid state
        """
        return (
            HealthState.DEGRADED in intermediate_healths.values()
            or tile_health == HealthState.DEGRADED
        )

    def healthy_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, HealthState],
        tile_health: HealthState,
    ) -> bool:
        """
        Test whether OK is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_health: the tile's computed health from it's communication and fault
            states, among others. Does not include monitoring points.
        :return: True if OK is a valid state
        """
        return (
            HealthState.OK in intermediate_healths.values()
            and tile_health == HealthState.OK
        )

    @property
    def default_thresholds(self: TileHealthRules) -> dict[str, Any]:
        """
        Get the default thresholds for tile.

        :return: the default thresholds
        """
        return TileData.MIN_MAX_MONITORING_POINTS

    def compute_intermediate_state(
        self: TileHealthRules,
        monitoring_points: dict[str, Any],
        min_max: dict[str, Any],
    ) -> HealthState:
        """
        Compute the intermediate health state for the Tile.

        This is computed for a particular category of monitoring points
        e.g. voltage, io etc.

        :param monitoring_points: dictionary of all the TPM monitoring points
            for the given category of monitoring point
        :param min_max: minimum/maximum/expected values for the monitoring points.
            For monitoring points where a minimum/maximum doesn't make sense,
            the value provided will be that which the monitoring point is required
            to have for the device to be healthy
        :return: the computed health state
        """
        states = {}
        for p in monitoring_points:
            if isinstance(monitoring_points[p], dict):
                states[p] = self.compute_intermediate_state(
                    monitoring_points[p], min_max[p]
                )
            else:
                if monitoring_points[p] is None:
                    states[p] = HealthState.OK
                elif isinstance(min_max[p], dict):
                    states[p] = (
                        HealthState.OK
                        if monitoring_points[p] >= min_max[p]["min"]
                        and monitoring_points[p] <= min_max[p]["max"]
                        else HealthState.FAILED
                    )
                else:
                    states[p] = (
                        HealthState.OK
                        if monitoring_points[p] == min_max[p]
                        else HealthState.FAILED
                    )
        return self._combine_states(*states.values())

    def _combine_states(self: TileHealthRules, *args: HealthState) -> HealthState:
        states = [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]
        for state in states:
            if state in args:
                return state
        return HealthState.UNKNOWN
