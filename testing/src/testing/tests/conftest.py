# type: ignore
"""
This module contains pytest fixtures and other test setups common to all ska_low_mccs
tests: unit, integration and functional (BDD).
"""
import logging
import typing
import json
from time import sleep
import pytest
import tango

from ska_tango_base.commands import ResultCode
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


_test_contexts = {
    "test": set(),
    "local": {"tangodb"},
    "stfc": {"tangodb"},
    "psi": {"tangodb", "tpm"},
}


def pytest_configure(config):
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    :type config: :py:class:`pytest.config.Config`
    """
    all_tags = set().union(*_test_contexts.values())
    for tag in all_tags:
        config.addinivalue_line("markers", f"needs_{tag}")


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--context` option, used to
    specify the context in which the test is running. This could be
    used, for example, to skip tests that have requirements not met by
    the context.

    :param parser: the command line options parser
    :type parser: :py:class:`argparse.ArgumentParser`
    """
    parser.addoption(
        "--context",
        choices=_test_contexts.keys(),
        default="test",
        help="Specify the context in which the tests are running.",
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify the list of tests to be run, after pytest has collected them.

    This hook implementation skips tests that are marked as needing some
    tag that is not provided by the current test context, as specified
    by the "--context" option.

    For example, if we have a hardware test that requires the presence
    of a real TPM, we can tag it with "@needs_tpm". When we run in a
    "test" context (that is, with "--context test" option), the test
    will be skipped because the "test" context does not provide a TPM.
    But when we run in "pss" context, the test will be run because the
    "pss" context provides a TPM.

    :param config: the pytest config object
    :type config: :py:class:`pytest.config.Config`
    :param items: list of tests collected by pytest
    :type items: list(:py:class:`pytest.Item`)
    """
    context = config.getoption("--context")
    available_tags = _test_contexts.get(context, set())
    for item in items:
        needs_tags = set(tag[6:] for tag in item.keywords if tag.startswith("needs_"))
        unmet_tags = list(needs_tags - available_tags)
        if unmet_tags:
            item.add_marker(
                pytest.mark.skip(
                    reason=f"Context '{context}' does not meet test needs: {unmet_tags}."
                )
            )


@pytest.fixture()
def initial_mocks():
    """
    Fixture that registers device proxy mocks prior to patching. By default no initial
    mocks are registered, but this fixture can be overridden by test modules/classes
    that need to register initial mocks.

    :return: an empty dictionary
    :rtype: dict
    """
    return {}


@pytest.fixture()
def mock_factory():
    """
    Fixture that provides a mock factory for device proxy mocks. This default factory
    provides vanilla mocks, but this fixture can be overridden by test modules/classes
    to provide mocks with specified behaviours.

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
    """
    return MockDeviceBuilder()


@pytest.fixture(scope="session")
def tango_harness_factory(request, logger):
    """
    Returns a factory for creating a test harness for testing Tango
    devices. The Tango context used depends upon the context in which
    the tests are being run, as specified by the `--context` option.

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

    context = request.config.getoption("--context")

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

        if context == "test":
            tango_harness = _CPTCTangoHarness(device_info, logger, **tango_config)
        else:
            tango_harness = ClientProxyTangoHarness(device_info, logger)

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
    Fixture that returns basic configuration information for a Tango test harness, such
    as whether or not to run in a separate process.

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
def empty_json_dict():
    """
    A fixture to return an empty json dictionary.

    :return: an empty json encoded dictionary
    """
    empty_dict = {"": ""}
    return json.dumps(empty_dict)


@pytest.fixture()
def test_string():
    """
    A simple test string fixture.

    :return: a simple test string
    """
    return "This is a simple text string"


class CommandHelper:
    """Class providing helper methods for testing."""

    @staticmethod
    def device_command(device_under_test, command, mock_message_uid):
        """
        Help method to transition the device under test into the desired state.

        As commands use the message queue, a callback is required to complete
        the commands. This method simply sends the desired command and then
        offers a reply in the form of a callback to the requestor. Only one
        callback is required because the message_uid is mocked to be the same
        value for all of the subservient device requests that are made.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param command: command to send to the DUT
        :type command: str
        :param mock_message_uid: a mock message uid for testing
        :type mock_message_uid: str

        :return: A tuple containing a return code and a string containing the
            message unique ID.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        dispatcher = {
            "On": device_under_test.On,
            "Off": device_under_test.Off,
        }
        [result_code], [_, message_uid] = dispatcher[command]()
        assert result_code == ResultCode.QUEUED
        args = {
            "message_object": {
                "command": command,
                "json_args": "",
                "message_uid": mock_message_uid,
                "notifications": False,
                "respond_to_fqdn": "",
                "callback": "",
            },
            "result_code": 0,
            "status": "",
        }
        json_string = json.dumps(args)
        [rc], _ = device_under_test.Callback(json_string)
        assert rc == ResultCode.QUEUED
        sleep(0.1)  # Required to allow DUT thread to run
        return (result_code, message_uid)

    @staticmethod
    def check_device_state(device, state):
        """
        Helper to check that the device is in the expected state with a timeout.

        :param device: the devices to check
        :type device: dict
        :param state: the state the device is expected to be in
        :type state: list(:py:class:`tango.DevState`)
        """
        count = 0.0
        while device.State() != state and count < 3.0:
            count += 0.1
            sleep(0.1)
        assert device.State() == state


@pytest.fixture()
def command_helper():
    """
    A command helper fixture.

    :return: the command helper class
    """
    return CommandHelper
