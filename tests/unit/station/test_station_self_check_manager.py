#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

import unittest.mock
from typing import Iterator

import pytest

from ska_low_mccs_spshw.station import SpsStationSelfCheckManager
from ska_low_mccs_spshw.station.tests import TestResult
from tests.harness import SpsTangoTestHarness


@pytest.fixture(name="test_context")
def test_context_fixture(
    subrack_id: int,
    mock_subrack_device_proxy: unittest.mock.Mock,
    tile_id: int,
    mock_tile_device_proxy: unittest.mock.Mock,
    daq_id: int,
) -> Iterator[None]:
    """
    Yield into a context in which Tango is running, with mock devices.

    The station component manager acts as a Tango client to the subrack
    and tile Tango device. In these unit tests, the subrack and tile
    Tango devices are mocked out, but since the station component
    manager uses tango to talk to them, we still need some semblance of
    a tango subsystem in place. Here, we assume that the station has
    only one subrack and one tile.

    :param subrack_id: ID of the subrack Tango device to be mocked
    :param mock_subrack_device_proxy: a mock subrack device proxy
        that has been configured with the required subrack behaviours.
    :param tile_id: ID of the tile Tango device to be mocked
    :param mock_tile_device_proxy: a mock tile device proxy
        that has been configured with the required subrack behaviours.
    :param daq_id: the ID number of the DAQ receiver.

    :yields: into a context in which Tango is running, with a mock
        subrack device.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(subrack_id, mock_subrack_device_proxy)
    harness.add_mock_tile_device(tile_id, mock_tile_device_proxy)
    harness.set_daq_instance()
    harness.set_daq_device(daq_id=daq_id, address=None)
    with harness:
        yield


def test_passing_test(station_self_check_manager: SpsStationSelfCheckManager) -> None:
    """
    Test a passing test.

    The test should result in a PASSED TestResult, and this should be reported in the
    test report.

    :param station_self_check_manager: SpsStationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("PassTest", 1) == [TestResult.PASSED]
    assert "Tests PASSED : 1" in station_self_check_manager._test_report


def test_failing_test(station_self_check_manager: SpsStationSelfCheckManager) -> None:
    """
    Test a failing test.

    The test should result in a FAILED TestResult, and this should be reported in the
    test report, and the test logs should include 'AssertionError'.

    :param station_self_check_manager: SpsStationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("FailTest", 1) == [TestResult.FAILED]
    assert "AssertionError" in station_self_check_manager._test_logs
    assert "Tests FAILED : 1" in station_self_check_manager._test_report


def test_erroring_test(station_self_check_manager: SpsStationSelfCheckManager) -> None:
    """
    Test an erroring test.

    The test should result in a ERRORED TestResult, and this should be reported in the
    test report, and the test logs should include 'KeyError'.

    :param station_self_check_manager: SpsStationSelfCheckManagerr under test.
    """
    assert station_self_check_manager.run_test("ErrorTest", 1) == [TestResult.ERROR]
    assert "KeyError" in station_self_check_manager._test_logs
    assert "Tests ERRORED : 1" in station_self_check_manager._test_report


def test_bad_requirements_test(
    station_self_check_manager: SpsStationSelfCheckManager,
) -> None:
    """
    Test a test which we don't meet the requirements of.

    The test should result in a NOT_RUN TestResult, and this should be reported in the
    test report, and the test logs should be empty.

    :param station_self_check_manager: SpsStationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("BadRequirementsTest", 1) == [
        TestResult.NOT_RUN
    ]
    assert "Tests NOT_RUN : 1" in station_self_check_manager._test_report
    assert (
        "Not running test BadRequirementsTest" in station_self_check_manager._test_logs
    )


def test_test_set(station_self_check_manager: SpsStationSelfCheckManager) -> None:
    """
    Test running the whole test set.

    The test should result in a list containing each TestResult,
    and this should be reported in the test report,
    and the test logs should include 'AssertionError' and 'KeyError'.

    :param station_self_check_manager: SpsStationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_tests() == [
        TestResult.PASSED,
        TestResult.FAILED,
        TestResult.ERROR,
        TestResult.NOT_RUN,
    ]
    assert "Tests PASSED : 1" in station_self_check_manager._test_report
    assert "Tests FAILED : 1" in station_self_check_manager._test_report
    assert "Tests ERRORED : 1" in station_self_check_manager._test_report
    assert "Tests NOT_RUN : 1" in station_self_check_manager._test_report
    assert "KeyError" in station_self_check_manager._test_logs
    assert "AssertionError" in station_self_check_manager._test_logs
