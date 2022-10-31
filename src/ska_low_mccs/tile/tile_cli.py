# type: ignore
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""The command line interface for the MCCS Tile device server."""

from __future__ import annotations  # allow forward references in type hints

import functools
import json
import types
from typing import Any, Callable, Optional, Type

import tango
from fire import Fire
from fire.core import FireError
from ska_tango_base.commands import ResultCode


class CliMeta(type):
    """
    Metaclass to catch and dissect exceptions for all class methods.

    They get turned into `fire.core.FireError` exceptions.
    """

    def __new__(
        cls: Type[CliMeta], name: str, bases: tuple[CliMeta], attrs: dict
    ) -> CliMeta:
        """
        Class constructor.

        :param name: name of the new class
        :param bases: parent classes of the new class
        :param attrs: class attributes

        :return: new class
        """
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, types.FunctionType):
                attrs[attr_name] = cls.fire_except(attr_value)
        return super(CliMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def fire_except(cls: Type[CliMeta], method: Callable) -> Callable:
        """
        Wrap the method to handle exceptions.

        Any :py:exc:`tango.DevFailed` exception raised by a method is converted to a
        :py:exc:`fire.core.FireError`, so that the CLI framework handles it nicely.

        :param method: the method to be wrapped

        :return: the wrapped method
        """

        @functools.wraps(method)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            """
            Wrap tango exceptions.

            Any :py:exc:`tango.DevFailed` exception
            raised by the wrapped method, and converts it to a
            :py:exc:`fire.core.FireError`, so that the CLI framework
            handles it nicely.

            :param args: positional arguments to the wrapped method
            :param kwargs: keyword arguments to the wrapped method

            :raises FireError: if a :py:exc:`tango.DevFailed` exception
                is raised by the method.

            :return: whatever the method returns
            """
            try:
                return method(*args, **kwargs)
            except tango.DevFailed as ptex:
                raise FireError(ptex.args[0].desc)
            except Exception as ex:
                raise FireError(str(ex))

        return _wrapper


def command_result_as_string(method: Callable) -> Callable:
    """
    Wrap and format device command results as a two-line string.

    :param method: function handle of the method to wrap

    :return: function handle of the wrapped method
    """

    @functools.wraps(method)
    def _wrapper(*args: tuple, **kwargs: dict) -> str:
        """
        Wrap and ensure device command methods return formatted two-line strings.

        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :return: what the method returns, formatted into a two-line
             string
        """
        reslist = method(*args, **kwargs)
        # The commands convert the command tuple to the form [[return_code], [message]]
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return _wrapper


class MccsTileCli(metaclass=CliMeta):
    """Command-line interface to :py:class:`ska_low_mccs.tile.tile_device.MccsTile`."""

    def __init__(self: MccsTileCli) -> None:
        """
        Initialise a new CLI instance.

        Hardcoded to connect to "low-mccs/tile/0001".
        """
        self.tile_number = 1
        self._dp = tango.DeviceProxy(f"low-mccs/tile/{self.tile_number:04}")

    @command_result_as_string
    def connect(self: MccsTileCli) -> tuple[ResultCode, str]:
        """
        Connect to the hardware.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._dp.command_inout("connect", True)

    def subarrayid(self: MccsTileCli) -> int:
        """
        Return the id of the subarray the tile has been allocated to.

        :return: subarray ID
        """
        return self._dp.subarrayId

    def logginglevel(self: MccsTileCli, level: Optional[str] = None) -> str:
        """
        Get and/or set the logging level of the device.

        :param level: the logging level to be set. If omited, return the current
            logging level

        :return: logging level value
        """
        if level is not None:
            elevel = self._dp.logginglevel.__class__[level.upper()]
            self._dp.logginglevel = elevel
        return self._dp.logginglevel.name

    @command_result_as_string
    def SendBeamData(
        self: MccsTileCli,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> tuple[ResultCode, str]:
        """
        Transmit a snapshot containing beamformed data.

        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        args = {
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendBeamData", jstr)

    @command_result_as_string
    def SendChannelisedDataContinuous(
        self: MccsTileCli,
        channel_id: Optional[int] = None,
        num_samples: int = 128,
        wait_seconds: int = 0,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> tuple[ResultCode, str]:
        """
        Transmit channelised data continuously.

        :param channel_id: index of channel to send
        :param num_samples: number of spectra to send, defaults to 1024
        :param wait_seconds: wait time before sending data
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :raises RuntimeError: if a general failure occurred in device
        """
        try:
            args = {
                "ChannelID": channel_id,
                "NSamples": num_samples,
                "WaitSeconds": wait_seconds,
                "Timestamp": timestamp,
                "Seconds": seconds,
            }
            jstr = json.dumps(args)
            return self._dp.command_inout("SendChannelisedDataContinuous", jstr)
        except tango.DevFailed:
            raise RuntimeError("ChannelID mandatory argument...cannot be a NULL value")

    @command_result_as_string
    def SendChannelisedData(
        self: MccsTileCli,
        num_samples: int = 128,
        first_channel: int = 0,
        last_channel: int = 511,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> tuple[ResultCode, str]:
        """
        Transmit a snapshot 0f channelized data totalling number_of_samples spectra.

        :param num_samples: number of spectra to send, defaults to 1024
        :param first_channel: first channel to send, defaults to 0
        :param last_channel: last channel to send, defaults to 511
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        args = {
            "NSamples": num_samples,
            "FirstChannel": first_channel,
            "LastChannel": last_channel,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendChannelisedData", jstr)

    @command_result_as_string
    def SendRawData(
        self: MccsTileCli,
        sync: bool = False,
        timestamp: Optional[str] = None,
        seconds: float = 0.2,
    ) -> tuple[ResultCode, str]:
        """
        Transmit a snapshot containing raw antenna data.

        :param sync: whether synchronised, defaults to False
        :param timestamp: when to start(?), defaults to None
        :param seconds: when to synchronise, defaults to 0.2

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        args = {
            "Sync": sync,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        jstr = json.dumps(args)
        return self._dp.command_inout("SendRawData", jstr)

    @command_result_as_string
    def ConfigureIntegratedBeamData(
        self: MccsTileCli, integration_time: float = 0.5
    ) -> tuple[ResultCode, str]:
        """
        Configure the transmission of integrated beam data with the integration time.

        :param integration_time: integration time in seconds, defaults
            to 0.5

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._dp.command_inout("ConfigureIntegratedBeamData", integration_time)

    @command_result_as_string
    def ConfigureIntegratedChannelData(
        self: MccsTileCli, integration_time: float = 0.5
    ) -> tuple[ResultCode, str]:
        """
        Configure the transmission of integrated channel data with the integration time.

        :param integration_time: integration_time in seconds (defaults
            to 0.5)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._dp.command_inout(
            "ConfigureIntegratedChannelData", integration_time
        )

    @command_result_as_string
    def StartBeamformer(
        self: MccsTileCli, start_time: int = 0, duration: int = -1
    ) -> tuple[ResultCode, str]:
        """
        Start the beamformer at the specified time delay.

        :param start_time: the start time
        :param duration: how long to run (default is -1, meaning run
            forever)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        args = {"StartTime": start_time, "Duration": duration}
        jstr = json.dumps(args)
        return self._dp.command_inout("StartBeamformer", jstr)

    @command_result_as_string
    def StopBeamformer(self: MccsTileCli) -> tuple[ResultCode, str]:
        """
        Stop the beamformer.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._dp.command_inout("StopBeamformer")

    @command_result_as_string
    def LoadPointingDelay(
        self: MccsTileCli, load_time: int = 0
    ) -> tuple[ResultCode, str]:
        """
        Load the pointing delays at the specified time delay.

        :param load_time: time delay (default = 0)

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        return self._dp.command_inout("LoadPointingDelay", load_time)


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return Fire(MccsTileCli)


if __name__ == "__main__":
    main()
