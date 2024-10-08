#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of an observation state model for a station."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ska_control_model import ObsState

__all__ = ["SpsStationObsStateModel"]


class SpsStationObsStateModel:
    """An observation state model for a station."""

    def __init__(
        self: SpsStationObsStateModel,
        logger: logging.Logger,
        obs_state_changed_callback: Callable[[ObsState], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use
        :param obs_state_changed_callback: callback to be called when
            there is a change to this model's evaluated observation
            state.
        """
        self._logger = logger

        self._is_configured = False
        self._obs_state = self._evaluate_obs_state()

        self._obs_state_changed_callback = obs_state_changed_callback

        assert self._obs_state is not None  # for the type checker
        self._obs_state_changed_callback(self._obs_state)

    def is_configured_changed(
        self: SpsStationObsStateModel,
        is_configured: bool,
    ) -> None:
        """
        Handle a change in whether the station is configured.

        :param is_configured: whether the station is configured
        """
        self._is_configured = is_configured
        self.update_obs_state()

    def update_obs_state(self: SpsStationObsStateModel) -> None:
        """Update the observation state, ensuring that the callback is called."""
        obs_state = self._evaluate_obs_state()
        if obs_state is None:
            return
        if self._obs_state != obs_state:
            self._obs_state = obs_state
            self._obs_state_changed_callback(obs_state)

    def _evaluate_obs_state(
        self: SpsStationObsStateModel,
    ) -> Optional[ObsState]:
        """
        Return the evaluated observation state of the station.

        The evaluated observation state is based on whether the station
        is resourced, and whether it is configuring.

        :return: the evaluated observation state of the station.
        """
        return ObsState.READY if self._is_configured else ObsState.IDLE
