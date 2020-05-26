# -*- coding: utf-8 -*-
#
# This file is part of the Mccs project.
#
# Used to drive the Command Line Interface for the
# MCCS Master Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
import functools
import fire
import json
import tango
import PyTango

"""
The command line interface for the MCCS Master device server. Functionality
to handle passing variables to be added as functionality is added to the
Master DS.
"""


def format_exception(method):
    """decorator to catch and disect  `PyTango.DevFailed` execption and turn it
    into a `fire.core.FireError`
    """

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except PyTango.DevFailed as ptex:
            raise fire.core.FireError(ptex.args[0].desc)
        except Exception as ex:
            raise fire.core.FireError(str(ex))

    return wrapper


class MccsMasterCli:
    def __init__(self):
        self._dp = tango.DeviceProxy("low/elt/master")
        self._log_levels = [
            lvl for lvl in dir(self._dp.logginglevel.__class__) if lvl.isupper()
        ]

    @property
    def adminmode(self):
        """show the admin mode
        TODO: make writable
        :return: adminmode
        :rtype: str
        """
        return self._dp.adminmode.name

    @property
    def controlmode(self):
        """show the control mode
        TODO: make writable
        :return: controlmode
        :rtype: str
        """
        return self._dp.controlmode.name

    @property
    def simulationmode(self):
        """show the control mode
        TODO: make writable
        :return: simulationmode
        :rtype: str
        """
        return self._dp.simulationmode.name

    @property
    def healthstate(self):
        """show the health state
        :return: healtstate
        :rtype: str
        """
        return self._dp.healthstate.name

    @format_exception
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

    @format_exception
    def on(self):
        self._dp.command_inout("On")

    @format_exception
    def off(self):
        self._dp.command_inout("Off")

    @format_exception
    def standbylow(self):
        self._dp.command_inout("StandbyLow")

    @format_exception
    def standbyfull(self):
        self._dp.command_inout("StandbyFull")

    @format_exception
    def operate(self):
        self._dp.command_inout("Operate")

    @format_exception
    def reset(self):
        self._dp.command_inout("Reset")

    @format_exception
    def enablesubarray(self, subarray_id):
        """Enable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("EnableSubarray", subarray_id)

    @format_exception
    def disablesubarray(self, subarray_id):
        """Disable given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("DisableSubarray", subarray_id)

    @format_exception
    def allocate(self, subarray_id=0, stations=""):
        """
        Args:
            subarray_id (int, optional): [description]. Defaults to 0.
            stations (str, optional): comma separated list of station numbers (not the
            FQDN). Defaults to "".
        """
        args = {
            "subarray_id": subarray_id,
            "stations": ["low/elt/{}".format(station) for station in stations],
        }
        jstr = json.dumps(args)
        self._dp.command_inout("Allocate", jstr)

    @format_exception
    def release(self, subarray_id):
        """Release given subarray

        :param subarray_id: the id of the subarray
        :type subarray_id: int
        """
        self._dp.command_inout("Release", subarray_id)

    @format_exception
    def maintenance(self):
        self._dp.command_inout("Maintenance")


def main():
    fire.Fire(MccsMasterCli)


if __name__ == "__main__":
    main()
