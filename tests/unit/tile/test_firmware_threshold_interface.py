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


def test_no_database_connection_skips_sync_without_touching_it() -> None:
    """Test that a None db_connection skips the database phase entirely."""
    thresholds = FirmwareThresholds()

    adapter = FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=None,
    )
    assert thresholds.fpga1_alarm_threshold == "Undefined"

    adapter.write_threshold_to_db()  # should not raise
    adapter.resync_with_db()  # should not raise


def test_real_database_failure_at_init_propagates() -> None:
    """Test that a database failure with a real db_connection is not swallowed."""
    thresholds = FirmwareThresholds()
    failing_db = MagicMock()
    failing_db.get_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )

    with pytest.raises(tango.DevFailed):
        FirmwareThresholdsDbAdapter(
            device_name="test/tile/1",
            thresholds=thresholds,
            db_connection=failing_db,
        )


def test_real_database_write_failure_propagates() -> None:
    """Test that a database failure on write with a real connection propagates."""
    thresholds = FirmwareThresholds()
    working_db = MagicMock()
    working_db.get_device_attribute_property.return_value = {
        "temperatures": {},
        "voltages": {},
        "currents": {},
    }
    adapter = FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=working_db,
    )

    working_db.put_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )
    with pytest.raises(tango.DevFailed):
        adapter.write_threshold_to_db()


def test_injected_database_is_used_when_provided() -> None:
    """Test that a working, injected db_connection is used to sync thresholds."""
    thresholds = FirmwareThresholds()
    working_db = MagicMock()
    working_db.get_device_attribute_property.return_value = {
        "temperatures": {"fpga1_alarm_threshold": ["70"]},
        "voltages": {},
        "currents": {},
    }

    FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=working_db,
    )

    working_db.get_device_attribute_property.assert_called_once()
    assert thresholds.fpga1_alarm_threshold == 70
