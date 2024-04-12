# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the calibration system."""

from __future__ import annotations

import json
import time
from typing import Any, Iterator, Optional

import pytest
import tango
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import SpsTangoTestHarnessContext


@scenario(
    "features/calibration.feature",
    "Store a calibration solution",
)
def test_storing_solution(database_connection_pool: ConnectionPool) -> None:
    """
    Test storing a calibration solution.

    Check that when a solution is sent to the MccsCalibrationStore, the solution
    is stored in the database.

    Bear in mind that data in the database will persist between test runs if not
    cleaned up, so here we remove any data from the table.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


@scenario(
    "features/calibration.feature",
    "Add a calibration solution to existing table",
)
def test_add_to_existing_table(database_connection_pool: ConnectionPool) -> None:
    """
    Test storing a calibration solution when there's already data.

    Check that when a solution is sent to the MccsCalibrationStore, the solution
    is stored in the database, without overwriting existing data.

    Bear in mind that data in the database will persist between test runs if not
    cleaned up, so here we remove any data from the table.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


@scenario(
    "features/calibration.feature",
    "Load a non-existent calibration solution",
)
def test_loading_non_existent_solution(
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Test retrieving a calibration solution for inputs that don't have a solution.

    This should return an empty array to indicate the solution doesn't exist.

    Bear in mind that data in the database will persist between test runs if not
    cleaned up, so here we remove any data from the table.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


@scenario(
    "features/calibration.feature",
    "Load a calibration solution",
)
def test_loading_solution(database_connection_pool: ConnectionPool) -> None:
    """
    Test retrieving a calibration solution.

    Check that when the station calibrator tries to retrieve an existing solution,
    the correct solution is returned.

    Bear in mind that data in the database will persist between test runs if not
    cleaned up, so here we remove any data from the table.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


@scenario(
    "features/calibration.feature",
    "Load a calibration solution with multiple available",
)
def test_loading_solution_multiple_available(
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Test retrieving a calibration solution, when there are multiple available.

    Check that when the station calibrator tries to retrieve an existing solution,
    the most recently stored solution is returned.

    Bear in mind that data in the database will persist between test runs if not
    cleaned up, so here we remove any data from the table.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


def empty_table(database_connection_pool: ConnectionPool) -> None:
    """
    Empty the table from leftover data from previous test runs.

    :param database_connection_pool: connection pool for the database
    """
    with database_connection_pool.connection() as cx:
        cx.execute("DELETE FROM tab_mccs_calib")


# pylint: disable=too-many-arguments
@pytest.fixture(name="database_connection_pool")
def database_connection_pool_fixture(
    true_context: bool,
    database_host: str,
    database_port: int,
    database_name: str,
    database_admin_user: str,
    database_admin_password: str,
) -> ConnectionPool:
    """
    Get a connection pool for the database.

    :param true_context: whether to test against an existing Tango deployment
    :param database_host: the database host
    :param database_port: the database port
    :param database_name: the database name
    :param database_admin_user: the database admin user
    :param database_admin_password: the database admin password
    :return: a connection pool for the database
    """
    if not true_context:
        pytest.xfail(
            "Functional testing of the calibration store requires a "
            "full deployment including a database"
        )
    conninfo = (
        f"host={database_host} "
        f"port={database_port} "
        f"dbname={database_name} "
        f"user={database_admin_user} "
        f"password={database_admin_password}"
    )
    connect_kwargs = {"row_factory": dict_row}

    return ConnectionPool(conninfo, kwargs=connect_kwargs)


@pytest.fixture(name="calibration_solution")
def calibration_solution_fixture() -> list[float]:
    """
    Fixture that provides a sample calibration solution.

    This is distinct to the calibration solutions that may be initially stored in the
    database, so that it can be verified that the correct solution is retrieved.

    :return: a sample calibration solution.
    """
    return [float(2)] + [0.7 * i for i in range(8)]


@pytest.fixture(name="alternative_calibration_solutions")
def alternative_calibration_solutions_fixture(
    frequency_channel: int, outside_temperature: float
) -> dict[tuple[int, float], list[float]]:
    """
    Fixture that provides alternative sample calibration solutions.

    This is used to test for when there are multiple solutions for the same inputs,
    that the correct one is retrieved.

    :param outside_temperature: a fixture with an outside temperature
    :param frequency_channel: a fixture with a calibration frequency channel

    :return: a sample calibration solution. The keys are tuples of the channel
        and the outside temperature, and the values are lists of calibration values
    """
    return {
        (frequency_channel, outside_temperature): [float(1)]
        + [0.5 * i for i in range(8)],
        (23, 25.0): [float(4)] + [0.8 * i for i in range(8)],
        (45, 25.0): [float(7)] + [1.4 * (i % 2) for i in range(8)],
        (23, 30.0): [float(1)] + [0.1 * i for i in range(8)],
        (45, 30.0): [float(2)] + [1.1 * (i % 2) for i in range(8)],
        (23, 35.0): [float(4)] + [0.9 * i for i in range(8)],
        (45, 35.0): [float(8)] + [1.4 * (i % 2) for i in range(8)],
    }


@pytest.fixture(name="unused_outside_temperature")
def unused_outside_temperature_fixture() -> float:
    """
    Fixture for a not calibrated-for outside temperature.

    :return: the outside temperature
    """
    return 15.0


@pytest.fixture(name="unused_frequency_channel")
def unused_frequency_channel_fixture() -> int:
    """
    Fixture for a not calibrated-for calibration frequency channel.

    :return: the frequency channel
    """
    return 13


@given("a calibration store that is online", target_fixture="calibration_store")
def given_a_calibration_store(
    true_context: bool,
    functional_test_context: SpsTangoTestHarnessContext,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Iterator[tango.DeviceProxy]:
    """
    Yield the calibration store device under test.

    :param true_context: whether to test against an existing Tango deployment
    :param functional_test_context: the context in which the test is running.
    :param change_event_callbacks: A change event callback group.

    :yield: the calibration store device
    """
    if not true_context:
        pytest.xfail(
            "Functional testing of the calibration store requires a "
            "full deployment including a database"
        )
    calibration_store = functional_test_context.get_calibration_store_device()

    calibration_store.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["calibration_store_state"],
    )

    admin_mode = calibration_store.adminMode
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "calibration_store_state", tango.DevState.DISABLE
        )

        calibration_store.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "calibration_store_state", tango.DevState.UNKNOWN
        )
        change_event_callbacks.assert_change_event(
            "calibration_store_state", tango.DevState.ON
        )
    else:
        change_event_callbacks.assert_change_event(
            "calibration_store_state", tango.DevState.ON
        )
    yield calibration_store


@given("a field station that is online", target_fixture="field_station")
def given_a_field_station(
    functional_test_context: SpsTangoTestHarnessContext,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Iterator[tango.DeviceProxy]:
    """
    Yield the field station device under test.

    :param functional_test_context: the context in which the test is running.
    :param change_event_callbacks: A change event callback group.

    :yield: the field station device
    """
    field_station = functional_test_context.get_field_station_device()

    field_station.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["field_station_state"],
    )

    admin_mode = field_station.adminMode
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "field_station_state", tango.DevState.DISABLE
        )

        field_station.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "field_station_state", tango.DevState.UNKNOWN
        )
        change_event_callbacks.assert_change_event(
            "field_station_state", tango.DevState.ON
        )
    else:
        change_event_callbacks.assert_change_event(
            "field_station_state", tango.DevState.ON
        )
    yield field_station


@given("a station calibrator that is online", target_fixture="station_calibrator")
def given_a_station_calibrator(
    functional_test_context: SpsTangoTestHarnessContext,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Iterator[tango.DeviceProxy]:
    """
    Yield the station calibrator device under test.

    :param functional_test_context: the context in which the test is running.
    :param change_event_callbacks: A change event callback group.

    :yield: the station calibrator device
    """
    station_calibrator = functional_test_context.get_station_calibrator_device()

    station_calibrator.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["station_calibrator_state"],
    )

    admin_mode = station_calibrator.adminMode
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "station_calibrator_state", tango.DevState.DISABLE
        )

        station_calibrator.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "station_calibrator_state", tango.DevState.UNKNOWN
        )
        change_event_callbacks.assert_change_event(
            "station_calibrator_state", tango.DevState.ON
        )
    else:
        change_event_callbacks.assert_change_event(
            "station_calibrator_state", tango.DevState.ON
        )
    yield station_calibrator


@given("the database table is initially empty")
def given_initial_empty_table(database_connection_pool: ConnectionPool) -> None:
    """
    Empty the table from leftover data from previous test runs.

    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)


