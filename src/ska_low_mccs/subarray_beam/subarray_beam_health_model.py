# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for subarray beams."""
from __future__ import annotations

from typing import Callable

from ska_tango_base.control_model import HealthState

from ska_low_mccs.health import HealthModel

__all__ = ["SubarrayBeamHealthModel"]


class SubarrayBeamHealthModel(HealthModel):
    """A health model for subarray beams."""

    def __init__(
        self: SubarrayBeamHealthModel,
        health_changed_callback: Callable[[HealthState], None],
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: a callback to be called when the
            health of the subarray beam (as evaluated by this model)
            changes
        """
        self._is_beam_locked = False
        super().__init__(health_changed_callback)

    def evaluate_health(
        self: SubarrayBeamHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the subarray beam.

        The overall health is based on the whether the beam is locked or
        not.

        :return: an overall health of the subarray beam
        """
        health = super().evaluate_health()
        if health == HealthState.OK and not self._is_beam_locked:
            health = HealthState.DEGRADED
        return health

    def is_beam_locked_changed(
        self: SubarrayBeamHealthModel, is_beam_locked: bool
    ) -> None:
        """
        Handle a change in whether the subarray beam is locked.

        This is a callback hook that is called when whether asubarray
        beam is locked changes.

        :param is_beam_locked: whether the subarray beam is locked
        """
        self._is_beam_locked = is_beam_locked
        self.update_health()
