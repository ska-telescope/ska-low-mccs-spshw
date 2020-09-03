# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MccsMaster Tango device prototype

MccsMaster TANGO device class for the MccsMaster prototype
"""
__all__ = ["MccsMaster", "main"]

import numpy
import json
import threading

# PyTango imports
import tango
from tango import DebugIt, DevFailed, DevState
from tango.server import attribute, command, device_property

# Additional import
from ska.base import SKAMaster, SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode

import ska.low.mccs.release as release
from ska.low.mccs.utils import call_with_json, tango_raise
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthMonitor, HealthRollupPolicy


class MccsMaster(SKAMaster):
    """
    MccsMaster TANGO device class for the MCCS prototype

    **Properties:**

    - Device Property
        MccsSubarrays
            - The FQDNs of the Mccs sub-arrays
            - Type: :class:`~tango.DevVarStringArray`
        MccsStations
            - List of MCCS station  TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsStationBeams
            - List of MCCS station beam TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsTiles
            - List of MCCS Tile TANGO Device names.
            - Type: :class:`~tango.DevVarStringArray`
        MccsAntenna
            - List of MCCS Antenna TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
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

        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("Reset", self.ResetCommand(*args))
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Off", self.OffCommand(*args))
        self.register_command_object("StandbyLow", self.StandbyLowCommand(*args))
        self.register_command_object("StandbyFull", self.StandbyFullCommand(*args))
        self.register_command_object("Operate", self.OperateCommand(*args))
        self.register_command_object(
            "EnableSubarray", self.EnableSubarrayCommand(*args)
        )
        self.register_command_object(
            "DisableSubarray", self.DisableSubarrayCommand(*args)
        )
        self.register_command_object("Allocate", self.AllocateCommand(*args))
        self.register_command_object("Release", self.ReleaseCommand(*args))
        self.register_command_object("Maintenance", self.MaintenanceCommand(*args))

    class InitCommand(SKAMaster.InitCommand):
        """
        A class for MccsMaster's init_device() "command".
        """

        def do(self):
            """
            Initialises the attributes and properties of the MccsMaster.
            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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

            device._lock = threading.Lock()
            # initialise the health table using the FQDN as the key.
            # Create and event manager per FQDN and subscribe to events from it
            device._eventManagerList = []
            fqdns = device._station_fqdns
            device._rollup_policy = HealthRollupPolicy(device.update_healthstate)
            device._health_monitor = HealthMonitor(
                fqdns, device._rollup_policy.rollup_health
            )
            for fqdn in device._station_fqdns:
                device._eventManagerList.append(
                    EventManager(fqdn, device._health_monitor.update_health_table)
                )

            message = "MccsMaster Init command completed OK"
            self.logger.info(message)
            return (ResultCode.OK, message)

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
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

        :return: number of seconds it is expected to take to complete
           the command
        :rtype: int
        """
        return 0

    # --------
    # Commands
    # --------
    class StandbyLowCommand(ResponseCommand):
        """
        Class for handling the StandbyLow command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Transition the MCCS system to the low-power STANDBY_LOW_POWER
            operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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
        :rtype: (ResultCode, str)
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
            Transition the MCCS system to the STANDBY_FULL_POWER operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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
        :rtype: (ResultCode, str)
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
            Stateless hook for implementation of Operate()
            command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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
        :rtype: (ResultCode, str)
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
        :raises: DevFailed if this command is not allowed to be run
            in current device state
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
            Reset command. This implementation resets the MCCS
            system as a whole as an attempt to clear a FAULT
            state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()
            # MCCS-specific Reset functionality goes here
            return (result_code, message)

    @command(
        dtype_in="DevLong",
        doc_in="Sub-Array ID",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    def EnableSubarray(self, argin):
        """
        Activate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: DevVarLongArray
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (ResultCode, str)
        """
        handler = self.get_command_object("EnableSubarray")
        (resultcode, message) = handler(argin)
        return [[resultcode], [message]]

    class EnableSubarrayCommand(ResponseCommand):
        """
        Activate an MCCS Sub-Array
        """

        def do(self, argin):
            """
            Stateless do hook for the EnableSubarray() command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            device = self.target
            subarray_id = argin

            if not (1 <= subarray_id <= len(device._subarray_fqdns)):
                return (
                    ResultCode.FAILED,
                    "Subarray index {} is out of range".format(subarray_id),
                )

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]

            if device._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    "Subarray {} is already enabled".format(subarray_fqdn),
                )
            else:
                subarray_device = tango.DeviceProxy(subarray_fqdn)
                (result_code, message) = subarray_device.On()
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Failed to enable subarray {subarray_fqdn}: {message}",
                    )
                device._subarray_enabled[subarray_id - 1] = True
                return (ResultCode.OK, "EnableSubarray command successful")

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.ON

    def is_EnableSubarray_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        :raises: DevFailed if this command is not allowed to be run
            in current device state
        """
        handler = self.get_command_object("EnableSubarray")
        if not handler.check_allowed():
            tango_raise("EnableSubarray() is not allowed in current state")
        return True

    @command(
        dtype_in="DevLong",
        doc_in="Sub-Array ID",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    def DisableSubarray(self, argin):
        """
        De-activate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: DevVarLongArray
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (ResultCode, str)
        """
        handler = self.get_command_object("DisableSubarray")
        (resultcode, message) = handler(argin)
        return [[resultcode], [message]]

    class DisableSubarrayCommand(ResponseCommand):
        """
        De-activate an MCCS Sub-Array
        """

        def do(self, argin):
            """
            Stateless do hook for the DisableSubarray command

            :param argin: Sub-Array ID
            :type argin: DevVarLongArray
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            device = self.target
            subarray_id = argin

            if not (1 <= subarray_id <= len(device._subarray_fqdns)):
                return (
                    ResultCode.FAILED,
                    "Subarray index {} is out of range".format(subarray_id),
                )

            subarray_fqdn = device._subarray_fqdns[subarray_id - 1]

            if not device._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    "Subarray {} is already disabled".format(subarray_fqdn),
                )
            else:
                mask = device._station_allocated == subarray_id
                fqdns = device._station_fqdns[mask]
                fqdns = list(fqdns)
                for fqdn in fqdns:
                    station = tango.DeviceProxy(fqdn)
                    station.subarrayId = 0
                device._station_allocated[mask] = 0

                subarray_device = tango.DeviceProxy(subarray_fqdn)
                try:
                    (result_code, message) = subarray_device.ReleaseAllResources()
                except DevFailed:
                    pass  # it probably has no resources to release

                (result_code, message) = subarray_device.Off()
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Subarray failed to turn off: {message}",
                    )
                device._subarray_enabled[subarray_id - 1] = False
                return (ResultCode.OK, "DisableSubarray command successful")

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.ON

    def is_DisableSubarray_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        :raises: DevFailed if this command is not allowed to be run
            in current device state
        """
        handler = self.get_command_object("DisableSubarray")
        if not handler.check_allowed():
            tango_raise("DisableSubarray() is not allowed in current state")
        return True

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
            subarray_id, and arrays of station fqdns.
        :type argin: str
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (ResultCode, str)

        :example:

        >>> proxy = tango.DeviceProxy("low/elt/master")
        >>> proxy.EnableSubarray(1)
        >>> proxy.Allocate('{"subarray_id":1,
                            "stations": ["mccs/station/01", "mccs/station/02",]}')
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

        # subarray_id, stations
        def do(self, argin):
            """
            Stateless hook implementing the functionality of the Allocate command

            Allocate a set of unallocated MCCS resources to a sub-array.
            The JSON argument specifies the overall sub-array composition in
            terms of which stations should be allocated to the specified Sub-Array.

            :param argin: JSON-formatted string containing an integer
                subarray_id, and arrays of station fqdns.
            :type argin: str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """

            args = json.loads(argin)
            subarray_id = args["subarray_id"]
            stations = args["stations"]
            masterdevice = self.target

            assert 1 <= subarray_id <= len(masterdevice._subarray_fqdns)
            subarray_fqdn = masterdevice._subarray_fqdns[subarray_id - 1]

            if not masterdevice._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    "Cannot allocate resources to disabled subarray {}".format(
                        subarray_fqdn
                    ),
                )
            station_allocation = numpy.isin(
                masterdevice._station_fqdns, stations, assume_unique=True
            )
            already_allocated = numpy.logical_and.reduce(
                (
                    masterdevice._station_allocated != 0,
                    masterdevice._station_allocated != subarray_id,
                    station_allocation,
                )
            )

            if numpy.any(already_allocated):
                already_allocated_fqdns = list(
                    masterdevice._station_fqdns[already_allocated]
                )
                return (
                    ResultCode.FAILED,
                    "Cannot allocate stations already allocated: {}".format(
                        ", ".join(already_allocated_fqdns)
                    ),
                )
            subarray_device = tango.DeviceProxy(subarray_fqdn)

            release_mask = numpy.logical_and(
                masterdevice._station_allocated == subarray_id,
                numpy.logical_not(station_allocation),
            )
            if numpy.any(release_mask):
                stations_to_release = list(masterdevice._station_fqdns[release_mask])
                (result_code, message) = call_with_json(
                    subarray_device.ReleaseResources, stations=stations_to_release
                )
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Failed to release resources from subarray {subarray_fqdn}:"
                        f"{message}",
                    )
                for fqdn in stations_to_release:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = 0

            assign_mask = numpy.logical_and(
                masterdevice._station_allocated == 0, station_allocation
            )
            if numpy.any(assign_mask):
                stations_to_assign = list(masterdevice._station_fqdns[assign_mask])
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

            masterdevice._station_allocated[release_mask] = 0
            masterdevice._station_allocated[assign_mask] = subarray_id
            return (ResultCode.OK, "Allocate command successful")

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state

            :return: True if this command is allowed to be run in
                current device state
            :rtype: boolean
            """
            return self.state_model.op_state == DevState.ON

    def is_Allocate_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        :raises: DevFailed if this command is not allowed to be run
            in current device state
        """
        handler = self.get_command_object("Allocate")
        if not handler.check_allowed():
            tango_raise("Allocate() is not allowed in current state")
        return True

    @command(
        dtype_in="DevLong",
        doc_in="Sub-Array ID",
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    def Release(self, argin):
        """
        De-activate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: DevVarLongArray
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (ResultCode, str)
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
            Stateless do hook for the Release command

            :param argin: Sub-Array ID
            :type argin: DevVarLongArray
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            subarray_id = argin
            assert 1 <= subarray_id <= len(self.target._subarray_fqdns)

            subarray_fqdn = self.target._subarray_fqdns[subarray_id - 1]

            if not self.target._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    "Cannot release resources from disabled subarray {}".format(
                        subarray_fqdn
                    ),
                )
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            try:
                (result_code, message) = subarray_device.ReleaseAllResources()
            except DevFailed:
                return (
                    ResultCode.FAILED,
                    "Subarray errored on release resources: it probably has "
                    "no resources to release.",
                )
            if result_code == ResultCode.FAILED:
                return (
                    ResultCode.FAILED,
                    "Subarray failed to release resources: {message}",
                )

            mask = self.target._station_allocated == subarray_id
            fqdns = list(self.target._station_fqdns[mask])
            for fqdn in fqdns:
                device = tango.DeviceProxy(fqdn)
                device.subarrayId = 0
            self.target._station_allocated[mask] = 0
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

    def is_Release_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state

        :return: True if this command is allowed to be run in
            current device state
        :rtype: boolean
        :raises: DevFailed if this command is not allowed to be run
            in current device state
        """
        handler = self.get_command_object("Release")
        if not handler.check_allowed():
            tango_raise("Release() is not allowed in current state")
        return True

    class MaintenanceCommand(ResponseCommand):
        """
        Class for handling the Maintenance command.

        :todo: What is this command supposed to do? It takes no
            argument, and returns nothing.
        """

        def do(self):
            """
            Power off the MCCS system.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
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
        :rtype: (ResultCode, str)
        """
        handler = self.get_command_object("Maintenance")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def update_healthstate(self, health_state):
        """
        Update and push a change event for the healthstate attribute

        :param health_state: The new healthstate
        :type health_state: enum (defined in ska.base.control_model)
        """
        self.push_change_event("healthState", health_state)
        with self._lock:
            self._health_state = health_state
        self.logging.info(f"health state = {health_state}")


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsMaster module."""

    return MccsMaster.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
