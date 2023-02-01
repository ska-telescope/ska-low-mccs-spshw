#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module implements a DemoTileDevice.

DemoTileDevice extends TileDevice with extra interface features that
support testing and demonstrating the MCCS Tile device.
"""

from __future__ import annotations  # allow forward references in type hints

from tango.server import Device, command

from .tile_device import MccsTile

__all__ = ["DemoTile"]


class _FaultSimulatingDevice(Device):
    """
    A tango device mixin that adds a single simulateFault command.

    This can be used with any tango device that has a component manager
    attribute.
    """

    @command(dtype_in=bool)
    def SimulateFault(self: _FaultSimulatingDevice, is_faulty: bool) -> None:
        """
        Tells the device whether or not to simulate a fault.

        :param is_faulty: whether or not to simulate a fault
        """
        self.component_manager.update_component_fault(is_faulty)


class DemoTile(MccsTile, _FaultSimulatingDevice):
    """Version of the MccsTile tango device with extra methods for testing/demos."""

    def init_device(self: DemoTile) -> None:
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warning("I am a DEMO tile!")


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return DemoTile.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
