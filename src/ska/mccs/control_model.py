# -*- coding: utf-8 -*-
#
# This file is part of the SKA Software lfaa-lmc-prototype project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains definitions and helper methods that assist with
managing the device state machines.
"""
__all__ = ["ReturnCode", "device_check"]

import enum
from functools import wraps
from tango import Except, ErrSeverity


class ReturnCode(enum.IntEnum):
    """ Python enumerator type for return codes."""

    OK = 0
    """
    Commands return this code when the command was successfully run to
    completion synchronously.
    """

    STARTED = 1
    """
    Commands return this code to indicate that it was immediately able
    to start an asynchronous context (e.g. thread, asyncio coroutine) to
    execute the command.
    """

    QUEUED = 2
    """
    Commands return this code to indicate that the command has been
    queued to run, and will start at some time in the future.
    """

    FAILED = 3
    """
    Commands return this code to indicates that the command has failed.
    """

    UNKNOWN = 4
    """
    Commands return this code to indicate that the status of the command
    is not known.
    """


class device_check:
    """
    Method decorator that only permits a device method to be run if the
    device passes the given checks, otherwise raising a
    ``tango.DevFailed`` exception.

    It can be used on a command itself (e.g. `Scan()`), or, to conform
    to Tango subsystem expectations, as the implementation of the
    `is_[Command]_allowed` method (e.g. `is_Scan_allowed()`) that the
    Tango subsystem calls prior to calling the command itself. It can
    also be used on asynchronous callbacks, to check that the state is
    what the asynchronous context expected it to be.

    Since this decorator knows nothing of the implementation details
    of any device, the device class must register the checks that it may
    want to perform, before making use of the decorator.

    :example: `FooDevice` has a `state` attribute, the current value of
        which is stored in `self._state`. The device command `Foo()` is
        allowed only when the state is `READY`. The device class (note
        class not instance) first registers a check named "state":

        ::

            device_check.register(
                "state",
                lambda device, value: device._state == value
            )

        and then it can use the ``@device_check`` decorator to ensure
        that the state is checked before `Foo()` is run:

        ::

            @device_check(state=READY)
            def Foo(self):
                pass

        A device that subclasses `FooDevice` will inherit the checks
        `FooDevice` has registered, but can register new checks of its
        own.
    """

    checks = {}

    @classmethod
    def register(cls, name, func):
        """
        Registers a device check with the ``@device_check`` decorator.

        :param name: the name of the check. Once registered, this check
            may be invoked by using the name as an argument to the
            decorator.
        :type name: string
        :param func: a function that takes two arguments: the device to
            checked, and a comparison value to be passed into the check.
        :type func: function
        """
        cls.checks[name] = func

    def __init__(self, **kwargs):
        """
        Initialises a callable device_check object, to function as a
        device method generator.

        :param kwargs: a dictionary where the keys are the names of the
            checks to be run, and the values are passed into the check.
            Each key must have been registered by the device class, or a
            KeyError will occur when the decorator is called.
        :type kwargs: dict

        """
        self._kwargs = kwargs

    def __call__(self, func):
        """
        The decorator method. Makes this class callable, and ensures
        that when called on a device method, a wrapped method is
        returned.

        :param func: The target of the decorator
        :type func: function

        """
        @wraps(func)
        def wrapped(device, *args, **kwargs):
            self._check(device, func.__name__)
            return func(device, *args, **kwargs)
        return wrapped

    def _check(self, device, origin, throw=True):
        """
        Performs the requested device checks.

        :param device: the device on which the checks are performed.
        :type device: by intent, a Tango device; however it could be
            any object really
        :param origin: the origin of this check; used to construct a
            helpful DevFailed exception.
        :type origin: string
        :param throw: What to do if a check fails. If ``True``, raise a
            ``Tango.DevFailed`` exception; if ``False``, return
            ``False``.
        :type throw: boolean (default ``True``)
        :raises Tango.DevFailed: if the ``throw`` argument is ``True``
            and a check fails.

        """
        for key in self._kwargs:
            if not device_check.checks[key](device, self._kwargs[key]):
                if throw:
                    self._throw(origin, key)
                else:
                    return False
        return True

    def _throw(self, origin, check):
        """
        Helper method that constructs and throws a ``Tango.DevFailed``
        exception.

        :param origin: the origin of the check; typically the name of
            the command that the check was being conducted for.
        :type origin: string
        :param check: the name of the check that failed.
        :type check: string

        """
        Except.throw_exception(
            "API_CommandFailed",
            "{}: Command disallowed on check '{}'".format(origin, check),
            origin,
            ErrSeverity.ERR
        )
