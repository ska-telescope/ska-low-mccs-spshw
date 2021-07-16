# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of an observation state model for a station."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ska_tango_base.control_model import ObsState


__all__ = ["StationObsStateModel"]


class StationObsStateModel:
    """An observation state model for a station."""

    def __init__(
        self: StationObsStateModel,
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

        self._is_resourced = False
        self._is_configured = False
        self._obs_state = self._evaluate_obs_state()

        self._obs_state_changed_callback = obs_state_changed_callback

        assert self._obs_state is not None  # for the type checker
        self._obs_state_changed_callback(self._obs_state)

    def is_resourced_changed(
        self: StationObsStateModel,
        is_resourced: bool,
    ) -> None:
        """
        Handle a change in whether the station is resourced.

        :param is_resourced: whether the station is resourced
        """
        self._is_resourced = is_resourced
        if not is_resourced:
            self._is_configured = False
        self.update_obs_state()

    def is_configured_changed(
        self: StationObsStateModel,
        is_configured: bool,
    ) -> None:
        """
        Handle a change in whether the station is configured.

        :param is_configured: whether the station is configured
        """
        self._is_configured = is_configured
        self.update_obs_state()

    def update_obs_state(self: StationObsStateModel) -> None:
        """Update the observation state, ensuring that the callback is called."""
        obs_state = self._evaluate_obs_state()
        if obs_state is None:
            return
        if self._obs_state != obs_state:
            self._obs_state = obs_state
            self._obs_state_changed_callback(obs_state)

    def _evaluate_obs_state(
        self: StationObsStateModel,
    ) -> Optional[ObsState]:
        """
        Return the evaluated observation state of the station.

        The evaluated observation state is based on whether the station
        is resourced, and whether it is configuring.

        :return: the evaluated observation state of the station.
        """
        obs_state_map = {
            (False, False): ObsState.EMPTY,
            (True, False): ObsState.IDLE,
            (True, True): ObsState.READY,
        }
        try:
            return obs_state_map[(self._is_resourced, self._is_configured)]
        except KeyError:
            self._logger.error(
                "Cannot evaluate obs state: "
                f"resourced: {self._is_resourced}, "
                f"configured: {self._is_configured}, "
            )
            return None
