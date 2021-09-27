#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests of the controller resource manager."""
from __future__ import annotations

import pytest

from ska_low_mccs.controller import ControllerResourceManager


class TestControllerResourceManager:
    """Tests of the controller resource manager."""

    def test_validate_subarray(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that a allocation to a dodgy subarray fails validation.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        dodgy_subarray = "low-mccs/subarray/dodgy"
        with pytest.raises(
            ValueError, match=f"Unsupported allocatee: {dodgy_subarray}"
        ):
            controller_resource_manager.allocate(
                dodgy_subarray,
                stations=["low-mccs/station/001", "low-mccs/station/002"],
            )

    def test_validate_resources(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that a dodgy resource fails validation.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        dodgy_station = "low-mccs/station/dodgy"
        with pytest.raises(
            ValueError,
            match=rf"Unsupported resources: {{'stations': \['{dodgy_station}'\]}}.",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/01",
                stations=["low-mccs/station/001", dodgy_station],
            )

    def test_ready_healthy(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that we can't allocate to a subarray that isn't ready.

        nor allocate unhealthy resources.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        with pytest.raises(
            ValueError,
            match=r"Allocatee is unready: low-mccs/subarray/01.",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/01",
                stations=["low-mccs/station/001", "low-mccs/station/002"],
            )

        controller_resource_manager.set_ready("low-mccs/subarray/01", True)

        with pytest.raises(
            ValueError,
            match="Cannot allocate unhealthy resources: "
            r"{'stations': \['low-mccs/station/001', 'low-mccs/station/002'\]}.",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/01",
                stations=["low-mccs/station/001", "low-mccs/station/002"],
            )

        controller_resource_manager.set_health("stations", "low-mccs/station/001", True)

        with pytest.raises(
            ValueError,
            match=r"Cannot allocate unhealthy resources: {'stations': \['low-mccs/station/002'\]}.",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/01",
                stations=["low-mccs/station/001", "low-mccs/station/002"],
            )

        controller_resource_manager.set_health("stations", "low-mccs/station/002", True)

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001", "low-mccs/station/002"],
        )

    def test_resources_cannot_be_overallocated(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that resources cannot be allocated to two subarrays at once.

        Once a resource has been allocated to a subarray, it can be
        reallocated to that same subarray, but cannot be allocated to
        another subarray until it has been deallocated.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        controller_resource_manager.set_health("stations", "low-mccs/station/001", True)
        controller_resource_manager.set_health("stations", "low-mccs/station/002", True)
        controller_resource_manager.set_health("subracks", "low-mccs/subrack/01", True)
        controller_resource_manager.set_ready("low-mccs/subarray/01", True)

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001", "low-mccs/station/002"],
        )

        with pytest.raises(
            ValueError,
            match=r"Cannot allocate resources: {'stations': \['low-mccs/station/001'\]} "
            "to allocatee low-mccs/subarray/02",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/02",
                stations=["low-mccs/station/001"],
                subracks=["low-mccs/subrack/01"],
            )

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001"],
            subracks=["low-mccs/subrack/01"],
        )

    def test_deallocation(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that resources can be allocated after being deallocated.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        controller_resource_manager.set_health("stations", "low-mccs/station/001", True)
        controller_resource_manager.set_health("stations", "low-mccs/station/002", True)
        controller_resource_manager.set_health("subracks", "low-mccs/subrack/01", True)
        controller_resource_manager.set_ready("low-mccs/subarray/01", True)
        controller_resource_manager.set_ready("low-mccs/subarray/02", True)

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001", "low-mccs/station/002"],
            subracks=["low-mccs/subrack/01"],
        )
        controller_resource_manager.deallocate(
            stations=["low-mccs/station/001", "low-mccs/station/002"]
        )

        with pytest.raises(
            ValueError,
            match=r"Cannot allocate resources: {'subracks': \['low-mccs/subrack/01'\]} "
            "to allocatee low-mccs/subarray/02",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/02",
                stations=["low-mccs/station/001"],
                subracks=["low-mccs/subrack/01"],
            )

        controller_resource_manager.allocate(
            "low-mccs/subarray/02",
            stations=["low-mccs/station/001", "low-mccs/station/002"],
        )

        controller_resource_manager.deallocate_from("low-mccs/subarray/02")

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001", "low-mccs/station/002"],
            subracks=["low-mccs/subrack/01"],
        )

    def test_health(
        self, controller_resource_manager: ControllerResourceManager
    ) -> None:
        """
        Test that we can deallocate but not allocate an unhealthy resource.

        :param controller_resource_manager: the controller resource
            manager under test.
        """
        controller_resource_manager.set_ready("low-mccs/subarray/01", True)

        controller_resource_manager.set_health("stations", "low-mccs/station/001", True)

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001"],
        )

        controller_resource_manager.set_health(
            "stations", "low-mccs/station/001", False
        )

        controller_resource_manager.allocate(
            "low-mccs/subarray/01",
            stations=["low-mccs/station/001"],
        )

        controller_resource_manager.deallocate(stations=["low-mccs/station/001"])

        with pytest.raises(
            ValueError,
            match=r"Cannot allocate unhealthy resources: {'stations': \['low-mccs/station/001'\]}.",
        ):
            controller_resource_manager.allocate(
                "low-mccs/subarray/01",
                stations=["low-mccs/station/001"],
            )
