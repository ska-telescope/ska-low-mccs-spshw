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
