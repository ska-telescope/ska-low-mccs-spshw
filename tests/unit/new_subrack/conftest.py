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
import threading
import time
from typing import Any, TypedDict

import pytest
import uvicorn
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.subrack import FanMode, NewSubrackDriver, SubrackData
from ska_low_mccs_spshw.subrack.subrack_simulator import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import configure_server

SubrackInfoType = TypedDict(
    "SubrackInfoType", {"host": str, "port": int, "simulator": bool}
)


@pytest.fixture()
def callbacks() -> dict[str, MockCallable]:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return {
        "communication_status": MockCallable(),
        "component_state": MockCallable(),
    }


@pytest.fixture(name="subrack_simulator_config")
def subrack_simulator_config_fixture() -> dict[str, Any]:
    """
    Return attribute values with which the subrack simulator is configured.

    :return: a key-value dictionary of attribute values with which the
        subrack simulator is configured.
    """
    return {
        "tpm_present": [False, True, False, False, True, False, False, False],
        "tpm_on_off": [False, False, False, False, False, False, False, False],
        "backplane_temperatures": [39.0, 40.0],
        "board_temperatures": [40.0, 41.0],
        "board_current": 1.1,
        "power_supply_currents": [4.2, 5.8],
        "power_supply_fan_speeds": [90.0, 100.0],
        "power_supply_voltages": [12.0, 12.1],
        "subrack_fan_speeds": [4999.0, 5000.0, 5001.0, 5002.0],
        "subrack_fan_modes": [FanMode.AUTO, FanMode.AUTO, FanMode.AUTO, FanMode.AUTO],
        "tpm_currents": [0.4] * 8,
        "tpm_temperatures": [40.0] * 8,
        "tpm_voltages": [12.0] * 8,
    }


@pytest.fixture(name="subrack_simulator_attribute_values")
def subrack_simulator_attribute_values_fixture(
    subrack_simulator_config,
) -> dict[str, Any]:
    """
    Return attribute values that the subrack simulator is expected to report.

    :param subrack_simulator_config: attribute values with which the
        subrack simulator is configured.

    :return: a key-value dictionary of attribute values that the subrack
        simulator is expected to report.
    """

    def _approxify(list_of_floats):
        return [pytest.approx(element) for element in list_of_floats]

    return {
        "tpm_present": subrack_simulator_config["tpm_present"],
        "tpm_count": subrack_simulator_config["tpm_present"].count(True),
        "tpm_on_off": subrack_simulator_config["tpm_on_off"],
        "backplane_temperatures": _approxify(
            subrack_simulator_config["backplane_temperatures"]
        ),
        "board_temperatures": _approxify(
            subrack_simulator_config["board_temperatures"]
        ),
        "board_current": pytest.approx(subrack_simulator_config["board_current"]),
        "power_supply_currents": _approxify(
            subrack_simulator_config["power_supply_currents"]
        ),
        "power_supply_fan_speeds": _approxify(
            subrack_simulator_config["power_supply_fan_speeds"]
        ),
        "power_supply_voltages": _approxify(
            subrack_simulator_config["power_supply_voltages"]
        ),
        "power_supply_powers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["power_supply_currents"],
                subrack_simulator_config["power_supply_voltages"],
            )
        ],
        "subrack_fan_speeds": subrack_simulator_config["subrack_fan_speeds"],
        "subrack_fan_speeds_percent": [
            pytest.approx(s * 100.0 / SubrackData.MAX_SUBRACK_FAN_SPEED)
            for s in subrack_simulator_config["subrack_fan_speeds"]
        ],
        "subrack_fan_modes": subrack_simulator_config["subrack_fan_modes"],
        "tpm_currents": _approxify(subrack_simulator_config["tpm_currents"]),
        "tpm_temperatures": _approxify(subrack_simulator_config["tpm_temperatures"]),
        "tpm_voltages": _approxify(subrack_simulator_config["tpm_voltages"]),
        "tpm_powers": [
            pytest.approx(c * v)
            for c, v in zip(
                subrack_simulator_config["tpm_currents"],
                subrack_simulator_config["tpm_voltages"],
            )
        ],
    }


@pytest.fixture()
def subrack_simulator(subrack_simulator_config: dict[str, Any]) -> SubrackSimulator:
    """
    Return a subrack simulator.

    This is the backend python object, not the web server interface to it.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a subrack simulator.
    """
    return SubrackSimulator(**subrack_simulator_config)


@pytest.fixture()
def subrack_server(subrack_simulator: SubrackSimulator) -> None:
    """
    Yield a running subrack server.

    :param subrack_simulator: the actual backend simulator to which this
        server provides an interface.

    :yields: a running subrack server.
    """

    class ThreadableServer(uvicorn.Server):
        def install_signal_handlers(self):
            pass

    import socket

    my_socket = socket.socket()
    server_config = configure_server(subrack_simulator, host="127.0.0.1", port=0)

    the_server = ThreadableServer(config=server_config)
    server_thread = threading.Thread(target=the_server.run, args=([my_socket],))
    server_thread.start()

    while not the_server.started:
        time.sleep(1e-3)
    yield my_socket.getsockname()
    the_server.should_exit = True
    server_thread.join()


@pytest.fixture()
def subrack_ip(subrack_server: tuple[str, int]) -> str:
    """
    Return the IP address of the subrack.

    :param subrack_server: a running subrack server, available at this
        IP address. (This pytest fixture does not actually need the
        subrack server fixture. However specifying this dependency
        prevents the subrack server fixture from being torn down for as
        long as this fixture remains in use.)

    :return: the IP address of the subrack.
    """
    return "127.0.0.1"


@pytest.fixture()
def subrack_port(subrack_server: None) -> int:
    """
    Return the subrack port.

    :param subrack_server: a running subrack server.
    :return: the subrack port.
    """
    return subrack_server[1]


@pytest.fixture()
def subrack_driver(
    subrack_ip: str,
    subrack_port: int,
    logger: logging.Logger,
    callbacks: dict[str, MockCallable],
) -> NewSubrackDriver:
    """
    Return a subrack driver, configured to talk to a running subrack server.

    (This is a pytest fixture.)

    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks

    :return: a subrack driver.
    """
    return NewSubrackDriver(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        update_rate=1.0,
    )
