#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""An implementation of a health model for a Tile."""

from __future__ import annotations  # allow forward references in type hints

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

    _health_rules: TileHealthRules

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
        self.logger = None
        self._health_rules = TileHealthRules(thresholds)
        super().__init__(health_changed_callback)

    def set_logger(self, logger: Any) -> None:
        """
        Set logger for debugging.

        :param logger: a logger.
        """
        self.logger = logger

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

        def debug(msg: str) -> None:
            if self.logger:
                self.logger.debug(msg)

        debug("TileHealthModel: evaluate_health")
        tile_health, tile_report = super().evaluate_health()
        debug(f"super tile_health={tile_health} tile_report = {tile_report}")
        intermediate_healths = self.intermediate_healths
        debug(f"intermediate healths = {intermediate_healths}")
        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]:
            if health == tile_health:
                debug(f"matched: {health} super tile_report:{tile_report}")
                return tile_health, tile_report
            debug(f"not matched eval {health}")
            debug(f"rule = {self._health_rules.rules[health]}")
            result, report = self._health_rules.rules[health](intermediate_healths)
            debug(f"result = {result} report = {report}")
            if result:
                debug(f"result true report = {report}")
                return health, report
        return HealthState.UNKNOWN, "No rules matched"

    @property
    def intermediate_healths(
        self: TileHealthModel,
    ) -> dict[str, tuple[HealthState, str]]:
        """
        Get the intermediate health roll-up states.

        :return: the intermediate health roll-up states
        """
        monitoring_points: dict[str, Any] = self._state.get("tile_health_structure", {})
        return {
            health_key: self._health_rules.compute_intermediate_state(
                monitoring_points.get(health_key, {}),
                parameters,
            )
            for health_key, parameters in self.health_params.items()
        }

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
