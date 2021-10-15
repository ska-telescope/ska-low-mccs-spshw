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
"""This module defines a pytest harness for testing the MCCS PaSD bus module."""


from __future__ import annotations

import logging

from typing import Callable

import pytest
import yaml

from ska_tango_base.control_model import SimulationMode

from ska_low_mccs.pasd_bus import (
    PasdBusSimulator,
    PasdBusSimulatorComponentManager,
    PasdBusComponentManager,
)

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.component import MessageQueue
from ska_low_mccs.testing.mock import MockCallable


@pytest.fixture()
def pasd_config_path() -> str:
    """
    Return the path to a YAML file that specifies the PaSD configuration.

    :return: the path to a YAML file that specifies the PaSD
        configuration.
    """
    return "src/ska_low_mccs/pasd_bus/pasd_configuration.yaml"


@pytest.fixture()
def station_id() -> int:
    """
    Return the id of the station whose configuration will be used in testing.

    :return: the id of the station whose configuration will be used in
        testing.
    """
    return 1


@pytest.fixture()
def pasd_config(pasd_config_path: str, station_id: int) -> dict:
    """
    Return the PaSD config that the pasd bus device uses.

    :param pasd_config_path: path to a YAML file that specifies the PaSD
        configuration
    :param station_id: id of the staion whose configuration will be used
        in testing.

    :return: the PaSD config that the PaSD bus object under test uses.

    :raises yaml.YAMLError: if the config file could not be parsed.
    """
    with open(pasd_config_path, "r") as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError:
            raise
    return config["stations"][station_id - 1]


@pytest.fixture()
def pasd_bus_simulator(
    pasd_config_path: str,
    station_id: int,
    logger: logging.Logger,
) -> PasdBusSimulator:
    """
    Fixture that returns a PaSD bus simulator.

    :param pasd_config_path: path to a YAML file that specifies the PaSD
        configuration.
    :param station_id: the id of the station whose PaSD bus we are
        simulating.
    :param logger: a logger for the PaSD bus simulator to use.

    :return: a PaSD bus simulator
    """
    return PasdBusSimulator(pasd_config_path, station_id, logger)


@pytest.fixture()
def pasd_bus_simulator_component_manager(
    message_queue: MessageQueue,
    logger: logging.Logger,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
) -> PasdBusSimulatorComponentManager:
    """
    Return a PaSD bus simulator component manager.

    (This is a pytest fixture.)

    :param message_queue: the message queue to be used by this component
        manager
    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)

    :return: a PaSD bus simulator component manager.
    """
    return PasdBusSimulatorComponentManager(
        message_queue,
        logger,
        communication_status_changed_callback,
        component_fault_callback,
    )


@pytest.fixture()
def pasd_bus_component_manager(
    logger: logging.Logger,
    communication_status_changed_callback: Callable[[CommunicationStatus], None],
    component_fault_callback: MockCallable,
    message_queue_size_callback: Callable[[int], None],
) -> PasdBusComponentManager:
    """
    Return a PaSD bus component manager.

    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param message_queue_size_callback: callback to be called when the
        size of the message queue changes.

    :return: a PaSD bus component manager
    """
    return PasdBusComponentManager(
        SimulationMode.TRUE,
        logger,
        communication_status_changed_callback,
        component_fault_callback,
        message_queue_size_callback,
    )
