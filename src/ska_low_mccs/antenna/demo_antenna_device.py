# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoAntennaDevice.

DemoAntennaDevice extends MccsAntenna with extra interface features that
support testing and demonstrating the MCCS Antenna device.
"""

from __future__ import annotations  # allow forward references in type hints

__all__ = ["DemoAntenna"]

from tango import DevState
from tango.server import command

from ska_low_mccs import MccsAntenna


class DemoAntenna(MccsAntenna):
    """A version of MccsAntenna tango device with extra testing/demo functionality."""

    def init_device(self: DemoAntenna) -> None:
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warn("I am a DEMO antenna!")

    @command()
    def DemoOff(self: DemoAntenna) -> None:
        """
        Put the Tile into DISABLE state (i.e. turn the TPM off).

        :todo: This is needed for demo purposes, just until we have
            resolved SP-1501.
        """
        if self.get_state() == DevState.ON:
            self.Off()
        self.Disable()

    @command()
    def DemoOn(self: DemoAntenna) -> None:
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
def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return DemoAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
