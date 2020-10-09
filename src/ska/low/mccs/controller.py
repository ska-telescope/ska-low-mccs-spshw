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
from enum import Enum

# PyTango imports
import tango
from tango import DebugIt, DevFailed, DevState, EnsureOmniThread
from tango.server import attribute, command, device_property

# Additional import
from ska.base import SKAMaster, SKABaseDevice
from ska.base.commands import ResponseCommand, ResultCode
from ska.base.control_model import HealthState

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


class ControllerResourceManager:
    """
    This class implements a resource manger for the MCCS controller device
    """

    def __init__(self, fqdns):
        """Initialize new ControllerResourceManager instance

        Args:
            fqdns (list): A list of device FQDNs
        """
        # Array holding all registered FQDNs of managed devices
        self._fqdns = numpy.array([] if fqdns is None else fqdns)
        # Array holding the assignments to owners of the devices
        self._allocation = numpy.zeros(
            0 if fqdns is None else len(fqdns), dtype=numpy.uint8
        )

    def CheckManaged(self, fqdns):
        """Test if the given FQDNs are being managed

        Args:
            fqdns (list): The FQDNs to check

        Returns:
            bool: True if all FQDNs are being managed
        """
        tocheck = numpy.array(fqdns)

        return numpy.isin(tocheck, self._fqdns).all()

    def GetAllFqdns(self):
        """
        Get all FQDNs managed by this resource manager

        Returns:
            list: List of FQDNs managed
        """
        return list(self._fqdns)

    def GetAssignedFqdns(self, owner_id):
        """Get the FQDNs assigned to a given owner id

        Args:
            owner_id (int): 1-based device id that we check for ownership

        Returns:
            list: List of FQDNs assigned to owner_id
        """

        mask = self._allocation == owner_id

        return list(self._fqdns[mask])

    def QueryAllocation(self, fqdns, new_owner_id):
        """Test if a (re)allocation is allowed, and if so, return lists of FQDNs
        to assign and to release. If the allocation is not permitted due to some
        FQDNs being allocated to another owner already, the list of blocking
        FQDNs is returned as the ReleaseList.

        Args:
            fqdns (list): The list of FQDNs we would like to assign
            new_owner_id (int): 1-based device id that would take ownership

        Returns: tuple (Allowed, AssignList, ReleaseList)
            WHERE
            Allowed (bool): True if this (re)allocation is allowed
            AssignList (list): The list of FQDNs to allocate, or None
            ReleaseList (list): The list of FQDNs to release, or None
        """

        if not self.CheckManaged(fqdns):
            raise TypeError(f"Some of these FQDNs are not being managed: {fqdns}")

        # Create mask of FQDNs present in the wanted list
        wanted_allocation = numpy.isin(self._fqdns, fqdns, assume_unique=True)
        # Examine the allocation ids for these entries
        already_allocated = numpy.logical_and.reduce(
            (
                self._allocation != 0,
                self._allocation != new_owner_id,
                wanted_allocation,
            )
        )

        if numpy.any(already_allocated):
            # Some of the requested FQDNs are already allocated
            # Which ones?
            already_allocated_fqdns = list(self._fqdns[already_allocated])
            # Return False (we can't allocate) and the list of FQDNs
            # that would have to be freed
            return (False, None, already_allocated_fqdns)

        # Generate mask of devices already allocated to the new owner
        # but no longer wanted
        release_mask = numpy.logical_and(
            self._allocation == new_owner_id,
            numpy.logical_not(wanted_allocation),
        )
        if numpy.any(release_mask):
            fqdns_to_release = list(self._fqdns[release_mask])
        else:
            fqdns_to_release = None

        # Generate mask of devices not yet allocated to any owner
        # which we now want
        assign_mask = numpy.logical_and(self._allocation == 0, wanted_allocation)
        if numpy.any(assign_mask):
            fqdns_to_assign = list(self._fqdns[assign_mask])
        else:
            fqdns_to_assign = None

        print(f"#### Asign ###\n{fqdns_to_assign}", file=sys.stderr)
        return (True, fqdns_to_assign, fqdns_to_release)

    def Assign(self, fqdns, owner_id):
        """Take a list of device FQDNs and assign them to a new owner id.

        Args:
            fqdns (list): The list of device FQDNs to assign
            owner_id (int): 1-based id of the new owner
        """

        if not self.CheckManaged(fqdns):
            raise TypeError(f"Some of these FQDNs are not being managed: {fqdns}")

        mask = numpy.isin(self._fqdns, fqdns, assume_unique=True)
        safe_to_allocate = numpy.logical_or.reduce(
            (
                self._allocation == 0,  # Not allocated
                self._allocation == owner_id,  # Already satisfied
                numpy.invert(mask),  # Not wanted
            )
        ).all()

        if not safe_to_allocate:
            raise TypeError(
                "Assign failed. Some requested devices are already otherwise assigned."
            )

        self._allocation[mask] = owner_id

    def Release(self, fqdns):
        """Take a list of device FQDNs and flag them as unassigned.

        Args:
            fqdns (list): The list of device FQDNs to release.
        """
        if not self.CheckManaged(fqdns):
            raise TypeError(f"Some of these FQDNs are not being managed: {fqdns}")

        mask = numpy.isin(self._fqdns, fqdns, assume_unique=True)
        self._allocation[mask] = 0


