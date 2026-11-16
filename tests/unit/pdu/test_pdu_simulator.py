#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the PDU simulator alone, through a plain SNMP client.

Each test starts its own simulator, so the outlet states it changes do not
reach the next test.
"""
from __future__ import annotations

import asyncio
from typing import Any, Iterator

import pytest
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    set_cmd,
)
from pysnmp.proto.rfc1902 import Integer32

from ska_low_mccs_spshw.pdu.pdu_simulator import (
    PduSimulatorContextManager,
    responder_arguments,
)

# Enlogic objects, by numeric OID, so the test reads the wire as it is.
SYS_DESCR = "1.3.6.1.2.1.1.1.0"
SERIAL_NUMBER = "1.3.6.1.4.1.38446.1.1.2.1.12.1"
NUMBER_OF_PORTS = "1.3.6.1.4.1.38446.1.2.3.1.4.1"
OUTLET_1_CURRENT = "1.3.6.1.4.1.38446.1.5.9.1.5.1.1"
OUTLET_3_STATE = "1.3.6.1.4.1.38446.1.5.4.1.4.1.3"
OUTLET_3_CONTROL = "1.3.6.1.4.1.38446.1.5.5.1.4.1.3"

# Enlogic writes immediateOn(2) and immediateOff(1). The state reads on(1) and
# off(0).
IMMEDIATE_ON = 2
IMMEDIATE_OFF = 1


def _request(
    address: tuple[str, int], command: Any, *objects: ObjectType, community: str
) -> list[tuple[str, str]] | str:
    """
    Send one SNMP request and return what came back.

    :param address: the host and port of the simulator.
    :param command: ``get_cmd`` or ``set_cmd``.
    :param objects: the objects to read or write.
    :param community: the SNMP community to send with.

    :return: each object and its value, or the error the request ended with.
    """

    async def send() -> list[tuple[str, str]] | str:
        engine = SnmpEngine()
        try:
            target = await UdpTransportTarget.create(address, timeout=1, retries=0)
            (error, status, _, binds) = await command(
                engine, CommunityData(community), target, ContextData(), *objects
            )
        finally:
            engine.close_dispatcher()
        if error:
            return str(error)
        if status:
            return status.prettyPrint()
        return [(str(oid), value.prettyPrint()) for oid, value in binds]

    return asyncio.run(send())


def _get(
    address: tuple[str, int], *oids: str, community: str = "private"
) -> list[tuple[str, str]] | str:
    """
    Read objects from the simulator.

    :param address: the host and port of the simulator.
    :param oids: the objects to read.
    :param community: the SNMP community to send with.

    :return: each object and its value, or the error the request ended with.
    """
    objects = [ObjectType(ObjectIdentity(oid)) for oid in oids]
    return _request(address, get_cmd, *objects, community=community)


def _set(address: tuple[str, int], oid: str, value: int) -> list[tuple[str, str]] | str:
    """
    Write one integer object on the simulator.

    :param address: the host and port of the simulator.
    :param oid: the object to write.
    :param value: the value to write.

    :return: the object and its value, or the error the request ended with.
    """
    obj = ObjectType(ObjectIdentity(oid), Integer32(value))
    return _request(address, set_cmd, obj, community="private")


@pytest.fixture(name="simulator")
def simulator_fixture() -> Iterator[PduSimulatorContextManager]:
    """
    Return a running Enlogic simulator.

    :yields: the simulator, which is running.
    """
    simulator = PduSimulatorContextManager("ENLOGIC")
    with simulator:
        yield simulator


@pytest.fixture(name="address")
def address_fixture(simulator: PduSimulatorContextManager) -> tuple[str, int]:
    """
    Return where the simulator listens.

    :param simulator: the running simulator.

    :return: its host and port.
    """
    return simulator.address


def test_serves_the_recorded_values(address: tuple[str, int]) -> None:
    """
    Test that the simulator serves the recorded data, with its site details replaced.

    :param address: the host and port of the simulator.
    """
    assert _get(
        address, SYS_DESCR, SERIAL_NUMBER, NUMBER_OF_PORTS, OUTLET_1_CURRENT
    ) == [
        (SYS_DESCR, "Simulated Enlogic PDU"),
        (SERIAL_NUMBER, "SIM00001"),
        (NUMBER_OF_PORTS, "24"),
        (OUTLET_1_CURRENT, "63"),
    ]


def test_a_control_write_switches_the_outlet(address: tuple[str, int]) -> None:
    """
    Test that a write to an outlet's control object changes its state.

    The control object then reads back as the command that matches the state,
    as on a real Enlogic PDU.

    :param address: the host and port of the simulator.
    """
    assert _get(address, OUTLET_3_STATE, OUTLET_3_CONTROL) == [
        (OUTLET_3_STATE, "0"),
        (OUTLET_3_CONTROL, "1"),
    ]

    assert _set(address, OUTLET_3_CONTROL, IMMEDIATE_ON) == [
        (OUTLET_3_CONTROL, str(IMMEDIATE_ON))
    ]
    assert _get(address, OUTLET_3_STATE, OUTLET_3_CONTROL) == [
        (OUTLET_3_STATE, "1"),
        (OUTLET_3_CONTROL, str(IMMEDIATE_ON)),
    ]

    _set(address, OUTLET_3_CONTROL, IMMEDIATE_OFF)
    assert _get(address, OUTLET_3_STATE) == [(OUTLET_3_STATE, "0")]


def test_a_wrong_community_gets_no_answer(address: tuple[str, int]) -> None:
    """
    Test that the simulator does not answer a community it has no data for.

    :param address: the host and port of the simulator.
    """
    assert "No SNMP response" in _get(address, SYS_DESCR, community="public")


def test_a_stopped_simulator_does_not_answer(
    simulator: PduSimulatorContextManager, address: tuple[str, int]
) -> None:
    """
    Test that stopping the simulator makes the PDU stop answering.

    :param simulator: the running simulator.
    :param address: the host and port of the simulator.
    """
    simulator.stop()

    assert "No SNMP response" in _get(address, SYS_DESCR)


def test_a_model_without_data_is_refused() -> None:
    """Test that the simulator refuses a model it has no recording of."""
    with pytest.raises(ValueError, match="No simulator data for PDU model RARITAN"):
        responder_arguments("RARITAN", "127.0.0.1", 1610, "/tmp")
