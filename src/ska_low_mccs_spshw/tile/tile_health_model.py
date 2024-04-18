#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""An implementation of a health model for an APIU."""

from __future__ import annotations  # allow forward references in type hints

import copy
from typing import Any, Optional

from ska_control_model import HealthState
from ska_low_mccs_common.health import BaseHealthModel, HealthChangedCallbackProtocol

from .tile_health_rules import TileHealthRules

__all__ = ["TileHealthModel"]


class TileHealthModel(BaseHealthModel):
    """
    A health model for a tile.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """

    def __init__(
        self: TileHealthModel,
        health_changed_callback: HealthChangedCallbackProtocol,
        thresholds: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        :param thresholds: the threshold parameters for the health rules
        """
        self._health_rules = TileHealthRules(thresholds)
        super().__init__(health_changed_callback)

    def evaluate_health(
        self: TileHealthModel,
    ) -> tuple[HealthState, str]:
        """
        Compute overall health of the station.

        The overall health is based on the fault and communication
        status of the station overall, together with the health of the
        tiles that it manages.

        This implementation simply sets the health of the station to the
        health of its least healthy component.

        :return: an overall health of the station
        """
        tile_health, tile_report = super().evaluate_health()
        intermediate_healths = self.intermediate_healths
        print(f"Evaluating health with intermediates {intermediate_healths}")
        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]:
            if health == tile_health:
                return tile_health, tile_report
            result, report = self._health_rules.rules[health](intermediate_healths)
            if result:
                return health, report
        return HealthState.UNKNOWN, "No rules matched"

    @property
    def intermediate_healths(self: TileHealthModel) -> dict[str, tuple[HealthState, str]]:
        """
        Get the 6 intermediate health roll-up quantities.

        :return: the 6 intermediate health roll-up quantities
        """
        if "tile_health_structure" not in self._state:
            return {
                "temperatures": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "voltages": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "currents": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "alarms": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "adcs": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "timing": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "io": (HealthState.UNKNOWN, "Health model inputs not yet read"),
                "dsp": (HealthState.UNKNOWN, "Health model inputs not yet read"),
            }
        monitoring_points: dict[str, Any] = self._state[
            "tile_health_structure"
        ]  # type: ignore[assignment]
        assert isinstance(self._health_rules, TileHealthRules)  # for the type-checker
        intermediates = {
            state: self._health_rules.compute_intermediate_state(
                monitoring_points[state], self.health_params[state]
            )
            for state in monitoring_points
        }
        print(f"Intermediate healths are {intermediates}")
        return intermediates

    @property
    def health_params(self: TileHealthModel) -> dict[str, Any]:
        """
        Get the thresholds for health rules.

        :return: the thresholds for health rules
        """
        return self._health_rules._thresholds

    @health_params.setter
    def health_params(self: TileHealthModel, params: dict[str, Any]) -> None:
        """
        Set the thresholds for health rules.

        :param params: A dictionary of parameters with the param name as key and
            threshold as value
        """
        self._health_rules._thresholds = self._merge_dicts(
            self._health_rules.default_thresholds, params
        )

    def _merge_dicts(
        self: TileHealthModel, dict_a: dict[str, Any], dict_b: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Merge two nested dictionaries, taking values from b when available.

        This is necessary for nested dictionaries of thresholds

        TODO: Move into common repo

        :param dict_a: the dictionary to take from if not in dictionary b
        :param dict_b: the dictionary to preferentially take from
        :return: the merged dictionary
        """
        output = copy.deepcopy(dict_a)
        for key in dict_b:
            if isinstance(dict_b[key], dict):
                output[key] = self._merge_dicts(dict_a[key], dict_b[key])
            else:
                output[key] = dict_b[key]
        return output
