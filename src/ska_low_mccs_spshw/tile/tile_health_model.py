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
        hw_version: str,
        bios_version: str,
        thresholds: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        :param hw_version: the TPM version.
        :param bios_version: the TPM bios version.
        :param thresholds: the threshold parameters for the health rules
        """
        self._hw_version = hw_version
        self._bios_version = bios_version
        self.logger = None
        self._health_rules = TileHealthRules(
            self._hw_version, self._bios_version, thresholds
        )
        super().__init__(health_changed_callback)
        # Add new section for non-hardware/derived health quantities.
        additional_health = {"derived": {"pps_drift": 0}}
        self.update_state(**additional_health)

    def set_logger(self, logger: Any) -> None:
        """
        Set logger for debugging.

        :param logger: a logger.
        """
        self.logger = logger
        self._health_rules.set_logger(logger)

    def evaluate_health(
        self: TileHealthModel,
    ) -> tuple[HealthState, str]:
        """
        Compute overall health of the tile.

        The overall health is based on the fault and communication
        status of the tile.

        :return: an overall health of the tile
        """
        tile_health, tile_report = super().evaluate_health()
        intermediate_healths = self.intermediate_healths
        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]:
            if health == tile_health:
                return tile_health, tile_report
            result, report = self._health_rules.rules[health](
                intermediate_healths, self._state
            )
            if result:
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
        monitoring_points.update(derived=self._state.get("derived", {}))
        return {
            health_key: self._health_rules.compute_intermediate_state(
                monitoring_points.get(health_key, {}),
                min_max=parameters,
                health_key=health_key,
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

    def update_data(self: TileHealthModel, new_states: dict) -> None:
        """
        Update this health model with state relevant to evaluating health.

        :param new_states: New states of the data points.
        """
        self._state.update(new_states)
        self.update_health()
