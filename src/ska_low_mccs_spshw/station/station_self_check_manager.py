#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of self check procedures for a station."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from .tests.base_tpm_test import TestResult, TpmSelfCheckTest
from .tests.test_station_initialise import InitialiseStation
from .tests.test_tango import BasicTangoTest

__all__ = ["SpsStationSelfCheckManager"]

if TYPE_CHECKING:
    from .station_component_manager import SpsStationComponentManager


# pylint: disable=too-many-instance-attributes, too-many-arguments
class SpsStationSelfCheckManager:
    """A class for initiating station self-check procedures."""

    def __init__(
        self: SpsStationSelfCheckManager,
        logger: logging.Logger,
        tile_trls: list[str],
        subrack_trls: list[str],
        daq_trl: str,
        component_manager: SpsStationComponentManager,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use.
        :param tile_trls: trls of tiles the station has.
        :param subrack_trls: trls of subracks the station has.
        :param daq_trl: trl of the daq the station has.
        :param component_manager: SpsStation component manager under test.
        """
        self.logger = logger
        self._test_logs = ""
        self._test_report = ""

        self._tile_trls = tile_trls
        self._subrack_trls = subrack_trls
        self._daq_trl = daq_trl
        self._component_manager = component_manager

        tpm_tests = [
            tpm_test(
                component_manager=self._component_manager,
                logger=self.logger,
                tile_trls=list(self._tile_trls),
                subrack_trls=list(self._subrack_trls),
                daq_trl=self._daq_trl,
            )
            for tpm_test in [BasicTangoTest, InitialiseStation]
        ]
        self._tpm_test_names = [tpm_test.__class__.__name__ for tpm_test in tpm_tests]
        self._tpm_tests: dict[str, TpmSelfCheckTest] = {
            tpm_test.__class__.__name__: tpm_test for tpm_test in tpm_tests
        }

    def _clear_logs_and_report(self: SpsStationSelfCheckManager) -> None:
        self._test_report = "Test report:\n\n"
        self._test_logs = ""

    def run_tests(self: SpsStationSelfCheckManager) -> list[TestResult]:
        """
        Run all self check tests.

        :returns: results of the test set.
        """
        self._clear_logs_and_report()
        test_results = [TestResult.NOT_RUN for _ in range(len(self._tpm_tests))]
        start_time = time.time()
        for test_no, tpm_test in enumerate(self._tpm_tests.values()):
            test_results[test_no], test_log = tpm_test.run_test()
            self._test_logs += f"\n{'#'*5} {tpm_test.__class__.__name__} {'#'*5}\n"
            self._test_logs += test_log
            self._update_report(
                test_result=test_results[test_no],
                test_name=tpm_test.__class__.__name__,
            )
        duration = time.time() - start_time
        self._generate_report(test_results=test_results, duration=duration)
        return test_results

    def run_test(
        self: SpsStationSelfCheckManager, test_name: str, count: int
    ) -> list[TestResult]:
        """
        Run a specific test, with an optional count parameter to run multiple times.

        :param test_name: name of the test to run.
        :param count: number of times to run test.

        :returns: results of the tests.
        """
        self._clear_logs_and_report()
        test_results = [TestResult.NOT_RUN for _ in range(count)]
        start_time = time.time()
        tpm_test = self._tpm_tests[test_name]
        for test_run in range(count):
            test_results[test_run], test_log = tpm_test.run_test()
            self._test_logs += f"\n{'#'*5} {test_name} {'#'*5}\n"
            self._test_logs += test_log
            self._update_report(
                test_result=test_results[test_run],
                test_name=test_name,
            )
        duration = time.time() - start_time
        self._generate_report(test_results=test_results, duration=duration)
        return test_results

    def _generate_report(
        self: SpsStationSelfCheckManager,
        test_results: list[TestResult],
        duration: Optional[float] = None,
    ) -> None:
        """
        Generate test report.

        :param test_results: results of the tests.
        :param duration: how long the test set took to run.
        """
        passed_count = [
            test_result
            for test_result in test_results
            if test_result == TestResult.PASSED
        ]
        failed_count = [
            test_result
            for test_result in test_results
            if test_result == TestResult.FAILED
        ]
        error_count = [
            test_result
            for test_result in test_results
            if test_result == TestResult.ERROR
        ]
        not_run_count = [
            test_result
            for test_result in test_results
            if test_result == TestResult.NOT_RUN
        ]
        self._test_report += f"\nTests PASSED : {len(passed_count)}, "
        self._test_report += f"Tests FAILED : {len(failed_count)}, "
        self._test_report += f"Tests ERRORED : {len(error_count)}, "
        self._test_report += f"Tests NOT_RUN : {len(not_run_count)}\n"
        self._test_report += f"Tests completed in {duration:.2f} seconds"

    def _update_report(
        self: SpsStationSelfCheckManager, test_result: TestResult, test_name: str
    ) -> None:
        self._test_report += f"Test: {test_name}," f" Result: {test_result.name}\n"
