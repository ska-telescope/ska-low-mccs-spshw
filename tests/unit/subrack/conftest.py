# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS subrack module."""
from __future__ import annotations

import logging
from typing import Any, Iterator

import pytest
from ska_control_model import PowerState
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.subrack import (
    SubrackComponentManager,
    SubrackDriver,
    SubrackSimulator,
)
from tests.harness import SpsTangoTestHarness


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


@pytest.fixture(name="subrack_address")
def subrack_address_fixture(
    subrack_id: int,
    subrack_simulator: SubrackSimulator,
) -> Iterator[tuple[str, int]]:
    """
    Yield the host and port of a running subrack server.

    That is, enter a test context with a running subrack simulator server
    but no subrack Tango device. Then yield the address of the server.

    :param subrack_id: the ID of the subrack under test
    :param subrack_simulator: the backend simulator to be served in this
        test context.

    :yields: the host and port of a running subrack server.
    """
    harness = SpsTangoTestHarness()
    harness.add_subrack_simulator(subrack_id, subrack_simulator)
    with harness as context:
        yield context.get_subrack_address(subrack_id)


@pytest.fixture(name="subrack_driver")
def subrack_driver_fixture(
    subrack_address: tuple[str, int],
    logger: logging.Logger,
    callbacks: MockCallableGroup,
) -> SubrackDriver:
    """
    Return a subrack driver, configured to talk to a running subrack server.

    (This is a pytest fixture.)

    :param subrack_address: the host and port of the subrack
    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks

    :return: a subrack driver.
    """
    subrack_ip, subrack_port = subrack_address
    return SubrackDriver(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        update_rate=1.0,
    )


@pytest.fixture(name="subrack_component_manager")
def subrack_component_manager_fixture(
    logger: logging.Logger,
    subrack_address: tuple[str, int],
    subrack_driver: SubrackDriver,
    initial_power_state: PowerState,
    callbacks: MockCallableGroup,
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_address: the host and port of the subrack
    :param subrack_driver: the subrack driver to use. Normally the
        subrack component manager creates its own driver; here we inject
        this driver instead.
    :param initial_power_state: the initial power state of the upstream
        power supply
    :param callbacks: dictionary of driver callbacks

    :return: an subrack component manager in the specified simulation mode.
    """
    subrack_ip, subrack_port = subrack_address
    return SubrackComponentManager(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        _driver=subrack_driver,
        _initial_power_state=initial_power_state,
    )


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> MockCallableGroup:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return MockCallableGroup(
        "communication_status",
        "component_state",
        "task",
        timeout=2.0,
    )
