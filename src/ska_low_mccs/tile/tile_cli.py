# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
The command line interface for the MCCS Tile device server.
"""
import functools
import json
import types

from fire import Fire
from fire.core import FireError
import tango

from ska_tango_base.commands import ResultCode


class CliMeta(type):
    """
    Metaclass to catch and dissect :py:class:`tango.DevFailed` and other
    exceptions for all class methods.

    They get turned into `fire.core.FireError` exceptions.
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

            :raises FireError: if a :py:exc:`tango.DevFailed` exception
                is raised by the method.

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


def command_result_as_string(method):
    """
    Wrapper to format device command results as a two-line string.

    :param method: function handle of the method to wrap
    :type method: callable

    :return: function handle of the wrapped method
    :rtype: callable
    """

    @functools.wraps(method)
    def _wrapper(*args, **kwargs):
        """
        Wrapper that ensure device command methods return results
        formatted as a a two-line string.

        :param args: positional arguments to the wrapped method
        :type args: list
        :param kwargs: keyword arguments to the wrapped method
        :type kwargs: dict

        :return: what the method returns, formatted into a two-line
             string
        :rtype: str
        """
        reslist = method(*args, **kwargs)
        # The commands convert the command tuple to the form [[return_code], [message]]
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return _wrapper


class MccsTileCli(metaclass=CliMeta):
    """
    Command-line interface to the
    :py:class:`ska_low_mccs.MccsTile` tango device.
    """

    def __init__(self):
        """
        Initialise a new CLI instance.

        Hardcoded to connect to "low-mccs/tile/0001".
        """
        self.tile_number = 1
        self._dp = tango.DeviceProxy(f"low-mccs/tile/{self.tile_number:04}")

    @command_result_as_string
    def connect(self):
        """
        Connect to the hardware.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("connect", True)

    def subarrayid(self):
        """
        Return the id of the subarray the tile has been allocated to.

        :return: subarray ID
        :rtype: int
        """
        return self._dp.subarrayId

    def logginglevel(self, level=None):
        """
        Get and/or set the logging level of the device.

        :param level: the logging level to be set. If omited, return the current
            logging level
        :type level: str

        :return: logging level value
        :rtype: str
        """
        if level is not None:
            elevel = self._dp.logginglevel.__class__[level.upper()]
            self._dp.logginglevel = elevel
        return self._dp.logginglevel.name

    @command_result_as_string
    def SendBeamData(self, period=0, timeout=0, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing beamformed data.

        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        args = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendBeamData", jstr)

    @command_result_as_string
    def SendChannelisedDataContinuous(
        self,
        channel_id=None,
        num_samples=128,
        wait_seconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        :param channel_id: index of channel to send
        :type channel_id: int
        :param num_samples: number of spectra to send, defaults to 1024
        :type num_samples: int, optional
        :param wait_seconds: wait time before sending data
        :type wait_seconds: float
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        :raises RuntimeError: if a general failure occurred in device
        """
        try:
            args = {
                "ChannelID": channel_id,
                "NSamples": num_samples,
                "WaitSeconds": wait_seconds,
                "Timeout": timeout,
                "Timestamp": timestamp,
                "Seconds": seconds,
            }
            jstr = json.dumps(args)
            return self._dp.command_inout("SendChannelisedDataContinuous", jstr)
        except tango.DevFailed:
            raise RuntimeError("ChannelID mandatory argument...cannot be a NULL value")

    @command_result_as_string
    def SendChannelisedData(
        self,
        num_samples=128,
        first_channel=0,
        last_channel=511,
        period=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        """
        Transmit a snapshot containing channelized data totalling
        number_of_samples spectra.

        :param num_samples: number of spectra to send, defaults to 1024
        :type num_samples: int, optional
        :param first_channel: first channel to send, defaults to 0
        :type first_channel: int, optional
        :param last_channel: last channel to send, defaults to 511
        :type last_channel: int, optional
        :param period: period of time, in seconds, to send data, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        args = {
            "NSamples": num_samples,
            "FirstChannel": first_channel,
            "LastChannel": last_channel,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendChannelisedData", jstr)

    @command_result_as_string
    def SendRawData(self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2):
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :type sync: bool, optional
        :param period: duration to send data, in seconds, defaults to 0
        :type period: int, optional
        :param timeout: when to stop, defaults to 0
        :type timeout: int, optional
        :param timestamp: when to start(?), defaults to None
        :type timestamp: int, optional
        :param seconds: when to synchronise, defaults to 0.2
        :type seconds: float, optional

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        args = {
            "Sync": sync,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendRawData", jstr)

    @command_result_as_string
    def ConfigureIntegratedBeamData(self, integration_time=0.5):
        """
        Configure the transmission of integrated beam data with the
        provided integration time.

        :param integration_time: integration time in seconds, defaults
            to 0.5
        :type integration_time: float

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("ConfigureIntegratedBeamData", integration_time)

    @command_result_as_string
    def ConfigureIntegratedChannelData(self, integration_time=0.5):
        """
        Configure the transmission of integrated channel data with the
        provided integration time.

        :param integration_time: integration_time in seconds (defaults
            to 0.5)
        :type integration_time: float

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout(
            "ConfigureIntegratedChannelData", integration_time
        )

    @command_result_as_string
    def StartBeamformer(self, start_time=0, duration=-1):
        """
        Start the beamformer at the specified time delay.

        :param start_time: the start time
        :type start_time: int
        :param duration: how long to run (default is -1, meaning run
            forever)
        :type duration: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        args = {"StartTime": start_time, "Duration": duration}
        jstr = json.dumps(args)
        return self._dp.command_inout("StartBeamformer", jstr)

    @command_result_as_string
    def StopBeamformer(self):
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("StopBeamformer")

    @command_result_as_string
    def LoadPointingDelay(self, load_time=0):
        """
        Loads the pointing delays at the specified time delay.

        :param load_time: time delay (default = 0)
        :type load_time: int

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        return self._dp.command_inout("LoadPointingDelay", load_time)


def main():
    """
    Entry point for CLI.
    """
    Fire(MccsTileCli)


if __name__ == "__main__":
    main()
