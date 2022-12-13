# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS subrack module."""
from __future__ import annotations

import logging
import unittest.mock
from typing import Any, Callable, Optional

import pytest
import requests
from ska_control_model import CommunicationStatus, PowerState, SimulationMode

from ska_low_mccs_spshw.subrack import (
    SubrackComponentManager,
    SubrackData,
    SubrackDriver,
    SubrackSimulator,
    SubrackSimulatorComponentManager,
    SwitchingSubrackComponentManager,
)


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
def max_workers() -> int:
    """
    Return the number of worker threads.

    (This is a pytest fixture.)

    :return: the number of worker threads
    """
    return 1


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
def initial_power_state() -> PowerState:
    """
    Return the initial power mode of the subrack's simulated power supply.

    :return: the initial power mode of the subrack's simulated power
        supply.
    """
    return PowerState.OFF


@pytest.fixture()
def subrack_simulator(
    component_progress_changed_callback: Callable[[int], None],
) -> SubrackSimulator:
    """
    Fixture that returns a subrack simulator.

    :param component_progress_changed_callback: callback to be
        called when the progress value changes

    :return: a subrack simulator
    """
    subrack_simulator = SubrackSimulator()
    subrack_simulator.set_progress_changed_callback(component_progress_changed_callback)
    return subrack_simulator


@pytest.fixture()
def subrack_simulator_component_manager(
    logger: logging.Logger,
    max_workers: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SubrackSimulatorComponentManager:
    """
    Return a subrack simulator component manager.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object
    :param max_workers: nos of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: a subrack simulator component manager.
    """
    return SubrackSimulatorComponentManager(
        logger,
        max_workers,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def switching_subrack_component_manager(
    logger: logging.Logger,
    max_workers,
    subrack_ip: str,
    subrack_port: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SwitchingSubrackComponentManager:
    """
    Return an component manager that switched between subrack driver and simulator.

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback  to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be called when the
        component state changes

    :return: an subrack component manager in simulation mode.
    """
    return SwitchingSubrackComponentManager(
        SimulationMode.TRUE,
        logger,
        max_workers,
        subrack_ip,
        subrack_port,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def subrack_driver(
    monkeypatch: pytest.MonkeyPatch,
    logger: logging.Logger,
    max_workers,
    subrack_ip: str,
    subrack_port: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
) -> SubrackDriver:
    """
    Return a subrack driver (with HTTP connection monkey-patched).

    (This is a pytest fixture.)

    :param monkeypatch: the pytest monkey-patching fixture
    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param max_workers: nos of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the state changes

    :return: an subrack simulator component manager.
    """

    class MockResponse:
        """A mock class to replace requests.Response."""

        status_code = 200
        ATTRIBUTE_VALUES = {
            "tpm_on_off": [False, False, False],
            "backplane_temperatures": SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURES,
            "board_temperatures": SubrackSimulator.DEFAULT_BOARD_TEMPERATURES,
            "board_current": SubrackSimulator.DEFAULT_BOARD_CURRENT,
            "subrack_fan_speeds": SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS,
            "subrack_fan_speeds_percent": [
                speed * 100.0 / SubrackData.MAX_SUBRACK_FAN_SPEED
                for speed in SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
            ],
            "subrack_fan_modes": SubrackSimulator.DEFAULT_SUBRACK_FAN_MODES,
            "tpm_count": SubrackData.TPM_BAY_COUNT,
            #  "tpm_temperatures" is not implemented in driver
            "tpm_powers": [
                SubrackSimulator.DEFAULT_TPM_VOLTAGE
                * SubrackSimulator.DEFAULT_TPM_CURRENT
            ]
            * 8,
            "tpm_voltages": [SubrackSimulator.DEFAULT_TPM_VOLTAGE] * 8,
            "power_supply_fan_speeds": SubrackSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
            "power_supply_currents": SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENTS,
            "power_supply_powers": SubrackSimulator.DEFAULT_POWER_SUPPLY_POWERS,
            "power_supply_voltages": SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGES,
            "tpm_present": SubrackSimulator.DEFAULT_TPM_PRESENT,
            "tpm_currents": [SubrackSimulator.DEFAULT_TPM_CURRENT] * 8,
        }

        def __init__(
            self: MockResponse, params: Optional[dict[str, str]] = None
        ) -> None:
            """
            Initialise a new instance.

            :param params: requests.get parameters for which values are
                to be returned in this response.
            """
            self._json: dict[str, Any] = {}

            if params is not None:
                if params["type"] == "command":
                    self._json = {
                        "status": "OK",
                        "info": f"{params['param']} completed OK",
                        "command": params["param"],
                        "retvalue": "",
                    }
                elif params["type"] == "getattribute":
                    self._json = {
                        "status": "OK",
                        "info": f"{params['param']} completed OK",
                        "attribute": params["param"],
                        "value": self.ATTRIBUTE_VALUES[params["param"]],
                    }

        def json(self: MockResponse) -> dict[str, str]:
            """
            Replace the patched :py:meth:`request.Response.json` with mock.

            This implementation always returns the same key-value pair.

            :return: a dictionary with a single key-value pair in it.
            """
            return self._json

    def mock_request(method: str, url: str, **kwargs: Any) -> MockResponse:
        """
        Replace requests.request method with a mock method.

        :param method: "GET" or "POST"
        :param url: the URL
        :param kwargs: other keyword args

        :return: a response
        """
        return MockResponse()

    def mock_get(url: str, params: Any = None, **kwargs: Any) -> MockResponse:
        """
        Replace requests.get with mock method.

        :param url: the URL
        :param params: arguments to the GET
        :param kwargs: other keyword args

        :return: a response
        """
        return MockResponse(params)

    monkeypatch.setattr(requests, "request", mock_request)
    monkeypatch.setattr(requests, "get", mock_get)

    return SubrackDriver(
        logger,
        max_workers,
        subrack_ip,
        subrack_port,
        communication_state_changed_callback,
        component_state_changed_callback,
    )


@pytest.fixture()
def component_manager_with_upstream_power_supply():
    """
    Mock callable.

    :return: the mock callable
    """
    return unittest.mock.MagicMock


@pytest.fixture()
def subrack_component_manager_mocked_upstream_power(
    logger: logging.Logger,
    component_manager_with_upstream_power_supply,
    max_workers: int,
    subrack_ip: str,
    subrack_port: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
    initial_power_state: PowerState,
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes
    :param initial_power_state: the initial power mode of the simulated
        power supply.
    :param component_manager_with_upstream_power_supply: mocked component_manager

    :return: an subrack component manager in the specified simulation mode.
    """
    return SubrackComponentManager(
        SimulationMode.TRUE,
        logger,
        max_workers,
        subrack_ip,
        subrack_port,
        communication_state_changed_callback,
        component_state_changed_callback,
        initial_power_state,
    )


@pytest.fixture()
def subrack_component_manager(
    logger: logging.Logger,
    max_workers: int,
    subrack_ip: str,
    subrack_port: int,
    communication_state_changed_callback: Callable[[CommunicationStatus], None],
    component_state_changed_callback: Callable[[dict[str, Any]], None],
    initial_power_state: PowerState,
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param max_workers: nos. of worker threads
    :param communication_state_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_state_changed_callback: callback to be
        called when the component state changes
    :param initial_power_state: the initial power mode of the simulated
        power supply.

    :return: an subrack component manager in the specified simulation mode.
    """
    return SubrackComponentManager(
        SimulationMode.TRUE,
        logger,
        max_workers,
        subrack_ip,
        subrack_port,
        communication_state_changed_callback,
        component_state_changed_callback,
        initial_power_state,
    )
