#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""The command line interface for the MCCS Controller device server."""

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
    Metaclass to catch exceptions.

    Dissect :py:exc:`tango.DevFailed` and other exceptions for all class
    methods. They get turned into :py:exc:`fire.core.FireError`
    exceptions.
    """

    def __new__(
        cls: Type[CliMeta], name: str, bases: tuple[type], attrs: dict
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
        Wrap a Tango exception and raise a FireError.

        Wraps the method so that any :py:exc:`tango.DevFailed` exception
        raised by a method is converted to a
        :py:exc:`fire.core.FireError`, so that the CLI framework handles
        it nicely.

        :param method: the method to be wrapped

        :return: the wrapped method
        """

        @functools.wraps(method)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            """
            Catch a tango.DevFailed and raise a FireError.

            Wrapper that catches any :py:exc:`tango.DevFailed` exception
            raised by the wrapped method, and converts it to a
            :py:exc:`fire.core.FireError`, so that the CLI framework
            handles it nicely.

            :param args: positional arguments to the wrapped method
            :param kwargs: keyword arguments to the wrapped method

            :raises FireError: if a :py:exc:`tango.DevFailed`
                exception is raised by the method.

            :return: whatever the method returns
            """
            try:
                return method(*args, **kwargs)
            except tango.DevFailed as ptex:
                raise FireError(ptex.args[0].desc)
            except Exception as ex:
                raise FireError(str(ex))

        return _wrapper


def format_wrapper(
    method: Callable,
) -> Callable[[tuple[ResultCode, str]], str]:
    """
    Wrap the return message as a two line string.

    Wraps a method with a wrapper that ensures that the method returns results formatted
    as a two-line string.

    :param method: the method to be wrapped

    :return: the wrapped method
    """

    @functools.wraps(method)
    def _wrapper(*args: Any, **kwargs: Any) -> str:
        """
        Wrap the return message as a two line string.

        Wrapper that ensure device command methods return results formatted as a
        two- line string.

        :param args: positional arguments to the wrapped method
        :param kwargs: keyword arguments to the wrapped method

        :return: what the method returns, formatted into a two-line
             string
        """
        reslist = method(*args, **kwargs)
        return (
            f"Return code: {ResultCode(reslist[0][0]).name}\nMessage: {reslist[1][0]}"
        )

    return _wrapper


class MccsControllerCli(metaclass=CliMeta):
    """Command-line interface to the MccsController tango device."""

    def __init__(
        self: MccsControllerCli, fqdn: str = "low-mccs/control/control"
    ) -> None:
        """
        Initialise a new CLI instance.

        :param fqdn: the FQDN of the controller device. Optional:
            defaults to "low-mccs/control/control"
        """
        self._dp = tango.DeviceProxy(fqdn)
        self._log_levels = [
            lvl for lvl in dir(self._dp.logginglevel.__class__) if lvl.isupper()
        ]

    def adminmode(self: MccsControllerCli) -> str:
        """
        Show the admin mode.

        :todo: make writable

        :return: the admin mode
        """
        return self._dp.adminmode.name

    def controlmode(self: MccsControllerCli) -> str:
        """
        Show the control mode.

        :todo: make writable

        :return: control mode
        """
        return self._dp.controlmode.name

    def simulationmode(self: MccsControllerCli) -> str:
        """
        Show the control mode.

        :todo: make writable

        :return: simulation mode
        """
        return self._dp.simulationmode.name

    def healthstate(self: MccsControllerCli) -> str:
        """
        Show the health state.

        :return: health state
        """
        return self._dp.healthstate.name

    def logginglevel(self: MccsControllerCli, level: Optional[str] = None) -> str:
        """
        Get and/or set the logging level of the device.

        :param level: the logging level, defaults to None (only print the level)

        :return: logging level value
        """
        if level is not None:
            elevel = self._dp.logginglevel.__class__[level.upper()]
            self._dp.logginglevel = elevel
        return self._dp.logginglevel.name

    @format_wrapper
    def on(self: MccsControllerCli) -> str:
        """
        Turn the controller (and hence all of MCCS) on.

        :return: A return code and a string
            message indicating status converted into a two line string
        """
        return self._dp.command_inout("On")

    @format_wrapper
    def off(self: MccsControllerCli) -> str:
        """
        Turn the controller (and hence all of MCCS) off.

        :return: A return code and a string
            message indicating status converted into a two line string
        """
        return self._dp.command_inout("Off")

    @format_wrapper
    def standbyfull(self: MccsControllerCli) -> str:
        """
        Put the controller (and hence all of MCCS) into full-power standby mode.

        :return: A return code and a string
            message indicating status converted into a two line string
        """
        return self._dp.command_inout("StandbyFull")

    @format_wrapper
    def reset(self: MccsControllerCli) -> str:
        """
        Reset the controller following a fatal error.

        :return: A return code and a string
            message indicating status converted into a two line string
        """
        return self._dp.command_inout("Reset")

    @format_wrapper
    def allocate(
        self: MccsControllerCli,
        subarray_id: int = 0,
        station_ids: list[list[int]] = [[1]],
        subarray_beam_ids: list[int] = [1],
        channel_blocks: list[int] = [1],
    ) -> str:
        """
        Allocate stations to a subarray.

        :param subarray_id: the subarray id, defaults to 1
        :param station_ids: the station ids, defaults to [[1]]
        :param subarray_beam_ids: the subarray_beam ids, defaults to [1]
        :param channel_blocks: the nos. of channel_blocks, defaults to [1]

        :return: a result message
        """
        (rc, message) = self._dp.command_inout(
            "Allocate",
            json.dumps(
                {
                    "subarray_id": subarray_id,
                    "station_ids": station_ids,
                    "subarray_beam_ids": subarray_beam_ids,
                    "channel_blocks": channel_blocks,
                }
            ),
        )
        return message

    @format_wrapper
    def release(self: MccsControllerCli, subarray_id: int = 0) -> str:
        """
        Release resources from a subarray.

        :param subarray_id: the subarray id, defaults to 0

        :return: A return code and a string
            message indicating status converted into a two line string
        """
        return self._dp.command_inout("Release", subarray_id)


def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return Fire(MccsControllerCli)


if __name__ == "__main__":
    main()
