"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs lightweight integration tests
"""

import pytest
import socket
import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process

    param item: the collected test for which this hook is called
    type item: a collected test
    """
    if "device_context" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture(scope="module")
def devices_info(request):
    """
    Pytest fixture that retrieves the `devices_info` (note plural
    "devices") attribute from the module under test. The `devices_info`
    attribute contains information about the multiple devices, necessary
    to stand up those devices in a tango.MultiDeviceTestContext for
    integration testing.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: _pytest.fixtures.SubRequest
    """
    yield getattr(request.module, "devices_info")


@pytest.fixture(scope="function")
def device_context(mocker, devices_info):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: pytest wrapper
    :param devices_info: Information about the devices under test that
        are needed to stand the device up in a DeviceTestContext, such
        as the device classes and properties
    :type devices_info: dict
    """

    def _get_open_port():
        """
        Helper function that returns an available port on the local machine
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    HOST = get_host_ip()
    PORT = _get_open_port()

    _DeviceProxy = tango.DeviceProxy
    mocker.patch(
        "tango.DeviceProxy",
        wraps=lambda fqdn, *args, **kwargs: _DeviceProxy(
            "tango://{0}:{1}/{2}#dbase=no".format(HOST, PORT, fqdn), *args, **kwargs
        ),
    )

    with MultiDeviceTestContext(
        devices_info, process=True, host=HOST, port=PORT
    ) as context:
        yield context
