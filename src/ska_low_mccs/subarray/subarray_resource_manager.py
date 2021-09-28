# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements resource management for the MCCS subarray."""
from __future__ import annotations

from typing import Hashable, Iterable
from ska_low_mccs.resource_manager import HealthfulReadyResourceManager


__all__ = ["SubarrayResourceManager"]


class SubarrayResourceManager:
    """A resource manager for the subarray component manager."""

    def __init__(
        self: SubarrayResourceManager,
        subarray_beams: Iterable[str],
        station_beams: Iterable[str],
    ) -> None:
        """
        Initialise a new instance.

        :param subarray_beams: all subarray beams to be managed by this
            resource manager
        :param station_beams: all subarray beams to be managed by this
            resource manager
        """
        self._resource_manager = HealthfulReadyResourceManager(
            subarray_beams,
            {"station_beams"},
            station_beams=station_beams,
        )

    def allocate(
        self: SubarrayResourceManager,
        subarray_beam: str,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Allocate resources to a subarray beam.

        :param subarray_beam: the subarray beam to which resources are to be
            allocated
        :param resources: the resources to allocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be allocated. For example:

            .. code-block:: python

                subarray_resource_manager.allocate(
                    "low-mccs/subarray_beam/01",
                    station_beams=[
                        "low-mccs/beam/001", "low-mccs/beam/002"
                    ],
                )
        """
        self._resource_manager.allocate(subarray_beam, **resources)

    def deallocate(
        self: SubarrayResourceManager,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Deallocate resources (regardless of what subarray beam they are allocated to.

        :param resources: the resources to deallocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be deallocated. For example:

            .. code-block:: python

                subarray_resource_manager.deallocate(
                    station_beams=[
                        "low-mccs/beam/001", "low-mccs/beam/002"
                    ],
                )
        """
        self._resource_manager.deallocate(**resources)

    def deallocate_from(
        self: SubarrayResourceManager,
        subarray_beam: str,
    ) -> None:
        """
        Deallocate all resources from a subarray beam.

        :param subarray_beam: the subarray beam to which resources are to be
            allocated
        """
        self._resource_manager.deallocate_from(subarray_beam)

    def add_resources(
        self: SubarrayResourceManager,
        resources: Iterable[Hashable],
    ) -> None:
        """
        Add a resource to this resource manager.

        :param resources: keyword args, with each keyword being the name
            of a resource type, and the value being the set of resources
            of that type to be added to this resource manager's resources.
        """
        self._resource_manager.add_resources(**resources)

    def remove_resources(
        self: SubarrayResourceManager,
        resources: Iterable[Hashable],
    ) -> None:
        """
        Remove a resource from this resource manager.

        :param resources: keyword args, with each keyword being the name
            of a resource type, and the value being the set of resources
            of that type to be removed from this resource manager's resources.
        """
        self._resource_manager.remove_resources(**resources)

    def add_allocatees(
        self: SubarrayResourceManager,
        allocatees: Iterable[Hashable],
    ) -> None:
        """
        Add a resource to this resource manager.

        :param allocatees: new targets for allocation of resources.
        """
        self._resource_manager.add_allocatees(allocatees)

    def remove_allocatees(
        self: SubarrayResourceManager,
        allocatees: Iterable[Hashable],
    ) -> None:
        """
        Remove a resource to this resource manager.

        :param allocatees: new targets for allocation to remove.
        """
        self._resource_manager.remove_allocatees(allocatees)

    def set_ready(
        self: SubarrayResourceManager,
        subarray_beam: str,
        is_ready: bool,
    ) -> None:
        """
        Set the health of a resource.

        :param subarray_beam: the subarray beam to be set as ready
        :param is_ready: whether the subarray_beam is ready or not
        """
        self._resource_manager.set_ready(subarray_beam, is_ready)

    def set_health(
        self: SubarrayResourceManager,
        resource_type: str,
        resource: Hashable,
        is_healthy: bool,
    ) -> None:
        """
        Set the health of a resource.

        :param resource_type: the resource type of the resource whose
            health is being set
        :param resource: the resource whose health is being set
        :param is_healthy: the new health status of the resource
        """
        self._resource_manager.set_health(resource_type, resource, is_healthy)
