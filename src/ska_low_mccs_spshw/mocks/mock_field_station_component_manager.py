#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the mock component management for mock field station."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ska_control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = ["MockFieldStationComponentManager"]


# pylint: disable-next=abstract-method
class MockFieldStationComponentManager(TaskExecutorComponentManager):
    """A mock component manager for MockFieldStation."""

    def __init__(
        self: MockFieldStationComponentManager,
        logger: logging.Logger,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[
            [Optional[bool], Optional[PowerState]], None
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param component_state_changed_callback: callback to be
            called when the component state changes
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        super().__init__(
            logger,
            communication_state_changed_callback,
            component_state_changed_callback,
            max_workers=1,
        )

        self.logger = logger

    def start_communicating(self: MockFieldStationComponentManager) -> None:
        """Establish communication."""
        self.logger.info("start_comms")

    def stop_communicating(self: MockFieldStationComponentManager) -> None:
        """Break off communication with the pasdBus."""
        self.logger.info("stop_comms")
