# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Used to drive the Command Line Interface for the
# MCCS Controller Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""The command line interface for the MCCS Controller device server."""
import types
import functools

from fire import Fire
from fire.core import FireError
import tango

from ska_tango_base.commands import ResultCode

from ska_low_mccs.utils import call_with_json


class CliMeta(type):
    """
    Metaclass to catch and dissect :py:exc:`tango.DevFailed` and other exceptions for
    all class methods.

    They get turned into :py:exc:`fire.core.FireError` exceptions.
    """

    def __new__(cls, name, bases, attrs):
        """
        Class constructor.

        :param name: name of the new class
        :type name: str
        :param bases: parent classes of the new class
        :type bases: tuple(cls)
        :param attrs: class attributes
        :type attrs: dict

        :return: new class
        :rtype: cls
        """
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, types.FunctionType):
                attrs[attr_name] = cls.fire_except(attr_value)
        return super(CliMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def fire_except(cls, method):
        """
        Wraps the method so that any :py:exc:`tango.DevFailed` exception
        raised by a method is converted to a
        :py:exc:`fire.core.FireError`, so that the CLI framework handles
        it nicely.

        :param method: the method to be wrapped
        :type method: callable

        :return: the wrapped method
        :rtype: callable
        """

        @functools.wraps(method)
        def _wrapper(*args, **kwargs):
            """
            Wrapper that catches any :py:exc:`tango.DevFailed` exception
            raised by the wrapped method, and converts it to a
            :py:exc:`fire.core.FireError`, so that the CLI framework
            handles it nicely.

            :param args: positional arguments to the wrapped method
            :type args: list
            :param kwargs: keyword arguments to the wrapped method
            :type kwargs: dict

            :raises FireError: if a :py:exc:`tango.DevFailed`
                exception is raised by the method.

            :return: whatever the method returns
            :rtype: object
            """
            try:
                return method(*args, **kwargs)
            except tango.DevFailed as ptex:
                raise FireError(ptex.args[0].desc)
            except Exception as ex:
                raise FireError(str(ex))

        return _wrapper


def format_wrapper(method):
    """
    Wraps a method with a wrapper that ensures that the method returns results formatted
    as a two-line string.

    :param method: the method to be wrapped
    :type method: callable

    :return: the wrapped method
    :rtype: callable
    """

    @functools.wraps(method)
    def _wrapper(*args, **kwargs):
        """Wrapper that ensure device command methods return results formatted as a a
        two- line string.

        :param args: positional arguments to the wrapped method
        :type args: list
        :param kwargs: keyword arguments to the wrapped method
        :type kwargs: dict

        :return: what the method returns, formatted into a two-line
             string
        :rtype: str
        """
        reslist = method(*args, **kwargs)
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return _wrapper


class MccsControllerCli(metaclass=CliMeta):
    """
    Command-line interface to the
    :py:class:`ska_low_mccs.MccsController` tango device.
    """

    def __init__(self, fqdn="low-mccs/control/control"):
        """
        Initialise a new CLI instance.

        :param fqdn: the FQDN of the controller device. Optional:
            defaults to "low-mccs/control/control"
        :type fqdn: str
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
        """
        Turn the controller (and hence all of MCCS) on.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("On")

    @format_wrapper
    def off(self):
        """
        Turn the controller (and hence all of MCCS) off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("Off")

    @format_wrapper
    def standbylow(self):
        """
        Put the controller (and hence all of MCCS) into low-power standby mode.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("StandbyLow")

    @format_wrapper
    def standbyfull(self):
        """
        Put the controller (and hence all of MCCS) into full-power standby mode.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("StandbyFull")

    @format_wrapper
    def operate(self):
        """
        Call the "Operate" command on the controller.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("Operate")

    @format_wrapper
    def reset(self):
        """
        Reset the controller following a fatal error.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
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
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("Release", subarray_id)

    @format_wrapper
    def maintenance(self):
        """
        Set admin mode to maintenance.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("Maintenance")


def main():
    """Entry point for CLI."""
    Fire(MccsControllerCli)


if __name__ == "__main__":
    main()
