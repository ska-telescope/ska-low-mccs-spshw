"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs unit tests.
"""
from collections import defaultdict
import pytest
import time
import tango
from ska.base.commands import ResultCode


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the :py:meth:`device_context` fixture, causing them
    to be sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: a collected test
    """
    if "device_under_test" in item.fixturenames:
        item.add_marker("forked")


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
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: a wrapper around the :py:mod:`unittest.mock` package
    :type mocker: obj

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an instance)
    """
    return mocker.Mock


@pytest.fixture()
def mock_device_proxies(mocker, mock_factory, initial_mocks):
    """
    Fixture that patches :py:class:`tango.DeviceProxy` to always return
    the same mock for each fqdn.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: wrapper for :py:mod:`unittest.mock`
    :param mock_factory: a factory for producing
        :py:class:`tango.DeviceProxy` mocks
    :type mock_factory: object
    :param initial_mocks: :py:class:`tango.DeviceProxy` mocks to be used
        for given FQDNs
    :type initial_mocks: dict

    :return: a dictionary (but don't access it directly, access it
        through :py:class:`tango.DeviceProxy` calls)
    :rtype: dict
    """
    mocks = defaultdict(mock_factory, initial_mocks)
    mocker.patch(
        "tango.DeviceProxy", side_effect=lambda fqdn, *args, **kwargs: mocks[fqdn]
    )
    return mocks


@pytest.fixture()
def tango_config(mock_device_proxies):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation - for unit testing - ensures that mocking of
    device proxies is set up, and that Tango is run in a thread
    (necessary for mocks to work).

    :param mock_device_proxies: fixture that patches
        :py:class:`tango.DeviceProxy` to always return the same mock
        for each fqdn
    :type mock_device_proxies: dict

    :returns: tango configuration information: a dictionary with keys
        "process", "host" and "port".
    :rtype: dict
    """
    return {"process": False, "host": None, "port": 0}


@pytest.fixture()
def devices_to_load(device_to_load):
    """
    Fixture that provides specifications of devices to load.

    In this case, it maps the simpler single-device spec returned by the
    "device_to_load" fixture used in unit testing, onto the more
    general multi-device spec.

    :param device_to_load: fixture that provides a specification of a
        single devic to load; used only in unit testing where tests will
        only ever stand up one device at a time.
    :type device_to_load: dict

    :return: specification of the devices (in this case, just one
        device) to load
    :rtype: dict
    """
    spec = {
        "path": device_to_load["path"],
        "package": device_to_load["package"],
        "devices": [device_to_load["device"]],
    }
    if "patch" in device_to_load:
        spec["patch"] = {device_to_load["device"]: device_to_load["patch"]}
    return spec


@pytest.fixture()
def device_under_test(device_context, device_to_load):
    """
    Creates and returns a proxy to the device under test, in a
    DeviceTestContext.

    In addition, tango.DeviceProxy is mocked out,
    since these are unit tests and there is neither any reason nor any
    ability for device to be talking to each other.

    :param device_context: a test context for a set of tango devices
    :type device_context: :py:class:`tango.MultiDeviceTestContext`
    :param device_to_load: fixture that provides a specification of a
        single device to load; used only in unit testing where tests
        will only ever stand up one device at a time.
    :type device_to_load: dict

    :returns: a :py:class:`tango.DeviceProxy` under a
        :py:class:`tango.test_context.MultiDeviceTestContext`
    :rtype: :py:class:`tango.DeviceProxy`
    """
    device = device_context.get_device(device_to_load["device"])
    return device


@pytest.fixture()
def mock_callback(mocker):
    class MockCallback(mocker.Mock):
        def check_event_data(self, name, result):
            """
            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska.base.commands.ResultCode`
            """
            # push_change_event isn't synchronous, because it has to go
            # through the 0MQ event system. So we have to sleep long enough
            # for the event to arrive
            time.sleep(0.2)

            self.assert_called_once()
            event_data = self.call_args[0][0].attr_value

            assert event_data.name.casefold() == name.casefold()
            if result is not None:
                assert event_data.value == result
                assert event_data.quality == tango.AttrQuality.ATTR_VALID
            self.reset_mock()

        def check_command_result(self, name, result):
            """
            Special callback check routine for commandResult. There should
            always be two entries for commandResult; the first should reset
            commandResult to ResultCode.UNKNOWN, the second should match the
            expected result passed into this routine.

            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska.base.commands.ResultCode`
            """
            # push_change_event isn't synchronous, because it has to go
            # through the 0MQ event system. So we have to sleep long enough
            # for the event to arrive
            time.sleep(0.2)

            self.assert_called()
            assert len(self.mock_calls) == 2  # exactly two calls

            first_event_data = self.mock_calls[0][1][0].attr_value
            second_event_data = self.mock_calls[1][1][0].attr_value
            assert first_event_data.name.casefold() == name.casefold()
            assert second_event_data.name.casefold() == name.casefold()
            assert first_event_data.value == ResultCode.UNKNOWN
            assert first_event_data.quality == tango.AttrQuality.ATTR_VALID
            if result is not None:
                assert second_event_data.value == result
                assert second_event_data.quality == tango.AttrQuality.ATTR_VALID
            self.reset_mock()

    return MockCallback()
