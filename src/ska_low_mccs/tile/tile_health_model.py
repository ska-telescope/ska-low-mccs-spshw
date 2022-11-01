# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of a health model for an APIU."""

from __future__ import annotations  # allow forward references in type hints

from typing import Any, Callable

from ska_control_model import HealthState, PowerState
from ska_low_mccs_common.health import HealthModel

__all__ = ["TileHealthModel"]


class TileHealthModel(HealthModel):
    """
    A health model for a tile.

    At present this uses the base health model; this is a placeholder
    for a future, better implementation.
    """

    def __init__(
        self: TileHealthModel,
        health_changed_callback: Callable[[Any], None],
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        """
        self._power_mode = PowerState.UNKNOWN
        super().__init__(health_changed_callback)

    def evaluate_health(self: TileHealthModel) -> HealthState:
        """
        Re-evaluate the health state.

        This method contains the logic for evaluating the health. It is
        this method that should be extended by subclasses in order to
        define how health is evaluated by their particular device.

        :return: the new health state.
        """
        if self._faulty:
            return HealthState.FAILED
        if not self._communicating and self._power_mode != PowerState.OFF:
            return HealthState.UNKNOWN
        return HealthState.OK

    def set_power_mode(self: TileHealthModel, power_mode: PowerState) -> None:
        """
        Update power mode.

        :param power_mode: changed power mode
        """
        self._power_mode = power_mode
        self.update_health()
