# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoControllerDevice.

DemoControllerDevice extents MccsController with extra interface
features that support testing and demonstrating the MCCS Controller
device.
"""

from __future__ import annotations  # allow forward references in type hints

from tango import DevState
from tango.server import command

from ska_low_mccs import MccsController


__all__ = ["DemoController"]


class DemoController(MccsController):
    """A version of the MccsController tango device with testing/demo functionality."""

    def init_device(self: DemoController) -> None:
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warn("I am a DEMO controller!")

    @command()
    def DemoOff(self: DemoController) -> None:
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
def main(*args: tuple, **kwargs: dict) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return DemoController.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
