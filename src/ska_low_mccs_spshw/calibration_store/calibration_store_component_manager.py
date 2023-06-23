#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the component management for a calibration store."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ska_control_model import CommunicationStatus, PowerState
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = ["CalibrationStoreComponentManager"]


# pylint: disable-next=abstract-method
class CalibrationStoreComponentManager(TaskExecutorComponentManager):
    """A component manager for MccsCalibrationStore."""

    def __init__(
        self: CalibrationStoreComponentManager,
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
        self._communication_state_callback = communication_state_changed_callback
        self._component_state_callback = component_state_changed_callback
        self.logger = logger

    def start_communicating(self: CalibrationStoreComponentManager) -> None:
        """Establish communication."""
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
        self._update_communication_state(CommunicationStatus.ESTABLISHED)

    def stop_communicating(self: CalibrationStoreComponentManager) -> None:
        """Break off communication."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)
