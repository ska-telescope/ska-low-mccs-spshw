# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains BDD tests for a "Controller Only" deployment of MCCS."""
from __future__ import annotations

import pytest
import tango
from pytest_bdd import given, parsers, scenarios, then, when
from ska_tango_base.control_model import HealthState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.tango_harness import DevicesToLoadType


@pytest.fixture(scope="module")
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    Here we specify that we want a controller-only deployment and provide a custom chart.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/controller_only_configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
        ],
    }


# Map substitution variable name to its type.
EXTRA_TYPES = {
    "initial": str,
    "final": str,
    "command": str,
}

# Specify the types of the parametrized args in the scenario outline.
CONVERTERS = {
    "initial": str,
    "final": str,
    "command": str,
}

scenarios("features/controller_only_deployment.feature")


# This uses the already existing fixture in conftest and just decorates it for use.
@given("MccsController is available", target_fixture="controller_bdd")
def controller_bdd(controller: MccsDeviceProxy) -> MccsDeviceProxy:
    """
    Return a DeviceProxy to an instance of MccsController.

    :param controller: The controller fixture to use.

    :return: A MccsDeviceProxy instance to MccsController stored in the target_fixture `controller_bdd`.
    """
    return controller


@given(
    parsers.cfparse("MccsController is in '{state:w}' state", extra_types=EXTRA_TYPES)
)
@then(
    parsers.cfparse("MccsController is in '{state:w}' state", extra_types=EXTRA_TYPES)
)
def controller_is_in_state(controller_bdd, state):
    """
    Make an assertion that MccsController is in the desired state.

    :raises KeyError: when an invalid State is supplied.

    :param controller_bdd: The MccsDeviceProxy to controller to use.
    :param state: The state that MccsController should be in.
    """
    state_map = {"on": tango.DevState.ON, "disable": tango.DevState.DISABLE}
    if state not in state_map.keys():
        raise KeyError(
            f"State = {state} | Controller state must be one of {list[state_map.keys()]}!"
        )

    assert controller_bdd.state() == state_map[state]


@when(parsers.cfparse("MccsController AdminMode is set to '{admin_mode_value}'"))
def controller_ready_for_commands(controller_bdd, admin_mode_value):
    """
    Set the adminMode of MccsController to the desired value.

    :param controller_bdd: The MccsDeviceProxy to controller to use.
    :param admin_mode_value: The value of AdminMode to set on MccsController.
    """
    controller_bdd.adminMode = admin_mode_value


@given(
    parsers.cfparse(
        "MccsController is in '{health:w}' healthState", extra_types=EXTRA_TYPES
    )
)
@then(
    parsers.cfparse(
        "MccsController is in '{health:w}' healthState", extra_types=EXTRA_TYPES
    )
)
def controller_has_health(controller_bdd, health):
    """
    Make an assertion that MccsController is in the proper HealthState.

    :raises KeyError: when an invalid healthState is supplied.

    :param controller_bdd: The MccsDeviceProxy to controller to use.
    :param health: The healthState that MccsController should have.
    """
    health_map = {
        "unknown": HealthState.UNKNOWN,
        "ok": HealthState.OK,
        "failed": HealthState.FAILED,
        "degraded": HealthState.DEGRADED,
    }
    if health not in health_map.keys():
        raise KeyError(
            f"Health = {health} | Controller health must be one of {list[health_map.keys()]}!"
        )

    assert controller_bdd.HealthState == health_map[health]
