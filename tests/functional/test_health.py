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
import os
import time
from typing import Any, Callable

import pytest
import tango
from pytest_bdd import given, parsers, scenario, scenarios, then, when
from ska_control_model import AdminMode, HealthState
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_sps_station_name

scenarios("./features/health.feature")


@scenario(
    "features/health.feature",
    "Failed when tile monitoring point is out of bounds",
)
def test_failed_when_tile_monitoring_point_is_out_of_bounds(
    station_devices: dict[str, tango.DeviceProxy]
) -> None:
    """
    Reset Tile health parameters.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param station_devices: dictionary of proxies with device name as a key.
    """
    for tile in station_devices["Tiles"]:
        tile.healthModelParams = "{}"


@scenario(
    "features/health.feature",
    "Failed when subrack monitoring point is out of bounds",
)
def test_failed_when_subrack_monitoring_point_is_out_of_bounds(
    station_devices: dict[str, tango.DeviceProxy]
) -> None:
    """
    Reset Subrack health parameters.

    Any code in this scenario method is run at the *end* of the
    scenario.

    :param station_devices: dictionary of proxies with device name as a key.
    """
    for subrack in station_devices["Subracks"]:
        subrack.healthModelParams = json.dumps(
            {"failed_fan_speed_diff": 100000, "degraded_fan_speed_diff": 100000}
        )


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@pytest.fixture(name="attribute_read_info")
def attribute_read_fixture() -> dict[str, Any]:
    """
    Fixture to store attribute values.

    :returns: Empty list.
    """
    return {}


@pytest.fixture(name="excluded_tile_attributes")
def excluded_tile_attributes_fixture() -> list[str]:
    """
    Fixture to store attributes to exclude from Tile check.

    :returns: Attribute list.
    """
    return [
        "buildState",
        "fortyGbDestinationIps",
        "fortyGbDestinationPorts",
        "clockPresent",
        "sysrefPresent",
    ]


@pytest.fixture(name="station_name")
def station_name_fixture(true_context: bool) -> str:
    """
    Return the name of the station under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: the name of the station under test
    """
    if not true_context:
        pytest.skip("This needs to be run in a true-context")
    return os.getenv("STATION_LABEL", "real-daq-1")


@pytest.fixture(name="station_devices")
def device_proxies_fixture(station_name: str) -> dict[str, list[tango.DeviceProxy]]:
    """
    Get the dictionary of device proxies.

    The device name is used as a key.

    :param station_name: the station name to use for the test.
    :return: dictionary of device proxies.
    """
    station_proxy = tango.DeviceProxy(get_sps_station_name(station_name))
    tiles_fqdns = list(station_proxy.get_property("TileFQDNs")["TileFQDNs"])
    subracks_fqdns = list(station_proxy.get_property("SubrackFQDNs")["SubrackFQDNs"])
    daqs_fqdns = list(station_proxy.get_property("DaqTRL")["DaqTRL"])
    return {
        "Tiles": [tango.DeviceProxy(tile_fqdn) for tile_fqdn in tiles_fqdns],
        "Subracks": [
            tango.DeviceProxy(subrack_fqdn) for subrack_fqdn in subracks_fqdns
        ],
        "Station": [station_proxy],
        "DAQs": [tango.DeviceProxy(daq_fqdn) for daq_fqdn in daqs_fqdns],
    }


