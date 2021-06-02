# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a Demo APIU device, with extra interface features that support
testing and demonstrating the MCCS APIU device.
"""
from tango import DevState
from tango.server import attribute, command

from ska_low_mccs import MccsAPIU


__all__ = ["DemoAPIU"]


class DemoAPIU(MccsAPIU):
    """
    A version of the MccsDemo tango device with extra attributes...

    because Webjive.
    """

    def init_device(self):
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo APIU.
        """
        super().init_device()
        self.logger.warn("I am a DEMO APIU!")

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
    def PowerUpAntenna1(self):
        """
        Turn on power to antenna 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(1)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna2(self):
        """
        Turn on power to antenna 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(2)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna3(self):
        """
        Turn on power to antenna 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(3)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerUpAntenna4(self):
        """
        Turn on power to antenna 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerUpAntenna")
        (return_code, message) = handler(4)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna1(self):
        """
        Turn off power to antenna 1.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(1)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna2(self):
        """
        Turn off power to antenna 2.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(2)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna3(self):
        """
        Turn off power to antenna 3.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(3)
        return [[return_code], [message]]

    @command(dtype_out="DevVarLongStringArray")
    def PowerDownAntenna4(self):
        """
        Turn off power to antenna 4.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("PowerDownAntenna")
        (return_code, message) = handler(4)
        return [[return_code], [message]]

    @attribute(dtype=bool, label="Is antenna 1 powered")
    def isAntenna1Powered(self):
        """
        Return whether antenna 1 is powered.

        :return: whether antenna 1 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(1)

    @attribute(dtype=bool, label="Is antenna 2 powered")
    def isAntenna2Powered(self):
        """
        Return whether antenna 2 is powered.

        :return: whether antenna 2 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(2)

    @attribute(dtype=bool, label="Is antenna 3 powered")
    def isAntenna3Powered(self):
        """
        Return whether antenna 3 is powered.

        :return: whether antenna 3 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(3)

    @attribute(dtype=bool, label="Is antenna 4 powered")
    def isAntenna4Powered(self):
        """
        Return whether antenna 4 is powered.

        :return: whether antenna 4 is powered
        :rtype: bool
        """
        handler = self.get_command_object("IsAntennaOn")
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
    return DemoAPIU.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
