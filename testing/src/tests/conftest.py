"""
This module contains pytest fixtures and other test setups common to all ska_low_mccs
tests: unit, integration and functional (BDD).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Generator, Set, cast
import pytest
import tango
import unittest
import yaml

from ska_low_mccs.testing.mock import MockChangeEventCallback, MockDeviceBuilder
from ska_low_mccs.testing.tango_harness import (
    ClientProxyTangoHarness,
    DevicesToLoadType,
    MccsDeviceInfo,
    MockingTangoHarness,
    StartingStateTangoHarness,
    TangoHarness,
    TestContextTangoHarness,
)


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Pytest hook; prints info about tango version.

    :param session: a pytest Session object
    """
    print(tango.utils.info())


with open("testing/testbeds.yaml", "r") as stream:
    _testbeds: dict[str, set[str]] = yaml.safe_load(stream)


def pytest_configure(config: pytest.config.Config) -> None:
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    """
    all_tags: Set[str] = cast(Set[str], set()).union(*_testbeds.values())
    for tag in all_tags:
        config.addinivalue_line("markers", f"needs_{tag}")


def pytest_addoption(parser: pytest.config.ArgumentParser) -> None:
    """
    Pytest hook; implemented to add the `--testbed` option, used to specify the context
    in which the test is running. This could be used, for example, to skip tests that
    have requirements not met by the context.

    :param parser: the command line options parser
    """
    parser.addoption(
        "--testbed",
        choices=_testbeds.keys(),
        default="test",
        help="Specify the testbed on which the tests are running.",
    )


def pytest_collection_modifyitems(
    config: pytest.config.Config, items: list[pytest.Item]
) -> None:
    """
    Modify the list of tests to be run, after pytest has collected them.

    This hook implementation skips tests that are marked as needing some
    tag that is not provided by the current test context, as specified
    by the "--testbed" option.

    For example, if we have a hardware test that requires the presence
    of a real TPM, we can tag it with "@needs_tpm". When we run in a
    "test" context (that is, with "--testbed test" option), the test
    will be skipped because the "test" context does not provide a TPM.
    But when we run in "pss" context, the test will be run because the
    "pss" context provides a TPM.

    :param config: the pytest config object
    :param items: list of tests collected by pytest
    """
    testbed = config.getoption("--testbed")
    available_tags = _testbeds.get(testbed, set())

    prefix = "needs_"
    for item in items:
        needs_tags = set(
            tag[len(prefix) :] for tag in item.keywords if tag.startswith(prefix)
        )
        unmet_tags = list(needs_tags - available_tags)
        if unmet_tags:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"Testbed '{testbed}' does not meet test needs: "
                        f"{unmet_tags}."
                    )
                )
            )


@pytest.fixture()
def initial_mocks() -> dict[str, unittest.mock.Mock]:
    """
    Fixture that registers device proxy mocks prior to patching.

    By default no initial mocks are registered, but this fixture can be
    overridden by test modules/classes that need to register initial
    mocks.

    :return: an empty dictionary
    """
    return {}


@pytest.fixture()
def mock_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Fixture that provides a mock factory for device proxy mocks. This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :return: a factory for device proxy mocks
    """
    print(f"RCL: mdb = MockDeviceBuilder()...")
    mdb = MockDeviceBuilder()
    print(f"RCL: mdb = MockDeviceBuilder() Done")
    return mdb


@pytest.fixture(scope="session")
def tango_harness_factory(
    request, logger
):
    """
    Returns a factory for creating a test harness for testing Tango devices. The Tango
    context used depends upon the context in which the tests are being run, as specified
    by the `--testbed` option.

    If the context is "test", then this harness deploys the specified
    devices into a
    :py:class:`tango.test_context.MultiDeviceTestContext`.

    Otherwise, this harness assumes that devices are already running;
    that is, we are testing a deployed system.

    This fixture is implemented as a factory so that the actual
    `tango_harness` fixture can vary in scope: unit tests require test
    isolation, so will want to build a new harness every time. But
    functional tests assume a single harness that maintains state
    across multiple tests, so they will want to instantiate the harness
    once and then use it for multiple tests.

    :param request: A pytest object giving access to the requesting test
        context.
    :param logger: the logger to be used by this object.

    :return: a tango harness factory
    """

    class _CPTCTangoHarness(ClientProxyTangoHarness, TestContextTangoHarness):
        """
        A Tango test harness with the client proxy functionality of
        :py:class:`~ska_low_mccs.testing.tango_harness.ClientProxyTangoHarness`
        within the lightweight test context provided by
        :py:class:`~ska_low_mccs.testing.tango_harness.TestContextTangoHarness`.
        """

        pass

    testbed = request.config.getoption("--testbed")

    def build_harness(
        tango_config: dict[str, Any],
        devices_to_load: DevicesToLoadType,
        mock_factory: Callable[[], unittest.mock.Mock],
        initial_mocks: dict[str, unittest.mock.Mock],
    ) -> TangoHarness:
        """
        Builds the Tango test harness.

        :param tango_config: basic configuration information for a tango
            test harness
        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :param mock_factory: the factory to be used to build mocks
        :param initial_mocks: a pre-build dictionary of mocks to be used
            for particular

        :return: a tango test harness
        """
        print(f"RCL: build_harness...")
        if devices_to_load is None:
            print(f"RCL: device_info = None...")
            device_info = None
        else:
            print(f"RCL: device_info = MccsDeviceInfo(**devices_to_load)...")
            device_info = MccsDeviceInfo(**devices_to_load)

        print(f"RCL: 1111")

        tango_harness: TangoHarness  # type hint only
        if testbed == "test":
            tango_harness = _CPTCTangoHarness(device_info, logger, **tango_config)
        else:
            tango_harness = ClientProxyTangoHarness(device_info, logger)
        print(f"RCL: 2222")

        starting_state_harness = StartingStateTangoHarness(tango_harness)

        print(f"RCL: 3333")
        mocking_harness = MockingTangoHarness(
            starting_state_harness, mock_factory, initial_mocks
        )
        print(f"RCL: 4444")

        return mocking_harness

    return build_harness


@pytest.fixture()
def tango_config() -> dict[str, Any]:
    """
    Fixture that returns basic configuration information for a Tango test harness, such
    as whether or not to run in a separate process.

    :return: a dictionary of configuration key-value pairs
    """
    return {"process": False}


@pytest.fixture()
def tango_harness(
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
    Creates a test harness for testing Tango devices.

    :param tango_harness_factory: a factory that provides a test harness
        for testing tango devices
    :param tango_config: basic configuration information for a tango
        test harness
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :param mock_factory: the factory to be used to build mocks
    :param initial_mocks: a pre-build dictionary of mocks to be used
        for particular

    :yields: a tango test harness
    """
    print(f"RCL: with tango_harness_factory...2222")
    with tango_harness_factory(
        tango_config, devices_to_load, mock_factory, initial_mocks
    ) as harness:
        print(f"RCL: about to yield the harness...2222")
        yield harness


@pytest.fixture(scope="session")
def logger() -> logging.Logger:
    """
    Fixture that returns a default logger.

    :return: a logger
    """
    return logging.getLogger()


@pytest.fixture()
def mock_change_event_callback_factory() -> Callable[[str], MockChangeEventCallback]:
    """
    Return a factory that returns a new mock change event callback each call.

    :return: a factory that returns a new mock change event callback
        each time it is called with the name of a device attribute.
    """
    return MockChangeEventCallback
