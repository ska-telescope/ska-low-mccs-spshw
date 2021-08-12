# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for the MCCS controller."""
from __future__ import annotations

from typing import Any, Hashable, Iterable, Mapping, Optional, cast


__all__ = ["ControllerResourceManager"]


class _ResourceManager:
    """
    A generic resource manager / tracker.

    This resource manager treats resources as abstract concepts that can
    be allocated to and deallocated from abstract allocatees.
    """

    def __init__(
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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
        self: _ResourceManager,
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


class _HealthfulResourceManager(_ResourceManager):
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

                resource_manager = _HealthfulResourceManager(
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


class _ReadyResourceManager(_ResourceManager):
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


class _HealthfulReadyResourceManager(
    _HealthfulResourceManager,
    _ReadyResourceManager,
):
    """A resource manager that manages both allocatee readiness and resource health."""

    pass


class ControllerResourceManager:
    """A resource manager for the controller component manager."""

    def __init__(
        self: ControllerResourceManager,
        subarrays: Iterable[str],
        subracks: Iterable[str],
        stations: Iterable[str],
        subarray_beams: Iterable[str],
        channel_blocks: Iterable[int],
    ) -> None:
        """
        Initialise a new instance.

        :param subarrays: all subarrays to be managed by this resource
            manager
        :param subracks: all subracks to be managed by this resource
            manager
        :param stations: all stations to be managed by this resource
            manager
        :param subarray_beams: all subarray beams to be managed by this
            resource manager
        :param channel_blocks: all channel blocks to be managed by this
            resource manager
        """
        self._resource_manager = _HealthfulReadyResourceManager(
            subarrays,
            {"stations", "subracks", "subarray_beams"},
            stations=stations,
            subracks=subracks,
            subarray_beams=subarray_beams,
            channel_blocks=channel_blocks,
        )

    def set_health(
        self: ControllerResourceManager,
        resource_type: str,
        resource: Hashable,
        is_healthy: bool,
    ) -> None:
        """
        Set the health of a resource.

        :param resource_type: the type of resource whose health is to be
            set
        :param resource: the resource whose health is to be set
        :param is_healthy: whether the resource is healthy or not
        """
        self._resource_manager.set_health(resource_type, resource, is_healthy)

    def set_ready(
        self: ControllerResourceManager,
        subarray: str,
        is_ready: bool,
    ) -> None:
        """
        Set the health of a resource.

        :param subarray: the subarray to be set as ready
        :param is_ready: whether the subarray is ready or not
        """
        self._resource_manager.set_ready(subarray, is_ready)

    def allocate(
        self: ControllerResourceManager,
        subarray: str,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Allocate resources to a subarray.

        :param subarray: the subarray to which resources are to be
            allocated
        :param resources: the resources to allocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be allocated. For example:

            .. code-block:: python

                controller_resource_manager.allocate(
                    "low-mccs/subarray/01",
                    stations=[
                        "low-mccs/station/001", "low-mccs/station/002"
                    ],
                    channel_blocks=[2, 3],
                )
        """
        self._resource_manager.allocate(subarray, **resources)

    def deallocate(
        self: ControllerResourceManager,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Deallocate resources (regardless of what subarray they are allocated to.

        :param resources: the resources to deallocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be deallocated. For example:

            .. code-block:: python

                controller_resource_manager.deallocate(
                    stations=[
                        "low-mccs/station/001", "low-mccs/station/002"
                    ],
                    channel_blocks=[2, 3],
                )
        """
        self._resource_manager.deallocate(**resources)

    def deallocate_from(
        self: ControllerResourceManager,
        subarray: str,
    ) -> None:
        """
        Deallocate all resources from a subarray.

        :param subarray: the subarray to which resources are to be
            allocated
        """
        self._resource_manager.deallocate_from(subarray)

    def get_allocated(
        self: ControllerResourceManager,
        subarray: str,
    ) -> Mapping[str, Iterable[str]]:
        """
        Return the resources allocated to a given subarray.

        :param subarray: FQDN of the subarray for which the allocated
            resources are to be returned

        :return: the resources allocated to the subarray.
        """
        return cast(
            Mapping[str, Iterable[str]], self._resource_manager.get_allocated(subarray)
        )
