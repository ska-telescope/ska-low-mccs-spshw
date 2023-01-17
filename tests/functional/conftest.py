# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for MCCS functional (BDD) tests."""
from __future__ import annotations

import unittest
from typing import Any, Callable, Generator

import _pytest
import pytest
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup


def pytest_configure(
    config: _pytest.config.Config,
) -> None:
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    """
    config.addinivalue_line("markers", "XTP-1170: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1257: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1260: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1261: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1473: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1762: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1763: XRay BDD test marker")


@pytest.fixture(scope="module", name="initial_mocks")
def initial_mocks_fixture() -> dict[str, unittest.mock.Mock]:
    """
    Fixture that registers device proxy mocks prior to patching.

    By default no initial mocks are registered, but this fixture can be
    overridden by test modules/classes that need to register initial
    mocks.

    (Overruled here with the same implementation, just to give the
    fixture module scope)

    :return: an empty dictionary
    """
    return {}


@pytest.fixture(scope="module", name="mock_factory")
def mock_factory_fixture() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a mock factory for device proxy mocks.

    This default factory provides vanilla mocks,
    but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    (Overruled here with the same implementation, just to give the
    fixture module scope)

    :return: a factory for device proxy mocks
    """
    return MockDeviceBuilder()


@pytest.fixture(scope="module", name="tango_config")
def tango_config_fixture() -> dict[str, Any]:
    """
    Fixture that returns basic configuration information for a Tango test harness.

    e.g. such as whether or not to run in a separate process.

    :return: a dictionary of configuration key-value pairs
    """
    return {"process": False}


@pytest.fixture(scope="module", name="tango_harness")
def tango_harness_fixture(
    tango_harness_factory: Callable[
        [
            dict[str, Any],
            DevicesToLoadType,
            Callable[[], unittest.mock.Mock],
            dict[str, unittest.mock.Mock],
        ],
        TangoHarness,
    ],
    tango_config: dict[str, str],
    devices_to_load: DevicesToLoadType,
    mock_factory: Callable[[], unittest.mock.Mock],
    initial_mocks: dict[str, unittest.mock.Mock],
) -> Generator[TangoHarness, None, None]:
    """
    Create a test harness for testing Tango devices.

    (This overwrites the `tango_harness` fixture, in order to change the
    fixture scope.)

    :param tango_harness_factory: a factory that provides a test harness
        for testing tango devices
    :param tango_config: basic configuration information for a tango
        test harness
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :param mock_factory: the factory to be used to build mocks
    :param initial_mocks: a pre-build dictionary of mocks to be used
        for particular

    :yields: the test harness
    """
    with tango_harness_factory(
        tango_config, devices_to_load, mock_factory, initial_mocks
    ) as harness:
        yield harness


@pytest.fixture()
def change_event_callbacks() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of change event callbacks with asynchrony support.

    :returns: a callback group.
    """
    return MockTangoEventCallbackGroup(
        "controller_health",
        "controller_state",
        timeout=30.0,
    )


@pytest.fixture(scope="module", name="devices_to_load")
def devices_to_load_fixture() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "tests/data/deployment_configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_03", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_04", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "beam_01", "proxy": MccsDeviceProxy},
            {"name": "beam_02", "proxy": MccsDeviceProxy},
            {"name": "beam_03", "proxy": MccsDeviceProxy},
            {"name": "beam_04", "proxy": MccsDeviceProxy},
            {"name": "apiu_001", "proxy": MccsDeviceProxy},
            {"name": "apiu_002", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
            {"name": "antenna_000001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000002", "proxy": MccsDeviceProxy},
            {"name": "antenna_000003", "proxy": MccsDeviceProxy},
            {"name": "antenna_000004", "proxy": MccsDeviceProxy},
            {"name": "antenna_000005", "proxy": MccsDeviceProxy},
            {"name": "antenna_000006", "proxy": MccsDeviceProxy},
            {"name": "antenna_000007", "proxy": MccsDeviceProxy},
            {"name": "antenna_000008", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture(name="controller")
def controller_fixture(
    tango_harness: TangoHarness,
) -> MccsDeviceProxy:
    """
    Return the controller device.

    :param tango_harness: a test harness for tango devices

    :return: the controller device
    """
    return tango_harness.get_device("low-mccs/control/control")


@pytest.fixture(name="subrack")
def subrack_fixture(
    tango_harness: TangoHarness,
) -> MccsDeviceProxy:
    """
    Return the subrack device.

    :param tango_harness: a test harness for tango devices

    :return: the subrack device
    """
    return tango_harness.get_device("low-mccs/subrack/01")


@pytest.fixture()
def daq(
    tango_harness: TangoHarness,
) -> MccsDeviceProxy:
    """
    Return the daq device.

    :param tango_harness: a test harness for tango devices

    :return: the daq device
    """
    return tango_harness.get_device("low-mccs/daq/01")


@pytest.fixture()
def subarrays(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of subarrays keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: subarrays by number
    """
    return {
        1: tango_harness.get_device("low-mccs/subarray/01"),
        2: tango_harness.get_device("low-mccs/subarray/02"),
    }


@pytest.fixture(name="stations")
def stations_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of stations keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: stations by number
    """
    return {
        1: tango_harness.get_device("low-mccs/station/001"),
        2: tango_harness.get_device("low-mccs/station/002"),
    }


@pytest.fixture(name="apius")
def apius_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of APIUs keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: APIUs by number
    """
    return {
        1: tango_harness.get_device("low-mccs/apiu/001"),
        2: tango_harness.get_device("low-mccs/apiu/002"),
    }


@pytest.fixture(name="subarray_beams")
def subarray_beams_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of subarray beams keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: subarray beams by number
    """
    return {
        1: tango_harness.get_device("low-mccs/subarraybeam/01"),
        2: tango_harness.get_device("low-mccs/subarraybeam/02"),
        3: tango_harness.get_device("low-mccs/subarraybeam/03"),
        4: tango_harness.get_device("low-mccs/subarraybeam/04"),
    }


@pytest.fixture(name="station_beams")
def station_beams_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of station beams keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: station beams by number
    """
    return {
        1: tango_harness.get_device("low-mccs/beam/01"),
        2: tango_harness.get_device("low-mccs/beam/02"),
        3: tango_harness.get_device("low-mccs/beam/03"),
        4: tango_harness.get_device("low-mccs/beam/04"),
    }


@pytest.fixture(name="tiles")
def tiles_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of tiles keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: tiles by number
    """
    return {
        1: tango_harness.get_device("low-mccs/tile/0001"),
        2: tango_harness.get_device("low-mccs/tile/0002"),
        3: tango_harness.get_device("low-mccs/tile/0003"),
        4: tango_harness.get_device("low-mccs/tile/0004"),
    }


@pytest.fixture(name="antennas")
def antennas_fixture(tango_harness: TangoHarness) -> dict[int, MccsDeviceProxy]:
    """
    Return a dictionary of antennas keyed by their number.

    :param tango_harness: a test harness for tango devices

    :return: antennas by number
    """
    return {
        1: tango_harness.get_device("low-mccs/antenna/000001"),
        2: tango_harness.get_device("low-mccs/antenna/000002"),
        3: tango_harness.get_device("low-mccs/antenna/000003"),
        4: tango_harness.get_device("low-mccs/antenna/000004"),
        5: tango_harness.get_device("low-mccs/antenna/000005"),
        6: tango_harness.get_device("low-mccs/antenna/000006"),
        7: tango_harness.get_device("low-mccs/antenna/000007"),
        8: tango_harness.get_device("low-mccs/antenna/000008"),
    }
