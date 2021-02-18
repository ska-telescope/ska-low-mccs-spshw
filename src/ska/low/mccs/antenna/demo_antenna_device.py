# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoAntennaDevice, with extra interface
features that support testing and demonstrating the MCCS Antenna device.
"""
from tango import DevState
from tango.server import command

from ska.low.mccs import MccsAntenna


__all__ = ["DemoAntenna"]


class DemoAntenna(MccsAntenna):
    """
    A version of the MccsAntenna tango device with extra functionality
    for testing/demos.
    """

    def init_device(self):
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warn("I am a DEMO antenna!")

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
    return DemoAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
