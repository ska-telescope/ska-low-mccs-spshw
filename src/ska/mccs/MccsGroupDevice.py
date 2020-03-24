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
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device, DeviceMeta
from tango.server import attribute, command
from tango.server import device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType, PipeWriteType

# Additional import
# PROTECTED REGION ID(MccsGroupDevice.additionnal_import) ENABLED START #
import MccsDevice

# PROTECTED REGION END #    //  MccsGroupDevice.additionnal_import


class MccsGroupDevice(MccsDevice):
    """

    **Properties:**

    - Device Property
    """

    # PROTECTED REGION ID(MccsGroupDevice.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsGroupDevice.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    memberStates = attribute(
        dtype=("DevState",),
        max_dim_x=256,
        doc="An aggregated list of Tango states for each member in the group",
    )

    memberList = attribute(
        dtype=("DevString",),
        max_dim_x=256,
        doc="A list of Tango addresses to devices comprising this group",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsGroupDevice."""
        MccsDevice.init_device(self)
        # PROTECTED REGION ID(MccsGroupDevice.init_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsGroupDevice.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsGroupDevice.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsGroupDevice.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsGroupDevice.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsGroupDevice.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_memberStates(self):
        # PROTECTED REGION ID(MccsGroupDevice.memberStates_read) ENABLED START #
        """Return the memberStates attribute."""
        return (PyTango.DevState.UNKNOWN,)
        # PROTECTED REGION END #    //  MccsGroupDevice.memberStates_read

    def read_memberList(self):
        # PROTECTED REGION ID(MccsGroupDevice.memberList_read) ENABLED START #
        """Return the memberList attribute."""
        return ("",)
        # PROTECTED REGION END #    //  MccsGroupDevice.memberList_read

    # --------
    # Commands
    # --------

    @command(
        dtype_in="DevString", doc_in="The device name to register eg. sys/tg_test/1"
    )
    @DebugIt()
    def AddMember(self, argin):
        # PROTECTED REGION ID(MccsGroupDevice.AddMember) ENABLED START #
        """
        Registers this device as a member of this composite group

        :param argin: 'DevString'
        The device name to register eg. sys/tg_test/1

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsGroupDevice.AddMember

    @command(dtype_in="DevString", doc_in="The name of the device to de-register")
    @DebugIt()
    def RemoveMember(self, argin):
        # PROTECTED REGION ID(MccsGroupDevice.RemoveMember) ENABLED START #
        """
        De-registers a device as a memnber of this composite group

        :param argin: 'DevString'
        The name of the device to de-register

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsGroupDevice.RemoveMember

    @command(dtype_in="DevString", doc_in="The command to run")
    @DebugIt()
    def RunCommand(self, argin):
        # PROTECTED REGION ID(MccsGroupDevice.RunCommand) ENABLED START #
        """
        A wrapper around running commands on a group proxy for this group of devices

        :param argin: 'DevString'
        The command to run

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsGroupDevice.RunCommand


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsGroupDevice module."""
    # PROTECTED REGION ID(MccsGroupDevice.main) ENABLED START #
    return MccsGroupDevice.run(args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsGroupDevice.main


if __name__ == "__main__":
    main()
