"""
Module for MCCS utils
"""
from functools import wraps
import inspect
import pkg_resources
import json
import jsonschema

from tango import Except, ErrSeverity
from tango.server import Device


class LazyInstance:
    """
    Wrapper for lazy object instantiation. The MCCS use case is device
    initialisation that requires the creation of device proxies to other
    devices, which themselves might not have been initialised yet. This
    causes connection errors, thus forcing us to refactor to ensure that
    devices can initialise in isolation -- they do not rely on other
    devices being ready before them.

    Through the use of this class, we can create a lazy device proxy: an
    object that looks and behaves like a tango.DeviceProxy, but that
    won't actually do the work to become one until the first time it is
    used.

    Example::

        device = LazyInstance(tango.DeviceProxy, fqdn)
        # we can now use this like tango.DeviceProxy, even though the
        # DeviceProxy hasn't actually been created yet

        device.On()
        # Calling the On() command on the device forces the deferred
        # creation of the tango.DeviceProxy object, so that the On()
        # command can be called

    """

    def __init__(self, cls, *args, **kwargs):
        """
        Initialise a new LazyInstance wrapper for a provided class
        instantiation

        :param cls: the class of the instantiation to be wrapped
        :param args: the positional args to pass to the class
            initialisation
        :param kwargs: the named args to pass to the class
            initialisation
        """
        self.__cls = cls
        self.__args = args
        self.__kwargs = kwargs

        self.__wrapped = None

    def __getattr__(self, attr):
        """
        Called if an attribute in this class is not found in the usual
        way. This is implemented to assume that the desired attribute
        is an attribute on the wrapped instance. It triggers
        instantiation of the wrapped instance if necessary, then passes
        the call to it.

        :param attr: name of the attribute sought
        :type attr: str
        """
        if self.__wrapped is None:
            self.__wrapped = self.__cls(*self.__args, **self.__kwargs)
        return getattr(self.__wrapped, attr)


def tango_raise(
    msg, reason="API_CommandFailed", severity=ErrSeverity.ERR, _origin=None
):
    """Helper function to provide a concise way to throw `tango.Except.throw_exception`

    Example::

        class MyDevice(Device):
            @command
            def some_command(self):
                if condition:
                    pass
                else:
                    tango_throw("Condition not true")


    :param msg: [description]
    :type msg: [type]
    :param reason: the tango api DevError description string, defaults to
                     "API_CommandFailed"
    :type reason: str, optional
    :param severity: the tango error severity, defaults to `tango.ErrSeverity.ERR`
    :type severity: `tango.ErrSeverity`, optional
    :param _origin: the calling object name, defaults to None (autodetected)
                   Note that autodetection only works for class methods not e.g.
                   decorators
    :type _origin: str, optional
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

    :param func: the function to call
    :ptype func: callable
    :param kwargs: parameters to be jsonified and passed to func
    :ptype kwargs: any
    :return: the return value of func
    :example: Suppose you need to use MccsMaster.Allocate() to command
        a master device to allocate certain stations and tiles to a
        subarray. Allocate() accepts a single JSON string argument.
        Instead of

            parameters={"id": id, "stations": stations, "tiles": tiles}
            json_string=json.dumps(parameters)
            master.Allocate(json_string)

        save yourself the trouble and

            call_with_json(master.Allocate,
                           id=id, stations=stations, tiles=tiles)

    """
    return func(json.dumps(kwargs))


class json_input:
    """
    Method decorator that parses and validates JSON input into a python
    object. The wrapped method is thus called with a JSON string, but
    can be implemented as if it had been passed an object.

    If the string cannot be parsed as JSON, an exception is raised.

    :param schema_path: an optional path to a schema against which the
        JSON should be validated. Not working at the moment, so leave it
        None.
    :ptype: string
    :raises FileNotFoundException: if no file is found at the schema
        path provided
    :raises json.JSONDecodeError: if the file at the specified schema
        path is not valid JSON

    :example: Conceptually, MccsMaster.Allocate() takes as arguments a
        subarray id, an array of stations, and an array of tiles. In
        practice, however, these arguments are encoded into a JSON
        string. Implement the function with its conceptual parameters,
        then wrap it in this decorator:

            @json_input
            def MccsMaster.Allocate(id, stations, tiles):

        The decorator will provide the JSON interface and handle the
        decoding for you.
    """

    def __init__(self, schema_path=None):
        """
        Initialises a callable json_input object, to function as a
        device method generator.
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

        """

        @wraps(func)
        def wrapped(cls, json_string):
            json_object = self._parse(json_string, func.__name__)
            return func(cls, **json_object)

        return wrapped

    def _parse(self, json_string, origin):
        """
        Parses and validates the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object
        :type json_string: str
        :param origin: the origin of this check; used to construct a
            helpful DevFailed exception.
        :type origin: str
        :raises json.JSONDecodeError: if the string cannot be decoded as
            a JSON string
        :raises jsonschema.ValidationError: if the decoded JSON object
            does not validate against a schema

        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object
