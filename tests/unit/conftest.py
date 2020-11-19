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
    behaviours

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: wrapper for :py:mod:`unittest.mock`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`Mock` (the class itself, not an instance)
    """
    return mocker.Mock


@pytest.fixture()
def mock_device_proxies(mocker, mock_factory, initial_mocks):
    """
    Fixture that patches :py:class:`tango.DeviceProxy` to always return
    the same mock for each fqdn

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


@backoff.on_predicate(backoff.expo, factor=0.1, max_time=3)
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
