"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs lightweight integration tests
"""

import pytest
import socket
import time

import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process

    :param item: the collected test for which this hook is called
    :type item: a collected test
    """
    if "device_context" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture()
def device_context(mocker, devices_info):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
        :type mocker: wrapper for :py:mod:`unittest.mock`
    :param devices_info: Information about the devices under test that
        are needed to stand the device up in a DeviceTestContext, such
        as the device classes and properties
    :type devices_info: dict
    :yield: a tango testing context
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
    mocker.patch(
        "tango.DeviceProxy",
        wraps=lambda fqdn, *args, **kwargs: _DeviceProxy(
            f"tango://{HOST}:{PORT}/{fqdn}#dbase=no", *args, **kwargs
        ),
    )

    with MultiDeviceTestContext(
        devices_info, process=True, host=HOST, port=PORT
    ) as context:
        yield context


def _still_initialising(devices):
    """
    Helper function that culls initialised devices out of a list of
    initialising devices

    :param devices: list of devices that are being monitored for
        completion of initialisations
    :type devices: list of :py:class:`tango.DeviceProxy`

    :return: updated list of devices that are still initialising
    :rtype devices: list of :py:class:`tango.DeviceProxy`
    """
    return [device for device in devices if device.state() == tango.DevState.INIT]


def wait_for_initialisation(devices):
    """
    Helper function that ensures the `device_under_test` fixture does
    not return until the device has moved out of the INIT state.

    :param devices: list of devices that we are waiting to initialise
    :type devices: list of :py:class:`tango.DeviceProxy`

    :raises TimeoutError: if retries have been exhausted and the device
        still has not initialised
    """
    sleeps = [0.1, 0.2, 0.5, 1, 2, 4]
    for sleep in sleeps:
        devices = _still_initialising(devices)
        if devices:
            time.sleep(sleep)
        else:
            break
    else:
        if _still_initialising(devices):
            raise TimeoutError(
                "Retries exhausted; stuck at asynchronous initialisation?"
            )
