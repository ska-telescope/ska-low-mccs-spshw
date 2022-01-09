# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest test harness for testing the MCCS APIU module."""
from __future__ import annotations

import random

import logging
from typing import Callable

import unittest.mock

import pytest

from ska_tango_base.control_model import PowerMode, SimulationMode

from ska_low_mccs.apiu import (
    ApiuSimulator,
    ApiuSimulatorComponentManager,
    ApiuComponentManager,
    SwitchingApiuComponentManager,
)
from ska_low_mccs.component import CommunicationStatus

from ska_low_mccs.testing.mock import MockCallable, MockChangeEventCallback


@pytest.fixture()
def apiu_antenna_count() -> int:
    """
    Return the number of antennas in the APIU.

    (This is a pytest fixture.)

    :return: the number of antennas in the APIU
    """
    return 16


@pytest.fixture()
def component_antenna_power_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for when the power mode of a component's antenna changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the power mode of a
        component's antenna changes.
    """
    return mock_callback_factory()


@pytest.fixture()
def initial_power_mode() -> PowerMode:
    """
    Return the initial power mode of the APIU's simulated power supply.

    :return: the initial power mode of the APIU's simulated power
        supply.
    """
    return PowerMode.OFF


@pytest.fixture()
def apiu_simulator(
    apiu_antenna_count: int,
    initial_fault: bool = False,
    #    component_fault_callback: MockCallable,
) -> ApiuSimulator:
    """
    Return an APIU simulator.

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param initial_fault: whether the simulator should start by
        simulating a fault.

    :return: an APIU simulator
    """
    #     :param component_fault_callback: callback to be called when the
    #         component faults (or stops faulting)
    return ApiuSimulator(
        apiu_antenna_count,
        initial_fault,
        #        component_fault_callback,
    )


@pytest.fixture()
def apiu_simulator_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_antenna_power_changed_callback: MockCallable,
) -> ApiuSimulatorComponentManager:
    """
    Return an APIU simulator component manager.

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_antenna_power_changed_callback: callback to be
        called when the power mode of an antenna changes

    :return: an APIU simulator component manager.
    """
    return ApiuSimulatorComponentManager(
        apiu_antenna_count,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_fault_callback,
        component_antenna_power_changed_callback,
    )


@pytest.fixture()
def switching_apiu_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_fault_callback: Callable[[bool], None],
    component_antenna_power_changed_callback: MockCallable,
) -> SwitchingApiuComponentManager:
    """
    Return an component manager that switched between APIU driver and simulator.

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_antenna_power_changed_callback: callback to be
        called when the power mode of an antenna changes

    :return: an APIU component manager in simulation mode.
    """
    return SwitchingApiuComponentManager(
        SimulationMode.TRUE,
        apiu_antenna_count,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_fault_callback,
        component_antenna_power_changed_callback,
    )


@pytest.fixture()
def apiu_component_manager(
    apiu_antenna_count: int,
    logger: logging.Logger,
    lrc_result_changed_callback: MockChangeEventCallback,
    communication_status_changed_callback: MockCallable,
    component_power_mode_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_antenna_power_changed_callback: MockCallable,
    initial_power_mode: PowerMode,
) -> ApiuComponentManager:
    """
    Return an APIU component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param apiu_antenna_count: the number of antennas in the APIU
    :param logger: the logger to be used by this object.
    :param lrc_result_changed_callback: a callback to
        be used to subscribe to device LRC result changes
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_antenna_power_changed_callback: callback to be
        called when the power mode of an antenna changes
    :param initial_power_mode: the initial power mode of the simulated
        power supply.

    :return: an APIU component manager in the specified simulation mode.
    """
    return ApiuComponentManager(
        SimulationMode.TRUE,
        apiu_antenna_count,
        logger,
        lrc_result_changed_callback,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        component_antenna_power_changed_callback,
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
