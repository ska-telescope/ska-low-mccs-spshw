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
        intermediate_healths: dict[str, tuple[HealthState, str]],
    ) -> tuple[bool, str]:
        """
        Test whether UNKNOWN is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if UNKNOWN is a valid state
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.UNKNOWN:
                return True, f"Intermediate health {key} is in {value[0].name} HealthState. Cause: {value[1]}"
        return False, ""

    def failed_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
    ) -> tuple[bool, str]:
        """
        Test whether FAILED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if FAILED is a valid state
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.FAILED:
                return True, f"Intermediate health {key} is in {value[0].name} HealthState. Cause: {value[1]}"
        return False, ""

    def degraded_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
    ) -> tuple[bool, str]:
        """
        Test whether DEGRADED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if DEGRADED is a valid state
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.DEGRADED:
                return True, f"Intermediate health {key} is in {value[0].name} HealthState. Cause: {value[1]}"
        return False, ""

    def healthy_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
    ) -> tuple[bool, str]:
        """
        Test whether OK is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :return: True if OK is a valid state
        """
        if all(intermediate_healths.values() == HealthState.OK):
            return True, "Health is OK"
        return False, "Health not OK"

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
        path: str = "",
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
                    monitoring_points[p], min_max[p], path=f"{path}/{p}"
                )
            else:
                if monitoring_points[p] is None:
                    states[p] = HealthState.UNKNOWN, f"Monitoring point {p} not yet read"
                elif isinstance(min_max[p], dict):
                    states[p] = (
                        (HealthState.OK, "")
                        if monitoring_points[p] >= min_max[p]["min"]
                        and monitoring_points[p] <= min_max[p]["max"]
                        else (HealthState.FAILED, f"Monitoring point \"{path}/{p}\": {monitoring_points[p]} not in range {min_max[p]['min']} - {min_max[p]['max']}")
                    )
                else:
                    states[p] = (
                        (HealthState.OK, "")
                        if monitoring_points[p] == min_max[p]
                        else (HealthState.FAILED, f"Monitoring point \"{path}/{p}\": {monitoring_points[p]} =/= {min_max[p]}")
                    )
        return self._combine_states(*states.values())

    def _combine_states(self: TileHealthRules, *args: tuple[HealthState, str]) -> HealthState:
        states = [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]
        filtered_results = {state: [report for health, report in args if health == state] for state in states}
        for state in states:
            if len(filtered_results[state]) > 0:
                if state == HealthState.OK:
                    return state, ""
                return state, " | ".join(filtered_results[state]) 
        return HealthState.UNKNOWN, "No health state matches"
