# -*- coding: utf-8 -*-
#
# This file is part of the MccsController project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MccsController Tango device prototype

MccsController TANGO device class for the MccsController prototype
"""
__all__ = ["MccsController", "main"]

import numpy
import json
import threading

# PyTango imports
import tango
from tango import DebugIt, DevFailed, DevState, EnsureOmniThread
from tango.server import attribute, command, device_property

# Additional import
from ska.base import SKAMaster, SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode

from ska.low.mccs.power import PowerManager, PowerManagerError
import ska.low.mccs.release as release
from ska.low.mccs.utils import call_with_json, tango_raise
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel


class ControllerPowerManager(PowerManager):
    """
    This class that implements the power manager for the MCCS Controller
    device.
    """

    def __init__(self, station_fqdns):
        """
        Initialise a new ControllerPowerManager

        :param station_fqdns: the FQDNs of the stations that this controller
            device manages
        :type station_fqdns: list of string
        """
        super().__init__(None, station_fqdns)


class MccsController(SKAMaster):
    """
    MccsController TANGO device class for the MCCS prototype.

    This is a subclass of :py:class:`ska.base.SKAMaster`.

    **Properties:**

    - Device Property
        MccsSubarrays
            - The FQDNs of the Mccs sub-arrays
            - Type: :py:class:`~tango.DevVarStringArray`
        MccsStations
            - List of MCCS station  TANGO Device names
            - Type: :py:class:`~tango.DevVarStringArray`
        MccsStationBeams
            - List of MCCS station beam TANGO Device names
            - Type: :py:class:`~tango.DevVarStringArray`
        MccsTiles
            - List of MCCS Tile TANGO Device names.
            - Type: :py:class:`~tango.DevVarStringArray`
        MccsAntenna
            - List of MCCS Antenna TANGO Device names
            - Type: :py:class:`~tango.DevVarStringArray`
    """

    # -----------------
    # Device Properties
    # -----------------

    MccsSubarrays = device_property(dtype="DevVarStringArray")
    MccsStations = device_property(dtype="DevVarStringArray")

    # ---------------
    # General methods
    # ---------------

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        # Technical debt -- forced to register base class stuff rather than
        # calling super(), because On() and Off() are registered on a
        # thread, and we don't want the super() method clobbering them
        args = (self, self.state_model, self.logger)
        self.register_command_object("Disable", self.DisableCommand(*args))
        self.register_command_object("Standby", self.StandbyCommand(*args))
        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
        )

        self.register_command_object("StandbyLow", self.StandbyLowCommand(*args))
        self.register_command_object("StandbyFull", self.StandbyFullCommand(*args))
        self.register_command_object("Operate", self.OperateCommand(*args))
        self.register_command_object("Allocate", self.AllocateCommand(*args))
        self.register_command_object("Release", self.ReleaseCommand(*args))
        self.register_command_object("Maintenance", self.MaintenanceCommand(*args))

    class InitCommand(SKAMaster.InitCommand):
        """
        A class for :py:class:`~ska.low.mccs.controller.MccsController`'s Init command.
        The :py:meth:`~ska.low.mccs.controller.MccsController.InitCommand.do` method
        below is called upon :py:class:`~ska.low.mccs.controller.MccsController`'s
        initialisation.
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            `MccsController`.
            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            super().do()

            device = self.target
            device._build_state = release.get_release_info()
            device._version_id = release.version

            device._subarray_fqdns = numpy.array(
                [] if device.MccsSubarrays is None else device.MccsSubarrays, dtype=str
            )

            # whether subarray is enabled
            device._subarray_enabled = numpy.zeros(
                len(device.MccsSubarrays), dtype=bool
            )

            device._station_fqdns = numpy.array(
                [] if device.MccsStations is None else device.MccsStations, dtype=str
            )

            # id of subarray that station is allocated to, zero if unallocated
            device._station_allocated = numpy.zeros(
                len(device.MccsStations), dtype=numpy.ubyte
            )

            self._thread = threading.Thread(
                target=self._initialise_connections,
                args=(device, device._station_fqdns),
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device, fqdns):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices to which
                this device must maintain connections
            :type: list of str
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_health_monitoring(device, fqdns)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_power_management(device, fqdns)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()

        def _initialise_health_monitoring(self, device, fqdns):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device monitors health
            :type: list of str
            """
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)

            device.event_manager = EventManager(fqdns)
            device.health_model = HealthModel(
                None, fqdns, device.event_manager, device._update_health_state
            )

        def _initialise_power_management(self, device, fqdns):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device manages power
            :type: list of str
            """
            device.power_manager = ControllerPowerManager(device._station_fqdns)

            power_args = (device.power_manager, device.state_model, device.logger)
            device.register_command_object("Off", device.OffCommand(*power_args))
            device.register_command_object("On", device.OnCommand(*power_args))

        def interrupt(self):
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.controller.MccsController.InitCommand.do` method of the
        nested :py:class:`~ska.low.mccs.controller.MccsController.InitCommand` class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.controller.MccsController.InitCommand.do` method to be
        released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    @attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        polling_period=3000,
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
        doc="Percentage progress implemented for commands that result in "
        "state/mode transitions for a large \nnumber of components and/or "
        "are executed in stages (e.g power up, power down)",
    )
    def commandProgress(self):
        """
        Return the commandProgress attribute value.

        :return: command progress as a percentage
        :rtype: int
        """
        return 0

    @attribute(
        dtype="DevUShort",
        unit="s",
        doc="Amount of time it will take to prepare the requested state/mode "
        "transition ? implemented as needed.",
    )
    def commandDelayExpected(self):

        """
        Return the commandDelayExpected attribute.

        :return: number of seconds it is expected to take to complete the command
        :rtype: int
        """
        return 0

    # --------
    # Commands
    # --------

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On command.
        """

        def do(self):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`MccsController.On` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                if power_manager.on():
                    return (ResultCode.OK, "On command completed OK")
                else:
                    return (ResultCode.FAILED, "On command failed")
            except PowerManagerError as pme:
                return (ResultCode.FAILED, f"On command failed: {pme}")

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off command.
        """

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                if power_manager.off():
                    return (ResultCode.OK, "Off command completed OK")
                else:
                    return (ResultCode.FAILED, "Off command failed")
            except PowerManagerError as pme:
                return (ResultCode.FAILED, f"Off command failed: {pme}")

    class StandbyLowCommand(ResponseCommand):
        """
        Class for handling the StandbyLow command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`MccsController.StandbyLow` command.

            Transitions the MCCS system to the low-power STANDBY_LOW_POWER
            operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of StandbyLowCommand(), does nothing",
            )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def StandbyLow(self):
        """
        StandbyLow Command

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StandbyLow")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class StandbyFullCommand(ResponseCommand):
        """
        Class for handling the StandbyFull command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`MccsController.StandbyFull` command.

            Transition the MCCS system to the STANDBY_FULL_POWER operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of StandbyFullCommand(), does nothing",
            )

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def StandbyFull(self):
        """
        StandbyFull Command

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("StandbyFull")
        (return_code, message) = handler()
        return [[return_code], [message]]

    class OperateCommand(ResponseCommand):
        """
        Class for handling the Operate command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`MccsController.Operate` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of OperateCommand(), does nothing",
            )

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.OFF

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def Operate(self):
        """
        Transit to the OPERATE operating state, ready for signal processing.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Operate")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def is_Operate_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        """
        handler = self.get_command_object("Operate")
        if not handler.check_allowed():
            tango_raise("Operate() is not allowed in current state")
        return True

    class ResetCommand(SKABaseDevice.ResetCommand):
        """
        Command class for the Reset() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`MccsController.Reset` command. This
            implementation resets the MCCS system as a whole as an
            attempt to clear a FAULT state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    @command(
        dtype_in="DevString",
        doc_in="JSON-formatted string",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    def Allocate(self, argin):
        """
        Allocate a set of unallocated MCCS resources to a sub-array.
        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, station_ids, channels and station_beam_ids.
        :type argin: str
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)

        :example:

        >>> proxy = tango.DeviceProxy("low-mccs/control/control")
        >>> proxy.Allocate(
                json.dumps(
                    {
                        "subarray_id":1,
                        "station_ids": [1, 2],
                        "channels": [1,2,3,4,5,6,7,8],
                        "station_beam_ids": [1],
                    }
                )
            )
        """

        handler = self.get_command_object("Allocate")
        (resultcode, message) = handler(argin)
        return [[resultcode], [message]]

    class AllocateCommand(ResponseCommand):
        """
        Allocate a set of unallocated MCCS resources to a sub-array.
        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified Sub-Array.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`MccsController.Allocate` command

            Allocate a set of unallocated MCCS resources to a sub-array.
            The JSON argument specifies the overall sub-array composition in
            terms of which stations should be allocated to the specified Sub-Array.

            :param argin: JSON-formatted string containing an integer
                subarray_id, station_ids, channels and station_beam_ids.
            :type argin: str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """

            args = json.loads(argin)
            subarray_id = args["subarray_id"]
            station_ids = args["station_ids"]
            controllerdevice = self.target
            assert 1 <= subarray_id <= len(controllerdevice._subarray_fqdns)

            # Allocation request checks
            station_fqdns = []
            for station_id in station_ids:
                station_fqdns.append(f"low-mccs/station/{station_id:03}")

            station_allocation = numpy.isin(
                controllerdevice._station_fqdns, station_fqdns, assume_unique=True
            )
            already_allocated = numpy.logical_and.reduce(
                (
                    controllerdevice._station_allocated != 0,
                    controllerdevice._station_allocated != subarray_id,
                    station_allocation,
                )
            )
            if numpy.any(already_allocated):
                already_allocated_fqdns = list(
                    controllerdevice._station_fqdns[already_allocated]
                )
                fqdns_string = ", ".join(already_allocated_fqdns)
                return (
                    ResultCode.FAILED,
                    f"Cannot allocate stations already allocated: {fqdns_string}",
                )

            # Check to see if we need to release resources before allocating
            subarray_fqdn = controllerdevice._subarray_fqdns[subarray_id - 1]
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            release_mask = numpy.logical_and(
                controllerdevice._station_allocated == subarray_id,
                numpy.logical_not(station_allocation),
            )
            if numpy.any(release_mask):
                stations_to_release = list(
                    controllerdevice._station_fqdns[release_mask]
                )
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

            # Enable the subarray specified by the caller (if required)
            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                self._enable_subarray(subarray_id)

            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                return (ResultCode.FAILED, f"Cannot enable subarray {subarray_fqdn}")

            # Now, assign resources
            assign_mask = numpy.logical_and(
                controllerdevice._station_allocated == 0, station_allocation
            )

            if numpy.any(assign_mask):
                stations_to_assign = list(controllerdevice._station_fqdns[assign_mask])
                (result_code, message) = call_with_json(
                    subarray_device.AssignResources, stations=stations_to_assign
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

            controllerdevice._station_allocated[release_mask] = 0
            controllerdevice._station_allocated[assign_mask] = subarray_id
            return (ResultCode.OK, "Allocate command successful")

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.ON

        def _enable_subarray(self, argin):
            """
            Method to enable the specified subarray

            :param argin: the subarray id
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
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

    def is_Allocate_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        """
        handler = self.get_command_object("Allocate")
        if not handler.check_allowed():
            tango_raise("Allocate() is not allowed in current state")
        return True

    @command(
        dtype_in="DevString",
        doc_in="JSON-formatted string",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    def Release(self, argin):
        """
        Release resources from an MCCS Sub-Array

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag and array resources (TBD).
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Release")
        (resultcode, message) = handler(argin)
        return [[resultcode], [message]]

    class ReleaseCommand(ResponseCommand):
        """
        Release a sub-array's Capabilities and resources (stations),
        marking the resources and Capabilities as unassigned and
        idle.
        """

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`MccsController.Release` command

            :param argin: JSON-formatted string containing an integer
                subarray_id, a release all flag and array resources (TBD).
            :type argin: str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            device = self.target
            args = json.loads(argin)
            subarray_id = args["subarray_id"]
            release_all = args["release_all"]
            if not (1 <= subarray_id <= len(device._subarray_fqdns)):
                return (
                    ResultCode.FAILED,
                    f"Subarray index {subarray_id} is out of range",
                )

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]
            if not device._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    f"Cannot release resources from disabled subarray {subarray_fqdn}",
                )

            if release_all:
                mask = device._station_allocated == subarray_id
                active_station_fqdns = list(device._station_fqdns[mask])
                for station_fqdn in active_station_fqdns:
                    station = tango.DeviceProxy(station_fqdn)
                    station.subarrayId = 0
                device._station_allocated[mask] = 0

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

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.ON

        def _disable_subarray(self, argin):
            """
            Method to disable the specified subarray

            :param argin: the subarray id
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            device = self.target
            subarray_id = argin

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            try:
                (result_code, message) = subarray_device.ReleaseAllResources()
            except DevFailed:
                pass  # it probably has no resources to release

            (result_code, message) = subarray_device.Off()
            if result_code == ResultCode.FAILED:
                return (ResultCode.FAILED, f"Subarray failed to turn off: {message}")
            device._subarray_enabled[subarray_id - 1] = False
            return (ResultCode.OK, "_disable_subarray was successful")

    def is_Release_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        """
        handler = self.get_command_object("Release")
        if not handler.check_allowed():
            tango_raise("Release() is not allowed in current state")
        return True

    class MaintenanceCommand(ResponseCommand):
        """
        Class for handling the
        :py:meth:`MccsController.Maintenance` command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Stateless do-hook for handling the
            :py:meth:`MccsController.Maintenance` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`ska.base.commands.ResultCode`, str)
            """
            return (ResultCode.OK, "Stub implementation of Maintenance(), does nothing")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def Maintenance(self):
        """
        Transition the MCCS to a MAINTENANCE state.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Maintenance")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def _update_health_state(self, health_state):
        """
        Update and push a change event for the healthState attribute

        :param health_state: The new health state
        :type health_state: :py:class:`ska.base.control_model.HealthState`
        """
        self.push_change_event("healthState", health_state)
        self._health_state = health_state
        self.logger.info("health state = " + str(health_state))


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.controller` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """

    return MccsController.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
