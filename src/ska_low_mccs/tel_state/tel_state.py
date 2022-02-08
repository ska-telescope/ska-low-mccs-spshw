# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains a placeholder for a telescope state component."""
from __future__ import annotations

import logging

from ska_low_mccs.component import ObjectComponent

__all__ = ["TelState"]


class TelState(ObjectComponent):
    """A placeholder for a telescope state component."""

    def __init__(
        self: TelState,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this component to use
        """
        self._logger = logger

        self._elements_states = ""
        self._observations_states = ""
        self._algorithms = ""
        self._algorithms_version = ""

    @property
    def elements_states(self: TelState) -> str:
        """
        Return the elements_states attribute.

        :todo: What is this?

        :return: the elements_states attribute
        """
        return self._elements_states

    @elements_states.setter
    def elements_states(self: TelState, value: str) -> None:
        """
        Set the elements_states attribute.

        :todo: What is this?

        :param value: the new elements_states attribute value
        """
        self._elements_states = value

    @property
    def observations_states(self: TelState) -> str:
        """
        Return the observations_states attribute.

        :todo: What is this?

        :return: the observations_states attribute
        """
        return self._observations_states

    @observations_states.setter
    def observations_states(self: TelState, value: str) -> None:
        """
        Set the observations_states attribute.

        :todo: What is this?

        :param value: the new observations_states attribute value
        """
        self._observations_states = value

    @property
    def algorithms(self: TelState) -> str:
        """
        Return the algorithms attribute.

        :todo: What is this? TBD

        :return: the algorithms attribute
        """
        return self._algorithms

    @algorithms.setter
    def algorithms(self: TelState, value: str) -> None:
        """
        Set the algorithms attribute.

        :todo: What is this? TBD

        :param value: the new value for the algorithms attribute
        """
        self._algorithms = value

    @property
    def algorithms_version(self: TelState) -> str:
        """
        Return the algorithm version.

        :return: the algorithm version
        """
        return self._algorithms_version

    @algorithms_version.setter
    def algorithms_version(self: TelState, value: str) -> None:
        """
        Set the algorithm version.

        :param value: the new value for the algorithm version
        """
        self._algorithms_version = value
