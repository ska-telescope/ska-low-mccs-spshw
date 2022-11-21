# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS subarray beam module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable

import pytest
from ska_control_model import CommunicationStatus

from ska_low_mccs.subarray_beam import SubarrayBeam, SubarrayBeamComponentManager


@pytest.fixture()
def component_is_beam_locked_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the subarray beam is locked.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that whether the beam is locked has changed
    """
    return mock_callback_factory()


@pytest.fixture()
def is_configured_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[bool], None]:
    """
    Return a mock callback for a change in whether the subarray beam is configured.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that whether the beam is configured has changed
    """
    return mock_callback_factory()


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of worker threads.

    :return: number of worker threads
    """
    return 1


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for a change in the subarray beam state.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        deque factory (i.e. an object that returns mock callback deques when
        called).

    :return: a mock callback deque to be called when the component manager
        detects that the subarray beam state has changed
    """
    return mock_callback_deque_factory()


@pytest.fixture()
def subarray_beam_component(
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SubarrayBeam:
    """
    Fixture that returns a subarray beam component.

    :param logger: a logger for the subarray beam component to use.
    :param max_workers: number of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: a callback to be
        called when the component state changes.

    :return: a subarray beam component
    """
    return SubarrayBeam(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def subarray_beam_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SubarrayBeamComponentManager:
    """
    Return a subarray beam component manager.

    :param logger: the logger to be used by this object.
    :param max_workers: number of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: a callback to be
        called when the component state changes.

    :return: a subarray beam component manager
    """
    return SubarrayBeamComponentManager(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )
