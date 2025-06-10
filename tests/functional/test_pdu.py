# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains a test for the pdu functional tests.

Depending on your exact deployment the individual tests may or may not be run.
This test just checks that anything which can run passes.
"""
from __future__ import annotations

import time
from typing import Any

import pytest
import tango
from pytest_bdd import given, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import OneOf
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import get_pdu_name, get_subrack_name


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    subrack_id: int,
) -> tango.DeviceProxy:
    """
    Return the subrack device under test.

    :param subrack_id: ID of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango.DeviceProxy(get_subrack_name(subrack_id))


@pytest.fixture(name="pdu_device")
def pdu_device_fixture() -> tango.DeviceProxy:
    """
    Return the pdu device under test.

    :return: the pdu Tango device under test.
    """
    return tango.DeviceProxy(get_pdu_name())


@pytest.fixture(name="pdu_port", scope="module")
def pdu_port_fixture() -> int:
    """
    Return the pdu port to be used.

    :return: the pdu port to be used.
    """
    return 1


@pytest.fixture(name="command_info")
def command_info_fixture() -> dict[str, Any]:
    """
    Fixture to store command ID.

    :returns: Empty dictionary.
    """
    return {}


@scenario("features/pdu.feature", "Pdu turns ports ON")
def test_pdu_port_on_test() -> None:
    """Run a test scenario that tests turning on the pdu port."""
    for device in [
        tango.DeviceProxy(trl)
        for trl in tango.Database().get_device_exported("low-mccs/*")
    ]:
        device.adminmode = AdminMode.ONLINE


@scenario("features/pdu.feature", "Pdu turns ports OFF")
def test_pdu_port_off_test() -> None:
    """Run a test scenario that tests turning off the pdu port."""
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


@given("a PDU that is online and ON")
def check_pdu_is_online_and_on(
    pdu_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the pdu is online and on.

    :param pdu_device: the pdu Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    admin_mode = pdu_device.adminMode
    assert admin_mode in [AdminMode.OFFLINE, AdminMode.ONLINE, AdminMode.ENGINEERING]

    pdu_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["pdu_state"],
    )

    # Test can run in ONLINE or ENGINEERING admin mode,
    # so we only need to act if the admin mode is OFFLINE
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event("pdu_state", tango.DevState.DISABLE)
        pdu_device.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event("pdu_state", tango.DevState.UNKNOWN)

    change_event_callbacks.assert_change_event(
        "pdu_state",
        OneOf(tango.DevState.OFF, tango.DevState.ON),
    )
    state = pdu_device.state()

    if state == tango.DevState.OFF:
        pdu_device.On()

        change_event_callbacks.assert_change_event(
            "pdu_state",
            tango.DevState.ON,
        )

    assert pdu_device.state() == tango.DevState.ON


@given("a subrack that is online and ON")
def check_subrack_is_online_and_on(
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Check that the subrack is online and on.

    :param subrack_device: the subrack Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    admin_mode = subrack_device.adminMode
    assert admin_mode in [AdminMode.OFFLINE, AdminMode.ONLINE, AdminMode.ENGINEERING]

    subrack_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_state"],
    )

    # Test can run in ONLINE or ENGINEERING admin mode,
    # so we only need to act if the admin mode is OFFLINE
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event(
            "subrack_state", tango.DevState.DISABLE
        )
        subrack_device.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event(
            "subrack_state", tango.DevState.UNKNOWN
        )

    change_event_callbacks.assert_change_event(
        "subrack_state",
        OneOf(tango.DevState.OFF, tango.DevState.ON),
    )
    state = subrack_device.state()

    if state == tango.DevState.OFF:
        subrack_device.On()

        change_event_callbacks.assert_change_event(
            "subrack_state",
            tango.DevState.ON,
        )

    assert subrack_device.state() == tango.DevState.ON


@given("all the PDU ports are OFF")
def assert_pdu_ports_are_off(
    pdu_device: tango.DeviceProxy,
) -> None:
    """
    Make sure the pdu ports are off.

    :param pdu_device: the pdu Tango device under test.
    """
    port_state = pdu_device.outlet1State
    if port_state == 0:
        return
    pdu_device.outlet1Command(0)
    # pdu_device.outlet1Command = 0
    for i in range(5):
        port_state = pdu_device.outlet1State
        if port_state == 0:
            return
        time.sleep(1)
    assert False, "Pdu port 1 not in correct state"


@given("all the PDU ports are ON")
def assert_pdu_ports_are_on(
    pdu_device: tango.DeviceProxy,
) -> None:
    """
    Make sure the pdu ports are on.

    :param pdu_device: the pdu Tango device under test.
    """
    port_state = pdu_device.outlet1State
    if port_state == 1:
        return
    pdu_device.outlet1Command(1)
    # pdu_device.outlet1Command = 1
    for i in range(5):
        port_state = pdu_device.outlet1State
        if port_state == 1:
            return
        time.sleep(1)
    assert False, "Pdu port 1 not in correct state"


@when("subrack commands pdu turn ON port")
def subrack_commands_pdu_port_on(
    subrack_device: tango.DeviceProxy,
    pdu_port: int,
) -> None:
    """
    Subrack commands the pdu to turn on port.

    :param subrack_device: the subrack Tango device under test.
    :param pdu_port: the pdu port to power on and off
    """
    subrack_device.PowerPduPortOn(pdu_port)


@when("subrack commands pdu turn OFF port")
def subrack_commands_pdu_port_off(
    subrack_device: tango.DeviceProxy,
    pdu_port: int,
) -> None:
    """
    Subrack commands the pdu to turn off port.

    :param subrack_device: the subrack Tango device under test.
    :param pdu_port: the pdu port to power on and off
    """
    subrack_device.PowerPduPortOff(pdu_port)


@then("the PDU port turns ON")
def pdu_port_turns_on(
    pdu_device: tango.DeviceProxy,
) -> None:
    """
    PDU port turns on.

    :param pdu_device: the subrack Tango device under test.
    """
    for i in range(5):
        port_state = pdu_device.outlet1State
        if port_state == 1:
            return
        time.sleep(1)
    assert False, "Pdu port 1 not in correct state"


@then("the PDU port turns OFF")
def pdu_port_turns_off(
    pdu_device: tango.DeviceProxy,
) -> None:
    """
    PDU port turns off.

    :param pdu_device: the subrack Tango device under test.
    """
    for i in range(5):
        port_state = pdu_device.outlet1State
        if port_state == 0:
            return
        time.sleep(1)
    assert False, "Pdu port 1 not in correct state"
