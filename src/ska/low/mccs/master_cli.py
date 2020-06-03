# -*- coding: utf-8 -*-
#
# This file is part of the Mccs project.
#
# Used to drive the Command Line Interface for the
# MCCS Master Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
The command line interface for the MCCS Master device server. Functionality
to handle passing variables to be added as functionality is added to the
Master DS.
"""
import types
import functools
import fire
import tango
from ska.low.mccs.utils import call_with_json


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


class MccsMasterCli(metaclass=CliMeta):
    """test

    Command-line tool to access the MCCS master tango device

        :param fqdn: the FQDN of the master device, defaults to "low/elt/master"
        :type fqdn: str, optional
    """

    def __init__(self, fqdn="low/elt/master"):
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

    def on(self):
        self._dp.command_inout("On")

    def off(self):
        self._dp.command_inout("Off")

    def standbylow(self):
        self._dp.command_inout("StandbyLow")

    def standbyfull(self):
        self._dp.command_inout("StandbyFull")

    def operate(self):
        self._dp.command_inout("Operate")

    def reset(self):
        self._dp.command_inout("Reset")

    def enablesubarray(self, subarray_id):
        """Enable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("EnableSubarray", subarray_id)

    def disablesubarray(self, subarray_id):
        """Disable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("DisableSubarray", subarray_id)

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
            fqdn = "low/elt/station_{}".format(station)
            station_fqdns.append(fqdn)
            station_proxies.append(tango.DeviceProxy(fqdn))
        call_with_json(
            self._dp.Allocate, subarray_id=subarray_id, stations=station_fqdns,
        )
        for proxy in station_proxies:
            status = proxy.adminmode.name
            name = proxy.name()
            print(f"{name}: {status}")

    def release(self, subarray_id):
        """Release given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("Release", subarray_id)

    def maintenance(self):
        self._dp.command_inout("Maintenance")


def main():
    fire.Fire(MccsMasterCli)


if __name__ == "__main__":
    main()
