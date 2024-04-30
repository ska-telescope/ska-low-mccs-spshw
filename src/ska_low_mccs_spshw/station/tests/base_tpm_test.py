#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of self check procedures for a station."""
from __future__ import annotations

import abc
import enum
import logging
import traceback
from io import StringIO

from ska_control_model import LoggingLevel
from ska_ser_logging.configuration import _FORMAT_STR_NO_TAGS  # type: ignore

__all__ = ["TestResult", "TpmSelfCheckTest"]


class TestResult(enum.IntEnum):
    """Enumerate for test results."""

    PASSED = 0

    FAILED = 1

    ERROR = 2

    NOT_RUN = 3


class TpmSelfCheckTest(abc.ABC):
    """Base class for Tpm self check tests."""

    def __init__(
        self: TpmSelfCheckTest,
        logger: logging.Logger,
        tile_trls: list[str],
        subrack_trls: list[str],
        daq_trl: str,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this model to use.
        :param tile_trls: trls of tiles the station has.
        :param subrack_trls: trls of subracks the station has.
        :param daq_trl: trl of the daq the station has.
        """
        self.logger = logger
        self.tile_trls = tile_trls
        self.subrack_trls = subrack_trls
        self.daq_trl = daq_trl
        self._configure_test_logger()

    def _configure_test_logger(self: TpmSelfCheckTest) -> None:
        """Configure logger used for tests so we get split off test logs."""
        self.test_logger = logging.getLogger(self.__class__.__name__)
        self.stringio_buffer = StringIO()
        self.stringio_handler = logging.StreamHandler(self.stringio_buffer)
        self.stringio_handler.setFormatter(logging.Formatter(_FORMAT_STR_NO_TAGS))
        self.test_logger.addHandler(self.stringio_handler)
        self.test_logger.setLevel(LoggingLevel.DEBUG)

    def _clear_test_logs(self: TpmSelfCheckTest) -> None:
        """Before each test run, we want to clear the test logs."""
        self.stringio_buffer.truncate(0)
        self.stringio_buffer.seek(0)

    @abc.abstractmethod
    def test(self: TpmSelfCheckTest) -> None:
        """
        This should be written by sub-classes.

        :raises NotImplementedError: this is abstract.
        """
        raise NotImplementedError

    def check_requirements(self: TpmSelfCheckTest) -> tuple[bool, str]:
        """
        Check requirements for the test before running.

        :return: true as no requirements have been set.
        """
        return (True, "No requirements set for test")

    def run_test(self: TpmSelfCheckTest) -> tuple[TestResult, str]:
        """
        Run the self-check test, collect results.

        :returns: test result.
        """
        self._clear_test_logs()

        try:
            self.test()
            result = TestResult.PASSED
        except AssertionError as e:
            error_traceback = traceback.format_exc()
            self.test_logger.error(f"{repr(e)} : {error_traceback}")
            result = TestResult.FAILED
        except Exception as e:  # pylint: disable=broad-except
            error_traceback = traceback.format_exc()
            self.test_logger.error(f"{repr(e)} : {error_traceback}")
            result = TestResult.ERROR
        return result, self.stringio_handler.stream.getvalue()
