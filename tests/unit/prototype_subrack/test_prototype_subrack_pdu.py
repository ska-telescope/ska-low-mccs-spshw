#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of how the prototype subrack device uses the PDU that feeds it.

The subrack, the poller, the health recorder and the PDU link are injected
through the device module's :py:func:`subrack_factory`, and all four are
mocks. A test sets what the mocked link reports, supplies the device with a
poll, and asserts what the device does with the two together. ``On`` and
``Off`` run against the same mocked link.

Each test gets a fresh context with two devices. One has a PDU, and the other
has neither ``PduTrl`` nor ``PduPorts``.
"""

from __future__ import annotations

import gc
import threading
from typing import Callable, Iterator
from unittest import mock

import pytest
import tango
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_base.callback_scheduler import CallbackScheduler
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DevState

from ska_low_mccs_spshw.prototype_subrack import CommandOutcome, HttpError, RequestError
from ska_low_mccs_spshw.prototype_subrack.constants import PDU_COMMAND_TIMEOUT
from ska_low_mccs_spshw.prototype_subrack.prototype_subrack_device import (
    subrack_factory as device_class_factory,
)
from ska_low_mccs_spshw.prototype_subrack.subrack_client import SubrackPollResponse
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext
from tests.test_tools import LRCManager

COMMANDS_MODULE = "ska_low_mccs_spshw.prototype_subrack.prototype_subrack_commands"

# TODO: gc.disable() works around a hang during garbage collection.
gc.disable()

SUBRACK_ID = 1
# A second device in the same context, which has no PDU.
NO_PDU_SUBRACK_ID = 2
BOARD_HOST = "a-fake-board"
BOARD_PORT = 8081
PDU_TRL = "low-mccs/pdu/a-fake-pdu"
PDU_PORTS = [3, 8]
TIMESTAMP = 1700000000.0

# How long to wait for a change event. Everything below the device is mocked,
# so this only covers the task executor handing a task to a thread.
EVENT_TIMEOUT = 5.0

# The TPM on off flags a poll reports, and the power state each bay gives.
TPM_ON_OFF = [True, False, True, False, False, False, False, False]
TPM_POWER_STATES = [PowerState.ON if is_on else PowerState.OFF for is_on in TPM_ON_OFF]


@pytest.fixture(name="subrack_factory")
def subrack_factory_fixture() -> mock.Mock:
    """
    Return the subrack factory, which carries the device's poll callbacks.

    :return: the factory.
    """
    return mock.Mock(name="subrack_factory")


@pytest.fixture(name="board", autouse=True)
def board_fixture(subrack_factory: mock.Mock) -> Iterator[mock.Mock]:
    """
    Return the subrack client the device holds, set up to accept a shutdown.

    The shutdown wait is patched to nothing, so ``Off`` does not wait for an
    SMM that does not exist.

    :param subrack_factory: the injected subrack factory.

    :yields: the mocked subrack client.
    """
    board = subrack_factory.return_value
    board.run_board_command.return_value = (
        CommandOutcome.COMPLETED,
        "The command completed.",
        None,
    )
    with mock.patch(f"{COMMANDS_MODULE}.SMM_SHUTDOWN_TIME", 0.0):
        yield board


@pytest.fixture(name="poller_factory")
def poller_factory_fixture() -> mock.Mock:
    """
    Return the poller factory. Its return value is the poller the device holds.

    :return: the factory.
    """
    return mock.Mock(name="poller_factory")


@pytest.fixture(name="pdu_link")
def pdu_link_fixture() -> mock.Mock:
    """
    Return the PDU link the device holds.

    It starts with both ports unknown, as a real link does.

    :return: a mock of the PDU link.
    """
    link = mock.Mock(name="pdu_link")
    link.port_states = [PowerState.UNKNOWN, PowerState.UNKNOWN]
    link.power_state = PowerState.UNKNOWN
    link.set_ports.return_value = (ResultCode.OK, "The PDU accepted every port.")
    link.wait_for.return_value = (CommandOutcome.COMPLETED, "What the PDU did.")
    return link


@pytest.fixture(name="pdu_link_factory")
def pdu_link_factory_fixture(pdu_link: mock.Mock) -> mock.Mock:
    """
    Return the PDU link factory of the device with a PDU.

    :param pdu_link: the PDU link it should return.

    :return: the factory.
    """
    return mock.Mock(name="pdu_link_factory", return_value=pdu_link)


@pytest.fixture(name="no_pdu_link_factory")
def no_pdu_link_factory_fixture() -> mock.Mock:
    """
    Return the PDU link factory of the device that has no PDU.

    :return: the factory, which a correct device never calls.
    """
    return mock.Mock(name="no_pdu_link_factory")


@pytest.fixture(name="device_context")
def device_context_fixture(
    subrack_factory: mock.Mock,
    poller_factory: mock.Mock,
    pdu_link_factory: mock.Mock,
    no_pdu_link_factory: mock.Mock,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Run a device with a PDU and a device without one.

    :param subrack_factory: builds the subrack client of the device with a PDU.
    :param poller_factory: builds the poller of the device with a PDU.
    :param pdu_link_factory: builds the PDU link of the device with a PDU.
    :param no_pdu_link_factory: the PDU link factory of the device without one.

    :yields: the running test harness context.
    """
    harness = SpsTangoTestHarness()
    harness.add_prototype_subrack_device(
        SUBRACK_ID,
        address=(BOARD_HOST, BOARD_PORT),
        device_class=device_class_factory(
            subrack=subrack_factory,
            subrack_poller=poller_factory,
            health_recorder=mock.Mock(name="health_recorder_factory"),
            pdu_link=pdu_link_factory,
        ),
        pdu_trl=PDU_TRL,
        pdu_ports=PDU_PORTS,
    )
    harness.add_prototype_subrack_device(
        NO_PDU_SUBRACK_ID,
        address=(BOARD_HOST, BOARD_PORT),
        # A distinct Tango class name, because one context cannot hold two
        # entries pointing at the same class.
        device_class=type(
            "MccsNoPduPrototypeSubrack",
            (
                device_class_factory(
                    subrack=mock.Mock(name="no_pdu_subrack_factory"),
                    subrack_poller=mock.Mock(name="no_pdu_poller_factory"),
                    health_recorder=mock.Mock(name="no_pdu_health_recorder"),
                    pdu_link=no_pdu_link_factory,
                ),
            ),
            {},
        ),
    )
    with harness as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    device_context: SpsTangoTestHarnessContext,
) -> tango.DeviceProxy:
    """
    Return the device that has a PDU.

    :param device_context: the running test harness context.

    :return: a proxy to the device under test.
    """
    return device_context.get_prototype_subrack_device(SUBRACK_ID)


