#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the PDU link, against a mocked callback scheduler and command proxies.

No Tango device runs. A test calls the event callbacks that the link
registered with the scheduler, in the way the scheduler thread would, and
asserts what the link makes of them.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Iterator
from unittest import mock

import numpy
import pytest
import tango
from ska_control_model import PowerState, ResultCode

from ska_low_mccs_spshw.prototype_subrack import CommandOutcome
from ska_low_mccs_spshw.prototype_subrack.pdu_link import (
    PduLink,
    combined_power_state,
    port_power_state,
)

PDU_TRL = "low-mccs/pdu/a-fake-pdu"
# Two ports, as each deployed subrack has. Not adjacent, so a port number used
# as an index into the list fails.
PORTS = [3, 8]

# How long a test waits for a thread that should already be finishing.
JOIN_TIMEOUT = 5.0


def _event(value: Any) -> mock.Mock:
    """
    Return a change event that carries one value.

    :param value: the attribute value the event carries.

    :return: the event.
    """
    return mock.Mock(err=False, attr_value=mock.Mock(value=value))


def _error_event() -> mock.Mock:
    """
    Return a change event that reports an error.

    :return: the event.
    """
    return mock.Mock(err=True, attr_value=None)


@pytest.fixture(name="scheduler")
def scheduler_fixture() -> mock.Mock:
    """
    Return the callback scheduler that the device would give the link.

    :return: the mock scheduler.
    """
    return mock.Mock(name="callback_scheduler")


@pytest.fixture(name="commands")
def commands_fixture() -> Iterator[dict[str, mock.Mock]]:
    """
    Replace the command proxies that the link switches the ports through.

    The link builds a command proxy each time it switches the ports. Each
    build of a command gives the same mock, so a test can set what it answers
    before the call. Each one accepts every port, unless a test says otherwise.

    :yields: the mock command proxy for each ``MccsPdu`` command, by name.
    """
    commands = {
        name: mock.Mock(name=name, return_value=(ResultCode.OK, "Queued."))
        for name in ("pduPortOn", "pduPortOff")
    }

    def build(trl: str, command_name: str, _logger: logging.Logger) -> mock.Mock:
        assert trl == PDU_TRL
        return commands[command_name]

    with mock.patch(
        "ska_low_mccs_spshw.prototype_subrack.pdu_link.MccsCommandProxy",
        side_effect=build,
    ):
        yield commands


@pytest.fixture(name="link")
def link_fixture(
    scheduler: mock.Mock,
    commands: dict[str, mock.Mock],
) -> PduLink:
    """
    Return a PDU link, which subscribes as it is built.

    :param scheduler: the mock scheduler the link registers with.
    :param commands: the mock command proxies the link builds.

    :return: the link under test.
    """
    return PduLink(PDU_TRL, PORTS, scheduler, logging.getLogger(__name__))


def _callback(scheduler: mock.Mock, attribute_name: str) -> Callable[[Any], None]:
    """
    Return the most recent callback the link registered for one attribute.

    :param scheduler: the mock scheduler the link registered with.
    :param attribute_name: the attribute the callback is for.

    :raises AssertionError: if the link subscribed to nothing by that name.

    :return: the callback.
    """
    for call in reversed(scheduler.register_event_callback.call_args_list):
        (trl, name, event_type, callback) = call.args
        if name == attribute_name:
            assert trl == PDU_TRL
            assert event_type == tango.EventType.CHANGE_EVENT
            return callback
    raise AssertionError(f"Nothing subscribed to {attribute_name}.")


def _switch_on(scheduler: mock.Mock) -> None:
    """
    Deliver an event for each port that says it is on.

    :param scheduler: the mock scheduler the link registered with.
    """
    for port in PORTS:
        _callback(scheduler, f"pduPort{port}State")(_event(True))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(True, PowerState.ON, id="enlogic-on"),
        pytest.param(False, PowerState.OFF, id="enlogic-off"),
        pytest.param(numpy.bool_(True), PowerState.ON, id="enlogic-numpy-on"),
        pytest.param(numpy.bool_(False), PowerState.OFF, id="enlogic-numpy-off"),
        pytest.param(7, PowerState.ON, id="raritan-on"),
        pytest.param(8, PowerState.OFF, id="raritan-off"),
        # An int that is not a bool is a Raritan sensor state, and 0 and 1 are
        # open and closed rather than off and on.
        pytest.param(1, PowerState.UNKNOWN, id="raritan-closed"),
        pytest.param(0, PowerState.UNKNOWN, id="raritan-open"),
        pytest.param(4, PowerState.UNKNOWN, id="raritan-normal"),
        pytest.param(None, PowerState.UNKNOWN, id="none"),
    ],
)
def test_port_power_state(value: Any, expected: PowerState) -> None:
    """
    Test that each PDU model's port value gives the right power state.

    :param value: the ``pduPort{N}State`` value.
    :param expected: the power state it should give.
    """
    assert port_power_state(value) == expected


@pytest.mark.parametrize(
    ("port_states", "expected"),
    [
        ([PowerState.ON, PowerState.ON], PowerState.ON),
        ([PowerState.ON, PowerState.OFF], PowerState.ON),
        ([PowerState.OFF, PowerState.ON], PowerState.ON),
        ([PowerState.ON, PowerState.UNKNOWN], PowerState.ON),
        ([PowerState.OFF, PowerState.OFF], PowerState.OFF),
        ([PowerState.OFF, PowerState.UNKNOWN], PowerState.UNKNOWN),
        ([PowerState.UNKNOWN, PowerState.UNKNOWN], PowerState.UNKNOWN),
        ([], PowerState.UNKNOWN),
    ],
    ids=lambda value: "-".join(state.name for state in value)
    if isinstance(value, list)
    else value.name,
)
def test_combined_power_state(
    port_states: list[PowerState], expected: PowerState
) -> None:
    """
    Test that one port on powers the subrack, and only every port off is off.

    :param port_states: the state of each port.
    :param expected: the power state of the subrack.
    """
    assert combined_power_state(port_states) == expected


