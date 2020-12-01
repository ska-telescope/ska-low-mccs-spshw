# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Used to drive the Command Line Interface for the
# MCCS Controller Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
The command line interface for the MCCS Controller device server.

Functionality to handle passing variables to be added as functionality
is added to the Controller DS.
"""
import types
import functools
import fire
import tango
from ska.low.mccs.utils import call_with_json

from ska.base.commands import ResultCode


class CliMeta(type):
    """Metaclass to catch and disect
    :py:class:`tango.DevFailed` and other exceptions for
    all class methods. They get turned into `fire.core.FireError` exceptions.
    """

    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, types.FunctionType):
                attrs[attr_name] = cls.fire_except(attr_value)
        return super(CliMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def fire_except(cls, method):
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except tango.DevFailed as ptex:
                raise fire.core.FireError(ptex.args[0].desc)
            except Exception as ex:
                raise fire.core.FireError(str(ex))

        return wrapper


def format_wrapper(method):
    """
    Wrapper to format device command results as a two-line string.

    :param method: function handle of the method to be wrapped
    :type method: callable

    :return: function handle of the wrapped method
    :rtype: callable
    """

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        reslist = method(*args, **kwargs)
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return wrapper


class MccsControllerCli(metaclass=CliMeta):
    """
    Command-line tool to access the
    :py:class:`ska.low.mccs.MccsController` tango device.
    """

    def __init__(self, fqdn="low-mccs/control/control"):
        """
        Initialise a new CLI instance.

        :param fqdn: the FQDN of the controller device, defaults to
            "low-mccs/control/control"
        :type fqdn: str, optional
        """
        self._dp = tango.DeviceProxy(fqdn)
        self._log_levels = [
            lvl for lvl in dir(self._dp.logginglevel.__class__) if lvl.isupper()
        ]

    def adminmode(self):
        """
        Show the admin mode.

        :todo: make writable

        :return: the admin mode
        :rtype: str
        """
        return self._dp.adminmode.name

    def controlmode(self):
        """
        Show the control mode.

        :todo: make writable

        :return: control mode
        :rtype: str
        """
        return self._dp.controlmode.name

    def simulationmode(self):
        """
        Show the control mode.

        :todo: make writable

        :return: simulation mode
        :rtype: str
        """
        return self._dp.simulationmode.name

    def healthstate(self):
        """
        Show the health state.

        :return: health state
        :rtype: str
        """
        return self._dp.healthstate.name

    def logginglevel(self, level=None):
        """
        Get and/or set the logging level of the device.

        :param level: the logging level, defaults to None (only print the level)
        :type level: str, optional

        :return: logging level value
        :rtype: str
        """
        if level is not None:
            elevel = self._dp.logginglevel.__class__[level.upper()]
            self._dp.logginglevel = elevel
        return self._dp.logginglevel.name

    @format_wrapper
    def on(self):
        return self._dp.command_inout("On")

    @format_wrapper
    def off(self):
        return self._dp.command_inout("Off")

    @format_wrapper
    def standbylow(self):
        return self._dp.command_inout("StandbyLow")

    @format_wrapper
    def standbyfull(self):
        return self._dp.command_inout("StandbyFull")

    @format_wrapper
    def operate(self):
        return self._dp.command_inout("Operate")

    @format_wrapper
    def reset(self):
        return self._dp.command_inout("Reset")

    @format_wrapper
    def allocate(self, subarray_id=0, station_ids=None):
        """
        Allocate stations to a subarray.

        :param subarray_id: the subarray id, defaults to 0
        :type subarray_id: int, optional
        :param station_ids: the station ids, defaults to None
        :type station_ids: list(int), optional

        :return: a result message
        :rtype: str
        """
        if station_ids is None:
            station_ids = []
        station_proxies = []
        for station in station_ids:
            fqdn = f"low-mccs/station/{station:03}"
            station_proxies.append(tango.DeviceProxy(fqdn))
        message = self._dp.Allocate
        call_with_json(message, subarray_id=subarray_id, station_ids=station_ids)
        for proxy in station_proxies:
            status = proxy.adminmode.name
            name = proxy.name()
            print(f"{name}: {status}")
        return message

    @format_wrapper
    def release(self, subarray_id):
        """
        Release resources from a a subarray.

        :param subarray_id: the subarray id, defaults to 0
        :type subarray_id: int, optional

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("Release", subarray_id)

    @format_wrapper
    def maintenance(self):
        return self._dp.command_inout("Maintenance")


def main():
    fire.Fire(MccsControllerCli)


if __name__ == "__main__":
    main()
