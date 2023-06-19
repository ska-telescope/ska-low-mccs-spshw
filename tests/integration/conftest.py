# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW integration tests."""
from __future__ import annotations

import functools
from typing import Any, Callable, Generator

import pytest

from ska_low_mccs_spshw.subrack import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
    SubrackServerContextManager,
)


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `tango_harness` fixture, causing them to be sandboxed
    in their own process.

    :param item: the collected test for which this hook is called
    """
    if "tango_harness" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(name="subrack_simulator_factory", scope="session")
def subrack_simulator_factory_fixture(
    subrack_simulator_config: dict[str, Any],
) -> Callable[[], SubrackSimulator]:
    """
    Return a subrack simulator factory.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a subrack simulator factory.
    """
    return functools.partial(SubrackSimulator, **subrack_simulator_config)


@pytest.fixture(name="subrack_simulator")
def subrack_simulator_fixture(
    subrack_simulator_factory: Callable[[], SubrackSimulator],
) -> SubrackSimulator:
    """
    Return a subrack simulator.

    :param subrack_simulator_factory: a factory that returns a backend
        simulator to which the server will provide an interface.

    :return: a subrack simulator.
    """
    return subrack_simulator_factory()


@pytest.fixture(name="subrack_address")
def subrack_address_fixture(
    subrack_simulator: SubrackSimulator,
) -> Generator[tuple[str, int], None, None]:
    """
    Yield the host and port of a running subrack server.

    :param subrack_simulator: the actual backend simulator to which this
        server provides an interface.

    :yields: the host and port of a running subrack server.
    """
    with SubrackServerContextManager(subrack_simulator) as (host, port):
        yield host, port
