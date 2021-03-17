"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs unit tests.
"""
from collections import defaultdict
import pytest
import time
import tango

from ska_tango_base.commands import ResultCode
from ska.low.mccs import MccsDeviceProxy


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the ``device_context`` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: :py:class:`pytest.Item`
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
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
    """
    return mocker.Mock


@pytest.fixture()
def mock_device_proxies(mocker, mock_factory, initial_mocks):
    """
    Fixture that sets ups :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` to
    build itself around a mock factory instead of
    :py:class:`tango.DeviceProxy`.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: :py:class:`pytest_mock.mocker`
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

    MccsDeviceProxy.set_default_connection_factory(
        lambda fqdn, *args, **kwargs: mocks[fqdn]
    )
    return mocks


@pytest.fixture()
def tango_config(mock_device_proxies):
    """
    Fixture that returns configuration information that specifies how
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
        single device to load; used only in unit testing where tests
        will only ever stand up one device at a time.
    :type device_to_load: dict

    :return: specification of the devices (in this case, just one
        device) to load
    :rtype: dict
    """
    device_spec = {
        "path": device_to_load["path"],
        "package": device_to_load["package"],
        "devices": [
            {
                "name": device_to_load["device"],
                "proxy": device_to_load["proxy"],
            }
        ],
    }
    if "patch" in device_to_load:
        device_spec["devices"][0]["patch"] = device_to_load["patch"]

    return device_spec


@pytest.fixture()
def device_under_test(device_context, device_to_load):
    """
    Creates and returns a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` to
    the device under test, in a
    :py:class:`tango.test_context.MultiDeviceTestContext`.

    :param device_context: a test context for a set of tango devices
    :type device_context: :py:class:`tango.test_context.MultiDeviceTestContext`
    :param device_to_load: fixture that provides a specification of a
        single device to load; used only in unit testing where tests
        will only ever stand up one device at a time.
    :type device_to_load: dict

    :returns: a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` under a
        :py:class:`tango.test_context.MultiDeviceTestContext`
    :rtype: :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
    """
    device = device_context.get_device(device_to_load["device"])
    return device


@pytest.fixture()
def mock_callback(mocker):
    """
    Fixture that returns a mock to use as a callback.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a mock to pass as a callback
    :rtype: :py:class:`unittest.mock.Mock`
    """
    return mocker.Mock()


@pytest.fixture()
def mock_event_callback(mocker):
    """
    Fixture that returns a mock for use as an event callback.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a mock to pass as an event callback
    :rtype: :py:class:`unittest.mock.Mock`
    """

    class _MockEventCallback(mocker.Mock):
        """
        Mocker private class.
        """

        def check_event_data(self, name, result):
            """
            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska_tango_base.commands.ResultCode`
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
            Special callback check routine for commandResult. There
            should always be two entries for commandResult; the first
            should reset commandResult to ResultCode.UNKNOWN, the second
            should match the expected result passed into this routine.

            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska_tango_base.commands.ResultCode`
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

    return _MockEventCallback()
