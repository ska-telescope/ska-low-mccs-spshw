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

from typing import Any, Hashable, Iterable, Mapping, Optional, cast
from ska_low_mccs.resource_manager import HealthfulReadyResourceManager


__all__ = ["SubarrayResourceManager"]

class SubarrayResourceManager:
    """A resource manager for the subarray component manager."""

    def __init__(
        self: SubarrayResourceManager,
        stations: Iterable[str],
        subarray_beams: Iterable[str],
        station_beams: Iterable[str],
        channel_blocks: Iterable[int],
    ) -> None:
        """
        Initialise a new instance.

        :param stations: all stations to be managed by this resource
            manager
        :param subarray_beams: all subarray beams to be managed by this
            resource manager
        :param station_beams: all subarray beams to be managed by this
            resource manager
        :param channel_blocks: all channel blocks to be managed by this
            resource manager
        """
        self._resource_manager = HealthfulReadyResourceManager(
            stations,
            {"subracks", "station_beams", "subarray_beams"},
            stations=stations,
            station_beams=station_beams,
            subarray_beams=subarray_beams,
            channel_blocks=channel_blocks,
        )

    def allocate(
        self: SubarrayResourceManager,
        station: str,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Allocate resources to a station.

        :param subarray: the subarray to which resources are to be
            allocated
        :param resources: the resources to allocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be allocated. For example:

            .. code-block:: python

                subarray_resource_manager.allocate(
                    "low-mccs/station/01",
                    station_beams=[
                        "low-mccs/beam/001", "low-mccs/beam/002"
                    ],
                    channel_blocks=[2, 3],
                )
        """
        self._resource_manager.allocate(station, **resources)

    def deallocate(
        self: SubarrayResourceManager,
        **resources: Iterable[Hashable],
    ) -> None:
        """
        Deallocate resources (regardless of what station they are allocated to.

        :param resources: the resources to deallocate. Each keyword
            specifies a resource type, with the value a list of the
            resources of that type to be deallocated. For example:

            .. code-block:: python

                subarray_resource_manager.deallocate(
                    station_beams=[
                        "low-mccs/beam/001", "low-mccs/beam/002"
                    ],
                    channel_blocks=[2, 3],
                )
        """
        self._resource_manager.deallocate(**resources)