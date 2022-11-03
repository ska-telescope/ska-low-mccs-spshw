# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS transient buffer module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable

import pytest
from ska_control_model import CommunicationStatus

from ska_low_mccs.transient_buffer import (
    TransientBuffer,
    TransientBufferComponentManager,
)


@pytest.fixture()
def transient_buffer_component(logger: logging.Logger) -> TransientBuffer:
    """
    Fixture that returns a transient buffer.

    :param logger: a logger for the transient buffer to use.

    :return: a transient buffer
    """
    return TransientBuffer(logger)


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of maximum worker threads.

    :return: the number of maximum worker threads.
    """
    return 1


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for antenna state change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the state of its component has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def transient_buffer_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[Any], None],
) -> TransientBufferComponentManager:
    """
    Return a transient buffer component manager.

    :param logger: the logger to be used by this object.
    :param max_workers: the maximum worker threads available
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called
        when the component state changes

    :return: a transient buffer component manager
    """
    return TransientBufferComponentManager(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )
