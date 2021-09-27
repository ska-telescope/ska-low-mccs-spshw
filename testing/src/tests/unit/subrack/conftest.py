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

from typing import Any, Callable, Optional
import unittest.mock

import pytest
import requests

from ska_tango_base.control_model import PowerMode, SimulationMode, TestMode

from ska_low_mccs.component import MessageQueue
from ska_low_mccs.subrack import (
    SubrackDriver,
    SubrackSimulator,
    SubrackSimulatorComponentManager,
    SwitchingSubrackComponentManager,
    SubrackComponentManager,
)

from ska_low_mccs.testing.mock import MockCallable


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
def subrack_simulator(
    component_progress_changed_callback: Callable[[int], None],
) -> SubrackSimulator:
    """
    Fixture that returns a TPM simulator.

    :param component_progress_changed_callback: callback to be
        called when the progress value changes

    :return: a subrack simulator
    """
    subrack_simulator = SubrackSimulator()
    subrack_simulator.set_progress_changed_callback(component_progress_changed_callback)
    return subrack_simulator


@pytest.fixture()
def subrack_simulator_component_manager(
    message_queue: MessageQueue,
    logger: logging.Logger,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_progress_changed_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
) -> SubrackSimulatorComponentManager:
    """
    Return an subrack simulator component manager.

    (This is a pytest fixture.)

    :param message_queue: the message queue to be used by this component
        manager
    :param logger: the logger to be used by this object.
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_progress_changed_callback: callback to be
        called when the progress value changes
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes

    :return: an subrack simulator component manager.
    """
    return SubrackSimulatorComponentManager(
        message_queue,
        logger,
        communication_status_changed_callback,
        component_fault_callback,
        component_progress_changed_callback,
        component_tpm_power_changed_callback,
    )


@pytest.fixture()
def switching_subrack_component_manager(
    message_queue: MessageQueue,
    logger: logging.Logger,
    subrack_ip: str,
    subrack_port: int,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_progress_changed_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
) -> SwitchingSubrackComponentManager:
    """
    Return an component manager that switched between subrack driver and simulator.

    (This is a pytest fixture.)

    :param message_queue: the message queue to be used by this component
        manager
    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_progress_changed_callback: callback to be
        called when the progress value changes
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes

    :return: an subrack component manager in simulation mode.
    """
    return SwitchingSubrackComponentManager(
        SimulationMode.TRUE,
        TestMode.NONE,
        message_queue,
        logger,
        subrack_ip,
        subrack_port,
        communication_status_changed_callback,
        component_fault_callback,
        component_progress_changed_callback,
        component_tpm_power_changed_callback,
    )


# TODO: pytest is partially typehinted but does not yet export monkeypatch
@pytest.fixture()
def subrack_driver(
    monkeypatch: pytest.monkeypatch,  # type: ignore[name-defined]
    message_queue: MessageQueue,
    logger: logging.Logger,
    subrack_ip: str,
    subrack_port: int,
    communication_status_changed_callback: MockCallable,
    component_fault_callback: MockCallable,
    component_progress_changed_callback: MockCallable,
    component_tpm_power_changed_callback: MockCallable,
) -> SubrackDriver:
    """
    Return a subrack driver (with HTTP connection monkey-patched).

    (This is a pytest fixture.)

    :param monkeypatch: the pytest monkey-patching fixture
    :param message_queue: the message queue to be used by this component
        manager
    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param communication_status_changed_callback: callback to be
        called when the status of the communications channel between
        the component manager and its component changes
    :param component_fault_callback: callback to be called when the
        component faults (or stops faulting)
    :param component_progress_changed_callback: callback to be
        called when the progress value changes
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes

    :return: an subrack simulator component manager.
    """

    class MockResponse:
        """A mock class to replace requests.Response."""

        ATTRIBUTE_VALUES = {
            "tpm_on_off": [False, False, False],
            "backplane_temperatures": SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURES,
            "board_temperatures": SubrackSimulator.DEFAULT_BOARD_TEMPERATURES,
            "board_current": SubrackSimulator.DEFAULT_BOARD_CURRENT,
            "subrack_fan_speeds": SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS,
            "subrack_fan_speeds_percent": [
                speed * 100.0 / SubrackSimulator.MAX_SUBRACK_FAN_SPEED
                for speed in SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
            ],
            "subrack_fan_modes": SubrackSimulator.DEFAULT_SUBRACK_FAN_MODES,
            "tpm_count": SubrackSimulator.TPM_BAY_COUNT,
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
            self.status_code = requests.codes.ok

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
        message_queue,
        logger,
        subrack_ip,
        subrack_port,
        communication_status_changed_callback,
        component_fault_callback,
        component_progress_changed_callback,
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
    component_progress_changed_callback: MockCallable,
    message_queue_size_callback: Callable[[int], None],
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
    :param component_progress_changed_callback: callback to be
        called when the progress value changes
    :param message_queue_size_callback: callback to be called when the
        size of the message queue changes.
    :param component_tpm_power_changed_callback: callback to be
        called when the power mode of an tpm changes
    :param initial_power_mode: the initial power mode of the simulated
        power supply.

    :return: an subrack component manager in the specified simulation mode.
    """
    return SubrackComponentManager(
        SimulationMode.TRUE,
        TestMode.NONE,
        logger,
        subrack_ip,
        subrack_port,
        communication_status_changed_callback,
        component_power_mode_changed_callback,
        component_fault_callback,
        component_progress_changed_callback,
        message_queue_size_callback,
        component_tpm_power_changed_callback,
        initial_power_mode,
    )
