# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a DemoTileDevice, with extra interface features
that support testing and demonstrating the MCCS Tile device.
"""
from tango import DevState
from tango.server import command, Device

from ska.base.control_model import AdminMode, SimulationMode
from ska.low.mccs import MccsTile


__all__ = ["ConnectionFailableDevice"]


class ConnectionFailableDevice(Device):
    """
    A tango device mixin that adds a single simulate_connection_failure
    command.

    This can be used with any tango device that has a
    hardware_manager attribute that is an instance of
    :py:class:`~ska.low.mccs.hardware.SimulableHardwareManager`.
    """

    def is_SimulateConnectionFailure_allowed(self):
        """
        Return whether the SimulateConnectionFailure command is allowed
        to be called.

        :return: whether the SimulateConnectionFailure command is
            allowed to be called
        :rtype: bool
        """
        return self.hardware_manager.simulation_mode == SimulationMode.TRUE

    @command(dtype_in=bool)
    def SimulateConnectionFailure(self, is_fail):
        """
        Tells the simulate whether or not to simulate connection
        failure.

        :param is_fail: whether or not to simulate connection failure.
        :type is_fail: bool
        """
        self.hardware_manager.simulate_connection_failure(is_fail)


class DemoTile(MccsTile, ConnectionFailableDevice):
    """
    A version of the MccsTile tango device with extra functionality for
    testing/demos:

    * an additional command that can be used, when the device is in
      simulation mode, to tell the simulator to simulate connection
      failure

    * the ability to write adminMode as an int instead of as a
      HealthState, in order to support webjive
    """

    def init_device(self):
        """
        Tango hook for initialisation code.

        Overridden here to log the fact that this is a demo tile.
        """
        super().init_device()
        self.logger.warn("I am a DEMO tile!")

    # class InitCommand(MccsTile.InitCommand):
    #     def _initialise_power_management(self, device):
    #         super()._initialise_power_management(self, device)

    @command()
    def TakeOffline(self):
        """
        Disable the tile and put it into admin mode OFFLINE.

        Implemented this way because webjive.
        """
        if self.get_state() == DevState.ON:
            self.Off()
        self.Disable()
        self.write_adminMode(AdminMode.OFFLINE)

    @command()
    def PutOnline(self):
        """
        Put the tile into admin mode ONLINE, then enable it.

        Implemented this way because webjive.
        """
        self.write_adminMode(AdminMode.ONLINE)
        self.Off()
        self.On()

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
    return DemoTile.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
