# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This file contains a test for the station wren during initialise."""

from __future__ import annotations

from typing import Any, Generator

import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode, HealthState, ResultCode

from tests.test_tools import wait_for_condition, wait_for_lrc_result


@pytest.fixture(name="wren_trl")
def wren_trl_fixture() -> str:
    """
    Return the WREN TRL.

    :returns: The WREN TRL

    """
    return "low-sat/whiterabbitsimulator/ci-1"


@pytest.fixture(name="wren")
def wren_fixture(wren_trl: str) -> tango.DeviceProxy:
    """
    Return the WREN device proxy.

    :param wren_trl: The WREN TRL.

    :returns: The WREN device proxy.

    """
    return tango.DeviceProxy(wren_trl)


@given("an SPS deployment against a real context")
def check_against_real_context(true_context: bool, station_label: str) -> None:
    """
    Skip the test if not in real context.

    :param true_context: whether or not the current context is real.
    :param station_label: Station to test against.
    """
    if not true_context:
        pytest.skip("This test requires real context.")


@given("the SpsStation has a WREN TRL")
def check_sps_station_has_a_wren_trl(
    station: tango.DeviceProxy, wren_trl: str
) -> Generator:
    """
    Check the station has a WREN TRL.

    :param station: a proxy to the station under test.
    :param wren_trl: The WREN TRL.

    :yields: None

    """
    # Get the initial TRL
    initial_wren_trl = station.WrenTRL

    # Set the TRL here
    if initial_wren_trl != wren_trl:
        station.put_property({"WRENTRL": wren_trl})
        station.Init()
        assert station.WrenTRL == wren_trl

    # Yield control
    yield

    # Reset the TRL to the initial value
    if initial_wren_trl != station.WrenTRL:
        station.put_property({"WRENTRL": ""})
        station.Init()
        assert station.WrenTRL == initial_wren_trl


@given(
    parsers.parse("the SpsStation is in AdminMode.ONLINE"),
)
def set_station_admin_mode(station: tango.DeviceProxy) -> None:
    """
    Set the station admin mode.

    :param station: station device under test.

    """
    # Set the admin mode
    station.adminMode = AdminMode.ONLINE

    # Wait to ensure it is in that state
    assert wait_for_condition(lambda: station.adminMode == AdminMode.ONLINE)


@given(
    parsers.parse("the SpsStation WRENHealthCheckFailOnTimeout is {enabled}"),
    converters={"enabled": lambda x: {"true": True, "false": False}[x.lower()]},
)
def set_wren_health_check_fail_on_timeout(
    station: tango.DeviceProxy, enabled: bool
) -> Generator:
    """
    Set the WREN health check enabled flag.

    :param station: a proxy to the station under test.
    :param enabled: is the WRENHealthCheckFailOnTimeout True/False.

    :yields: Gives back control after setting the enabled flag

    """
    # Get the original value of the enabled flag
    initial_enabled = station.WrenHealthCheckFailOnTimeout

    # Then set the new value
    station.WrenHealthCheckFailOnTimeout = enabled

    # Ensure it is set
    wait_for_condition(lambda: station.WrenHealthCheckFailOnTimeout == enabled)

    # Yield the station device
    yield

    # Now reset the flag
    station.WrenHealthCheckFailOnTimeout = initial_enabled


@given(
    parsers.parse("the SpsStation WRENHealthCheckTimeout is set to {timeout} seconds"),
    converters={"timeout": float},
)
def set_wren_health_check_timeout(
    station: tango.DeviceProxy, timeout: float
) -> Generator:
    """
    Set the WREN health check timeout.

    :param station: a proxy to the station under test.
    :param timeout: Timeout value in seconds.

    :yields: Gives back control after setting the timeout

    """
    # Get the original value of the enabled flag
    initial_timeout = station.WrenHealthCheckTimeout

    # Then set the new value
    station.WrenHealthCheckTimeout = timeout

    # Yield the station device
    yield

    # Reset the timeout
    station.WrenHealthCheckTimeout = initial_timeout


