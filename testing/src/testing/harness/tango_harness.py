# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module implements a MCCS test harness for Tango devices.
"""

from __future__ import annotations  # Allow forward refs in type hints; see PEP 563


from collections import defaultdict
import json
import logging
import typing

import tango
from tango.test_context import MultiDeviceTestContext

import ska_tango_base
from ska_tango_base.control_model import TestMode

from ska_low_mccs.device_proxy import MccsDeviceProxy


__all__ = ["MccsDeviceInfo", "MccsTangoContext", "MccsDeviceTestContext"]


class MccsDeviceInfo:
    """
    Data structure class that loads and holds information about devices,
    and can provide that information in the format required by
    :py:class:`tango.test_context.MultiDeviceTestContext`.
    """

    def __init__(self, source_path: str, package: str):
        """
        Create a new instance.

        :param source_path: the path to the configuration file that
            contains information about all available devices.
        :param package: name of the package from which to draw classes
        """
        with open(source_path, "r") as json_file:
            self._source_data = json.load(json_file)
        self._package = package
        self._devices = {}
        self._proxies = {}

    def include_device(
        self,
        name: str,
        proxy: MccsDeviceProxy,
        patch: ska_tango_base.SKABaseDevice = None,
    ) -> None:
        """
        Include a device in this specification.

        :param name: the name of the device to be included. The
            source data must contain configuration information for a
            device listed under this name
        :param proxy: the proxy class to use to access the device.
        :param patch: an optional device class with which to patch the
            named device

        :raises ValueError: if the named device does not exist in the
            source configuration data
        """
        for server in self._source_data["servers"]:
            if name in self._source_data["servers"][server]:
                device_spec = self._source_data["servers"][server][name]
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

                self._devices[name] = {
                    "server": server,
                    "class": klass,
                    "fqdn": fqdn,
                    "properties": properties,
                    "memorized": memorized,
                }
                self._proxies[fqdn] = proxy
                break
        else:
            raise ValueError(f"Device {name} not found in source data.")

    @property
    def device_map(self) -> typing.Dict[str, str]:
        """
        A dictionary that maps device names onto FQDNs.

        :return: a mapping from device names to FQDNs
        """
        return {
            name: {
                "fqdn": self._devices[name]["fqdn"],
                "proxy": self._proxies[self._devices[name]["fqdn"]],
            }
            for name in self._devices
        }

    @property
    def proxy_map(self) -> typing.Dict[str, MccsDeviceProxy]:
        """
        Return a map from FQDN to proxy type.

        :return: a map from FQDN to proxy type
        """
        return dict(self._proxies)

    def as_mdtc_device_info(self) -> typing.Dict:
        """
        Return this device info in a format required by
        :py:class:`tango.test_context.MultiDeviceTestContext`.

        :return: device info in a format required by
            :py:class:`tango.test_context.MultiDeviceTestContext`.
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


