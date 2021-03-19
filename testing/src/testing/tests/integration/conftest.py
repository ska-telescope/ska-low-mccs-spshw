"""
This module contains pytest fixtures and other test setups for the
ska_low_mccs lightweight integration tests.
"""
import pytest
import socket
import tango
from tango.test_context import get_host_ip

from ska_low_mccs import MccsDeviceProxy


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: :py:class:`pytest.Item`
    """
    if "device_context" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture()
def patch_device_proxy():
    """
    Fixture that provides a patcher that set up
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` to use a connection factory
    that wraps :py:class:`tango.DeviceProxy` with a workaround for a bug
    in :py:class:`tango.test_context.MultiDeviceTestContext`, then returns the host
    and port used by the patch.

    This is a factory; the patch won't be applied unless you actually
    call the fixture.

    :return: the callable patcher
    :rtype: callable
    """

    def patcher():
        """
        Callable returned by this parent fixture, which performs
        patching when called.

        :return: the host and port used by the patch
        :rtype: tuple
        """

        def _get_open_port():
            """
            Helper function that returns an available port on the local
            machine.

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

        host = get_host_ip()
        port = _get_open_port()

        MccsDeviceProxy.set_default_connection_factory(
            lambda fqdn, *args, **kwargs: tango.DeviceProxy(
                f"tango://{host}:{port}/{fqdn}#dbase=no", *args, **kwargs
            ),
        )
        return (host, port)

    return patcher


@pytest.fixture()
def tango_config(patch_device_proxy):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation ensures that
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` uses a connection factory
    that wraps :py:class:`tango.DeviceProxy` with a workaround for a bug
    in :py:class:`tango.test_context.MultiDeviceTestContext`.

    :param patch_device_proxy: the host and port used by the wrapped
        :py:class:`tango.DeviceProxy`
    :type patch_device_proxy: tuple

    :returns: tango configuration information: a dictionary with keys
        "process", "host" and "port".
    :rtype: dict
    """
    (host, port) = patch_device_proxy()
    return {"process": True, "host": host, "port": port}
