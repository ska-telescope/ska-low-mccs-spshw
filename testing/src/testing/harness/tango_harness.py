# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements a MCCS test harness for Tango devices."""

from __future__ import annotations  # Allow forward refs in type hints; see PEP 563
from collections import defaultdict
import json
import logging
import socket
from types import TracebackType
import typing
import unittest.mock

import tango
from tango.test_context import MultiDeviceTestContext, get_host_ip


import ska_tango_base

from ska_low_mccs.device_proxy import MccsDeviceProxy


__all__ = [
    "MccsDeviceInfo",
    "TangoHarness",
    "BaseTangoHarness",
    "TestContextTangoHarness",
    "ClientProxyTangoHarness",
    "StartingStateTangoHarness",
    "MockingTangoHarness",
]


class MccsDeviceInfo:
    """
    Data structure class that loads and holds information about devices,
    and can provide that information in the format required by
    :py:class:`tango.test_context.MultiDeviceTestContext`.
    """

    def __init__(
        self: MccsDeviceInfo,
        path: str,
        package: str,
        devices: typing.Dict = None,
    ) -> None:
        """
        Create a new instance.

        :param path: the path to the configuration file that
            contains information about all available devices.
        :param package: name of the package from which to draw classes
        :param devices: option specification of devices. If not
            provided, then devices can be added via the
            :py:meth:`.include_device` method.
        """
        with open(path, "r") as json_file:
            self._source_data = json.load(json_file)
        self._package = package
        self._devices = {}
        self._proxies = {}

        if devices is not None:
            for device_spec in devices:
                self.include_device(**device_spec)

    def include_device(
        self: MccsDeviceInfo,
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
    def fqdns(self: MccsDeviceInfo) -> typing.List[str]:
        """
        Return a list of device fqdns.

        :returns: a list of device FQDNs
        """
        return self.fqdn_map.values()

    @property
    def fqdn_map(self: MccsDeviceInfo) -> typing.Dict[str, str]:
        """
        A dictionary that maps device names onto FQDNs.

        :return: a mapping from device names to FQDNs
        """
        return {name: self._devices[name]["fqdn"] for name in self._devices}

    @property
    def proxy_map(self: MccsDeviceInfo) -> typing.Dict[str, MccsDeviceProxy]:
        """
        Return a map from FQDN to proxy type.

        :return: a map from FQDN to proxy type
        """
        return dict(self._proxies)

    def as_mdtc_device_info(self: MccsDeviceInfo) -> typing.Dict:
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


class TangoHarness:
    """
    Abstract base class for Tango test harnesses. This does very little, because it
    needs to support both harnesses that directly interact with Tango, and wrapper
    harnesses that add functionality to another harness.

    The one really important thing it does do, is ensure that
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` uses this
    harness's ``connection factory`` to make connections.
    """

    def __init__(self: TangoHarness) -> None:
        """Initialise a new instance."""
        MccsDeviceProxy.set_default_connection_factory(self.connection_factory)

    @property
    def connection_factory(self: TangoHarness) -> None:
        """
        The connection factory to use when establishing connections to devices.

        :raises NotImplementedError: because this method is abstract
        """
        raise NotImplementedError("TangoHarness is abstract.")

    @property
    def fqdns(self: TangoHarness) -> typing.List[str]:
        """
        The FQDNs of devices in this harness.

        :raises NotImplementedError: because this method is abstract
        """
        raise NotImplementedError("TangoHarness is abstract.")

    def get_device(
        self: TangoHarness,
        fqdn: str,
    ) -> MccsDeviceProxy:
        """
        Create and return a proxy to the device at the given FQDN.

        :param fqdn: FQDN of the device for which a proxy is required

        :raises NotImplementedError: because this method is abstract
        """
        raise NotImplementedError("TangoHarness is abstract.")

    def __enter__(self: TangoHarness) -> TangoHarness:
        """
        Entry method for "with" context.

        :return: the context object
        """
        return self

    def __exit__(
        self: TangoHarness,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        return exception is None


class BaseTangoHarness(TangoHarness):
    """
    A basic test harness for Tango devices.

    This harness doesn't stand up any device; it assumes that devices
    are already running. It is thus useful for testing against deployed
    devices.
    """

    def __init__(
        self: BaseTangoHarness, device_info: MccsDeviceInfo, logger: logging.Logger
    ) -> None:
        """
        Initialise a new instance.

        :param device_info: object that makes device info available
        :param logger: a logger for the harness
        """
        self._fqdns = list(device_info.fqdns)
        self.logger = logger
        super().__init__()

    @property
    def connection_factory(self: BaseTangoHarness) -> typing.Type[tango.DeviceProxy]:
        """
        The connection factory to use when establishing connections to devices.

        This class uses :py:class:`tango.DeviceProxy` as its connection
        factory.

        :return: a DeviceProxy for use in establishing connections.
        """
        return tango.DeviceProxy

    @property
    def fqdns(self: BaseTangoHarness) -> typing.List[str]:
        """
        The FQDNs of devices in this harness.

        :return: a list of FQDNs of devices in this harness.
        """
        return list(self._fqdns)

    def get_device(
        self: BaseTangoHarness,
        fqdn: str,
    ) -> MccsDeviceProxy:
        """
        Create and return a proxy to the device at the given FQDN.

        :param fqdn: FQDN of the device for which a proxy is required

        :return: A proxy of the type specified by the proxy map.
        """
        return MccsDeviceProxy(fqdn, self.logger)


class ClientProxyTangoHarness(BaseTangoHarness):
    """A test harness for Tango devices that can return tailored client proxies."""

    def __init__(
        self: BaseTangoHarness,
        device_info: MccsDeviceInfo,
        logger: logging.Logger,
        **kwargs: typing.Any,
    ) -> None:
        """
        Initialise a new instance.

        :param device_info: object that makes device info available
        :param logger: a logger for the harness
        :param kwargs: keyword arguments
        """
        self._proxy_map = dict(device_info.proxy_map)
        super().__init__(device_info, logger, **kwargs)

    def get_device(
        self: BaseTangoHarness,
        fqdn: str,
    ) -> MccsDeviceProxy:
        """
        Create and return a proxy to the device at the given FQDN.

        :param fqdn: FQDN of the device for which a proxy is required

        :return: A proxy of the type specified by the proxy map.
        """
        proxy = self._proxy_map.get(fqdn, MccsDeviceProxy)
        return proxy(fqdn, self.logger)


class TestContextTangoHarness(BaseTangoHarness):
    """
    A test harness for testing MCCS Tango devices in a lightweight test context.

    It stands up a
    :py:class:`tango.test_context.MultiDeviceTestContext` with the
    specified devices.
    """

    def __init__(
        self: TestContextTangoHarness,
        device_info: MccsDeviceInfo,
        logger: logging.Logger,
        process: bool = False,
        **kwargs: typing.Any,
    ) -> None:
        """
        Initialise a new instance.

        :param device_info: object that makes device info available
        :param logger: a logger for the harness
        :param process: whether to run the test context in a separate
            process or not
        :param kwargs: keyword arguments
        """
        self._host = get_host_ip()

        def _get_open_port() -> int:
            """
            Helper function that returns an available port on the local machine.

            TODO: Note the possibility of a race condition here. By the
            time the calling method tries to make use of this port, it
            might already have been taken by another process.

            :return: An open port
            :rtype: int
            """
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        self._port = _get_open_port()

        self._test_context = MultiDeviceTestContext(
            device_info.as_mdtc_device_info(),
            process=process,
            host=self._host,
            port=self._port,
        )
        super().__init__(device_info, logger, **kwargs)

    @property
    def connection_factory(
        self: TestContextTangoHarness,
    ) -> typing.Callable[[str, ...], tango.DeviceProxy]:
        """
        The connection factory to use when establishing connections to devices.

        This class uses :py:class:`tango.DeviceProxy` but patches it to
        use the long-form FQDN, as a workaround to an issue with
        :py:class:`tango.test_context.MultiDeviceTestContext`.

        :return: a DeviceProxy for use in establishing connections.
        """

        def connect(
            fqdn: str, *args: typing.Any, **kwargs: typing.Any
        ) -> tango.DeviceProxy:
            """
            Connect to the device.

            :param fqdn: the FQDN of the device to connect to
            :param args: positional args to pass to the underlying connection
            :param kwargs: keyword args to pass to the underlying connection

            :return: a connection to the device
            """
            return tango.DeviceProxy(
                f"tango://{self._host}:{self._port}/{fqdn}#dbase=no", *args, **kwargs
            )

        return connect

    def __enter__(self: TestContextTangoHarness) -> TestContextTangoHarness:
        """
        Entry method for "with" context.

        :return: the context object
        """
        self._test_context.__enter__()
        return super().__enter__()

    def __exit__(
        self: TestContextTangoHarness,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        if self._test_context.__exit__(exc_type, exception, trace):
            return super().__exit__(None, None, None)
        else:
            return super().__exit__(exc_type, exception, trace)


class WrapperTangoHarness(TangoHarness):
    """A base class for a Tango test harness that wraps another harness, providing some
    functionality in the wrapper."""

    def __init__(self: WrapperTangoHarness, harness: TangoHarness) -> None:
        """
        Initialise a new instance.

        :param harness: the harness to be wrapped
        """
        self._harness = harness
        super().__init__()

    def __enter__(self: WrapperTangoHarness) -> WrapperTangoHarness:
        """
        Entry method for "with" context.

        This just calls the entry method of the wrapped harness.

        :return: the context object
        """
        self._harness.__enter__()
        return self

    def __exit__(
        self: WrapperTangoHarness,
        exc_type: typing.Type[BaseException],
        exception: BaseException,
        trace: TracebackType,
    ) -> bool:
        """
        Exit method for "with" context.

        This just calls the entry method of the wrapped harness.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        return self._harness.__exit__(exc_type, exception, trace)

    @property
    def connection_factory(
        self: WrapperTangoHarness,
    ) -> typing.Callable[[str, ...], tango.DeviceProxy]:
        """
        The connection factory to use when establishing connections to devices.

        This just uses the connection factory of the wrapped harness.

        :return: a DeviceProxy for use in establishing connections.
        """
        return self._harness.connection_factory

    @property
    def fqdns(self: WrapperTangoHarness) -> typing.List[str]:
        """
        Return the FQDNs of devices in this harness.

        This implementation just returns FQDNs of devices in the wrapped
        harness.

        :returns: list of FQDNs of devices in this harness
        """
        return self._harness.fqdns

    def get_device(self: WrapperTangoHarness, fqdn: str) -> MccsDeviceProxy:
        """
        Return a device proxy to the device at the given FQDN.

        This implementation just gets the device from the wrapped
        harness.

        :param fqdn: the FQDN of the device

        :return: a proxy to the device
        """
        return self._harness.get_device(fqdn)


class StartingStateTangoHarness(WrapperTangoHarness):
    """
    A test harness for testing Tango devices, that provides for certain actions and
    checks that ensure that devices are in a desired initial state prior to testing.

    Specifically, it can:

    * Tell devices to bypass their attribute cache, so that written
      values can be read back immediately
    * Check that devices have completed initialisation and transitioned
      out of the INIT state
    * Set device testMode to TestMode.TEST
    """

    def __init__(
        self: StartingStateTangoHarness,
        harness: TangoHarness,
        bypass_cache: bool = True,
        check_ready: bool = True,
        set_test_mode: bool = True,
    ) -> None:
        """
        Initialise a new instance.

        :param harness: the wrapped harness
        :param bypass_cache: whether to tell each device to bypass its
            attribute cache so that written attribute values can be read
            back again immediately
        :param check_ready: whether to check whether each device has
            completed initialisation and transitioned out of INIT state
            before allowing tests to be run.
        :param set_test_mode: whether to set the device into test mode
            before allowing tests to be run.
        """
        self._bypass_cache = bypass_cache
        self._check_ready = check_ready
        self._set_test_mode = set_test_mode

        super().__init__(harness)

    def __enter__(self: StartingStateTangoHarness) -> StartingStateTangoHarness:
        """
        Entry method for "with" context.

        This is where we make sure that devices are ready to be tested.

        :return: the context object
        """
        super().__enter__()
        self._make_devices_ready()
        return self

    def _make_devices_ready(self: StartingStateTangoHarness) -> None:
        """Helper method that applies actions and checks to ensure that devices are
        ready to be tested."""
        if self._bypass_cache or self._check_ready or self._set_test_mode:
            for fqdn in self.fqdns:
                device = self.get_device(fqdn)
                if self._bypass_cache:
                    device.set_source(tango.DevSource.DEV)
                if self._check_ready:
                    assert device.check_initialised()
                if self._set_test_mode:
                    device.testMode = ska_tango_base.control_model.TestMode.TEST


class MockingTangoHarness(WrapperTangoHarness):
    """A Tango test harness that wraps another harness, but only uses that harness for a
    specified set of devices under test, and mocks out all other devices."""

    def __init__(
        self: MockingTangoHarness,
        harness: TangoHarness,
        mock_factory: typing.Callable[[str], unittest.mock.Mock],
        initial_mocks: typing.Dict[str, unittest.mock.Mock],
    ) -> None:
        """
        Initialise a new instance.

        :param harness: the wrapped harness
        :param mock_factory: the factory to be used to build mocks
        :param initial_mocks: a pre-build dictionary of mocks to be used
            for particular
        """
        self._mocks = defaultdict(mock_factory, initial_mocks)
        super().__init__(harness)

    @property
    def connection_factory(
        self: MockingTangoHarness,
    ) -> typing.Callable[
        [str, ...], typing.Union[tango.DeviceProxy, unittest.mock.Mock]
    ]:
        """
        The connection factory to use when establishing connections to devices.

        This is where we check whether the requested device is on our
        list. Devices on the list are passed to the connection factory
        of the wrapped harness. Devices not on the list are intercepted
        and given a mock factory instead.

        :return: a factory that putatively provides device connections,
            but might actually provide mocks.
        """

        def connect(
            fqdn: str, *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Union[tango.DeviceProxy, unittest.mock.Mock]:
            """
            Connect to the device.

            :param fqdn: the FQDN of the device to connect to
            :param args: positional args to pass to the underlying connection
            :param kwargs: keyword args to pass to the underlying connection

            :return: a connection (possibly mocked) to the device
            """
            if fqdn in self.fqdns:
                return self._harness.connection_factory(fqdn, *args, **kwargs)
            else:
                return self._mocks[fqdn]

        return connect
