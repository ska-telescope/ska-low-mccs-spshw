"""
Module for MCCS utils.
"""
from functools import wraps
import inspect
import json
import pkg_resources

import backoff
import jsonschema
from tango import DevFailed, DevState, Except, ErrSeverity
from tango.server import Device
import tango


class _DeviceConnector:
    """
    Class that handles connecting to devices.

    Because devices will try to connect to unready devices during system
    startup, this class contains a sequence of checks, in backoff-retry
    loops, to ensure that connection requests do not complete until the
    target device is completely ready.
    """

    def __init__(self, logger):
        """
        Create a new instance.

        :param logger: the logger to be used.
        :type logger: :py:class:`logging.Logger`
        """
        self._logger = logger

    def _get_proxy(self, fqdn, max_time=120):
        """
        Get a proxy to a device at a given FQDN.

        The :py:class:`tango.DeviceProxy` is written to be stateless, so
        we can successfully get a proxy to a device as soon as the Tango
        subsystem knows about the FQDN. Thus, obtaining a proxy does not
        mean that the device is ready to accept connections.

        :param fqdn: the fully qualified device name of the device
        :type fqdn: str
        :param max_time: the (optional) maximum time to attempt
            connection before giving up. The default is two minutes.
            This needs a large wait time because it will be called by
            initialising devices at subsystem startup. In an
            under-resourced k8s cluster, initialisation may take several
            minutes; that is, the pods that host devices may initialise
            several minutes apart.
        :type max_time: int

        :return: a proxy for the device
        :rtype: :py:class:`tango.DeviceProxy`
        """

        def _on_giveup_get_proxy(details):
            """
            Handler for when the backoff-retry loop gives up trying to
            make a connection to the device.

            :param details: a dictionary providing call context, such as
                the call args and the elapsed time
            :type details: dict
            """
            fqdn = details.args[0]
            self._logger.warning(
                f"Gave up trying to connect to device {fqdn} after "
                f"{details.elapsed} seconds."
            )

        @backoff.on_exception(
            backoff.expo,
            DevFailed,
            on_giveup=_on_giveup_get_proxy,
            factor=1,
            max_time=max_time,
        )
        def _backoff_get_proxy(fqdn):
            """
            Attempts connection to a specified device, using an
            exponential backoff-retry scheme in case of failure.

            :param fqdn: the fully qualified device name of the device for
                which this DeviceEventManager will manage change events
            :type fqdn: str

            :return: a proxy for the device
            :rtype: :py:class:`tango.DeviceProxy`
            """
            return tango.DeviceProxy(fqdn)

        return _backoff_get_proxy(fqdn)

    def _ping(self, device, max_time=120):
        """
        Ping a device until it is responsive.

        :param device: the device to be pinged
        :type device: :py:class:`tango.DeviceProxy`
        :param max_time: the (optional) maximum time to attempt to ping
            the device before giving up. The default is two minutes.
            This needs a large wait time because it has been found that,
            during startup in an under-resourced k8s cluster, a device
            may be unresponsive to pings for up to a minute after a
            proxy to the device has been obtained.
        :type max_time: int
        """

        def _on_giveup_ping(details):
            """
            Handler for when the backoff-retry loop gives up trying to
            ping the device.

            :param details: a dictionary providing call context, such as
                the call args and the elapsed time
            :type details: dict
            """
            fqdn = details.args[0]
            self._logger.warning(
                f"Gave up trying to get response from device {fqdn} after "
                f"{details.elapsed} seconds."
            )

        @backoff.on_exception(
            backoff.expo,
            DevFailed,
            on_giveup=_on_giveup_ping,
            factor=1,
            max_time=max_time,
        )
        def _backoff_ping(device):
            """
            Ping a device to see if it is ready to accept connections,
            using an exponential backoff-retry schema in case of
            failure.

            :param device: the device to be pinged
            :type device: :py:class:`tango.DeviceProxy`
            """
            _ = device.ping()

        _backoff_ping(device)

    def _check_initialised(self, device, max_time=120):
        """
        Check that a device has completed initialisation; that is, it is
        not longer in state INIT.

        :param device: the device to be checked
        :type device: :py:class:`tango.DeviceProxy`
        :param max_time: the (optional) maximum time to wait for the
            device to complete initialisation. The default is two
            minutes.
        :type max_time: int

        :raises TimeoutError: if the device still hasn't initialised
            after a sufficient wait time.
        """

        def _on_giveup_check_initialised(details):
            """
            Handler for when the backoff-retry loop gives up waiting for
            the device to complete initialisation.

            :param details: a dictionary providing call context, such as
                the call args and the elapsed time
            :type details: dict
            """
            fqdn = details.args[0]
            self._logger.warning(
                f"Gave up waiting for device {fqdn} to complete initialisation after "
                f"{details.elapsed} seconds."
            )

        @backoff.on_predicate(
            backoff.expo,
            on_giveup=_on_giveup_check_initialised,
            factor=1,
            max_time=max_time,
        )
        def _backoff_check_initialised(device):
            """
            Check that the device has completed initialisation; that is,
            it is no longer in DevState.INIT.

            Checking that a device has initialised means calling its
            `state()` method, and even after the device returns a
            response from a ping, it might still raise an exception in
            response to reading device state
            (``"BAD_INV_ORDER_ORBHasShutdown``). So here we catch that
            exception.

            :param device: the device to be checked
            :type device: :py:class:`tango.DeviceProxy`

            :return: whether the device has completed initialisation
            :rtype: bool
            """
            try:
                return device.state() != DevState.INIT
            except DevFailed:
                self._logger.debug(
                    "Caught a DevFailed exception while checking that the device has "
                    "initialised. This is most likely a 'BAD_INV_ORDER_ORBHasShutdown "
                    "exception triggered by the call to state()."
                )
                return False

        if not _backoff_check_initialised(device):
            raise TimeoutError(
                "Gave up waiting for device {fqdn} to complete initialisation."
            )

    def connect(self, fqdn):
        """
        Returns a connection to a device that is responsive and has
        completed its initialisation.

        Firstly, it repeatedly attempts to connect to the device at the
        given FQDN until it succeeds (or times out). However success
        means only that the Tango subsystem knows about the FQDNs and
        has allows a stateless connection to the device. It does not
        mean that the device is ready. It doesn't even mean that the
        device has been started yet.

        Secondly, it repeatedly pings the device until the device
        becomes responsive (or times out).

        Thirdly, it repeatedly checks device state until that state is
        not INIT.

        Only when we have a connection to a responsive device that has
        completed initialisation, do we return it for use.

        :param fqdn: the fully qualified device name of the device
        :type fqdn: str

        :return: a connection to a device that is responsive and has
            completed its initialisation.
        :rtype: :py:class:`tango.DeviceProxy`
        """
        device = self._get_proxy(fqdn)
        self._ping(device)
        self._check_initialised(device)
        return device


