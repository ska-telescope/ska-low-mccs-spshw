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
from typing import Callable
import unittest

import pytest

from ska_tango_base.control_model import HealthState, PowerMode, SimulationMode

from ska_low_mccs.cluster_manager import (
    ClusterComponentManager,
    ClusterSimulatorComponentManager,
    ClusterSimulator,
)
from ska_low_mccs.component import CommunicationStatus, MessageQueue


@pytest.fixture()
def component_shadow_master_pool_node_health_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> Callable[[list[bool]], None]:
    """
    Return a mock callback for a change in shadow master pool node health.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the health of a node in its shadow master pool has
        changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def cluster_simulator() -> ClusterSimulator:
    """
    Fixture that returns a cluster simulator.

    :return: a cluster simulator
    """
    return ClusterSimulator()


@pytest.fixture()
def cluster_simulator_component_manager(
    message_queue: MessageQueue,
    logger: logging.Logger,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_power_mode_changed_callback: Callable[[PowerMode], None],
    component_fault_callback: Callable[[bool], None],
    component_shadow_master_pool_node_health_changed_callback: Callable[
        [list[HealthState]], None
    ],
) -> ClusterSimulatorComponentManager:
    """
    Return a cluster simulator component manager.

    :param message_queue: the message queue to be used by this component
        manager
    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_shadow_master_pool_node_health_changed_callback:
        callback to be called when the health of a node in the
        shadow pool changes

    :return: a cluster simulator component manager
    """
    return ClusterSimulatorComponentManager(
        message_queue,
        logger,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        component_shadow_master_pool_node_health_changed_callback,
    )


@pytest.fixture()
def cluster_component_manager(
    logger: logging.Logger,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_power_mode_changed_callback: Callable[[PowerMode], None],
    component_fault_callback: Callable[[bool], None],
    message_queue_size_callback: Callable[[int], None],
    component_shadow_master_pool_node_health_changed_callback: Callable[
        [list[HealthState]], None
    ],
) -> ClusterComponentManager:
    """
    Return a cluster component manager in simulation mode.

    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param message_queue_size_callback: callback to be called when the
        size of the message queue changes.
    :param component_shadow_master_pool_node_health_changed_callback:
        callback to be called when the health of a node in the
        shadow pool changes

    :return: a cluster manager for the MCCS cluster manager device, in
        hardware simulation mode
    """
    return ClusterComponentManager(
        logger,
        SimulationMode.TRUE,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        message_queue_size_callback,
        component_shadow_master_pool_node_health_changed_callback,
    )
