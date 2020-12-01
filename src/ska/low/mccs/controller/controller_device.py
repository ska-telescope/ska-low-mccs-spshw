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

__all__ = [
    "MccsController",
    "ControllerResourceManager",
    "ControllerPowerManager",
    "main",
]

import json
import threading
from enum import Enum

# PyTango imports
import tango
from tango import DebugIt, DevFailed, DevState, EnsureOmniThread
from tango.server import attribute, command, device_property

# Additional import
from ska.base import SKAMaster, SKABaseDevice
from ska.base.control_model import HealthState
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
        Initialise a new ControllerPowerManager.

        :param station_fqdns: the FQDNs of the stations that this controller
            device manages
        :type station_fqdns: list(str)
        """
        super().__init__(None, station_fqdns)


class ControllerResourceManager:
    """
    This class implements a resource manger for the MCCS controller
    device.

    Initialize with a list of FQDNs of devices to be managed. The
    ControllerResourceManager holds the FQDN and the (1-based) ID of the
    device that owns each managed device.
    """

    class ResourceState(Enum):
        """
        This enum describes a resource's assigned state.

        * A resource which is UNAVAILABLE cannot be assigned.
        * A resource which is AVAILABLE can be assigned.
        * A resource which is ASSIGNED cannot be assigned until the
          original assignment has been released.
        """

        UNAVAILABLE = 1
        """
        The resource is unallocated and cannot be allocated; for
        example, it is in a fault state
        """

        AVAILABLE = 2
        """
        The resource is unallocated and available for allocation
        """

        ASSIGNED = 3
        """
        The resource is allocated.
        """

    class ResourceAvailabilityPolicy:
        """
        This inner class implements a resource allocation policy for the
        resources belonging to the parent.

        Initialise with a list of allocatable health states:
        (OK = 0, DEGRADED = 1, FAILED = 2, UNKNOWN = 3).
        Defaults to [OK]
        """

        def __init__(self, allocatable_health_states=[HealthState.OK]):
            """
            Create a new instance.

            :param allocatable_health_states: list of health states that
                are to be regarded as okay to allocate, defaults to only
                OK
            :type allocatable_health_states: list of
                :py:class:`~ska.base.control_model.HealthState`
            """
            self._allocatable_health_states = list(allocatable_health_states)

        def is_allocatable(self, health_state):
            """
            Check if a state allows allocation.

            :param health_state: The state of health to check
            :type health_state: int

            :return: True if this is suitable for allocation
            :rtype: bool
            """
            return health_state in self._allocatable_health_states

        def assign_allocatable_health_states(self, health_states):
            """
            Set the health states allowed for allocation.

            :param health_states: Allowed health states
            :type health_states: list(int)
            """
            self._allocatable_health_states = list(health_states)

        def reset(self):
            """
            Reset to the default set of states allowed for allocation.
            """
            self._allocatable_health_states = [HealthState.OK]

    class Resource:
        """
        This inner class implements state recording for a managed
        resource.

        Initialise with a device id number.
        """

        def __init__(self, availability_policy, fqdn):
            """
            Initialise a new Resource instance.

            :param availability_policy: the policy associated with this
                device
            :type availability_policy:
                :py:class:`.ResourceAvailabilityPolicy`
            :param fqdn: FQDN of supervised device
            :type fqdn: str
            """
            self._resource_availability_policy = availability_policy
            self._fqdn = fqdn
            self._resource_state = ControllerResourceManager.ResourceState.AVAILABLE
            self._assigned_to = 0
            self._health_state = HealthState.UNKNOWN

        def assigned_to(self):
            """
            Get the ID to which this resource is assigned.

            :return: Device ID
            :rtype: int
            """
            return self._assigned_to

        def is_assigned(self):
            """
            Check if this resource is assigned.

            :return: True if assigned
            :rtype: bool
            """
            return (
                self._resource_state == ControllerResourceManager.ResourceState.ASSIGNED
                and self._assigned_to != 0
            )

        def is_available(self):
            """
            Check if this resource is AVAILABLE (for assignment)

            :return: True if available
            :rtype: bool
            """
            return (
                self._resource_state
                == ControllerResourceManager.ResourceState.AVAILABLE
            )

        def is_unavailable(self):
            """
            Check if this resource is UNAVAILABLE.

            :return: True if unavailable
            :rtype: bool
            """
            return (
                self._resource_state
                == ControllerResourceManager.ResourceState.UNAVAILABLE
            )

        def is_not_available(self):
            """
            Check if this resource is not available A resource is not
            available if it is ASSIGNED or UNAVAILABLE.

            :return: True if not unavailable
            :rtype: bool
            """
            return (
                self._resource_state
                == ControllerResourceManager.ResourceState.UNAVAILABLE
                or self._resource_state
                == ControllerResourceManager.ResourceState.ASSIGNED
            )

        def is_healthy(self):
            """
            Check if this resource is in a healthy state, as defined by
            its resource availability policy.

            :return: True if healthy
            :rtype: bool
            """
            return self._resource_availability_policy.is_allocatable(self._health_state)

        def _health_changed(self, fqdn, event_value):
            """
            Update the health state of the resource.

            :param fqdn: FQDN of the device for which healthState has
                changed
            :type fqdn: str
            :param event_value: the HealthState to assign to the
                resource
            :type event_value: int
            """
            assert fqdn == self._fqdn
            self._health_state = event_value

        def assign(self, owner):
            """
            Assign a resource to an owner.

            :param owner: Device ID of the owner
            :type owner: int

            :raises ValueError: if the named resource is already assigned
            :raises ValueError: if the named resource is unhealthy
            :raises ValueError: if the named resource is otherwise unavailable
            """
            # Don't allow assign if already assigned to another owner
            if self.is_assigned():
                if self._assigned_to != owner:
                    # Trying to assign to new owner not allowed
                    raise ValueError(
                        f"{self._fqdn} already assigned to {self._assignedTo}"
                    )
                # No action if repeating the existing assignment
                return
            # Don't allow assign if resource is not healthy
            if not self.is_healthy():
                raise ValueError(
                    f"{self._fqdn} does not pass health check for assignment"
                )

            if self.is_available():
                self._assigned_to = owner
                self._resource_state = ControllerResourceManager.ResourceState.ASSIGNED
            else:
                raise ValueError(f"{self._fqdn} is unavailable")

        def release(self):
            """
            Release the resource from assignment.

            :raises ValueError: if the resource was unassigned
            """
            if self._assigned_to == 0:
                raise ValueError(
                    f"Attempt to release unassigned resource, {self._fqdn}"
                )
            self._assigned_to = 0

            if self._resource_state == ControllerResourceManager.ResourceState.ASSIGNED:
                # Previously assigned resource becomes available
                if not self.is_healthy():
                    self.make_unavailable()
                else:
                    self._resource_state = (
                        ControllerResourceManager.ResourceState.AVAILABLE
                    )
            # Unassigned or unavailable resource does not change state

        def make_unavailable(self):
            """
            Mark the resource as unavailable for assignment.
            """
            # Change resource state to unavailable
            # If it was previously AVAILABLE (not ASSIGNED) we can just switch
            if self.is_available():
                self._resource_state = (
                    ControllerResourceManager.ResourceState.UNAVAILABLE
                )
            elif (
                self._resource_state == ControllerResourceManager.ResourceState.ASSIGNED
            ):
                # TODO
                # We must decide what to do with rescources that were assigned already
                pass

        def make_available(self):
            """
            Mark the resource as available for assignment.
            """
            # Change resource state to available
            # If it was previously UNAVAILABLE (not ASSIGNED) we can just switch
            if self.is_unavailable():
                self._resource_state = ControllerResourceManager.ResourceState.AVAILABLE
            elif (
                self._resource_state == ControllerResourceManager.ResourceState.ASSIGNED
            ):
                # TODO
                # We must decide what to do with resources that were assigned already
                pass

    def __init__(self, health_monitor, managername, fqdns):
        """
        Initialize new ControllerResourceManager instance.

        :param health_monitor: Provides for monitoring of health states
        :type health_monitor:
            :py:class:`~ska.low.mccs.health.HealthMonitor`
        :param managername: Name for this manager (imformation only)
        :type managername: str
        :param fqdns: A list of device FQDNs
        :type fqdns: list(str)
        """
        self._managername = managername
        self._resources = dict()
        self.resource_availability_policy = self.ResourceAvailabilityPolicy(
            [HealthState.OK]
        )
        # For each resource, identified by FQDN, create an object
        for fqdn in fqdns:
            self._resources[fqdn] = self.Resource(
                self.resource_availability_policy, fqdn
            )
            health_monitor.register_callback(
                self._resources[fqdn]._health_changed, fqdn
            )

    def _except_on_unmanaged(self, fqdns):
        """
        Raise an exception if any of the listed FQDNs are not being
        managed by this manager.

        :param fqdns: The FQDNs to check
        :type fqdns: list(str)
        :raises ValueError: if an FQDN is not managed by this
        """
        # Are these keys all managed?
        # return any FQDNs not in our list of managed FQDNs
        bad = [fqdn for fqdn in fqdns if fqdn not in self._resources]
        if any(bad):
            raise ValueError(
                f"These FQDNs are not managed by {self._managername}: {bad}"
            )

    def get_all_fqdns(self):
        """
        Get all FQDNs managed by this resource manager.

        :return: List of FQDNs managed
        :rtype: list(str)
        """
        return self._resources.keys()

    def get_assigned_fqdns(self, owner_id):
        """
        Get the FQDNs assigned to a given owner id.

        :param owner_id: 1-based device id that we check for ownership
        :type owner_id: int

        :return: List of FQDNs assigned to owner_id
        :rtype: list(str)
        """

        return [
            fqdn
            for fqdn, res in self._resources.items()
            if (res.is_assigned() and res.assigned_to() == owner_id)
        ]

    def query_allocation(self, fqdns, new_owner):
        """
        Test if a (re)allocation is allowed, and if so, return lists of
        FQDNs to assign and to release. If the allocation is not
        permitted due to some FQDNs being allocated to another owner
        already, the list of blocking FQDNs is returned as the
        ReleaseList.

        :param fqdns: The list of FQDNs we would like to assign
        :type fqdns: list(str)
        :param new_owner: 1-based device id that would take ownership
        :type new_owner: int

        :return: tuple (Allowed, AssignList, ReleaseList)
            WHERE
            Allowed (bool): True if this (re)allocation is allowed
            AssignList (list): The list of FQDNs to allocate, or None
            ReleaseList (list): The list of FQDNs to release, or None
        :rtype: tuple(bool, list(str), list(str))
        """

        self._except_on_unmanaged(fqdns)

        # Make a list of any FQDNs which are blocking this allocation
        blocking = [
            fqdn
            for fqdn in fqdns
            if (
                (self._resources[fqdn].is_unavailable())
                or (
                    self._resources[fqdn].is_assigned()
                    and self._resources[fqdn].assigned_to() != new_owner
                )
            )
        ]

        if any(blocking):
            # Return False to indicate we are blocked, with the list
            return (False, None, blocking)

        # Make a list of wanted FQDNs not already assigned
        needed = [fqdn for fqdn in fqdns if (not self._resources[fqdn].is_assigned())]
        if len(needed) == 0:
            needed = None

        # Make a list of already-assigned FQDNs no longer wanted
        to_release = [
            fqdn
            for (fqdn, res) in self._resources.items()
            if (
                res.is_assigned()
                and res.assigned_to() == new_owner
                and fqdn not in fqdns
            )
        ]
        if len(to_release) == 0:
            to_release = None

        # Return True (ok to proceed), with the lists
        return (True, needed, to_release)

    def assign(self, fqdns, new_owner):
        """
        Take a list of device FQDNs and assign them to a new owner id.

        :param fqdns: The list of device FQDNs to assign
        :type fqdns: list(str)
        :param new_owner: 1-based id of the new owner
        :type new_owner: int
        :raises ValueError: if any of the FQDNs are unavailable or not healthy
        """

        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            try:
                self._resources[fqdn].assign(new_owner)
            except ValueError as value_error:
                raise ValueError(f"{self._managername}: {value_error}") from value_error

    def release(self, fqdns):
        """
        Take a list of device FQDNs and flag them as unassigned.

        :param fqdns: The list of device FQDNs to release
        :type fqdns: list(str)
        :raises ValueError: if any of the FQDNs are not being managed
        """
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            try:
                self._resources[fqdn].release()
            except ValueError as value_error:
                raise ValueError(f"{self._managername}: {value_error}") from value_error

    def make_unavailable(self, fqdns):
        """
        For each resource in the given list of FQDNs make its
        availability state unavailable.

        :param fqdns: The list of device FQDNs to make unavailable
        :type fqdns: list(str)
        """
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].make_unavailable()

    def make_available(self, fqdns):
        """
        For each resource in the given list of FQDNs make its
        availability state available.

        :param fqdns: The list of device FQDNs to make unavailable
        :type fqdns: list(str)
        """
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].make_available()

    def fqdn_from_id(self, devid):
        """
        Find a device FQDN by searching on its id number.

        :param devid: The device ID to find
        :type devid: int
        :raises ValueError: if the devid is not being managed
        :return: fqdn
        :rtype: str
        """

        for fqdn, res in self._resources.items():
            if res._devid == devid:
                return fqdn
        raise ValueError(f"Device ID {devid} is not managed by {self._managername}")

    def assign_allocatable_health_states(self, health_states):
        """
        Assign a list of health states which permit allocation.

        :param health_states: The list of allowed states
        :type health_states:
            list(:py:class:`~ska.base.control_model.HealthState`)
        """
        self.resource_availability_policy.assign_allocatable_health_states = (
            health_states
        )

    def reset_resource_availability_policy(self):
        """
        Reset to the default list of health states which permit
        allocation.
        """
        self.resource_availability_policy.reset()


class MccsController(SKAMaster):
    """
    MccsController TANGO device class for the MCCS prototype.

    This is a subclass of :py:class:`~ska.base.SKAMaster`.

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
        A class for :py:class:`~.MccsController`'s Init command.

        The
        :py:meth:`~.MccsController.InitCommand.do` method below is
        called during :py:class:`~.MccsController`'s initialisation.
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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            super().do()

            device = self.target
            device._command_result = None
            device._build_state = release.get_release_info()
            device._version_id = release.version
            device.set_change_event("commandResult", True, False)

            if device.MccsSubarrays is None:
                device._subarray_fqdns = list()
            else:
                device._subarray_fqdns = device.MccsSubarrays
            device._subarray_enabled = [False] * len(device.MccsSubarrays)
            if device.MccsStations is None:
                device._station_fqdns = list()
            else:
                device._station_fqdns = device.MccsStations

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
            :type: list(str)
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
                self._initialise_resource_management(device, fqdns)
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
            :type: list(str)
            """
            device.event_manager = EventManager(self.logger, device._station_fqdns)

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                None, device._station_fqdns, device.event_manager, device.health_changed
            )

        def _initialise_power_management(self, device, fqdns):
            """
            Initialise power management for this device.

            :param device: the device for which power management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices for which
                this device manages power
            :type: list(str)
            """
            device.power_manager = ControllerPowerManager(device._station_fqdns)
            power_args = (device.power_manager, device.state_model, device.logger)
            device.register_command_object("Off", device.OffCommand(*power_args))
            device.register_command_object("On", device.OnCommand(*power_args))

        def _initialise_resource_management(self, device, fqdns):
            """
            Initialise resource management for this device.

            :param device: the device for which resource management is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            :param fqdns: the fqdns of subservient devices allocation of which
                is managed by this device
            :type: list(str)
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
        :py:meth:`~.MccsController.InitCommand.do` method of the nested
        :py:class:`~.MccsController.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsController.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------
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
        doc="Result code from the previously completed command",
    )
    def commandResult(self):
        """
        Return the commandResult attribute.

        :return: commandResult attribute
        :rtype: :py:class:`~ska.base.commands.ResultCode`
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

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ReturnType, 'informational message')",
    )
    @DebugIt()
    def On(self):
        """
        Turn the controller on.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        command = self.get_command_object("On")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class OnCommand(SKABaseDevice.OnCommand):
        """
        Class for handling the On command.
        """

        def do(self):
            """
            Stateless do hook for implementing the functionality of the
            :py:meth:`.MccsController.On` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                result = power_manager.on()
                if result is None:
                    return (ResultCode.OK, "On command redundant; already on")
                elif result:
                    return (ResultCode.OK, "On command completed OK")
                else:
                    return (ResultCode.FAILED, "On command failed")
            except PowerManagerError as pme:
                return (ResultCode.FAILED, f"On command failed: {pme}")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ReturnType, 'informational message')",
    )
    @DebugIt()
    def Off(self):
        """
        Turn the controller off.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype:
            (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        command = self.get_command_object("Off")
        (result_code, message) = command()
        self._command_result = result_code
        self.push_change_event("commandResult", self._command_result)
        return [[result_code], [message]]

    class OffCommand(SKABaseDevice.OffCommand):
        """
        Class for handling the Off command.
        """

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.Off` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            power_manager = self.target
            try:
                result = power_manager.off()
                if result is None:
                    return (ResultCode.OK, "Off command redundant; already off")
                elif result:
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
            :py:meth:`.MccsController.StandbyLow` command.

            Transitions the MCCS system to the low-power STANDBY_LOW_POWER
            operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        StandbyLow Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
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

        def do(self):
            """
            Stateless do-hook for implementing the functionality of the
            :py:meth:`.MccsController.StandbyFull` command.

            Transition the MCCS system to the STANDBY_FULL_POWER operating state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        StandbyFull Command.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
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

        def do(self):
            """
            Stateless hook for implementation of
            :py:meth:`.MccsController.Operate` command
            functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            return (
                ResultCode.OK,
                "Stub implementation of OperateCommand(), does nothing",
            )

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            :rtype: bool
            """
            return self.state_model.op_state == DevState.OFF

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'information-only string')",
    )
    @DebugIt()
    def Operate(self):
        """
        Transit to the OPERATE operating state, ready for signal
        processing.

        :todo: What does this command do?

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Operate")
        (result_code, message) = handler()
        return [[result_code], [message]]

    def is_Operate_allowed(self):
        """
        Whether this command is allowed to be run in current device
        state.

        :return: True if this command is allowed to be run in
            current device state
        :rtype: bool
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
            (inherited) :py:meth:`ska.base.SKABaseDevice.Reset` command
            for this :py:class:`.MccsController` device.

            This implementation resets the MCCS system as a whole as an
            attempt to clear a FAULT state.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        Allocate a set of unallocated MCCS resources to a sub-array. The
        JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified
        Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, station_ids, channels and station_beam_ids.
        :type argin: str
        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)

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

        def do(self, argin):
            """
            Stateless hook implementing the functionality of the
            :py:meth:`.MccsController.Allocate` command

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
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """

            controllerdevice = self.target

            args = json.loads(argin)
            subarray_id = args["subarray_id"]
            station_ids = args["station_ids"]

            assert 1 <= subarray_id <= len(controllerdevice._subarray_fqdns)

            # Allocation request checks
            # Generate station FQDNs from IDs
            station_fqdns = [
                f"low-mccs/station/{station_id:03}" for station_id in station_ids
            ]

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

                # Inform manager that we made the assignments
                controllerdevice._stations_manager.assign(
                    stations_to_assign, subarray_id
                )

            return (ResultCode.OK, "Allocate command successful")

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            :rtype: bool
            """
            return self.state_model.op_state == DevState.ON

        def _enable_subarray(self, argin):
            """
            Method to enable the specified subarray.

            :param argin: the subarray id
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        state.

        :return: True if this command is allowed to be run in
            current device state
        :rtype: bool
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
        Release resources from an MCCS Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, a release all flag and array resources (TBD).
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
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

        def do(self, argin):
            """
            Stateless do hook for the
            :py:meth:`.MccsController.Release` command

            :param argin: JSON-formatted string containing an integer
                subarray_id, a release all flag and array resources (TBD).
            :type argin: str
            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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

        def check_allowed(self):
            """
            Whether this command is allowed to be run in current device
            state.

            :return: True if this command is allowed to be run in
                current device state
            :rtype: bool
            """
            return self.state_model.op_state == DevState.ON

        def _disable_subarray(self, argin):
            """
            Method to disable the specified subarray.

            :param argin: the subarray id
            :type argin: int

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        state.

        :return: True if this command is allowed to be run in
            current device state
        :rtype: bool
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

        def do(self):
            """
            Stateless do-hook for handling the
            :py:meth:`.MccsController.Maintenance` command.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
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
        :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Maintenance")
        (result_code, message) = handler()
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

    return MccsController.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
