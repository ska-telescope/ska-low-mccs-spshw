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

__all__ = ["MccsController", "ControllerResourceManager", "main"]

import json
import logging
import threading
from typing import List, Dict, Tuple


# PyTango imports
import tango
from tango import DebugIt, DevState, EnsureOmniThread
from tango.server import attribute, command, device_property

# Additional import
from ska_tango_base import SKAMaster, SKABaseDevice
from ska_tango_base.control_model import HealthState
from ska_tango_base.commands import ResponseCommand, ResultCode

from ska.low.mccs.pool import DevicePool, DevicePoolSequence
import ska.low.mccs.release as release
from ska.low.mccs.utils import call_with_json, tango_raise
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel, HealthMonitor
from ska.low.mccs.resource import ResourceManager


class ControllerResourceManager(ResourceManager):
    """
    This class implements a resource manger for the MCCS controller
    device.

    Initialize with a list of FQDNs of devices to be managed. The
    ResourceManager holds the FQDN and the (1-based) ID of the device
    that owns each managed device.
    """

    def __init__(
        self, health_monitor: HealthMonitor, manager_name: str, station_fqdns: List[str]
    ):
        """
        Initialise the conroller resource manager.

        :param health_monitor: Provides for monitoring of health states
        :param manager_name: Name for this manager (imformation only)
        :param station_fqdns: the FQDNs of the stations that this controller
            device manages
        """
        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
        super().__init__(health_monitor, manager_name, stations)

    def assign(self, station_fqdns: List[str], subarray_id: int):
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


