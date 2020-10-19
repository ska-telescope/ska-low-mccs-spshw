"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs unit tests
"""
from collections import defaultdict
import pytest
import time

# import tango
from tango import DevSource, DevState
from tango.test_context import DeviceTestContext


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
    device_proxy_mocks = defaultdict(mocker.Mock)
    mocker.patch("tango.DeviceProxy", side_effect=lambda fqdn: device_proxy_mocks[fqdn])
    return device_proxy_mocks


def _wait_for_initialisation(device):
    """
    Helper function that ensures the `device_under_test` fixture does
    not return until the device has moved out of the INIT state.

    :param device: the device that we are waiting to initialise
    :type device: :py:class:`tango.DeviceProxy`

    :raises TimeoutError: if retries have been exhausted and the device
        still has not initialised
    """
    sleeps = [0.1, 0.2, 0.5, 1, 2, 4]
    for sleep in sleeps:
        if device.state() == DevState.INIT:
            time.sleep(sleep)
        else:
            break
    else:
        if device.state() == DevState.INIT:
            raise TimeoutError(
                "Retries exhausted; stuck at asynchronous initialisation?"
            )


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

    :yields: a DeviceProxy under a DeviceTestContext
    """
    try:
        with DeviceTestContext(
            device_info["class"], properties=device_info["properties"]
        ) as device_under_test:
            device_under_test.set_source(DevSource.DEV)
            _wait_for_initialisation(device_under_test)
            yield device_under_test
    except Exception as e:
        print(e)