def test_subscribes_to_each_port(link: PduLink, scheduler: mock.Mock) -> None:
    """
    Test that the link subscribes once to each port, and to nothing else.

    :param link: the link under test.
    :param scheduler: the mock scheduler the link registered with.
    """
    subscribed = [
        call.args[1] for call in scheduler.register_event_callback.call_args_list
    ]
    assert subscribed == ["pduPort3State", "pduPort8State"]
    assert link.port_states == [PowerState.UNKNOWN, PowerState.UNKNOWN]


def test_a_port_event_changes_only_its_port(
    link: PduLink, scheduler: mock.Mock
) -> None:
    """
    Test that a port event changes its own port and leaves the other alone.

    :param link: the link under test.
    :param scheduler: the mock scheduler the link registered with.
    """
    _switch_on(scheduler)

    _callback(scheduler, "pduPort8State")(_event(False))

    assert link.port_states == [PowerState.ON, PowerState.OFF]
    assert link.power_state == PowerState.ON


@pytest.mark.parametrize(
    "event",
    [
        # MccsPdu pushes an invalid value for each port when it loses contact
        # with its PDU, and an invalid value reads as None.
        pytest.param(_event(None), id="invalid"),
        # The scheduler gives an error event while the PDU device is down.
        pytest.param(_error_event(), id="error"),
    ],
)
def test_no_value_makes_its_port_unknown(
    link: PduLink, scheduler: mock.Mock, event: mock.Mock
) -> None:
    """
    Test that an event with no value for a port makes that port unknown.

    :param link: the link under test.
    :param scheduler: the mock scheduler the link registered with.
    :param event: the event with no value.
    """
    _switch_on(scheduler)

    _callback(scheduler, "pduPort3State")(event)

    assert link.port_states == [PowerState.UNKNOWN, PowerState.ON]


@pytest.mark.parametrize(
    ("on", "command"), [(True, "pduPortOn"), (False, "pduPortOff")], ids=["on", "off"]
)
def test_set_ports_switches_every_port(
    link: PduLink, commands: dict[str, mock.Mock], on: bool, command: str
) -> None:
    """
    Test that switching sends one command for each port, with its number.

    :param link: the link under test.
    :param commands: the mock command proxies the link built.
    :param on: whether to switch the ports on.
    :param command: the ``MccsPdu`` command that should be sent.
    """
    (result_code, _) = link.set_ports(on)

    assert result_code == ResultCode.OK
    assert commands[command].call_args_list == [
        mock.call(3, is_lrc=False),
        mock.call(8, is_lrc=False),
    ]


def test_set_ports_stops_at_the_first_refusal(
    link: PduLink, commands: dict[str, mock.Mock]
) -> None:
    """
    Test that a port the PDU refuses ends the call, and its result is returned.

    :param link: the link under test.
    :param commands: the mock command proxies the link built.
    """
    commands["pduPortOn"].return_value = (ResultCode.FAILED, "The PDU refused.")

    assert link.set_ports(True) == (ResultCode.FAILED, "The PDU refused.")
    commands["pduPortOn"].assert_called_once_with(3, is_lrc=False)


def test_wait_for_ends_when_every_port_reaches_the_target(
    link: PduLink, scheduler: mock.Mock
) -> None:
    """
    Test that a wait ends on the event that brings the last port to the target.

    The first port reaching the target is not enough, so the wait is still
    running after it.

    :param link: the link under test.
    :param scheduler: the mock scheduler the link registered with.
    """
    _switch_on(scheduler)
    outcomes: list[tuple[CommandOutcome, str]] = []
    waiter = threading.Thread(
        target=lambda: outcomes.append(
            link.wait_for(PowerState.OFF, JOIN_TIMEOUT, threading.Event())
        )
    )
    waiter.start()

    _callback(scheduler, "pduPort3State")(_event(False))
    assert waiter.is_alive()
    _callback(scheduler, "pduPort8State")(_event(False))

    waiter.join(JOIN_TIMEOUT)
    assert outcomes == [(CommandOutcome.COMPLETED, "The PDU ports are OFF.")]


def test_wait_for_aborts(link: PduLink) -> None:
    """
    Test that a wait ends as aborted when the abort event is set.

    :param link: the link under test.
    """
    abort_event = threading.Event()
    outcomes: list[tuple[CommandOutcome, str]] = []
    waiter = threading.Thread(
        target=lambda: outcomes.append(
            link.wait_for(PowerState.ON, JOIN_TIMEOUT, abort_event)
        )
    )
    waiter.start()

    abort_event.set()

    waiter.join(JOIN_TIMEOUT)
    assert outcomes == [
        (CommandOutcome.ABORTED, "Aborted while the PDU ports switched ON.")
    ]


def test_wait_for_times_out(link: PduLink) -> None:
    """
    Test that a wait fails when the ports never reach the target in time.

    :param link: the link under test.
    """
    assert link.wait_for(PowerState.ON, 0.0, threading.Event()) == (
        CommandOutcome.FAILED,
        "The PDU ports did not all switch ON within 0.0s.",
    )
