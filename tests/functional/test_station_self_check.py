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

import time
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_sps_station_name
from tests.test_tools import wait_for_lrc_result


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
def test_station_self_check(sps_devices_exported: list[tango.DeviceProxy]) -> None:
    """
    Run a test scenario that checks the SpsStation.SelfCheck() method.

    Any code in this scenario function is run at the *end* of the
    scenario.

    :param sps_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    """
    for device in sps_devices_exported:
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
    sps_devices_exported: list[tango.DeviceProxy],
    exported_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ENGINEERING AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param sps_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.
    :param exported_tiles: A list containing the ``tango.DeviceProxy``
        of the exported tiles. Or Empty list if no devices exported.
    """
    station.subscribe_event(
        "adminmode",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_adminmode"],
    )
    change_event_callbacks.assert_change_event(
        "device_adminmode", Anything, consume_nonmatches=True
    )
    for device in sps_devices_exported:
        device.adminmode = AdminMode.ENGINEERING

    change_event_callbacks.assert_change_event(
        "device_adminmode", AdminMode.ENGINEERING, consume_nonmatches=True
    )

    if any(
        device.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for device in sps_devices_exported
    ):
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

    iters = 0
    while any(
        tile.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in exported_tiles
    ):
        if iters >= 120:
            pytest.fail(
                f"Not all tiles came ON: {[tile.state() for tile in exported_tiles]}"
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
    # We're running a growing batch of tests which are taking longer to run, at the
    # moment about 17-18 mins on average.
    timeout = 20 * 60

    try:
        wait_for_lrc_result(
            device=station,
            uid=command_info["SelfCheck"],
            expected_result=ResultCode.OK,
            timeout=timeout,
        )
    except ValueError:
        print(station.testlogs)
        print(station.testreport)
        pytest.fail("Self Check did not succeed.")
