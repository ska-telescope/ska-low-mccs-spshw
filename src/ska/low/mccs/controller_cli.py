# -*- coding: utf-8 -*-
#
# This file is part of the Mccs project.
#
# Used to drive the Command Line Interface for the
# MCCS Controller Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
The command line interface for the MCCS Controller device server. Functionality
to handle passing variables to be added as functionality is added to the
Controller DS.
"""
import types
import functools
import fire
import tango
from ska.low.mccs.utils import call_with_json

from ska.base.commands import ResultCode


class CliMeta(type):
    """Metaclass to catch and disect `PyTango.DevFailed` and other exceptions for
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
    Wrapper to format device command results as a two-line string
    """

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        reslist = method(*args, **kwargs)
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return wrapper


class MccsControllerCli(metaclass=CliMeta):
    """test

    Command-line tool to access the MCCS controller tango device

        :param fqdn: the FQDN of the controller device, defaults to
            "low-mccs/control/control"
        :type fqdn: str, optional
    """

    def __init__(self, fqdn="low-mccs/control/control"):
        self._dp = tango.DeviceProxy(fqdn)
        self._log_levels = [
            lvl for lvl in dir(self._dp.logginglevel.__class__) if lvl.isupper()
        ]

    def adminmode(self):
        """show the admin mode
        TODO: make writable
        :return: adminmode
        :rtype: str
        """
        return self._dp.adminmode.name

    def controlmode(self):
        """show the control mode
        TODO: make writable
        :return: controlmode
        :rtype: str
        """
        return self._dp.controlmode.name

    def simulationmode(self):
        """show the control mode
        TODO: make writable
        :return: simulationmode
        :rtype: str
        """
        return self._dp.simulationmode.name

    def healthstate(self):
        """show the health state
        :return: healtstate
        :rtype: str
        """
        return self._dp.healthstate.name

    def logginglevel(self, level=None):
        """Get and/or set the logging level of the device.

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
    def enablesubarray(self, subarray_id):
        """Enable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        return self._dp.command_inout("EnableSubarray", subarray_id)

    @format_wrapper
    def disablesubarray(self, subarray_id):
        """Disable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        return self._dp.command_inout("DisableSubarray", subarray_id)

    @format_wrapper
    def allocate(self, subarray_id=0, stations=None):
        """
        Args:
            subarray_id (int, optional): [description]. Defaults to 0.
            stations (int, optional): [description]. Defaults to None.
        """
        if stations is None:
            stations = []
        station_fqdns = []
        station_proxies = []
        for station in stations:
            fqdn = f"low-mccs/station/{station:03}"
            station_fqdns.append(fqdn)
            station_proxies.append(tango.DeviceProxy(fqdn))
        message = self._dp.Allocate
        call_with_json(message, subarray_id=subarray_id, stations=station_fqdns)
        for proxy in station_proxies:
            status = proxy.adminmode.name
            name = proxy.name()
            print(f"{name}: {status}")
        return message

    @format_wrapper
    def release(self, subarray_id):
        """Release given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        return self._dp.command_inout("Release", subarray_id)

    @format_wrapper
    def maintenance(self):
        return self._dp.command_inout("Maintenance")


def main():
    fire.Fire(MccsControllerCli)


if __name__ == "__main__":
    main()