def backoff_connect(fqdn, logger):
    """
    Create a proxy connection to the device, and if necessary wait for
    the device to become responsive and complete initialisation.

    :param fqdn: the fully qualified device name of the device for
        which this DeviceEventManager will manage change events
    :type fqdn: str
    :param logger: the logger to be used.
    :type logger: :py:class:`logging.Logger`

    :return: a proxy for the device
    :rtype: :py:class:`tango.DeviceProxy`
    """
    return _DeviceConnector(logger).connect(fqdn)


@backoff.on_predicate(backoff.expo, factor=0.1, max_time=3)
def _backoff_device_ready(device):
    """
    Checks that device is ready to accept commands, using an exponential
    backoff-retry scheme in case it is still initialising.

    :param device: proxy to the device
    :type device: :py:class:`tango.DeviceProxy`

    :return: whether the device is ready
    :rtype: bool
    """
    return device.state() != DevState.INIT


def backoff_connect(fqdn, wait=True):
    """
    Connects to a specified device (using an exponential backoff-retry
    scheme in case of failure), then (optionally) waits for the device to have
    completed initialisation.

    :param fqdn: the fully qualified device name of the device for
        which this DeviceEventManager will manage change events
    :type fqdn: str
    :param wait: whether to wait for the target device to complete
        initialisation before returning
    :type wait: bool

    :return: a proxy for the device
    :rtype: :py:class:`tango.DeviceProxy`
    """
    device = _backoff_device_proxy(fqdn)
    if wait and _backoff_device_ready(device):
        return device
    else:
        return None


