# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoSubrackDevice, with extra interface features that support
testing and demonstrating the MCCS Subrack device.
"""
from tango import DevState
from tango.server import attribute, command

from ska_low_mccs import MccsSubrack


__all__ = ["DemoSubrack"]


class DemoSubrack(MccsSubrack):
    """
    A version of the MccsSubrack tango device with extra attributes...

    because Webjive.
    """

    def init_device(self):
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo subrack.
        """
        super().init_device()
        self.logger.warn("I am a DEMO subrack!")

    @command()
    def DemoOff(self):
        """
        Put the Tile into DISABLE state (i.e. turn the TPM off).

        :todo: This is needed for demo purposes, just until we have
            resolved SP-1501.
        """
        if self.get_state() == DevState.ON:
            self.Off()
        self.Disable()

    @command()
    def DemoOn(self):
        """
        Put the tile into ON state (i.e. turn the TPM on).

        :todo: This is needed for demo purposes, just until we have
            resolved SP-1501.
        """
        self.Off()
        self.On()

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm1(self):
        """
        Turn on power to TPM 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(1)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm2(self):
        """
        Turn on power to TPM 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(2)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm3(self):
        """
        Turn on power to TPM 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(3)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOnTpm4(self):
        """
        Turn on power to TPM 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOnTpm")
        (return_code, message) = handler(4)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm1(self):
        """
        Turn off power to TPM 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(1)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm2(self):
        """
        Turn off power to TPM 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(2)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm3(self):
        """
        Turn off power to TPM 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(3)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerOffTpm4(self):
        """
        Turn off power to TPM 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerOffTpm")
        (return_code, message) = handler(4)
        return [[return_code], [message]]

    @attribute(dtype=bool, label="Is TPM 1 powered")
    def isTpm1Powered(self):
        """
        Return whether TPM 1 is powered.

        :return: whether TPM 1 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler(1)

    @attribute(dtype=bool, label="Is TPM 2 powered")
    def isTpm2Powered(self):
        """
        Return whether TPM 2 is powered.

        :return: whether TPM 2 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler(2)

    @attribute(dtype=bool, label="Is TPM 3 powered")
    def isTpm3Powered(self):
        """
        Return whether TPM 3 is powered.

        :return: whether TPM 3 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler(3)

    @attribute(dtype=bool, label="Is TPM 4 powered")
    def isTpm4Powered(self):
        """
        Return whether TPM 4 is powered.

        :return: whether TPM 4 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsTpmOn")
        return handler(4)


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Entry point for module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return DemoSubrack.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
