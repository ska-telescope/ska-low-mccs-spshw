"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs functional (BDD) tests.
"""
from collections import defaultdict
import json
import socket

import pytest
import tango
from tango.test_context import get_host_ip, MultiDeviceTestContext

from ska_tango_base.control_model import TestMode
from ska.low.mccs import MccsDeviceProxy


def pytest_configure(config):
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    :type config: :py:class:`pytest.config.Config`
    """
    config.addinivalue_line("markers", "XTP-1170: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1257: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1260: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1261: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1473: XRay BDD test marker")


@pytest.fixture(scope="module")
def patch_device_proxy():
    """
    Fixture that provides a patcher that set up
    :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` to use a connection factory
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


class MccsDeviceInfo:
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
        self._proxies = {}

    def include_device(self, name, proxy, patch=None):
        """
        Include a device in this specification.

        :param name: the name of the device to be included. The
            source data must contain configuration informotion for a
            device listed under this name
        :type name: str
        :param proxy: the proxy class to use to access the device.
        :type proxy: :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
        :param patch: an optional device class with which to patch the
            named device
        :type patch: :py:class:`ska_tango_base.SKABaseDevice`

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
                break
        else:
            raise ValueError(f"Device {name} not found in source data.")

        self._proxies[name] = proxy

    @property
    def device_map(self):
        """
        A dictionary that maps device names onto FQDNs.

        :return: a mapping from device names to FQDNs
        :rtype: dict
        """
        return {
            name: {
                "fqdn": self._devices[name]["fqdn"],
                "proxy": self._proxies[name],
            }
            for name in self._devices
        }

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


