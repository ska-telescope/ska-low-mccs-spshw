#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile component manage."""
from __future__ import annotations

from ska_low_mccs_spshw.station import StationSelfCheckManager
from ska_low_mccs_spshw.station.tests import TestResult


def test_passing_test(station_self_check_manager: StationSelfCheckManager) -> None:
    """
    Test a passing test.

    The test should result in a PASSED TestResult, and this should be reported in the
    test report.

    :param station_self_check_manager: StationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("PassTest", 1) == [TestResult.PASSED]
    assert "Tests PASSED : 1" in station_self_check_manager._test_report


def test_failing_test(station_self_check_manager: StationSelfCheckManager) -> None:
    """
    Test a failing test.

    The test should result in a FAILED TestResult, and this should be reported in the
    test report, and the test logs should include 'AssertionError'.

    :param station_self_check_manager: StationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("FailTest", 1) == [TestResult.FAILED]
    assert "AssertionError" in station_self_check_manager._test_logs
    assert "Tests FAILED : 1" in station_self_check_manager._test_report


def test_erroring_test(station_self_check_manager: StationSelfCheckManager) -> None:
    """
    Test an erroring test.

    The test should result in a ERRORED TestResult, and this should be reported in the
    test report, and the test logs should include 'KeyError'.

    :param station_self_check_manager: StationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("ErrorTest", 1) == [TestResult.ERROR]
    assert "KeyError" in station_self_check_manager._test_logs
    assert "Tests ERRORED : 1" in station_self_check_manager._test_report


def test_bad_requirements_test(
    station_self_check_manager: StationSelfCheckManager,
) -> None:
    """
    Test a test which we don't meet the requirements of.

    The test should result in a NOT_RUN TestResult, and this should be reported in the
    test report, and the test logs should be empty.

    :param station_self_check_manager: StationSelfCheckManager under test.
    """
    assert station_self_check_manager.run_test("BadRequirementsTest", 1) == [
        TestResult.NOT_RUN
    ]
    assert "Tests NOT_RUN : 1" in station_self_check_manager._test_report
    assert station_self_check_manager._test_logs == ""


def test_test_set(station_self_check_manager: StationSelfCheckManager) -> None:
    """
    Test running the whole test set.

    The test should result in a list containing each TestResult,
    and this should be reported in the test report,
    and the test logs should include 'AssertionError' and 'KeyError'.

    :param station_self_check_manager: StationSelfCheckManager under test.
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
