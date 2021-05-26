# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module contains the SKA Low MCCS Controller device prototype.
"""

from __future__ import annotations  # allow forward references in type hints

import json
import logging
import threading
from typing import List, Tuple

# PyTango imports
from tango import DebugIt, DevState, EnsureOmniThread, SerialModel, Util
from tango.server import attribute, command, device_property

# Additional import
from ska_tango_base import DeviceStateModel, SKAMaster, SKABaseDevice
from ska_tango_base.control_model import HealthState
from ska_tango_base.commands import ResponseCommand, ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.pool import DevicePool, DevicePoolSequence
import ska_low_mccs.release as release
from ska_low_mccs.utils import call_with_json, tango_raise
from ska_low_mccs.events import EventManager
from ska_low_mccs.health import HealthModel, HealthMonitor
from ska_low_mccs.resource import ResourceManager
from ska_low_mccs.message_queue import MessageQueue

__all__ = ["MccsController", "ControllerResourceManager", "main"]


class ControllerResourceManager(ResourceManager):
    """
    This class implements a resource manger for the MCCS controller
    device.

    Initialize with a list of FQDNs of devices to be managed. The
    ResourceManager holds the FQDN and the (1-based) ID of the device
    that owns each managed device.
    """

    def __init__(
        self: ControllerResourceManager,
        health_monitor: HealthMonitor,
        manager_name: str,
        station_fqdns: List[str],
        logger: logging.Logger,
    ) -> None:
        """
        Initialise the conroller resource manager.

        :param health_monitor: Provides for monitoring of health states
        :param manager_name: Name for this manager (imformation only)
        :param station_fqdns: the FQDNs of the stations that this controller
            device manages
        :param logger: the logger to be used by the object under test
        """
        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
        super().__init__(health_monitor, manager_name, stations, logger)

    def assign(
        self: ControllerResourceManager, station_fqdns: List[str], subarray_id: int
    ) -> None:
        """
        Assign stations to a subarray device.

        :param station_fqdns: list of station device FQDNs to assign
        :param subarray_id: ID of the subarray to which the stations
            should be assigned
        """
        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
        super().assign(stations, subarray_id)


class MccsControllerQueue(MessageQueue):
    """
    A concrete implementation of a message queue specific to
    MccsController.
    """

    def _notify_listener(
        self: MccsControllerQueue,
        result_code: ResultCode,
        message_uid: str,
        status: str,
    ) -> None:
        """
        Concrete implementation that can notify specific listeners.

        :param result_code: Result code of the command being executed
        :param message_uid: The message uid that needs a push notification
        :param status: Status message
        """
        device = self._target
        device._command_result["result_code"] = result_code
        device._command_result["message_uid"] = message_uid
        device._command_result["status"] = status
        json_results = json.dumps(device._command_result)
        device.push_change_event("commandResult", json_results)


class MccsController(SKAMaster):
    """
    MccsController TANGO device class for the MCCS prototype.

    This is a subclass of :py:class:`ska_tango_base.SKAMaster`.

    **Properties:**

    - Device Property
        MccsSubarrays
            - The FQDNs of the Mccs sub-arrays
            - Type: list(str)
        MccsStations
            - List of MCCS station  TANGO Device names
            - Type: list(str)
        MccsStationBeams
            - List of MCCS station beam TANGO Device names
            - Type: list(str)
        MccsSubarrayBeams
            - List of MCCS subarray beam TANGO Device names
            - Type: list(str)
        MccsTiles
            - List of MCCS Tile TANGO Device names.
            - Type: list(str)
        MccsAntenna
            - List of MCCS Antenna TANGO Device names
            - Type: list(str)
    """

    # -----------------
    # Device Properties
    # -----------------

    MccsSubarrays = device_property(dtype="DevVarStringArray", default_value=[])
    MccsSubracks = device_property(dtype="DevVarStringArray", default_value=[])
    MccsStations = device_property(dtype="DevVarStringArray", default_value=[])
    MccsSubarrayBeams = device_property(dtype="DevVarStringArray", default_value=[])

    # ---------------
    # General methods
    # ---------------
    def init_device(self: MccsController) -> None:
        """
        Initialise the device; overridden here to change the Tango
        serialisation model.
        """
        util = Util.instance()
        util.set_serial_model(SerialModel.NO_SYNC)
        super().init_device()

    def init_command_objects(self: MccsController) -> None:
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("Operate", self.OperateCommand(*args))
        self.register_command_object("Maintenance", self.MaintenanceCommand(*args))

        for (command_name, command_object) in [
            ("Disable", self.DisableCommand),
            ("StandbyLow", self.StandbyLowCommand),
            ("StandbyFull", self.StandbyFullCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(self.device_pool, self.state_model, self.logger),
            )

        for (command_name, command_object) in [
            ("Startup", self.StartupCommand),
            ("On", self.OnCommand),
            ("OnCallback", self.OnCallbackCommand),
            ("Off", self.OffCommand),
        ]:
            self.register_command_object(
                command_name, command_object(self, self.state_model, self.logger)
            )

    class InitCommand(SKAMaster.InitCommand):
        """
        A class for :py:class:`~.MccsController`'s Init command.

        The
        :py:meth:`~.MccsController.InitCommand.do` method below is
        called during :py:class:`~.MccsController`'s initialisation.
        """

        def __init__(
            self: MccsController.InitCommand,
            target: object,
            state_model: DeviceStateModel,
            logger: logging.Logger = None,
        ) -> None:
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False
            self._message_queue = None
            self._qdebuglock = threading.Lock()

        def do(self: MccsController.InitCommand) -> Tuple[ResultCode, str]:
            """
            Initialises the attributes and properties of the
            `MccsController`. State is managed under the hood; the basic
            sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            super().do()

            device = self.target
            device._heart_beat = 0
            device._command_result = {
                "result_code": ResultCode.UNKNOWN,
                "message_uid": "",
                "status": "",
            }
            device._progress = 0
            device.queue_debug = ""
            device._assigned_resources = ""
            device._build_state = release.get_release_info()
            device._version_id = release.version
            device.set_change_event("commandResult", True, False)
            device.set_change_event("commandProgress", True, False)
            device.set_change_event("assignedResources", True, False)

            device._subarray_fqdns = list(device.MccsSubarrays)
            device._subarray_enabled = [False] * len(device.MccsSubarrays)

            device._subrack_fqdns = list(device.MccsSubracks)
            device._station_fqdns = list(device.MccsStations)

            subrack_pool = DevicePool(device._subrack_fqdns, self.logger, connect=False)
            station_pool = DevicePool(device._station_fqdns, self.logger, connect=False)

            device.device_pool = DevicePoolSequence(
                [subrack_pool, station_pool], self.logger, connect=False
            )

            # Start the Message queue for this device
            device._message_queue = MccsControllerQueue(
                target=device, lock=self._qdebuglock, logger=self.logger
            )
            device._message_queue.start()

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(
            self: MccsController.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_device_pool(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_health_monitoring(
                    device, device._subrack_fqdns + device._station_fqdns
                )
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_resource_management(device, device._station_fqdns)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()

        def _initialise_device_pool(
            self: MccsController.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Initialise the device pool for this device.

            :param device: the device for which power management is
                being initialised
            """
            device.device_pool.connect()

        def _initialise_health_monitoring(
            self: MccsController.InitCommand, device: SKABaseDevice, fqdns: List[str]
        ) -> None:
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :param fqdns: the fqdns of subservient devices for which
                this device monitors health
            """
            device.event_manager = EventManager(self.logger, fqdns)

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                None, fqdns, device.event_manager, device.health_changed
            )

        def _initialise_resource_management(
            self: MccsController.InitCommand, device: SKABaseDevice, fqdns: List[str]
        ) -> None:
            """
            Initialise resource management for this device.

            :param device: the device for which resource management is
                being initialised
            :param fqdns: the fqdns of subservient devices allocation of which
                is managed by this device
            """
            health_monitor = device.health_model._health_monitor

            # Instantiate a resource manager for the Stations
            device._stations_manager = ControllerResourceManager(
                health_monitor, "StationsManager", fqdns, self.logger
            )
            resource_args = (device, device.state_model, device.logger)
            device.register_command_object(
                "Allocate", device.AllocateCommand(*resource_args)
            )
            device.register_command_object(
                "Release", device.ReleaseCommand(*resource_args)
            )
            device.register_command_object(
                "Restart", device.RestartCommand(*resource_args)
            )

        def interrupt(self: MccsController.InitCommand) -> bool:
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

        def succeeded(self: MccsController.InitCommand) -> None:
            """
            Hook called when the initialisation thread finishes
            successfully.
            """
            self.state_model.perform_action("init_succeeded_disable")

    def always_executed_hook(self: MccsController) -> None:
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self: MccsController) -> None:
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsController.InitCommand.do` method of the nested
        :py:class:`~.MccsController.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsController.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        if self._message_queue.is_alive():
            self._message_queue.terminate_thread()
            self._message_queue.join()

    # ----------
    # Attributes
    # ----------
    def health_changed(self: MccsController, health: HealthState) -> None:
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevString")
    def commandResult(self: MccsController) -> ResultCode:
        """
        Return the _command_result attributes.

        :return: JSON encoded _command_results attributes map
        """
        json_results = json.dumps(self._command_result)
        return json_results

    @attribute(dtype="DevString")
    def aPoolStats(self: MccsController) -> str:
        """
        Return the aPoolStats attribute.

        :return: aPoolStats attribute
        """
        return self.device_pool.pool_stats()

    @attribute(dtype="DevString")
    def aQueueDebug(self: MccsController) -> str:
        """
        Return the queueDebug attribute.

        :return: queueDebug attribute
        """
        return self.queue_debug

    @aQueueDebug.write
    def aQueueDebug(self: MccsController, debug_string: str) -> None:
        """
        Update the queue debug attribute.

        :param debug_string: the new debug string for this attribute
        """
        self.queue_debug = debug_string

    @attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
    )
    def commandProgress(self: MccsController) -> int:
        """
        Return the commandProgress attribute value.

        :return: command progress as a percentage
        """
        return self._progress

    @attribute(dtype="DevULong")
    def aHeartBeat(self: MccsController) -> int:
        """
        Return the Heartbeat attribute value.

        :return: heart beat as a percentage
        """
        return self._heart_beat

    @attribute(dtype="DevUShort", unit="s")
    def commandDelayExpected(self: MccsController) -> int:

        """
        Return the commandDelayExpected attribute.

        :return: number of seconds it is expected to take to complete the command
        """
        return 0

    @attribute(dtype="DevString")
    def assignedResources(self: MccsController) -> str:
        """
        Return the assigned resources attribute.

        :return: assignedResources attribute
        """
        return self._assigned_resources

    def notify_listener(
        self: MccsControllerQueue,
        result_code: ResultCode,
        message_uid: str,
        status: str,
    ) -> None:
        """
        Thin wrapper around the message queue's notify listener method.

        :param result_code: Result code of the command being executed
        :param message_uid: The message uid that needs a push notification
        :param status: Status message
        """
        self._message_queue._notify_listener(result_code, message_uid, status)

    # --------
    # Commands
    # --------
    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Startup(self: MccsController) -> Tuple[ResultCode, [str, str]]:
        """
        Start up the MCCS subsystem.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        if self._command_result.get("result_code") in [
            ResultCode.STARTED,
            ResultCode.QUEUED,
        ]:
            return [
                [ResultCode.FAILED],
                ["A controller command is already in progress", None],
            ]
        else:
            self.notify_listener(ResultCode.UNKNOWN, "", "")
            self.logger.debug("send_message(Startup)")
            (result_code, message_uid, status) = self._message_queue.send_message(
                command="Startup", notifications=True
            )
            return [[result_code], [status, message_uid]]

    class StartupCommand(ResponseCommand):
        """
        Class for handling the Startup command.
        """

        SUCCEEDED_MESSAGE = "Startup command completed OK"
        FAILED_OFF_MESSAGE = "Startup command failed: Off"
        FAILED_ON_MESSAGE = "Startup command failed: On"

        def do(
            self: MccsController.StartupCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.Startup` command.

            :param argin: Messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            # TODO: For now, we need to get our devices to OFF state
            # (the highest state of device readiness for a device that
            # isn't actually on) before we can put them into ON state.
            # This is a counterintuitive mess that will be fixed in
            # SP-1501. Meanwhile, Startup() is implemented to turn all
            # devices OFF (which will actually cause all the hardware to
            # come on), and then turn them ON.
            device = self.target
            device_pool = device.device_pool

            message_uid = device._command_result.get("message_uid")
            if device_pool.off():
                self.state_model.perform_action("off_succeeded")
            else:
                self.state_model.perform_action("off_failed")
                device.notify_listener(
                    ResultCode.FAILED, message_uid, self.FAILED_OFF_MESSAGE
                )
                return (ResultCode.FAILED, message_uid + "," + self.FAILED_OFF_MESSAGE)

            if device_pool.on():
                self.state_model.perform_action("on_succeeded")
                device.notify_listener(
                    ResultCode.OK, message_uid, self.SUCCEEDED_MESSAGE
                )
                return (ResultCode.OK, message_uid + "," + self.SUCCEEDED_MESSAGE)
            else:
                self.state_model.perform_action("on_failed")
                device.notify_listener(
                    ResultCode.FAILED, message_uid, self.FAILED_ON_MESSAGE
                )
                return (ResultCode.FAILED, message_uid + "," + self.FAILED_ON_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def On(self: MccsController) -> Tuple[ResultCode, [str, str]]:
        """
        Send a message to turn the controller on.

        Method returns as soon as the message has been enqueued.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        if self._command_result.get("result_code") in [
            ResultCode.STARTED,
            ResultCode.QUEUED,
        ]:
            return [
                [ResultCode.FAILED],
                ["A controller command is already in progress", None],
            ]
        else:
            self.notify_listener(ResultCode.UNKNOWN, "", "")
            self.logger.debug("send_message(On)")
            (result_code, message_uid, status) = self._message_queue.send_message(
                command="On", notifications=True
            )
            return [[result_code], [status, message_uid]]

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On command.
        """

        QUEUED_MESSAGE = "Controller On command queued"
        FAILED_MESSAGE = "Controller On command failed"

        def do(self: MccsController.OnCommand, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.On` command.

            :param argin: JSON encoded messaging system and command arguments
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device = self.target
            device_pool = device.device_pool

            message_uid = device._command_result.get("message_uid")
            if device_pool.invoke_command_with_callback(
                command_name="On", fqdn=device.get_name(), callback="OnCallback"
            ):
                return (ResultCode.OK, message_uid + "," + self.QUEUED_MESSAGE)
            else:
                self.logger.error(message_uid + "," + self.FAILED_MESSAGE)
                device.notify_listener(
                    ResultCode.FAILED, message_uid, self.FAILED_MESSAGE
                )
                # This needs to be successful or it drives the state machine into FAULT
                return (ResultCode.OK, message_uid + "," + self.FAILED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def OnCallback(self: MccsController, argin: str) -> Tuple[ResultCode, [str, str]]:
        """
        On callback method.

        :param argin: Argument containing JSON encoded command message and result
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, [str, str])
        """
        (result_code, message_uid, status) = self._message_queue.send_message(
            command="OnCallback", json_args=argin
        )
        return [[result_code], [status, message_uid]]

    class OnCallbackCommand(ResponseCommand):
        """
        Class for handling the On Callback command.
        """

        SUCCESSFUL_MESSAGE = "On command completed successfully"

        def do(
            self: MccsController.OnCallbackCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.OnCallback` command.

            :param argin: Argument containing JSON encoded command message and result
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            device_pool = device.device_pool
            device.logger.debug("Controller Callback called")

            message_uid = device._command_result.get("message_uid")
            # Defer callback to our pool device
            (command_complete, result_code, status) = device_pool.callback(argin)
            if command_complete:
                device.logger.debug(
                    f"OnCallback({result_code.name}:{message_uid}:{self.SUCCESSFUL_MESSAGE})"
                )
                device.notify_listener(
                    result_code, message_uid, self.SUCCESSFUL_MESSAGE
                )
                return (result_code, message_uid + "," + self.SUCCESSFUL_MESSAGE)
            else:
                return (ResultCode.STARTED, message_uid + "," + status)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Disable(self: MccsController) -> Tuple[ResultCode, str]:
        """
        Disable the controller.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        command = self.get_command_object("Disable")
        (result_code, status) = command()
        self.notify_listener(result_code, "", status)
        return [[result_code], [status]]

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable command.
        """

        SUCCEEDED_MESSAGE = "Disable command completed OK"
        FAILED_MESSAGE = "Disable command failed"

        def do(self: MccsController.DisableCommand) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device_pool = self.target

            if device_pool.disable():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Off(self: MccsController) -> Tuple[ResultCode, str]:
        """
        Turn the controller off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        command = self.get_command_object("Off")
        (result_code, status) = command()
        self.notify_listener(result_code, "", status)
        return [[result_code], [status]]

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off command.
        """

        SUCCEEDED_MESSAGE = "Off command completed OK"
        FAILED_MESSAGE = "Off command failed"

        def do(self: MccsController.OffCommand) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device = self.target
            device_pool = device.device_pool
            if device_pool.off():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class StandbyLowCommand(ResponseCommand):
        """
        Class for handling the StandbyLow command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        SUCCEEDED_MESSAGE = "StandbyLow command completed OK"
        FAILED_MESSAGE = "StandbyLow command failed"

        def do(self: MccsController.StandbyLowCommand) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.StandbyLow` command.

            :todo: For now, StandbyLow and StandbyHigh simply implement
                a general "standby".

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def StandbyLow(self: MccsController) -> Tuple[ResultCode, str]:
        """
        StandbyLow Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StandbyLow")
        (result_code, status) = handler()
        return [[result_code], [status]]

    class StandbyFullCommand(ResponseCommand):
        """
        Class for handling the StandbyFull command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        SUCCEEDED_MESSAGE = "StandbyFull command completed OK"
        FAILED_MESSAGE = "StandbyFull command failed"

        def do(self: MccsController.StandbyFullCommand) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.StandbyFull` command.

            :todo: For now, StandbyLow and StandbyHigh simply implement
                a general "standby".

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def StandbyFull(self: MccsController) -> Tuple[ResultCode, str]:
        """
        StandbyFull Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("StandbyFull")
        (result_code, status) = handler()
        return [[result_code], [status]]

    class OperateCommand(ResponseCommand):
        """
        Class for handling the Operate command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        SUCCEEDED_MESSAGE = "Operate command completed OK"

        def do(self: MccsController.OperateCommand) -> Tuple[ResultCode, str]:
            """
            Stateless hook for implementation of
            :py:meth:`.MccsController.Operate` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def check_allowed(self: MccsController.OperateCommand) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.OFF

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Operate(self: MccsController) -> Tuple[ResultCode, str]:
        """
        Transit to the OPERATE operating state, ready for signal
        processing.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Operate")
        (result_code, status) = handler()
        return [[result_code], [status]]

    def is_Operate_allowed(self: MccsController) -> bool:
        """
        Whether this command is allowed to be run in current device
        state.

        :return: True if this command is allowed to be run in
            current device state
        """
        handler = self.get_command_object("Operate")
        if not handler.check_allowed():
            tango_raise("Operate() is not allowed in current state")
        return True

    class ResetCommand(SKABaseDevice.ResetCommand):
        """
        Command class for the Reset() command.
        """

        def do(self: MccsController.ResetCommand) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Reset`
            command for this :py:class:`.MccsController` device.

            This implementation resets the MCCS system as a whole as an
            attempt to clear a FAULT state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Allocate(self: MccsController, argin: str) -> Tuple[ResultCode, str]:
        """
        Allocate a set of unallocated MCCS resources to a sub-array. The
        JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, station_ids, channels and subarray_beam_ids.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> proxy = tango.DeviceProxy("low-mccs/control/control")
        >>> proxy.Allocate(
                json.dumps(
                {
                    "interface": "https://schema.skatelescope.org/ska-low-mccs-assignresources/1.0",
                    "subarray_id": 1,
                    "subarray_beam_ids": [1],
                    "station_ids": [[1,2]],
                    "channel_blocks": [3],
                }
                )
            )
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        handler = self.get_command_object("Allocate")
        (result_code, status) = handler(argin)
        self.notify_listener(result_code, "", status)
        return [[result_code], [status]]

    class AllocateCommand(ResponseCommand):
        """
        Allocate a set of unallocated MCCS resources to a sub-array.

        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        subarray_beam.
        """

        FAILED_ALREADY_ALLOCATED_MESSAGE_PREFIX = (
            "Cannot allocate stations already allocated"
        )
        FAILED_TO_RELEASE_MESSAGE_PREFIX = "Failed to release resources from subarray"
        FAILED_TO_ENABLE_SUBARRAY_MESSAGE_PREFIX = "Cannot enable subarray"
        FAILED_TO_ALLOCATE_MESSAGE_PREFIX = "Failed to allocate resources to subarray"
        SUCCEEDED_MESSAGE = "Allocate command completed OK"
        SUCCEEDED_ENABLE_SUBARRAY_MESSAGE = "_enable_subarray was successful"

        def do(
            self: MccsController.AllocateCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the
            :py:meth:`.MccsController.Allocate` command

            Allocate a set of unallocated MCCS resources to a sub-array.
            The JSON argument specifies the overall sub-array composition in
            terms of which stations should be allocated to the specified Sub-Array.

            :param argin: JSON-formatted string
                {
                "interface": "https://schema.skatelescope.org/ska-low-mccs-assignresources/1.0",
                "subarray_id": int,
                "subarray_beam_ids": list[int],
                "station_ids": list[list[int]],
                "channel_blocks": list[int],
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            controllerdevice = self.target

            kwargs = json.loads(argin)
            subarray_id = kwargs.get("subarray_id")
            subarray_beam_ids = kwargs.get("subarray_beam_ids", list())
            station_ids = kwargs.get("station_ids", list())
            channel_blocks = kwargs.get("channel_blocks", list())
            controllerdevice = self.target
            assert 1 <= subarray_id <= len(controllerdevice._subarray_fqdns)

            # Generate station FQDNs from IDs
            all_stations = {}
            stations_per_beam = []
            for station_sub_ids in station_ids:
                station_sublist = []
                for station_id in station_sub_ids:
                    all_stations[station_id] = f"low-mccs/station/{station_id:03}"
                    station_sublist.append(f"low-mccs/station/{station_id:03}")
                stations_per_beam.append(station_sublist)
            station_fqdns = all_stations.values()
            subarray_beams = {}
            for subarray_beam_id in subarray_beam_ids:
                subarray_beams[
                    subarray_beam_id
                ] = f"low-mccs/subarraybeam/{subarray_beam_id:02}"
            subarray_beam_fqdns = sorted(subarray_beams.values())

            # Generate subarray FQDN from ID
            subarray_fqdn = controllerdevice._subarray_fqdns[subarray_id - 1]

            # Query stations resource manager
            # Are we allowed to make this allocation?
            # Which FQDNs need to be assigned and released?
            (
                alloc_allowed,
                stations_to_assign,
                stations_to_release,
            ) = controllerdevice._stations_manager.query_allocation(
                station_fqdns, subarray_id
            )
            if not alloc_allowed:
                # If manager returns False (not allowed) stations_to_release
                # gives the list of FQDNs blocking the allocation.
                aalist = ", ".join(stations_to_release)
                return (
                    ResultCode.FAILED,
                    f"{self.FAILED_ALREADY_ALLOCATED_MESSAGE_PREFIX}: {aalist}",
                )

            subarray_device = MccsDeviceProxy(subarray_fqdn, self.logger)

            # Manager gave this list of stations to release (no longer required)
            if stations_to_release is not None:
                (result_code, message) = call_with_json(
                    subarray_device.ReleaseResources, stations=stations_to_release
                )
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"{self.FAILED_TO_RELEASE_MESSAGE_PREFIX} {subarray_fqdn}:"
                        f"{message}",
                    )
                for station_fqdn in stations_to_release:
                    station = MccsDeviceProxy(station_fqdn, self.logger)
                    station.subarrayId = 0

                # Inform manager that we made the releases
                controllerdevice._stations_manager.release(stations_to_release)

            # Enable the subarray specified by the caller (if required)
            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                self._enable_subarray(subarray_id)

            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    f"{self.FAILED_TO_ENABLE_SUBARRAY_MESSAGE_PREFIX} {subarray_fqdn}",
                )

            # Manager gave this list of stations to assign
            if stations_to_assign is not None:
                (result_code, message) = call_with_json(
                    subarray_device.AssignResources,
                    stations=stations_per_beam,
                    subarray_beams=subarray_beam_fqdns,
                    channel_blocks=channel_blocks,
                )
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"{self.FAILED_TO_ALLOCATE_MESSAGE_PREFIX} {subarray_fqdn}:"
                        f"{message}",
                    )
                for fqdn in stations_to_assign:
                    device = MccsDeviceProxy(fqdn, self.logger)
                    device.subarrayId = subarray_id

                # Inform manager that we made the assignments
                controllerdevice._stations_manager.assign(
                    stations_to_assign, subarray_id
                )

            # assume all is OK for now ie send back what we received.
            controllerdevice._assigned_resources = json.dumps(
                {
                    "interface": "https://schema.skatelescope.org/ska-low-mccs-assignedresources/1.0",
                    "subarray_beam_ids": subarray_beam_ids,
                    "station_ids": station_ids,
                    "channel_blocks": channel_blocks,
                }
            )
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def check_allowed(self: MccsController.AllocateCommand) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.ON

        def _enable_subarray(
            self: MccsController.AllocateCommand, argin: int
        ) -> Tuple[ResultCode, str]:
            """
            Method to enable the specified subarray.

            :param argin: the subarray id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device = self.target
            subarray_id = argin

            if not (1 <= subarray_id <= len(device._subarray_fqdns)):
                return (
                    ResultCode.FAILED,
                    f"Subarray index {subarray_id} is out of range",
                )

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]

            if device._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    f"Subarray {subarray_fqdn} is already enabled",
                )

            subarray_device = MccsDeviceProxy(subarray_fqdn, self.logger)
            if not subarray_device.State() == DevState.ON:
                (result_code, message) = subarray_device.On()

                # TODO: handle ResultCode.STARTED
                if result_code == ResultCode.FAILED:
                    return (
                        result_code,
                        f"Failed to enable subarray {subarray_fqdn}: {message}",
                    )

            device._subarray_enabled[subarray_id - 1] = True
            return (ResultCode.OK, self.SUCCEEDED_ENABLE_SUBARRAY_MESSAGE)

    def is_Allocate_allowed(self: MccsController) -> bool:
        """
        Whether this command is allowed to be run in current device
        state.

        :return: True if this command is allowed to be run in
            current device state
        """
        handler = self.get_command_object("Allocate")
        if not handler.check_allowed():
            tango_raise("Allocate() is not allowed in current state")
        return True

    def _disable_subarray(
        self: MccsController, subarray_id: int, restart: bool
    ) -> Tuple[ResultCode, str]:
        """
        Method to disable the specified subarray.

        :param subarray_id: the subarray id
        :param restart: was this calls due to a restart command?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]
        subarray_device = MccsDeviceProxy(subarray_fqdn, self.logger)
        if restart:
            (result_code, message) = subarray_device.Restart()
            if result_code == ResultCode.FAILED:
                return (ResultCode.FAILED, f"Subarray restart failed: {message}")
        else:
            # try:
            (result_code, message) = subarray_device.ReleaseAllResources()
            # except DevFailed:
            # pass  # it probably has no resources to release
            if result_code == ResultCode.FAILED:
                return (
                    ResultCode.FAILED,
                    f"Subarray release all resources failed: {message}",
                )
        (result_code, message) = subarray_device.Off()
        if result_code == ResultCode.FAILED:
            return (ResultCode.FAILED, f"Subarray failed to turn off: {message}")
        self._subarray_enabled[subarray_id - 1] = False
        return (ResultCode.OK, "_disable_subarray was successful")

    def _release_resources(
        self: MccsController, argin: str, restart: bool = False
    ) -> Tuple[ResultCode, str]:
        """
        Method that releases subarray resources.

        :param argin: JON encoded subarray ID
        :param restart: release resources due to a restart command

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        kwargs = json.loads(argin)
        subarray_id = kwargs.get("subarray_id")
        if subarray_id is None or not (1 <= subarray_id <= len(self._subarray_fqdns)):
            return (
                ResultCode.FAILED,
                f"Subarray index '{subarray_id}' is out of range",
            )

        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]
        if not self._subarray_enabled[subarray_id - 1]:
            return (
                ResultCode.FAILED,
                f"Cannot release resources from disabled subarray {subarray_fqdn}",
            )

        # Query stations resouce manager for stations assigned to subarray
        fqdns = self._stations_manager.get_assigned_fqdns(subarray_id)
        # and clear the subarrayId in each
        for fqdn in fqdns:
            station = MccsDeviceProxy(fqdn, self.logger)
            station.subarrayId = 0
        # Finally release them from assignment in the manager
        self._stations_manager.release(fqdns)

        result = self._disable_subarray(subarray_id, restart)
        if result[0] is not ResultCode.OK:
            return (
                result[0],
                "_disable_subarray() release all or disable subarray failed",
            )
        return (ResultCode.OK, "Release resources completed OK")

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Restart(self: MccsController, argin: str) -> Tuple[ResultCode, str]:
        """
        Restart an MCCS Sub-Array.

        :param argin: JSON-formatted string containing an integer subarray_id.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        handler = self.get_command_object("Restart")
        (result_code, status) = handler(argin)
        self.notify_listener(result_code, "", status)
        return [[result_code], [status]]

    class RestartCommand(ResponseCommand):
        """
        Restart a sub-array's Capabilities and resources (stations),
        marking the resources and Capabilities as unassigned and idle.
        """

        def do(
            self: MccsController.RestartCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for the
            :py:meth:`.MccsController.Restart` command

            :param argin: JSON-formatted string containing an integer subarray_id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            controller = self.target
            return controller._release_resources(argin, restart=True)

        def check_allowed(self: MccsController.RestartCommand) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.ON

    def is_Restart_allowed(self: MccsController) -> bool:
        """
        Whether this command is allowed to be run in current device
        state.

        :return: True if this command is allowed to be run in
            current device state
        """
        handler = self.get_command_object("Restart")
        if not handler.check_allowed():
            tango_raise("Restart() is not allowed in current state")
        return True

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Release(self: MccsController, argin: str) -> Tuple[ResultCode, str]:
        """
        Release resources from an MCCS Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag and array resources.
            {
            "interface": "https://schema.skatelescope.org/ska-low-tmc-releaseresources/1.0",
            "subarray_id": 1,
            "release_all": true
            }

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        handler = self.get_command_object("Release")
        (result_code, status) = handler(argin)
        self.notify_listener(result_code, "", status)
        return [[result_code], [status]]

    class ReleaseCommand(ResponseCommand):
        """
        Release a sub-array's Capabilities and resources (stations),
        marking the resources and Capabilities as unassigned and idle.
        """

        def do(
            self: MccsController.ReleaseCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for the
            :py:meth:`.MccsController.Release` command

            :param argin: JSON-formatted string containing an integer
                subarray_id, a release all flag and array resources (TBD).

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            controller = self.target
            return controller._release_resources(argin)

        def check_allowed(self: MccsController.ReleaseCommand) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.ON

    def is_Release_allowed(self: MccsController) -> bool:
        """
        Whether this command is allowed to be run in current device
        state.

        :return: True if this command is allowed to be run in
            current device state
        """
        handler = self.get_command_object("Release")
        if not handler.check_allowed():
            tango_raise("Release() is not allowed in current state")
        return True

    class MaintenanceCommand(ResponseCommand):
        """
        Class for handling the
        :py:meth:`.MccsController.Maintenance` command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        SUCCEEDED_MESSAGE = "Maintenance command completed OK"

        def do(self: MccsController.MaintenanceCommand) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for handling the
            :py:meth:`.MccsController.Maintenance` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Maintenance(self: MccsController) -> Tuple[ResultCode, str]:
        """
        Transition the MCCS to a MAINTENANCE state.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Maintenance")
        (result_code, status) = handler()
        return [[result_code], [status]]


# ----------
# Run server
# ----------


def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsController.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
