#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the PDU device against the PDU simulator.

The device talks real SNMP to a simulator that serves data recorded from a real
PDU. So these tests also check the device definition. An attribute whose OID
the real PDU does not serve reads ``None``.
"""
from __future__ import annotations

import gc
import importlib.resources
from typing import Iterator

import pytest
import tango
from ska_control_model import AdminMode
from ska_snmp_device.definitions import load_device_definition, parse_device_definition
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.pdu.pdu_simulator import PduSimulatorContextManager
from tests.harness import SpsTangoTestHarness

# TODO: gc.disable() works around a hang during garbage collection.
gc.disable()

# Fast, so that each test waits a short time for the next poll.
UPDATE_RATE = 0.5
# Long enough for the SNMP client to give up on a PDU that stopped answering.
EVENT_TIMEOUT = 30.0
# Recorded as off, so switching it on is a change.
PORT = 3


def _definition_attributes(model_file: str) -> list[str]:
    """
    Return the name of every attribute a device definition gives.

    :param model_file: the definition file of the PDU model.

    :return: the attribute names.
    """
    definition = importlib.resources.files(
        "ska_low_mccs_spshw.pdu.device_definitions"
    ).joinpath(model_file)
    return [
        attribute.attr_args["name"]
        for attribute in parse_device_definition(
            load_device_definition(str(definition))
        )
    ]


@pytest.fixture(name="simulator")
def simulator_fixture() -> Iterator[PduSimulatorContextManager]:
    """
    Return a running Enlogic simulator.

    :yields: the simulator, which is running.
    """
    simulator = PduSimulatorContextManager("ENLOGIC")
    with simulator:
        yield simulator


@pytest.fixture(name="pdu_device")
def pdu_device_fixture(
    simulator: PduSimulatorContextManager,
) -> Iterator[tango.DeviceProxy]:
    """
    Run a PDU device against the simulator.

    :param simulator: the running simulator.

    :yields: a proxy to the PDU device.
    """
    (host, port) = simulator.address
    harness = SpsTangoTestHarness()
    harness.add_pdu_device(
        "ENLOGIC", host, "private", port=port, update_rate=UPDATE_RATE
    )
    with harness as context:
        yield context.get_pdu_device()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return the change event callbacks the tests subscribe with.

    :return: a group of change event callbacks.
    """
    return MockTangoEventCallbackGroup(
        "state",
        f"pduPort{PORT}State",
        timeout=EVENT_TIMEOUT,
        assert_no_error=False,
    )


@pytest.fixture(name="online_device")
def online_device_fixture(
    pdu_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> tango.DeviceProxy:
    """
    Return the PDU device, online and communicating with the simulator.

    :param pdu_device: the PDU device under test.
    :param change_event_callbacks: the callbacks to subscribe with.

    :return: the PDU device under test.
    """
    for name in ("state", f"pduPort{PORT}State"):
        pdu_device.subscribe_event(
            name, tango.EventType.CHANGE_EVENT, change_event_callbacks[name]
        )
    pdu_device.adminMode = AdminMode.ONLINE
    # The events before these, such as the failed reads while offline, are
    # consumed, so each test starts from the device being ON.
    change_event_callbacks["state"].assert_change_event(
        tango.DevState.ON, lookahead=4, consume_nonmatches=True
    )
    change_event_callbacks[f"pduPort{PORT}State"].assert_change_event(
        False, lookahead=3, consume_nonmatches=True
    )
    return pdu_device


def test_every_attribute_reads(online_device: tango.DeviceProxy) -> None:
    """
    Test that every attribute in the Enlogic definition reads a value.

    An attribute whose OID the real PDU does not serve would read ``None``, so
    this catches a definition that names the wrong OID.

    :param online_device: the PDU device, online.
    """
    unread = [
        name
        for name in _definition_attributes("enlogic.yaml")
        if online_device.read_attribute(name).value is None
    ]
    assert not unread, f"These attributes read no value: {unread}"


@pytest.mark.parametrize(
    ("command", "state"), [("pduPortOn", True), ("pduPortOff", False)]
)
def test_a_port_command_switches_the_port(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    command: str,
    state: bool,
) -> None:
    """
    Test that a port command switches the port, through a real SNMP write.

    The port starts off, so switching it off first switches it on.

    :param online_device: the PDU device, online.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param command: the command to run.
    :param state: the state the port should then report.
    """
    if not state:
        online_device.pduPortOn(PORT)
        change_event_callbacks[f"pduPort{PORT}State"].assert_change_event(True)

    online_device.command_inout(command, PORT)

    change_event_callbacks[f"pduPort{PORT}State"].assert_change_event(state)


def test_the_device_follows_a_lost_pdu_and_its_return(
    online_device: tango.DeviceProxy,
    simulator: PduSimulatorContextManager,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test that the device leaves ON when the PDU stops answering, and comes back.

    The PDU answers again before the test ends. A poll against a PDU that does
    not answer blocks for several SNMP timeouts, and that would hold up the
    device server's shutdown beyond what the test context allows.

    :param online_device: the PDU device, online.
    :param simulator: the running simulator.
    :param change_event_callbacks: the callbacks subscribed to the device.
    """
    simulator.stop()
    change_event_callbacks["state"].assert_change_event(tango.DevState.UNKNOWN)

    simulator.restart()
    change_event_callbacks["state"].assert_change_event(
        tango.DevState.ON, lookahead=2, consume_nonmatches=True
    )
