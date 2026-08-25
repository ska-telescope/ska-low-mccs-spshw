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

from ska_low_mccs_spshw.tile import firmware_threshold_interface
from ska_low_mccs_spshw.tile.firmware_threshold_interface import (
    FirmwareThresholds,
    FirmwareThresholdsDbAdapter,
    _is_running_without_database,
)


def test_no_running_server_defaults_to_real_database_behaviour() -> None:
    """Test that the no-db check defaults to False with no Tango server running."""
    # This test runs with no Tango device server started, exactly like a
    # real deployment where the database happens to be unreachable would
    # look from this function's point of view. It must default to "assume
    # a real database", not to "assume no-db mode".
    assert _is_running_without_database() is False


def test_no_db_mode_swallows_a_failed_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that a DB failure in no-db mode is swallowed, leaving defaults.

    :param monkeypatch: pytest fixture for patching module attributes.
    """
    monkeypatch.setattr(
        firmware_threshold_interface, "_is_running_without_database", lambda: True
    )
    failing_db = MagicMock()
    failing_db.get_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )
    failing_db.put_device_attribute_property.side_effect = tango.DevFailed(
        "Failed to connect to database"
    )

    thresholds = FirmwareThresholds()
    adapter = FirmwareThresholdsDbAdapter(
        device_name="test/tile/1",
        thresholds=thresholds,
        db_connection=failing_db,
    )
    assert thresholds.fpga1_alarm_threshold == "Undefined"

    adapter.write_threshold_to_db()  # should not raise
    adapter.resync_with_db()  # should not raise


def test_real_database_failure_at_init_propagates() -> None:
    """Test that a database failure in real (non-no-db) mode is not swallowed."""
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
    """Test that a database failure on write in real mode is not swallowed."""
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


def test_no_db_detection_is_irrelevant_when_database_call_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that a successful DB call is used as-is, regardless of no-db detection.

    This is a regression guard for the "try first, only consult no-db
    detection on failure" ordering: a device server that mocks/injects a
    working database connection (as our own device-level unit tests do,
    via a patched ``Database`` class) must have that connection used
    normally, even though those tests also happen to run inside a
    file-based Tango test context that would otherwise look like a
    deliberate no-db (e.g. ``tangodocgen``) scenario.

    :param monkeypatch: pytest fixture for patching module attributes.
    """
    monkeypatch.setattr(
        firmware_threshold_interface, "_is_running_without_database", lambda: True
    )
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
