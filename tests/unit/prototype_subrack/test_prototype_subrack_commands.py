#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the prototype subrack board commands, against a mocked subrack.

The subrack and the poller are injected through the device module's
:py:func:`subrack_factory`, and both are mocks. So no board is reached and no
thread polls. A test says what the subrack client reports and asserts what the
command did with it, which leaves only the command code under test.

The hardware client and the computed values are left real, because the mocked
subrack means nothing ever calls them.

An outcome is read from the ``lrcFinished`` change event, through the repo's
:py:class:`~tests.test_tools.LRCManager`. There is no version 1
``longRunningCommandResult`` on this device, because it supports only version 2
of the long running command protocol.
"""

from __future__ import annotations

import gc
import json
import threading
from typing import Any, Iterator
from unittest import mock

import pytest
import tango
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DevState

from ska_low_mccs_spshw.prototype_subrack import BoardCommandStatus
from ska_low_mccs_spshw.prototype_subrack.prototype_subrack_device import (
    subrack_factory as device_class_factory,
)
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext
from tests.test_tools import LRCManager

# TODO: gc.disable() works around a hang during garbage collection.
gc.disable()

SUBRACK_ID = 1
# A second device in the same context, which assembles with no subrack.
UNASSEMBLED_SUBRACK_ID = 2
BOARD_HOST = "a-fake-board"
BOARD_PORT = 8081

# How long to wait for a command's change events. Every board command is
# mocked, so this only covers the task executor handing the task to a thread.
COMMAND_TIMEOUT = 10.0

# One row per command that passes straight through to one SMB command, giving
# the Tango command, its argument, and the SMB command and argument string it
# should produce. Every value is distinct, so a command wired to the wrong SMB
# name or a fan id swapped with a speed fails.
PASSED_THROUGH: list[tuple[str, Any, str, str]] = [
    ("PowerOnTpm", 3, "turn_on_tpm", "3"),
    ("PowerOffTpm", 5, "turn_off_tpm", "5"),
    ("PowerUpTpms", None, "turn_on_tpms", ""),
    ("PowerDownTpms", None, "turn_off_tpms", ""),
    (
        "SetSubrackFanSpeed",
        json.dumps({"subrack_fan_id": 2, "speed_percent": 70}),
        "set_subrack_fan_speed",
        "2,70",
    ),
    (
        "SetSubrackFanMode",
        json.dumps({"fan_id": 3, "mode": 1}),
        "set_fan_mode",
        "3,1",
    ),
    (
        "SetPowerSupplyFanSpeed",
        json.dumps({"power_supply_fan_id": 2, "speed_percent": 60}),
        "set_power_supply_fan_speed",
        "2,60",
    ),
]

# Every command that reaches the board, for the tests that do not care what
# each one sends.
BOARD_COMMANDS: list[tuple[str, Any]] = [
    (command, argument) for command, argument, _, _ in PASSED_THROUGH
]

# Every command runs through ``_board_command_task``, and
# ``_report_outcome`` maps an outcome to a status without knowing which
# command it is reporting for. So one command stands for all of them.
OUTCOME_COMMAND = "PowerUpTpms"


@pytest.fixture(name="subrack", scope="module")
def subrack_fixture() -> mock.Mock:
    """
    Return the subrack client the device is built around, built once.

    The device binds this object when it initialises, so it cannot be replaced
    per test. :py:func:`reset_device_fixture` resets it instead.

    :return: a mock of the subrack client.
    """
    return mock.Mock(name="subrack")


@pytest.fixture(name="subrack_factory", scope="module")
def subrack_factory_fixture(subrack: mock.Mock) -> mock.Mock:
    """
    Return the subrack factory, which carries the device's poll callbacks.

    The reset needs ``stopped_callback``, because the poller that would
    otherwise call it is a mock.

    :param subrack: the subrack client it should return.

    :return: the factory.
    """
    return mock.Mock(name="subrack_factory", return_value=subrack)


@pytest.fixture(name="device_context", scope="module")
def device_context_fixture(
    subrack_factory: mock.Mock,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Run one prototype subrack device for the whole module.

    :param subrack_factory: builds the subrack client the device holds.

    :yields: the running test harness context.
    """
    harness = SpsTangoTestHarness()
    harness.add_prototype_subrack_device(
        SUBRACK_ID,
        address=(BOARD_HOST, BOARD_PORT),
        device_class=device_class_factory(
            subrack=subrack_factory,
            subrack_poller=mock.Mock(name="poller_factory"),
        ),
    )
    # A second device whose subrack factory supplies nothing, so it assembles
    # with no subrack. It stands in for an assembly that failed part way
    # through.
    harness.add_prototype_subrack_device(
        UNASSEMBLED_SUBRACK_ID,
        address=(BOARD_HOST, BOARD_PORT),
        # A distinct Tango class name, because one context cannot hold two
        # entries pointing at the same class.
        device_class=type(
            "MccsUnassembledPrototypeSubrack",
            (
                device_class_factory(
                    subrack=mock.Mock(name="no_subrack_factory", return_value=None),
                    subrack_poller=mock.Mock(name="poller_factory"),
                ),
            ),
            {},
        ),
    )
    with harness as context:
        yield context


