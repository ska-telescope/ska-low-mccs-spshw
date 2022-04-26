# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a pytest harness for testing the MCCS cluster manager module."""
from __future__ import annotations

import logging
import unittest
from typing import Any, Callable

import pytest
from ska_tango_base.control_model import CommunicationStatus, SimulationMode

from ska_low_mccs.cluster_manager import (
    ClusterComponentManager,
    ClusterSimulator,
    ClusterSimulatorComponentManager,
)


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[list[bool]], None]:
    """
    Return a mock callback for a change in component state.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the state has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of maximum worker threads.

    :return: the number of maximum worker threads.
    """
    return 1


@pytest.fixture()
def cluster_simulator() -> ClusterSimulator:
    """
    Fixture that returns a cluster simulator.

    :return: a cluster simulator
    """
    return ClusterSimulator()


@pytest.fixture()
def cluster_simulator_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[Any], None],
) -> ClusterSimulatorComponentManager:
    """
    Return a cluster simulator component manager.

    :param logger: the logger to be used by this object.
    :param max_workers: the maximum number of worker threads
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes

    :return: a cluster simulator component manager
    """
    return ClusterSimulatorComponentManager(
        logger,
        max_workers,
        communication_status_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def cluster_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[Any], None],
) -> ClusterComponentManager:
    """
    Return a cluster component manager in simulation mode.

    :param logger: the logger to be used by this object.
    :param max_workers: the maximum number of worker threads
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes

    :return: a cluster manager for the MCCS cluster manager device, in
        hardware simulation mode
    """
    return ClusterComponentManager(
        logger,
        max_workers,
        SimulationMode.TRUE,
        communication_status_changed_callback,
        component_state_changed_callback,
    )
