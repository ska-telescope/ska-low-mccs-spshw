# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains a test for the SpsStation.SelfCheck() method.

Depending on your exact deployment the individual tests may or may not be run.
This test just checks that anything which can run passes.
"""
from __future__ import annotations

import json
import time
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_sps_station_name


@pytest.fixture(name="station")
def station_fixture(available_stations: list[str]) -> tango.DeviceProxy:
    """
    Fixture containing a proxy to the station under test.

    :param available_stations: the names of the stations we are testing against.

    :returns: a proxy to the station under test.
    """
    return tango.DeviceProxy(get_sps_station_name(available_stations[-1]))


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@scenario("features/station_self_check.feature", "Test SpsStation Self Check")
def test_station_self_check() -> None:
    """
    Run a test scenario that checks the SpsStation.SelfCheck() method.

    Any code in this scenario function is run at the *end* of the
    scenario.
    """
    for device in [
        tango.DeviceProxy(trl)
        for trl in tango.Database().get_device_exported("low-mccs/*")
    ]:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool) -> None:
    """
    Skip the test if not against HW.

    :param hw_context: whether or not the current context is against real HW.
    """
    if not hw_context:
        pytest.skip("This test requires real HW.")


@given("the SpsStation is ON and in ENGINEERING mode")
def check_spsstation_state(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ENGINEERING AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    station.subscribe_event(
        "adminmode",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_adminmode"],
    )
    change_event_callbacks.assert_change_event(
        "device_adminmode", Anything, consume_nonmatches=True
    )
    for device in [
        tango.DeviceProxy(trl)
        for trl in tango.Database().get_device_exported("low-mccs/*")
    ]:
        device.adminmode = AdminMode.ENGINEERING

    change_event_callbacks.assert_change_event(
        "device_adminmode", AdminMode.ENGINEERING, consume_nonmatches=True
    )

    if station.state() != tango.DevState.ON:
        state_callback = MockTangoEventCallbackGroup("state", timeout=300)
        station.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            state_callback["state"],
        )
        state_callback.assert_change_event("state", Anything, consume_nonmatches=True)
        station.on()
        state_callback.assert_change_event(
            "state", tango.DevState.ON, consume_nonmatches=True, lookahead=3
        )

    tile_devices = [
        tango.DeviceProxy(trl)
        for trl in tango.Database().get_device_exported("low-mccs/tile/*")
    ]

    iters = 0
    while any(tile.state() != tango.DevState.ON for tile in tile_devices):
        if iters >= 60:
            pytest.fail(
                f"Not all tiles came ON: {[tile.state() for tile in tile_devices]}"
            )
        time.sleep(1)
        iters += 1

    assert station.state() == tango.DevState.ON


@when("I run the SpsStation Self Check")
def run_station_self_check(station: tango.DeviceProxy, command_info: dict) -> None:
    """
    Run SpsStation.SelfCheck().

    :param station: a proxy to the station under test.
    :param command_info: a dict in which to store command IDs
    """
    _, [command_id] = station.SelfCheck()
    command_info["SelfCheck"] = command_id


@then("the SpsStation Self Check passes")
def check_self_check_result(station: tango.DeviceProxy, command_info: dict) -> None:
    """
    Check the result of SpsStation.SelfCheck().

    :param station: a proxy to the station under test.
    :param command_info: a dict in which to store command IDs

    """
    lrc_result_callback = MockTangoEventCallbackGroup("lrc_result", timeout=300)
    station.subscribe_event(
        "longRunningCommandResult",
        tango.EventType.CHANGE_EVENT,
        lrc_result_callback["lrc_result"],
    )
    lrc_result_callback.assert_change_event(
        "lrc_result",
        Anything,
        consume_nonmatches=True,
    )
    try:
        lrc_result_callback.assert_change_event(
            "lrc_result",
            (
                command_info["SelfCheck"],
                json.dumps([ResultCode.OK, "Tests completed OK."]),
            ),
            consume_nonmatches=True,
            lookahead=5,
        )
    except AssertionError:
        print(station.testlogs)
        print(station.testreport)
        pytest.fail("Self Check did not succeed.")
