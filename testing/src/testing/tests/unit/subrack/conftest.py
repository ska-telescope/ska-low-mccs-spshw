#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module defined a pytest harness for testing the MCCS subrack module."""
from __future__ import annotations

import logging

from typing import Callable
import unittest.mock

import pytest

from ska_tango_base.control_model import PowerMode, SimulationMode

from ska_low_mccs.subrack import (
    SubrackSimulator,
    SubrackSimulatorComponentManager,
    SwitchingSubrackComponentManager,
    SubrackComponentManager,
)

from testing.harness.mock import MockCallable


@pytest.fixture()
def component_tpm_power_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for when the power mode of a component's TPM changes.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the power mode of a
        component's TPM changes.
    """
    return mock_callback_factory()


@pytest.fixture()
def subrack_ip() -> str:
    """
    Return the IP address of the subrack.

    :return: the IP address of the subrack.
    """
    return "0.0.0.0"


@pytest.fixture()
def subrack_port() -> int:
    """
    Return the subrack port.

    :return: the subrack port.
    """
    return 10000


@pytest.fixture()
def initial_power_mode() -> PowerMode:
    """
    Return the initial power mode of the subrack's simulated power supply.

    :return: the initial power mode of the subrack's simulated power
        supply.
    """
    return PowerMode.OFF


@pytest.fixture()
def subrack_simulator() -> SubrackSimulator:
    """
    Fixture that returns a TPM simulator.

    :return: a subrack simulator
    :rtype:
        :py:class:`ska_low_mccs.subrack.subrack_simulator.SubrackSimulator`
    """
    return SubrackSimulator()


@pytest.fixture()
def subrack_simulator_component_manager(
    logger: logging.Logger,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
) -> SubrackSimulatorComponentManager:
    """
    Return an subrack simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes

    :return: an subrack simulator component manager.
    """
    return SubrackSimulatorComponentManager(
        logger,
        communication_status_changed_callback,
        component_fault_callback,
        component_tpm_power_changed_callback,
    )


@pytest.fixture()
def switching_subrack_component_manager(
    logger: logging.Logger,
    subrack_ip: str,
    subrack_port: int,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
) -> SwitchingSubrackComponentManager:
    """
    Return an component manager that switched between subrack driver and simulator.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes

    :return: an subrack component manager in simulation mode.
    """
    return SwitchingSubrackComponentManager(
        SimulationMode.TRUE,
        logger,
        subrack_ip,
        subrack_port,
        communication_status_changed_callback,
        component_fault_callback,
        component_tpm_power_changed_callback,
    )


@pytest.fixture()
def subrack_component_manager(
    logger: logging.Logger,
    subrack_ip: str,
    subrack_port: int,
    communication_status_changed_callback: MockCallable,
    component_power_mode_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
    initial_power_mode: PowerMode,
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_power_mode_changed_callback: callback to be
        called when the component power mode changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes
    :param initial_power_mode: the initial power mode of the simulated
        power supply.

    :return: an subrack component manager in the specified simulation mode.
    """
    return SubrackComponentManager(
        SimulationMode.TRUE,
        logger,
        subrack_ip,
        subrack_port,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        component_tpm_power_changed_callback,
        initial_power_mode,
    )
