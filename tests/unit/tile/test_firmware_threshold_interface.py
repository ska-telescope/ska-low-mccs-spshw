# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the firmware thresholds DB adapter."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import tango

from ska_low_mccs_spshw.tile.firmware_threshold_interface import (
    FirmwareThresholds,
    FirmwareThresholdsDbAdapter,
)


@pytest.fixture(name="unreachable_db")
def unreachable_db_fixture() -> MagicMock:
    """
    Return a mock DB connection that always raises DevFailed.

    :return: a mock Tango database connection that behaves as though the
        Tango database cannot be reached.
    """
    db = MagicMock()
    db.get_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )
    db.put_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )
    return db


def test_init_tolerates_unreachable_database(unreachable_db: MagicMock) -> None:
    """
    Test that construction survives an unreachable Tango database.

    :param unreachable_db: a mock DB connection that always fails.
    """
    thresholds = FirmwareThresholds()
    adapter = FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=unreachable_db,
    )
    assert thresholds.fpga1_alarm_threshold == "Undefined"
    unreachable_db.get_device_attribute_property.assert_called_once()

    # A later resync should retry against the database rather than raising.
    adapter.resync_with_db()
    assert unreachable_db.get_device_attribute_property.call_count == 2


def test_write_tolerates_unreachable_database(unreachable_db: MagicMock) -> None:
    """
    Test that writing thresholds survives an unreachable Tango database.

    :param unreachable_db: a mock DB connection that always fails.
    """
    thresholds = FirmwareThresholds()
    adapter = FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=unreachable_db,
    )

    adapter.write_threshold_to_db()  # should not raise

    unreachable_db.put_device_attribute_property.assert_called_once()
