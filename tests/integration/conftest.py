# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW integration tests."""
from __future__ import annotations

from typing import Generator

import pytest
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy


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


@pytest.fixture(name="tile_name")
def tile_name_fixture() -> str:
    """
    Return the name of the subrack Tango device.

    :return: the name of the subrack Tango device.
    """
    return "low-mccs/tile/0001"


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    subrack_name: str,
    subrack_address: tuple[str, int],
    tile_name: str,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param subrack_name: the name of the subrack Tango device
    :param subrack_address: the host and port of the subrack
    :param tile_name: the name of the tile Tango device

    :yields: a tango context.
    """
    subrack_ip, subrack_port = subrack_address

    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        subrack_name,
        "ska_low_mccs_spshw.MccsSubrack",
        SubrackIp=subrack_ip,
        SubrackPort=subrack_port,
        UpdateRate=1.0,
        LoggingLevelDefault=5,
    )
    context_manager.add_device(
        tile_name,
        "ska_low_mccs_spshw.MccsTile",
        TileId=1,
        SubrackFQDN=subrack_name,
        SubrackBay=1,
        AntennasPerTile=2,
        SimulationConfig=1,
        TestConfig=1,
        TpmIp="10.0.10.201",
        TpmCpldPort=10000,
        TpmVersion="tpm_v1_6",
        LoggingLevelDefault=5,
    )
    with context_manager as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> DeviceProxy:
    """
    Return the subrack Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    tango_harness: TangoContextProtocol,
    tile_name: str,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param tile_name: name of the tile Tango device.

    :return: the tile Tango device under test.
    """
    return tango_harness.get_device(tile_name)


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "subrack_state",
        "subrack_result",
        "subrack_tpm_power_state",
        "tile_state",
        timeout=2.0,
    )
