# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for PaSD functional tests."""
import os
from typing import Any, Callable, ContextManager, Generator, TypedDict, Union, cast

import _pytest
import pytest
from ska_control_model import LoggingLevel
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
    TrueTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.subrack import SubrackSimulator

SubrackInfoType = TypedDict("SubrackInfoType", {"host": str, "port": int})


# TODO: https://github.com/pytest-dev/pytest-forked/issues/67
# We're stuck on pytest 6.2 until this gets fixed, and this version of
# pytest is not fully typehinted
def pytest_addoption(
    parser: _pytest.config.argparsing.Parser,  # type: ignore[name-defined]
) -> None:
    """
    Add a command line option to pytest.

    This is a pytest hook, here implemented to add the `--true-context`
    option, used to indicate that a true Tango subsystem is available,
    so there is no need for the test harness to spin up a Tango test
    context.

    :param parser: the command line options parser
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        default=False,
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )


@pytest.fixture(name="true_context", scope="session")
def true_context_fixture(request: pytest.FixtureRequest) -> bool:
    """
    Return whether to test against an existing Tango deployment.

    If True, then Tango is already deployed, and the tests will be run
    against that deployment.

    If False, then Tango is not deployed, so the test harness will stand
    up a test context and run the tests against that.

    :param request: A pytest object giving access to the requesting test
        context.

    :return: whether to test against an existing Tango deployment
    """
    if request.config.getoption("--true-context"):
        return True
    if os.getenv("TRUE_TANGO_CONTEXT", None):
        return True
    return False


@pytest.fixture(name="subrack_info", scope="module")
def subrack_info_fixture(
    subrack_simulator_factory: Callable[[], SubrackSimulator],
    subrack_server_launcher: Callable[
        [SubrackSimulator], ContextManager[tuple[str, int]]
    ],
) -> Generator[dict[str, Any], None, None]:
    """
    Return information about the subrack.

    The information consists of the host and port, and whether it is a
    simulator.

    :param subrack_simulator_factory: a factory that returns a backend
        simulator to which the server will provide an interface.
    :param subrack_server_launcher: a callable that, when called,
        returns a context manager that spins up a subrack server, yields
        it for use in testing, and then shuts its down afterwards.

    :yields: the protocol, host and port of the subrack management
        board.
    """
    address_var = "SUBRACK_ADDRESS"
    if address_var in os.environ:
        [host, port_str] = os.environ[address_var].split(":")

        yield {
            "host": host,
            "port": int(port_str),
        }
    else:
        simulator = subrack_simulator_factory()
        with subrack_server_launcher(simulator) as (host, port):
            yield {
                "host": host,
                "port": port,
            }


@pytest.fixture(name="tango_harness", scope="module")
def tango_harness_fixture(
    subrack_name: str,
    subrack_info: SubrackInfoType,
    true_context: bool,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Yield a Tango context containing the device/s under test.

    :param subrack_name: name of the subrack Tango device.
    :param subrack_info: information about the subrack, such as the host
        and port, and whether it is a simulator.
    :param true_context: whether to test against an existing Tango
        deployment

    :yields: a Tango context containing the devices under test
    """
    context_manager: Union[
        TrueTangoContextManager, ThreadedTestTangoContextManager
    ]  # for the type checker
    if true_context:
        context_manager = TrueTangoContextManager()
    else:
        context_manager = ThreadedTestTangoContextManager()
        cast(ThreadedTestTangoContextManager, context_manager).add_device(
            subrack_name,
            "ska_low_mccs_spshw.MccsSubrack",
            SubrackIp=subrack_info["host"],
            SubrackPort=subrack_info["port"],
            UpdateRate=1.0,
            LoggingLevelDefault=int(LoggingLevel.DEBUG),
        )
    with context_manager as context:
        yield context


@pytest.fixture(name="change_event_callbacks", scope="module")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "subrack_state",
        "subrack_fan_modes",
        "subrack_fan_speeds",
        "subrack_fan_speeds_percent",
        "subrack_tpm_power_state",
        timeout=2.0,
    )


@pytest.fixture()
def tpm_number() -> int:
    """
    Return the number of the TPM under test in the subrack under test.

    :returns: the number of the TPM
    """
    return 2
