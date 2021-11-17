# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""Module for MCCS utils."""

from __future__ import annotations  # allow forward references in type hints

import functools
import json
import pkg_resources
import threading
from types import FunctionType
from typing import Any, Callable, Optional

import jsonschema


def call_with_json(func: Callable, **kwargs: Any) -> Any:
    """
    Call a command with a json string.

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
    Parse and validate json string input.

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
        Initialise a callable json_input object.

        To function as a device method generator.

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
        Make a class callable.

        The decorator method. Makes this class callable, and ensures that when called on
        a device method, a wrapped method is returned.

        :param func: The target of the decorator

        :return: function handle of the wrapped method
        """

        @functools.wraps(func)
        def wrapped(obj: object, json_string: str) -> object:
            """
            Wrap a function.

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
        Parse and validate the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object

        :return: a dictionary parsed from the input JSON string
        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object


CHECK_THREAD_SAFETY = False


class ThreadsafeCheckingMeta(type):  # pragma: no cover
    """Metaclass that checks for methods being run by multiple concurrent threads."""

    @staticmethod
    def _init_wrap(func: Callable) -> Callable:
        """
        Wrap ``__init__`` to add thread safety checking stuff.

        :param func: the ``__init__`` method being wrapped

        :return: a wrapped ``__init__`` method
        """

        @functools.wraps(func)
        def _wrapper(self: ThreadsafeCheckingMeta, *args: Any, **kwargs: Any) -> None:
            self._thread_id = {}  # type: ignore[attr-defined]
            func(self, *args, **kwargs)

        return _wrapper

    @staticmethod
    def _check_wrap(func: Callable) -> Callable:
        """
        Wrap the class methods that injects thread safety checks.

        :param func: the method being wrapped

        :return: the wrapped method
        """

        @functools.wraps(func)
        def _wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            thread_id = threading.current_thread().ident

            try:
                if func in self._thread_id:
                    assert (
                        self._thread_id[func] != thread_id
                    ), f"Method {func} has been re-entered by thread {thread_id}"

                    is_threadsafe = getattr(func, "_is_threadsafe", False)
                    assert (
                        is_threadsafe
                    ), f"Method {func} is already being run by thread {self._thread_id[func]}."
            except AssertionError:
                raise
            except Exception as exception:
                raise ValueError(
                    f"Exception when trying to run method {func}"
                ) from exception

            self._thread_id[func] = thread_id
            try:
                return func(self, *args, **kwargs)
            finally:
                # thread-safey way to delete this key, without caring if it has already
                # been deleted by another thread (because we might be multithreading
                # through this wrapper if the wrapped method is marked threadsafe).
                self._thread_id.pop(func, None)

        return _wrapper

    def __new__(
        cls: type[ThreadsafeCheckingMeta], name: str, bases: tuple[type], attrs: dict
    ) -> ThreadsafeCheckingMeta:
        """
        Construct Class.

        :param name: name of the new class
        :param bases: parent classes of the new class
        :param attrs: class attributes

        :return: new class
        """
        if CHECK_THREAD_SAFETY:
            methods = [attr for attr in attrs if isinstance(attrs[attr], FunctionType)]
            for attr_name in methods:
                if attr_name == "__init__":
                    attrs[attr_name] = cls._init_wrap(attrs[attr_name])
                elif attr_name in ["__getattr__", "__setattr__"]:
                    pass
                else:
                    attrs[attr_name] = cls._check_wrap(attrs[attr_name])

        return super(ThreadsafeCheckingMeta, cls).__new__(cls, name, bases, attrs)


def threadsafe(func: Callable) -> Callable:  # pragma: no cover
    """
    Use this method as a decorator for marking a method as threadsafe.

    This tells the ``ThreadsafeCheckingMeta`` metaclass that it is okay
    for the decorated method to have more than one thread in it at a
    time. The metaclass will still raise an exception if the *same*
    thread enters the method multiple times, because re-entry is a
    common cause of deadlock.

    :param func: the method to be marked as threadsafe

    :return: the method, marked as threadsafe
    """
    func._is_threadsafe = True  # type: ignore[attr-defined]
    return func
