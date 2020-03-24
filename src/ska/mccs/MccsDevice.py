# -*- coding: utf-8 -*-
#
# This file is part of the MccsDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" Mccs Base Device

A base class for all Mccs Devices
"""

__all__ = ["MccsDevice", "main"]

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
# PROTECTED REGION ID(MccsDevice.additionnal_import) ENABLED START #
from ska.base import SKABaseDevice

# PROTECTED REGION END #    //  MccsDevice.additionnal_import


class MccsDevice(SKABaseDevice):
    """
    A base class for all Mccs Devices

    **Properties:**

    - Device Property
    """

    # PROTECTED REGION ID(MccsDevice.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsDevice.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # Attributes
    # ----------

    isHardwareDevice = attribute(dtype="DevBoolean")

    diagMode = attribute(dtype="DevBoolean")

    calledUndefinedDevice = attribute(dtype="DevBoolean")

    calledDeadServer = attribute(dtype="DevBoolean")

    detectedDeadServer = attribute(dtype="DevBoolean")

    calledNonRunningDevice = attribute(dtype="DevBoolean")

    callTimeout = attribute(dtype="DevBoolean")

    callCommFailed = attribute(dtype="DevBoolean")

    invalidAsynId = attribute(dtype="DevBoolean")

    calledInexistentCalback = attribute(dtype="DevBoolean")

    requestIdMismatch = attribute(dtype="DevBoolean")

    expectedReplyNotReady = attribute(dtype="DevBoolean")

    experiencedSubscriptionFailure = attribute(dtype="DevBoolean")

    invalidEventId = attribute(dtype="DevBoolean")

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsDevice."""
        SKABaseDevice.init_device(self)
        # PROTECTED REGION ID(MccsDevice.init_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsDevice.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsDevice.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsDevice.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsDevice.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsDevice.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_isHardwareDevice(self):
        # PROTECTED REGION ID(MccsDevice.isHardwareDevice_read) ENABLED START #
        """Return the isHardwareDevice attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.isHardwareDevice_read

    def read_diagMode(self):
        # PROTECTED REGION ID(MccsDevice.diagMode_read) ENABLED START #
        """Return the diagMode attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.diagMode_read

    def read_calledUndefinedDevice(self):
        # PROTECTED REGION ID(MccsDevice.calledUndefinedDevice_read) ENABLED START #
        """Return the calledUndefinedDevice attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.calledUndefinedDevice_read

    def read_calledDeadServer(self):
        # PROTECTED REGION ID(MccsDevice.calledDeadServer_read) ENABLED START #
        """Return the calledDeadServer attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.calledDeadServer_read

    def read_detectedDeadServer(self):
        # PROTECTED REGION ID(MccsDevice.detectedDeadServer_read) ENABLED START #
        """Return the detectedDeadServer attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.detectedDeadServer_read

    def read_calledNonRunningDevice(self):
        # PROTECTED REGION ID(MccsDevice.calledNonRunningDevice_read) ENABLED START #
        """Return the calledNonRunningDevice attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.calledNonRunningDevice_read

    def read_callTimeout(self):
        # PROTECTED REGION ID(MccsDevice.callTimeout_read) ENABLED START #
        """Return the callTimeout attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.callTimeout_read

    def read_callCommFailed(self):
        # PROTECTED REGION ID(MccsDevice.callCommFailed_read) ENABLED START #
        """Return the callCommFailed attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.callCommFailed_read

    def read_invalidAsynId(self):
        # PROTECTED REGION ID(MccsDevice.invalidAsynId_read) ENABLED START #
        """Return the invalidAsynId attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.invalidAsynId_read

    def read_calledInexistentCalback(self):
        # PROTECTED REGION ID(MccsDevice.calledInexistentCalback_read) ENABLED START #
        """Return the calledInexistentCalback attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.calledInexistentCalback_read

    def read_requestIdMismatch(self):
        # PROTECTED REGION ID(MccsDevice.requestIdMismatch_read) ENABLED START #
        """Return the requestIdMismatch attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.requestIdMismatch_read

    def read_expectedReplyNotReady(self):
        # PROTECTED REGION ID(MccsDevice.expectedReplyNotReady_read) ENABLED START #
        """Return the expectedReplyNotReady attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.expectedReplyNotReady_read

    def read_experiencedSubscriptionFailure(self):
        # PROTECTED REGION ID(MccsDevice.experiencedSubscriptionFailure_read) ENABLED START #
        """Return the experiencedSubscriptionFailure attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.experiencedSubscriptionFailure_read

    def read_invalidEventId(self):
        # PROTECTED REGION ID(MccsDevice.invalidEventId_read) ENABLED START #
        """Return the invalidEventId attribute."""
        return False
        # PROTECTED REGION END #    //  MccsDevice.invalidEventId_read

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def ExceptionCallback(self):
        # PROTECTED REGION ID(MccsDevice.ExceptionCallback) ENABLED START #
        """

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsDevice.ExceptionCallback

    @command()
    @DebugIt()
    def DefaultAlarmOnCallback(self):
        # PROTECTED REGION ID(MccsDevice.DefaultAlarmOnCallback) ENABLED START #
        """

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsDevice.DefaultAlarmOnCallback

    @command()
    @DebugIt()
    def DefaultAlarmOffCallback(self):
        # PROTECTED REGION ID(MccsDevice.DefaultAlarmOffCallback) ENABLED START #
        """

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsDevice.DefaultAlarmOffCallback

    @command()
    @DebugIt()
    def GetFullReport(self):
        # PROTECTED REGION ID(MccsDevice.GetFullReport) ENABLED START #
        """

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsDevice.GetFullReport

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetCommandReport(self):
        # PROTECTED REGION ID(MccsDevice.GetCommandReport) ENABLED START #
        """

        :return:'DevVarStringArray'
        """
        return [""]
        # PROTECTED REGION END #    //  MccsDevice.GetCommandReport

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetAttributeReport(self):
        # PROTECTED REGION ID(MccsDevice.GetAttributeReport) ENABLED START #
        """

        :return:'DevVarStringArray'
        """
        return [""]
        # PROTECTED REGION END #    //  MccsDevice.GetAttributeReport

    @command(dtype_in="DevString")
    @DebugIt()
    def ConstructDeviceProxyAddress(self, argin):
        # PROTECTED REGION ID(MccsDevice.ConstructDeviceProxyAddress) ENABLED START #
        """

        :param argin: 'DevString'

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  MccsDevice.ConstructDeviceProxyAddress


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsDevice module."""
    # PROTECTED REGION ID(MccsDevice.main) ENABLED START #
    return run((MccsDevice,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsDevice.main


if __name__ == "__main__":
    main()
