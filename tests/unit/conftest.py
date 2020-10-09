"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs unit tests
"""
from collections import defaultdict
import pytest

# import tango
from tango.test_context import DeviceTestContext


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process

    param item: the collected test for which this hook is called
    type item: a collected test
    """
    if "device_under_test" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture
def mock_device_proxies(mocker):
    """
    Fixture that patches :py:class:`tango.DeviceProxy` to always return
    the same mock for each fqdn

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: unittest.Mock wrapper
    :yield: a dictionary (but don't access it directly, access it
        through :py:class:`tango.DeviceProxy` calls)
    """
    device_proxy_mocks = defaultdict(mocker.Mock)
    mocker.patch("tango.DeviceProxy", side_effect=lambda fqdn: device_proxy_mocks[fqdn])
    yield device_proxy_mocks


@pytest.fixture(scope="function")
def device_under_test(request, device_info, mock_device_proxies):
    """
    Creates and returns a proxy to the device under test, in a
    DeviceTestContext. In addition, tango.DeviceProxy is mocked out,
    since these are unit tests and there is neither any reason nor any
    ability for device to be talking to each other.

    :param device_info: Information about the device under test that is
        needed to stand the device up in a DeviceTestContext, such as
        the device class and properties
    :type device_info: dict
    :param mock_device_proxies: fixture that mocks out tango.DeviceProxy.
        Since these are unit tests, we will always want to mock this out.
    :type mock_device_proxies: a dictionary (but don't access it
        directly, access it through :py:class:`tango.DeviceProxy` calls)

    :yields: a DeviceProxy under a DeviceTestContext
    """
    try:
        with DeviceTestContext(
            device_info["class"], properties=device_info["properties"]
        ) as device_under_test:
            yield device_under_test
    except Exception as e:
        print(e)
