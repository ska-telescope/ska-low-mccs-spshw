#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the connection to the calibration database."""
from __future__ import annotations

import logging
from typing import Callable

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout
from ska_control_model import CommunicationStatus, ResultCode

DevVarLongStringArrayType = tuple[list[ResultCode], list[str]]


class CalibrationStoreDatabaseConnection:
    """A connection to a postgres database for the calibration store."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: CalibrationStoreDatabaseConnection,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        database_host: str,
        database_port: int,
        database_name: str,
        database_admin_user: str,
        database_admin_password: str,
    ) -> None:
        """
        Initialise a new instance of a database connection.

        :param logger: a logger for this object to use
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param database_host: the database host
        :param database_port: the database port
        :param database_name: the database name
        :param database_admin_user: the database admin user
        :param database_admin_password: the database admin password
        """
        self._logger = logger
        self._connection_pool = self._create_connection_pool(
            database_host,
            database_port,
            database_name,
            database_admin_user,
            database_admin_password,
        )
        self._communication_state_callback = communication_state_callback
        self._timeout = 10

    # pylint: disable=too-many-arguments
    def _create_connection_pool(
        self: CalibrationStoreDatabaseConnection,
        database_host: str,
        database_port: int,
        database_name: str,
        database_admin_user: str,
        database_admin_password: str,
    ) -> ConnectionPool:
        """
        Create the connection pool for connecting to a postgres database.

        :param database_host: the database host
        :param database_port: the database port
        :param database_name: the database name
        :param database_admin_user: the database admin user
        :param database_admin_password: the database admin password

        :return: the connection pool
        """
        conninfo = (
            f"host={database_host} "
            f"port={database_port} "
            f"dbname={database_name} "
            f"user={database_admin_user} "
            f"password={database_admin_password}"
        )
        connect_kwargs = {"row_factory": dict_row}

        return ConnectionPool(conninfo, kwargs=connect_kwargs)

    def verify_database_connection(self: CalibrationStoreDatabaseConnection) -> None:
        """Verify that connection to the database can be established."""
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
        :raises ValueError: if there is no stored solution for the provided inputs
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
            row = result.fetchone()
            if row is None:
                raise ValueError(
                    "Solution not found in database for "
                    f"channel {frequency_channel}, temperature {outside_temperature}"
                )
            return row["calibration"]

    def store_solution(
        self: CalibrationStoreDatabaseConnection,
        solution: list[float],
        frequency_channel: int,
        outside_temperature: float,
    ) -> DevVarLongStringArrayType:
        """
        Store the provided solution in the database.

        :param solution: the solution to store
        :param frequency_channel: the frequency channel that the solution is for
        :param outside_temperature: the outside temperature that the solution is for

        :return: tuple of result code and message.
        """
        with self._connection_pool.connection(self._timeout) as cx:
            query = sql.SQL(
                "INSERT INTO tab_mccs_calib("
                "creation_time, outside_temperature, channel, calibration)"
                "VALUES (current_timestamp, %s, %s, %s);"
            )

            cx.execute(query, [frequency_channel, outside_temperature, solution])
        return ([ResultCode.OK], ["Solution stored successfully"])
