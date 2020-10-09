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


def pytest_configure(config):
    """
    pytest hook, used here to register custom marks to get rid of spurious
    warnings
    """
    config.addinivalue_line(
        "markers", "mock_device_proxy: the test requires tango.DeviceProxy to be mocked"
    )


@pytest.fixture(scope="function")
def device_under_test(request, device_info, mocker):
    """
    Creates and returns a DeviceProxy under a DeviceTestContext.

    For tests that are marked with the custom "mock_device_proxy" marker
    (i.e. `@pytest.mark.mock_device_proxy`), `tango.DeviceProxy` will be
    mocked prior to initialisation of the device under test.

    :param device_info: Information about the device under test that is
        needed to stand the device up in a DeviceTestContext, such as
        the device class and properties
    :type device_info: dict
    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: pytest wrapper

    :yields: a DeviceProxy under a DeviceTestContext
    """
    mock_device_proxy = request.node.get_closest_marker("mock_device_proxy") is not None
    if mock_device_proxy:
        mock_device_proxies = defaultdict(mocker.Mock)
        mocker.patch(
            "tango.DeviceProxy", side_effect=lambda fqdn: mock_device_proxies[fqdn]
        )

    with DeviceTestContext(
        device_info["class"], properties=device_info["properties"]
    ) as device_under_test:
        yield device_under_test