@pytest.fixture(name="unassembled_device", scope="module")
def unassembled_device_fixture(
    device_context: SpsTangoTestHarnessContext,
) -> tango.DeviceProxy:
    """
    Return a device that assembled without a subrack, online.

    Online, so that a command it refuses is refused for want of a subrack
    rather than for being offline.

    :param device_context: the running test harness context.

    :return: a proxy to the device under test.
    """
    device = device_context.get_prototype_subrack_device(UNASSEMBLED_SUBRACK_ID)
    device.adminMode = AdminMode.ONLINE
    return device


@pytest.fixture(name="subrack_device", scope="module")
def subrack_device_fixture(
    device_context: SpsTangoTestHarnessContext,
) -> tango.DeviceProxy:
    """
    Return the one proxy every test in this module shares.

    :param device_context: the running test harness context.

    :return: a proxy to the device under test.
    """
    return device_context.get_prototype_subrack_device(SUBRACK_ID)


@pytest.fixture(name="change_event_callbacks", scope="module")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return the change event callbacks an :py:class:`LRCManager` subscribes with.

    The three keys are the ones that class expects when it is given no names of
    its own.

    :return: a group of change event callbacks.
    """
    return MockTangoEventCallbackGroup(
        "lrc_queue",
        "lrc_executing",
        "lrc_finished",
        timeout=COMMAND_TIMEOUT,
    )


@pytest.fixture(name="lrc", scope="module")
def lrc_fixture(
    subrack_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> LRCManager:
    """
    Return one long running command manager for the whole module.

    It subscribes to ``lrcQueue``, ``lrcExecuting`` and ``lrcFinished``, so a
    test waits on a change event rather than polling an attribute. Its
    constructor asserts that all three are empty, so it is built once, before
    the first command. It is then reused, because ``run_command`` replaces the
    command it tracks.

    :param subrack_device: the device under test.
    :param change_event_callbacks: the callbacks to subscribe with.

    :return: the long running command manager.
    """
    return LRCManager(subrack_device, change_event_callbacks)


# ---------------------------------------------------------------
# Reset between tests, in place of a fresh context
# ---------------------------------------------------------------
@pytest.fixture(name="reset_device", autouse=True)
def reset_device_fixture(
    subrack_device: tango.DeviceProxy,
    subrack: mock.Mock,
    subrack_factory: mock.Mock,
) -> None:
    """
    Put the device and its subrack back to a known state before each test.

    This is what a fresh context gives for free, and what a shared one has to
    do by hand.

    Writing ``adminMode`` is not enough on its own. The device reaches
    ``DISABLE`` from :py:meth:`_polling_stopped`, which the real poller calls
    after its last poll. This poller is a mock, so the reset calls that
    callback itself. Without it the device would stay ``UNKNOWN`` once any
    earlier test had taken it online.

    :param subrack_device: the device under test.
    :param subrack: the subrack client the device holds.
    :param subrack_factory: the factory, which carries the poll callbacks.
    """
    subrack.reset_mock()
    subrack.run_board_command.return_value = (
        BoardCommandStatus.COMPLETED,
        "The command completed.",
        None,
    )
    subrack_device.adminMode = AdminMode.OFFLINE
    with tango.EnsureOmniThread():
        subrack_factory.call_args.kwargs["stopped_callback"]()


@pytest.fixture(name="online_device")
def online_device_fixture(subrack_device: tango.DeviceProxy) -> tango.DeviceProxy:
    """
    Return the device under test, online and so willing to command the board.

    The poller is a mock, so going online starts nothing and nothing is
    polled. The device leaves ``DISABLE``, which is what lets a board command
    run.

    :param subrack_device: the device under test.

    :return: the device under test.
    """
    subrack_device.adminMode = AdminMode.ONLINE
    assert subrack_device.state() == DevState.UNKNOWN
    return subrack_device


@pytest.mark.parametrize(
    ("command", "argument", "board_command", "board_argument"),
    PASSED_THROUGH,
    ids=[command for command, _, _, _ in PASSED_THROUGH],
)
def test_a_command_sends_one_board_command(  # pylint: disable=too-many-arguments
    online_device: tango.DeviceProxy,
    lrc: LRCManager,
    subrack: mock.Mock,
    command: str,
    argument: Any,
    board_command: str,
    board_argument: str,
) -> None:
    """
    Test that each command sends the SMB command and argument it stands for.

    :param online_device: the device under test, online.
    :param lrc: the long running command manager for the device under test.
    :param subrack: the mocked subrack client.
    :param command: the name of the command to invoke.
    :param argument: the argument to invoke it with.
    :param board_command: the SMB command it should send.
    :param board_argument: the SMB argument string it should send.
    """
    lrc.run_command(command, argument)

    lrc.assert_command_finished(status="COMPLETED", result_code=ResultCode.OK)
    subrack.run_board_command.assert_called_once_with(
        board_command, board_argument, abort_event=mock.ANY
    )
    # The task's own abort event, so aborting the command reaches the board.
    assert isinstance(
        subrack.run_board_command.call_args.kwargs["abort_event"], threading.Event
    )


@pytest.mark.parametrize(
    ("outcome", "status", "result_code"),
    [
        (BoardCommandStatus.COMPLETED, "COMPLETED", ResultCode.OK),
        (BoardCommandStatus.FAILED, "FAILED", ResultCode.FAILED),
        (BoardCommandStatus.ABORTED, "ABORTED", ResultCode.ABORTED),
    ],
    ids=["completed", "failed", "aborted"],
)
def test_every_outcome_ends_the_command(  # pylint: disable=too-many-arguments
    online_device: tango.DeviceProxy,
    lrc: LRCManager,
    subrack: mock.Mock,
    outcome: BoardCommandStatus,
    status: str,
    result_code: ResultCode,
) -> None:
    """
    Test that every board command outcome ends the command on a final status.

    A command left on a non-final status would sit in ``lrcExecuting`` for
    ever. Reaching ``lrcFinished`` is what proves it was not stranded there.

    Checked against one command rather than against all seven, because
    :py:meth:`SubrackCommands._report_outcome` maps an outcome to a status
    without knowing which command it is reporting for. Running the same lookup
    through every command would assert the same two lines seven times, and
    each case costs a device round trip.

    :param online_device: the device under test, online.
    :param lrc: the long running command manager for the device under test.
    :param subrack: the mocked subrack client.
    :param outcome: what the subrack client should report.
    :param status: the task status the command should finish with.
    :param result_code: the result code the command should report.
    """
    subrack.run_board_command.return_value = (outcome, "What the board did.", None)

    lrc.run_command(OUTCOME_COMMAND)

    lrc.assert_command_finished(
        status=status,
        result_code=result_code,
        result_message="What the board did.",
    )


@pytest.mark.parametrize(
    ("command", "argument"), BOARD_COMMANDS, ids=[name for name, _ in BOARD_COMMANDS]
)
def test_an_offline_device_reaches_no_board(
    subrack_device: tango.DeviceProxy,
    subrack: mock.Mock,
    command: str,
    argument: Any,
) -> None:
    """
    Test that a command is refused while adminMode is OFFLINE.

    OFFLINE asks the device to make no contact with the subrack, so a command
    that reached the board anyway would break that.

    :param subrack_device: the device under test, still offline.
    :param subrack: the mocked subrack client.
    :param command: the name of the command to invoke.
    :param argument: the argument to invoke it with.
    """
    assert subrack_device.state() == DevState.DISABLE

    with pytest.raises(tango.DevFailed):
        subrack_device.command_inout(command, argument)

    subrack.run_board_command.assert_not_called()


@pytest.mark.parametrize(
    ("command", "argument"),
    [
        ("SetSubrackFanSpeed", json.dumps({"subrack_fan_id": 9, "speed_percent": 70})),
        ("SetSubrackFanSpeed", json.dumps({"subrack_fan_id": 2})),
        ("SetSubrackFanMode", json.dumps({"fan_id": 2, "mode": 7})),
        ("SetPowerSupplyFanSpeed", json.dumps({"power_supply_fan_id": 3})),
        ("SetPowerSupplyFanSpeed", "not json at all"),
    ],
    ids=[
        "fan-out-of-range",
        "speed-missing",
        "mode-out-of-range",
        "id-only",
        "no-json",
    ],
)
def test_a_bad_argument_reaches_no_board(
    online_device: tango.DeviceProxy,
    subrack: mock.Mock,
    command: str,
    argument: str,
) -> None:
    """
    Test that an argument the schema refuses never reaches the board.

    :param online_device: the device under test, online.
    :param subrack: the mocked subrack client.
    :param command: the name of the command to invoke.
    :param argument: the argument to invoke it with.
    """
    with pytest.raises(tango.DevFailed):
        online_device.command_inout(command, argument)

    subrack.run_board_command.assert_not_called()


@pytest.mark.parametrize(
    ("command", "argument"), BOARD_COMMANDS, ids=[name for name, _ in BOARD_COMMANDS]
)
def test_a_device_without_a_subrack_refuses(
    unassembled_device: tango.DeviceProxy, command: str, argument: Any
) -> None:
    """
    Test that a device which did not finish assembling refuses a command.

    ``assemble`` leaves ``_subrack`` as ``None`` when it fails part way
    through. A command then has nothing to run through, and each task factory
    settles that before the command is submitted, so it is refused rather than
    accepted and then failed.

    :param unassembled_device: a device that assembled with no subrack.
    :param command: the name of the command to invoke.
    :param argument: the argument to invoke it with.
    """
    assert unassembled_device.state() != DevState.DISABLE

    with pytest.raises(tango.DevFailed):
        unassembled_device.command_inout(command, argument)


@pytest.mark.parametrize("command", ["Standby", "Reset"], ids=["Standby", "Reset"])
def test_a_command_the_subrack_cannot_do_is_rejected(
    online_device: tango.DeviceProxy,
    subrack: mock.Mock,
    command: str,
) -> None:
    """
    Test that Standby and Reset answer with a rejection.

    Neither action exists on a subrack. Both are implemented so that the
    command answers, rather than raising ``NotImplementedError`` from the base
    class.

    :param online_device: the device under test, online.
    :param subrack: the mocked subrack client.
    :param command: the name of the command to invoke.
    """
    ([result_code], [message]) = online_device.command_inout(command)

    assert result_code == ResultCode.REJECTED
    assert message
    subrack.run_board_command.assert_not_called()
