# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for MCCS unit tests."""
from typing import ContextManager, Generator

import pytest
from _pytest.fixtures import SubRequest
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
    TrueTangoContextManager,
)


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This pytest hook implementation adds the "forked" custom mark to all
    tests that use the ``tango_harness`` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    """
    if "tango_harness" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(scope="session", name="testbed")
def testbed_fixture(request: SubRequest) -> str:
    """
    Return the name of the testbed.

    The testbed is specified by providing the `--testbed` argument to
    pytest. Information about what testbeds are supported and what tests
    can be run in each testbed is provided in `testbeds.yaml`

    :param request: A pytest object giving access to the requesting test
        context.

    :return: the name of the testbed.
    """
    return request.config.getoption("--testbed")


@pytest.fixture(name="tango_harness", scope="session")
def tango_harness_fixture(
    testbed: str,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param testbed: the name of the testbed to which these tests are
        deployed

    :raises ValueError: if the testbed is unknown

    :yields: a tango context.
    """
    context_manager: ContextManager[TangoContextProtocol]
    if testbed == "local":
        context_manager = TrueTangoContextManager()
    elif testbed == "test":
        context_manager = ThreadedTestTangoContextManager()
        context_manager.add_device(
            "low-mccs/subrack/01",
            "ska_low_mccs_spshw.MccsSubrack",
        )
        context_manager.add_device(
            "low-mccs/tile/0001",
            "ska_low_mccs_spshw.MccsTile",
            SubrackFQDN="low-mccs/subrack/01",
            SubrackBay=1,
        )
    else:
        raise ValueError(f"Testbed {testbed} is not supported.")

    with context_manager as context:
        yield context