@given("the calibration store database contains calibration solutions")
def given_database_has_solutions(
    calibration_solutions: dict[tuple[int, float], list[float]],
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Populate the database with test data.

    :param calibration_solutions: the calibration solutions to store
    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)

    with database_connection_pool.connection() as cx:
        for channel, temperature in calibration_solutions:
            query = sql.SQL(
                "INSERT INTO tab_mccs_calib("
                "creation_time, frequency_channel, outside_temperature, calibration)"
                "VALUES (current_timestamp, %s, %s, %s);"
            )

            cx.execute(
                query,
                [channel, temperature, calibration_solutions[(channel, temperature)]],
            )


@given(
    "the calibration store database contains multiple calibration solutions "
    "for the same inputs"
)
def given_database_has_multiple_solutions(
    calibration_solutions: dict[tuple[int, float], list[float]],
    alternative_calibration_solutions: dict[tuple[int, float], list[float]],
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Populate the database with multiple solutions for the same inputs.

    :param calibration_solutions: the calibration solutions to store
    :param alternative_calibration_solutions: the alternative calibration
        solutions to store
    :param database_connection_pool: connection pool for the database
    """
    empty_table(database_connection_pool)

    with database_connection_pool.connection() as cx:
        for channel, temperature in calibration_solutions:
            query = sql.SQL(
                "INSERT INTO tab_mccs_calib("
                "creation_time, frequency_channel, outside_temperature, calibration)"
                "VALUES (current_timestamp, %s, %s, %s);"
            )

            cx.execute(
                query,
                [channel, temperature, calibration_solutions[(channel, temperature)]],
            )
        # Commit the database transaction for the first set of data
        cx.commit()

        # brief pause before inserting the new set of data
        time.sleep(0.1)

        for channel, temperature in alternative_calibration_solutions:
            query = sql.SQL(
                "INSERT INTO tab_mccs_calib("
                "creation_time, frequency_channel, outside_temperature, calibration)"
                "VALUES (current_timestamp, %s, %s, %s);"
            )

            cx.execute(
                query,
                [
                    channel,
                    temperature,
                    alternative_calibration_solutions[(channel, temperature)],
                ],
            )


@given("the field station has read the outside temperature")
def given_field_station_has_read_temperature(
    field_station: tango.DeviceProxy,
    outside_temperature: float,
) -> None:
    """
    Make the mock field station device push a change in the outside temperature.

    :param field_station: proxy to the field station
    :param outside_temperature: the outside temperature
    """
    assert field_station.adminMode == AdminMode.ONLINE
    assert field_station.state() == tango.DevState.ON

    [result_code], [_] = field_station.MockOutsideTemperatureChange(outside_temperature)
    assert result_code == ResultCode.OK


@when("the calibration store is given a solution to store")
def when_store_solution(
    calibration_store: tango.DeviceProxy,
    outside_temperature: float,
    frequency_channel: int,
    calibration_solution: list[float],
) -> None:
    """
    Use the Calibration Store device to store a solution.

    :param calibration_store: proxy to the calibration store
    :param outside_temperature: the outside temperature
    :param frequency_channel: the frequency channel to calibrate for
    :param calibration_solution: the test calibration solution
    """
    [result_code], [message] = calibration_store.StoreSolution(
        json.dumps(
            {
                "frequency_channel": frequency_channel,
                "outside_temperature": outside_temperature,
                "solution": calibration_solution,
            }
        )
    )
    assert result_code == ResultCode.OK
    assert message == "Solution stored successfully"


@then("the solution is stored in the database")
def then_solution_stored(
    calibration_solution: list[float],
    outside_temperature: float,
    frequency_channel: int,
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Verify the database contains the intended data.

    :param calibration_solution: the newly stored solution
    :param outside_temperature: the outside temperature
    :param frequency_channel: the frequency channel
    :param database_connection_pool: connection pool for the database
    """
    with database_connection_pool.connection() as cx:
        query = sql.SQL(
            "SELECT calibration, creation_time "
            "FROM tab_mccs_calib "
            "WHERE frequency_channel=%s AND outside_temperature=%s "
            "ORDER BY creation_time DESC"
        )

        result = cx.execute(query, [frequency_channel, outside_temperature])
        # fetchone to get the most recent
        row: Optional[dict[str, Any]] = result.fetchone()  # type: ignore[assignment]
        if row is None:
            pytest.fail(
                "Solution not found in database for "
                f"channel {frequency_channel}, temperature {outside_temperature}"
            )
        assert row["calibration"] == pytest.approx(  # type: ignore[call-overload]
            calibration_solution
        )


@then("existing data is not overwritten")
def then_existing_data_not_overwritten(
    calibration_solutions: dict[tuple[int, float], list[float]],
    outside_temperature: float,
    frequency_channel: int,
    database_connection_pool: ConnectionPool,
) -> None:
    """
    Verify the database still contains existing data.

    :param calibration_solutions: the initially stored solutions
    :param outside_temperature: the outside temperature
    :param frequency_channel: the frequency channel
    :param database_connection_pool: connection pool for the database
    """
    with database_connection_pool.connection() as cx:
        query = sql.SQL(
            "SELECT calibration, creation_time "
            "FROM tab_mccs_calib "
            "WHERE frequency_channel=%s AND outside_temperature=%s "
            "ORDER BY creation_time DESC"
        )

        result = cx.execute(query, [frequency_channel, outside_temperature])
        # fetchone to pop the most recent, which will be the newly added data
        result.fetchone()

        # then get the second-most recent, which will be the existing data
        row: Optional[dict[str, Any]] = result.fetchone()  # type: ignore[assignment]
        if row is None:
            pytest.fail(
                "Solution not found in database for "
                f"channel {frequency_channel}, temperature {outside_temperature}"
            )
        assert row["calibration"] == pytest.approx(  # type: ignore[call-overload]
            calibration_solutions[(frequency_channel, outside_temperature)]
        )


@when(
    "the station calibrator tries to get a calibration solution",
    target_fixture="retrieved_solution",
)
def when_get_calibration(
    station_calibrator: tango.DeviceProxy,
    frequency_channel: int,
) -> list[float]:
    """
    Retrieve a calibration solution using the station calibrator.

    :param station_calibrator: proxy to the station calibrator
    :param frequency_channel: the frequency channel to get a solution for
    :return: the retrieved calibration solution
    """
    retrieved_solution = station_calibrator.GetCalibration(
        json.dumps({"frequency_channel": frequency_channel})
    )
    # TODO: Fix this race condition properly
    if not list(retrieved_solution):
        time.sleep(5.0)
        retrieved_solution = station_calibrator.GetCalibration(
            json.dumps({"frequency_channel": frequency_channel})
        )
    return retrieved_solution


@when(
    "the calibration store tries to get a calibration solution not in the database",
    target_fixture="missing_solution",
)
def when_get_non_existent_calibration(
    calibration_store: tango.DeviceProxy,
    unused_outside_temperature: float,
    unused_frequency_channel: int,
) -> list[float]:
    """
    Retrieve a non_existent calibration solution using the calibration store.

    This should return just an empty list since the solution does not exist

    :param calibration_store: proxy to the station calibrator
    :param unused_outside_temperature: the outside temperature to get a solution for
    :param unused_frequency_channel: the frequency channel to get a solution for
    :return: the retrieved calibration solution, which is an empty list
    """
    return calibration_store.GetSolution(
        json.dumps(
            {
                "outside_temperature": unused_outside_temperature,
                "frequency_channel": unused_frequency_channel,
            }
        )
    )


@then("the calibration store returns an empty array")
def then_empty_calibration(
    missing_solution: list[float],
) -> None:
    """
    Verify the returned solution is an empty array.

    :param missing_solution: the retrieved solution from the database
    """
    assert not missing_solution


@then("the correct calibration solution is retrieved")
def then_correct_calibration(
    retrieved_solution: list[float],
    calibration_solutions: dict[tuple[int, float], list[float]],
    outside_temperature: float,
    frequency_channel: int,
) -> None:
    """
    Verify the returned solution is the one stored previously.

    :param retrieved_solution: the retrieved solution from the database
    :param calibration_solutions: the initially stored solutions
    :param outside_temperature: the outside temperature
    :param frequency_channel: the frequency channel
    """
    assert retrieved_solution == pytest.approx(
        calibration_solutions[(frequency_channel, outside_temperature)]
    )


@then("the most recently stored calibration solution is retrieved")
def then_most_recent_calibration(
    retrieved_solution: list[float],
    alternative_calibration_solutions: dict[tuple[int, float], list[float]],
    outside_temperature: float,
    frequency_channel: int,
) -> None:
    """
    Verify the returned solution is the one stored most recently.

    :param retrieved_solution: the retrieved solution from the database
    :param alternative_calibration_solutions: the most recently stored solutions
    :param outside_temperature: the outside temperature
    :param frequency_channel: the frequency channel
    """
    assert retrieved_solution == pytest.approx(
        alternative_calibration_solutions[(frequency_channel, outside_temperature)]
    )
