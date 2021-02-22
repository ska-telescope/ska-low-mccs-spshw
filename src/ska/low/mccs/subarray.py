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
__all__ = [
    "MccsSubarray",
    "StationsResourceManager",
    "StationBeamsResourceManager",
    "main",
]

# imports
import json
import threading
import time

# PyTango imports
import tango
from tango import DebugIt, DevState, EnsureOmniThread
from tango.server import attribute, command

# Additional import
from ska.base import SKASubarray
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import HealthState, ObsState

from ska.low.mccs.events import EventManager
from ska.low.mccs.health import MutableHealthModel
import ska.low.mccs.release as release
from ska.low.mccs.resource import ResourceManager
from ska.low.mccs.utils import backoff_connect


class StationsResourceManager(ResourceManager):
    """
    A simple manager for the pool of stations that are assigned to a
    subarray.

    Inherits from ResourceManager.
    """

    def __init__(self, health_monitor, station_fqdns):
        """
        Initialise a new StationsResourceManager.

        :param health_monitor: Provides for monitoring of health states
        :type health_monitor: :py:class:`ska.low.mccs.health.HealthModel` object
        :param station_fqdns: the FQDNs of the stations that this
            subarray manages
        :type station_fqdns: list(str)
        """
        self._devices = dict()
        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
        super().__init__(health_monitor, "Stations Resource Manager", stations)

    def items(self):
        """
        Return the stations managed by this device.

        :return: A dictionary of Station IDs, FQDNs managed by this
            StationsResourceManager
        :rtype: dict
        """
        devices = dict()
        for key, resource in self._resources.items():
            devices[key] = resource._fqdn
        return devices

    def add_to_managed(self, stations):
        """
        Add new stations(s) to be managed by this resource manager, will
        also run InitialSetup() on stations.

        :param stations: The IDs and FQDNs of devices to add
        :type stations: dict
        """
        for station_fqdn in stations.values():
            if station_fqdn not in self.station_fqdns:
                station = tango.DeviceProxy(station_fqdn)
                station.InitialSetup()
                self._devices[station_fqdn] = station
        super()._add_to_managed(stations)

    def release_all(self):
        """
        Remove all stations from this resource manager.
        """
        self._remove_from_managed(self.get_all_fqdns())

    @property
    def station_fqdns(self):
        """
        Returns the FQDNs of currently assigned stations.

        :return: FQDNs of currently assigned stations
        :rtype: list(str)
        """
        return sorted(self.get_all_fqdns())

    @property
    def station_ids(self):
        """
        Returns the device IDs of currently assigned stations.

        :return: IDs of currently assigned stations
        :rtype: list(str)
        """
        return sorted(self._resources.keys())