@pytest.fixture(name="no_pdu_device")
def no_pdu_device_fixture(
    device_context: SpsTangoTestHarnessContext,
) -> tango.DeviceProxy:
    """
    Return the device that has no PDU, online.

    :param device_context: the running test harness context.

    :return: a proxy to the device without a PDU.
    """
    device = device_context.get_prototype_subrack_device(NO_PDU_SUBRACK_ID)
    device.adminMode = AdminMode.ONLINE
    return device


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return the change event callbacks the tests subscribe with.

    :return: a group of change event callbacks.
    """
    return MockTangoEventCallbackGroup(
        "state",
        "lrc_queue",
        "lrc_executing",
        "lrc_finished",
        timeout=EVENT_TIMEOUT,
        assert_no_error=False,
    )


@pytest.fixture(name="online_device")
def online_device_fixture(
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> tango.DeviceProxy:
    """
    Return the device with a PDU, subscribed to and online, with nothing polled.

    :param subrack_device: the device under test.
    :param change_event_callbacks: the callbacks to subscribe with.

    :return: the device under test.
    """
    subrack_device.subscribe_event(
        "state", tango.EventType.CHANGE_EVENT, change_event_callbacks["state"]
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    subrack_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    return subrack_device


@pytest.fixture(name="lrc")
def lrc_fixture(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> LRCManager:
    """
    Return a long running command manager for the device under test, online.

    :param online_device: the device under test, online.
    :param change_event_callbacks: the callbacks to subscribe with.

    :return: the long running command manager.
    """
    return LRCManager(online_device, change_event_callbacks)


@pytest.fixture(name="poll_succeeded")
def poll_succeeded_fixture(subrack_factory: mock.Mock) -> Callable[[], None]:
    """
    Return a callable that supplies the device with one successful poll.

    The poll reports only the TPM on off flags, so every other attribute keeps
    its value.

    :param subrack_factory: the injected subrack factory, which carries the
        device's data callback.

    :return: a callable taking no arguments.
    """

    def report() -> None:
        response = SubrackPollResponse(
            values={"tpm_on_off": TPM_ON_OFF}, timestamp=TIMESTAMP
        )
        with tango.EnsureOmniThread():
            subrack_factory.call_args.kwargs["data_callback"](response)

    return report


@pytest.fixture(name="poll_failed")
def poll_failed_fixture(subrack_factory: mock.Mock) -> Callable[[Exception], None]:
    """
    Return a callable that supplies the device with one failed poll.

    :param subrack_factory: the injected subrack factory, which carries the
        device's error callback.

    :return: a callable taking the exception to report.
    """

    def report(exception: Exception) -> None:
        with tango.EnsureOmniThread():
            subrack_factory.call_args.kwargs["error_callback"](exception)

    return report


@pytest.fixture(name="polling_stopped")
def polling_stopped_fixture(subrack_factory: mock.Mock) -> Callable[[], None]:
    """
    Return a callable that tells the device that polling has stopped.

    :param subrack_factory: the injected subrack factory, which carries the
        device's stopped callback.

    :return: a callable taking no arguments.
    """

    def report() -> None:
        with tango.EnsureOmniThread():
            subrack_factory.call_args.kwargs["stopped_callback"]()

    return report


def _set_pdu(pdu_link: mock.Mock, *port_states: PowerState) -> None:
    """
    Make the mocked link report these port states, and their combined state.

    :param pdu_link: the mocked PDU link.
    :param port_states: the state of each port.
    """
    pdu_link.port_states = list(port_states)
    if PowerState.ON in port_states:
        pdu_link.power_state = PowerState.ON
    elif all(state == PowerState.OFF for state in port_states):
        pdu_link.power_state = PowerState.OFF
    else:
        pdu_link.power_state = PowerState.UNKNOWN


def _tpm_power_states(device: tango.DeviceProxy) -> list[PowerState]:
    """
    Read the power state of every TPM bay.

    :param device: the device under test.

    :return: the power state of each bay, in bay order.
    """
    return [
        PowerState(device.read_attribute(f"tpm{bay}PowerState").value)
        for bay in range(1, len(TPM_ON_OFF) + 1)
    ]


# ---------------------------------
# Assembly and the link's lifecycle
# ---------------------------------
def test_builds_a_pdu_link_when_full_control_is_asked_for(
    subrack_device: tango.DeviceProxy,
    no_pdu_device: tango.DeviceProxy,
    pdu_link_factory: mock.Mock,
    no_pdu_link_factory: mock.Mock,
) -> None:
    """
    Test that the link is built the first time the device goes online, and once.

    It is built from PduTrl and PduPorts, and only when both are set. It
    subscribes through the device's own callback scheduler.

    :param subrack_device: the device under test, offline.
    :param no_pdu_device: the device that has no PDU, online.
    :param pdu_link_factory: the PDU link factory of the device with a PDU.
    :param no_pdu_link_factory: the PDU link factory of the device without one.
    """
    pdu_link_factory.assert_not_called()

    subrack_device.adminMode = AdminMode.ONLINE
    subrack_device.adminMode = AdminMode.OFFLINE
    subrack_device.adminMode = AdminMode.ONLINE

    pdu_link_factory.assert_called_once()
    (trl, ports, callback_scheduler, _logger) = pdu_link_factory.call_args.args
    assert trl == PDU_TRL
    assert ports == PDU_PORTS
    assert isinstance(callback_scheduler, CallbackScheduler)
    no_pdu_link_factory.assert_not_called()


def test_init_builds_a_new_link_on_a_new_scheduler(
    subrack_device: tango.DeviceProxy,
    pdu_link_factory: mock.Mock,
) -> None:
    """
    Test that re-initialising shuts the old scheduler down and builds another.

    Shutting the old scheduler down is what ends the old link's subscriptions.

    adminMode is memorized, so the device goes online again as it initialises,
    and that builds the new link.

    :param subrack_device: the device under test.
    :param pdu_link_factory: the PDU link factory.
    """
    subrack_device.adminMode = AdminMode.ONLINE
    with mock.patch.object(CallbackScheduler, "shutdown", autospec=True) as shutdown:
        subrack_device.Init()

    shutdown.assert_called_once()
    assert pdu_link_factory.call_count == 2
    (first, second) = [call.args[2] for call in pdu_link_factory.call_args_list]
    assert first is not second


# ---------------------------------
# State
# ---------------------------------
@pytest.mark.parametrize(
    ("port_states", "poll", "expected"),
    [
        pytest.param((PowerState.OFF, PowerState.OFF), None, DevState.OFF, id="off"),
        pytest.param(
            (PowerState.OFF, PowerState.OFF),
            RequestError("Connection refused"),
            DevState.OFF,
            id="off-unreachable",
        ),
        pytest.param(
            (PowerState.OFF, PowerState.OFF),
            HttpError("500 Server Error"),
            DevState.OFF,
            id="off-board-error",
        ),
        pytest.param((PowerState.ON, PowerState.ON), None, DevState.ON, id="on"),
        pytest.param(
            (PowerState.ON, PowerState.OFF), None, DevState.ON, id="one-port-on"
        ),
        pytest.param(
            (PowerState.UNKNOWN, PowerState.UNKNOWN),
            None,
            DevState.ON,
            id="unknown-board-answers",
        ),
        pytest.param(
            (PowerState.OFF, PowerState.UNKNOWN),
            None,
            DevState.ON,
            id="one-port-unknown-board-answers",
        ),
    ],
)
def test_the_pdu_and_the_poll_decide_the_state(  # pylint: disable=too-many-arguments
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    pdu_link: mock.Mock,
    poll_succeeded: Callable[[], None],
    poll_failed: Callable[[Exception], None],
    port_states: tuple[PowerState, ...],
    poll: Exception | None,
    expected: DevState,
) -> None:
    """
    Test that every port off gives OFF, and otherwise the poll decides.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param pdu_link: the mocked PDU link.
    :param poll_succeeded: supplies a successful poll.
    :param poll_failed: supplies a failed poll.
    :param port_states: the state of each PDU port.
    :param poll: the exception the poll fails with, or None for a poll that
        succeeds.
    :param expected: the state the device should reach.
    """
    _set_pdu(pdu_link, *port_states)

    if poll is None:
        poll_succeeded()
    else:
        poll_failed(poll)

    change_event_callbacks["state"].assert_change_event(expected)


def test_the_pdu_going_off_clears_a_fault(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    pdu_link: mock.Mock,
    poll_succeeded: Callable[[], None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that a faulted subrack goes OFF when its PDU ports go off, and back ON.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param pdu_link: the mocked PDU link.
    :param poll_succeeded: supplies a successful poll.
    :param poll_failed: supplies a failed poll.
    """
    _set_pdu(pdu_link, PowerState.ON, PowerState.ON)
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    poll_failed(HttpError("500 Server Error"))
    change_event_callbacks["state"].assert_change_event(DevState.FAULT)

    _set_pdu(pdu_link, PowerState.OFF, PowerState.OFF)
    poll_failed(RequestError("Connection refused"))
    change_event_callbacks["state"].assert_change_event(DevState.OFF)

    _set_pdu(pdu_link, PowerState.ON, PowerState.ON)
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)


