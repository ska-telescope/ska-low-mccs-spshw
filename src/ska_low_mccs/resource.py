# -*- coding: utf-8 -*-
#
# This file is part of the ska_low_mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements infrastructure for resource management in MCCS."""

from __future__ import annotations  # allow forward references in type hints

from enum import Enum
import logging
from typing import Iterable, Optional

from ska_tango_base.control_model import HealthState

from ska_low_mccs.health import MutableHealthMonitor


class ResourceState(Enum):
    """
    This enum describes a resource's assigned state.

    A resource which is UNAVAILABLE cannot be assigned. A resource which
    is AVAILABLE can be assigned. A resource which is ASSIGNED cannot be
    assigned until the original assignment has been released.
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
    This inner class implements a resource allocation policy for the resources belonging
    to the parent.

    Initialise with a list of allocatable health states:
    (OK = 0, DEGRADED = 1, FAILED = 2, UNKNOWN = 3).
    Defaults to [OK]
    """

    def __init__(
        self: ResourceAvailabilityPolicy,
        allocatable_health_states: list[HealthState] = [HealthState.OK],
    ) -> None:
        """
        Initialise a new ResourceAvailabilityPolicy instance.

        :param allocatable_health_states: the policy associated with this
            device
        """
        self._allocatable_health_states = list(allocatable_health_states)

    def is_allocatable(
        self: ResourceAvailabilityPolicy, health_state: HealthState
    ) -> bool:
        """
        Check if a state allows allocation.

        :param health_state: The state of health to check

        :return: True if this is suitable for allocation
        """
        return health_state in self._allocatable_health_states

    def assign_allocatable_health_states(
        self: ResourceAvailabilityPolicy, health_states: list[HealthState]
    ) -> None:
        """
        Set the health states allowed for allocation.

        :param health_states: Allowed health states
        """
        self._allocatable_health_states = list(health_states)

    def reset(self: ResourceAvailabilityPolicy) -> None:
        """Reset to the default set of states allowed for allocation."""
        self._allocatable_health_states = [HealthState.OK]


class Resource:
    """
    This inner class implements state recording for a managed resource.

    Initialise with a device id number.
    """

    def __init__(
        self: Resource,
        availability_policy: ResourceAvailabilityPolicy,
        fqdn: str,
        device_id: int = 0,
    ) -> None:
        """
        Initialise a new Resource instance.

        :param availability_policy: the policy associated with this
            device
        :param fqdn: FQDN of supervised device
        :param device_id: ID of supervised device
        """
        self._resource_availability_policy = availability_policy
        self._fqdn = fqdn
        self._resource_state = ResourceState.AVAILABLE
        self._assigned_to = 0
        self._health_state = HealthState.UNKNOWN
        self._device_id = device_id

    def assigned_to(self: Resource) -> int:
        """
        Get the ID to which this resource is assigned.

        :return: Device ID
        """
        return self._assigned_to

    def is_assigned(self: Resource) -> bool:
        """
        Check if this resource is assigned.

        :return: True if assigned
        """
        return self._resource_state == ResourceState.ASSIGNED and self._assigned_to != 0

    def is_available(self: Resource) -> bool:
        """
        Check if this resource is AVAILABLE (for assignment)

        :return: True if available
        """
        return self._resource_state == ResourceState.AVAILABLE

    def is_unavailable(self: Resource) -> bool:
        """
        Check if this resource is UNAVAILABLE.

        :return: True if unavailable
        """
        return self._resource_state == ResourceState.UNAVAILABLE

    def is_not_available(self: Resource) -> bool:
        """
        Check if this resource is not available A resource is not available if it is
        ASSIGNED or UNAVAILABLE.

        :return: True if not unavailable
        """
        return (
            self._resource_state == ResourceState.UNAVAILABLE
            or self._resource_state == ResourceState.ASSIGNED
        )

    def is_healthy(self: Resource) -> bool:
        """
        Check if this resource is in a healthy state, as defined by its resource
        availability policy.

        :return: True if healthy
        """
        return self._resource_availability_policy.is_allocatable(self._health_state)

    def _health_changed(self: Resource, fqdn: str, event_value: int) -> None:
        """
        Update the health state of the resource.

        :param fqdn: FQDN of the device for which healthState has
            changed
        :param event_value: The HealthState to assign to the resource

        :raises Exception: if requested healthstate change is not an integer
        """
        assert fqdn == self._fqdn
        if not isinstance(event_value, int):
            raise Exception(
                f"{fqdn}: invalid healthstate change: {self._health_state} -> {event_value}"
            )
        self._health_state = event_value

    def assign(self: Resource, owner: int) -> None:
        """
        Assign a resource to an owner.

        :param owner: Device ID of the owner

        :raises ValueError: if the named resource is already assigned
        :raises ValueError: if the named resource is unhealthy
        :raises ValueError: if the named resource is otherwise unavailable
        """
        # Don't allow assign if already assigned to another owner
        if self.is_assigned():
            if self._assigned_to != owner:
                # Trying to assign to new owner not allowed
                raise ValueError(
                    f"{self._fqdn} already assigned to {self._assigned_to}"
                )
            # No action if repeating the existing assignment
            return
        # Don't allow assign if resource is not healthy
        if not self.is_healthy():
            raise ValueError(
                f"{self._fqdn} does not pass health check for"
                f" assignment (health={self._health_state})"
            )

        if self.is_available():
            self._assigned_to = owner
            self._resource_state = ResourceState.ASSIGNED
        else:
            raise ValueError(f"{self._fqdn} is unavailable")

    def release(self: Resource) -> None:
        """
        Release the resource from assignment.

        :raises ValueError: if the resource was unassigned
        """
        if self._assigned_to == 0:
            raise ValueError(f"Attempt to release unassigned resource, {self._fqdn}")
        self._assigned_to = 0

        if self._resource_state == ResourceState.ASSIGNED:
            # Previously assigned resource becomes available
            if not self.is_healthy():
                self.make_unavailable()
            else:
                self._resource_state = ResourceState.AVAILABLE
        # Unassigned or unavailable resource does not change state

    def make_unavailable(self: Resource) -> None:
        """Mark the resource as unavailable for assignment."""
        # Change resource state to unavailable
        # If it was previously AVAILABLE (not ASSIGNED) we can just switch
        if self.is_available():
            self._resource_state = ResourceState.UNAVAILABLE
        elif self._resource_state == ResourceState.ASSIGNED:
            # TODO
            # We must decide what to do with rescources that were assigned already
            pass

    def make_available(self: Resource) -> None:
        """Mark the resource as available for assignment."""
        # Change resource state to available
        # If it was previously UNAVAILABLE (not ASSIGNED) we can just switch
        if self.is_unavailable():
            self._resource_state = ResourceState.AVAILABLE
        elif self._resource_state == ResourceState.ASSIGNED:
            # TODO
            # We must decide what to do with resources that were assigned already
            pass