class StationBeamsResourceManager(ResourceManager):
    """
    A simple manager for the pool of station beams that are assigned to
    a subarray.

    Inherits from ResourceManager.
    """

    def __init__(self, health_monitor, station_beam_fqdns, stations_manager):
        """
        Initialise a new StationBeamsResourceManager.

        :param health_monitor: Provides for monitoring of health states
        :type health_monitor: :py:class:`ska.low.mccs.health.HealthMonitor`
        :param station_beam_fqdns: the FQDNs of the station beams that this
            subarray manages
        :type station_beam_fqdns: list(str)
        :param stations_manager: the StationResourceManager holding the station
            devices belonging to the parent Subarray
        :type stations_manager:
            :py:class:`ska.low.mccs.subarray.StationsResourceManager` object
        """
        self._stations = stations_manager
        station_beams = {}
        for station_beam_fqdn in station_beam_fqdns:
            station_beam_id = int(station_beam_fqdn.split("/")[-1:][0])
            station_beams[station_beam_id] = station_beam_fqdn
        super().__init__(
            health_monitor,
            "Station Beams Resource Manager",
            station_beams,
            [HealthState.OK],
        )

    def __len__(self):
        """
        Return the number of stations assigned to this subarray resource
        manager.

        :return: the number of stations assigned to this subarray resource
            manager
        :rtype: int
        """
        return len(self.get_all_fqdns())

    def assign(self, station_beam_fqdns, station_fqdns):
        """
        Assign devices to this subarray resource manager.

        :param station_beam_fqdns: list of FQDNs of station beams to be assigned
        :type station_beam_fqdns: list(str)
        :param station_fqdns: list of FQDNs of stations to be assigned
        :type station_fqdns: list(str)
        """

        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
            if station_fqdn not in self._stations.station_fqdns:
                self._stations.add_to_managed(stations)

        station_beams = {}
        for station_beam_fqdn in station_beam_fqdns:
            station_beam_id = int(station_beam_fqdn.split("/")[-1:][0])
            station_beams[station_beam_id] = station_beam_fqdn
            station_beam = tango.DeviceProxy(station_beam_fqdn)
            station_beam.stationIds = sorted(stations.keys())
            # TODO for now assigning single station fqdn to station beam
            # for health monitoring, rather than an array
            # This will be the case when Subarray Beam is fully implemented
            station_beam.stationFqdn = station_fqdns[0]

        self._add_to_managed(station_beams)
        for station_beam_fqdn in station_beam_fqdns:
            station_beam = tango.DeviceProxy(station_beam_fqdn)
            station_beam.isBeamLocked = True
            self.update_resource_health(station_beam_fqdn, station_beam.healthState)

        super().assign(station_beams, list(stations.keys()))

    def scan(self, logger, argin):
        """
        Start a scan on the configured subarray resources.

        :param logger: the logger to be used.
        :type logger: :py:class:`logging.Logger`
        :param argin: JSON scan specification
        :type argin: str
        :return: A tuple containing a result code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        # TODO: station_beam_fqdns actually store subarray_bean_fqdns (for now)
        subarray_beam_device_proxies = []
        for subarray_beam_fqdn in self.station_beam_fqdns:
            device_proxy = backoff_connect(subarray_beam_fqdn, logger=logger)
            subarray_beam_device_proxies.append(device_proxy)

        result_failure = None
        error_message = ""
        for subarray_beam_device_proxy in subarray_beam_device_proxies:
            # TODO: Ideally we want to kick these off in parallel...
            (result_code, message) = subarray_beam_device_proxy.Scan(argin)
            if result_code in [ResultCode.FAILED, ResultCode.UNKNOWN]:
                error_message += message + " "
                result_failure = result_code

        return (result_failure, error_message)

    def release(self, station_beam_fqdns, station_fqdns):
        """
        Release devices from this subarray resource manager.

        :param station_beam_fqdns: list of  FQDNs of station beams to be released
        :type station_beam_fqdns: list(str)
        :param station_fqdns: list of  FQDNs of the stations which if assigned to,
            station beams should be released
        :type station_fqdns: list(str)
        """
        station_ids_to_release = []
        # release station beams assigned to station_fqdns
        for station_id, station_fqdn in self._stations.items().items():
            if station_fqdn in station_fqdns:
                station_ids_to_release.append(station_id)
        for station_beam in self._resources.values():
            if station_beam._assigned_to in station_ids_to_release:
                if station_beam.fqdn not in station_beam_fqdns:
                    station_beam_fqdns.append(station_beam.fqdn)

        # release station beams by given fqdns
        for station_beam_fqdn in station_beam_fqdns:
            station_beam = tango.DeviceProxy(station_beam_fqdn)
            station_beam.stationIds = []
            station_beam.stationFqdn = ""
        super().release(station_beam_fqdns)

    def release_all(self):
        """
        Release all devices from this subarray resource manager.
        """
        devices = self.get_all_fqdns()
        self.release(devices, list())
        self._stations.release_all()

    @property
    def station_beam_fqdns(self):
        """
        Returns the FQDNs of currently assigned station beams.

        :return: FQDNs of currently assigned station beams
        :rtype: list(str)
        """
        return sorted(self.get_all_fqdns())

    @property
    def station_fqdns(self):
        """
        Returns the FQDNs of currently assigned stations.

        :return: FQDNs of currently assigned stations
        :rtype: list(str)
        """
        return sorted(self._stations.values())


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
            device._command_result = None
            device.set_change_event("commandResult", True, False)

            device._scan_id = -1
            device._transient_buffer_manager = TransientBufferManager()

            device._station_fqdns = list()
            device._station_beam_fqdns = list()

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
                self._initialise_resource_management(device)
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

        def _initialise_resource_management(self, device):
            """
            Initialise the resource management for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device._station_pool_manager = StationsResourceManager(
                device.health_model._health_monitor, device._station_fqdns
            )
            device._station_beam_pool_manager = StationBeamsResourceManager(
                device.health_model._health_monitor,
                device._station_beam_fqdns,
                device._station_pool_manager,
            )
            resourcing_args = (
                device._station_beam_pool_manager,
                device.state_model,
                device.logger,
            )
            device.register_command_object(
                "AssignResources", device.AssignResourcesCommand(*resourcing_args)
            )
            device.register_command_object(
                "ReleaseResources", device.ReleaseResourcesCommand(*resourcing_args)
            )
            device.register_command_object(
                "ReleaseAllResources",
                device.ReleaseAllResourcesCommand(*resourcing_args),
            )

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        # TODO: Technical debt -- forced to register base class stuff rather than
        # calling super(), because AssignResources(), ReleaseResources() and
        # ReleaseAllResources() are registered on a thread, and
        # we don't want the super() method clobbering them
        args = (self, self.state_model, self.logger)
        self.register_command_object("On", self.OnCommand(*args))
        self.register_command_object("Off", self.OffCommand(*args))
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("Scan", self.ScanCommand(*args))
        self.register_command_object("EndScan", self.EndScanCommand(*args))
        self.register_command_object("End", self.EndCommand(*args))
        self.register_command_object("Abort", self.AbortCommand(*args))
        self.register_command_object("ObsReset", self.ObsResetCommand(*args))
        self.register_command_object("Restart", self.RestartCommand(*args))
        self.register_command_object(
            "SendTransientBuffer",
            self.SendTransientBufferCommand(
                self._transient_buffer_manager, self.state_model, self.logger
            ),
        )
        self.register_command_object(
            "GetVersionInfo", self.GetVersionInfoCommand(*args)
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
        pass

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

    @attribute(dtype="DevLong", format="%i", polling_period=1000)
    def commandResult(self):
        """
        Return the commandResult attribute.

        :return: commandResult attribute
        :rtype: :py:class:`~ska.base.commands.ResultCode`
        """
        return self._command_result

    @attribute(dtype="DevLong", format="%i", polling_period=1000)
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

    @attribute(dtype=("DevString",), max_dim_x=512, format="%s", polling_period=1000)
    def stationFQDNs(self):
        """
        Return the FQDNs of stations assigned to this subarray.

        :return: FQDNs of stations assigned to this subarray
        :rtype: list(str)
        """
        return sorted(self._station_pool_manager.station_fqdns)

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

            :param argin: json string with the resources to be assigned
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            kwargs = json.loads(argin)
            stations = kwargs.get("stations", [])
            subarray_beams = kwargs.get("subarray_beams", [])
            # TODO: Are channels required in subarray during allocation or are they
            # only required in MCCSController? Remove noqa upon decision
            channels = kwargs.get("channels", [])  # noqa: F841
            station_beam_pool_manager = self.target
            station_beam_pool_manager.assign(subarray_beams, stations)

            # TODO: Should we always return success?
            return [ResultCode.OK, "AssignResources command completed successfully"]

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target) == 0:
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
            kwargs = json.loads(argin)
            stations = kwargs.get("station_fqdns", [])
            subarray_beams = kwargs.get("subarray_beam_fqdns", [])
            station_beam_pool_manager = self.target
            station_beam_pool_manager.release(subarray_beams, stations)
            return [ResultCode.OK, "ReleaseResources command completed successfully"]

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target):
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
            try:
                device.release_all()
            except ValueError as val:
                return (ResultCode.FAILED, f"ReleaseAllResources command failed: {val}")

            device._health_monitor.remove_all_devices()
            return (ResultCode.OK, "ReleaseAllResources command completed successfully")

        def succeeded(self):
            """
            Action to take on successful completion of a resourcing
            command.
            """
            if len(self.target):
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
                        {
                        "stations":[{"station_id": 1},{"station_id": 2}],
                        "subarray_beams":[{
                        "subarray_id":1,
                        "subarray_beam_id":1,
                        "station_ids":[1,2],
                        "channels":  [[0, 8, 1, 1], [8, 8, 2, 1]],
                        "update_rate": 0.0,
                        "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0]}]
                        }
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            kwargs = json.loads(argin)
            stations = kwargs.get("stations", list())
            station_beam_pool_manager = self.target._station_beam_pool_manager
            for station in stations:
                # This is here for future expansion of json strings
                station.get("station_id")

            subarray_beams = kwargs.get("subarray_beams", list())
            for subarray_beam in subarray_beams:
                subarray_beam_id = subarray_beam.get("subarray_beam_id")
                if subarray_beam_id:
                    subarray_beam_fqdn = station_beam_pool_manager.fqdn_from_id(
                        subarray_beam_id
                    )
                    if subarray_beam_fqdn:
                        dp = tango.DeviceProxy(subarray_beam_fqdn)
                        json_str = json.dumps(subarray_beam)
                        dp.configure(json_str)

            result_code = ResultCode.OK
            message = "Configure command completed successfully"
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

            device = self.target
            kwargs = json.loads(argin)
            device._scan_id = kwargs.get("id")
            device._scan_time = kwargs.get("scan_time")

            station_beam_pool_manager = self.target._station_beam_pool_manager
            (pool_failure_code, pool_message) = station_beam_pool_manager.scan(
                self.logger, argin
            )
            if not pool_failure_code:
                return (result_code, message)
            else:
                return (pool_failure_code, pool_message)

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

            An abort command will leave the system in an ABORTED state.
            Output to CSP is stopped, as is the beamformer and all running
            jobs. The system can then be inspected in the ABORTED state
            before it's de-configured and returned to the IDLE state by the
            ObsReset command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # TODO: MCCS-specific stuff goes here
            # 1. Interrupt the current running scan, like EndScan
            #    but with a little more urgency:
            #    a. Send an Abort to the Subarray Beam
            #    b. Subarray beam raises an alarm to highlight the Abort
            #    c. Subarray Beam sends Abort to Station Beams
            #    d. Station Beam send Abort to Station
            #    e. Station sends Abort to Tile
            #    f. Tile sends Abort to the TPM:
            #       a. Output to CSP is first stopped to avoid invalid data being
            #          transmitted while aborting the observation
            #       b. Stop the beam former in the TPM
            # 2. Send Abort to the Cluster Manager to stop all running jobs

            # TODO: Remove this delay. It simply emulates the time to achieve the above.
            time.sleep(1)

            return (result_code, message)

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :todo: The Abort command is currently limited based on the
                available implementaion of MCCS.

            :return: True if this command is allowed to be run in
                current device obsstates
            :rtype: bool
            """
            return self.state_model.obs_state in [ObsState.SCANNING]

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Abort(self):
        """
        Abort any long-running command such as ``Configure()`` or
        ``Scan()``.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        self._command_result = DevState.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("Abort")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

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

            # TODO: MCCS-specific stuff goes here
            # 1. All jobs should be terminated (via the Cluster manager)
            # 2. All elements should be deconfigured (as if they had just
            #    been allocated).

            # TODO: Remove this delay. It simply emulates the time to achieve the above.
            time.sleep(1)

            return (result_code, message)

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :todo: The ObsReset command is currently limited based on the
                available implementaion of MCCS.

            :return: True if this command is allowed to be run in
                current device obsstates
            :rtype: bool
            """
            return self.state_model.obs_state in [ObsState.ABORTED]

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def ObsReset(self):
        """
        Reset the current observation process.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        self._command_result = ResultCode.UNKNOWN
        self.push_change_event("commandResult", self._command_result)
        command = self.get_command_object("ObsReset")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

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

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
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
