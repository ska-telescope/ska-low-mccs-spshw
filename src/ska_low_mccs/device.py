# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module implements the MCCS Base Device, a base class for all MCCS
devices.
"""
__all__ = ["MccsDevice", "main"]

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska_tango_base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode

# Local imports
import ska_low_mccs.release as release


class MccsDevice(SKABaseDevice):
    """
    A base class for all Mccs Devices.

    This is a subclass of :py:class:`ska_tango_base.SKABaseDevice`.
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

        SUCCEEDED_MESSAGE = "Init command completed OK"

        def do(self):
            """
            Stateless hook for device initialisation: initialises the
            attributes and properties of the :py:class:`.MccsDevice`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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

            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    def init_command_objects(self):
        """
        Set up the handler objects for Commands.
        """
        super().init_command_objects()

        for (command_name, command_object) in [
            ("ExceptionCallback", self.ExceptionCallbackCommand),
            ("DefaultAlarmOffCallback", self.DefaultAlarmOffCallbackCommand),
            ("DefaultAlarmOnCallback", self.DefaultAlarmOnCallbackCommand),
            ("ConstructDeviceProxyAddress", self.ConstructDeviceProxyAddressCommand),
            ("GetFullReport", self.GetFullReportCommand),
            ("GetCommandReport", self.GetCommandReportCommand),
            ("GetAttributeReport", self.GetAttributeReportCommand),
        ]:
            self.register_command_object(
                command_name, command_object(self, self.state_model, self.logger)
            )

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsDevice.InitCommand.do` method of the nested
        :py:class:`~.MccsDevice.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~.MccsDevice.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """
        pass

    # --------------------------------
    # Attributes overriding base class
    # --------------------------------
    @attribute(dtype="DevString")
    def versionId(self):
        """
        The version id of this device.

        :return: the version_id of this device
        :rtype: str
        """
        return release.version

    @attribute(dtype="DevString")
    def buildState(self):
        """
        The build state of this device.

        :return: the build state of this device
        :rtype: str
        """
        return release.get_release_info()

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevBoolean")
    def isHardwareDevice(self):
        """
        Return whether this device manages hardware.

        :return: whether this device mamages hardware
        :rtype: bool
        """
        return self._is_hardware_device

    @attribute(dtype="DevBoolean")
    def diagMode(self):
        """
        Return the diagMode attribute.

        :todo: What does this mean?

        :return: the value of the diagMode attribute
        :rtype: bool
        """
        return self._diag_mode

    @attribute(dtype="DevBoolean")
    def calledUndefinedDevice(self):
        """
        Return a flag indicating whether this device has tried to call a
        device that is not defined in the device database.

        :return: whether this device has tried to call a device that is
            not defined in the device database
        :rtype: bool
        """
        return self._called_undefined_device

    @attribute(dtype="DevBoolean")
    def calledDeadServer(self):
        """
        Return a flag indicating whether this device has tried to call a
        dead server.

        :return: whether this device has tried to call a dead server
        :rtype: bool
        """
        return self._called_dead_server

    @attribute(dtype="DevBoolean")
    def detectedDeadServer(self):
        """
        Return a flag indicating whether this device has detected a dead
        server.

        :return: whether this device has detected a dead server
        :rtype: bool
        """
        return self._detected_dead_server

    @attribute(dtype="DevBoolean")
    def calledNonRunningDevice(self):
        """
        Return a flag indicating whether this device has tried to call a
        device that is not running.

        :return: whether this device has tried to call a device that is
            not running
        :rtype: bool
        """
        return self._called_non_running_device

    @attribute(dtype="DevBoolean")
    def callTimeout(self):
        """
        Return a flag indicating whether this device has experienced a
        call timeout.

        :return: whether this device has had a call timeout
        :rtype: bool
        """
        return self._call_timeout

    @attribute(dtype="DevBoolean")
    def callCommFailed(self):
        """
        Return a flag indicating whether this device has had a call fail
        due to communications failure.

        :return: whether this device has had a call fail due to
            communications failure
        :rtype: bool
        """
        return self._call_comm_failed

    @attribute(dtype="DevBoolean")
    def invalidAsynId(self):
        """
        Return a flag indicating whether this device has had a call fail
        due to an invalid "asyn" id.

        :todo: what is an "asyn" id?

        :return: whether this device has had a call fail due to an
            invalid asyn id
        :rtype: bool
        """
        return self._invalid_asyn_id

    @attribute(dtype="DevBoolean")
    def calledInexistentCallback(self):
        """
        Return a flag indicating whether this device has tried to call a
        nonexistent callback.

        :return: whether this device has tried to call a nonexistent
            callback
        :rtype: bool
        """
        return self._called_inexistent_callback

    @attribute(dtype="DevBoolean")
    def requestIdMismatch(self):
        """
        Return a flag indicating whether this device has experienced a
        request id mismatch.

        :return: whether this device has experienced a request id
            mismatch
        :rtype: bool
        """
        return self._request_id_mismatch

    @attribute(dtype="DevBoolean")
    def expectedReplyNotReady(self):
        """
        Return a flag indicating whether this device has experienced an
        expected reply not being ready.

        :return: whether this device has experienced an expected reply
            not being ready
        :rtype: bool
        """
        return self._expected_reply_not_ready

    @attribute(dtype="DevBoolean")
    def experiencedSubscriptionFailure(self):
        """
        Return a flag indicating whether this device has experienced a
        subscription failure.

        :return: whether this device has experienced a subscription
            failure
        :rtype: bool
        """
        return self._experienced_subscription_failure

    @attribute(dtype="DevBoolean")
    def invalidEventId(self):
        """
        Return a flag indicating whether this device has errored due to
        an invalid event id.

        :return: whether this device has errored due to an invalid event
            id
        :rtype: bool
        """
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

        SUCCEEDED_MESSAGE = "ExceptionCallback command completed OK"

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.ExceptionCallback`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command()
    @DebugIt()
    def ExceptionCallback(self):
        """
        ExceptionCallback Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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

        SUCCEEDED_MESSAGE = "DefaultAlarmOnCallback command completed OK"

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.DefaultAlarmOnCallback`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command()
    @DebugIt()
    def DefaultAlarmOnCallback(self):
        """
        DefaultAlarmOnCallback Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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

        SUCCEEDED_MESSAGE = "DefaultAlarmOffCallback command completed OK"

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.DefaultAlarmOffCallback`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command()
    @DebugIt()
    def DefaultAlarmOffCallback(self):
        """
        DefaultAlarmOffCallback Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.GetFullReport` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetFullReport(self):
        """
        GetFullReport Command.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("GetFullReport")
        return handler()

    class GetCommandReportCommand(BaseCommand):
        """
        Class for handling the GetCommandReport() command.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.GetCommandReport`
            command functionality.

            :return: a command report
            :rtype: list(str)
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetCommandReport(self):
        """
        GetCommandReport Command.

        :return: a command report
        :rtype: list(str)
        """
        handler = self.get_command_object("GetCommandReport")
        return handler()

    class GetAttributeReportCommand(BaseCommand):
        """
        Class for handling the GetAttributeReport() command.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.GetAttributeReport`
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return [""]

    @command(dtype_out="DevVarStringArray")
    @DebugIt()
    def GetAttributeReport(self):
        """
        GetAttributeReport Command.

        :return: an attribute report
        :rtype: list(str)
        """
        handler = self.get_command_object("GetAttributeReport")
        return handler()

    class ConstructDeviceProxyAddressCommand(ResponseCommand):
        """
        Class for handling the ConstructDeviceProxyAddress(argin)
        command.

        :todo: What does this command do? It sounds like it constructs
            an address, but if so it doesn't return it.
        """

        SUCCEEDED_MESSAGE = "ConstructDeviceProxyAddress command completed OK"

        def do(self, argin):
            """
            Stateless hook for implementation of
            :py:meth:`ska_low_mccs.device.MccsDevice.ConstructDeviceProxyAddress`
            command functionality.

            :param argin: TODO: what argument does this take
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def ConstructDeviceProxyAddress(self, argin):
        """
        ConstructDeviceProxyAddress Command.

        :param argin: 'DevString'

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("ConstructDeviceProxyAddress")
        (return_code, message) = handler(argin)
        return [[return_code], [message]]


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
    return MccsDevice.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()