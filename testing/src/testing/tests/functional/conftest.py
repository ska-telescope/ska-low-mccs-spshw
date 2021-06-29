# type: ignore
"""This module contains pytest-specific test harness for MCCS functional (BDD) tests."""
from __future__ import annotations

import pytest
from typing import Callable

from testing.harness.mock.mock_device import MockDeviceBuilder
from testing.harness.tango_harness import TangoHarness


def pytest_configure(config):
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    :type config: :py:class:`pytest.config.Config`
    """
    config.addinivalue_line("markers", "XTP-1170: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1257: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1260: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1261: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1473: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1762: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1763: XRay BDD test marker")


@pytest.fixture(scope="module")
def initial_mocks():
    """
    Fixture that registers device proxy mocks prior to patching. By default no initial
    mocks are registered, but this fixture can be overridden by test modules/classes
    that need to register initial mocks.

    (Overruled here with the same implementation, just to give the
    fixture module scope)

    :return: an empty dictionary
    :rtype: dict
    """
    return {}


@pytest.fixture(scope="module")
def mock_factory():
    """
    Fixture that provides a mock factory for device proxy mocks. This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    (Overruled here with the same implementation, just to give the
    fixture module scope)

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
    """
    return MockDeviceBuilder()


@pytest.fixture(scope="module")
def tango_config():
    """
    Fixture that returns basic configuration information for a Tango test harness, such
    as whether or not to run in a separate process.

    :return: a dictionary of configuration key-value pairs
    """
    return {"process": True}


@pytest.fixture(scope="module")
def tango_harness(
    tango_harness_factory: Callable[[], TangoHarness],
    tango_config: dict[str, str],
    devices_to_load,
    mock_factory,
    initial_mocks,
):
    """
    Creates a test harness for testing Tango devices.

    (This overwrites the `tango_harness` fixture, in order to change the
    fixture scope.)

    :param tango_harness_factory: a factory that provides a test harness
        for testing tango devices
    :param tango_config: basic configuration information for a tango
        test harness
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dict
    :param mock_factory: the factory to be used to build mocks
    :type mock_factory: object
    :param initial_mocks: a pre-build dictionary of mocks to be used
        for particular
    :type initial_mocks: dict<str, :py:class:`pytest_mock.mocker.Mock`>

    :yields: the test harness
    """
    with tango_harness_factory(
        tango_config, devices_to_load, mock_factory, initial_mocks
    ) as harness:
        yield harness


@pytest.fixture(scope="module")
def cached_obsstate():
    """
    Use a pytest message box to retain obsstate between test stages.

    :return: cached_obsstate: pytest message box for the cached obsstate
    :rtype: cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    return {}
