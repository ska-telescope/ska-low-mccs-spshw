# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the custum AttributeManagers."""
from __future__ import annotations

import unittest
import unittest.mock
from typing import Any

import pytest

from ska_low_mccs_spshw.tile.tile_poll_management import (
    RequestIterator,
    TileLRCRequest,
    TileRequestProvider,
)
from ska_low_mccs_spshw.tile.tpm_status import TpmStatus


@pytest.fixture(name="request_iterator", scope="module")
def request_iterator_fixture() -> RequestIterator:
    """
    Fixture that returns a RequestIterator instance.

    :return: a RequestIterator instance.
    """
    return RequestIterator()


@pytest.fixture(name="stale_attribute_callback", scope="module")
def stale_attribute_callback_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock to call for value change handling.

    :return: a mock to call for value change handling
    """
    return unittest.mock.Mock()


@pytest.fixture(name="tile_request_provider")
def tile_request_provider_fixture(
    request_iterator: RequestIterator,
    stale_attribute_callback: unittest.mock.Mock,
) -> TileRequestProvider:
    """
    Fixture returning a TileRequestProvider instance.

    :param request_iterator: a `RequestIterator` instance.
    :param stale_attribute_callback: a fixture containing
        a mock to be called when attribute is no longer polled.

    :return: a TileRequestProvider instance.
    """
    return TileRequestProvider(stale_attribute_callback, request_iterator)


class TestRequestProvider:
    """Test the base `AttributeManager` behaviour."""

    def test_commands_take_precedence(
        self: TestRequestProvider,
        tile_request_provider: TileRequestProvider,
    ) -> None:
        """
        Test that commands take precedence over attributes.

        :param tile_request_provider: a `TileRequestProvider` instance.
        """
        request = TileLRCRequest(
            name="initialise",
            command_object=unittest.mock.Mock(),
            task_callback=unittest.mock.Mock(),
        )
        assert not isinstance(
            tile_request_provider.get_request(TpmStatus.INITIALISED), TileLRCRequest
        )
        # Picked up when the TPM is connectable. Or ABORTED after 60 seconds.
        tile_request_provider.enqueue_lrc(request)
        assert isinstance(
            tile_request_provider.get_request(TpmStatus.INITIALISED), TileLRCRequest
        )
        # check that the TileLRCRequest is no longer supplied
        assert not isinstance(
            tile_request_provider.get_request(TpmStatus.INITIALISED), TileLRCRequest
        )

    def test_command_execution_order(
        self: TestRequestProvider, tile_request_provider: TileRequestProvider
    ) -> None:
        """
        Test that commands of equal priority are executed in the ordet they were input.

        :param tile_request_provider: a `TileRequestProvider` instance.
        """
        request_1 = TileLRCRequest(
            name="my_dummy_command_1",
            command_object=unittest.mock.Mock(),
            task_callback=unittest.mock.Mock(),
        )
        request_2 = TileLRCRequest(
            name="my_dummy_command_2",
            command_object=unittest.mock.Mock(),
            task_callback=unittest.mock.Mock(),
        )
        assert not isinstance(
            tile_request_provider.get_request(TpmStatus.INITIALISED), TileLRCRequest
        )
        for x in range(10):
            if x % 2:
                tile_request_provider.enqueue_lrc(request_1, priority=1)
            else:
                tile_request_provider.enqueue_lrc(request_2, priority=1)

        for x in range(10):
            if x % 2:
                assert (
                    tile_request_provider.get_request(TpmStatus.INITIALISED)
                    == request_1
                )
            else:
                assert (
                    tile_request_provider.get_request(TpmStatus.INITIALISED)
                    == request_2
                )

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        "starting_tpm_status",
        TpmStatus,
    )
    @pytest.mark.parametrize(
        "new_tpm_status",
        TpmStatus,
    )
    def test_stale_attributes(
        self: TestRequestProvider,
        tile_request_provider: TileRequestProvider,
        stale_attribute_callback: unittest.mock.Mock,
        request_iterator: RequestIterator,
        starting_tpm_status: TpmStatus,
        new_tpm_status: TpmStatus,
    ) -> None:
        """
        Test that when attributes go stale we notify callback.

        :param tile_request_provider: a `TileRequestProvider` instance.
        :param stale_attribute_callback: a fixture containing
            a mock to be called when attribute is no longer polled.
        :param request_iterator: a `RequestIterator` instance.
        :param starting_tpm_status: a fixture containing
            the starting TpmStatus.
        :param new_tpm_status: a fixture containing
            the new TpmStatus.
        """
        request_iterator._state = starting_tpm_status
        expected_stale_attribute: Any = set(
            request_iterator.allowed_attributes[starting_tpm_status]
        ) - set(request_iterator.allowed_attributes[new_tpm_status])
        # Check the request is from the set of attributes allowed in new TpmStatus.
        assert tile_request_provider.get_request(new_tpm_status) in set(
            request_iterator.allowed_attributes[new_tpm_status]
        )
        # Check that callback is called when any attribute are stale.
        if expected_stale_attribute:
            stale_attribute_callback.assert_called_once_with(expected_stale_attribute)
        else:
            stale_attribute_callback.assert_not_called()
