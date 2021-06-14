# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
Module for MCCS utils.
"""

from __future__ import annotations  # allow forward references in type hints

import json
import inspect
import jsonschema
import pkg_resources
from functools import wraps
from typing import Callable, cast

from tango import Except, ErrSeverity  # type: ignore[attr-defined]
from tango.server import Device  # type: ignore[attr-defined]
from ska_tango_base.commands import ResultCode


def tango_raise(
    msg: str,
    reason: str = "API_CommandFailed",
    severity: ErrSeverity = ErrSeverity.ERR,
    _origin: str = None,
) -> None:
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
    :param reason: the tango api :py:class:`tango.DevError`
        description string, defaults to "API_CommandFailed"
    :param severity: the tango error severity, defaults to `tango.ErrSeverity.ERR`
    :param _origin: the calling object name, defaults to None (autodetected)
        Note that autodetection only works for class methods not e.g.
        decorators

    :raises TypeError: if used from an object that is not a tango device
        instance
    """
    if _origin is None:
        current_frame = inspect.currentframe()
        if current_frame is not None:
            frame = current_frame.f_back
            if frame is not None:
                fcode = frame.f_code
                flocals = frame.f_locals["self"]
                if fcode is not None and flocals is not None:
                    calling_method = fcode.co_name
                    calling_class = frame.f_locals["self"].__class__
                    if Device not in inspect.getmro(calling_class):
                        raise TypeError("Can only be used in a tango device instance")
                    class_name = calling_class.__name__
                    _origin = f"{class_name}.{calling_method}()"
                    Except.throw_exception(reason, msg, _origin, severity)
        raise TypeError("Can't access frame, f_code or f_locals")
    Except.throw_exception(reason, msg, _origin, severity)


def call_with_json(func: Callable, **kwargs: dict[str, str]) -> tuple[ResultCode, str]:
    """
    Allows the calling of a command that accepts a JSON string as input, with the actual
    unserialised parameters.

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
    :param kwargs: parameters to be jsonified and passed to func

    :return: the return value of func
    """
    return func(json.dumps(kwargs))


class json_input:  # noqa: N801
    """
    Method decorator that parses and validates JSON input into a python dictionary,
    which is then passed to the method as kwargs. The wrapped method is thus called with
    a JSON string, but can be implemented as if it had been passed a sequence of named
    arguments.

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

    def __init__(self: json_input, schema_path: str = None):
        """
        Initialises a callable json_input object, to function as a device method
        generator.

        :param schema_path: an optional path to a schema against which
            the JSON should be validated. Not working at the moment, so
            leave it None.
        """
        self.schema = None

        if schema_path is not None:
            schema_string = pkg_resources.resource_string(
                "ska_low_mccs.schemas", schema_path
            )
            self.schema = json.loads(schema_string)

    def __call__(self: json_input, func: Callable) -> Callable:
        """
        The decorator method. Makes this class callable, and ensures that when called on
        a device method, a wrapped method is returned.

        :param func: The target of the decorator

        :return: function handle of the wrapped method
        """

        @wraps(func)
        def wrapped(obj: object, json_string: str) -> object:
            """
            The wrapped function.

            :param obj: the object that owns the method to be wrapped
                i.e. the value passed into the method as "self"
            :param json_string: The string to be JSON-decoded into
                kwargs

            :return: whatever the function to be wrapped returns
            """
            json_object = self._parse(json_string)
            cast(dict, json_object)
            return func(obj, **cast(dict, json_object))

        return wrapped

    def _parse(self: json_input, json_string: str) -> object:
        """
        Parses and validates the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object

        :return: an object parsed from the input JSON string
        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object
