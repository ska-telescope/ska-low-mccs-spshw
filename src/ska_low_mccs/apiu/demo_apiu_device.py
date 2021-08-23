# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a Demo APIU device.

DemoAPIU extends MccsAPIU with extra interface features that support
testing and demonstrating the MCCS APIU device.
"""

from __future__ import annotations  # allow forward references in type hints

from typing import List, Optional, Tuple

from tango.server import attribute, command

from ska_low_mccs import MccsAPIU
from ska_tango_base.commands import ResultCode


__all__ = ["DemoAPIU"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class DemoAPIU(MccsAPIU):
    """
    A version of the MccsDemo tango device with extra attributes...

    because Webjive.
    """

    def init_device(self: DemoAPIU) -> None:
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo APIU.
        """
        super().init_device()
        self.logger.warn("I am a DEMO APIU!")

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna1(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn on power to antenna 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(1)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna2(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn on power to antenna 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(2)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna3(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn on power to antenna 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(3)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna4(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn on power to antenna 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(4)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna1(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn off power to antenna 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(1)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna2(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn off power to antenna 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(2)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna3(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn off power to antenna 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(3)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna4(self: DemoAPIU) -> DevVarLongStringArrayType:
        """
        Turn off power to antenna 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(4)
        return ([return_code], [message])

    @attribute(dtype=bool, label="Is antenna 1 powered")
    def isAntenna1Powered(self: DemoAPIU) -> bool:
        """
        Return whether antenna 1 is powered.

        :return: whether antenna 1 is powered
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(1)

    @attribute(dtype=bool, label="Is antenna 2 powered")
    def isAntenna2Powered(self: DemoAPIU) -> bool:
        """
        Return whether antenna 2 is powered.

        :return: whether antenna 2 is powered
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(2)

    @attribute(dtype=bool, label="Is antenna 3 powered")
    def isAntenna3Powered(self: DemoAPIU) -> bool:
        """
        Return whether antenna 3 is powered.

        :return: whether antenna 3 is powered
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(3)

    @attribute(dtype=bool, label="Is antenna 4 powered")
    def isAntenna4Powered(self: DemoAPIU) -> bool:
        """
        Return whether antenna 4 is powered.

        :return: whether antenna 4 is powered
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(4)


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return DemoAPIU.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
