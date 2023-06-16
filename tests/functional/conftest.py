# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW functional tests."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Callable, ContextManager, Generator, Union, cast

import _pytest
import pytest
from ska_control_model import LoggingLevel
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
    TrueTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup


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


@pytest.fixture(name="subrack_address_context_manager_factory", scope="module")
def subrack_address_context_manager_factory_fixture(
    subrack_simulator_config: dict[str, Any],
) -> Callable[[], ContextManager[tuple[str, int]]]:
    """
    Return the subrack address context manager factory.

    That is, return a callable that, when called, provides a context
    manager that, when entered, returns a subrack host and port, while
    at the same time ensuring the validity of that host and port.

    This fixture obtains the subrack address in one of two ways:

    Firstly it checks for a `SUBRACK_ADDRESS` environment variable, of
    the form "localhost:8081". If found, it is expected that a subrack
    is already available at this host and port, so there is nothing more
    for this fixture to do. The callable that it returns, will itself
    return an empty context manager that, when entered, simply yields
    the specified host and port.

    Otherwise, the callable that this factory returns will be a context
    manager for a subrack simulator server instance. When entered, that
    context manager will launch the subrack simulator server, and then
    yield the host and port on which it is running.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a callable that returns a context manager that, when
        entered, yields the host and port of a subrack server.
    """
    address_var = "SUBRACK_ADDRESS"
    if address_var in os.environ:
        [host, port_str] = os.environ[address_var].split(":")

        @contextmanager
        def _yield_address() -> Generator[tuple[str, int], None, None]:
            yield host, int(port_str)

        return _yield_address
    else:

        def _subrack_server_context_manager() -> ContextManager[tuple[str, int]]:
            # Imports are deferred until now,
            # so that we do not try to import from ska_low_mccs_spshw
            # until we know that we need to.
            # This allows us to runour functional tests
            # against a real cluster
            # from within a test runner pod
            # that does not have ska_low_mccs_spshw installed.
            try:
                from ska_low_mccs_spshw.subrack import SubrackSimulator
                from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
                    SubrackServerContextManager,
                )
            except ImportError as import_error:
                raise ImportError(
                    """Error: you must do one of the following:
                    * use "--true-context" flag or TRUE_TANGO_CONTEXT environment
                    variable to run these tests against a pre-deployed cluster in
                    which the Tango device under test is already running.
                    * use SUBRACK_ADDRESS environment variable to specify the host
                    and port of a subrack server. The test harness will stand up
                    the Tango device under test to monitor and control the subrack
                    at that server address.
                    * run these tests in an environment in which ska_low_mccs_spshw
                    and its dependencies are installed. The test harness will
                    stand up its own subrack simulator server, and then stand up
                    the Tango device under test to monitor and control that
                    subrack simulator server."""
                ) from import_error

            subrack_simulator = SubrackSimulator(**subrack_simulator_config)
            return SubrackServerContextManager(subrack_simulator)

        return _subrack_server_context_manager


@pytest.fixture(name="tango_harness", scope="module")
def tango_harness_fixture(
    subrack_name: str,
    subrack_address_context_manager_factory: Callable[
        [], ContextManager[tuple[str, int]]
    ],
    true_context: bool,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Yield a Tango context containing the device/s under test.

    :param subrack_name: name of the subrack Tango device.
    :param subrack_address_context_manager_factory: a callable that
         returns a context manager that, when entered, yields the host
         and port of a subrack.
    :param true_context: whether to test against an existing Tango
        deployment

    :yields: a Tango context containing the devices under test
    """
    tango_context_manager: Union[
        TrueTangoContextManager, ThreadedTestTangoContextManager
    ]  # for the type checker
    if true_context:
        tango_context_manager = TrueTangoContextManager()
        with tango_context_manager as context:
            yield context
    else:
        with subrack_address_context_manager_factory() as (host, port):
            tango_context_manager = ThreadedTestTangoContextManager()
            cast(ThreadedTestTangoContextManager, tango_context_manager).add_device(
                subrack_name,
                "ska_low_mccs_spshw.MccsSubrack",
                SubrackIp=host,
                SubrackPort=port,
                UpdateRate=1.0,
                LoggingLevelDefault=int(LoggingLevel.DEBUG),
            )
            with tango_context_manager as context:
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
        "subrack_fan_mode",
        "subrack_fan_speeds",
        "subrack_fan_speeds_percent",
        "subrack_tpm_power_state",
        "subrack_tpm_present",
        timeout=30.0,
    )
