# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW integration tests."""
from __future__ import annotations

from typing import Any, Iterator

import pytest
from tango import DeviceProxy

from ska_low_mccs_spshw.subrack import SubrackSimulator
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `integration_test_context` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    """
    if "integration_test_context" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(name="subrack_simulator")
def subrack_simulator_fixture(
    subrack_simulator_config: dict[str, Any],
) -> SubrackSimulator:
    """
    Return a subrack simulator.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a subrack simulator.
    """
    return SubrackSimulator(**subrack_simulator_config)


@pytest.fixture(name="integration_test_context")
def integration_test_context_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
    tile_id: int,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which both subrack simulator and Tango device are running.

    :param subrack_id: the ID of the subrack under test
    :param subrack_simulator: the backend simulator that the Tango
        device will monitor and control
    :param tile_id: the ID of the tile under test

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    harness.add_subrack_device(subrack_id)
    harness.add_tile_device(tile_id, subrack_id, subrack_bay=1)
    harness.set_sps_station_device(subrack_ids=[subrack_id], tile_ids=[tile_id])

    with harness as context:
        yield context


@pytest.fixture(name="sps_station_device")
def sps_station_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
) -> DeviceProxy:
    """
    Return the SPS station Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.

    :return: the SPS station Tango device under test.
    """
    return integration_test_context.get_sps_station_device()


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
    subrack_id: int,
) -> DeviceProxy:
    """
    Return the subrack Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.
    :param subrack_id: ID of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return integration_test_context.get_subrack_device(subrack_id)


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    integration_test_context: SpsTangoTestHarnessContext,
    tile_id: int,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param integration_test_context: the test context in which
        integration tests will be run.
    :param tile_id: ID of the tile Tango device.

    :return: the tile Tango device under test.
    """
    return integration_test_context.get_tile_device(tile_id)
