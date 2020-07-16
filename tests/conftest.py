"""
A module defining pytest fixtures for testing ska.low.mccs.
"""
from collections import defaultdict
import pytest
import socket
import tango
from tango.test_context import DeviceTestContext, MultiDeviceTestContext, get_host_ip


def pytest_configure(config):
    """
    pytest hook, used here to register custom marks to get rid of spurious
    warnings
    """
    config.addinivalue_line(
        "markers", "mock_device_proxy: the test requires tango.DeviceProxy to be mocked"
    )


@pytest.fixture(scope="module")
def device_info(request):
    """
    Pytest fixture that retrieves the `device_info` (note singular
    "device") attribute from the module under test. The `device_info`
    attribute contains information about the device under test, such as
    property values, necessary to stand up that device in a
    tango.DeviceTestContext for unit testing.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: _pytest.fixtures.SubRequest
    """
    yield getattr(request.module, "device_info")


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

    with MultiDeviceTestContext(devices_info, host=HOST, port=PORT) as context:
        yield context
