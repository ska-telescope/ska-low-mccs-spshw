# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
This module implements MCCS functionality for monitoring and control of subarrays.

It does this mainly by defining MccsSubarray, a Tango device class for
MCCS subarrays.
"""

from __future__ import annotations  # allow forward references in type hints

__all__ = [
    "MccsSubarray",
    "SubarrayBeamsResourceManager",
    "main",
]

# imports
import json
import logging
import threading
from typing import List, Optional, Tuple

# PyTango imports
from tango import DebugIt, EnsureOmniThread, Group
from tango.server import attribute, command

# Additional import
from ska_tango_base import SKASubarray
from ska_tango_base.commands import ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, ObsState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.health import MutableHealthModel, HealthMonitor
import ska_low_mccs.release as release
from ska_low_mccs.resource import ResourceManager
from ska_low_mccs.message_queue import MessageQueue  # type: ignore[attr-defined]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsSubarrayQueue(MessageQueue):
    """A concrete implementation of a message queue specific to MccsSubarray."""

    def _notify_listener(
        self: MccsSubarrayQueue,
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


class StationsResourceManager(ResourceManager):
    """
    A simple manager for the pool of stations that are assigned to a subarray.

    Inherits from ResourceManager.
    """

    def __init__(
        self: StationsResourceManager,
        health_monitor: HealthMonitor,
        station_fqdns: List[str],
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new StationsResourceManager.

        :param health_monitor: Provides for monitoring of health states
        :param station_fqdns: the FQDNs of the stations that this
            subarray manages
        :param logger: the logger to be used by the object under test
        """
        self._devices = dict()
        stations = {}
        for station_fqdn in station_fqdns:
            station_id = int(station_fqdn.split("/")[-1:][0])
            stations[station_id] = station_fqdn
        super().__init__(health_monitor, "Stations Resource Manager", stations, logger)

    def items(self: StationsResourceManager):
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
        Add new stations(s) to be managed by this resource manager, will also run
        InitialSetup() on stations.

        :param stations: The IDs and FQDNs of devices to add
        :type stations: dict
        """
        for station_fqdn in stations.values():
            if station_fqdn not in self.station_fqdns:
                # TODO: Establishment of connections should happen at initialization
                station = MccsDeviceProxy(station_fqdn, logger=self._logger)
                station.InitialSetup()
                self._devices[station_fqdn] = station
        super()._add_to_managed(stations)

    def release_all(self):
        """Remove all stations from this resource manager."""
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


class SubarrayBeamsResourceManager(ResourceManager):
    """
    A simple manager for the pool of subarray beams that are assigned to a subarray.

    Inherits from ResourceManager.
    """

    def __init__(
        self: SubarrayBeamsResourceManager,
        health_monitor: HealthMonitor,
        subarray_beam_fqdns: List[str],
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new SubarrayBeamsResourceManager.

        :param health_monitor: Provides for monitoring of health states
        :param subarray_beam_fqdns: the FQDNs of the subarray_beams that this
            subarray manages
        :type subarray_beam_fqdns: list(str)
        :param logger: the logger to be used by the object under test
        """
        self.assigned_station_fqdns = []
        subarray_beams = {}
        for subarray_beam_fqdn in subarray_beam_fqdns:
            subarray_beam_id = int(subarray_beam_fqdn.split("/")[-1:][0])
            subarray_beams[subarray_beam_id] = subarray_beam_fqdn
        super().__init__(
            health_monitor,
            "Station Beams Resource Manager",
            subarray_beams,
            logger,
            [HealthState.OK],
        )

    def __len__(self) -> int:
        """
        Return the number of stations assigned to this subarray resource manager.

        :return: the number of stations assigned to this subarray resource manager
        """
        return len(self.get_all_fqdns())

    def assign(
        self: SubarrayBeamsResourceManager,
        subarray_beam_fqdns: List[str],
        station_fqdns: list[List[str]],
    ) -> None:
        """
        Assign devices to this subarray resource manager.

        :param subarray_beam_fqdns: list of FQDNs of station beams to be assigned
        :param station_fqdns: list of FQDNs of stations to be assigned
        """
        stations = {}

        station_ids_per_beam = []
        for station_sub_fqdns in station_fqdns:
            station_id_sublist = []
            for station_fqdn in station_sub_fqdns:
                station_id = int(station_fqdn.split("/")[-1:][0])
                stations[station_id] = station_fqdn
                station_id_sublist.append(station_id)
                if station_fqdn not in self.assigned_station_fqdns:
                    self.assigned_station_fqdns.append(station_fqdn)
            station_ids_per_beam.append(station_id_sublist)
        subarray_beams = {}
        subarray_beam_group = Group("subarray_beam_group")
        subarray_beam_station_ids = list()
        for index, subarray_beam_fqdn in enumerate(subarray_beam_fqdns):
            subarray_beam_id = int(subarray_beam_fqdn.split("/")[-1:][0])
            subarray_beams[subarray_beam_id] = subarray_beam_fqdn
            subarray_beam_group.add(subarray_beam_fqdn)

            # TODO: Establishment of connections should happen at initialization
            # subarray_beam = MccsDeviceProxy(subarray_beam_fqdn, logger=self._logger)
            # subarray_beam.stationIds = sorted(station_ids_per_beam[index])
            subarray_beam_station_ids.append(sorted(station_ids_per_beam[index]))
        subarray_beam_group.write_attribute_asynch(
            "stationIds", subarray_beam_station_ids, True, True
        )

        self._add_to_managed(subarray_beams)

        subarray_beam_group.write_attribute_asynch("isBeamLocked", True)
        subarray_beam_health_states = subarray_beam_group.read_attribute("healthState")

        for index, subarray_beam_fqdn in enumerate(subarray_beam_fqdns):

            # TODO: Establishment of connections should happen at initialization
            # subarray_beam = MccsDeviceProxy(subarray_beam_fqdn, logger=self._logger)

            # subarray_beam.isBeamLocked = True
            self.update_resource_health(
                subarray_beam_fqdn, subarray_beam_health_states[index]
            )

        self._health_monitor.add_devices(stations.values())

        super().assign(subarray_beams, list(stations.keys()))

    def configure(
        self: SubarrayBeamsResourceManager, logger: logging.Logger, argin: str
    ) -> Tuple[ResultCode, str]:
        """
        Configure devices from this subarray resource manager.

        :param logger: the logger to be used.
        :param argin: JSON configuration specification
            {
            "interface": "https://schema.skao.int/ska-low-mccs-configure/2.0",
            "stations":[{"station_id": 1},{"station_id": 2}],
            "subarray_beams":[{
            "subarray_beam_id":1,
            "station_ids":[1,2],
            "update_rate": 0.0,
            "channels":  [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
            "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
            "antenna_weights": [1.0, 1.0, 1.0],
            "phase_centre": [0.0, 0.0],
            }]
            }

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        kwargs = json.loads(argin)
        stations = kwargs.get("stations", list())
        for station in stations:
            # TODO: This is here for future expansion of json strings
            station.get("station_id")

        subarray_beams = kwargs.get("subarray_beams", list())
        for subarray_beam in subarray_beams:
            subarray_beam_id = subarray_beam.get("subarray_beam_id")
            if subarray_beam_id:
                subarray_beam_fqdn = self.fqdn_from_id(subarray_beam_id)
                if subarray_beam_fqdn:
                    # TODO: Establishment of connections should happen at initialization
                    dp = MccsDeviceProxy(subarray_beam_fqdn, logger=logger)

                    json_str = json.dumps(subarray_beam)
                    dp.configure(json_str)

        result_code = ResultCode.OK
        message = MccsSubarray.ConfigureCommand.SUCCEEDED_MESSAGE
        return (result_code, message)

    def scan(
        self: SubarrayBeamsResourceManager, logger: logging.Logger, argin: str
    ) -> Tuple[ResultCode, str]:
        """
        Start a scan on the configured subarray resources.

        :param logger: the logger to be used.
        :param argin: JSON scan specification

        :return: A tuple containing a result code and a string
        """
        subarray_beam_device_proxies = []
        for subarray_beam_fqdn in self.subarray_beam_fqdns:
            # TODO: Establishment of connections should be happening at initialization
            device_proxy = MccsDeviceProxy(subarray_beam_fqdn, logger=logger)
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

    def release(
        self: SubarrayBeamsResourceManager,
        subarray_beam_fqdns: List[str],
        station_fqdns: List[str],
    ) -> None:
        """
        Release devices from this subarray resource manager.

        :param subarray_beam_fqdns: list of  FQDNs of subarray_beams to be released
        :param station_fqdns: list of  FQDNs of the stations which if assigned to,
            subarray_beams should be released
        """
        station_ids_to_release = [
            int(station_fqdn.split("/")[-1:][0]) for station_fqdn in station_fqdns
        ]

        for subarray_beam in self._resources.values():
            if subarray_beam._assigned_to in station_ids_to_release:
                if subarray_beam.fqdn not in subarray_beam_fqdns:
                    subarray_beam_fqdns.append(subarray_beam.fqdn)

        # release subarray_beams by given fqdns
        for subarray_beam_fqdn in subarray_beam_fqdns:
            # TODO: Establishment of connections should happen at initialization
            subarray_beam = MccsDeviceProxy(subarray_beam_fqdn, logger=self._logger)

            subarray_beam.stationIds = []
            subarray_beam.stationFqdn = None
        super().release(subarray_beam_fqdns)

    def release_all(self: SubarrayBeamsResourceManager) -> None:
        """Release all devices from this subarray resource manager."""
        devices = self.get_all_fqdns()
        self.release(devices, list())
        self.assigned_station_fqdns = []

    @property
    def subarray_beam_fqdns(self: SubarrayBeamsResourceManager) -> List[str]:
        """
        Returns the FQDNs of currently assigned subarray_beams.

        :return: FQDNs of currently assigned subarray_beams
        """
        return sorted(self.get_all_fqdns())

    @property
    def station_fqdns(self) -> List[str]:
        """
        Returns the FQDNs of currently assigned stations.

        :return: FQDNs of currently assigned stations
        """
        return sorted(self.assigned_station_fqdns)


class TransientBufferManager:
    """
    Stub class for management of a transient buffer.

    Currently does nothing useful
    """

    def __init__(self):
        """Construct a new TransientBufferManager."""
        pass

    def send(self, segment_spec):
        """
        Instructs the manager to send the specified segments of the transient buffer.

        :param segment_spec: JSON-encoded specification of the segment
            to be sent
        :type segment_spec: str
        """
        pass


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray prototype.

    This is a subclass of :py:class:`ska_tango_base.SKASubarray`.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKASubarray.InitCommand):
        """Command class for device initialisation."""

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
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False
            self._message_queue = None
            self._qdebuglock = threading.Lock()

        def do(self):
            """
            Stateless hook for initialisation of the attributes and properties of the
            :py:class:`.MccsSubarray`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            device = self.target
            device._command_result = {
                "result_code": ResultCode.UNKNOWN,
                "message_uid": "",
                "status": "",
            }
            device.set_change_event("commandResult", True, False)

            device._heart_beat = 0
            device.queue_debug = ""
            device._scan_id = -1
            device._transient_buffer_manager = TransientBufferManager()

            device._station_beam_fqdns = list()
            device._subarray_beam_fqdns = list()

            device._build_state = release.get_release_info()
            device._version_id = release.version

            # Start the Message queue for this device
            device._message_queue = MccsSubarrayQueue(
                target=device, lock=self._qdebuglock, logger=self.logger
            )
            device._message_queue.start()

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections to external
            entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
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
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device._health_state = HealthState.OK
            device.set_change_event("healthState", True, False)
            device.health_model = MutableHealthModel(
                None, [], self.logger, device.health_changed
            )

        def _initialise_resource_management(self, device):
            """
            Initialise the resource management for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            device._subarray_beam_resource_manager = SubarrayBeamsResourceManager(
                device.health_model._health_monitor,
                device._subarray_beam_fqdns,
                self.logger,
            )
            resourcing_args = (
                device._subarray_beam_resource_manager,
                device.state_model,
                device.logger,
            )
            for (command_name, command_object) in [
                ("AssignResources", device.AssignResourcesCommand),
                ("ReleaseResources", device.ReleaseResourcesCommand),
                ("ReleaseAllResources", device.ReleaseAllResourcesCommand),
                ("Restart", device.RestartCommand),
            ]:
                device.register_command_object(
                    command_name,
                    command_object(*resourcing_args),
                )

    def init_command_objects(self):
        """Initialises the command handlers for commands supported by this device."""
        # TODO: Technical debt -- forced to register base class stuff rather than
        # calling super(), because AssignResources(), ReleaseResources() and
        # ReleaseAllResources() are registered on a thread, and
        # we don't want the super() method clobbering them
        for (command_name, command_object) in [
            ("On", self.OnCommand),
            ("Off", self.OffCommand),
            ("Configure", self.ConfigureCommand),
            ("Scan", self.ScanCommand),
            ("EndScan", self.EndScanCommand),
            ("End", self.EndCommand),
            ("Abort", self.AbortCommand),
            ("ObsReset", self.ObsResetCommand),
            ("GetVersionInfo", self.GetVersionInfoCommand),
        ]:
            self.register_command_object(
                command_name, command_object(self, self.state_model, self.logger)
            )

        self.register_command_object(
            "SendTransientBuffer",
            self.SendTransientBufferCommand(
                self._transient_buffer_manager, self.state_model, self.logger
            ),
        )

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

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
        if self._message_queue.is_alive():
            self._message_queue.terminate_thread()
            self._message_queue.join()

    def notify_listener(
        self: MccsSubarrayQueue,
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

    # ------------------
    # Attribute methods
    # ------------------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state changes;
        responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevULong")
    def aHeartBeat(self: MccsSubarray) -> int:
        """
        Return the Heartbeat attribute value.

        :return: heart beat as a percentage
        """
        return self._heart_beat

    @attribute(dtype="DevString")
    def aQueueDebug(self: MccsSubarray) -> str:
        """
        Return the queueDebug attribute.

        :return: queueDebug attribute
        """
        return self.queue_debug

    @aQueueDebug.write  # type: ignore[no-redef]
    def aQueueDebug(self: MccsSubarray, debug_string: str) -> None:
        """
        Update the queue debug attribute.

        :param debug_string: the new debug string for this attribute
        """
        self.queue_debug = debug_string

    @attribute(dtype="DevString", format="%i")
    def commandResult(self: MccsSubarray) -> str:
        """
        Return the _command_result attributes.

        :return: JSON encoded _command_results attributes map
        :rtype: str
        """
        json_results = json.dumps(self._command_result)
        return json_results

    @attribute(dtype="DevLong", format="%i")
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
        dtype=[
            "DevString",
        ],
        max_dim_x=512,
        format="%s",
    )
    # Attribute defined as a list, but being returned as a tuple.
    # There is also a Tango bug in which an empty list is written/read as None
    # (hence extra logic) which may be related, see for instance
    # https://github.com/tango-controls/pytango/issues/229 and
    # and https://github.com/tango-controls/pytango/issues/230
    def stationFQDNs(self):
        """
        Return the FQDNs of stations assigned to this subarray.

        :return: FQDNs of stations assigned to this subarray
        :rtype: list(str)
        """
        if len(self._subarray_beam_resource_manager.assigned_station_fqdns or []) == 0:
            return list()
        return list(self._subarray_beam_resource_manager.assigned_station_fqdns)

    @stationFQDNs.write
    def stationFQDNs(self, station_fqdns):
        """
        Set the stationFQDNs attribute.

        :param station_fqdns: the new stationFQDNs
        :type station_fqdns: list(str)
        """
        self._subarray_beam_resource_manager.assigned_station_fqdns = list(
            station_fqdns or []
        )

    # -------------------------------------------
    # Base class command and gatekeeper overrides
    # -------------------------------------------
    def _send_message(
        self: MccsSubarray, command: str, json_args: str
    ) -> DevVarLongStringArrayType:
        """
        Helper method to send a message to execute the specified command.

        :param command: the command to send a message for
        :param json_args: arguments to pass with the command

        :return: A tuple containing a return code, a string
            message indicating status and message UID.
            The string message is for information purposes only, but
            the message UID is for message management use.
        """
        self.logger.info(f"Subarray {command}")

        kwargs = json.loads(json_args)
        respond_to_fqdn = kwargs.get("respond_to_fqdn")
        callback = kwargs.get("callback")
        assert respond_to_fqdn
        assert callback
        self.logger.debug(f"Subarray {command} message call")
        (
            result_code,
            message_uid,
            status,
        ) = self._message_queue.send_message_with_response(
            command=command, respond_to_fqdn=respond_to_fqdn, callback=callback
        )
        return [[result_code], [status, message_uid]]

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    @DebugIt()
    def On(self: MccsSubarray, json_args: str) -> DevVarLongStringArrayType:
        """
        Send a message to turn the subarray on.

        Method returns as soon as the message has been enqueued.

        :param json_args: JSON encoded messaging system and command arguments

        :return: A tuple containing a return code, a string
            message indicating status and message UID.
            The string message is for information purposes only, but
            the message UID is for message management use.
        """
        return self._send_message(command="On", json_args=json_args)

    class OnCommand(SKASubarray.OnCommand):
        """Class for handling the On() command."""

        SUCCEEDED_MESSAGE = "Subarray On command completed OK"
        FAILED_MESSAGE = "Subarray On command failed"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.On` command for this
            :py:class:`.MccsSubarray` device.

            :param argin: Argument containing JSON encoded command message and result
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, _) = super().do()

            # MCCS-specific stuff goes here

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class OffCommand(SKASubarray.OffCommand):
        """Class for handling the Off() command."""

        SUCCEEDED_MESSAGE = "Off command completed OK"
        FAILED_MESSAGE = "Off command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKABaseDevice.Off` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, _) = super().do()

            # MCCS-specific stuff goes here

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    class AssignResourcesCommand(SKASubarray.AssignResourcesCommand):
        """Class for handling the AssignResources(argin) command."""

        SUCCEEDED_MESSAGE = "AssignResources command completed OK"
        FAILED_MESSAGE = "AssignResources command failed"

        def do(self, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the
            (inherited)
            :py:meth:`ska_tango_base.SKASubarray.AssignResources`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: json string with the resources to be assigned
                {
                "subarray_beams": ["low-mccs/subarraybeam/01"],
                "stations": [["low-mccs/station/001", "low-mccs/station/002"]],
                "channel_blocks": [3]
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            kwargs = json.loads(argin)
            station_fqdns = kwargs.get("stations", [])
            subarray_beam_fqdns = kwargs.get("subarray_beams", [])
            # TODO: Are channels required in subarray during allocation or are they
            # only required in MCCSController? Remove noqa upon decision
            channel_blocks = kwargs.get("channel_blocks", [])  # noqa: F841
            subarray_beam_resource_manager = self.target
            if len(subarray_beam_fqdns) == len(station_fqdns):
                subarray_beam_resource_manager.assign(
                    subarray_beam_fqdns, station_fqdns
                )
            else:
                self.logger.error(
                    f"There is a mismatch between len({subarray_beam_fqdns}) and len({station_fqdns})"
                )
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

            # TODO: Should we always return success?
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def succeeded(self):
            """Action to take on successful completion of a resourcing command."""
            if len(self.target) == 0:
                action = "resourcing_succeeded_no_resources"
            else:
                action = "resourcing_succeeded_some_resources"
            self.state_model.perform_action(action)

    class ReleaseResourcesCommand(SKASubarray.ReleaseResourcesCommand):
        """Class for handling the ReleaseResources(argin) command."""

        SUCCEEDED_MESSAGE = "ReleaseResources command completed OK"

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            (inherited)
            :py:meth:`ska_tango_base.SKASubarray.ReleaseResources`
            command for this :py:class:`.MccsSubarray` device.

            :param argin: The resources to be released
            :type argin: list(str)

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            kwargs = json.loads(argin)
            stations = kwargs.get("station_fqdns", [])
            subarray_beams = kwargs.get("subarray_beam_fqdns", [])
            subarray_beam_resource_manager = self.target
            subarray_beam_resource_manager.release(subarray_beams, stations)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def succeeded(self):
            """Action to take on successful completion of a resourcing command."""
            if len(self.target):
                action = "resourcing_succeeded_some_resources"
            else:
                action = "resourcing_succeeded_no_resources"
            self.state_model.perform_action(action)

    class ReleaseAllResourcesCommand(SKASubarray.ReleaseAllResourcesCommand):
        """Class for handling the ReleaseAllResources() command."""

        SUCCEEDED_MESSAGE = "ReleaseAllResources command completed OK"
        FAILED_MESSAGE_PREFIX = "ReleaseAllResources command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the
            (inherited)
            :py:meth:`ska_tango_base.SKASubarray.ReleaseAllResources`
            command for this :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            # deliberately not calling super() -- we're passing a different
            # target object
            device = self.target
            try:
                device.release_all()
            except ValueError as val:
                return (ResultCode.FAILED, f"{self.FAILED_MESSAGE_PREFIX}: {val}")

            device._health_monitor.remove_all_devices()
            device.assigned_station_fqdns = []
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

        def succeeded(self):
            """Action to take on successful completion of a resourcing command."""
            if len(self.target):
                action = "resourcing_succeeded_some_resources"
            else:
                action = "resourcing_succeeded_no_resources"
            self.state_model.perform_action(action)

    class ConfigureCommand(SKASubarray.ConfigureCommand):
        """Class for handling the Configure(argin) command."""

        SUCCEEDED_MESSAGE = "Configure command completed OK"

        def do(self, argin: str):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.Configure` command for this
            :py:class:`.MccsSubarray` device.

            :param argin: JSON configuration specification
                {
                "interface": "https://schema.skao.int/ska-low-mccs-configure/2.0",
                "stations":[{"station_id": 1},{"station_id": 2}],
                "subarray_beams":[{
                "subarray_beam_id":1,
                "station_ids":[1,2],
                "update_rate": 0.0,
                "channels":  [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0]}]
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            subarray_beam_resource_manager = self.target._subarray_beam_resource_manager
            return subarray_beam_resource_manager.configure(self.logger, argin)

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device state.

            :return: True if this command is allowed to be run in
                current device obsstates
            :rtype: bool
            """
            return self.state_model.obs_state in [ObsState.IDLE, ObsState.READY]

    class ScanCommand(SKASubarray.ScanCommand):
        """Class for handling the Scan(argin) command."""

        def do(self, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.Scan` command for this
            :py:class:`.MccsSubarray` device.

            :param argin: JSON scan specification
                {
                "interface": "https://schema.skao.int/ska-low-mccs-scan/2.0",
                "scan_id":1,
                "start_time": 0.0,
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do(argin)

            device = self.target
            kwargs = json.loads(argin)
            device._scan_id = kwargs.get("scan_id")
            device._scan_time = kwargs.get("start_time")

            subarray_beam_resource_manager = device._subarray_beam_resource_manager
            (
                resource_failure_code,
                resource_message,
            ) = subarray_beam_resource_manager.scan(self.logger, argin)
            if not resource_failure_code:
                return (result_code, message)
            else:
                return (resource_failure_code, resource_message)

    class EndScanCommand(SKASubarray.EndScanCommand):
        """Class for handling the EndScan() command."""

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.EndScan` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class EndCommand(SKASubarray.EndCommand):
        """Class for handling the End() command."""

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.End` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            # MCCS-specific stuff goes here
            return (result_code, message)

    class AbortCommand(SKASubarray.AbortCommand):
        """Class for handling the Abort() command."""

        SUCCEEDED_MESSAGE = "Abort command completed OK"
        FAILED_MESSAGE = "Abort command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.Abort` command for this
            :py:class:`.MccsSubarray` device.

            An abort command will leave the system in an ABORTED state.
            Output to CSP is stopped, as is the beamformer and all running
            jobs. The system can then be inspected in the ABORTED state
            before it's de-configured and returned to the IDLE state by the
            ObsReset command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, _) = super().do()

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
            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    @DebugIt()
    def Abort(self):
        """
        Abort any long-running command such as ``Configure()`` or ``Scan()``.

        To modify behaviour for this command, modify the do() method of
        the command class.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        command = self.get_command_object("Abort")
        (result_code, status) = command()
        self.notify_listener(result_code, "", status)
        return ([result_code], [status])

    class ObsResetCommand(SKASubarray.ObsResetCommand):
        """Class for handling the ObsReset() command."""

        SUCCEEDED_MESSAGE = "ObsReset command completed OK"
        FAILED_MESSAGE = "ObsReset command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.ObsReset` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, _) = super().do()

            # TODO: MCCS-specific stuff goes here
            # 1. All jobs should be terminated (via the Cluster manager)
            # 2. All elements should be deconfigured (as if they had just
            #    been allocated).

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

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
        :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
        """
        self.notify_listener(ResultCode.UNKNOWN, "", "")
        command = self.get_command_object("ObsReset")
        (result_code, status) = command()
        self.notify_listener(result_code, "", status)
        return ([result_code], [status])

    class RestartCommand(SKASubarray.RestartCommand):
        """Class for handling the Restart() command."""

        SUCCEEDED_MESSAGE = "RestartCommand command completed OK"
        FAILED_MESSAGE_PREFIX = "RestartCommand command failed"

        def do(self):
            """
            Stateless hook implementing the functionality of the (inherited)
            :py:meth:`ska_tango_base.SKASubarray.Restart` command for this
            :py:class:`.MccsSubarray` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            device = self.target
            try:
                device.release_all()
            except ValueError as val:
                return (ResultCode.FAILED, f"{self.FAILED_MESSAGE_PREFIX}: {val}")

            device._health_monitor.remove_all_devices()
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    # ---------------------
    # MccsSubarray Commands
    # ---------------------

    class SendTransientBufferCommand(ResponseCommand):
        """Class for handling the SendTransientBuffer(argin) command."""

        SUCCEEDED_MESSAGE = "SendTransientBuffer command completed OK"

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
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            transient_buffer_manager = self.target
            transient_buffer_manager.send(argin)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevVarLongArray", dtype_out="DevVarLongStringArray")
    @DebugIt()
    def SendTransientBuffer(self, argin):
        """
        Cause the subarray to send the requested segment of the transient buffer to SDP.
        The requested segment is specified by:

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
        (result_code, status) = handler(argin)
        return [[result_code], [status]]


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
