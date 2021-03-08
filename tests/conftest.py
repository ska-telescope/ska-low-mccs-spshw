"""
This module contains pytest fixtures and other test setups common to all
ska.low.mccs tests: unit, integration and functional (BDD).
"""
import backoff
from collections import defaultdict
import json
import logging

import pytest
import tango
from tango.test_context import MultiDeviceTestContext
from ska_tango_base.control_model import TestMode


def pytest_sessionstart(session):
    """
    Pytest hook; prints info about tango version.

    :param session: a pytest Session object
    :type session: :py:class:`pytest.Session`
    """
    print(tango.utils.info())


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a :py:class:`tango.MultiDeviceTestContext`.

    :param parser: the command line options parser
    :type parser: :py:class:`argparse.ArgumentParser`
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )


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

                attribute_properties = device_spec[class_name][fqdn].get(
                    "attribute_properties", {}
                )
                memorized = {
                    name: value["__value"]
                    for name, value in attribute_properties.items()
                    if "__value" in value
                }

                if patch is None:
                    package = __import__(self._package, fromlist=[class_name])
                    klass = getattr(package, class_name)
                else:
                    klass = patch

                self._devices[device_name] = {
                    "server": server,
                    "class": klass,
                    "fqdn": fqdn,
                    "properties": properties,
                    "memorized": memorized,
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

    @property
    def device_names(self):
        """
        The names of devices included in this data structure.

        :return: the names of included devices
        :rtype: list
        """
        return self._devices.keys()

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
                {
                    "name": device["fqdn"],
                    "properties": device["properties"],
                    "memorized": device["memorized"],
                }
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

    def __init__(
        self,
        devices_to_load,
        ready_condition=None,
        source=None,
        process=False,
        host=None,
        port=None,
    ):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :type devices_to_load: dictionary
        :param ready_condition: function to run against each device
            after creating the test context. The context will not be
            returned until all functions return True
        :type ready_condition: callable
        :param source: a source value to be set on all devices
        :type source: :py:class:`tango.DevSource`, optional
        :param process: whether to run the test context in its own
            process; if False, it is run on a thread.
        :type: bool
        :param host: hostname of the machine hosting the devices
        :type host: str
        :param port: port for the tango subsystem
        :type port: int
        """
        self._devices_info = self._load_devices(devices_to_load)
        mdtc_devices_info = self._devices_info.as_mdtc_device_info()
        self._multi_device_test_context = MultiDeviceTestContext(
            mdtc_devices_info, process=process, host=host, port=port
        )
        self._ready_condition = ready_condition
        self._source_setting = source

    def _check_ready_condition(self, device):
        """
        Checks whether a device meets the ready condition.

        :param device: the device to be checked
        :type device: :py:class:`tango.DeviceProxy`

        :return: whether ready
        :rtype: bool
        """
        try:
            return self._ready_condition(device)
        except tango.DevFailed as dev_failed:
            print(dev_failed)
            return False

    @backoff.on_predicate(backoff.expo, factor=0.1, max_time=20)
    def _backoff_retry_ready(self, unready_devices):
        """
        Implements exponential backoff-retry loop checking remaining
        unready devices for readiness.

        :param unready_devices: list of unready devices. This has to be a
            mutable container (e.g. don't pass a tuple) because devices
            are removed from it as they become ready
        :type unready_devices: list

        :return: whether all devices are ready
        :rtype: bool
        """
        unready_devices[:] = [
            device
            for device in unready_devices
            if not self._check_ready_condition(device)
        ]
        if unready_devices:
            print(f"The following devices still aren't ready: {unready_devices}.")
        return not unready_devices

    def _check_ready(self):
        """
        Ensure that all included devices are checked against the
        provided ready condition.
        """
        if self._ready_condition is None:
            return

        unready = [
            self.get_device(device_name)
            for device_name in self._devices_info.device_names
        ]
        return self._backoff_retry_ready(unready)

    def _set_source(self):
        """
        Ensure that all included devices have the required source
        setting applied.
        """
        if self._source_setting is None:
            return
        for device_name in self._devices_info.device_names:
            self.get_device(device_name).set_source(self._source_setting)

            # HACK: increasing the timeout until we can make some commands synchronous
            self.get_device(device_name).set_timeout_millis(5000)

    def _set_test_mode(self):
        """
        Ensure that all included devices are set into test mode, since
        we are testing.
        """
        for device_name in self._devices_info.device_names:
            self.get_device(device_name).testMode = TestMode.TEST

    def __enter__(self):
        """
        Entry method for "with" context.

        :return: the context object
        :rtype: `MCCSDeviceTestContext`
        """
        self._multi_device_test_context.__enter__()
        self._set_source()
        assert self._check_ready()
        self._set_test_mode()
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

        :param name: the name of the device for which a
            :py:class:`tango.DeviceProxy` is sought.
        :type name: str

        :return: a :py:class:`tango.DeviceProxy` to the named device
        :rtype: :py:class:`tango.DeviceProxy`
        """
        fqdn = self._devices_info.fqdn_map[name]
        device = self._multi_device_test_context.get_device(fqdn)
        return device


@pytest.fixture()
def tango_config(mock_device_proxies):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation - for unit testing - ensures that mocking of
    device proxies is set up, and that Tango is run in a thread
    (necessary for mocks to work).

    :param mock_device_proxies: fixture that patches
        :py:class:`tango.DeviceProxy` to always return the same mock
        for each fqdn
    :type mock_device_proxies: dict

    :returns: tango configuration information: a dictionary with keys
        "process", "host" and "port".
    :rtype: dict
    """
    return {"process": True, "host": None, "port": 0}


@pytest.fixture()
def device_context(devices_to_load, tango_config):
    """
    Creates and returns a TANGO MultiDeviceTestContext object, with a
    tango.DeviceProxy patched to a work around a name resolving issue.

    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dictionary
    :param tango_config: fixture that returns configuration information
        that specifies how the Tango system should be established and
        run.
    :type tango_config: dict

    :yield: a tango testing context
    """
    with MCCSDeviceTestContext(
        devices_to_load,
        ready_condition=lambda device: device.state()
        not in [tango.DevState.UNKNOWN, tango.DevState.INIT],
        source=tango.DevSource.DEV,
        process=tango_config["process"],
        host=tango_config["host"],
        port=tango_config["port"],
    ) as context:
        yield context


@pytest.fixture()
def logger():
    """
    Fixture that returns a default logger.

    :return: a logger
    :rtype logger: :py:class:`logging.Logger`
    """
    return logging.getLogger()
