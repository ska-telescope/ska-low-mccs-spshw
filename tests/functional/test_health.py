# -*- coding: utf-8 -*-
# pylint: skip-file
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the bdd test steps of the health aggregation."""
from __future__ import annotations

import json
import time

import pytest
import tango
from pytest_bdd import given, parsers, scenario, scenarios, then, when
from ska_control_model import AdminMode, HealthState
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import (
    get_daq_name,
    get_sps_station_name,
    get_subrack_name,
    get_tile_name,
)

scenarios("./features/health.feature")


@scenario(
    "features/health.feature",
    "Failed when tile monitoring point is out of bounds",
)
def test_failed_when_tile_monitoring_point_is_out_of_bounds(
    device_proxies: dict[str, tango.DeviceProxy]
) -> None:
    """
    Reset Tile health parameters.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param device_proxies: dictionary of proxies with device name as a key.
    """
    device_proxies["Tile"].healthModelParams = "{}"


@scenario(
    "features/health.feature",
    "Failed when subrack monitoring point is out of bounds",
)
def test_failed_when_subrack_monitoring_point_is_out_of_bounds(
    device_proxies: dict[str, tango.DeviceProxy]
) -> None:
    """
    Reset Subrack health parameters.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param device_proxies: dictionary of proxies with device name as a key.
    """
    device_proxies["Subrack"].healthModelParams = json.dumps(
        {"failed_fan_speed_diff": 100000, "degraded_fan_speed_diff": 100000}
    )


@pytest.fixture(name="station_name")
def station_name_fixture(true_context: bool) -> str:
    """
    Return the name of the station under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: the name of the station under test
    """
    if not true_context:
        pytest.skip("This needs to be run in a true-context")
    return "real-daq-1"


@pytest.fixture(name="subrack_id")
def subrack_id_fixture() -> int:
    """
    Get the subrack id to use in the test.

    :return: subrack id.
    """
    return 1


@pytest.fixture(name="tile_id")
def tile_id_fixture() -> int:
    """
    Get the tile id to use in the test.

    :return: tile id.
    """
    return 10


@pytest.fixture(name="device_proxies")
def device_proxies_fixture(
    subrack_id: int, tile_id: int, station_name: str
) -> dict[str, tango.DeviceProxy]:
    """
    Get the dictionary of device proxies.

    The device name is used as a key.

    :param subrack_id: the subrack id to use for the test.
    :param tile_id: the tile id to use for the test.
    :param station_name: the station name to use for the test.
    :return: dictionary of device proxies.
    """
    return {
        "Tile": tango.DeviceProxy(get_tile_name(tile_id, station_name)),
        "Subrack": tango.DeviceProxy(get_subrack_name(subrack_id, station_name)),
        "Station": tango.DeviceProxy(get_sps_station_name(station_name)),
        "DAQ": tango.DeviceProxy(get_daq_name(station_name)),
    }


@given(parsers.cfparse("a {device} that is online"))
def device_online(
    device: str,
    device_proxies: dict[str, tango.DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Put a given device online if it isn't already.

    :param device: device to put online.
    :param device_proxies: dictionary of device proxies.
    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.
    """
    print(f"Turning {device} online")
    device_proxy = device_proxies[device]
    device_proxy.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["device_state"],
    )
    if device_proxy.adminMode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "device_state", tango.DevState.DISABLE
        )

        device_proxy.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "device_state", tango.DevState.UNKNOWN
        )
    change_event_callbacks.assert_change_event("device_state", Anything)


@given("the Station has been commanded to turn on")
@when("the Station has been commanded to turn on")
def station_on(device_proxies: dict[str, tango.DeviceProxy]) -> None:
    """
    Command the station to turn on.

    :param device_proxies: dictionary of device proxies.
    """
    device_proxies["Station"].On()


@given("the Station has been commanded to turn off")
def station_off(device_proxies: dict[str, tango.DeviceProxy]) -> None:
    """
    Command the station to turn off.

    :param device_proxies: dictionary of device proxies.
    """
    device_proxies["Station"].Off()


@given(parsers.cfparse("the {device} reports that its {attribute} is {value}"))
@then(parsers.cfparse("the {device} reports that its {attribute} is {value}"))
def device_verify_attribute(
    device_proxies: dict[str, tango.DeviceProxy],
    device: str,
    attribute: str,
    value: str,
) -> None:
    """
    Verify that a device is in the desired state.

    :param device_proxies: dictionary of device proxies.
    :param device: the device to test.
    :param attribute: the attribute to verify the value of.
    :param value: the value to verify.
    """
    device_proxy = device_proxies[device]
    enum_value = None
    if attribute == "state":
        enum_value = {"ON": tango.DevState.ON, "OFF": tango.DevState.OFF}[value.upper()]
    elif attribute == "HealthState":
        enum_value = {
            "OK": HealthState.OK,
            "DEGRADED": HealthState.DEGRADED,
            "FAILED": HealthState.FAILED,
            "UNKNOWN": HealthState.UNKNOWN,
        }[value]
    timeout = 10
    device_value = None
    for _ in range(timeout):
        if attribute == "state":
            device_value = device_proxy.state()
        elif attribute == "HealthState":
            device_value = device_proxy.healthState
        if device_value == enum_value:
            break
        time.sleep(1)
    if attribute == "HealthState":
        assert (
            device_value == enum_value
        ), f"Expected health to be {enum_value} but got {device_value}, "
        f"Reason: {device_proxy.healthReport}"
    else:
        assert device_value == enum_value


@when("the Tile board temperature thresholds are adjusted")
def set_tile_health_params(device_proxies: dict[str, tango.DeviceProxy]) -> None:
    """
    Set the board temperature thresholds of the Tile.

    :param device_proxies: dictionary of device proxies.
    """
    new_board_params = {
        "temperatures": {"board": {"min": 100, "max": 170}},
    }
    tile_device = device_proxies["Tile"]
    tile_device.healthModelParams = json.dumps(new_board_params)


@when("the Subrack board temperature thresholds are adjusted")
def set_subrack_health_params(device_proxies: dict[str, tango.DeviceProxy]) -> None:
    """
    Set the board temperature thresholds of the Subrack.

    :param device_proxies: dictionary of device proxies.
    """
    new_board_params = {
        "failed_max_board_temp": 170.0,
        "degraded_max_board_temp": 160.0,
        "failed_min_board_temp": 110.0,
        "degraded_min_board_temp": 120.0,
    }
    subrack_device = device_proxies["Subrack"]
    subrack_device.healthModelParams = json.dumps(new_board_params)
