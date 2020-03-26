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
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKABaseDevice

# local imports
from . import release


class MccsDevice(SKABaseDevice):
    """
    A base class for all Mccs Devices

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
        """Initialises the attributes and properties of the MccsDevice."""
        SKABaseDevice.init_device(self)
        self._is_hardware_device = False
        self._diag_mode = False
        self._called_undefined_device = False
        self._called_dead_server = False
        self._detected_dead_server = False
        self._called_non_running_device = False
        self._call_timeout = False
        self._call_comm_failed = False
        self._invalid_asyn_id = False
        self._called_inexistent_callback = False
        self._request_id_mismatch = False
        self._expected_reply_not_ready = False
        self._experienced_subscription_failure = False
        self._invalid_event_id = False

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
    @attribute(dtype="DevString")
    def versionId(self):
        return release.version

    @attribute(dtype="DevString")
    def buildState(self):
        build = ", ".join((release.name, release.version, release.description))
        print(build)
        return build

    @attribute(dtype="DevBoolean")
    def isHardwareDevice(self):
        """Return the isHardwareDevice attribute."""
        return self._is_hardware_device

    @attribute(dtype="DevBoolean")
    def diagMode(self):
        """Return the diagMode attribute."""
        return self._diag_mode

    @attribute(dtype="DevBoolean")
    def calledUndefinedDevice(self):
        """Return the calledUndefinedDevice attribute."""
        return self._called_undefined_device

    @attribute(dtype="DevBoolean")
    def calledDeadServer(self):
        """Return the calledDeadServer attribute."""
        return self._called_dead_server

    @attribute(dtype="DevBoolean")
    def detectedDeadServer(self):
        """Return the detectedDeadServer attribute."""
        return self._detected_dead_server

    @attribute(dtype="DevBoolean")
    def calledNonRunningDevice(self):
        """Return the calledNonRunningDevice attribute."""
        return self._called_non_running_device

    @attribute(dtype="DevBoolean")
    def callTimeout(self):
        """Return the callTimeout attribute."""
        return self._call_timeout

    @attribute(dtype="DevBoolean")
    def callCommFailed(self):
        """Return the callCommFailed attribute."""
        return self._call_comm_failed

    @attribute(dtype="DevBoolean")
    def invalidAsynId(self):
        """Return the invalidAsynId attribute."""
        return self._invalid_asyn_id

    @attribute(dtype="DevBoolean")
    def calledInexistentCallback(self):
        """Return the calledInexistentCallback attribute."""
        return self._called_inexistent_callback

    @attribute(dtype="DevBoolean")
    def requestIdMismatch(self):
        """Return the requestIdMismatch attribute."""
        return self._request_id_mismatch

    @attribute(dtype="DevBoolean")
    def expectedReplyNotReady(self):
        """Return the expectedReplyNotReady attribute."""
        return self._expected_reply_not_ready

    @attribute(dtype="DevBoolean")
    def experiencedSubscriptionFailure(self):
        """Return the experiencedSubscriptionFailure attribute."""
        return self._experienced_subscription_failure

    @attribute(dtype="DevBoolean")
    def invalidEventId(self):
        """Return the invalidEventId attribute."""
        return self._invalid_event_id

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def ExceptionCallback(self):
        """

        :return:None
        """
        pass

    @command()
    @DebugIt()
    def DefaultAlarmOnCallback(self):
        """

        :return:None
        """
        pass

    @command()
    @DebugIt()
    def DefaultAlarmOffCallback(self):
        """

        :return:None
        """
        pass

    @command()
    @DebugIt()
    def GetFullReport(self):
        """

        :return:None
        """
        pass

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetCommandReport(self):
        """

        :return:'DevVarStringArray'
        """
        return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetAttributeReport(self):
        """

        :return:'DevVarStringArray'
        """
        return [""]

    @command(dtype_in="DevString")
    @DebugIt()
    def ConstructDeviceProxyAddress(self, argin):
        """

        :param argin: 'DevString'

        :return:None
        """
        pass


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsDevice module."""
    return MccsDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
