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
from ska.base import SKABaseDevice

# from .device import MccsDevice
import ska.low.mccs.release as release
from ska.base.commands import ResponseCommand, ResultCode


class MccsGroupDevice(SKABaseDevice):
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

    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Group Device

        """

        def do(self):
            """Initialises the attributes and properties of the MccsGroupDevice."""
            super().do()
            device = self.target
            device._member_states = (DevState.UNKNOWN,)
            device._member_list = ("",)
            device._version_id = release.version
            device._build_state = release.get_release_info()
            return (ResultCode.OK, "Init command succeeded")

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
    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("AddMember", self.AddMemberCommand(*args))
        self.register_command_object("RemoveMember", self.RemoveMemberCommand(*args))
        self.register_command_object("Run", self.RunCommand(*args))

    class AddMemberCommand(ResponseCommand):
        """
        Class for handling the AddMember command.
        """

        def do(self, argin):
            return (ResultCode.OK, "AddMember command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="The device name to register eg. sys/tg_test/1",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def AddMember(self, argin):
        """
        Registers this device as a member of this composite group

        :param argin: The device name to register eg. sys/tg_test/1
        :type argin: 'DevString'

        :return: (ResultCode, 'informational message')
        """
        handler = self.get_command_object("AddMember")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class RemoveMemberCommand(ResponseCommand):
        """
        Class for handling the RemoveMember command
        """

        def do(self, argin):
            return (ResultCode.OK, "RemoveMember command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="The name of the device to de-register",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def RemoveMember(self, argin):
        """
        De-registers a device as a memnber of this composite group

        :param argin: The name of the device to de-register
        :type argin: 'DevString'

        :return: (ResultCode, 'informational message')
        """
        handler = self.get_command_object("RemoveMember")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]

    class RunCommand(ResponseCommand):
        """
        Class for handling the Run command
        """

        def do(self, argin):
            return (ResultCode.OK, "Run command succeeded")

    @command(
        dtype_in="DevString",
        doc_in="The command to run",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def Run(self, argin):
        """
        A wrapper around running commands on a group proxy for this group of
        devices

        :param argin: The command to run
        :type argin: 'DevString'

        :return: (ResultCode, 'informational message')
        """
        handler = self.get_command_object("Run")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsGroupDevice module."""
    return MccsGroupDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()