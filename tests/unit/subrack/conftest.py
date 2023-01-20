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
from typing import TypedDict

import pytest
from ska_control_model import PowerState
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.subrack import SubrackComponentManager, SubrackDriver

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
        "task": MockCallable(),
    }


@pytest.fixture()
def subrack_driver(
    subrack_ip: str,
    subrack_port: int,
    logger: logging.Logger,
    callbacks: dict[str, MockCallable],
) -> SubrackDriver:
    """
    Return a subrack driver, configured to talk to a running subrack server.

    (This is a pytest fixture.)

    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks

    :return: a subrack driver.
    """
    return SubrackDriver(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        update_rate=1.0,
    )


@pytest.fixture()
def subrack_component_manager(
    logger: logging.Logger,
    subrack_ip: str,
    subrack_port: int,
    subrack_driver: SubrackDriver,
    initial_power_state: PowerState,
    callbacks: dict[str, MockCallable],
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_ip: the IP address of the subrack
    :param subrack_port: the subrack port
    :param subrack_driver: the subrack driver to use. Normally the
        subrack component manager creates its own driver; here we inject
        this driver instead.
    :param initial_power_state: the initial power state of the upstream
        power supply
    :param callbacks: dictionary of driver callbacks

    :return: an subrack component manager in the specified simulation mode.
    """
    return SubrackComponentManager(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        _driver=subrack_driver,
        _initial_power_state=initial_power_state,
    )
