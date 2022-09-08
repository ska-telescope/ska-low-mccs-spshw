# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the BDD tests for TMC-MCCS interactions."""
from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

import tango

from ska_tango_base.control_model import AdminMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockChangeEventCallback


@scenario(
    "features/controller_no_subservients.feature",
    "MCCS Turn on and off low telescope",
)
def test_turn_on_low_telescope(
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    This is run at the end of the scenario. Turn MCCS Controller Off.

    :param controller: a proxy to the controller device
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    """
    print("when is this run")
#     controller.Off()
#     controller_device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)
#     assert controller.state() == tango.DevState.OFF


@given(parsers.parse("we have a running instance of mccs"))
def we_have_a_running_instance_of_mccs(
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Assert the existence/availability of a subsystem.

    :param subsystem_name: name of the subsystem
    :param controller: a proxy to the controller device
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    """
    assert subsystem_name in ["mccs", "tmc"]

    if subsystem_name == "tmc":
        return

    controller.add_change_event_callback(
        "state", controller_device_state_changed_callback
    )

    admin_mode_0_device_sequence = {
        controller,
    }

    for device in admin_mode_0_device_sequence:
        assert device.adminMode == AdminMode.ONLINE

    controller_device_state_changed_callback.assert_last_change_event(
        tango.DevState.OFF
    )


@given(parsers.parse("mccs is ready to receive commands"))
def mccs_is_ready_to_receive_on_command(
    controller: MccsDeviceProxy,
) -> None:
    """
    Assert that a mccs is ready to receive an on command.

    :param controller: a proxy to the controller device
    """
    assert controller.state() == tango.DevState.OFF


@when(parsers.parse("client tells mccs controller to turn on"))
def client_tells_mccs_controller_to_turn_on() -> None:
    """Turn on the MCCS subsystem.

    :param state_name: asserted state of the device either "off" or "on"
    """
    controller.On()


@when(parsers.parse("client tells mccs controller to turn off"))
def client_tells_mccs_controller_to_turn_off() -> None:
    """Turn on the MCCS subsystem.

    :param state_name: asserted state of the device either "off" or "on"
    """
    controller.Off()


@then(parsers.parse("mccs controller state is {state_name}"))
def check_mccs_controller_state(
    state_name: str,
    controller: MccsDeviceProxy,
    controller_device_state_changed_callback: MockChangeEventCallback,
) -> None:
    """
    Assert that mccs controller is on/off.

    :param state_name: asserted state of the device either "off" or "on"
    :param controller: a proxy to the controller device
    :param controller_device_state_changed_callback: a callback to be
        used to subscribe to controller state change
    """
    state_map = {
        "off": tango.DevState.OFF,
        "on": tango.DevState.ON,
    }
    device_state = state_map[state_name]
    controller_device_state_changed_callback.assert_last_change_event(device_state)
    assert controller.state() == device_state
