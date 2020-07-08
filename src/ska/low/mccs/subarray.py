# -*- coding: utf-8 -*-
#
# This file is part of the SKA Software ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module provides MccsSubarray, the Tango device class for the MCCS
Subarray prototype.
"""
__all__ = ["MccsSubarray", "main"]

import json

# PyTango imports
import tango
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKASubarray
from ska.base.commands import ResponseCommand, ResultCode
import ska.low.mccs.release as release


class StationPoolManager:
    """
    A simple manager for the pool of stations that are assigned to a
    subarray. The current implementation allows to assign and release
    stations, and get a list of the FQDNs of the assigned stations.
    """
    def __init__(self):
        """
        Create a new StationPoolManager
        """
        self._stations = {}

    def __len__(self):
        """
        Return the number of stations assigned to this station pool
        manager.

        :return: the number of stations assigned to this station pool
            manager
        :rtype: int
        """
        return len(self._stations)

    def assign(self, stations):
        """
        Assign stations to this station pool manager

        :param stations: list of FQDNs of stations to be assigned
        :type stations: list of string
        """
        for fqdn in stations:
            if fqdn not in self._stations:
                station = tango.DeviceProxy(fqdn)
                station.Configure()
                self._stations[fqdn] = station

    def release(self, stations):
        """
        Release stations from this station pool manager

        :param stations: list of FQDNs of stations to be released
        :type stations: list of string
        """
        (self._stations.pop(station, None) for station in stations)

    def release_all(self):
        """
        Release all stations from this station pool manager
        """
        self._stations.clear()

    @property
    def fqdns(self):
        """
        Returns the FQDNs of currently assigned stations

        :return: FQDNs of currently assigned stations
        :rtype: list of string
        """
        returning = sorted(self._stations)
        print(f"Returning {returning}")
        return sorted(self._stations)


class TransientBufferManager:
    """
    Stub class for management of a transient buffer. Currently does
    nothing useful
    """
    def __init__(self):
        """
        Construct a new TransientBufferManager
        """
        pass

    def send(self, segment_spec):
        """
        Instructs the manager to send the specified segments of the
        transient buffer

        :param segment_spec: specification of the segment to be sent
        :type segment_spec: JSON string
        """
        pass


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray
    prototype.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKASubarray.InitCommand):
        """
        Command class for device initialisation
        """
        def do(self):
            """
            Stateless hook for initialisation of the attributes and
            properties of the MccsSubarray.
            """
            (result_code, message) = super().do()

            device = self.target
            device.station_pool_manager = StationPoolManager()
            device.transient_buffer_manager = TransientBufferManager()

            device._scan_id = -1

            device.set_change_event("stationFQDNs", True, True)
            device.set_archive_event("stationFQDNs", True, True)

            device._build_state = release.get_release_info()
            device._version_id = release.version

            return (result_code, message)

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        resourcing_args = (
            self.station_pool_manager, self.state_model, self.logger
        )
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Off", self.OnCommand(*args))
        self.register_command_object(
            "AssignResources", self.AssignResourcesCommand(*resourcing_args)
        )
        self.register_command_object(
            "ReleaseResources", self.ReleaseResourcesCommand(*resourcing_args)
        )
        self.register_command_object(
            "ReleaseAllResources",
            self.ReleaseAllResourcesCommand(*resourcing_args)
        )
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("Scan", self.ScanCommand(*args))
        self.register_command_object("EndScan", self.EndScanCommand(*args))
        self.register_command_object("End", self.EndCommand(*args))
        self.register_command_object("Abort", self.AbortCommand(*args))
        self.register_command_object("ObsReset", self.ResetCommand(*args))
        self.register_command_object("Restart", self.RestartCommand(*args))
        self.register_command_object(
            "SendTransientBuffer", self.SendTransientBufferCommand(
                self.transient_buffer_manager, self.state_model, self.logger
            )
        )

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated
        in the init_device() method to be released.  This method is
        called by the device destructor and by the device Init command.
        """

    # ------------------
    # Attribute methods
    # ------------------
    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        doc="The ID of the current scan, set via commands Scan() and "
        "endScan(). A scanId of 0 means that the subarray is idle.",
    )
    def scanId(self):
        """
        Return the scanId attribute.
        """
        return self._scan_id

    @scanId.write
    def scanId(self, id):
        """
        Set the scanId attribute

        :param id: the new scanId
        :type id: int
        """
        self._scan_id = id

    @attribute(
        dtype=("DevString",),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the "
        "Stations allocated to this Subarray",
    )
    def stationFQDNs(self):
        """
        Return the stationFQDNs attribute.
        """
        return self.station_pool_manager.fqdns

    # -------------------------------------------
    # Base class command and gatekeeper overrides
    # -------------------------------------------

    class OnCommand(SKASubarray.OnCommand):
        """
        Command class for the On() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            On command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class OffCommand(SKASubarray.OffCommand):
        """
        Command class for the Off() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            Off command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class AssignResourcesCommand(SKASubarray.AssignResourcesCommand):
        """
        Command class for the AssignResources() command
        """
        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            AssignResources command

            :param argin: The resources to be assigned
            :type argin: list of str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            stations = json.loads(argin)["stations"]
            station_pool_manager = self.target
            station_pool_manager.assign(stations)
            return [
                ResultCode.OK,
                "AssignResources command completed successfully"
            ]

    class ReleaseResourcesCommand(SKASubarray.ReleaseResourcesCommand):
        """
        Command class for the ReleaseResources() command
        """
        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            ReleaseResources command

            :param argin: The resources to be released
            :type argin: list of str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            stations = json.loads(argin)["stations"]
            station_pool_manager = self.target
            station_pool_manager.release(stations)
            return [
                ResultCode.OK,
                "ReleaseResources command completed successfully"
            ]

    class ReleaseAllResourcesCommand(SKASubarray.ReleaseAllResourcesCommand):
        """
        Command class for the ReleaseAllResources() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            ReleaseAllResources command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            station_pool_manager = self.target
            station_pool_manager.release_all()
            return (
                ResultCode.OK,
                "ReleaseAllResources command completed successfully"
            )

    class ConfigureCommand(SKASubarray.ConfigureCommand):
        """
        Command class for the Configure() command
        """
        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            Configure command

            :param argin: Configuration specification
            :type argin: JSON str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do(argin)

            # MCCS-specific stuff goes here
            return (result_code, message)

    class ScanCommand(SKASubarray.ScanCommand):
        """
        Command class for the Scan() command
        """
        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            Scan command

            :param argin: Scan specification
            :type argin: JSON string
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do(argin)

            # MCCS-specific stuff goes here
            return (result_code, message)

    class EndScanCommand(SKASubarray.EndScanCommand):
        """
        Command class for the EndScan() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            EndScan command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class EndCommand(SKASubarray.EndCommand):
        """
        Command class for the End() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            End command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class AbortCommand(SKASubarray.AbortCommand):
        """
        Command class for the Abort() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            Abort command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class ObsResetCommand(SKASubarray.ObsResetCommand):
        """
        Command class for the ObsReset() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            ObsReset command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class RestartCommand(SKASubarray.RestartCommand):
        """
        Command class for the Restart() command
        """
        def do(self):
            """
            Stateless hook implementing the functionality of the
            Restart command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    # ---------------------
    # MccsSubarray Commands
    # ---------------------

    class SendTransientBufferCommand(ResponseCommand):
        def do(self, argin):
            transient_buffer_manager = self.target
            transient_buffer_manager.send(argin)
            return (
                ResultCode.OK,
                "SendTransientBuffer command completed successfully"
            )

    @command(
        dtype_in="DevVarLongArray",
        doc_in="Specification of the segment of the transient buffer "
        "to send, comprising:"
        "1. Start time (timestamp: milliseconds since UNIX epoch)"
        "2. End time (timestamp: milliseconds since UNIX epoch)"
        "3. Dispersion measure"
        "Together, these parameters narrow the selection of transient"
        "buffer data to the period of time and frequencies that are of"
        "interest."
        ""
        "Additional metadata, such as the ID of a triggering Scheduling"
        "Block, may need to be supplied to allow SDP to assign data"
        "ownership correctly (TBD75).",
        dtype_out="DevVarLongStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):
        """
        Cause the subarray to send the requested segment of the
        transient buffer to SDP. The requested segment is specified by:

        1. Start time (timestamp: milliseconds since UNIX epoch)
        2. End time (timestamp: milliseconds since UNIX epoch)
        3. Dispersion measure

        Together, these parameters narrow the selection of transient
        buffer data to the period of time and frequencies that are of
        interest.

        Additional metadata, such as the ID of a triggering Scheduling
        Block, may need to be supplied to allow SDP to assign data
        ownership correctly (TBD75).

        :todo: This method is a stub that does nothing but return a
            dummy string.
        :param argin: Specification of the segment of the transient
            buffer to send
        :type argin: DevVarLongArray
        :return: ASCII String that indicates status, for information
            purposes only
        :rtype: DevString
        """
        handler = self.get_command_object("SendTransientBuffer")
        (result_code, message) = handler(argin)
        return [[result_code], [message]]


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Mainline for the MccsSubarray module.
    """
    return MccsSubarray.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
