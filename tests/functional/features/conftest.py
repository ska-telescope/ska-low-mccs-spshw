"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs functional (BDD) tests
"""
from collections import defaultdict
from contextlib import contextmanager
import json
import socket

import backoff
import pytest
import tango
from tango import DevState
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
            :rtype: :py:class:`tango.DeviceProxy`
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
    :rtype: :py:class:`tango.MultiDeviceTestContext`
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


def _load_data_from_json(path):
    """
    Loads a dataset from a named json file.

    :param path: path to the JSON file from which the dataset is to be
        loaded.
    :type path: string

    :return: data loaded and deserialised from a JSON data file
    :rtype: anything JSON-serialisable
    """
    with open(path, "r") as json_file:
        return json.load(json_file)


def _load_devices(path, device_names):
    """
    Loads device configuration data for specified devices from a
    specified JSON configuration file.

    :param path: path to the JSON configuration file
    :type path: string
    :param device_names: names of the devices for which configuration
        data should be loaded
    :type device_names: list of string

    :return: a devices_info spec in a format suitable for use by as
        input to a :py:class:`tango.test_context.MultiDeviceTestContext`
    :rtype: dict
    """
    configuration = _load_data_from_json(path)
    devices_by_class = {}

    servers = configuration["servers"]
    for server in servers:
        for device_name in servers[server]:
            if device_name in device_names:
                for class_name, device_info in servers[server][device_name].items():
                    if class_name not in devices_by_class:
                        devices_by_class[class_name] = []
                    for fqdn, device_specs in device_info.items():
                        devices_by_class[class_name].append(
                            {"name": fqdn, **device_specs}
                        )

    devices_info = []
    for device_class in devices_by_class:
        device_info = []
        for device in devices_by_class[device_class]:
            device_info.append(device)

        devices_info.append({"class": device_class, "devices": device_info})

    return devices_info


@pytest.fixture(scope="module")
def devices_info(devices_to_load):
    """
    Constructs a devices_info dictionary in the form required by
    tango.test_context.MultiDeviceTestContext, with devices as specified
    by the devices_to_load fixture

    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary

    :return: a specification of devices
    :rtype: dict
    """
    devices = _load_devices(
        path=devices_to_load["path"], device_names=devices_to_load["devices"]
    )

    patches = devices_to_load["patch"] if "patch" in devices_to_load else {}

    devices_to_patch = defaultdict(list)
    devices_to_import = defaultdict(list)

    for group in devices:
        for device in group["devices"]:
            if device["name"] in patches:
                patch = patches[device["name"]]
                devices_to_patch[patch].append(device)
            else:
                devices_to_import[group["class"]].append(device)

    patched_devices = [
        {"class": cls, "devices": devices_to_patch[cls]} for cls in devices_to_patch
    ]

    package = __import__(devices_to_load["package"], fromlist=devices_to_import.keys())
    imported_devices = [
        {"class": getattr(package, cls), "devices": devices_to_import[cls]}
        for cls in devices_to_import
    ]

    return imported_devices + patched_devices


@pytest.fixture(scope="module")
def tango_context(request, devices_info, module_mocker):
    """
    Returns a Tango context. The Tango context returned depends upon
    whether or not pytest was invoked with the `--true-context` option.

    If no, then this returns a tango.test_context.MultiDeviceTestContext
    set up with the devices specified in the module's devices_info.

    If yes, then this returns a context with an interface like that of
    tango.test_context.MultiDeviceTestContext, but actually providing
    access to a true Tango context.

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`_pytest.fixtures.SubRequest`
    :param devices_info: Information about the devices under test that
        are needed to stand the device up in a DeviceTestContext, such
        as the device classes and properties
    :type devices_info: dict
    :param module_mocker: a module-scope thin wrapper for the
        :py:mod:`unittest.mock` package
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


@backoff.on_predicate(backoff.expo, factor=0.1, max_time=3)
def confirm_initialised(devices):
    """
    Helper function that tries to confirm that a device has completed
    its initialisation and transitioned out of INIT state, using an
    exponential backoff-retry scheme in case of failure

    :param devices: the devices that we are waiting to initialise
    :type devices: :py:class:`tango.DeviceProxy`

    :returns: whether the devices are all initialised or not
    :rtype: bool
    """
    return all(
        device.state() not in [DevState.UNKNOWN, DevState.INIT] for device in devices
    )
