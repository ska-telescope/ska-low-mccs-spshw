#
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for power marshallers."""
from __future__ import annotations

import logging
from typing import Callable

from ska_control_model import CommunicationStatus
from ska_low_mccs_common.component import MccsBaseComponentManager
from ska_tango_base.base import CommunicationStatusCallbackType
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = ["PowerMarshallerComponentManager"]


class PowerMarshallerComponentManager(
    MccsBaseComponentManager, TaskExecutorComponentManager
):
    """A component manager for a station."""

    def __init__(
        self: PowerMarshallerComponentManager,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        super().__init__(
            logger=logger,
            communication_state_callback=communication_state_callback,
            component_state_callback=component_state_callback,
        )

    def start_communicating(self: PowerMarshallerComponentManager) -> None:
        """Establish communication with the station components."""
        if self._communication_state_callback:
            self._communication_state_callback(CommunicationStatus.ESTABLISHED)

    def stop_communicating(self: PowerMarshallerComponentManager) -> None:
        """Break off communication with the station components."""
        if self._communication_state_callback:
            self._communication_state_callback(CommunicationStatus.DISABLED)
