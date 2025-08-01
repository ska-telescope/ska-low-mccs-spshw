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

import semver
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


def _check_hw_version(version_str: str) -> None:
    """
    Validate hardware version.

    :param version_str: the string to convert into a tuple.

    :raises ValueError: when version_string has invalid format.
    """
    if not version_str:
        # Default
        return
    # Convert 'v1.6.7a' -> (1, 6, 7, 'a')
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)([a-z])", version_str)
    if not match:
        raise ValueError(f"Invalid version format: '{version_str}'")


def _check_bios_version(bios_version: str) -> None:
    """
    Validate hardware bios_version.

    :param bios_version: the bios version to check.
    """
    if not bios_version:
        # Default
        return
    semver.VersionInfo.parse(bios_version)


class TileHealthRules(HealthRules):
    """A class to handle transition rules for tile."""

    # This is a map used to locate the thresholds
    # appropriate to the version of bios and hardware.
    THRESHOLD_LOCATOR = {
        ("0.6.0", "v2.0.1a"): "set3.yaml",
        ("0.6.0", "v2.0.2a"): "set3.yaml",
        ("0.6.0", "v2.0.5b"): "set3.yaml",
        ("0.6.0", "v1.6.7a"): "set4.yaml",
        ("0.6.0", "v1.6.5a"): "set4.yaml",
        ("0.5.0", "v1.6.5a"): "set1.yaml",
        ("0.5.0", "v1.6.7a"): "set1.yaml",
        ("0.5.0", "v2.0.1a"): "set2.yaml",
        ("0.5.0", "v2.0.2a"): "set2.yaml",
        ("0.5.0", "v2.0.5b"): "set2.yaml",
    }
    THRESHOLD_MODIFIERS = {
        ("has_preadu", False): "no_preadu.yaml",
    }

    def __init__(
        self: TileHealthRules,
        hw_version: str,
        bios_version: str,
        has_preadu: bool,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise this device object.

        :param hw_version: the TPM version.
        :param bios_version: the TPM bios version.
        :param has_preadu: whether the TPM has a preadu attached.
        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        # Validate inputs.
        _check_hw_version(hw_version)
        _check_bios_version(bios_version)

        self._threshold_locator = dict(self.THRESHOLD_LOCATOR)
        self._threshold_modifier = dict(self.THRESHOLD_MODIFIERS)

        self._min_max_monitoring_points = self._load_health_file(
            hw_version, bios_version
        )

        modifiers = self._threshold_modifier.get(("has_preadu", has_preadu))
        if modifiers is not None:
            path = files(health_config).joinpath(modifiers)
            modification_path = path.read_text()
            modification = yaml.safe_load(modification_path)
            self._min_max_monitoring_points = (
                self._min_max_monitoring_points | modification
            )

        self._bios_version = bios_version
        self._hw_version = hw_version
        super().__init__(*args, **kwargs)
        self.logger = None
        # self.previous_counters: dict = {}
        # for counter in COUNTERS:
        #     self.previous_counters[counter] = None

    def _load_health_file(
        self: TileHealthRules, hw_version: str, bios_version: str
    ) -> dict[str, Any]:
        """
        Load a specified health set.

        :param hw_version: the hardware version used to choose correct defaults.
        :param bios_version: the bios version used to choose correct defaults.

        :raises FileNotFoundError: when the health thresholds are not
            present.
        :raises ValueError: When there is no set defined

        :return: the loaded health dictionary.
        """
        resource_name = self._threshold_locator.get((bios_version, hw_version))
        if resource_name is None:
            if bios_version == "" or hw_version == "":
                # When bios_version is not defined we will
                # not evaluate pll_40g.
                # When the hardware_version is not defined we will not evaluate
                # the temperature ADCs
                # When we updated ska-low-sps-tpm-api:0.4.0 -> 0.6.0
                # we found that we had some new monitoring points.
                # These offered a different interface for the health evaluation
                # for different versions of bios_version and hardware_version.
                # This we would like to make mandatory. But for now we are
                # ommiting the appropriate monitoring points from health.
                resource_name = "set3.yaml"
            else:
                raise ValueError(
                    f"Undefined health resource for {bios_version}, {hw_version}. "
                )

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

    # pylint: disable = too-many-branches
    def compute_intermediate_state(
        self: TileHealthRules,
        monitoring_points: dict[str, Any],
        min_max: dict[str, Any],
        path: str = "",
        health_key: str | None = None,
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
        :param health_key: the root health key.
        :return: the computed health state and health report
        """
        states: dict[str, tuple[HealthState, str]] = {}
        if not monitoring_points and "hardware" in min_max:
            return (HealthState.OK, "")
        for p, p_state in monitoring_points.items():
            if isinstance(p_state, dict):
                if p in min_max:
                    states[p] = self.compute_intermediate_state(
                        monitoring_points=p_state,
                        min_max=min_max[p],
                        path=f"{path}/{p}",
                        health_key=health_key,
                    )
                else:
                    # TODO: MCCS-2196 - Updating the tile_health_attribute
                    # in ska-low-sps-tpm-api can cause a key error to be raised.
                    continue
            else:
                # We ignore specific monitoring points
                # if the _hw_version or _bios_version are undefined.
                if (
                    health_key == "temperatures"
                    and p in [f"ADC{i}" for i in range(16)]
                    and self._hw_version == ""
                ):
                    # If hw_version is not defined the ADC temperatures are ignored.
                    states[p] = (HealthState.OK, "")
                    continue
                if (
                    health_key == "timing"
                    and p == "pll_40g"
                    and self._bios_version == ""
                ):
                    # If bios_verion is not defined the pll_40g is ignored.
                    states[p] = (HealthState.OK, "")
                    continue

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
