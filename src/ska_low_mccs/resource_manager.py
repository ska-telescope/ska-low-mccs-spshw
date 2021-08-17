# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements infrastructure for resource management in the MCCS subsystem."""
from __future__ import annotations

from typing import Any, Hashable, Iterable, Mapping, Optional, cast


__all__ = ["ResourceManager", "HealthfulReadyResourceManager", "ResourcePool"]


class ResourceManager:
    """
    A generic resource manager / tracker.

    This resource manager treats resources as abstract concepts that can
    be allocated to and deallocated from abstract allocatees.
    """

    def __init__(
        self: ResourceManager,
        allocatees: Iterable[Hashable],
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Initialise a new instance.

        :param allocatees: targets for allocation of resources.
        :param resources: keyword args, with each keyword being the name
            of a resource type, and the value being the set of resources
            of that type managed by this resource manager. For example,
            to allocate toys, tools and treasure to boxes:

            .. code-block:: python

                resource_manager = _ResourceManager(
                    boxes,
                    toys={"teddybears", "lego"},
                    tools={"hammers", "saws", "drills"}
                    treasure={"diamonds", "rubies", "coins"},
                }

            The resource types will be maintained as separate
            namespaces, so you can re-use a resource marker across
            different types. For example, no problem using the number 2
            twice in this example:

            .. code-block:: python

                resource_manager = _ResourceManager(
                    subarrays,
                    station_ids={1, 2},
                    channel_blocks={2, 3}
                }
        """
        self._allocatees = set(allocatees)
        self._allocations: dict[str, dict[Hashable, Optional[Hashable]]] = {
            resource_type: {resource: None for resource in resources[resource_type]}
            for resource_type in resources
        }

    def _validate_resources(
        self: ResourceManager,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Check that the resources provided are managed by this resource manager.

        :param resources: the resources to check

        :raises ValueError: if any resources are not managed by this
            resource manager
        """
        unsupported_types = {
            resource_type
            for resource_type in resources
            if resource_type not in self._allocations
        }
        if unsupported_types:
            raise ValueError(f"Unsupported resource types: {unsupported_types}.")

        unsupported = {
            resource_type: [
                resource
                for resource in resources[resource_type]
                if resource not in self._allocations[resource_type]
            ]
            for resource_type in resources
        }
        # discard empty entries
        unsupported = {
            resource_type: unsupported[resource_type]
            for resource_type in unsupported
            if unsupported[resource_type]
        }

        if unsupported:
            raise ValueError(f"Unsupported resources: {unsupported}.")

    def _validate_allocatee(
        self: ResourceManager,
        allocatee: Hashable,
    ) -> None:
        """
        Check that the allocatee provided is known to this resource manager.

        :param allocatee: the allocatee to check

        :raises ValueError: if the allocatee is not known to this
            resource manager
        """
        if allocatee not in self._allocatees:
            raise ValueError(f"Unsupported allocatee: {allocatee}")

    def _validate_allocation(
        self: ResourceManager,
        allocatee: Hashable,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Check that the specified resources can be allocated to the specified allocatee.

        This method assumes that the resources and allocatee have been
        validated.

        :param resources: the resources to check
        :param allocatee: the allocatee to check

        :raises ValueError: if the resources are not available to be
            allocated to the allocatee
        """
        unallocatable = {
            resource_type: [
                resource
                for resource in resources[resource_type]
                if self._allocations[resource_type][resource] is not None
                and self._allocations[resource_type][resource] != allocatee
            ]
            for resource_type in resources
        }
        # discard empty entries
        unallocatable = {
            resource_type: unallocatable[resource_type]
            for resource_type in unallocatable
            if unallocatable[resource_type]
        }
        if unallocatable:
            raise ValueError(
                f"Cannot allocate resources: {unallocatable} to allocatee {allocatee}"
            )

    def allocate(
        self: ResourceManager,
        allocatee: Hashable,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Allocate resources to an allocatee.

        :param allocatee: the allocatee to which resources are to be
            allocated
        :param resources: the resources to allocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be allocated. For example:

            .. code-block:: python

                resource_manager.allocate(
                    "box_1",
                    toys={"lego"},
                    tools={"hammers", "saws"}
                }
        """
        self._validate_allocatee(allocatee)
        self._validate_resources(**resources)
        self._validate_allocation(allocatee, **resources)

        for resource_type in resources:
            for resource in resources[resource_type]:
                self._allocations[resource_type][resource] = allocatee

    def deallocate(
        self: ResourceManager,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Deallocate resources.

        :param resources: the resources to deallocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be allocated. For example:

            .. code-block:: python

                resource_manager.deallocate(
                    toys={"lego"},
                    tools={"hammers", "saws"}
                }
        """
        self._validate_resources(**resources)

        for resource_type in resources:
            for resource in resources[resource_type]:
                self._allocations[resource_type][resource] = None

    def deallocate_from(
        self: ResourceManager,
        allocatee: Hashable,
    ) -> None:
        """
        Deallocate all resources from an allocatee.

        :param allocatee: the allocatee to which resources are to be
            allocated
        """
        self._validate_allocatee(allocatee)

        for resource_type in self._allocations:
            for resource in self._allocations[resource_type]:
                if self._allocations[resource_type][resource] == allocatee:
                    self._allocations[resource_type][resource] = None

    def get_allocated(
        self: ResourceManager,
        allocatee: Hashable,
    ) -> Mapping[str, Iterable[Hashable]]:
        allocated = {
            resource_type: [
                resource
                for resource in self._allocations[resource_type]
                if self._allocations[resource_type][resource] == allocatee
            ]
            for resource_type in self._allocations
        }

        # discard empty entries
        allocated = {
            resource_type: allocated[resource_type]
            for resource_type in allocated
            if allocated[resource_type]
        }

        return allocated

    def get_unallocated(
        self: ResourceManager,
    ) -> Mapping[str, Iterable[Hashable]]:
        unallocated = {
            resource_type: [
                resource
                for resource in self._allocations[resource_type]
                if self._allocations[resource_type][resource] == None
            ]
            for resource_type in self._allocations
        }

        return unallocated

class _HealthfulResourceManager(ResourceManager):
    """A resource manager / tracker for resource types that may have a health state."""

    def __init__(
        self: _HealthfulResourceManager,
        allocatees: Iterable[Hashable],
        healthful_resource_types: Iterable[str],
        *args: Any,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Initialise a new instance.

        :param allocatees: targets for allocation of resources.
        :param healthful_resource_types: resource types that should be
            managed for health.
        :param args: other positional arguments
        :param resources: keyword args, with each keyword being the name
            of a resource type, and the value being the set of resources
            of that type managed by this resource manager. For example,
            to allocate toys, tools and treasure to boxes:

            .. code-block:: python

                resource_manager = _HealthfulResourceManager(
                    boxes,
                    ["toys", "tools"],
                    toys={"teddybears", "lego"},
                    tools={"hammers", "saws", "drills"}
                    treasure={"diamonds", "rubies", "coins"},
                }

            The resource types will be maintained as separate
            namespaces, so you can re-use a resource marker across
            different types. For example, no problem using the number 2
            twice in this example:

            .. code-block:: python

                resource_manager = _ResourceManager(
                    subarrays,
                    ["station_ids"],
                    station_ids={1, 2},
                    channel_blocks={2, 3}
                }
        """
        self._healthy = {
            resource_type: {resource: False for resource in resources[resource_type]}
            for resource_type in healthful_resource_types
        }
        super().__init__(allocatees, *args, **resources)

    def _validate_allocation(
        self: _HealthfulResourceManager,
        allocatee: Hashable,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Check that the specified resources can be allocated to the specified allocatee.

        This method assumes that the resources and allocatee have been
        validated.

        :param allocatee: the allocatee to check
        :param resources: the resources to check

        :raises ValueError: if the resources to be allocated are not all
            healthy.
        """
        super()._validate_allocation(allocatee, **resources)

        unhealthy = {
            resource_type: [
                resource
                for resource in resources[resource_type]
                if self._allocations[resource_type][resource] is None
                and not self._healthy[resource_type][resource]
            ]
            for resource_type in resources
            if resource_type in resources and resource_type in self._healthy
        }
        # discard empty entries
        unhealthy = {
            resource_type: unhealthy[resource_type]
            for resource_type in unhealthy
            if unhealthy[resource_type]
        }
        if unhealthy:
            raise ValueError(f"Cannot allocate unhealthy resources: {unhealthy}.")

    def set_health(
        self: _HealthfulResourceManager,
        resource_type: str,
        resource: Hashable,
        is_healthy: bool,
    ) -> None:
        """
        Set the health of a resource.

        :param resource_type: the resource type of the resources whose
            health is being set
        :param resource: the resource whose health is being set
        :param is_healthy: the new health status of the resource

        :raises ValueError: if the resource type is not managed for
            health
        """
        self._validate_resources(**{resource_type: {resource}})

        if resource_type not in self._healthy:
            raise ValueError(
                f"Resource type {resource_type} is not managed for health."
            )
        self._healthy[resource_type][resource] = is_healthy


class _ReadyResourceManager(ResourceManager):
    def __init__(
        self: _ReadyResourceManager,
        allocatees: Iterable[Hashable],
        *args: Any,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Initialise a new instance.

        :param allocatees: targets for allocation of resources.
        :param args: positional args to pass to underlying resource
            manager
        :param resources: keyword args, with each keyword being the name
            of a resource type, and the value being the set of resources
            of that type managed by this resource manager. For example,
            to allocate toys, tools and treasure to boxes:

            .. code-block:: python

                resource_manager = _ReadyResourceManager(
                    boxes,
                    toys={"teddybears", "lego"},
                    tools={"hammers", "saws", "drills"}
                    treasure={"diamonds", "rubies", "coins"},
                }

            The resource types will be maintained as separate
            namespaces, so you can re-use a resource marker across
            different types. For example, no problem using the number 2
            twice in this example:

            .. code-block:: python

                resource_manager = _ResourceManager(
                    subarrays,
                    station_ids={1, 2},
                    channel_blocks={2, 3}
                }
        """
        self._ready = {allocatee: False for allocatee in allocatees}
        super().__init__(allocatees, *args, **resources)

    def _validate_allocation(
        self: _ReadyResourceManager,
        allocatee: Hashable,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Check that the specified resources can be allocated to the specified allocatee.

        This method assumes that the resources and allocatee have been
        validated.

        :param allocatee: the allocatee to check
        :param resources: the resources to check

        :raises ValueError: if the allocatee is unready to be allocated
            resources.
        """
        super()._validate_allocation(allocatee, **resources)

        if not self._ready[allocatee]:
            raise ValueError(f"Allocatee is unready: {allocatee}.")

    def set_ready(
        self: _ReadyResourceManager,
        allocatee: Hashable,
        is_ready: bool,
    ) -> None:
        """
        Set an allocatee's readiness to be allocated resources.

        :param allocatee: the allocatee to set as ready or not ready
        :param is_ready: whether the subarray is ready or not
        """
        self._validate_allocatee(allocatee)
        self._ready[allocatee] = is_ready


class HealthfulReadyResourceManager(
    _HealthfulResourceManager,
    _ReadyResourceManager,
):
    """A resource manager that manages both allocatee readiness and resource health."""

    pass


class ResourcePool:
    """A manager for a finite pool of resources."""

    def __init__(
        self: ResourcePool,
        **resources: Iterable[Hashable],
        ) -> None:
        """
        Initialise a pool of resources.

        :param resources: the resources to be managed in this pool

        Sets all resources as free (allocatable).
        """
        self._resources: dict[Hashable, dict[Hashable, bool]] = {
            resource_type: {resources[resource_type]: True} for resource_type in resources
        }
        self._resources = resources

    def getFreeResource(
        self: ResourcePool,
        resource_type: Hashable,
        ) -> Hashable:
        """
        Get a free (unallocated) resource from the pool.

        :param resource_type: the type of resource

        :raises ValueError: if there a no free resources.
        """
        for resource in self._resources[resource_type]:
            if self._resources[resource_type][resource]:
                return self._resources[resource_type][resource]
        
        raise ValueError(f"No free resources of type: {resource_type}.")        

    def freeResource(
        self: ResourcePool,
        resource: Hashable,
    ) -> None:
        """
        Mark a resource as unallocated.
        """
        pass

    def lockResource(
        self: ResourcePool,
        resource: Hashable,
    ) -> None:
        pass