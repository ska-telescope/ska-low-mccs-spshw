# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains a test for the station syncronisation.

Depending on your exact deployment the individual tests may or may not be run.
This test just checks that anything which can run passes.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_sps_station_name

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


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


@scenario("features/station.feature", "Synchronising time stamping")
def test_tile(sps_devices_trl_exported: list[str]) -> None:
    """
    Run a test scenario that tests the station device.

    :param sps_devices_trl_exported: Fixture containing the trl
        root for all sps devices.
    """
    for device in [tango.DeviceProxy(trl) for trl in sps_devices_trl_exported]:
        device.adminmode = AdminMode.ONLINE


@given("an SPS deployment against HW")
def check_against_hardware(hw_context: bool) -> None:
    """
    Skip the test if not against HW.

    :param hw_context: whether or not the current context is against real HW.
    """
    if not hw_context:
        pytest.skip("This test requires real HW.")


@given("the SpsStation is ON")
def check_spsstation_state(
    station: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    sps_devices_trl_exported: list[str],
    exported_tiles: list[tango.DeviceProxy],
) -> None:
    """
    Check the SpsStation is ON, and all devices are in ONLINE AdminMode.

    :param station: a proxy to the station under test.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    :param sps_devices_trl_exported: Fixture containing the trl
        root for all sps devices.
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
    for device in [tango.DeviceProxy(trl) for trl in sps_devices_trl_exported]:
        device.adminmode = AdminMode.ENGINEERING

    change_event_callbacks.assert_change_event(
        "device_adminmode", AdminMode.ENGINEERING, consume_nonmatches=True
    )
    time.sleep(5)

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

    iters = 0
    while any(
        tile.state() not in [tango.DevState.ON, tango.DevState.ALARM]
        for tile in exported_tiles
    ):
        if iters >= 60:
            pytest.fail(
                f"Not all tiles came ON: {[tile.state() for tile in exported_tiles]}"
            )
        time.sleep(1)
        iters += 1

    assert station.state() == tango.DevState.ON


@given("the station is initialised")
def station_not_synched(station: tango.DeviceProxy) -> None:
    """
    Verify that a device is in the desired state.

    :param station: station device under test.
    """
    if not all(status in ("Synchronised") for status in station.tileProgrammingState):
        station.initialise()
        timeout = 0
        while timeout < 60:
            if all(
                status in ("Synchronised") for status in station.tileProgrammingState
            ):
                break
            time.sleep(1)
            timeout = timeout + 1
        if timeout >= 60:
            assert False, "Stations failed to initialise"


@when("the station is ordered to synchronise")
def sync_station(station: tango.DeviceProxy) -> None:
    """
    Sync the station.

    :param station: station device under test.
    """
    start_time = datetime.strftime(
        datetime.fromtimestamp(int(time.time()) + 2), RFC_FORMAT
    )
    station.StartAcquisition(json.dumps({"start_time": start_time}))


@then("the station becomes synchronised")
def station_is_synced(station: tango.DeviceProxy) -> None:
    """
    Check the station are synced.

    :param station: station device under test.
    """
    deadline = time.time() + 60  # seconds
    print("Waiting for all remaining unprogrammed tiles Synchronise")
    while time.time() < deadline:
        time.sleep(2)

        if all(status == "Synchronised" for status in station.tileProgrammingState):
            break
    else:
        pytest.fail("Timeout in waiting for tiles to Synchronise")
