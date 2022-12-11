# type: ignore
# pylint: skip-file
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module implements a DemoSubrack Tango device.

DemoSubrack extends MccsSubrack with extra interface features that
support testing and demonstrating the MCCS Subrack device.
"""

from __future__ import annotations  # allow forward references in type hints

from typing import Optional

from ska_low_mccs_spshw import MccsSubrack
from ska_tango_base.commands import ResultCode
from tango.server import command

__all__ = ["DemoSubrack"]


DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]


class DemoSubrack(MccsSubrack):
    """
    A version of the MccsSubrack tango device with extra commands...

    because Webjive.
    """

    def init_device(self: DemoSubrack) -> None:
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo subrack.
        """
        super().init_device()
        self.logger.warning("I am a DEMO subrack!")

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm1(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn on power to TPM 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOnTpm")
        result_code, message = handler(1)
        return ([result_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm2(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn on power to TPM 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(2)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm3(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn on power to TPM 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(3)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm4(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn on power to TPM 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(4)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm1(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn off power to TPM 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(1)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm2(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn off power to TPM 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(2)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm3(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn off power to TPM 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(3)
        return ([return_code], [message])

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm4(self: DemoSubrack) -> DevVarLongStringArrayType:
        """
        Turn off power to TPM 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(4)
        return ([return_code], [message])


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
    return DemoSubrack.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
