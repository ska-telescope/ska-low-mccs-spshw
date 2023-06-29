#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the connection to the calibration database"""
from __future__ import annotations

import logging
import os
from typing import Callable

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout
from ska_control_model import CommunicationStatus


def create_connection_pool(
    host: str = "test-postgresql",
    port: int = 5432,
    dbname: str = "postgres",
    user: str = "postgres",
    password: str = "",
) -> ConnectionPool:
    """
    Create the connection pool for connecting to a postgres database.

    :return: the connection pool
    """
    conninfo = (
        f"host={host} "
        f"port={port} "
        f"dbname={dbname} "
        f"user={user} "
        f"password={password}"
    )
    connect_kwargs = {"row_factory": dict_row}

    return ConnectionPool(conninfo, kwargs=connect_kwargs)


class CalibrationStoreDatabaseConnection:
    """A connection to a postgres database for the calibration store."""

    def __init__(
        self: CalibrationStoreDatabaseConnection,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        host: str = "test-postgresql",
        port: int = 5432,
        dbname: str = "postgres",
        user: str = "postgres",
        password: str = "",
    ) -> None:
        """Initialise a new instance of a database connection."""
        self._logger = logger
        self._connection_pool = create_connection_pool(host, port, dbname, user, password)
        self._communication_state_callback = communication_state_callback
        self._timeout = 10

    def verify_database_connection(self: CalibrationStoreDatabaseConnection) -> None:
        """Verify that connection to the database can be established"""
        try:
            self._connection_pool.wait(self._timeout)
        except PoolTimeout:
            self._logger.error("Timed out forming database connection")
            self._communication_state_callback(CommunicationStatus.NOT_ESTABLISHED)
        self._logger.info("Database connection established successfully")
        self._communication_state_callback(CommunicationStatus.ESTABLISHED)

    def get_solution(
        self: CalibrationStoreDatabaseConnection,
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
        with self._connection_pool.connection(self._timeout) as cx:
            query = sql.SQL(
                "SELECT calibration, creation_time "
                "FROM tab_mccs_calib "
                "WHERE frequency_channel=%s AND outside_temperature=%s "
                "ORDER BY creation_time DESC"
            )

            result = cx.execute(query, [frequency_channel, outside_temperature])
            return result.fetchone()["calibration"]

    def store_solution(
        self: CalibrationStoreDatabaseConnection,
        solution: list[float],
        frequency_channel: int,
        outside_temperature: float,
    ) -> None:
        """
        Store the provided solution in the database

        :param solution: the solution to store
        :param frequency_channel: the frequency channel that the solution is for
        :param outside_temperature: the outside temperature that the solution is for
        """
        with self._connection_pool.connection(self._timeout) as cx:
            query = sql.SQL(
                "INSERT INTO tab_mccs_calib("
                "creation_time, outside_temperature, channel, calibration)"
                "VALUES (current_timestamp, %s, %s, %s);"
            )

            cx.execute(query, [frequency_channel, outside_temperature, solution])
