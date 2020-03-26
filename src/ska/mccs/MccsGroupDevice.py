# -*- coding: utf-8 -*-
#
# This file is part of the MccsGroupDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" Grouping of MCCS devices

"""
__all__ = ["MccsGroupDevice", "main"]

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command
from tango import DevState

# Additional import
from .MccsDevice import MccsDevice
from . import release


class MccsGroupDevice(MccsDevice):
    """

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsGroupDevice."""
        MccsDevice.init_device(self)
        self._member_states = (DevState.UNKNOWN,)
        self._member_list = ("",)
        self._version_id = release.version
        self._build_state = release.get_release_info()

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ----------
    # Attributes
    # ----------

    @attribute(
        dtype=("DevState",),
        max_dim_x=256,
        doc="An aggregated list of Tango states for each member in the group",
    )
    def memberStates(self):
        """Return the memberStates attribute."""
        return self._member_states

    @attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="A list of Tango addresses to devices comprising this group",
    )
    def memberList(self):
        """Return the memberList attribute."""
        return self._member_list

    # --------
    # Commands
    # --------

    @command(
        dtype_in="DevString",
        doc_in="The device name to register eg. sys/tg_test/1",  # force wrap
    )
    @DebugIt()
    def AddMember(self, argin):
        """
        Registers this device as a member of this composite group

        :param argin: 'DevString'
        The device name to register eg. sys/tg_test/1

        :return:None
        """
        pass

    @command(
        dtype_in="DevString", doc_in="The name of the device to de-register"
    )  # force wrap
    @DebugIt()
    def RemoveMember(self, argin):
        """
        De-registers a device as a memnber of this composite group

        :param argin: 'DevString'
        The name of the device to de-register

        :return:None
        """
        pass

    @command(dtype_in="DevString", doc_in="The command to run")
    @DebugIt()
    def RunCommand(self, argin):
        """
        A wrapper around running commands on a group proxy for this group of
        devices

        :param argin: 'DevString'
        The command to run

        :return:None
        """
        pass


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsGroupDevice module."""
    return MccsGroupDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
