# type: ignore
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of an observation state model for a subarray beam."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ska_control_model import ObsState

__all__ = ["SubarrayBeamObsStateModel"]


class SubarrayBeamObsStateModel:
    """An observation state model for a subarray beam."""

    def __init__(
        self: SubarrayBeamObsStateModel,
        logger: logging.Logger,
        obs_state_changed_callback: Callable[[dict[str, ObsState]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use
        :param obs_state_changed_callback: callback to be called when
            there is a change to this model's evaluated observation
            state.
        """
        self._logger = logger

        self._is_resourced = False
        self._is_configured = False
        self._obs_state = self._evaluate_obs_state()

        self._obs_state_changed_callback = obs_state_changed_callback

    #         assert self._obs_state is not None  # for the type checker
    #         self._obs_state_changed_callback({"obs_state": self._obs_state})

    def is_configured_changed(
        self: SubarrayBeamObsStateModel,
        is_configured: bool,
    ) -> None:
        """
        Handle a change in whether the subarray_beam is configured.

        :param is_configured: whether the subarray_beam is configured
        """
        self._is_configured = is_configured
        self.update_obs_state()

    def update_obs_state(self: SubarrayBeamObsStateModel) -> None:
        """Update the observation state, ensuring that the callback is called."""
        obs_state = self._evaluate_obs_state()
        if obs_state is None:
            return
        if self._obs_state != obs_state:
            self._obs_state = obs_state

        self._obs_state_changed_callback({"obs_state": obs_state})

    def _evaluate_obs_state(
        self: SubarrayBeamObsStateModel,
    ) -> Optional[ObsState]:
        """
        Return the evaluated observation state of the subarray_beam.

        The evaluated observation state is based on whether the subarray_beam
        is resourced, and whether it is configuring.

        :return: the evaluated observation state of the subarray_beam.
        """
        return ObsState.READY if self._is_configured else ObsState.IDLE
