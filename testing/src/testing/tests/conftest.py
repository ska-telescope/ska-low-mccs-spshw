"""
This module contains pytest fixtures and other test setups common to all
ska_low_mccs tests: unit, integration and functional (BDD).
"""
import logging
import typing
import json

import pytest
import tango

from testing.harness.mock import MockDeviceBuilder

from testing.harness.tango_harness import (
    ClientProxyTangoHarness,
    MccsDeviceInfo,
    MockingTangoHarness,
    StartingStateTangoHarness,
    TangoHarness,
    TestContextTangoHarness,
)


def pytest_sessionstart(session):
    """
    Pytest hook; prints info about tango version.

    :param session: a pytest Session object
    :type session: :py:class:`pytest.Session`
    """
    print(tango.utils.info())


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a :py:class:`tango.test_context.MultiDeviceTestContext`.

    :param parser: the command line options parser
    :type parser: :py:class:`argparse.ArgumentParser`
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


@pytest.fixture()
def initial_mocks():
    """
    Fixture that registers device proxy mocks prior to patching. By
    default no initial mocks are registered, but this fixture can be
    overridden by test modules/classes that need to register initial
    mocks.

    :return: an empty dictionary
    :rtype: dict
    """
    return {}


@pytest.fixture()
def mock_factory():
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
    """
    return MockDeviceBuilder()


@pytest.fixture(scope="session")
def tango_harness_factory(request, logger):
    """
    Returns a factory for creating a test harness for testing Tango
    devices. The Tango context used depends upon whether or not pytest
    was invoked with the `--true-context` option.

    If yes, then this harness assumes that devices are already running;
    that is, we are testing a deployed system.

    If no, then this harness deploys the specified devices into a
    :py:class:`tango.test_context.MultiDeviceTestContext`.

    This fixture is implemented as a factory so that the actual
    `tango_harness` fixture can vary in scope: unit tests require test
    isolation, so will want to build a new harness every time. But
    functional tests assume a single harness that maintains state
    across multiple tests, so they will want to instantiate the harness
    once and then use it for multiple tests.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`
    :param logger: the logger to be used by this object.
    :type logger: :py:class:`logging.Logger`

    :return: a tango harness factory
    """

    class _CPTCTangoHarness(ClientProxyTangoHarness, TestContextTangoHarness):
        """
        A Tango test harness with the client proxy functionality of
        :py:class:`~testing.harness.tango_harness.ClientProxyTangoHarness`
        within the lightweight test context provided by
        :py:class:`~testing.harness.tango_harness.TestContextTangoHarness`.
        """

        pass

    true_context = request.config.getoption("--true-context")

    def build_harness(
        tango_config: typing.Dict[str, str],
        devices_to_load,
        mock_factory,
        initial_mocks,
    ) -> TangoHarness:
        """
        Builds the Tango test harness.

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

        :return: a tango test harness
        """
        device_info = MccsDeviceInfo(**devices_to_load)

        if true_context:
            tango_harness = ClientProxyTangoHarness(device_info, logger)
        else:
            tango_harness = _CPTCTangoHarness(device_info, logger, **tango_config)

        starting_state_harness = StartingStateTangoHarness(tango_harness)

        mocking_harness = MockingTangoHarness(
            starting_state_harness,
            mock_factory,
            initial_mocks,
        )

        return mocking_harness

    return build_harness


@pytest.fixture()
def tango_config() -> typing.Dict[str, str]:
    """
    Fixture that returns basic configuration information for a Tango
    test harness, such as whether or not to run in a separate process.

    :return: a dictionary of configuration key-value pairs
    """
    return {"process": False}


@pytest.fixture()
def tango_harness(
    tango_harness_factory: typing.Callable[[], TangoHarness],
    tango_config: typing.Dict[str, str],
    devices_to_load,
    mock_factory,
    initial_mocks,
):
    """
    Creates a test harness for testing Tango devices.

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

    :yields: a tango test harness
    """
    with tango_harness_factory(
        tango_config, devices_to_load, mock_factory, initial_mocks
    ) as harness:
        yield harness


@pytest.fixture(scope="session")
def logger():
    """
    Fixture that returns a default logger.

    :return: a logger
    :rtype logger: :py:class:`logging.Logger`
    """
    return logging.getLogger()


@pytest.fixture()
def dummy_json_args():
    """
    A fixture to return dummy json arguments.

    :return: dummy json encoded arguments
    """
    args = {"respond_to_fqdn": "resp", "callback": "call"}
    return json.dumps(args)


@pytest.fixture()
def test_string():
    """
    A simple test string fixture.

    :return: a simple test string
    """
    return "This is a simple text string"