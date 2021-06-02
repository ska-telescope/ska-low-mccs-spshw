# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoControllerDevice, with extra interface features that
support testing and demonstrating the MCCS Controller device.
"""
from tango import DevState
from tango.server import command

from ska_low_mccs import MccsController


__all__ = ["DemoController"]


class DemoController(MccsController):
    """
    A version of the MccsController tango device with extra functionality for
    testing/demos.
    """

    def init_device(self):
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warn("I am a DEMO controller!")

    @command()
    def DemoOff(self):
        """
        Put the Tile into DISABLE state (i.e. turn the TPM off).

        :todo: This is needed for demo purposes, just until we have
            resolved SP-1501.
        """
        if self.get_state() == DevState.FAULT:
            self.Reset()
        if self.get_state() == DevState.ON:
            self.Off()
        self.Disable()


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
    return DemoController.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
