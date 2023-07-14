# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the SpsStation tango device."""
from __future__ import annotations

import gc
import json
import time
from typing import Iterator
from unittest.mock import Mock

import pytest
from psycopg import sql
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy

from ska_low_mccs_spshw import MccsCalibrationStore
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "admin_mode",
        "command_result",
        "command_status",
        "health_state",
        "state",
        timeout=2.0,
    )


# pylint: disable=too-many-arguments
@pytest.fixture(name="test_context")
def test_context_fixture(
    patched_calibration_store_device_class: type[MccsCalibrationStore],
    database_host: str,
    database_port: int,
    database_name: str,
    database_admin_user: str,
    database_admin_password: str,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Yield into a context in which Tango is running, with mock devices.

    :param patched_calibration_store_device_class: a subclass of MccsCalibrationStore
        that has been patched to mock out the database connection
    :param database_host: the database host
    :param database_port: the database port
    :param database_name: the database name
    :param database_admin_user: the database admin user
    :param database_admin_password: the database admin password

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.set_calibration_store_device(
        device_class=patched_calibration_store_device_class,
        database_host=database_host,
        database_port=database_port,
        database_name=database_name,
        database_admin_user=database_admin_user,
        database_admin_password=database_admin_password,
    )
    with harness as context:
        yield context


@pytest.fixture(name="calibration_store_device")
def calibration_store_device_fixture(
    test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Fixture that returns the calibration store Tango device under test.

    :param test_context: a Tango test context containing a calibration store.

    :yield: the calibration store Tango device under test.
    """
    yield test_context.get_calibration_store_device()


def test_GetSolution(
    calibration_store_device: MccsCalibrationStore, mock_connection: Mock
) -> None:
    """
    Test of the GetCalibration command.

    :param calibration_store_device: the calibration store device under test
    :param mock_connection: the mock database connection
    """
    calibration_store_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]

    # Give the calibration store time to set up
    time.sleep(0.1)

    calibration_store_device.GetSolution(
        json.dumps({"frequency_channel": 5, "outside_temperature": 24.9})
    )

    query = sql.SQL(
        "SELECT calibration, creation_time "
        "FROM tab_mccs_calib "
        "WHERE frequency_channel=%s AND outside_temperature=%s "
        "ORDER BY creation_time DESC"
    )

    mock_connection.execute.assert_called_once_with(query, [5, 24.9])


def test_StoreSolution(
    calibration_store_device: MccsCalibrationStore, mock_connection: Mock
) -> None:
    """
    Test of the StoreSolution command.

    :param calibration_store_device: the calibration store device under test
    :param mock_connection: the mock database connection
    """
    calibration_store_device.adminMode = AdminMode.ONLINE  # type: ignore[assignment]

    # Give the calibration store time to set up
    time.sleep(0.1)

    solution = [5, 5.3, 2.4, 5.1, 2.6, 1.4, 1.8, 10.2, 1.1]

    [result_code], [message] = calibration_store_device.StoreSolution(
        json.dumps(
            {"solution": solution, "frequency_channel": 5, "outside_temperature": 24.9}
        )
    )

    command = sql.SQL(
        "INSERT INTO tab_mccs_calib("
        "creation_time, frequency_channel, outside_temperature, calibration)"
        "VALUES (current_timestamp, %s, %s, %s);"
    )

    mock_connection.execute.assert_called_once_with(command, [5, 24.9, solution])
    assert result_code == ResultCode.OK
    assert message == "Solution stored successfully"
