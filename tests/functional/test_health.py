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
from typing import Callable

import pytest
import tango
import time
from pytest_bdd import given, parsers, scenarios, then, when
from ska_control_model import AdminMode, HealthState
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.functional.conftest import (
    expect_attribute,
    poll_until_consumers_stopped,
    poll_until_state_change,
)
from tests.harness import get_daq_name, get_subrack_name, get_tile_name, get_calibration_store_name, get_sps_station_name, get_station_calibrator_name, SpsTangoTestHarnessContext

scenarios("./features/health.feature")

@pytest.fixture(name="station_name")
def station_name_fixture(true_context: bool) -> str:
    """
    Return the name of the station under test.

    :param true_context: whether to test against an existing Tango deployment

    :return: the name of the station under test
    """
    if not true_context:
        pytest.skip(
            "This needs to be run in a true-context"
        )
    return "real-daq-1"

@pytest.fixture(name="subrack_id")
def subrack_id_fixture() -> int:
    return 1

@pytest.fixture(name="tile_id")
def tile_id_fixture() -> int:
    return 10


@pytest.fixture(name="device_proxies")
def device_proxies_fixture(subrack_id, tile_id, station_name) -> dict[str, tango.DeviceProxy]:
    return {
        "Tile": tango.DeviceProxy(get_tile_name(tile_id, station_name)),
        "Subrack": tango.DeviceProxy(get_subrack_name(subrack_id, station_name)),
        "Station": tango.DeviceProxy(get_sps_station_name(station_name)),
        "DAQ": tango.DeviceProxy(get_daq_name(station_name)),
        "Calibration Store": tango.DeviceProxy(get_calibration_store_name(station_name)),
        "Station Calibrator": tango.DeviceProxy(get_station_calibrator_name(station_name)),
    }

@given(parsers.cfparse("a {device} that is online"))
def device_online(
    device: str, 
    device_proxies: dict[str, tango.DeviceProxy],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
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
    change_event_callbacks.assert_change_event(
        "device_state", 
        Anything
    )

@when("the Station has been commanded to turn on")
def station_on(device_proxies: dict[str, tango.DeviceProxy]) -> None:
    device_proxies["Station"].On()

@then(parsers.cfparse("the {device} reports that its {attribute} is {value}"))
def device_verify_attribute(device_proxies: dict[str, tango.DeviceProxy], device: str, attribute: str, value: str) -> None:
    device_proxy = device_proxies[device]
    enum_value = None
    if attribute == "state":
        enum_value = {"ON": tango.DevState.ON, "OFF": tango.DevState.OFF}[value.upper()]
    elif attribute == "HealthState":
        enum_value = {"OK": HealthState.OK, "DEGRADED": HealthState.DEGRADED, "FAILED": HealthState.FAILED, "UNKNOWN": HealthState.UNKNOWN}[value]
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
    try:
        assert device_value == enum_value
    except:
        print(f"{device_proxy.adminMode} {device_proxy.state()} {device_proxy.healthState}")
        assert device_value == enum_value