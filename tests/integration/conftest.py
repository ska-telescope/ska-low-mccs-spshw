"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs lightweight integration tests.
"""
import pytest
import socket
import tango
from tango.test_context import get_host_ip


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: a collected test
    """
    if "device_context" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture()
def patch_device_proxy(mocker):
    """
    Fixture that monkeypatches :py:class:`tango.DeviceProxy` as a
    workaround for a bug in
    :py:class:`tango.MultiDeviceTestContext`, then returns the host and
    port used by the patch.

    :param mocker: fixture that wraps :py:mod:`unittest.mock` package
    :type mocker: obj

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

    device_proxy_class = tango.DeviceProxy
    mocker.patch(
        "tango.DeviceProxy",
        wraps=lambda fqdn, *args, **kwargs: device_proxy_class(
            f"tango://{host}:{port}/{fqdn}#dbase=no", *args, **kwargs
        ),
    )
    return (host, port)


@pytest.fixture()
def tango_config(patch_device_proxy):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation entures that :py:class:`tango.DeviceProxy` is
    monkeypatched as a workaround for a bug in
    :py:class:`tango.MultiDeviceTestContext`, then returns the host and
    port used by the patch.

    :param patch_device_proxy: a fixture that handles monkeypatching of
        :py:class:`tango.DeviceProxy` as a workaround for a bug in
        :py:class:`tango.MultiDeviceTestContext`, and returns the host
        and port used in the patch
    :type patch_device_proxy: tuple

    :returns: tango configuration information: a dictionary with keys
        "process", "host" and "port".
    :rtype: dict
    """
    (host, port) = patch_device_proxy
    return {"process": True, "host": host, "port": port}
