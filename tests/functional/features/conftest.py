"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs functional (BDD) tests
"""
from contextlib import contextmanager
import pytest
import socket
import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


@contextmanager
def _tango_true_context():
    """
    Returns a context manager that provides access to a true TANGO
    environment through an interface like that of
    tango.MultiDeviceTestContext.

    :yield: A tango.MultiDeviceTestContext-like interface to a true
        Tango system
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

            :return: a DeviceProxy to the device with the given fqdn
            :rtype: tango.DeviceProxy
            """
            return tango.DeviceProxy(fqdn)

    yield _TangoTrueContext()


def _tango_test_context(_devices_info, _module_mocker):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.

    :param _devices_info: Information about the devices under test that
        are needed to stand the device up in a DeviceTestContext, such
        as the device classes and properties
    :type _devices_info: dict
    :param _module_mocker: module_scoped fixture that provides a thin
        wrapper around the `unittest.mock` package
    :type _module_mocker: pytest wrapper

    :return: a test contest set up as specified by the _devices_info
        argument
    :rtype: tango.MultiDeviceTestContext
    """

    def _get_open_port():
        """
        Helper function that returns an available port on the local machine

        Note the possibility of a race condition here. By the time the
        calling method tries to make use of this port, it might already
        have been taken by another process.

        :return: An open port
        :rtype: int
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
            f"tango://{HOST}:{PORT}/{fqdn}#dbase=no", *args, **kwargs
        ),
    )

    return MultiDeviceTestContext(_devices_info, process=True, host=HOST, port=PORT)


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
    :param module_mocker: a module-scope thin wrapper for the
        `unittest.mock` package
    :type module_mocker: wrapper
    :yield: a tango context
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
