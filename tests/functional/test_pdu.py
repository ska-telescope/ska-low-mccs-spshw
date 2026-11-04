# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This file contains the functional tests of the PDU device.

With ``--true-context`` the tests use the PDU device the deployment exports.
Without it they start a PDU simulator and a PDU device to talk to it.

A scenario that switches a port runs only against a simulated PDU. It skips
against a real one, because a real PDU powers real equipment.
"""
from __future__ import annotations

from typing import Iterator

import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import OneOf
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import SpsTangoTestHarness

# What the simulated PDU reports as its system description.
SIMULATED_DESCRIPTION = "Simulated Enlogic PDU"

# Long enough for the PDU device to queue a write, send it at its next poll,
# and read the port state back.
EVENT_TIMEOUT = 30.0


@pytest.fixture(name="pdu_device")
def pdu_device_fixture(
    true_context: bool, exported_pdus: list[tango.DeviceProxy]
) -> Iterator[tango.DeviceProxy]:
    """
    Return the PDU device under test.

    In a true context this is a PDU device the deployment exports. Otherwise
    it is a PDU device in a test harness, talking to a PDU simulator.

    :param true_context: whether to test against an existing Tango
        deployment.
    :param exported_pdus: the PDU devices the deployment exports, if any.

    :yields: the PDU device under test.
    """
    if true_context:
        if not exported_pdus:
            pytest.skip("The deployment exports no PDU device.")
        yield exported_pdus[0]
        return

    # Deferred, as in the harness, because a true context runs these tests from
    # a pod that does not have ska_low_mccs_spshw installed.
    # pylint: disable-next=import-outside-toplevel
    from ska_low_mccs_spshw.pdu.pdu_simulator import PduSimulatorContextManager

    with PduSimulatorContextManager("ENLOGIC") as (host, port):
        harness = SpsTangoTestHarness()
        harness.add_pdu_device("ENLOGIC", host, "private", port=port)
        with harness as context:
            yield context.get_pdu_device()


@pytest.fixture(name="pdu_callbacks")
def pdu_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return the change event callbacks the PDU steps subscribe with.

    :return: a group of change event callbacks.
    """
    return MockTangoEventCallbackGroup(
        "state", "port_state", timeout=EVENT_TIMEOUT, assert_no_error=False
    )


@scenario("features/pdu.feature", "Monitor the PDU")
def test_monitor_the_pdu() -> None:
    """Run a test scenario that reads what the PDU reports."""


@scenario("features/pdu.feature", "Switch a PDU port on")
def test_switch_a_pdu_port_on() -> None:
    """Run a test scenario that switches a PDU port on."""


@scenario("features/pdu.feature", "Switch a PDU port off")
def test_switch_a_pdu_port_off() -> None:
    """Run a test scenario that switches a PDU port off."""


@given("a PDU that is online and on")
def pdu_online_and_on(
    pdu_device: tango.DeviceProxy,
    pdu_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Put the PDU device online, and wait until it communicates with its PDU.

    The device is ``ON`` while it communicates with its PDU.

    :param pdu_device: the PDU device under test.
    :param pdu_callbacks: the change event callbacks to subscribe with.
    """
    pdu_device.subscribe_event(
        "state", tango.EventType.CHANGE_EVENT, pdu_callbacks["state"]
    )
    if pdu_device.adminMode == AdminMode.OFFLINE:
        pdu_device.adminMode = AdminMode.ONLINE
    pdu_callbacks["state"].assert_change_event(
        tango.DevState.ON, lookahead=4, consume_nonmatches=True
    )


@given("the PDU is simulated")
def pdu_is_simulated(pdu_device: tango.DeviceProxy) -> None:
    """
    Skip the scenario unless the PDU is a simulator.

    :param pdu_device: the PDU device under test.
    """
    description = pdu_device.systemDescription
    if description != SIMULATED_DESCRIPTION:
        pytest.skip(
            "Switching ports needs a simulated PDU, and this PDU reports "
            f"'{description}'."
        )


@given(parsers.parse("PDU port {port:d} is {power}"))
def pdu_port_is(
    pdu_device: tango.DeviceProxy,
    pdu_callbacks: MockTangoEventCallbackGroup,
    port: int,
    power: str,
) -> None:
    """
    Switch the port, if it is not already in the given state.

    :param pdu_device: the PDU device under test.
    :param pdu_callbacks: the change event callbacks to subscribe with.
    :param port: the port to set up.
    :param power: ``on`` or ``off``.
    """
    on = power == "on"
    pdu_device.subscribe_event(
        f"pduPort{port}State",
        tango.EventType.CHANGE_EVENT,
        pdu_callbacks["port_state"],
    )
    # The subscription reads the current state.
    pdu_callbacks["port_state"].assert_change_event(OneOf(True, False))
    if pdu_device.read_attribute(f"pduPort{port}State").value != on:
        pdu_device.command_inout("pduPortOn" if on else "pduPortOff", port)
        pdu_callbacks["port_state"].assert_change_event(on)


@when(parsers.parse("I switch PDU port {port:d} {power}"))
def switch_pdu_port(pdu_device: tango.DeviceProxy, port: int, power: str) -> None:
    """
    Switch a PDU port on or off.

    :param pdu_device: the PDU device under test.
    :param port: the port to switch.
    :param power: ``on`` or ``off``.
    """
    pdu_device.command_inout("pduPortOn" if power == "on" else "pduPortOff", port)


@then("the PDU reports its model and its number of ports")
def pdu_reports_its_model(pdu_device: tango.DeviceProxy) -> None:
    """
    Check that the PDU reports a model and a number of ports.

    :param pdu_device: the PDU device under test.
    """
    assert pdu_device.pduModel
    assert pdu_device.pduNumberOfPorts > 0


@then("the PDU reports the state of each port")
def pdu_reports_each_port_state(pdu_device: tango.DeviceProxy) -> None:
    """
    Check that every port the PDU device has reads a state.

    :param pdu_device: the PDU device under test.
    """
    names = [
        name
        for name in pdu_device.get_attribute_list()
        if name.startswith("pduPort") and name.endswith("State")
    ]
    assert names, "The PDU device has no port state attributes."
    unread = [name for name in names if pdu_device.read_attribute(name).value is None]
    assert not unread, f"These ports report no state: {unread}"


@then(parsers.parse("PDU port {port:d} reports that it is {power}"))
def pdu_port_reports(
    pdu_callbacks: MockTangoEventCallbackGroup, port: int, power: str
) -> None:
    """
    Check that the port reports the state it was switched to.

    :param pdu_callbacks: the change event callbacks subscribed to the port.
    :param port: the port that was switched.
    :param power: ``on`` or ``off``.
    """
    pdu_callbacks["port_state"].assert_change_event(power == "on")
