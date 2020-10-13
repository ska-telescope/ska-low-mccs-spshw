# -*- coding: utf-8 -*-
#
# This file is part of the Mccs project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
import types
import functools
import fire
import json
import tango

from ska.base.commands import ResultCode


class CliMeta(type):
    """Metaclass to catch and disect
    :py:class:`tango.DevFailed` and other exceptions for all
    class methods. They get turned into `fire.core.FireError` exceptions.
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


def commandResultAsString(method):
    """
    Wrapper to format device command results as a two-line string

    :param method: the method to wrap
    :type method: callable

    :return: the wrapped method
    :rtype: callable
    """

    @functools.wraps(method)
    def wrapper(*args, **kwds):
        reslist = method(*args, **kwds)
        # The commands convert the command tuple to the form [[return_code], [message]]
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return wrapper


class MccsTileCli(metaclass=CliMeta):
    def __init__(self):
        self.tile_number = 1
        self._dp = tango.DeviceProxy(f"low-mccs/tile/{self.tile_number:04}")

    @commandResultAsString
    def connect(self):
        """
        Connect to the hardware

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("connect", True)

    def subarrayid(self):
        """
        Return the id of the subarray the tile has been allocated to

        :return: subarray ID
        :rtype: int
        """
        return self._dp.subarrayId

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

    @commandResultAsString
    def SendBeamData(self, period=0, timeout=0, timestamp=None, seconds=0.2):
        args = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendBeamData", jstr)

    @commandResultAsString
    def SendChannelisedDataContinuous(
        self,
        channelID=None,
        nSamples=128,
        waitSeconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        try:
            args = {
                "ChannelID": channelID,
                "NSamples": nSamples,
                "WaitSeconds": waitSeconds,
                "Timeout": timeout,
                "Timestamp": timestamp,
                "Seconds": seconds,
            }
            jstr = json.dumps(args)
            return self._dp.command_inout("SendChannelisedDataContinuous", jstr)
        except tango.DevFailed:
            raise RuntimeError("ChannelID mandatory argument...cannot be a NULL value")

    @commandResultAsString
    def SendChannelisedData(
        self,
        nSamples=128,
        firstChannel=0,
        lastChannel=511,
        period=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        args = {
            "NSamples": nSamples,
            "FirstChannel": firstChannel,
            "LastChannel": lastChannel,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendChannelisedData", jstr)

    @commandResultAsString
    def SendRawData(self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2):
        args = {
            "Sync": sync,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendRawData", jstr)

    @commandResultAsString
    def ConfigureIntegratedBeamData(self, integration_time=0.5):
        return self._dp.command_inout("ConfigureIntegratedBeamData", integration_time)

    @commandResultAsString
    def ConfigureIntegratedChannelData(self, integration_time=0.5):
        return self._dp.command_inout(
            "ConfigureIntegratedChannelData", integration_time
        )

    @commandResultAsString
    def StartBeamformer(self, startTime=0, duration=-1):
        args = {"StartTime": startTime, "Duration": duration}
        jstr = json.dumps(args)
        return self._dp.command_inout("StartBeamformer", jstr)

    @commandResultAsString
    def StopBeamformer(self):
        return self._dp.command_inout("StopBeamformer")

    @commandResultAsString
    def LoadPointingDelay(self, load_time=0):
        return self._dp.command_inout("LoadPointingDelay", load_time)


def main():
    fire.Fire(MccsTileCli)


if __name__ == "__main__":
    main()
