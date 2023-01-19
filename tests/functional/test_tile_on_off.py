# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains a simple tests of the MCCS PaSD bus Tango device."""
from __future__ import annotations

import pytest
import tango
import time
from pytest_bdd import scenarios, given, then, when, parsers
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from ska_control_model import AdminMode, ResultCode
#from ska_tango_testing.mock.placeholders import OneOf

scenarios("./features/tile_on_off.feature")


@pytest.fixture(name="subrack_proxy")
def subrack_proxy_fixture(tango_harness: TangoHarness) -> tango.DeviceProxy:
    """
    Return the subrack device proxy.

    :return: the subrack device proxy
    """
    return tango_harness.get_device("low-mccs/subrack/01")

@pytest.fixture(name="tile_proxy")
def tile_proxy_fixture(tango_harness: TangoHarness) -> tango.DeviceProxy:
    """
    Return the tile device proxy.

    :return: the tile device proxy
    """
    return tango_harness.get_device("low-mccs/tile/0001")

@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary  of change event callbacks
    
    :return: a callback group
    """
    return MockTangoEventCallbackGroup(
        "tile_state_changed",
        "tile_admin_mode_changed",
        "tile_lrc_changed",
        "subrack_state_changed",
        "subrack_admin_mode_changed",
        "subrack_lrc_changed",
     )


@given(parsers.cfparse("the subrack is ONLINE"))
def check_subrack_online(
    subrack_proxy: tango.DeviceProxy,
    change_event_callbacks,
) -> None:
    starting_admin_mode = subrack_proxy.adminMode
    admin_mode_changed_callback = change_event_callbacks["subrack_admin_mode_changed"]
    id = subrack_proxy.subscribe_event(
        "adminMode", tango.EventType.CHANGE_EVENT,
        admin_mode_changed_callback,
    
    )
    admin_mode_changed_callback.assert_change_event(AdminMode.OFFLINE)

    starting_state = subrack_proxy.state()
    state_changed_callback = change_event_callbacks["subrack_state_changed"]
    id = subrack_proxy.subscribe_event(
        "state", tango.EventType.CHANGE_EVENT,
        state_changed_callback,
    
    )
    state_changed_callback.assert_change_event(tango.DevState.DISABLE)

    if starting_admin_mode == AdminMode.ONLINE:
        assert starting_state == tango.DevState.ON
    else:
        assert starting_state == tango.DevState.DISABLE
        subrack_proxy.adminMode = AdminMode.ONLINE
        admin_mode_changed_callback.assert_change_event(AdminMode.ONLINE)

@given("the tile is ONLINE")
def check_tile_online(
    tile_proxy: tango.DeviceProxy,
    change_event_callbacks,
) -> None:
    starting_admin_mode = tile_proxy.adminMode
    tile_admin_mode_changed_callback = change_event_callbacks["tile_admin_mode_changed"]
    id = tile_proxy.subscribe_event(
        "adminMode", tango.EventType.CHANGE_EVENT,
        tile_admin_mode_changed_callback,
      
    )
    tile_admin_mode_changed_callback.assert_change_event(AdminMode.OFFLINE)

    starting_state = tile_proxy.state()
    state_changed_callback = change_event_callbacks["tile_state_changed"]
    id = tile_proxy.subscribe_event(
        "state", tango.EventType.CHANGE_EVENT,
        state_changed_callback,
     
    )
    state_changed_callback.assert_change_event(tango.DevState.DISABLE)

    if starting_admin_mode == AdminMode.ONLINE:
        assert starting_state == tango.DevState.ON
    else:
        assert starting_state == tango.DevState.DISABLE
        tile_proxy.write_attribute("adminMode",AdminMode.ONLINE)
        tile_admin_mode_changed_callback.assert_change_event(AdminMode.ONLINE)

@when(parsers.cfparse("the subrack is turned ON"))
def turn_subrack_on(
    change_event_callbacks,
    subrack_proxy,
) -> None:
    id = subrack_proxy.subscribe_event(
        "longRunningCommandStatus",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_lrc_changed"],
    )
    details = change_event_callbacks["subrack_lrc_changed"].assert_against_call()
    [result_code],[command_id] = subrack_proxy.on()
    assert result_code == ResultCode.QUEUED
    while not result_code == "COMPLETED":
        details = change_event_callbacks["subrack_lrc_changed"].assert_against_call()
        _, result_code = details["attribute_value"]
    final_state = subrack_proxy.state()
    assert final_state == tango.DevState.ON

@when("the tile is turned ON")
def turn_tile_on(
    change_event_callbacks,
    tile_proxy,
) -> None:
    id = tile_proxy.subscribe_event(
        "longRunningCommandStatus",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_lrc_changed"],
    )
    details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
    [result_code],[command_id] = tile_proxy.on()
    assert result_code == ResultCode.QUEUED
    while not result_code == "FAILED":
        details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
        _, result_code = details["attribute_value"]
        print(f"£££££££££££££££ {result_code}")

@then("the subrack reports its state is ON")
def check_tile_on(
    change_event_callbacks,
) -> None:
    print(f"£££££££££££££££")

@then("the tile reports its state is ON")
def check_tile_on(
    change_event_callbacks,
) -> None:
#     final_state = tile_proxy.state()
#     assert final_state == tango.DevState.ON
#     print(f"£££££££££££££££ {final_state}")
    print(f"£££££££££££££££")

@when("the tile is turned OFF")
def turn_tile_off(
    change_event_callbacks,
) -> None:
    print(f"£££££££££££££££")

@then("the tile reports it's state OFF")
def check_tile_off(
    change_event_callbacks,
) -> None:
    print(f"£££££££££££££££")

@then("the subrack reports the tile as OFF")
def check_tile_off(
    change_event_callbacks,
) -> None:
    print(f"£££££££££££££££")

