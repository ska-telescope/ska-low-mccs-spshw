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

from .calibration_store_database_connection import CalibrationStoreDatabaseConnection

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
        host: str = "test-postgresql",
        port: int = 5432,
        dbname: str = "postgres",
        user: str = "postgres",
        password: str = "",
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
        self._database_connection = CalibrationStoreDatabaseConnection(
            logger, communication_state_changed_callback, host, port, dbname, user, password
        )

    def start_communicating(self: CalibrationStoreComponentManager) -> None:
        """Establish communication."""
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        self._database_connection.verify_database_connection()

    def stop_communicating(self: CalibrationStoreComponentManager) -> None:
        """Break off communication."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)

    def get_solution(
        self: CalibrationStoreComponentManager,
        frequency_channel: int,
        outside_temperature: float,
    ) -> list[float]:
        """
        Get a solution for the provided frequency and outside temperature.

        This at present will return the most recently stored solution for the inputs.

        :param frequency_channel: the frequency channel of the desired solution.
        :param outside_temperature: the outside temperature of the desired solution.
        :return: a calibration solution from the database.
        """
        return self._database_connection.get_solution(
            frequency_channel, outside_temperature
        )

    def store_solution(
        self: CalibrationStoreComponentManager,
        solution: list[float],
        frequency_channel: int,
        outside_temperature: float,
    ) -> None:
        """
        Store the provided solution in the database.

        :param solution: the solution to store
        :param frequency_channel: the frequency channel that the solution is for
        :param outside_temperature: the outside temperature that the solution is for
        """
        return self._database_connection.store_solution(
            solution, frequency_channel, outside_temperature
        )