class MccsTangoContext:
    """
    MCCS wrapper for a Tango context.

    It allows for devices to be accessed by MCCS device names, rather
    than the device FQDNs.
    """

    def _load_devices(self, devices_to_load: typing.Dict) -> typing.Dict:
        """
        Loads device configuration data for specified devices from a
        specified JSON configuration file.

        :param devices_to_load: fixture that provides a specification of
            the devices that are to be included in the devices_info
            dictionary

        :return: a devices_info spec in a format suitable for use by as
            input to a
            :py:class:`tango.test_context.MultiDeviceTestContext`
        """
        device_info = MccsDeviceInfo(
            devices_to_load["path"], devices_to_load["package"]
        )
        for device_spec in devices_to_load["devices"]:
            device_info.include_device(**device_spec)
        return device_info

    def __init__(
        self,
        devices_to_load: typing.Dict,
        logger: logging.Logger,
        source: tango.DevSource = None,
    ):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of
            the devices that are to be included in the `devices_info`
            dictionary
        :param logger: the logger to be used by this object.
        :param source: a source value to be set on all devices
        """
        self._devices_info = self._load_devices(devices_to_load)

        self._base_harness = BaseTangoHarness(logger, self._devices_info.proxy_map)
        self._source_setting = source

    def __enter__(self) -> MccsTangoContext:
        """
        Entry method for "with" context.

        :return: the context object
        """
        self._base_harness.__enter__()
        self._set_source()
        assert self._check_ready()
        self._set_test_mode()
        return self

    def __exit__(
        self,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: typing.TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        self._base_harness.__exit__(exc_type, exception, trace)
        return False

    def _set_source(self) -> None:
        """
        Ensure that all included devices have the required source
        setting applied.
        """
        if self._source_setting is None:
            return
        for device_name in self._devices_info.device_map:
            self.get_device(device_name).set_source(self._source_setting)

            # HACK: increasing the timeout until we can make some commands asynchronous
            self.get_device(device_name).set_timeout_millis(5000)

    def _check_ready(self) -> bool:
        """
        Ensure that all included devices are checked against the
        provided ready condition.

        :return: whether all devices are initialised
        """
        for device_name in self._devices_info.device_map:
            device = self.get_device(device_name)
            if not device.check_initialised():
                return False
        else:
            return True

    def _set_test_mode(self) -> None:
        """
        Ensure that all included devices are set into test mode, since
        we are testing.
        """
        for device_name in self._devices_info.device_map:
            self.get_device(device_name).testMode = TestMode.TEST

    def get_device(
        self,
        name: str,
        connection_factory: typing.Callable[[str], tango.DeviceProxy] = None,
    ) -> MccsDeviceProxy:
        """
        Returns a :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
        to a device as specified by the device name provided in the
        configuration file.

        Each call to this method returns a fresh proxy. This is
        deliberate.

        :param name: the name of the device for which a
            :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` is
            sought.
        :param connection_factory: an optional connection factory to use
            instead of the default

        :return: a :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
            to the named device
        """
        fqdn = self._devices_info.device_map[name]["fqdn"]
        return self._base_harness.get_device(
            fqdn, connection_factory=connection_factory
        )


class MccsDeviceTestContext(MccsTangoContext):
    """
    MCCS wrapper for a tango.test_context.MultiDeviceTestContext.

    It allows for devices to be accessed by MCCS device names, rather
    than the device FQDNs.
    """

    def __init__(
        self,
        devices_to_load: typing.Dict,
        logger: logging.Logger,
        source: tango.DevSource = None,
        process: bool = False,
        host: str = None,
        port: int = None,
    ):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of
            the devices that are to be included in the `devices_info`
            dictionary
        :param logger: the logger to be used by this object.
        :param source: a source value to be set on all devices
        :param process: whether to run the test context in its own
            process; if False, it is run on a thread.
        :param host: hostname of the machine hosting the devices
        :param port: port for the tango subsystem
        """
        super().__init__(devices_to_load, logger, source=source)
        self._logger = self._base_harness.logger
        mdtc_devices_info = self._devices_info.as_mdtc_device_info()
        self._multi_device_test_context = MultiDeviceTestContext(
            mdtc_devices_info, process=process, host=host, port=port
        )

    def __enter__(self) -> MccsDeviceTestContext:
        """
        Entry method for "with" context.

        :return: the context object
        """
        self._multi_device_test_context.__enter__()
        return super().__enter__()

    def __exit__(
        self,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: typing.TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        self._multi_device_test_context.__exit__(exc_type, exception, trace)
        return False

    def get_device(self, name: str) -> MccsDeviceProxy:
        """
        Returns a :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
        to a device as specified by the device name provided in the
        configuration file.

        Each call to this method returns a fresh proxy. This is
        deliberate.

        :param name: the name of the device for which a
            :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` is
            sought.

        :return: a :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`
            to the named device
        """
        return super().get_device(
            name, connection_factory=self._multi_device_test_context.get_device
        )


class BaseTangoHarness:
    """
    This is a basic test harness for testing Tango devices.

    It doesn't stand any devices up; it assumes that the devices are
    already running.

    All it really does is make sure that the right type of client proxy
    (i.e. the right subclass of
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy`) is created
    when we ask for a proxy to a device.
    """

    def __init__(
        self,
        logger: logging.Logger,
        proxy_map: typing.Dict[str, typing.Type[MccsDeviceProxy]] = None,
    ):
        """
        Create a new instance.

        :param proxy_map: a optional mapping that assigns a type of
            device proxy to each FQDN.
        :param logger: a logger for this harness
        """
        self._proxy_map = proxy_map or {}
        self.logger = logger

    def __enter__(self) -> BaseTangoHarness:
        """
        Entry method for "with" context.

        :return: the context object
        """
        return self

    def __exit__(
        self,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: typing.TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        return False

    def get_device(
        self,
        fqdn: str,
        connection_factory: typing.Callable[[str], tango.DeviceProxy] = None,
    ) -> MccsDeviceProxy:
        """
        Create and return a proxy to the device at the given FQDN.

        :param fqdn: FQDN of the device for which a proxy is required
        :param connection_factory: an optional connection factory to use
            instead of the default

        :return: If the proxy map has an entry for the FQDN, then this
            will return a proxy of the type specified; otherwise, it
            returns an
            :py:class:`~ska_low_mccs.device_proxy.MccsDeviceProxy`.
        """
        proxy = self._proxy_map.get(fqdn, MccsDeviceProxy)
        return proxy(fqdn, self.logger, connection_factory=connection_factory)