class MccsTangoContext:
    """
    MCCS wrapper for a Tango context.

    It allows for devices to be accessed by MCCS device names, rather
    than the device FQDNs.
    """

    def _load_devices(self, devices_to_load):
        """
        Loads device configuration data for specified devices from a
        specified JSON configuration file.

        :param devices_to_load: fixture that provides a specification of
            the devices that are to be included in the devices_info
            dictionary
        :type devices_to_load: dict

        :return: a devices_info spec in a format suitable for use by as
            input to a
            :py:class:`tango.test_context.MultiDeviceTestContext`
        :rtype: dict
        """
        device_info = MccsDeviceInfo(
            devices_to_load["path"], devices_to_load["package"]
        )
        for device_spec in devices_to_load["devices"]:
            device_info.include_device(**device_spec)
        return device_info

    def __init__(
        self,
        devices_to_load,
        logger,
        source=None,
    ):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :type devices_to_load: dict
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param source: a source value to be set on all devices
        :type source: :py:class:`tango.DevSource`, optional
        """
        self._logger = logger
        self._devices_info = self._load_devices(devices_to_load)
        self._source_setting = source

    def __enter__(self):
        """
        Entry method for "with" context.

        :return: the context object
        :rtype: :py:class:`.MccsDeviceTestContext`
        """
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
        pass

    def _set_source(self):
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

    def _check_ready(self):
        """
        Ensure that all included devices are checked against the
        provided ready condition.

        :return: whether all devices are initialised
        :rtype: bool
        """
        for device_name in self._devices_info.device_map:
            device = self.get_device(device_name)
            if not device.check_initialised():
                return False
        else:
            return True

    def _set_test_mode(self):
        """
        Ensure that all included devices are set into test mode, since
        we are testing.
        """
        for device_name in self._devices_info.device_map:
            self.get_device(device_name).testMode = TestMode.TEST

    def get_device(self, name):
        """
        Returns a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
        to a device as specified by the device name provided in the
        configuration file.

        Each call to this method returns a fresh proxy. This is
        deliberate.

        :param name: the name of the device for which a
            :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` is sought.
        :type name: str

        :return: a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` to the named device
        :rtype: :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
        """
        fqdn = self._devices_info.device_map[name]["fqdn"]
        proxy = self._devices_info.device_map[name]["proxy"]
        device = proxy(fqdn, self._logger)
        return device


class MccsDeviceTestContext(MccsTangoContext):
    """
    MCCS wrapper for a tango.test_context.MultiDeviceTestContext.

    It allows for devices to be accessed by MCCS device names, rather
    than the device FQDNs.
    """

    def __init__(
        self,
        devices_to_load,
        logger,
        source=None,
        process=False,
        host=None,
        port=None,
    ):
        """
        Create a new instance.

        :param devices_to_load: fixture that provides a specification of the
            devices that are to be included in the devices_info dictionary
        :type devices_to_load: dict
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
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
        super().__init__(devices_to_load, logger, source=source)
        mdtc_devices_info = self._devices_info.as_mdtc_device_info()
        self._multi_device_test_context = MultiDeviceTestContext(
            mdtc_devices_info, process=process, host=host, port=port
        )

    def __enter__(self):
        """
        Entry method for "with" context.

        :return: the context object
        :rtype: :py:class:`.MccsDeviceTestContext`
        """
        self._multi_device_test_context.__enter__()
        return super().__enter__()

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
        Returns a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
        to a device as specified by the device name provided in the
        configuration file.

        Each call to this method returns a fresh proxy. This is
        deliberate.

        :param name: the name of the device for which a
            :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` is sought.
        :type name: str

        :return: a :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy` to the named device
        :rtype: :py:class:`ska.low.mccs.device_proxy.MccsDeviceProxy`
        """
        fqdn = self._devices_info.device_map[name]["fqdn"]
        proxy = self._devices_info.device_map[name]["proxy"]
        device = proxy(
            fqdn,
            self._logger,
            connection_factory=self._multi_device_test_context.get_device,
        )
        return device


@pytest.fixture(scope="module")
def tango_config(patch_device_proxy):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation entures that :py:class:`tango.DeviceProxy` is
    monkeypatched as a workaround for a bug in
    :py:class:`tango.test_context.MultiDeviceTestContext`, then returns the host and
    port used by the patch.

    This is a factory; the config won't actually be provided until you
    call it.

    :param patch_device_proxy: a fixture that handles monkeypatching of
        :py:class:`tango.DeviceProxy` as a workaround for a bug in
        :py:class:`tango.test_context.MultiDeviceTestContext`, and returns the host
        and port used in the patch
    :type patch_device_proxy: tuple

    :return: a callable that sets up the config
    :rtype: callable
    """

    def _config():
        """
        Function returned by the parent fixture that sets up the tango
        config when called.

        :returns: tango configuration information: a dictionary with keys
            "process", "host" and "port".
        :rtype: dict
        """
        (host, port) = patch_device_proxy()
        return {"process": True, "host": host, "port": port}

    return _config


@pytest.fixture(scope="module")
def tango_context(request, devices_to_load, tango_config, logger):
    """
    Returns a Tango context. The Tango context returned depends upon
    whether or not pytest was invoked with the `--true-context` option.

    If no, then this returns a tango.test_context.MultiDeviceTestContext
    set up with the devices specified in the module's devices_info.

    If yes, then this returns a context with an interface like that of
    tango.test_context.MultiDeviceTestContext, but actually providing
    access to a true Tango context.

    :todo: Even when testing against a true Tango context, we are still
        setting up the test context. This will be fixed when we unify
        the test harnesses (MCCS-329)

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dict
    :param tango_config: fixture that returns configuration information
        that specifies how the Tango system should be established and
        run.
    :type tango_config: dict
    :param logger: the logger to be used by this object.
    :type logger: :py:class:`logging.Logger`

    :yield: a tango context
    """
    try:
        true_context = request.config.getoption("--true-context")
    except ValueError:
        true_context = False

    if true_context:
        with MccsTangoContext(
            devices_to_load,
            logger,
            source=tango.DevSource.DEV,
        ) as context:
            yield context
    else:
        config = tango_config()
        with MccsDeviceTestContext(
            devices_to_load,
            logger,
            source=tango.DevSource.DEV,
            process=config["process"],
            host=config["host"],
            port=config["port"],
        ) as context:
            yield context


@pytest.fixture(scope="module")
def cached_obsstate():
    """
    Use a pytest message box to retain obsstate between test stages.

    :return: cached_obsstate: pytest message box for the cached obsstate
    :rtype: cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    return {}
