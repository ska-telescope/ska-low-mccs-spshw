# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest test harness for testing the MCCS APIU module."""
from __future__ import annotations

import logging
import random
import unittest.mock
from typing import Any, Callable

import pytest
from ska_tango_base.control_model import CommunicationStatus, PowerState, SimulationMode

from ska_low_mccs.apiu import (
    ApiuComponentManager,
    ApiuSimulator,
    ApiuSimulatorComponentManager,
    SwitchingApiuComponentManager,
)
from ska_low_mccs.testing.mock import MockCallableDeque


@pytest.fixture()
def apiu_antenna_count() -> int:
    """
    Return the number of antennas in the APIU.

    (This is a pytest fixture.)

    :return: the number of antennas in the APIU
    """
    return 16


@pytest.fixture()
def max_workers() -> int:
    """
    Return the number of worker threads.

    (This is a pytest fixture.)

    :return: the number of worker threads
    """
    return 1


@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for when the state of a component changes.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the state of a
        component changes.
    """
    return mock_callback_deque_factory()


@pytest.fixture()
def initial_power_mode() -> PowerState:
    """
    Return the initial power mode of the APIU's simulated power supply.

    :return: the initial power mode of the APIU's simulated power
        supply.
    """
    return PowerState.OFF


@pytest.fixture()
def apiu_simulator(
    apiu_antenna_count: int,
    component_state_changed_callback: MockCallable,
    initial_fault: bool = False,
) -> ApiuSimulator:
    """
    Return an APIU simulator (This is a pytest fixture).

    :param apiu_antenna_count: the number of antennas in the APIU
    :param component_state_changed_callback: callback to be called when the
            component faults (or stops faulting)
    :param initial_fault: whether the simulator should start by
        simulating a fault.

    :return: an APIU simulator
    """
    return ApiuSimulator(
        apiu_antenna_count,
        component_state_changed_callback,
        initial_fault,
    )


@pytest.fixture()
def apiu_simulator_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> ApiuSimulatorComponentManager:
    """
    Return an APIU simulator component manager.

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param max_workers: nos of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: an APIU simulator component manager.
    """
    return ApiuSimulatorComponentManager(
        apiu_antenna_count,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def switching_apiu_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    max_workers,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SwitchingApiuComponentManager:
    """
    Return an component manager that switched between APIU driver and simulator.

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback  to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: an APIU component manager in simulation mode.
    """
    return SwitchingApiuComponentManager(
        SimulationMode.TRUE,
        apiu_antenna_count,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def apiu_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
    initial_power_mode: PowerState,
) -> ApiuComponentManager:
    """
    Return an APIU component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes
    :param initial_power_mode: the initial power mode of the simulated
        power supply.

    :return: an APIU component manager in the specified simulation mode.
    """
    return ApiuComponentManager(
        SimulationMode.TRUE,
        apiu_antenna_count,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
        initial_power_mode,
    )


@pytest.fixture()
def random_current() -> Callable[[], float]:
    """
    Return a callable that returns a random current value.

    :return: a callable that returns a random current value
    """
    return lambda: random.uniform(0.5, 1.0)


@pytest.fixture()
def random_humidity() -> Callable[[], float]:
    """
    Return a callable that returns a random humidity value.

    :return: a callable that returns a random humidity value
    """
    return lambda: random.uniform(5, 40.0)


@pytest.fixture()
def random_temperature() -> Callable[[], float]:
    """
    Return a callable that returns a random temperature.

    :return: a callable that returns a random temperature
    """
    return lambda: random.uniform(42.0, 47.0)


@pytest.fixture()
def random_voltage() -> Callable[[], float]:
    """
    Return a callable that returns a random voltage.

    :return: a callable that returns a random voltage
    """
    return lambda: random.uniform(11.5, 12.5)
