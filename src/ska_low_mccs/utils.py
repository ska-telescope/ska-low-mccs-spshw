# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""Module for MCCS utils."""

from __future__ import annotations  # allow forward references in type hints

from functools import wraps
import json
import pkg_resources
from typing import Callable, Optional

import jsonschema

from ska_tango_base.commands import ResultCode


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

    def __init__(self: json_input, schema_path: Optional[str] = None):
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
            return func(obj, **json_object)

        return wrapped

    def _parse(self: json_input, json_string: str) -> dict[str, str]:
        """
        Parses and validates the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object

        :return: a dictionary parsed from the input JSON string
        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object
