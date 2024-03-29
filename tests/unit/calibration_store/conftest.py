#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a harness for unit testing the Calibration store module."""
from __future__ import annotations

import logging
from typing import Any, Callable
from unittest.mock import MagicMock, Mock

import pytest
from ska_control_model import CommunicationStatus

from ska_low_mccs_spshw.calibration_store import (
    CalibrationStoreComponentManager,
    CalibrationStoreDatabaseConnection,
    MccsCalibrationStore,
)


@pytest.fixture(name="mock_connection")
def mock_connection_fixture() -> Mock:
    """
    Fixture for the mock connection for the mock connection pool to use.

    :return: a mock connection
    """
    connection = MagicMock()
    connection.__enter__ = lambda self: self
    return connection


@pytest.fixture(name="mock_connection_pool")
def mock_connection_pool_fixture(mock_connection: Mock) -> Mock:
    """
    Fixture for the mock connection pool to use.

    :param mock_connection: the mock connection to use
    :return: a mock connection pool.
    """
    connection_pool = Mock()
    connection_pool.connection = lambda _: mock_connection
    return connection_pool


@pytest.fixture(name="patched_calibration_store_database_connection_class")
def patched_calibration_store_database_connection_class_fixture(
    mock_connection_pool: Mock,
) -> type[CalibrationStoreDatabaseConnection]:
    """
    Return a calibration store database connection with the connection pool mocked out.

    :param mock_connection_pool: the mocked database connection pool
    :return: a calibration store database connection with a mocked connection pool.
    """

    class PatchedCalibrationStoreDatabaseConnection(CalibrationStoreDatabaseConnection):
        """
        Patched CalibrationStoreDatabaseConnection.

        It has been patched to have a mocked out connection pool.
        """

        def _create_connection_pool(
            self: PatchedCalibrationStoreDatabaseConnection, *args: Any, **kwargs: Any
        ) -> Mock:
            """
            Create the mock connection pool for connecting to a postgres database.

            :param args: positional arguments (ignored here)
            :param kwargs: named arguments (ignored here)
            :return: the mock connection pool
            """
            return mock_connection_pool

    return PatchedCalibrationStoreDatabaseConnection


@pytest.fixture(name="patched_calibration_store_component_manager_class")
def patched_calibration_store_component_manager_class_fixture(
    patched_calibration_store_database_connection_class: type[
        CalibrationStoreDatabaseConnection
    ],
) -> type[CalibrationStoreComponentManager]:
    """
    Return a patched calibration store component manager.

    It has been patched to have the database connection mocked out.

    :param patched_calibration_store_database_connection_class: patched class for the
        database connection with a mocked connection pool

    :return: a calibration store component manager with a mocked database connection.
    """

    class PatchedCalibrationStoreComponentManager(CalibrationStoreComponentManager):
        """
        Patched CalibrationStoreComponentManager.

        It has been patched to have a mocked out database connection.
        """

        # pylint: disable=too-many-arguments
        def create_database_connection(
            self: PatchedCalibrationStoreComponentManager,
            logger: logging.Logger,
            communication_state_changed_callback: Callable[[CommunicationStatus], None],
            database_host: str,
            database_port: int,
            database_name: str,
            database_admin_user: str,
            database_admin_password: str,
        ) -> CalibrationStoreDatabaseConnection:
            return patched_calibration_store_database_connection_class(
                logger,
                communication_state_changed_callback,
                database_host,
                database_port,
                database_name,
                database_admin_user,
                database_admin_password,
            )

    return PatchedCalibrationStoreComponentManager


@pytest.fixture(name="patched_calibration_store_device_class")
def patched_calibration_store_device_class_fixture(
    patched_calibration_store_component_manager_class: type[
        CalibrationStoreComponentManager
    ],
) -> type[MccsCalibrationStore]:
    """
    Return a calibration store device class patched with extra methods for testing.

    :param patched_calibration_store_component_manager_class: patched class for the
        component manager with a mocked database connection

    :return: a calibration store device class patched with extra methods for testing.
    """

    class PatchedCalibrationStoreDevice(MccsCalibrationStore):
        """MccsCalibrationStore patched with mocked out database connection."""

        def create_component_manager(
            self: PatchedCalibrationStoreDevice,
        ) -> CalibrationStoreComponentManager:
            """
            Create and return a component manager for this device.

            :return: a component manager for this device.
            """
            return patched_calibration_store_component_manager_class(
                self.logger,
                self._component_communication_state_changed,
                self._component_state_changed,
                self.DatabaseHost,
                self.DatabasePort,
                self.DatabaseName,
                self.DatabaseAdminUser,
                self.DatabaseAdminPassword,
            )

    return PatchedCalibrationStoreDevice