@given("the WREN is initially unhealthy")
def set_wren_unhealthy(wren: tango.DeviceProxy) -> None:
    """
    Configure the WREN to report unhealthy status initially.

    :param wren: The WREN device.

    """
    # Set the failed health state
    wren.healthState = HealthState.FAILED

    # Ensure the health state is failed
    assert wait_for_condition(lambda: wren.healthState == HealthState.FAILED)


@when("the WREN becomes healthy")
def set_wren_healthy(wren: tango.DeviceProxy) -> None:
    """
    Configure the WREN to report healthy status.

    :param wren: The WREN device.

    """
    # Set the ok health state
    wren.healthState = HealthState.OK

    # Ensure the health state is failed
    assert wait_for_condition(lambda: wren.healthState == HealthState.OK)


@when("the WREN remains unhealthy")
def check_wren_unhealthy(wren: tango.DeviceProxy) -> None:
    """
    Ensure the WREN continues to report unhealthy status.

    :param wren: The WREN device.

    """
    assert wait_for_condition(lambda: wren.healthState == HealthState.FAILED)


@when("the station is initialised")
def initialise_station(
    station: tango.DeviceProxy, command_info: dict[str, Any]
) -> None:
    """
    Initialise the station.

    :param station: station device under test.
    :param command_info: a dict containing command IDs.

    """
    # Call Initialise
    [result_code], [command_id] = station.Initialise()

    # Ensure the command is queued
    assert result_code == ResultCode.QUEUED

    # Add to the command info dictionary
    command_info["Initialise"] = command_id


@then(
    parsers.parse("the station is in DevState.ON"),
)
def check_station_state(station: tango.DeviceProxy) -> None:
    """
    Verify the station is in the expected state.

    :param station: station device under test.

    """
    assert wait_for_condition(lambda: station.state() == tango.DevState.ON)


@then("the Initialise command completes successfully")
def initialise_command_completed_successfully(
    station: tango.DeviceProxy, command_info: dict[str, Any]
) -> None:
    """
    Check the Initialise command completed with ResultCode.OK.

    :param station: station device under test.
    :param command_info: a dict containing command IDs.

    """
    wait_for_lrc_result(
        device=station,
        uid=command_info["Initialise"],
        expected_result=ResultCode.OK,
        timeout=300,
    )


@then("the Initialise command fails")
def initialise_command_failed(
    station: tango.DeviceProxy, command_info: dict[str, Any]
) -> None:
    """
    Check the Initialise command completed with ResultCode.FAILED.

    :param station: station device under test.
    :param command_info: a dict containing command IDs.

    """
    wait_for_lrc_result(
        device=station,
        uid=command_info["Initialise"],
        expected_result=ResultCode.FAILED,
        timeout=300,
        expected_status="FAILED",
    )


@pytest.mark.skip
@scenario(
    "features/wren_wait.feature",
    "Station waits for WREN during initialisation when enabled",
)
def test_station_waits_for_wren_when_enabled(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests WREN wait functionality when enabled.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.

    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@pytest.mark.skip
@scenario(
    "features/wren_wait.feature", "Station times out waiting for WREN when enabled"
)
def test_station_wren_timeout_when_enabled(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests WREN timeout functionality.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.

    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE


@pytest.mark.skip
@scenario(
    "features/wren_wait.feature",
    "Station ignores WREN timeout during initialisation when disabled",
)
def test_station_skips_wren_when_disabled(
    stations_devices_exported: list[tango.DeviceProxy],
) -> None:
    """
    Run a test scenario that tests WREN wait functionality when disabled.

    :param stations_devices_exported: Fixture containing the ``tango.DeviceProxy``
        for all exported sps devices.

    """
    for device in stations_devices_exported:
        device.adminmode = AdminMode.ONLINE