class MccsController(SKAMaster):
    """
    MccsController TANGO device class for the MCCS prototype.

    This is a subclass of :py:class:`~ska_tango_base.SKAMaster`.

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

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        # TODO: Technical debt -- forced to register base class stuff rather than
        # calling super(), because On() and Off() are registered on a
        # thread, and we don't want the super() method clobbering them
        args = (self, self.state_model, self.logger)
        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
        )
        self.register_command_object("Operate", self.OperateCommand(*args))
        self.register_command_object("Maintenance", self.MaintenanceCommand(*args))

    class InitCommand(SKAMaster.InitCommand):
        """
        A class for :py:class:`~.MccsController`'s Init command.

        The
        :py:meth:`~.MccsController.InitCommand.do` method below is
        called during :py:class:`~.MccsController`'s initialisation.
        """

        def __init__(
            self,
            target: object,
            state_model: DeviceStateModel,
            logger: logging.Logger = None,
        ):
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self) -> Tuple[ResultCode, str]:
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
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            super().do()

            device = self.target
            device._command_result = None
            device._build_state = release.get_release_info()
            device._version_id = release.version
            device.set_change_event("commandResult", True, False)

            device._subarray_fqdns = list(device.MccsSubarrays)
            device._subarray_enabled = [False] * len(device.MccsSubarrays)

            device._subrack_fqdns = list(device.MccsSubracks)
            device._station_fqdns = list(device.MccsStations)

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device: SKABaseDevice):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_device_pool(
                    device, device._subrack_fqdns, device._station_fqdns
                )
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
            self,
            device: SKABaseDevice,
            subrack_fqdns: List[str],
            station_fqdns: List[str],
        ):
            """
            Initialise the device pool for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
            :param subrack_fqdns: the fqdns of subservient subracks.
            :param station_fqdns: the fqdns of subservient stations.
            """
            subrack_pool = DevicePool(subrack_fqdns, self.logger)
            station_pool = DevicePool(station_fqdns, self.logger)
            device.device_pool = DevicePoolSequence(
                [subrack_pool, station_pool], self.logger
            )

            args = (device.device_pool, device.state_model, self.logger)
            device.register_command_object("Disable", device.DisableCommand(*args))
            device.register_command_object(
                "StandbyLow", device.StandbyLowCommand(*args)
            )
            device.register_command_object(
                "StandbyFull", device.StandbyFullCommand(*args)
            )
            device.register_command_object("Off", device.OffCommand(*args))
            device.register_command_object("On", device.OnCommand(*args))
            device.register_command_object("Startup", device.StartupCommand(*args))

        def _initialise_health_monitoring(
            self, device: SKABaseDevice, fqdns: List[str]
        ):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
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
            self, device: SKABaseDevice, fqdns: List[str]
        ):
            """
            Initialise resource management for this device.

            :param device: the device for which resource management is
                being initialised
            :type device: :py:class:`~ska_tango_base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices allocation of which
                is managed by this device
            """
            health_monitor = device.health_model._health_monitor

            # Instantiate a resource manager for the Stations
            device._stations_manager = ControllerResourceManager(
                health_monitor, "StationsManager", fqdns
            )
            resource_args = (device, device.state_model, device.logger)
            device.register_command_object(
                "Allocate", device.AllocateCommand(*resource_args)
            )
            device.register_command_object(
                "Release", device.ReleaseCommand(*resource_args)
            )

        def interrupt(self) -> bool:
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

        def succeeded(self):
            """
            Hook called when the initialisation thread finishes
            successfully.
            """
            self.state_model.perform_action("init_succeeded_disable")

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsController.InitCommand.do` method of the nested
        :py:class:`~.MccsController.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsController.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        pass

    # ----------
    # Attributes
    # ----------
    def health_changed(self, health: HealthState):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevLong", format="%i", polling_period=1000)
    def commandResult(self) -> ResultCode:
        """
        Return the commandResult attribute.

        :return: commandResult attribute
        :rtype: :py:class:`~ska_tango_base.commands.ResultCode`
        """
        return self._command_result

    @attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        polling_period=3000,
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
    )
    def commandProgress(self) -> int:
        """
        Return the commandProgress attribute value.

        :return: command progress as a percentage
        """
        return 0

    @attribute(dtype="DevUShort", unit="s")
    def commandDelayExpected(self) -> int:

        """
        Return the commandDelayExpected attribute.

        :return: number of seconds it is expected to take to complete the command
        """
        return 0

    # --------
    # Commands
    # --------

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Startup(self) -> Tuple[ResultCode, str]:
        """
        Start up the MCCS subsystem.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("Startup")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class StartupCommand(ResponseCommand):
        """
        Class for handling the Startup command.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.Startup` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            # TODO: For now, we need to get our devices to OFF state
            # (the highest state of device readiness for a device that
            # isn't actually on) before we can put them into ON state.
            # This is a counterintuitive mess that will be fixed in
            # SP-1501. Meanwhile, Startup() is implemented to turn all
            # devices OFF (which will actually cause all the hardware to
            # come on), and then turn them ON.
            device_pool = self.target

            if device_pool.off():
                self.state_model.perform_action("off_succeeded")
            else:
                self.state_model.perform_action("off_failed")
                return (ResultCode.FAILED, "Startup command failed")

            if device_pool.on():
                self.state_model.perform_action("on_succeeded")
                return (ResultCode.OK, "Startup command completed OK")
            else:
                self.state_model.perform_action("on_failed")
                return (ResultCode.FAILED, "Startup command failed")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def On(self) -> Tuple[ResultCode, str]:
        """
        Turn the controller on.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("On")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On command.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.On` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.on():
                return (ResultCode.OK, "On command completed OK")
            else:
                return (ResultCode.FAILED, "On command failed")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Disable(self) -> Tuple[ResultCode, str]:
        """
        Disable the controller.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("Disable")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class DisableCommand(SKABaseDevice.DisableCommand):
        """
        Class for handling the Disable command.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.disable():
                return (ResultCode.OK, "Off command completed OK")
            else:
                return (ResultCode.FAILED, "Off command failed")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Off(self) -> Tuple[ResultCode, str]:
        """
        Turn the controller off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("Off")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off command.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.off():
                return (ResultCode.OK, "Off command completed OK")
            else:
                return (ResultCode.FAILED, "Off command failed")

    class StandbyLowCommand(ResponseCommand):
        """
        Class for handling the StandbyLow command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.StandbyLow` command.

            :todo: For now, StandbyLow and StandbyHigh simply implement
                a general "standby".

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, "StandbyLow command completed OK")
            else:
                return (ResultCode.FAILED, "StandbyLow command failed")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def StandbyLow(self) -> Tuple[ResultCode, str]:
        """
        StandbyLow Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StandbyLow")
        (result_code, message) = handler()
        return [[result_code], [message]]

    class StandbyFullCommand(ResponseCommand):
        """
        Class for handling the StandbyFull command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.StandbyFull` command.

            :todo: For now, StandbyLow and StandbyHigh simply implement
                a general "standby".

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device_pool = self.target

            if device_pool.standby():
                return (ResultCode.OK, "StandbyFull command completed OK")
            else:
                return (ResultCode.FAILED, "StandbyFull command failed")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def StandbyFull(self) -> Tuple[ResultCode, str]:
        """
        StandbyFull Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StandbyFull")
        (result_code, message) = handler()
        return [[result_code], [message]]

    class OperateCommand(ResponseCommand):
        """
        Class for handling the Operate command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless hook for implementation of
            :py:meth:`.MccsController.Operate` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of OperateCommand(), does nothing",
            )

        def check_allowed(self) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.OFF

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Operate(self) -> Tuple[ResultCode, str]:
        """
        Transit to the OPERATE operating state, ready for signal
        processing.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Operate")
        (result_code, message) = handler()
        return [[result_code], [message]]

    def is_Operate_allowed(self) -> bool:
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

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska_tango_base.SKABaseDevice.Reset`
            command for this :py:class:`.MccsController` device.

            This implementation resets the MCCS system as a whole as an
            attempt to clear a FAULT state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Allocate(self, argin: str) -> Tuple[ResultCode, str]:
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
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)

        :example:

        >>> proxy = tango.DeviceProxy("low-mccs/control/control")
        >>> proxy.Allocate(
                json.dumps(
                    {
                        "subarray_id": 1,
                        "station_ids": [1,2],
                        "channels": [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                        "subarray_beam_ids": [1],
                    }
                )
            )
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        handler = self.get_command_object("Allocate")
        (result_code, message) = handler(argin)
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class AllocateCommand(ResponseCommand):
        """
        Allocate a set of unallocated MCCS resources to a sub-array.

        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        Sub-Array.
        """

        def do(self, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the
            :py:meth:`.MccsController.Allocate` command

            Allocate a set of unallocated MCCS resources to a sub-array.
            The JSON argument specifies the overall sub-array composition in
            terms of which stations should be allocated to the specified Sub-Array.

            :param argin: JSON-formatted string
                    {
                    "subarray_id": int,
                    "station_ids": list[int],
                    "channels": list[list[int]],
                    "subarray_beam_ids": list[int],
                    }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """

            controllerdevice = self.target

            kwargs = json.loads(argin)
            subarray_id = kwargs.get("subarray_id")
            station_ids = kwargs.get("station_ids", list())
            channels = kwargs.get("channels", list())
            subarray_beam_ids = kwargs.get("subarray_beam_ids", list())
            controllerdevice = self.target
            assert 1 <= subarray_id <= len(controllerdevice._subarray_fqdns)

            # Allocation request checks
            # Generate station FQDNs from IDs
            stations = {}
            for station_id in station_ids:
                stations[station_id] = f"low-mccs/station/{station_id:03}"
            station_fqdns = stations.values()
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
                    f"Cannot allocate stations already allocated: {aalist}",
                )

            subarray_device = tango.DeviceProxy(subarray_fqdn)

            # Manager gave this list of stations to release (no longer required)
            if stations_to_release is not None:
                (result_code, message) = call_with_json(
                    subarray_device.ReleaseResources, stations=stations_to_release
                )
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Failed to release resources from subarray {subarray_fqdn}:"
                        f"{message}",
                    )
                for station_fqdn in stations_to_release:
                    station = tango.DeviceProxy(station_fqdn)
                    station.subarrayId = 0

                # Inform manager that we made the releases
                controllerdevice._stations_manager.release(stations_to_release)

            # Enable the subarray specified by the caller (if required)
            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                self._enable_subarray(subarray_id)

            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                return (ResultCode.FAILED, f"Cannot enable subarray {subarray_fqdn}")

            # Manager gave this list of stations to assign
            if stations_to_assign is not None:
                (result_code, message) = call_with_json(
                    subarray_device.AssignResources,
                    stations=stations_to_assign,
                    subarray_beams=subarray_beam_fqdns,
                    channels=channels,
                )
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Failed to assign resources to subarray {subarray_fqdn}:"
                        f"{message}",
                    )
                for fqdn in stations_to_assign:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = subarray_id

                # Inform manager that we made the assignments
                controllerdevice._stations_manager.assign(
                    stations_to_assign, subarray_id
                )

            return (ResultCode.OK, "Allocate command successful")

        def check_allowed(self) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.ON

        def _enable_subarray(self, argin: int) -> Tuple[ResultCode, str]:
            """
            Method to enable the specified subarray.

            :param argin: the subarray id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
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

            subarray_device = tango.DeviceProxy(subarray_fqdn)
            if not subarray_device.State() == DevState.ON:
                (result_code, message) = subarray_device.On()

                # TODO: handle ResultCode.STARTED
                if result_code == ResultCode.FAILED:
                    return (
                        result_code,
                        f"Failed to enable subarray {subarray_fqdn}: {message}",
                    )

            device._subarray_enabled[subarray_id - 1] = True
            return (ResultCode.OK, "_enable_subarray was successful")

    def is_Allocate_allowed(self) -> bool:
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

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Release(self, argin: str) -> Tuple[ResultCode, str]:
        """
        Release resources from an MCCS Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag and array resources (TBD).

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        handler = self.get_command_object("Release")
        (result_code, message) = handler(argin)
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class ReleaseCommand(ResponseCommand):
        """
        Release a sub-array's Capabilities and resources (stations),
        marking the resources and Capabilities as unassigned and idle.
        """

        def do(self, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless do hook for the
            :py:meth:`.MccsController.Release` command

            :param argin: JSON-formatted string containing an integer
                subarray_id, a release all flag and array resources (TBD).

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            kwargs = json.loads(argin)
            subarray_id = kwargs.get("subarray_id")
            release_all = kwargs.get("release_all")
            if subarray_id is None or not (
                1 <= subarray_id <= len(device._subarray_fqdns)
            ):
                return (
                    ResultCode.FAILED,
                    f"Subarray index '{subarray_id}' is out of range",
                )

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]
            if not device._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    f"Cannot release resources from disabled subarray {subarray_fqdn}",
                )

            if release_all:
                # Query stations resouce manager for stations assigned to subarray
                fqdns = self.target._stations_manager.get_assigned_fqdns(subarray_id)
                # and clear the subarrayId in each
                for fqdn in fqdns:
                    station = tango.DeviceProxy(fqdn)
                    station.subarrayId = 0
                # Finally release them from assignment in the manager
                self.target._stations_manager.release(fqdns)

                result = self._disable_subarray(subarray_id)
                if result[0] is not ResultCode.OK:
                    return (
                        result[0],
                        "_disable_subarray() release all or disable subarray failed",
                    )
            else:
                return (
                    ResultCode.FAILED,
                    "Release() command failed - partial release currently unsupported",
                )

            return (ResultCode.OK, "Release() command successful")

        def check_allowed(self) -> bool:
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            """
            return self.state_model.op_state == DevState.ON

        def _disable_subarray(self, argin: int) -> Tuple[ResultCode, str]:
            """
            Method to disable the specified subarray.

            :param argin: the subarray id

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            subarray_id = argin

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            # try:
            (result_code, message) = subarray_device.ReleaseAllResources()
            # except DevFailed:
            # pass  # it probably has no resources to release

            (result_code, message) = subarray_device.Off()
            if result_code == ResultCode.FAILED:
                return (ResultCode.FAILED, f"Subarray failed to turn off: {message}")
            device._subarray_enabled[subarray_id - 1] = False
            return (ResultCode.OK, "_disable_subarray was successful")

    def is_Release_allowed(self) -> bool:
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

        def do(self) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for handling the
            :py:meth:`.MccsController.Maintenance` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, "Stub implementation of Maintenance(), does nothing")

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Maintenance(self) -> Tuple[ResultCode, str]:
        """
        Transition the MCCS to a MAINTENANCE state.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Maintenance")
        (result_code, message) = handler()
        return [[result_code], [message]]


# ----------
# Run server
# ----------


def main(args: List = None, **kwargs: Dict) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """

    return MccsController.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