class ResourceManager:
    """
    This class implements a resource manger for the MCCS subsystem.

    Initialize with a dictionary of IDs andFQDNs of devices to be
    managed. The ResourceManager holds the FQDN and the (1-based) ID of
    the device that owns each managed device.
    """

    def __init__(
        self: ResourceManager,
        health_monitor: MutableHealthMonitor,
        managername: str,
        devices: dict[int, str],
        logger: logging.Logger,
        availability_policy: list[HealthState] = [HealthState.OK],
    ) -> None:
        """
        Initialize new ResourceManager instance.

        :param health_monitor: Provides for monitoring of health states
        :param managername: Name for this manager (information only)
        :param devices: A dictionary of device IDs and FQDNs
        :param logger: the logger to be used by the object under test
        :param availability_policy: availability policy for this
            resource manager
        """
        self._logger = logger
        self._managername = managername
        self._resources = dict()
        self._health_monitor = health_monitor
        self.resource_availability_policy = ResourceAvailabilityPolicy(
            availability_policy
        )
        # For each resource, identified by FQDN, create an object
        for device_id, fqdn in devices.items():
            self._resources[fqdn] = Resource(
                self.resource_availability_policy, fqdn, device_id
            )
            self._health_monitor.register_callback(
                self._resources[fqdn]._health_changed, fqdn
            )

    def _except_on_unmanaged(self: ResourceManager, fqdns: Iterable[str]) -> None:
        """
        Raise an exception if any of the listed FQDNs are not being managed by this
        manager.

        :param fqdns: The FQDNs to check

        :raises ValueError: if an FQDN is not managed by this
        """
        # Are these keys all managed?
        # return any FQDNs not in our list of managed FQDNs
        bad = [fqdn for fqdn in fqdns if fqdn not in self._resources]
        if any(bad):
            raise ValueError(
                f"These FQDNs are not managed by {self._managername}: {bad}"
            )

    def _add_to_managed(self: ResourceManager, devices: dict[int, str]) -> None:
        """
        Add new device(s) to be managed by this resource manager.

        :param devices: The IDs and FQDNs of devices to add
        """
        self._health_monitor.add_devices(devices.values())
        for device_id, fqdn in devices.items():
            if fqdn not in self.get_all_fqdns():
                self._resources[fqdn] = Resource(
                    self.resource_availability_policy, fqdn, device_id
                )
                self._health_monitor.register_callback(
                    self._resources[fqdn]._health_changed, fqdn
                )

    def _remove_from_managed(self: ResourceManager, fqdns: list[str]) -> None:
        """
        Remove device(s) from this resource manager.

        :param fqdns: The FQDNs of devices to remove
        """
        for fqdn in fqdns:
            self._resources.pop(fqdn)

    def update_resource_health(
        self: ResourceManager, fqdn: str, health_state: HealthState
    ) -> None:
        """
        Update the health state of a resource managed by this resource manager.

        :param fqdn: The FQDN of the resource for which the HealthState is
            being updated
        :param health_state: The (new) HealthState of the device

        :raises ValueError: if FQDN of resource is unknown to resource manager
        """
        if fqdn in self._resources.keys():
            self._resources[fqdn]._health_changed(fqdn, health_state)
        else:
            raise ValueError(
                f"""{self._managername}: Cannot update health of {fqdn},
                device not managed by resource manager"""
            )

    def get_all_fqdns(self: ResourceManager) -> list[str]:
        """
        Get all FQDNs managed by this resource manager.

        :return: List of FQDNs managed
        """
        return sorted(self._resources.keys())

    def get_assigned_fqdns(self: ResourceManager, owner_id: int) -> list[str]:
        """
        Get the FQDNs assigned to a given owner id.

        :param owner_id: 1-based device id that we check for ownership

        :return: List of FQDNs assigned to owner_id
        """
        return [
            fqdn
            for fqdn, res in self._resources.items()
            if (res.is_assigned() and res.assigned_to() == owner_id)
        ]

    def query_allocation(
        self: ResourceManager, fqdns: list[str], new_owner: int
    ) -> tuple[bool, Optional[list[str]], Optional[list[str]]]:
        """
        Test if a (re)allocation is allowed, and if so, return lists of FQDNs to assign
        and to release. If the allocation is not permitted due to some FQDNs being
        allocated to another owner already, the list of blocking FQDNs is returned as
        the ReleaseList.

        :param fqdns: The list of FQDNs we would like to assign
        :param new_owner: 1-based device id that would take ownership

        :return: tuple (Allowed, AssignList, ReleaseList)
            WHERE
            Allowed (bool): True if this (re)allocation is allowed
            AssignList (list): The list of FQDNs to allocate, or None
            ReleaseList (list): The list of FQDNs to release, or None
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
        needed = [
            fqdn for fqdn in fqdns if (not self._resources[fqdn].is_assigned())
        ] or None
        #         if len(needed) == 0:
        #             needed = None

        # Make a list of already-assigned FQDNs no longer wanted
        to_release = [
            fqdn
            for (fqdn, res) in self._resources.items()
            if (
                res.is_assigned()
                and res.assigned_to() == new_owner
                and fqdn not in fqdns
            )
        ] or None
        #         if len(to_release) == 0:
        #             to_release = None

        # Return True (ok to proceed), with the lists
        return (True, needed, to_release)

    def assign(self: ResourceManager, devices: dict[int, str], new_owner: int) -> None:
        """
        Take a list of device FQDNs and assign them to a new owner id.

        :param devices: The dict of device IDs (key) and FQDNs (value) to assign
        :param new_owner: 1-based id of the new owner

        :raises ValueError: if any of the FQDNs are unavailable or not healthy
        """
        self._except_on_unmanaged(devices.values())
        for device_id in devices.keys():
            try:
                self._resources[devices[device_id]].assign(new_owner)
            except ValueError as value_error:
                raise ValueError(f"{self._managername}: {value_error}") from value_error

    def release(self: ResourceManager, fqdns: list[str]) -> None:
        """
        Take a list of device FQDNs and flag them as unassigned.

        :param fqdns: The list of device FQDNs to release

        :raises ValueError: if any of the FQDNs are not being managed
        """
        self._logger.error("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            try:
                self._resources[fqdn].release()
            except ValueError as value_error:
                raise ValueError(f"{self._managername}: {value_error}") from value_error

    def make_unavailable(self: ResourceManager, fqdns: list[str]) -> None:
        """
        For each resource in the given list of FQDNs make its availability state
        unavailable.

        :param fqdns: The list of device FQDNs to make unavailable
        """
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].make_unavailable()

    def make_available(self: ResourceManager, fqdns: list[str]) -> None:
        """
        For each resource in the given list of FQDNs make its availability state
        available.

        :param fqdns: The list of device FQDNs to make unavailable
        """
        self._except_on_unmanaged(fqdns)
        for fqdn in fqdns:
            self._resources[fqdn].make_available()

    def fqdn_from_id(self: ResourceManager, device_id: int) -> str:
        """
        Find a device FQDN by searching on its id number.

        :param device_id: The device ID to find

        :raises ValueError: if the device_id is not being managed

        :return: fqdn
        """
        for fqdn, res in self._resources.items():
            if res._device_id == device_id:
                return fqdn
        raise ValueError(f"Device ID {device_id} is not managed by {self._managername}")

    def assign_allocatable_health_states(
        self: ResourceManager, health_states: list[HealthState]
    ) -> None:
        """
        Assign a list of health states which permit allocation.

        :param health_states: The list of allowed states
        """
        self.resource_availability_policy.assign_allocatable_health_states(
            health_states
        )

    def reset_resource_availability_policy(self: ResourceManager) -> None:
        """Reset to the default list of health states which permit allocation."""
        self.resource_availability_policy.reset()
