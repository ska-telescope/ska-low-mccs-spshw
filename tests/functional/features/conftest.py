from contextlib import contextmanager
import pytest
import socket
import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


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


@contextmanager
def _tango_true_context():
    """
    Returns a context manager that provides access to a true TANGO
    environment through an interface like that of
    tango.MultiDeviceTestContext.
    """

    class _TangoTrueContext:
        """
        Implements a context that provides access to a true TANGO
        environment through an interface like that of
        tango.MultiDeviceTestContext."""

        def get_device(self, fqdn):
            """
            Returns a device proxy to the specified device

            :param fqdn: the fully qualified domain name of the server
            :type fqdn: string
            """
            return tango.DeviceProxy(fqdn)

    yield _TangoTrueContext()


def _tango_test_context(_devices_info, _module_mocker):
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
        Finds and returns an open port on localhost
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
    _module_mocker.patch(
        "tango.DeviceProxy",
        wraps=lambda fqdn, *args, **kwargs: _DeviceProxy(
            "tango://{0}:{1}/{2}#dbase=no".format(HOST, PORT, fqdn), *args, **kwargs
        ),
    )

    return MultiDeviceTestContext(_devices_info, host=HOST, port=PORT)


@pytest.fixture(scope="module")
def tango_context(request, devices_info, module_mocker):
    """
    Returns a Tango context. The Tango context returned depends upon
    whether or not pytest was invoked with the `--truecontext` option.

    If no, then this returns a tango.test_context.MultiDeviceTestContext
    set up with the devices specified in the module's devices_info.

    If yes, then this returns a context with an interface like that of
    tango.test_context.MultiDeviceTestContext, but actually providing
    access to a true Tango context.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: _pytest.fixtures.SubRequest
    :param devices_info: Information about the devices under test that
        are needed to stand the device up in a DeviceTestContext, such
        as the device classes and properties
    :type devices_info: dict
    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: pytest wrapper
    """
    try:
        true_context = request.config.getoption("--true-context")
    except ValueError:
        true_context = False

    if true_context:
        with _tango_true_context() as context:
            yield context
    else:
        with _tango_test_context(devices_info, module_mocker) as context:
            yield context
