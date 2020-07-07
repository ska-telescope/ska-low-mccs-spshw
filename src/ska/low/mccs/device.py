# -*- coding: utf-8 -*-
#
# This file is part of the MccsDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module implements the MCCS Base Device, a base class for all MCCS
devices
"""
__all__ = ["MccsDevice", "main"]

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKABaseDevice
from ska.base.commands import BaseCommand, ResponseCommand, ResultCode

# Local imports
import ska.low.mccs.release as release


class MccsDevice(SKABaseDevice):
    """
    A base class for all Mccs Devices
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKABaseDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Base
        Device. State is managed under the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off

        """
        def do(self):
            """
            Stateless hook for device initialisation: initialises the
            attributes and properties of the MccsDevice.
            """
            super().do()

            device = self.target
            device._is_hardware_device = False
            device._diag_mode = False
            device._called_undefined_device = False
            device._called_dead_server = False
            device._detected_dead_server = False
            device._called_non_running_device = False
            device._call_timeout = False
            device._call_comm_failed = False
            device._invalid_asyn_id = False
            device._called_inexistent_callback = False
            device._request_id_mismatch = False
            device._expected_reply_not_ready = False
            device._experienced_subscription_failure = False
            device._invalid_event_id = False

            device._version_id = release.version
            device._build_state = release.get_release_info()

            return (ResultCode.OK, "Init command succeeded")

    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object(
            "ExceptionCallback",
            self.ExceptionCallbackCommand(*args)
        )
        self.register_command_object(
            "DefaultAlarmOffCallback",
            self.DefaultAlarmOffCallbackCommand(*args)
        )
        self.register_command_object(
            "DefaultAlarmOnCallback",
            self.DefaultAlarmOnCallbackCommand(*args)
        )
        self.register_command_object(
            "ConstructDeviceProxyAddress",
            self.ConstructDeviceProxyAddressCommand(*args)
        )
        self.register_command_object(
            "GetFullReport",
            self.GetFullReportCommand(*args)
        )
        self.register_command_object(
            "GetCommandReport",
            self.GetCommandReportCommand(*args)
        )
        self.register_command_object(
            "GetAttributeReport",
            self.GetAttributeReportCommand(*args)
        )

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # --------------------------------
    # Attributes overriding base class
    # --------------------------------
    @attribute(dtype="DevString")
    def versionId(self):
        return release.version

    @attribute(dtype="DevString")
    def buildState(self):
        return release.get_release_info()

    # ----------
    # Attributes
    # ----------
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

    class ExceptionCallbackCommand(ResponseCommand):
        """
        Class for handling the ExceptionCallback command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """
        def do(self):
            """
            Stateless hook for implementation of ExceptionCallback()
            command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command()
    @DebugIt()
    def ExceptionCallback(self):
        """
        ExceptionCallback Command

        :todo: What does this command do?
        :return: None
        """
        handler = self.get_command_object("ExceptionCallback")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class DefaultAlarmOnCallbackCommand(ResponseCommand):
        """
        Class for handling the DefaultAlarmOnCallback command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """
        def do(self):
            """
            Stateless hook for implementation of
            DefaultAlarmOnCallback() command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command()
    @DebugIt()
    def DefaultAlarmOnCallback(self):
        """
        DefaultAlarmOnCallback Command

        :todo: What does this command do?
        :return: None
        """
        handler = self.get_command_object("DefaultAlarmOnCallback")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class DefaultAlarmOffCallbackCommand(ResponseCommand):
        """
        Class for handling the DefaultAlarmOffCallback command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """
        def do(self):
            """
            Stateless hook for implementation of
            DefaultAlarmOffCallback() command functionality.
            """
            return (ResultCode.OK, "Stub implementation, does nothing")

    @command()
    @DebugIt()
    def DefaultAlarmOffCallback(self):
        """
        DefaultAlarmOffCallback Command

        :todo: What does this command do?
        :return: None
        """
        handler = self.get_command_object("DefaultAlarmOffCallback")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class GetFullReportCommand(BaseCommand):
        """
        Class for handling the GetFullReport() command.
        """
        def do(self):
            """
            Stateless hook for implementation of GetFullReport()
            command functionality.
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetFullReport(self):
        """
        GetFullReport Command

        :return: None
        """
        handler = self.get_command_object("GetFullReport")
        return handler()

    class GetCommandReportCommand(BaseCommand):
        """
        Class for handling the GetCommandReport() command.
        """
        def do(self):
            """
            Stateless hook for implementation of GetCommandReport()
            command functionality.
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetCommandReport(self):
        """
        GetCommandReport Command

        :return: 'DevVarStringArray'
        """
        handler = self.get_command_object("GetCommandReport")
        return handler()

    class GetAttributeReportCommand(BaseCommand):
        """
        Class for handling the GetAttributeReport() command.
        """
        def do(self):
            """
            Stateless hook for implementation of GetAttributeReport()
            command functionality.
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetAttributeReport(self):
        """
        GetAttributeReport Command

        :return: 'DevVarStringArray'
        """
        handler = self.get_command_object("GetAttributeReport")
        return handler()

    class ConstructDeviceProxyAddressCommand(ResponseCommand):
        """
        Class for handling the ConstructDeviceProxyAddress() command.

        :todo: What does this command do? It sounds like it constructs
            an address, but if so it doesn't return it.
        """
        def do(self, argin):
            """
            Stateless hook for implementation of
            ConstructDeviceProxyAddress() command functionality.
            """
            return (ResultCode.OK, "Stub implementation, did nothing")

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    @DebugIt()
    def ConstructDeviceProxyAddress(self, argin):
        """
        ConstructDeviceProxyAddress Command

        :param argin: 'DevString'
        :return: None
        """
        handler = self.get_command_object("ConstructDeviceProxyAddress")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsDevice module."""
    return MccsDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
