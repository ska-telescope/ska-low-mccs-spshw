# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module provides MccsSubarray, the Tango device class for the MCCS
Subarray prototype.
"""
__all__ = ["MccsSubarray", "main"]

# imports
import json
import threading

# PyTango imports
import tango
from tango import DebugIt, EnsureOmniThread
from tango.server import attribute, command

# Additional import
from ska.base import SKASubarray
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import HealthState, ObsState

from ska.low.mccs.events import EventManager
from ska.low.mccs.health import MutableHealthModel
import ska.low.mccs.release as release


class StationPoolManager:
    """
    A simple manager for the pool of stations that are assigned to a
    subarray.

    The current implementation allows to assign and release stations,
    and get a list of the FQDNs of the assigned stations.
    """

    def __init__(self):
        """
        Create a new StationPoolManager.
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
        Assign stations to this station pool manager.

        :param stations: list of FQDNs of stations to be assigned
        :type stations: list(str)
        """
        for fqdn in stations:
            if fqdn not in self._stations:
                station = tango.DeviceProxy(fqdn)
                station.InitialSetup()
                self._stations[fqdn] = station

    def release(self, stations):
        """
        Release stations from this station pool manager.

        :param stations: list of FQDNs of stations to be released
        :type stations: list(str)
        """
        (self._stations.pop(station, None) for station in stations)

    def release_all(self):
        """
        Release all stations from this station pool manager.
        """
        self._stations.clear()

    @property
    def fqdns(self):
        """
        Returns the FQDNs of currently assigned stations.

        :return: FQDNs of currently assigned stations
        :rtype: list(str)
        """
        return sorted(self._stations)


class TransientBufferManager:
    """
    Stub class for management of a transient buffer.

    Currently does nothing useful
    """

    def __init__(self):
        """
        Construct a new TransientBufferManager.
        """
        pass

    def send(self, segment_spec):
        """
        Instructs the manager to send the specified segments of the
        transient buffer.

        :param segment_spec: JSON-encoded specification of the segment
            to be sent
        :type segment_spec: str
        """
        pass


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray
    prototype.

    This is a subclass of :py:class:`ska.base.SKASubarray`.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKASubarray.InitCommand):
        """
        Command class for device initialisation.
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska.base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Stateless hook for initialisation of the attributes and
            properties of the :py:class:`.MccsSubarray`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            device = self.target
            device._station_pool_manager = StationPoolManager()
            device._transient_buffer_manager = TransientBufferManager()

            device._scan_id = -1

            device.set_change_event("stationFQDNs", True, True)
            device.set_archive_event("stationFQDNs", True, True)

            device._build_state = release.get_release_info()
            device._version_id = release.version

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )

            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_health_monitoring(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.event_manager = EventManager(self.logger)
            device._health_state = HealthState.OK
            device.set_change_event("healthState", True, False)
            device.health_model = MutableHealthModel(
                None, [], device.event_manager, device.health_changed
            )

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Off", self.OffCommand(*args))
        self.register_command_object(
            "AssignResources", self.AssignResourcesCommand(*args)
        )
        self.register_command_object(
            "ReleaseResources", self.ReleaseResourcesCommand(*args)
        )
        self.register_command_object(
            "ReleaseAllResources", self.ReleaseAllResourcesCommand(*args)
        )
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("Scan", self.ScanCommand(*args))
        self.register_command_object("EndScan", self.EndScanCommand(*args))
        self.register_command_object("End", self.EndCommand(*args))
        self.register_command_object("Abort", self.AbortCommand(*args))
        self.register_command_object("ObsReset", self.ResetCommand(*args))
        self.register_command_object("Restart", self.RestartCommand(*args))
        self.register_command_object(
            "SendTransientBuffer",
            self.SendTransientBufferCommand(
                self._transient_buffer_manager, self.state_model, self.logger
            ),
        )

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsSubarray.InitCommand.do` method of the nested
        :py:class:`~.MccsSubarray.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsSubarray.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """

    # ------------------
    # Attribute methods
    # ------------------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska.base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        doc="The ID of the current scan, set via commands Scan() and "
        "endScan(). A scanId of 0 means that the subarray is idle.",
    )
    def scanId(self):
        """
        Return the scan id.

        :return: the scan id
        :rtype: int
        """
        return self._scan_id

    @scanId.write
    def scanId(self, scan_id):
        """
        Set the scanId attribute.

        :param scan_id: the new scanId
        :type scan_id: int
        """
        self._scan_id = scan_id

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
        Return the FQDNs of stations assigned to this subarray.

        :return: FQDNs of stations assigned to this subarray
        :rtype: list(str)
        """
        return self._station_pool_manager.fqdns

    # -------------------------------------------
    # Base class command and gatekeeper overrides
    # -------------------------------------------

    class OnCommand(SKASubarray.OnCommand):
        """
        Class for handling the On() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.On` command for
            this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class OffCommand(SKASubarray.OffCommand):
        """
        Class for handling the Off() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKABaseDevice.Off` command
            for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class AssignResourcesCommand(SKASubarray.AssignResourcesCommand):
        """
        Class for handling the AssignResources(argin) command.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.AssignResources`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: The resources to be assigned
            :type argin: list(str)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            stations = json.loads(argin)["stations"]
            device = self.target
            device.health_model.add_devices(stations)
            device._station_pool_manager.assign(stations)
            return [ResultCode.OK, "AssignResources command completed successfully"]

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target._station_pool_manager) == 0:
                action = "resourcing_succeeded_no_resources"
            else:
                action = "resourcing_succeeded_some_resources"
            self.state_model.perform_action(action)

    class ReleaseResourcesCommand(SKASubarray.ReleaseResourcesCommand):
        """
        Class for handling the ReleaseResources(argin) command.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.ReleaseResources`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: The resources to be released
            :type argin: list(str)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            stations = json.loads(argin)["stations"]
            device = self.target
            device._station_pool_manager.release(stations)
            device.health_model.remove_devices(stations)
            return [ResultCode.OK, "ReleaseResources command completed successfully"]

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target._station_pool_manager):
                action = "resourcing_succeeded_some_resources"
            else:
                action = "resourcing_succeeded_no_resources"
            self.state_model.perform_action(action)

    class ReleaseAllResourcesCommand(SKASubarray.ReleaseAllResourcesCommand):
        """
        Class for handling the ReleaseAllResources() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited)
            :py:meth:`ska.base.SKASubarray.ReleaseAllResources`
            command for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            device = self.target
            device._station_pool_manager.release_all()
            device.health_model.remove_all_devices()

            return (ResultCode.OK, "ReleaseAllResources command completed successfully")

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target._station_pool_manager):
                action = "resourcing_succeeded_some_resources"
            else:
                action = "resourcing_succeeded_no_resources"
            self.state_model.perform_action(action)

    class ConfigureCommand(SKASubarray.ConfigureCommand):
        """
        Class for handling the Configure(argin) command.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.Configure`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: JSON configuration specification
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            result_code = ResultCode.OK
            message = "Configure command completed successfully"

            # MCCS-specific stuff goes here
            return (result_code, message)

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device obsstates
            :rtype: bool
            """
            return self.state_model.obs_state in [ObsState.IDLE, ObsState.READY]

    class ScanCommand(SKASubarray.ScanCommand):
        """
        Class for handling the Scan(argin) command.
        """

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.Scan` command for
            this :py:class:`.MccsSubarray` device.

            :param argin: JSON scan specification
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do(argin)

            # MCCS-specific stuff goes here
            return (result_code, message)

    class EndScanCommand(SKASubarray.EndScanCommand):
        """
        Class for handling the EndScan() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.EndScan` command
            for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class EndCommand(SKASubarray.EndCommand):
        """
        Class for handling the End() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.End` command for
            this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class AbortCommand(SKASubarray.AbortCommand):
        """
        Class for handling the Abort() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.Abort` command
            for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class ObsResetCommand(SKASubarray.ObsResetCommand):
        """
        Class for handling the ObsReset() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.ObsReset` command
            for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class RestartCommand(SKASubarray.RestartCommand):
        """
        Class for handling the Restart() command.
        """

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited) :py:meth:`ska.base.SKASubarray.Restart` command
            for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    # ---------------------
    # MccsSubarray Commands
    # ---------------------

    class SendTransientBufferCommand(ResponseCommand):
        """
        Class for handling the SendTransientBuffer(argin) command.
        """

        def do(self, argin):
            """
            Stateless do-hook for the
            :py:meth:`.MccsSubarray.SendTransientBuffer`
            command

            :param argin: specification of the segment of the transient
                buffer to send, comprising:
                1. Start time (timestamp: milliseconds since UNIX epoch)
                2. End time (timestamp: milliseconds since UNIX epoch)
                3. Dispersion measure
                Together, these parameters narrow the selection of
                transient buffer data to the period of time and
                frequencies that are of interest.
            :type argin: list(int)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            transient_buffer_manager = self.target
            transient_buffer_manager.send(argin)
            return (ResultCode.OK, "SendTransientBuffer command completed successfully")

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
    def SendTransientBuffer(self, argin):
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
        :type argin: list(int)

        :return: ASCII String that indicates status, for information
            purposes only
        :rtype: str
        """
        handler = self.get_command_object("SendTransientBuffer")
        (result_code, message) = handler(argin)
        return [[result_code], [message]]


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
    return MccsSubarray.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
