# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW functional tests."""
from __future__ import annotations

import json
import os
from time import sleep
from typing import Iterator

import _pytest
import pytest
import tango
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext


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


@pytest.fixture(name="subrack_address", scope="module")
def subrack_address_fixture() -> tuple[str, int] | None:
    """
    Return the address of a subrack.

    If a real hardware subrack is present, or there is a pre-existing
    simulator, then this fixture returns the subrack address as a
    (hostname, port) tuple. If there is no pre-existing subrack server,
    then this fixture returns None, indicating that the test harness
    should stand up a subrack simulator server itself.

    :return: the address of a subrack, or None if a subrack server is
        not yet running.
    """
    address_var = "SUBRACK_ADDRESS"
    if address_var in os.environ:
        [host, port_str] = os.environ[address_var].split(":")
        return host, int(port_str)
    return None


@pytest.fixture(name="functional_test_context", scope="module")
def functional_test_context_fixture(
    true_context: bool,
    subrack_id: int,
    subrack_address: tuple[str, int] | None,
    daq_id: int,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Yield a Tango context containing the device/s under test.

    :param true_context: whether to test against an existing Tango
        deployment
    :param subrack_id: ID of the subrack Tango device.
    :param subrack_address: the address of a subrack server if one is
        already running; otherwise None.
    :param daq_id: the ID of the daq receiver

    :yields: a Tango context containing the devices under test
    """
    harness = SpsTangoTestHarness()

    if not true_context:
        if subrack_address is None:
            harness.add_subrack_simulator(subrack_id)
        harness.add_subrack_device(subrack_id, subrack_address)
        harness.set_daq_instance()
        harness.set_daq_device(
            daq_id,
            address=None,  # dynamically get address of DAQ instance
        )

    with harness as context:
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
        "daq_state",
        "calibration_store_state",
        "field_station_state",
        "station_calibrator_state",
        timeout=30.0,
    )


@pytest.fixture(name="acquisition_duration", scope="session")
def acquisition_duration_fixture() -> int:
    """
    Return the duration of data capture in seconds.

    :return: Duration of data capture.
    """
    return 2


# pylint: disable=inconsistent-return-statements
def poll_until_consumer_running(
    daq: tango.DeviceProxy, wanted_consumer: str, no_of_iters: int = 5
) -> None:
    """
    Poll until device is in wanted state.

    This function recursively calls itself up to `no_of_iters` times.

    :param daq: the DAQ receiver Tango device
    :param wanted_consumer: the consumer we're waiting for
    :param no_of_iters: number of times to iterate
    """
    status = json.loads(daq.DaqStatus())
    for consumer in status["Running Consumers"]:
        if wanted_consumer in consumer:
            return

    if no_of_iters == 1:
        pytest.fail(f"Wanted consumer: {wanted_consumer} not started.")

    sleep(1)
    return poll_until_consumer_running(daq, wanted_consumer, no_of_iters - 1)


# pylint: disable=inconsistent-return-statements
def poll_until_consumers_stopped(daq: tango.DeviceProxy, no_of_iters: int = 5) -> None:
    """
    Poll until device is in wanted state.

    This function recursively calls itself up to `no_of_iters` times.

    :param daq: the DAQ receiver Tango device
    :param no_of_iters: number of times to iterate
    """
    status = json.loads(daq.DaqStatus())
    if status["Running Consumers"] == []:
        return

    if no_of_iters == 1:
        pytest.fail("Consumers not stopped.")

    sleep(1)
    return poll_until_consumers_stopped(daq, no_of_iters - 1)


# pylint: disable=inconsistent-return-statements
def poll_until_state_change(
    daq: tango.DeviceProxy, wanted_state: tango.DevState, no_of_iters: int = 5
) -> None:
    """
    Poll until device is in wanted state.

    This function recursively calls itself up to `no_of_iters` times.

    :param daq: the DAQ receiver Tango device
    :param wanted_state: the state we're waiting for
    :param no_of_iters: number of times to iterate
    """
    if daq.state() == wanted_state:
        return

    if no_of_iters == 1:
        pytest.fail(
            f"device not in desired state, \
        wanted: {wanted_state}, actual: {daq.state()}"
        )

    sleep(1)
    return poll_until_state_change(daq, wanted_state, no_of_iters - 1)
