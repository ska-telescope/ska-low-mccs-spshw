"""
Module for MCCS utils
"""
from functools import wraps
import inspect
import json
import jsonschema

from tango import Except, ErrSeverity
from tango.server import Device


def tango_raise(msg, origin=None, reason="API_CommandFailed", severity=ErrSeverity.ERR):
    """Helper function to concisely way to throw `tango.Except.throw_exception`

    Example::

        class MyDevice:
            def some_command(self):
                if condition:
                    pass
                else:
                    tango_throw("Condition not true")


    :param msg: [description]
    :type msg: [type]
    :param origin: the calling object name, defaults to None (autodetected)
                   Note that autodetection only works for class methods not e.g.
                   decorators
    :type origin: str, optional
    :param reason: the tango api DevError description string, defaults to
                     "API_CommandFailed"
    :type reason: str, optional
    :param severity: the tango error severity, defaults to `tango.ErrSeverity.ERR`
    :type severity: `tango.ErrSeverity`, optional
    """
    if origin is None:
        frame = inspect.currentframe().f_back
        calling_method = frame.f_code.co_name
        calling_class = frame.f_locals["self"].__class__
        if Device not in inspect.getmro(calling_class):
            raise TypeError("Can only be used in a tango device instance")
        class_name = calling_class.__name__
        origin = f"{class_name}.{calling_method}()"
    Except.throw_exception(reason, msg, origin, severity)


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
            try:
                with open(schema_path, "r") as schema_file:
                    schema_string = schema_file.read()
            except FileNotFoundError:
                self._throw(
                    "@json_input",
                    "JSON schema file not found at {}".format(schema_path),
                )

            try:
                self.schema = json.loads(schema_string)
            except json.JSONDecodeError as error:
                self._throw(
                    "@json_input",
                    "Invalid JSON. Input is:\n{}\nParser error is\n{}".format(
                        schema_string, error
                    ),
                )

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
        :raises json.JSONDecodeError if the string cannot be decoded as
            a JSON string
        :raises jsonschema.ValidationError if the decoded JSON object
            does not validate against a schema

        """
        try:
            json_object = json.loads(json_string)
        except json.JSONDecodeError as error:
            self._throw(
                origin,
                "Not valid JSON. Input is:\n{}\nParser error is\n{}".format(
                    json_string, error
                ),
            )
        if self.schema is None:
            return json_object

        try:
            jsonschema.validate(json_object, self.schema)
        except jsonschema.ValidationError as error:
            self._throw(
                origin, "JSON object does not validate: {}".format(error.message)
            )

        return json_object

    def _throw(self, origin, reason):
        """
        Helper method that constructs and throws a ``Tango.DevFailed``
        exception.

        :param origin: the origin of the error; typically the name of
            the command that the check was being conducted for.
        :type origin: string
        :param reason: the reason for the error
        :type reason: string

        """
        Except.throw_exception(
            "API_CommandFailed",
            "{}: {}".format(origin, reason),
            origin,
            ErrSeverity.ERR,
        )
