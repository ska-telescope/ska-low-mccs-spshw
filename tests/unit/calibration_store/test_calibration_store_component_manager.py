#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the calibration store component manager."""
from __future__ import annotations

import logging
from typing import Iterator

import pytest
from ska_control_model import CommunicationStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.calibration_store import CalibrationStoreComponentManager
from tests.harness import SpsTangoTestHarness


@pytest.fixture(name="test_context")
def test_context_fixture() -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    :yields: into a context in which Tango is running
    """
    harness = SpsTangoTestHarness()
    with harness:
        yield


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        timeout=5.0,
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="calibration_store_component_manager")
def calibration_store_component_manager_fixture(
    test_context: None,
    patched_calibration_store_component_manager_class: type[
        CalibrationStoreComponentManager
    ],
    logger: logging.Logger,
    callbacks: MockCallableGroup,
    database_host: str,
    database_port: int,
    database_name: str,
    database_admin_user: str,
    database_admin_password: str,
) -> CalibrationStoreComponentManager:
    """
    Return a station calibrator component manager.

    The database connection for this component manager talks to a mock connection.

    :param test_context: a Tango test context running the required
        mock subservient devices
    :param patched_calibration_store_component_manager_class: the patched component
        manager class with a mock of the database connection
    :param logger: a logger to be used by the commonent manager
    :param callbacks: callback group
    :param database_host: the database host
    :param database_port: the database port
    :param database_name: the database name
    :param database_admin_user: the database admin user
    :param database_admin_password: the database admin password

    :return: a station calibrator component manager.
    """
    return patched_calibration_store_component_manager_class(
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        database_host,
        database_port,
        database_name,
        database_admin_user,
        database_admin_password,
    )


@pytest.mark.forked
def test_communication(
    calibration_store_component_manager: CalibrationStoreComponentManager,
    callbacks: MockCallableGroup,
) -> None:
    """
    Test communication for the calibration store component manager.

    :param calibration_store_component_manager: the calibration store component
        manager under test
    :param callbacks: dictionary of driver callbacks.
    """
    assert (
        calibration_store_component_manager.communication_state
        == CommunicationStatus.DISABLED
    )

    # takes the component out of DISABLED
    calibration_store_component_manager.start_communicating()
    callbacks["communication_status"].assert_call(CommunicationStatus.NOT_ESTABLISHED)
    callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

    calibration_store_component_manager.stop_communicating()

    callbacks["communication_status"].assert_call(CommunicationStatus.DISABLED)
