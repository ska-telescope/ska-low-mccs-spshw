# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defines a pytest harness for testing the MCCS PaSD bus module."""


from __future__ import annotations

import logging
import unittest.mock
from typing import Callable, Optional

import pytest
import pytest_mock
import yaml
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, PowerState, SimulationMode

from ska_low_mccs import MccsPasdBus
from ska_low_mccs.pasd_bus import (
    PasdBusComponentManager,
    PasdBusSimulator,
    PasdBusSimulatorComponentManager,
)
from ska_low_mccs.testing.mock import MockCallable
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque


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
    Return a mock callback for a change in the pasd bus state.

    :param mock_callback_deque_factory: fixture that provides a mock callback
        deque factory (i.e. an object that returns mock callback deques when
        called).

    :return: a mock callback deque to be called when the component manager
        detects that the pasd bus state has changed
    """
    return mock_callback_deque_factory()


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
def mock_pasd_bus_simulator(
    mocker: pytest_mock.MockerFixture,
    pasd_bus_simulator: PasdBusSimulator,
) -> unittest.mock.Mock:
    """
    Return a mock PaSD bus simulator.

    The returned mock wraps a real simulator instance, so it will behave
    like a real one, but we can access it as a mock too, for example
    assert calls.

    :param mocker: fixture that wraps unittest.Mock
    :param pasd_bus_simulator: a real PaSD bus simulator to wrap in a
        mock.

    :return: a mock PaSD bus simulator
    """
    mock_simulator = mocker.Mock(wraps=pasd_bus_simulator)

    # "wraps" doesn't handle properties -- we have to add them manually
    for property_name in [
        "fndh_psu48v_voltages",
        "fndh_psu5v_voltage",
        "fndh_psu48v_current",
        "fndh_psu48v_temperature",
        "fndh_psu5v_temperature",
        "fndh_pcb_temperature",
        "fndh_outside_temperature",
        "fndh_status",
        "fndh_service_led_on",
        "fndh_ports_power_sensed",
        "fndh_ports_connected",
        "fndh_port_forcings",
        "fndh_ports_desired_power_online",
        "fndh_ports_desired_power_offline",
        "smartbox_input_voltages",
        "smartbox_power_supply_output_voltages",
        "smartbox_statuses",
        "smartbox_power_supply_temperatures",
        "smartbox_outside_temperatures",
        "smartbox_pcb_temperatures",
        "smartbox_service_leds_on",
        "smartbox_fndh_ports",
        "smartboxes_desired_power_online",
        "smartboxes_desired_power_offline",
        "antennas_online",
        "antenna_forcings",
        "antennas_tripped",
        "antennas_power_sensed",
        "antennas_desired_power_online",
        "antennas_desired_power_offline",
        "antenna_currents",
    ]:
        setattr(
            type(mock_simulator),
            property_name,
            mocker.PropertyMock(
                return_value=getattr(pasd_bus_simulator, property_name)
            ),
        )

    return mock_simulator


@pytest.fixture()
def pasd_bus_simulator_component_manager(
    mock_pasd_bus_simulator: unittest.mock.Mock,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> PasdBusSimulatorComponentManager:
    """
    Return a PaSD bus simulator component manager.

    (This is a pytest fixture.)

    :param mock_pasd_bus_simulator: a mock PaSD bus simulator to be used
        by the PaSD bus simulator component manager
    :param logger: the logger to be used by this object.
    :param max_workers: number of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: a PaSD bus simulator component manager.
    """
    return PasdBusSimulatorComponentManager(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
        _simulator=mock_pasd_bus_simulator,
    )


@pytest.fixture()
def pasd_bus_component_manager(
    pasd_bus_simulator_component_manager: PasdBusSimulatorComponentManager,
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: MockCallable,
    component_state_changed_callback: MockCallableDeque,
) -> PasdBusComponentManager:
    """
    Return a PaSD bus component manager.

    :param pasd_bus_simulator_component_manager: a pre-initialised
        PaSD bus simulator component manager to be used by the PaSD bus
        component manager
    :param logger: the logger to be used by this object.
    :param max_workers: number of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: a PaSD bus component manager
    """
    return PasdBusComponentManager(
        SimulationMode.TRUE,
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
        _simulator_component_manager=pasd_bus_simulator_component_manager,
    )


@pytest.fixture()
def mock_component_manager(
    mocker: pytest_mock.mocker,  # type: ignore[valid-type]
    unique_id: str,
) -> unittest.mock.Mock:
    """
    Return a mock component manager.

    The mock component manager is a simple mock except for one bit of
    extra functionality: when we call start_communicating() on it, it
    makes calls to callbacks signaling that communication is established
    and the component is off.

    :param mocker: pytest wrapper for unittest.mock
    :param unique_id: a unique id used to check Tango layer functionality

    :return: a mock component manager
    """
    mock = mocker.Mock()  # type: ignore[attr-defined]
    mock.is_communicating = False

    def _start_communicating(mock: unittest.mock.Mock) -> None:
        mock.is_communicating = True
        mock._communication_status_changed_callback(CommunicationStatus.NOT_ESTABLISHED)
        mock._communication_status_changed_callback(CommunicationStatus.ESTABLISHED)
        mock._component_state_changed_callback({"power_state": PowerState.OFF})

    mock.start_communicating.side_effect = lambda: _start_communicating(mock)

    mock.return_value = unique_id, ResultCode.QUEUED

    return mock


@pytest.fixture()
def patched_pasd_bus_device_class(
    mock_component_manager: unittest.mock.Mock,
) -> type[MccsPasdBus]:
    """
    Return a pasd bus device that is patched with a mock component manager.

    :param mock_component_manager: the mock component manager with
        which to patch the device

    :return: a pasd bus device that is patched with a mock component
        manager.
    """

    class PatchedMccsPasdBus(MccsPasdBus):
        """A pasd bus device patched with a mock component manager."""

        def create_component_manager(
            self: PatchedMccsPasdBus,
        ) -> unittest.mock.Mock:
            """
            Return a mock component manager instead of the usual one.

            :return: a mock component manager
            """
            self._communication_status: Optional[CommunicationStatus] = None
            #             self._component_power_state: Optional[PowerState] = None

            mock_component_manager._communication_status_changed_callback = (
                self._communication_status_changed_callback
            )
            mock_component_manager._component_state_changed_callback = (
                self._component_state_changed_callback
            )
            return mock_component_manager

    return PatchedMccsPasdBus
