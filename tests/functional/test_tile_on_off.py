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
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_low_mccs_common.testing.tango_harness import TangoHarness
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

scenarios("./features/tile_on_off.feature")


@pytest.fixture(name="subrack_proxy")
def subrack_proxy_fixture(tango_harness: TangoHarness) -> tango.DeviceProxy:
    """
    Return the subrack device proxy.

    :param tango_harness: a Tango harness against which to run tests of the deployment.

    :return: the subrack device proxy
    """
    return tango_harness.get_device("low-mccs/subrack/01")


@pytest.fixture(name="tile_proxy")
def tile_proxy_fixture(tango_harness: TangoHarness) -> tango.DeviceProxy:
    """
    Return the tile device proxy.

    :param tango_harness: a Tango harness against which to run tests of the deployment.

    :return: the tile device proxy
    """
    return tango_harness.get_device("low-mccs/tile/0001")


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary  of change event callbacks.

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
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check starting state of the subrack.

    If the starting adminMode of the subrack is OFFLINE and the state is DISABLED
    then set the adminMode to ONLINE

    :param subrack_proxy: a tango.DeviceProxy to the subrack device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    starting_admin_mode = subrack_proxy.adminMode
    admin_mode_changed_callback = change_event_callbacks["subrack_admin_mode_changed"]
    subrack_proxy.subscribe_event(
        "adminMode",
        tango.EventType.CHANGE_EVENT,
        admin_mode_changed_callback,
    )
    admin_mode_changed_callback.assert_change_event(AdminMode.OFFLINE)

    starting_state = subrack_proxy.state()
    state_changed_callback = change_event_callbacks["subrack_state_changed"]
    subrack_proxy.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
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
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check starting state of the tile.

    If the starting adminMode of the tile is OFFLINE and the state is DISABLED
    then set the adminMode to ONLINE

    :param tile_proxy: a tango.DeviceProxy to the tile device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    starting_admin_mode = tile_proxy.adminMode
    tile_admin_mode_changed_callback = change_event_callbacks["tile_admin_mode_changed"]
    tile_proxy.subscribe_event(
        "adminMode",
        tango.EventType.CHANGE_EVENT,
        tile_admin_mode_changed_callback,
    )
    tile_admin_mode_changed_callback.assert_change_event(AdminMode.OFFLINE)

    starting_state = tile_proxy.state()
    state_changed_callback = change_event_callbacks["tile_state_changed"]
    tile_proxy.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        state_changed_callback,
    )
    state_changed_callback.assert_change_event(tango.DevState.DISABLE)

    if starting_admin_mode == AdminMode.ONLINE:
        assert starting_state == tango.DevState.ON
    else:
        assert starting_state == tango.DevState.DISABLE
        tile_proxy.write_attribute("adminMode", AdminMode.ONLINE)
        tile_admin_mode_changed_callback.assert_change_event(AdminMode.ONLINE)


@when("the subrack is turned ON")
def turn_subrack_on(
    subrack_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Turn the subrack on.

    :param subrack_proxy: a tango.DeviceProxy to the subrack device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    subrack_proxy.subscribe_event(
        "longRunningCommandStatus",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_lrc_changed"],
    )
    details = change_event_callbacks["subrack_lrc_changed"].assert_against_call()
    [result_code], [command_id] = subrack_proxy.on()
    assert result_code == ResultCode.QUEUED
    while not result_code == "COMPLETED":
        details = change_event_callbacks["subrack_lrc_changed"].assert_against_call()
        _, result_code = details["attribute_value"]
    final_state = subrack_proxy.state()
    assert final_state == tango.DevState.ON


@when("the tile is turned ON")
def turn_tile_on(
    tile_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Turn the tile on.

    :param tile_proxy: a tango.DeviceProxy to the tile device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    tile_proxy.subscribe_event(
        "longRunningCommandStatus",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_lrc_changed"],
    )
    details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
    [result_code], [command_id] = tile_proxy.on()
    assert result_code == ResultCode.QUEUED
    while not result_code == "COMPLETED":
        details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
        _, result_code = details["attribute_value"]


@then("the subrack reports the tpm power state is ON")
def check_subrack_reports_tile_tpm_on(
    subrack_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the subrack reports the power to the tile/tpm is on.

    :param subrack_proxy: a tango.DeviceProxy to the subrack device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    power_state = subrack_proxy.tpm1PowerState

    assert power_state == PowerState.ON


@then("the tile reports its state is ON")
def check_tile_on(
    tile_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the tile on.

    :param tile_proxy: a tango.DeviceProxy to the tile device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    final_state = tile_proxy.state()
    print(f"\n\n\n\n\n {final_state}")
    assert final_state == tango.DevState.ON


@when("the tile is turned OFF")
def turn_tile_off(
    tile_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Turn the tile off.

    :param tile_proxy: a tango.DeviceProxy to the tile device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    # not sure whether we need to subscribe again.
    #     tile_proxy.subscribe_event(
    #         "longRunningCommandStatus",
    #         tango.EventType.CHANGE_EVENT,
    #         change_event_callbacks["tile_lrc_changed"],
    #     )
    #     details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
    [result_code], [command_id] = tile_proxy.off()
    assert result_code == ResultCode.QUEUED
    while not result_code == "COMPLETED":
        details = change_event_callbacks["tile_lrc_changed"].assert_against_call()
        _, result_code = details["attribute_value"]


@then("the subrack reports the tpm power state as OFF")
def check_subrack_reports_tile_off(
    subrack_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the subrack reports the power to the tile/tpm is off.

    :param subrack_proxy: a tango.DeviceProxy to the subrack device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    power_state = subrack_proxy.tpm1PowerState
    assert power_state == PowerState.OFF


@then("the tile reports it's state OFF")
def check_tile_off(
    tile_proxy: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the tile off.

    :param tile_proxy: a tango.DeviceProxy to the tile device
    :param change_event_callbacks: callbacks for CHANGE_EVENT event types.
    """
    final_state = tile_proxy.state()
    assert final_state == tango.DevState.DISABLED