class ControllerResourceManager:
    """
    This class implements a resource manger for the MCCS controller device

    Initialize with a list of FQDNs of devices to be managed.
    The ControllerResourceManager holds the FQDN and the (1-based) ID
    of the device that owns each managed device.
    """

    class resource_state(Enum):
        UNAVAILABLE = 0  # Fault state
        AVAILABLE = 1  # Healthy, not assigned
        ASSIGNED = 2  # Healthy, assigned

    class ResourceAvailabilityPolicy:
        """
        This inner class implements the resource allocation policy for the resources
        belonging to the parent.

        Initialise with a list of allocatable health states:
        (OK = 0, DEGRADED = 1, FAILED = 2, UNKNOWN = 3).
        Defaults to [OK]
        """

        def __init__(self, allocatable_health_states=[HealthState.OK]):
            self._allocatableHealthStates = allocatable_health_states

        def is_allocatable(self, health_state):
            return health_state in self._allocatableHealthStates

        def assign_allocatable_health_states(self, health_states):
            self._allocatableHealthStates = health_states

        def reset(self):
            self._allocatableHealthStates = [HealthState.OK]

    class resource:
        """
        This inner class implements state recording for a managed resource.

        Initialize with a device id number.
        """

        def __init__(self, manager, fqdn, id):
            self._manager = manager
            self._fqdn = fqdn
            self._devid = id
            self._resourceState = ControllerResourceManager.resource_state.AVAILABLE
            self._assignedTo = 0

        def assignedTo(self):
            """Get the ID to which this resource is assigned

            Returns:
                int: Device ID
            """
            return self._assignedTo

        def isAssigned(self):
            """Check if this resource is assigned

            Returns:
                bool: True if assigned
            """
            return (
                self._resourceState == ControllerResourceManager.resource_state.ASSIGNED
                and self._assignedTo != 0
            )

        def isAvailable(self):
            """Check if this resource is AVAILABLE (for assignment)

            Returns:
                bool: True if available
            """
            return (
                self._resourceState
                == ControllerResourceManager.resource_state.AVAILABLE
            )

        def isUnavailable(self):
            """Check if this resource is UNAVAILABLE

            Returns:
                bool: True if unavailable
            """
            return (
                self._resourceState
                == ControllerResourceManager.resource_state.UNAVAILABLE
            )

        def isNotAvailable(self):
            """Check if this resource is not available
            A resource is not available if it is ASSIGNED or UNAVAILABLE

            Returns:
                bool: True if not available
            """
            return (
                self._resourceState
                == ControllerResourceManager.resource_state.UNAVAILABLE
                or self._resourceState
                == ControllerResourceManager.resource_state.ASSIGNED
            )

        def isHealthy(self):
            health_state_table = (
                self._manager._controller._health_monitor.get_healthstate_table()
            )
            fqdn = self._manager.FqdnFromId(self._devid)
            health = health_state_table[fqdn]
            health_state = health["healthstate"]
            return self._manager.resource_availability_policy.is_allocatable(
                health_state
            )

        def Assign(self, owner):
            """Assign a resource to an owner

            Args:
                owner (int): Device ID of the owner

            Raises:
                TypeError: Inidcating if the resource is already assigned
                TypeError: Indicating if the resource is unavailable
            """
            # Don't allow assign if already assigned to another owner
            if self.isAssigned():
                if self._assignedTo != owner:
                    # Trying to assign to new owner not allowed
                    raise TypeError(
                        f"{self._manager._managername}: "
                        f"{self._fqdn} already assigned to {self._assignedTo}"
                    )
                # No action if repeating the existing assignment
                return
            # Don't allow assign if resource is not healthy
            if not self.isHealthy():
                raise TypeError(
                    f"{self._manager._managername}: "
                    f"{self._fqdn} does not pass health check for assignment"
                )

            if self.isAvailable():
                self._assignedTo = owner
                self._resourceState = ControllerResourceManager.resource_state.ASSIGNED
            else:
                raise TypeError(
                    f"{self._manager._managername}: " f"{self._fqdn} is unavailable"
                )

        def Release(self):
            """Release the resource from assignment

            Raises:
                TypeError: Indicate if the resource was unassigned
            """
            if self._assignedTo == 0:
                raise TypeError(
                    f"{self._manager._managername}: "
                    f"Attempt to release unassigned resource, {self._fqdn}"
                )
            self._assignedTo = 0

            if self._resourceState == ControllerResourceManager.resource_state.ASSIGNED:
                # Previously assigned resource becomes available
                if not self.isHealthy():
                    self.MakeUnavailable()
                else:
                    self._resourceState = (
                        ControllerResourceManager.resource_state.AVAILABLE
                    )
            # Unassigned or unavailable resource does not change state

        def MakeUnavailable(self):
            # Change resource state to unavailable
            """Mark the resource as unavailable for assignment"""
            # Change resource state to unavailable
            # If it was previously AVAILABLE (not ASSIGNED) we can just switch
            if (
                self._resourceState
                == ControllerResourceManager.resource_state.AVAILABLE
            ):
                self._resourceState = (
                    ControllerResourceManager.resource_state.UNAVAILABLE
                )
            elif (
                self._resourceState == ControllerResourceManager.resource_state.ASSIGNED
            ):
                # TODO
                # We must decide what to do with rescources that were assigned already
                pass

        def MakeAvailable(self):
            """Mark the resource as available for assignment"""
            # Change resource state to available
            # If it was previously UNAVAILABLE (not ASSIGNED) we can just switch
            if (
                self._resourceState
                == ControllerResourceManager.resource_state.UNAVAILABLE
            ):
                self._resourceState = ControllerResourceManager.resource_state.AVAILABLE
            elif (
                self._resourceState == ControllerResourceManager.resource_state.ASSIGNED
            ):
                # TODO
                # We must decide what to do with resources that were assigned already
                pass

    def __init__(self, controller, managername, fqdns):
        """
        Initialize new ControllerResourceManager instance

        :param controller: Parent Controller object (for access to Health State)
        :type controller: MccsController object
        :param managername: Name for this manager (imformation only)
        :type managername: string
        :param fqdns: A list of device FQDNs
        :type fqdns: list of string
        """
        self._controller = controller
        self._managername = managername
        self._resources = dict()
        self.resource_availability_policy = self.ResourceAvailabilityPolicy(
            [HealthState.OK]
        )
        # For each resource, identified by FQDN, create an object
        for i, fqdn in enumerate(fqdns, start=1):
            self._resources[fqdn] = self.resource(self, fqdn, i)

    def exceptOnUnmanaged(self, fqdns):
        # Are these keys all managed?
        # return any FQDNs not in our list of managed FQDNs
        bad = [fqdn for fqdn in fqdns if fqdn not in self._resources]
        if any(bad):
            raise TypeError(
                f"These FQDNs are not managed by {self._managername}: {bad}"
            )

    def GetAllFqdns(self):
        """
        Get all FQDNs managed by this resource manager

        :return: List of FQDNs managed
        :rtype: list of strings
        """
        return self._resources.keys()

    def GetAssignedFqdns(self, owner_id):
        """
        Get the FQDNs assigned to a given owner id

        :param owner_id: 1-based device id that we check for ownership
        :type owner_id: int

        :return: List of FQDNs assigned to owner_id
        :rtype: list of strings
        """

        return [
            fqdn
            for fqdn, res in self._resources.items()
            if (res.isAssigned() and res.assignedTo() == owner_id)
        ]

    def QueryAllocation(self, fqdns, new_owner):
        """
        Test if a (re)allocation is allowed, and if so, return lists of FQDNs
        to assign and to release. If the allocation is not permitted due to some
        FQDNs being allocated to another owner already, the list of blocking
        FQDNs is returned as the ReleaseList.

        :param fqdns: The list of FQDNs we would like to assign
        :type fqdns: list of string
        :param new_owner_id: 1-based device id that would take ownership
        :type new_owner_id: int

        :return: tuple (Allowed, AssignList, ReleaseList)
            WHERE
            Allowed (bool): True if this (re)allocation is allowed
            AssignList (list): The list of FQDNs to allocate, or None
            ReleaseList (list): The list of FQDNs to release, or None
        :rtype: tuple (bool, list of strings, list of strings)
        """

        self.exceptOnUnmanaged(fqdns)

        # Make a list of any FQDNs which are blocking this allocation
        blocking = [
            fqdn
            for fqdn in fqdns
            if (
                (self._resources[fqdn].isUnavailable())
                or (
                    self._resources[fqdn].isAssigned()
                    and self._resources[fqdn].assignedTo() != new_owner
                )
            )
        ]

        if any(blocking):
            # Return False to indicate we are blocked, with the list
            return (False, None, blocking)

        # Make a list of wanted FQDNs not already assigned
        needed = [fqdn for fqdn in fqdns if (not self._resources[fqdn].isAssigned())]
        if len(needed) == 0:
            needed = None

        # Make a list of already-assigned FQDNs no longer wanted
        to_release = [
            fqdn
            for (fqdn, res) in self._resources.items()
            if (
                res.isAssigned() and res.assignedTo() == new_owner and fqdn not in fqdns
            )
        ]
        if len(to_release) == 0:
            to_release = None

        # Return True (ok to proceed), with the lists
        return (True, needed, to_release)

    def Assign(self, fqdns, new_owner):
        """
        Take a list of device FQDNs and assign them to a new owner id.

        :param fqdns: The list of device FQDNs to assign
        :type fqdns: list of string
        :param new_owner_id: 1-based id of the new owner
        :type new_owner_id: int
        :raises: TypeError if any of the FQDNs are not being managed
            or are otherwise assigned
        """

        self.exceptOnUnmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].Assign(new_owner)

    def Release(self, fqdns):
        """
        Take a list of device FQDNs and flag them as unassigned.

        :param fqdns: The list of device FQDNs to release
        :type fqdns: list of string
        :raises: TypeError if any of the FQDNs are not being managed
        """

        self.exceptOnUnmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].Release()

    def MakeUnavailable(self, fqdns):
        """
        For each resource in the given list of FQDNs make its availability state
        unavailable

        :param fqdns: The list of device FQDNs to make unavailable
        :type fqdns: list of string
        """
        self.exceptOnUnmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].MakeUnavailable()

    def MakeAvailable(self, fqdns):
        """
        For each resource in the given list of FQDNs make its availability state
        available

        :param fqdns: The list of device FQDNs to make unavailable
        :type fqdns: list of string
        """
        self.exceptOnUnmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].MakeAvailable()

    def FqdnFromId(self, devid):
        """
        Find a device FQDN by searching on its id number

        :param devid: The device ID to find
        :type devid: int

        :return: fqdn
        :rtype: string
        """

        for fqdn, res in self._resources.items():
            if res._devid == devid:
                return fqdn
        raise TypeError(f"Device ID {devid} is not managed by {self._managername}")

    def AssignAllocatableHealthStates(self, health_states):
        self.resource_availability_policy.assign_allocatable_health_states = (
            health_states
        )

    def ResetResourceAvailabilityPolicy(self):
        self.resource_availability_policy.reset()


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

            # Instantiate a resource manager for the Stations
            device._stations_manager = ControllerResourceManager(
                device, "StationsManager", device.MccsStations
            )
            station_fqdns = device._stations_manager.GetAllFqdns()

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

            # # id of subarray that station is allocated to, zero if unallocated
            # device._station_allocated = numpy.zeros(
            #     len(device.MccsStations), dtype=numpy.ubyte
            # )

            device._stations_manager = ControllerResourceManager(device.MccsStations)
            station_fqdns = device._stations_manager.GetAllFqdns()

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
            device._lock = threading.Lock()
            # initialise the health table using the FQDN as the key.
            # Create and event manager per FQDN and subscribe to events from it
            device._eventManagerList = []
            fqdns = station_fqdns
            device._rollup_policy = HealthRollupPolicy(device.update_healthstate)
            device._health_monitor = HealthMonitor(
                fqdns, device._rollup_policy.rollup_health
            )
            for fqdn in station_fqdns:
                device._eventManagerList.append(
                    EventManager(fqdn, device._health_monitor.update_health_table)
                )

            device.power_manager = ControllerPowerManager(station_fqdns)

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

            :param argin: the subarray id
            :type argin: int

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
                # Query stations resource manager for FQDNs assigned to this subarray
                fqdns = device._stations_manager.GetAssignedFqdns(subarray_id)
                for fqdn in fqdns:
                    station = tango.DeviceProxy(fqdn)
                    station.subarrayId = 0
                device._stations_manager.Release(fqdns)

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
            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                return (
                    "Cannot allocate resources to disabled subarray {}".format(
                        subarray_fqdn
                    ),
                )
            # station_allocation = numpy.isin(
            #     controllerdevice._station_fqdns, stations, assume_unique=True
            # )
            # already_allocated = numpy.logical_and.reduce(
            #     (
            #         controllerdevice._station_allocated != 0,
            #         controllerdevice._station_allocated != subarray_id,
            #         station_allocation,
            #     )
            # )

            # if numpy.any(already_allocated):
            #     already_allocated_fqdns = list(
            #         controllerdevice._station_fqdns[already_allocated]
            #     )
            #     return (
            #         ResultCode.FAILED,
            #         "Cannot allocate stations already allocated: {}".format(
            #             ", ".join(already_allocated_fqdns)
            #         ),
            #     )

            (
                alloc_allowed,
                stations_to_assign,
                stations_to_release,
            ) = controllerdevice._stations_manager.QueryAllocation(
                stations, subarray_id
            )
            if not alloc_allowed:
                return (
                    ResultCode.FAILED,
                    "Cannot allocate stations already allocated: {}".format(
                        ", ".join(stations_to_release)
                    ),
                )

            subarray_device = tango.DeviceProxy(subarray_fqdn)

            if not controllerdevice._subarray_enabled[subarray_id - 1]:
                return (
                    ResultCode.FAILED,
                    "Cannot allocate resources to disabled subarray {}".format(
                        subarray_fqdn
                    ),
                )

            # Query stations resource manager
            # Are we allowed to make this allocation?
            # Which FQDNs need to be assigned and released?
            (
                alloc_allowed,
                stations_to_assign,
                stations_to_release,
            ) = controllerdevice._stations_manager.QueryAllocation(
                stations, subarray_id
            )
            if not alloc_allowed:
                # If manager returns False (not allowed) stations_to_release
                # gives the list of FQDNs blocking the allocation.
                return (
                    ResultCode.FAILED,
                    "Cannot allocate stations already allocated: {}".format(
                        ", ".join(stations_to_release)
                    ),
                )

            subarray_device = tango.DeviceProxy(subarray_fqdn)

            # Manager gave this list of stations to release (no longer required)
            if stations_to_release is not None:
                (result_code, message) = call_with_json(
                    subarray_device.ReleaseResources, stations=stations_to_release
                if result_code == ResultCode.FAILED:
                    return (
                        ResultCode.FAILED,
                        f"Failed to release resources from subarray {subarray_fqdn}:"
                        f"{message}",
                    )
                for fqdn in stations_to_release:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = 0

                # Inform manager that we made the releases
                controllerdevice._stations_manager.Release(stations_to_release)

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
            # assign_mask = numpy.logical_and(
            #     controllerdevice._station_allocated == 0, station_allocation
            # )
            # if numpy.any(assign_mask):
            print(f"^^^^ ASSIGN ^^^^\n{stations_to_assign}", file=sys.stderr)
            if stations_to_assign is not None:
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
                controllerdevice._stations_manager.Assign(
                    stations_to_assign, subarray_id
                )

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

            # Query stations resouce manager for stations assigned tp subarray
            fqdns = self.target._stations_manager.GetAssignedFqdns(subarray_id)
            for fqdn in fqdns:
                station = tango.DeviceProxy(fqdn)
                station.subarrayId = 0
            self.target._stations_manager.Release(fqdns)

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