def test_a_board_error_after_off_is_unknown(
    online_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    pdu_link: mock.Mock,
    poll_succeeded: Callable[[], None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that a board error straight after OFF gives UNKNOWN, not FAULT.

    The operational state model has no transition from OFF into FAULT, so
    reporting one would raise. Nothing has been read since the power came
    back, so UNKNOWN is also what the device knows.

    :param online_device: the device under test, online and not yet polled.
    :param change_event_callbacks: the callbacks subscribed to the device.
    :param pdu_link: the mocked PDU link.
    :param poll_succeeded: supplies a successful poll.
    :param poll_failed: supplies a failed poll.
    """
    _set_pdu(pdu_link, PowerState.ON, PowerState.ON)
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.ON)
    _set_pdu(pdu_link, PowerState.OFF, PowerState.OFF)
    poll_succeeded()
    change_event_callbacks["state"].assert_change_event(DevState.OFF)

    _set_pdu(pdu_link, PowerState.UNKNOWN, PowerState.UNKNOWN)
    poll_failed(HttpError("500 Server Error"))

    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)


# ---------------------------------
# TPM power states and PDU port states
# ---------------------------------
def test_tpms_have_no_supply_while_the_pdu_is_off(
    online_device: tango.DeviceProxy,
    pdu_link: mock.Mock,
    poll_succeeded: Callable[[], None],
    poll_failed: Callable[[Exception], None],
) -> None:
    """
    Test that every TPM reports NO_SUPPLY while every PDU port is off.

    This is what ``MccsSubrack`` reports when its power is off.

    :param online_device: the device under test, online and not yet polled.
    :param pdu_link: the mocked PDU link.
    :param poll_succeeded: supplies a successful poll.
    :param poll_failed: supplies a failed poll.
    """
    _set_pdu(pdu_link, PowerState.OFF, PowerState.OFF)
    poll_failed(RequestError("Connection refused"))
    assert _tpm_power_states(online_device) == [PowerState.NO_SUPPLY] * len(TPM_ON_OFF)

    # A board that still answers does not override the PDU.
    poll_succeeded()
    assert _tpm_power_states(online_device) == [PowerState.NO_SUPPLY] * len(TPM_ON_OFF)

    _set_pdu(pdu_link, PowerState.ON, PowerState.ON)
    poll_succeeded()
    assert _tpm_power_states(online_device) == TPM_POWER_STATES


def test_pdu_port_states_follow_the_link(
    online_device: tango.DeviceProxy,
    pdu_link: mock.Mock,
    poll_succeeded: Callable[[], None],
    poll_failed: Callable[[Exception], None],
    polling_stopped: Callable[[], None],
) -> None:
    """
    Test that pduPortStates reports the link, and survives a failed poll.

    :param online_device: the device under test, online and not yet polled.
    :param pdu_link: the mocked PDU link.
    :param poll_succeeded: supplies a successful poll.
    :param poll_failed: supplies a failed poll.
    :param polling_stopped: tells the device that polling has stopped.
    """
    _set_pdu(pdu_link, PowerState.ON, PowerState.OFF)
    poll_succeeded()
    value = online_device.read_attribute("pduPortStates")
    assert value.quality == tango.AttrQuality.ATTR_VALID
    assert list(value.value) == [PowerState.ON, PowerState.OFF]

    # The PDU port states come from the PDU, so a lost board leaves them.
    poll_failed(RequestError("Connection refused"))
    value = online_device.read_attribute("pduPortStates")
    assert value.quality == tango.AttrQuality.ATTR_VALID
    assert list(value.value) == [PowerState.ON, PowerState.OFF]

    online_device.adminMode = AdminMode.OFFLINE
    polling_stopped()
    assert (
        online_device.read_attribute("pduPortStates").quality
        == tango.AttrQuality.ATTR_INVALID
    )


def test_a_device_without_a_pdu_reports_no_port_states(
    no_pdu_device: tango.DeviceProxy,
) -> None:
    """
    Test that a device with no PDU reports no PDU port states.

    :param no_pdu_device: the device that has no PDU, online.
    """
    assert no_pdu_device.state() == DevState.UNKNOWN
    assert (
        no_pdu_device.read_attribute("pduPortStates").quality
        == tango.AttrQuality.ATTR_INVALID
    )


# ---------------------------------
# On and Off
# ---------------------------------
@pytest.mark.parametrize(
    ("command", "on", "target", "commanded_state"),
    [
        ("On", True, PowerState.ON, "ON"),
        ("Off", False, PowerState.OFF, "OFF"),
    ],
    ids=["On", "Off"],
)
# pylint: disable-next=too-many-arguments
def test_a_power_command_switches_every_port_and_waits(
    lrc: LRCManager,
    online_device: tango.DeviceProxy,
    pdu_link: mock.Mock,
    board: mock.Mock,
    command: str,
    on: bool,
    target: PowerState,
    commanded_state: str,
) -> None:
    """
    Test that On and Off switch the ports, then wait for them to reach the target.

    Only Off shuts the SMM down first.

    :param lrc: the long running command manager for the device under test.
    :param online_device: the device under test, online.
    :param pdu_link: the mocked PDU link.
    :param board: the mocked subrack client.
    :param command: the command to run.
    :param on: whether the command switches the ports on.
    :param target: the power state the command waits for.
    :param commanded_state: what commandedState should read afterwards.
    """
    calls = mock.Mock()
    calls.attach_mock(board.run_board_command, "run_board_command")
    calls.attach_mock(pdu_link.set_ports, "set_ports")

    lrc.run_command(command)

    lrc.assert_command_finished(
        status="COMPLETED",
        result_code=ResultCode.OK,
        result_message="What the PDU did.",
        timeout=EVENT_TIMEOUT,
    )
    shutdown = [
        mock.call.run_board_command("poweroff_subrack", "false", abort_event=mock.ANY)
    ]
    assert calls.mock_calls == [*([] if on else shutdown), mock.call.set_ports(on)]
    pdu_link.wait_for.assert_called_once_with(
        target, PDU_COMMAND_TIMEOUT, abort_event=mock.ANY
    )
    assert online_device.commandedState == commanded_state


def test_off_does_not_shut_down_an_smm_that_has_no_power(
    lrc: LRCManager, pdu_link: mock.Mock, board: mock.Mock
) -> None:
    """
    Test that Off sends no shutdown while the PDU ports are already off.

    :param lrc: the long running command manager for the device under test.
    :param pdu_link: the mocked PDU link.
    :param board: the mocked subrack client.
    """
    pdu_link.power_state = PowerState.OFF

    lrc.run_command("Off")

    lrc.assert_command_finished(status="COMPLETED", timeout=EVENT_TIMEOUT)
    board.run_board_command.assert_not_called()
    pdu_link.set_ports.assert_called_once_with(False)


def test_off_switches_the_ports_when_the_smm_refuses_the_shutdown(
    lrc: LRCManager, pdu_link: mock.Mock, board: mock.Mock
) -> None:
    """
    Test that Off still removes power from a board that refuses the shutdown.

    :param lrc: the long running command manager for the device under test.
    :param pdu_link: the mocked PDU link.
    :param board: the mocked subrack client.
    """
    board.run_board_command.return_value = (
        CommandOutcome.FAILED,
        "The board did not answer.",
        None,
    )

    lrc.run_command("Off")

    lrc.assert_command_finished(status="COMPLETED", timeout=EVENT_TIMEOUT)
    pdu_link.set_ports.assert_called_once_with(False)


def _abort_while_shutting_down(
    name: str, args: str, abort_event: threading.Event
) -> tuple[CommandOutcome, str, None]:
    """
    Accept the shutdown, and ask for an abort before the shutdown wait.

    :param name: the board command.
    :param args: the board command argument string.
    :param abort_event: the abort event of the task.

    :return: what the board answers.
    """
    abort_event.set()
    return (CommandOutcome.COMPLETED, "The command completed.", None)


@pytest.mark.parametrize(
    "board_answer",
    [
        pytest.param(
            (CommandOutcome.ABORTED, "The command was aborted.", None),
            id="during_the_command",
        ),
        pytest.param(_abort_while_shutting_down, id="during_the_wait"),
    ],
)
def test_an_abort_during_the_shutdown_leaves_the_ports_on(
    lrc: LRCManager,
    pdu_link: mock.Mock,
    board: mock.Mock,
    board_answer: tuple[CommandOutcome, str, None] | Callable,
) -> None:
    """
    Test that an abort before the ports switch ends Off as aborted.

    :param lrc: the long running command manager for the device under test.
    :param pdu_link: the mocked PDU link.
    :param board: the mocked subrack client.
    :param board_answer: what the board answers, or a callable that answers.
    """
    if callable(board_answer):
        board.run_board_command.side_effect = board_answer
    else:
        board.run_board_command.return_value = board_answer

    lrc.run_command("Off")

    lrc.assert_command_finished(
        status="ABORTED",
        result_code=ResultCode.ABORTED,
        result_message_contains="before the PDU ports switched off",
        timeout=EVENT_TIMEOUT,
    )
    pdu_link.set_ports.assert_not_called()


@pytest.mark.parametrize(
    ("outcome", "status", "result_code"),
    [
        (CommandOutcome.ABORTED, "ABORTED", ResultCode.ABORTED),
        (CommandOutcome.FAILED, "FAILED", ResultCode.FAILED),
    ],
    ids=["aborted", "failed"],
)
def test_every_wait_outcome_ends_the_command(
    lrc: LRCManager,
    pdu_link: mock.Mock,
    outcome: CommandOutcome,
    status: str,
    result_code: ResultCode,
) -> None:
    """
    Test that every way a wait can end leaves the command on a final status.

    :param lrc: the long running command manager for the device under test.
    :param pdu_link: the mocked PDU link.
    :param outcome: what the wait reports.
    :param status: the task status the command should finish with.
    :param result_code: the result code the command should report.
    """
    pdu_link.wait_for.return_value = (outcome, "What the PDU did.")

    lrc.run_command("On")

    lrc.assert_command_finished(
        status=status,
        result_code=result_code,
        result_message="What the PDU did.",
        timeout=EVENT_TIMEOUT,
    )


def test_a_pdu_that_refuses_fails_the_command(
    lrc: LRCManager, pdu_link: mock.Mock
) -> None:
    """
    Test that a PDU that refuses a port fails the command without a wait.

    :param lrc: the long running command manager for the device under test.
    :param pdu_link: the mocked PDU link.
    """
    pdu_link.set_ports.return_value = (ResultCode.FAILED, "The PDU refused.")

    lrc.run_command("Off")

    lrc.assert_command_finished(
        status="FAILED",
        result_code=ResultCode.FAILED,
        result_message_contains="Could not switch the PDU ports OFF.",
        timeout=EVENT_TIMEOUT,
    )
    pdu_link.wait_for.assert_not_called()


@pytest.mark.parametrize("command", ["On", "Off"])
def test_a_device_without_a_pdu_refuses_power_commands(
    no_pdu_device: tango.DeviceProxy, command: str
) -> None:
    """
    Test that a device with no PDU refuses On and Off rather than accepting them.

    :param no_pdu_device: the device that has no PDU, online.
    :param command: the command to run.
    """
    with pytest.raises(tango.DevFailed, match="no PDU"):
        no_pdu_device.command_inout(command)


@pytest.mark.parametrize("command", ["On", "Off"])
def test_a_device_never_online_refuses_power_commands(
    subrack_device: tango.DeviceProxy,
    pdu_link: mock.Mock,
    command: str,
) -> None:
    """
    Test that On and Off are refused by a device that has not been online.

    The link is built when the device first goes online, so before that the
    command has nothing to switch the ports through.

    :param subrack_device: the device under test, offline.
    :param pdu_link: the mocked PDU link.
    :param command: the command to run.
    """
    assert subrack_device.state() == DevState.DISABLE

    with pytest.raises(tango.DevFailed, match="no PDU link"):
        subrack_device.command_inout(command)

    pdu_link.set_ports.assert_not_called()


@pytest.mark.parametrize("command", ["On", "Off"])
def test_an_offline_device_refuses_power_commands(  # pylint: disable=too-many-arguments
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
    pdu_link: mock.Mock,
    polling_stopped: Callable[[], None],
    command: str,
) -> None:
    """
    Test that On and Off are refused while the device is offline again.

    The base class refuses both in ``DISABLE``, which is where an offline
    device sits. It queues the command, and then rejects it when it would
    start, so the command finishes as ``REJECTED`` without reaching the PDU.

    :param subrack_device: the device under test, offline.
    :param change_event_callbacks: the callbacks to subscribe with.
    :param pdu_link: the mocked PDU link.
    :param polling_stopped: tells the device that polling has stopped.
    :param command: the command to run.
    """
    subrack_device.adminMode = AdminMode.ONLINE
    subrack_device.adminMode = AdminMode.OFFLINE
    polling_stopped()
    assert subrack_device.state() == DevState.DISABLE
    lrc = LRCManager(subrack_device, change_event_callbacks)

    lrc.run_command(command)

    lrc.assert_command_finished(status="REJECTED", timeout=EVENT_TIMEOUT)
    pdu_link.set_ports.assert_not_called()
