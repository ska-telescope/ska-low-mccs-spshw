# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for MCCS integration tests."""
from __future__ import annotations

from typing import Callable

import pytest
from ska_low_mccs_common.testing.mock import MockChangeEventCallback


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `tango_harness` fixture, causing them to be sandboxed
    in their own process.

    :param item: the collected test for which this hook is called
    """
    if "tango_harness" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(name="state_changed_callback_factory")
def state_changed_callback_factory_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> Callable[[], MockChangeEventCallback]:
    """
    Return a mock change event callback factory for device state change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback factory to be registered with
        a device via a change event subscription, so that it gets called
        when the device state changes.
    """

    def _factory() -> MockChangeEventCallback:
        return mock_change_event_callback_factory("state")

    return _factory


@pytest.fixture(name="obs_state_changed_callback_factory")
def obs_state_changed_callback_factory_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> Callable[[], MockChangeEventCallback]:
    """
    Return a mock change event callback factory for device obs state change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback factory to be registered with
        a device via a change event subscription, so that it gets called
        when the device state changes.
    """

    def _factory() -> MockChangeEventCallback:
        return mock_change_event_callback_factory("obsState")

    return _factory


@pytest.fixture(name="controller_device_state_changed_callback")
def controller_device_state_changed_callback_fixture(
    state_changed_callback_factory: Callable[[], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for controller device state change.

    :param state_changed_callback_factory: fixture that provides a mock
        change event callback factory for state change events.

    :return: a mock change event callback to be registered with the
        controller device via a change event subscription, so that it
        gets called when the device state changes.
    """
    return state_changed_callback_factory()


@pytest.fixture(name="controller_device_admin_mode_changed_callback")
def controller_device_admin_mode_changed_callback_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for controller device admin mode change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the
        controller via a change event subscription, so that it gets called
        when the device admin mode changes.
    """
    return mock_change_event_callback_factory("adminMode")


@pytest.fixture(name="subarray_device_obs_state_changed_callback")
def subarray_device_obs_state_changed_callback_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for subarray device obs state change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the
        subarray device via a change event subscription, so that it gets
        called when the device obs state changes.
    """
    return mock_change_event_callback_factory("obsState")


# @pytest.fixture()
# def subrack_device_admin_mode_changed_callback(
#     mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
# ) -> MockChangeEventCallback:
#     """
#     Return a mock change event callback for subrack device admin mode change.
#
#     :param mock_change_event_callback_factory: fixture that provides a
#         mock change event callback factory (i.e. an object that returns
#         mock callbacks when called).
#
#     :return: a mock change event callback to be registered with the
#         subrack via a change event subscription, so that it gets called
#         when the device admin mode changes.
#     """
#     return mock_change_event_callback_factory("adminMode")


# @pytest.fixture()
# def subrack_device_state_changed_callback(
#     mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
# ) -> MockChangeEventCallback:
#     """
#     Return a mock change event callback for subrack device state change.
#
#     :param mock_change_event_callback_factory: fixture that provides a
#         mock change event callback factory (i.e. an object that returns
#         mock callbacks when called).
#
#     :return: a mock change event callback to be registered with the
#         subrack via a change event subscription, so that it gets called
#         when the device state changes.
#     """
#     return mock_change_event_callback_factory("state")


@pytest.fixture(name="tile_device_admin_mode_changed_callback")
def tile_device_admin_mode_changed_callback_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for tile device admin mode change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the tile
        device via a change event subscription, so that it gets called
        when the device admin mode changes.
    """
    return mock_change_event_callback_factory("adminMode")


@pytest.fixture(name="tile_device_state_changed_callback")
def tile_device_state_changed_callback_fixture(
    mock_change_event_callback_factory: Callable[[str], MockChangeEventCallback],
) -> MockChangeEventCallback:
    """
    Return a mock change event callback for tile device state change.

    :param mock_change_event_callback_factory: fixture that provides a
        mock change event callback factory (i.e. an object that returns
        mock callbacks when called).

    :return: a mock change event callback to be registered with the tile
        device via a change event subscription, so that it gets called
        when the device state changes.
    """
    return mock_change_event_callback_factory("state")
