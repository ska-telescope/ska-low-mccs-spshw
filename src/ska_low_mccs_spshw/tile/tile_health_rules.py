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
import re
from importlib.resources import files
from typing import Any

import yaml
from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthRules

from ska_low_mccs_spshw.tile import health_config  # import the subpackage

# COUNTERS = [
#     "rd_cnt",
#     "wr_cnt",
#     "rd_dat_cnt",
# ]


def _both_nan(a: float, b: float) -> bool:
    """
    Compare 2 inputs.

    :param a: string a under test
    :param b: string b under test

    :return: True if both a and b are None or NaN.
    """
    # Guard against non-floats
    if not isinstance(a, float) or not isinstance(b, float):
        return False
    return math.isnan(a) and math.isnan(b)


def _bios_version_to_tuple(version_str: str) -> tuple[int, int, int]:
    """
    Return a tuple with the parsed version.

    :param version_str: the string to convert into a tuple.

    :return: A tuple with parsed version.

    :raises ValueError: when version_string has invalid format.
    """
    # Convert 'v0.5.0' -> (0, 5, 0)
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version_str)
    if not match:
        raise ValueError(f"Invalid version format: '{version_str}'")

    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch))


def _hw_version_to_tuple(version_str: str) -> tuple[int, int, int, str]:
    """
    Return a tuple with the parsed version.

    :param version_str: the string to convert into a tuple.

    :return: A tuple with parsed version.

    :raises ValueError: when version_string has invalid format.
    """
    # Convert 'v1.6.7a' -> (1, 6, 7, 'a')
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)([a-z])", version_str)
    if not match:
        raise ValueError(f"Invalid version format: '{version_str}'")

    major, minor, patch, letter = match.groups()
    return (int(major), int(minor), int(patch), letter)


def _hw_in_version_range(tpm_version: str, min_version: str, max_version: str) -> bool:
    tpm = _hw_version_to_tuple(tpm_version)
    min_v = _hw_version_to_tuple(min_version)
    max_v = _hw_version_to_tuple(max_version)
    return min_v <= tpm <= max_v


def _bios_in_version_range(
    bios_version: str, min_version: str, max_version: str
) -> bool:
    tpm = _bios_version_to_tuple(bios_version)
    min_v = _bios_version_to_tuple(min_version)
    max_v = _bios_version_to_tuple(max_version)
    return min_v <= tpm <= max_v


class TileHealthRules(HealthRules):
    """A class to handle transition rules for tile."""

    def __init__(
        self: TileHealthRules,
        tpm_version: str,
        bios_version: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise this device object.

        :param tpm_version: the TPM version.
        :param bios_version: the TPM bios version.
        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        self._min_max_monitoring_points = self._load_health_file(
            tpm_version, bios_version
        )
        self._tpm_version = tpm_version
        super().__init__(*args, **kwargs)
        self.logger = None
        # self.previous_counters: dict = {}
        # for counter in COUNTERS:
        #     self.previous_counters[counter] = None

    def _load_health_file(
        self: TileHealthRules, tpm_version: str, bios_version: str
    ) -> dict[str, Any]:
        """
        Load a specified health set.

        :param tpm_version: the hardware version used to choose correct defaults.
        :param bios_version: the bios version used to choose correct defaults.

        :raises FileNotFoundError: when the health thresholds are not
            present.
        :raises ValueError: When there is no set defined

        :return: the loaded health dictionary.
        """
        resource_name = None

        if _bios_in_version_range(bios_version, "v0.6.0", "v0.6.0"):
            resource_name = resource_name or "set3.yaml"

        if _hw_in_version_range(
            tpm_version=tpm_version, min_version="v1.5.0a", max_version="v1.9.9z"
        ):
            # We have not noticed any variance in thresholds, hardcoding to v1.5.0a.yaml
            resource_name = resource_name or "set1.yaml"
        elif _hw_in_version_range(
            tpm_version=tpm_version, min_version="v2.0.0a", max_version="v2.0.5b"
        ):
            # We have not noticed any variance in thresholds, hardcoding to v2.0.0a.yaml
            resource_name = resource_name or "set2.yaml"
        else:
            raise ValueError("No health set found.")

        path = files(health_config).joinpath(resource_name)

        if path.is_file():
            min_max_string = path.read_text()
        else:
            raise FileNotFoundError(
                f"{resource_name} not found in health_config package"
            )
        return (
            yaml.load(min_max_string, Loader=yaml.Loader).get("tpm_monitoring_points")
            or {}
        )

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
        return self._min_max_monitoring_points

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
                        states[p] = (
                            (HealthState.OK, "")
                            if min_max[p]["min"] <= p_state <= min_max[p]["max"]
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
                        if _both_nan(p_state, min_max[p]) or (p_state == min_max[p])
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
