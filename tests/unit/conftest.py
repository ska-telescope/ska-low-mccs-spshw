"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs unit tests
"""
import backoff
from collections import defaultdict
import pytest

# import tango
from tango import DevSource, DevState
from tango.test_context import DeviceTestContext

from ska.base.control_model import AdminMode, HealthState


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process

    :param item: the collected test for which this hook is called
    :type item: a collected test
    """
    if "device_under_test" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture()
def mock_device_proxies(mocker):
    """
    Fixture that patches :py:class:`tango.DeviceProxy` to always return
    the same mock for each fqdn

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: wrapper for :py:mod:`unittest.mock`
    :return: a dictionary (but don't access it directly, access it
        through :py:class:`tango.DeviceProxy` calls)
    :rtype: dict
    """

    class MockDeviceProxy(mocker.Mock):
        """
        A mock class for DeviceProxy with some DeviceProxy-specific
        behaviours:
        * read_attribute returns mock events, with specific attribute
          values for healthState and adminMode
        """

        class MockDeviceAttribute:
            """
            A class for mock device attributes, such as is returned by
            an attribute read or an attribute change event.
            """

            _VALUES = {
                "healthState": HealthState.UNKNOWN,
                "adminMode": AdminMode.ONLINE,
            }

            def __init__(self, name):
                """
                Create a new instance

                :param name: the name of the device attribute
                :type name: string
                """
                self.name = name
                self.value = self._VALUES[name] if name in self._VALUES else "MockValue"
                self.quality = "MockQuality"

        def read_attribute(self, name, *args, **kwargs):
            """
            Pretent to read an attribute

            :param name: the name of the attribute to be read
            :type name: str
            :param args: position args to read_attribute
            :type args: list
            :param kwargs: named args to read_attribute
            :type kwargs: dict

            :return: a mock device attribute for the named attribute
            :rtype: :py:class:`MockDeviceAttribute`
            """
            return self.MockDeviceAttribute(name)

    device_proxy_mocks = defaultdict(MockDeviceProxy)
    mocker.patch("tango.DeviceProxy", side_effect=lambda fqdn: device_proxy_mocks[fqdn])
    return device_proxy_mocks


@backoff.on_predicate(backoff.expo, factor=0.1, max_tries=5)
def _confirm_initialised(device):
    """
    Helper function that tries to confirm that a group of devices have
    all completed initialisation and transitioned out of INIT state,
    using an exponential backoff-retry scheme in case of failure.

    :param device: the device that we are waiting to initialise
    :type device: :py:class:`tango.DeviceProxy`

    :returns: whether the device is initialised or not
    :rtype: bool
    """
    return device.state() != DevState.INIT


@pytest.fixture()
def device_under_test(request, device_info, mock_device_proxies):
    """
    Creates and returns a proxy to the device under test, in a
    DeviceTestContext. In addition, tango.DeviceProxy is mocked out,
    since these are unit tests and there is neither any reason nor any
    ability for device to be talking to each other.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`_pytest.fixtures.SubRequest`
    :param device_info: Information about the device under test that is
        needed to stand the device up in a DeviceTestContext, such as
        the device class and properties
    :type device_info: dict
    :param mock_device_proxies: fixture that mocks out tango.DeviceProxy.
        Since these are unit tests, we will always want to mock this out.
    :type mock_device_proxies: a dictionary (but don't access it
        directly, access it through :py:class:`tango.DeviceProxy` calls)

    :raises TimeoutError: if the device does not complete initialisation
        within a reasonable time.
    :yields: a DeviceProxy under a DeviceTestContext
    """
    try:
        with DeviceTestContext(
            device_info["class"], properties=device_info["properties"]
        ) as device_under_test:
            device_under_test.set_source(DevSource.DEV)
            if not _confirm_initialised(device_under_test):
                raise TimeoutError("Device has not completed initialisation")
            yield device_under_test
    except Exception as e:
        print(e)
