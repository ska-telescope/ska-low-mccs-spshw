"""
Module for MCCS utils
"""
import backoff
from functools import wraps
import inspect
import pkg_resources
import json
import jsonschema

from tango import Except, ErrSeverity
from tango.server import Device
import tango


@backoff.on_exception(backoff.expo, tango.DevFailed, factor=0.1, max_tries=8)
def backoff_connect(fqdn):
    """
    Attempts connection to a specified device, using an exponential
    backoff-retry scheme in case of failure

    :param fqdn: the fully qualified device name of the device for
        which this DeviceEventManager will manage change events
    :type fqdn: str

    :return: a proxy for the device
    :rtype: :py:class:`tango.DeviceProxy`
    """
    return tango.DeviceProxy(fqdn)


def tango_raise(
    msg, reason="API_CommandFailed", severity=ErrSeverity.ERR, _origin=None
):
    """Helper function to provide a concise way to throw
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

    For example, suppose you need to use `MccsController.Allocate()` to
    command a controller device to allocate certain stations and tiles
    to a subarray. Allocate() accepts a single JSON string argument.
    Instead of

    Example::

        parameters={"id": id, "stations": stations, "tiles": tiles}
        json_string=json.dumps(parameters)
        controller.Allocate(json_string)

    save yourself the trouble and

    Example::

        call_with_json(controller.Allocate, id=id, stations=stations, tiles=tiles)

    :param func: the function to call
    :type func: callable
    :param kwargs: parameters to be jsonified and passed to func
    :type kwargs: any

    :return: the return value of func
    """
    return func(json.dumps(kwargs))


class json_input:
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
        :type schema_path: string
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
        :type func: function

        :return: the wrapped method
        :rtype: callable
        """

        @wraps(func)
        def wrapped(cls, json_string):
            json_object = self._parse(json_string)
            return func(cls, **json_object)

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