def tango_raise(
    msg, reason="API_CommandFailed", severity=ErrSeverity.ERR, _origin=None
):
    """
    Helper function to provide a concise way to throw
    :py:class:`tango.Except.throw_exception <pytango:tango.Except>`.

    Example::

        class MyDevice(Device):
            @command
            def some_command(self):
                if condition:
                    pass
                else:
                    tango_throw("Condition not true")


    :param msg: message
    :type msg: str
    :param reason: the tango api :py:class:`tango.DevError`
        description string, defaults to "API_CommandFailed"
    :type reason: str, optional
    :param severity: the tango error severity, defaults to `tango.ErrSeverity.ERR`
    :type severity: :py:class:`tango.ErrSeverity`, optional
    :param _origin: the calling object name, defaults to None (autodetected)
        Note that autodetection only works for class methods not e.g.
        decorators
    :type _origin: str, optional

    :raises TypeError: if used from an object that is not a tango device
        instance
    """
    if _origin is None:
        frame = inspect.currentframe().f_back
        calling_method = frame.f_code.co_name
        calling_class = frame.f_locals["self"].__class__
        if Device not in inspect.getmro(calling_class):
            raise TypeError("Can only be used in a tango device instance")
        class_name = calling_class.__name__
        _origin = f"{class_name}.{calling_method}()"
    Except.throw_exception(reason, msg, _origin, severity)


def call_with_json(func, **kwargs):
    """
    Allows the calling of a command that accepts a JSON string as input,
    with the actual unserialised parameters.

    For example, suppose you need to use `Allocate(resources)` command
    to tell a controller device to allocate certain stations and tiles
    to a subarray. `Allocate` accepts a single JSON string argument.
    Instead of

    Example::

        parameters={"id": id, "stations": stations, "tiles": tiles}
        json_string=json.dumps(parameters)
        controller.Allocate(json_string)

    save yourself the trouble and

    Example::

        call_with_json(controller.Allocate, id=id, stations=stations, tiles=tiles)

    :param func: the function handle to call
    :type func: callable
    :param kwargs: parameters to be jsonified and passed to func
    :type kwargs: dict[str]

    :return: the return value of func
    """
    return func(json.dumps(kwargs))


class json_input:  # noqa: N801
    """
    Method decorator that parses and validates JSON input into a python
    dictionary, which is then passed to the method as kwargs. The
    wrapped method is thus called with a JSON string, but can be
    implemented as if it had been passed a sequence of named arguments.

    If the string cannot be parsed as JSON, an exception is raised.

    For example, conceptually, MccsController.Allocate() takes as
    arguments a subarray id, an array of stations, and an array of
    tiles. In practice, however, these arguments are encoded into a JSON
    string. Implement the function with its conceptual parameters, then
    wrap it in this decorator:

    Example::

        @json_input
        def MccsController.Allocate(id, stations, tiles):

    The decorator will provide the JSON interface and handle the
    decoding for you.
    """

    def __init__(self, schema_path=None):
        """
        Initialises a callable json_input object, to function as a
        device method generator.

        :param schema_path: an optional path to a schema against which
            the JSON should be validated. Not working at the moment, so
            leave it None.
        :type schema_path: str
        """
        self.schema = None

        if schema_path is not None:
            schema_string = pkg_resources.resource_string(
                "ska.low.mccs.schemas", schema_path
            )
            self.schema = json.loads(schema_string)

    def __call__(self, func):
        """
        The decorator method. Makes this class callable, and ensures
        that when called on a device method, a wrapped method is
        returned.

        :param func: The target of the decorator
        :type func: callable

        :return: function handle of the wrapped method
        :rtype: callable
        """

        @wraps(func)
        def wrapped(obj, json_string):
            """
            The wrapped function.

            :param obj: the object that owns the method to be wrapped
                i.e. the value passed into the method as "self"
            :type obj: object
            :param json_string: The string to be JSON-decoded into
                kwargs
            :type json_string: str

            :return: whatever the function to be wrapped returns
            :rtype: any
            """
            json_object = self._parse(json_string)
            return func(obj, **json_object)

        return wrapped

    def _parse(self, json_string):
        """
        Parses and validates the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object
        :type json_string: str

        :return: an object parsed from the input JSON string
        :rtype: anything JSON-serialisable
        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object
