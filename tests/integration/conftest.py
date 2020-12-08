"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs lightweight integration tests.
"""

import backoff
from collections import defaultdict
import json
import pytest
import socket

import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


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


class MCCSDeviceInfo:
    """
    Data structure class that loads and holds information about devices,
    and can provide that information in the format required by
    :py:class:`tango.test_context.MultiDeviceTestContext`.
    """

    def __init__(self, source_path, package):
        """
        Create a new instance.

        :param source_path: the path to the configuration file that
            contains information about all available devices.
        :type source_path: str
        :param package: name of the package from which to draw classes
        :type package: str
        """
        with open(source_path, "r") as json_file:
            self._source_data = json.load(json_file)
        self._package = package
        self._devices = {}

    def include_device(self, device_name, patch=None):
        """
        Include a device in this specification.

        :param device_name: the name of the device to be included. The
            source data must contain configuration informatino for a
            device listed under this name
        :type device_name: str
        :param patch: a class with which to patch the named device
        :type patch: obj

        :raises ValueError: if the named device does not exist in the
            source configuration data
        """
        for server in self._source_data["servers"]:
            if device_name in self._source_data["servers"][server]:
                device_spec = self._source_data["servers"][server][device_name]
                class_name = next(iter(device_spec))
                fqdn = next(iter(device_spec[class_name]))
                properties = device_spec[class_name][fqdn]["properties"]

                if patch is None:
                    # klass = importlib.import_module(f".{class_name}", self._package)
                    package = __import__(self._package, fromlist=[class_name])
                    klass = getattr(package, class_name)
                else:
                    klass = patch

                self._devices[device_name] = {
                    "server": server,
                    "class": klass,
                    "fqdn": fqdn,
                    "properties": properties,
                }
                break
        else:
            raise ValueError(f"Device {device_name} not found in source data.")

    @property
    def fqdn_map(self):
        """
        A dictionary that maps device names onto FQDNs.

        :return: a mapping from device names to FQDNs
        :rtype: dict
        """
        return {name: self._devices[name]["fqdn"] for name in self._devices}

    def as_mdtc_device_info(self):
        """
        Return this device info in a format required by
        :py:class:`tango.test_context.MultiDeviceTestContext`.

        :return: device info in a format required by
            :py:class:`tango.test_context.MultiDeviceTestContext`.
        :rtype: dict
        """
        devices_by_class = defaultdict(list)
        for device in self._devices.values():
            devices_by_class[device["class"]].append(
                {"name": device["fqdn"], "properties": device["properties"]}
            )
        mdtc_device_info = [
            {"class": klass, "devices": devices}
            for klass, devices in devices_by_class.items()
        ]
        return mdtc_device_info


class MCCSDeviceTestContext:
    """
    MCCS wrapper for a tango.test_context.MultiDeviceTestContext.

    It allows for devices to be accessed by MCCS device names, rather
    than the device FQDNs.
    """

    def _load_devices(self, devices_to_load):
        """
        Loads device configuration data for specified devices from a
        specified JSON configuration file.

        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :type devices_to_load: dictionary

        :return: a devices_info spec in a format suitable for use by as
            input to a :py:class:`tango.test_context.MultiDeviceTestContext`
        :rtype: dict
        """
        device_info = MCCSDeviceInfo(
            devices_to_load["path"], devices_to_load["package"]
        )
        patches = devices_to_load["patch"] if "patch" in devices_to_load else {}

        for device_name in devices_to_load["devices"]:
            patch = patches[device_name] if device_name in patches else None
            device_info.include_device(device_name, patch=patch)

        return device_info

    def __init__(self, devices_to_load, host=None, port=None):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :type devices_to_load: dictionary
        :param host: hostname of the machine hosting the devices
        :type host: str
        :param port: port for the tango subsystem
        :type port: int
        """
        self._devices_info = self._load_devices(devices_to_load)
        mdtc_devices_info = self._devices_info.as_mdtc_device_info()
        self._multi_device_test_context = MultiDeviceTestContext(
            mdtc_devices_info, process=True, host=host, port=port
        )

    def __enter__(self):
        """
        Entry method for "with" context.

        :return: the context object
        :rtype: `MCCSDeviceTestContext`
        """
        self._multi_device_test_context.__enter__()
        return self

    def __exit__(self, exc_type, exception, trace):
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :type: obj
        :param exception: the exception thrown in the with block
        :type exception: obj
        :param trace: a traceback
        :type trace: obj
        """
        self._multi_device_test_context.__exit__(exc_type, exception, trace)

    def get_device(self, name):
        """
        Returns a :py:class:`tango.DeviceProxy` to a device as specified
        by the device name provided in the configuration file.

        This method also patches a bug in :py:class:`tango.DeviceProxy`,
        namely that it's :py:meth:`~tango.DeviceProxy.get_fqdn` method
        returns " " when run under a
        :py:class:`tango.test_context.MultiDeviceTestContext`.

        :param name: the name of the device for which a
            :py:class:`tango.DeviceProxy` is sought.
        :type name: str

        :return: a :py:class:`tango.DeviceProxy` to the named device
        :rtype: :py:class:`tango.DeviceProxy`
        """
        fqdn = self._devices_info.fqdn_map[name]
        device = self._multi_device_test_context.get_device(fqdn)
        device.get_fqdn = lambda: fqdn
        return device


@pytest.fixture()
def device_context(mocker, devices_to_load):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: wrapper for :py:mod:`unittest.mock`
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary
    :yield: a tango testing context
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

    with MCCSDeviceTestContext(devices_to_load, host=host, port=port) as context:
        yield context


@backoff.on_predicate(backoff.expo, factor=0.1, max_time=3)
def confirm_initialised(devices):
    """
    Helper function that tries to confirm that a group of devices have
    all completed initialisation and transitioned out of INIT state,
    using an exponential backoff-retry scheme in case of failure.

    :param devices: the devices that we are waiting to initialise
    :type devices: :py:class:`tango.DeviceProxy`

    :returns: whether the devices are all initialised or not
    :rtype: bool
    """
    return all(device.state() != tango.DevState.INIT for device in devices)
