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

import math
from typing import Any

from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthRules

from .tile_data import TileData

# COUNTERS = [
#     "rd_cnt",
#     "wr_cnt",
#     "rd_dat_cnt",
# ]


class TileHealthRules(HealthRules):
    """A class to handle transition rules for tile."""

    def __init__(
        self: TileHealthRules, tpm_version: str, *args: Any, **kwargs: Any
    ) -> None:
        """
        Initialise this device object.

        :param tpm_version: the TPM version.
        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        super().__init__(*args, **kwargs)
        self.logger = None
        self._tpm_version = tpm_version
        # self.previous_counters: dict = {}
        # for counter in COUNTERS:
        #     self.previous_counters[counter] = None

    def set_logger(self: TileHealthRules, logger: Any) -> None:
        """
        Set logger for debugging.

        :param logger: a logger.
        """
        self.logger = logger

    def unknown_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
        tile_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether UNKNOWN is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_state: State information for the tile.

        :return: True if UNKNOWN is a valid state, along with a text report.
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.UNKNOWN:
                return (
                    True,
                    f"Intermediate health {key} is in {value[0].name} HealthState. "
                    f"Cause: {value[1]}",
                )
        return False, ""

    def failed_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
        tile_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether FAILED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_state: State information for the tile.

        :return: True if FAILED is a valid state, along with a text report.
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.FAILED:
                return (
                    True,
                    f"Intermediate health {key} is in {value[0].name} HealthState. "
                    f"Cause: {value[1]}",
                )
        return False, ""

    def degraded_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
        tile_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether DEGRADED is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_state: State information for the tile.

        :return: True if DEGRADED is a valid state, along with a text report.
        """
        for key, value in intermediate_healths.items():
            if value[0] == HealthState.DEGRADED:
                return (
                    True,
                    f"Intermediate health {key} is in {value[0].name} HealthState. "
                    f"Cause: {value[1]}",
                )
        return False, ""

    def healthy_rule(  # type: ignore[override]
        self: TileHealthRules,
        intermediate_healths: dict[str, tuple[HealthState, str]],
        tile_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Test whether OK is valid for the tile.

        :param intermediate_healths: dictionary of intermediate healths
        :param tile_state: State information for the tile.

        :return: True if OK is a valid state, along with a text report.
        """
        if all(state == HealthState.OK for state, _ in intermediate_healths.values()):
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
    ) -> tuple[HealthState, str]:
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
        :param path: the location in the health structure dictionary that is currently
            being computed.
        :return: the computed health state and health report
        """
        states: dict[str, tuple[HealthState, str]] = {}
        if not monitoring_points and "hardware" in min_max:
            return (HealthState.OK, "")
        for p, p_state in monitoring_points.items():
            if isinstance(p_state, dict):
                if p in min_max:
                    states[p] = self.compute_intermediate_state(
                        p_state, min_max[p], path=f"{path}/{p}"
                    )
                else:
                    # TODO: MCCS-2196 - Updating the tile_health_attribute
                    # in ska-low-sps-tpm-api can cause a key error to be raised.
                    continue
            else:
                # last_path = path.split("/")[-1]
                if p_state is None and min_max[p] is not None:
                    states[p] = (
                        HealthState.UNKNOWN,
                        f"Monitoring point {p} is None.",
                    )
                # elif last_path in COUNTERS:
                #     p_state_previous = self.previous_counters.get(p)
                #     states[p] = (
                #         (HealthState.OK, "")
                #         if not p_state_previous or p_state_previous <= p_state
                #         else (
                #             HealthState.FAILED,
                #             f'Monitoring point "{path}/{p}": should be strictly'
                #             "increasing but"
                #             f"current {p_state} < previous {p_state_previous}",
                #         )
                #     )
                #     self.previous_counters[p] = p_state
                elif isinstance(min_max[p], dict):
                    # If limits are min/max
                    if "min" in min_max[p].keys():
                        allow_none_in_1_6 = min_max[p].get("allow_none_in_1_6", False)

                        is_nan = math.isnan(float(p_state))

                        states[p] = (
                            (HealthState.OK, "")
                            if (is_nan and allow_none_in_1_6)
                            and (self._tpm_version == "tpm_v1_6")
                            or min_max[p]["min"] <= p_state <= min_max[p]["max"]
                            else (
                                HealthState.FAILED,
                                f'Monitoring point "{path}/{p}": {p_state} not in range'
                                f" {min_max[p]['min']} - {min_max[p]['max']}",
                            )
                        )
                    # If limits are soft/hard.
                    # OK if <= soft limit
                    # DEGRADED if <= hard limit
                    # else FAILED
                    if "soft" in min_max[p].keys():
                        states[p] = (
                            (HealthState.OK, "")
                            if p_state <= min_max[p]["soft"]
                            else (
                                (
                                    HealthState.DEGRADED,
                                    f'Monitoring point "{path}/{p}": {p_state} over '
                                    f"soft limit: {min_max[p]['soft']}",
                                )
                                if p_state <= min_max[p]["hard"]
                                else (
                                    HealthState.FAILED,
                                    f'Monitoring point "{path}/{p}": {p_state} over '
                                    f"hard limit: {min_max[p]['hard']}",
                                )
                            )
                        )
                elif isinstance(min_max[p], list):
                    states[p] = (
                        (HealthState.OK, "")
                        if list(p_state) == min_max[p]
                        else (
                            HealthState.FAILED,
                            f'Monitoring point "{path}/{p}": '
                            f"{list(p_state)} =/= {min_max[p]}",
                        )
                    )
                else:
                    states[p] = (
                        (HealthState.OK, "")
                        if p_state == min_max[p]
                        else (
                            HealthState.FAILED,
                            f'Monitoring point "{path}/{p}": '
                            f"{p_state} =/= {min_max[p]}",
                        )
                    )

        return self._combine_states(*states.values())

    def _combine_states(
        self: TileHealthRules, *args: tuple[HealthState, str]
    ) -> tuple[HealthState, str]:
        states = [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]
        filtered_results = {
            state: [report for health, report in args if health == state]
            for state in states
        }
        for state in states:
            if len(filtered_results[state]) > 0:
                if state == HealthState.OK:
                    return state, ""
                return state, " | ".join(filtered_results[state])

        return (
            HealthState.UNKNOWN,
            f"No health state matches: args:{args} filtered results:{filtered_results}",
        )
