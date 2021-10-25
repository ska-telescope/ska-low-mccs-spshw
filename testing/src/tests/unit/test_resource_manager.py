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

from typing import Iterable
import pytest

from ska_low_mccs.resource_manager import ResourcePool


@pytest.fixture()
def channel_blocks() -> list[int]:
    """
    Return the channel blocks controlled by this controller.

    :return: the channel blocks controller by this controller.
    """
    return list(range(0, 2))


@pytest.fixture()
def resource_pool(
    channel_blocks: Iterable[int],
) -> ResourcePool:
    """
    Return a resource pool for testing.

    :param channel_blocks: ordinal numbers of all channel blocks

    :return: a resource pool for testing
    """
    return ResourcePool(
        channel_blocks=channel_blocks,
    )


class TestResourcePool:
    """Tests of the resource pool."""

    def test_get_free_resource(
        self: TestResourcePool, resource_pool: ResourcePool
    ) -> None:
        """
        Test the resource pool's get_free_resource() method.

        :param resource_pool: the resource pool under test.
        """
        assert resource_pool.get_free_resource("channel_blocks") == 0
        assert resource_pool.get_free_resource("channel_blocks") == 1
        with pytest.raises(
            ValueError, match=r"No free resources of type: channel_blocks"
        ):
            resource_pool.get_free_resource("channel_blocks")

    def test_free_resources(self, resource_pool: ResourcePool) -> None:
        """
        Test the resource pool's free_resources() method.

        :param resource_pool: the resource pool under test.
        """
        channel_block_1 = resource_pool.get_free_resource("channel_blocks")
        with pytest.raises(
            ValueError, match=r"Resource unknown_channel_block not in pool."
        ):
            resource_pool.free_resources({"channel_blocks": ["unknown_channel_block"]})
        resource_pool.free_resources({"channel_blocks": [channel_block_1]})
        assert channel_block_1 == resource_pool.get_free_resource("channel_blocks")

    def test_free_all_resources(self, resource_pool: ResourcePool) -> None:
        """
        Test the resource pool's free_all_resource() method.

        :param resource_pool: the resource pool under test.
        """
        assert resource_pool.get_free_resource("channel_blocks") is not None
        assert resource_pool.get_free_resource("channel_blocks") is not None
        resource_pool.free_all_resources("channel_blocks")

        assert resource_pool.get_free_resource("channel_blocks") == 0
        assert resource_pool.get_free_resource("channel_blocks") == 1
        resource_pool.free_all_resources()

        assert resource_pool.get_free_resource("channel_blocks") == 0
        assert resource_pool.get_free_resource("channel_blocks") == 1
        with pytest.raises(
            ValueError, match=r"No free resources of type: channel_blocks"
        ):
            resource_pool.get_free_resource("channel_blocks")
