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
from ska_low_mccs.resource_manager import HealthfulReadyResourceManager, ResourcePool


__all__ = ["ControllerResourceManager"]

class ControllerResourceManager:
    """A resource manager for the controller component manager."""

    def __init__(
        self: ControllerResourceManager,
        subarrays: Iterable[str],
        subracks: Iterable[str],
        subarray_beams: Iterable[str],
        station_beams: Iterable[str],
        channel_blocks: Iterable[int],
    ) -> None:
        """
        Initialise a new instance.

        :param subarrays: all subarrays to be managed by this resource
            manager
        :param subracks: all subracks to be managed by this resource
            manager
        :param subarray_beams: all subarray beams to be managed by this
            resource manager
        :param station_beams: all station beams to be managed by this
            resource manager (as a resource pool)
        :param channel_blocks: all channel blocks to be managed by this
            resource manager
        """
        self._resource_manager = HealthfulReadyResourceManager(
            subarrays,
            {"station_beams", "subracks", "subarray_beams"},
            subracks=subracks,
            subarray_beams=subarray_beams,
            channel_blocks=channel_blocks,
            station_beams=station_beams,
        )
        self.resource_pool = ResourcePool(
            station_beams=station_beams,
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
        station_beams = []        

        #scrape stations from iterable - these are not a resource
        #stations can be shared between subarrays - only need station_fqdn to assign other resources to
        if "stations" in resources:
            stations = resources.pop("stations", None)
            #one station beam per station per subarray beam
            #get free station beam for each station
            for station in stations:
                station_beams.append(self._resource_pool.getFreeResource("station_beams"))

        resources.update({"station_beams": station_beams})
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