@pytest.fixture(name="get_device_online")
def get_device_online(
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Callable:
    """
    Put a given device online if it isn't already.

    :param change_event_callbacks: a dictionary of callables to be used as
        tango change event callbacks.

    :returns: a callable to call when we want a device ONLINE.
    """

    def _get_device_online(device_proxy: tango.DeviceProxy) -> None:
        """
        Move a device to ONLINE.

        :param device_proxy: the tango DeviceProxy we want
            to bring ONLINE.
        """
        print(f"Turning {device_proxy.dev_name()} online")

        sub_id = device_proxy.subscribe_event(
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
        if "low-mccs/tile/" in device_proxy.dev_name():
            try:
                # Tile may enter a transient FAULT when put ONLINE.
                # The TPM can be polled but the Subrack is not yet
                # reporting the TPM as ON.
                change_event_callbacks.assert_change_event(
                    "device_state",
                    tango.DevState.FAULT,
                    lookahead=2,
                    consume_nonmatches=True,
                )
                change_event_callbacks.assert_change_event("device_state", Anything)
            except AssertionError:
                pass
        device_proxy.unsubscribe_event(sub_id)

    return _get_device_online


@given("the Station is online")
def station_online(
    station_devices: dict[str, list[tango.DeviceProxy]],
    get_device_online: Callable,
    station_name: str,
) -> None:
    """
    Put a station ONLINE.

    :param station_devices: A fixture with the station devices.
    :param get_device_online: a fixture to call to bring a device ONLINE
    :param station_name: the name of the station under test.
    """
    # if station_name == "stfc-ral-software":
    #     pytest.xfail("This test does not work consistently against hardware.")
    for subrack in station_devices["Subracks"]:
        get_device_online(subrack)
    for tile in station_devices["Tiles"]:
        get_device_online(tile)
    for daq in station_devices["DAQs"]:
        get_device_online(daq)
    for station in station_devices["Station"]:
        get_device_online(station)


@given("the Station has been commanded to turn On")
@when("the Station has been commanded to turn On")
def station_on(
    station_devices: dict[str, tango.DeviceProxy], command_info: dict[str, Any]
) -> None:
    """
    Command the station to turn on.

    :param station_devices: dictionary of device proxies.
    :param command_info: dictionary to store command ID.
    """
    _, [command_id] = station_devices["Station"][0].On()
    command_info[station_devices["Station"][0].dev_name() + "On"] = command_id


@when("the Tiles are commanded to turn On")
def tiles_on(
    station_devices: dict[str, tango.DeviceProxy], command_info: dict[str, Any]
) -> None:
    """
    Command the station to turn on.

    :param station_devices: dictionary of device proxies.
    :param command_info: dictionary to store command ID.
    """
    for tile in station_devices["Tiles"]:
        tile.On()


@given("the Station has been commanded to turn to Standby")
def station_standby(station_devices: dict[str, tango.DeviceProxy]) -> None:
    """
    Command the station to turn to standby.

    :param station_devices: dictionary of device proxies.
    """
    station_devices["Station"][0].Standby()


@then(parsers.cfparse("the Station {command} command finishes"))
def device_command_finishes(
    station_devices: dict[str, tango.DeviceProxy],
    command: str,
    command_info: dict[str, Any],
    wait_for_command_completion: Callable,
) -> None:
    """
    Wait for a command to complete.

    :param wait_for_command_completion: a fixture that waits on
        the completion of a command.
    :param station_devices: dictionary of device proxies.
    :param command: command to wait for
    :param command_info: dictionary to store command ID.
    """
    device = "Station"
    station_device = station_devices[device][0]
    wait_for_command_completion(station_device, command, command_info)


@pytest.fixture(name="wait_for_command_completion", scope="module")
def wait_for_command_completion_fixture() -> Callable:
    """
    Wait for the completion of the command.

    :return: a callable to call with device and command.
    """

    def _wait_for_command_completion(
        device: tango.DeviceProxy, command: str, command_info: dict[str, Any]
    ) -> None:
        command_id = command_info[device.dev_name() + command]
        count = 0
        while device.CheckLongRunningCommandStatus(command_id) != "COMPLETED":
            time.sleep(1)
            count += 1
            if count > 40:
                pytest.fail(
                    f"{device.dev_name()}.{command} did not complete: "
                    f"{device.CheckLongRunningCommandStatus(command_id)}"
                )

    return _wait_for_command_completion


@given(parsers.cfparse("the {device_group} reports that its {attribute} is {value}"))
@then(parsers.cfparse("the {device_group} reports that its {attribute} is {value}"))
def device_verify_attribute(
    station_devices: dict[str, tango.DeviceProxy],
    device_group: str,
    station_name: str,
    attribute: str,
    value: str,
) -> None:
    """
    Verify that a device is in the desired state.

    :param station_devices: dictionary of device proxies.
    :param device_group: the device group to test.
    :param station_name: the name of the station under test.
    :param attribute: the attribute to verify the value of.
    :param value: the value to verify.
    """
    device_proxys = station_devices[device_group]
    for device_proxy in device_proxys:
        enum_value = None
        if attribute == "state":
            enum_value = {
                "ON": tango.DevState.ON,
                "OFF": tango.DevState.OFF,
                "STANDBY": tango.DevState.STANDBY,
            }[value.upper()]
        elif attribute == "HealthState":
            enum_value = {
                "OK": HealthState.OK,
                "DEGRADED": HealthState.DEGRADED,
                "FAILED": HealthState.FAILED,
                "UNKNOWN": HealthState.UNKNOWN,
            }[value]
        timeout = 100
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
            try:
                assert device_value == enum_value, (
                    f"Expected health to be {enum_value} but got {device_value}, "
                    f"Reason: {device_proxy.healthReport}"
                )
            except Exception:
                if station_name == "stfc-ral-software":
                    pytest.xfail(
                        "at RAL there is an issue with the TPM current "
                        "meaning the subrack has DEGRADED health and "
                        "therefore station has DEGRADED healthstate."
                    )
                pytest.fail(
                    f"Expected health to be {enum_value} but got {device_value}, "
                    f"Reason: {device_proxy.healthReport}"
                )
        else:
            assert device_value == enum_value


@when("the Tiles board temperature thresholds are adjusted")
def set_tile_health_params(station_devices: dict[str, tango.DeviceProxy]) -> None:
    """
    Set the board temperature thresholds of the Tile.

    :param station_devices: dictionary of device proxies.
    """
    new_board_params = {
        "temperatures": {"board": {"min": 100, "max": 170}},
    }
    tile_devices = station_devices["Tiles"]
    for tile_device in tile_devices:
        tile_device.healthModelParams = json.dumps(new_board_params)


@when("the Subracks board temperature thresholds are adjusted")
def set_subrack_health_params(station_devices: dict[str, tango.DeviceProxy]) -> None:
    """
    Set the board temperature thresholds of the Subrack.

    :param station_devices: dictionary of device proxies.
    """
    new_board_params = {
        "failed_max_board_temp": 170.0,
        "degraded_max_board_temp": 160.0,
        "failed_min_board_temp": 110.0,
        "degraded_min_board_temp": 120.0,
    }
    for subrack in station_devices["Subracks"]:
        subrack.healthModelParams = json.dumps(new_board_params)


@when("all attributes are read on a Tile")
def read_all_tile_attributes(
    station_devices: dict[str, tango.DeviceProxy],
    attribute_read_info: dict[str, Any],
    excluded_tile_attributes: list[str],
) -> None:
    """
    Read all attributes on a Tile, assert we got a value.

    :param station_devices: A fixture containing the
        station devices.
    :param attribute_read_info: A dict of values returned by an attribute read.
    :param excluded_tile_attributes: A list of attributes to not check.
    """
    tiles = station_devices["Tiles"]
    for tile in tiles:
        for attr in tile.get_attribute_list():
            if attr in excluded_tile_attributes:
                continue
            try:
                attribute_read_info[attr] = getattr(tile, attr, None)
            except tango.DevFailed:
                attribute_read_info[attr] = None


@then("a value is returned for each")
def check_attribute_read_success(attribute_read_info: dict[str, Any]) -> None:
    """
    Assert that all attribute reads were successful.

    :param attribute_read_info: A dcit of values returned by an attribute read.
    """
    # Chose not to do `if any()` so we have the attr name also if there's a failure.
    for attr_name, attr_value in attribute_read_info.items():
        if attr_value is None:
            pytest.fail(f"Error reading attribute: {attr_name}")


@then(parsers.cfparse("the {device_group} reports that it is {programming_state}"))
def check_device_programming_state(
    station_devices: dict[str, tango.DeviceProxy],
    device_group: str,
    programming_state: str,
) -> None:
    """
    Check the tileProgrammingState of a device.

    :param station_devices: A fixture containing the
        station devices.
    :param device_group: The device group to check.
        Must be Station or Tile.
    :param programming_state: The programming state to check for.
    """
    for device in station_devices[device_group]:
        # List from Station, str from Tile.
        device_programming_state = device.tileProgrammingState
        if isinstance(device_programming_state, list):
            # Assert all Tiles in the Station are in the specified state.
            assert all(
                tile_programming_state == programming_state
                for tile_programming_state in device_programming_state
            )
        elif isinstance(device_programming_state, str):
            assert device_programming_state == programming_state
