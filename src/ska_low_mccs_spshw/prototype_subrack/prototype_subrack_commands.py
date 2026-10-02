#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The board commands of the prototype subrack device.

:py:class:`SubrackCommands` declares every Tango command that reaches the
management board, and nothing else. The device mixes it in and supplies the
subrack client the commands run through.

Each command is a long running command, because the SMB runs these
asynchronously. The task runs on a task executor thread, and
:py:meth:`~.subrack_client.Subrack.run_board_command` runs the whole handshake
on that thread. So a command never waits for a poll slot. A poll that lands
part way through a command gets ``BUSY`` from the board, and changes nothing.

The mixin inherits :py:class:`~ska_tango_base.long_running_commands.LRCMixin`,
because the ``long_running_command`` decorator needs the task executor and the
command tracker that mixin supplies. Stating that here rather than in the
device is what lets the device inherit the command surface and its machinery
together.
"""
from __future__ import annotations

import importlib.resources
import json
import threading
from typing import Any, Final, Optional

import ska_tango_base as stb
from ska_control_model import AdminMode, ResultCode, TaskStatus
from ska_tango_base.long_running_commands import LRCMixin, LRCReqType

from ..subrack.subrack_data import FanMode
from .constants import ClientCommand
from .subrack_client import BoardCommandStatus, Subrack

__all__ = ["SubrackCommands"]


# The task callback status each board command outcome ends on, and the result
# code that goes with it. Every outcome is terminal, so a command never stays
# in lrcExecuting.
_OUTCOMES: Final[dict[BoardCommandStatus, tuple[TaskStatus, ResultCode]]] = {
    BoardCommandStatus.COMPLETED: (TaskStatus.COMPLETED, ResultCode.OK),
    BoardCommandStatus.ABORTED: (TaskStatus.ABORTED, ResultCode.ABORTED),
    BoardCommandStatus.FAILED: (TaskStatus.FAILED, ResultCode.FAILED),
}


def _load_schema(command_name: str) -> dict[str, Any]:
    """
    Load the JSON schema for one command, from the file named after it.

    :param command_name: the Tango command the schema validates.

    :return: the schema.
    """
    return json.loads(
        importlib.resources.read_text(
            "ska_low_mccs_spshw.schemas.subrack",
            f"MccsSubrack_{command_name}.json",
        )
    )


# pylint: disable=too-many-ancestors
class SubrackCommands(LRCMixin):
    """
    The Tango commands of the prototype subrack device that reach the board.

    Mixed into the device, which supplies the subrack below. The only state
    the mixin holds is the command schemas, which it loads in
    :py:meth:`init_device`. A command reads the subrack the device assembled
    rather than one it keeps.

    Every command runs one SMB command through
    :py:meth:`~.subrack_client.Subrack.run_board_command`. What that returns
    maps onto a task status through ``_OUTCOMES``, so an abort reports
    ``ABORTED`` and a board that refused reports ``FAILED``.
    """

    # ----------------------------------
    # What the device must supply
    # ----------------------------------
    @property
    def subrack(self: SubrackCommands) -> Subrack:
        """
        Return the client the commands run through.

        :raises NotImplementedError: always, because the device supplies it.
        """
        raise NotImplementedError(
            f"'subrack' property must be implemented by '{type(self).__name__}'."
        )

    _admin_mode: AdminMode
    """The admin mode, which ``BaseInterface`` stores as it is written."""

    # ----------------------------------
    # Command schemas
    # ----------------------------------
    SetSubrackFanSpeed_SCHEMA: dict[str, Any]
    SetSubrackFanMode_SCHEMA: dict[str, Any]
    SetPowerSupplyFanSpeed_SCHEMA: dict[str, Any]

    def init_device(self: SubrackCommands) -> None:
        """
        Load the command schemas, then initialise the rest of the device.

        The schemas load here and not at import, so importing the module reads
        no files. Each JSON command names its schema as a string, which the
        validator resolves on the device at each call.
        """
        self.SetSubrackFanSpeed_SCHEMA = _load_schema("SetSubrackFanSpeed")
        self.SetSubrackFanMode_SCHEMA = _load_schema("SetSubrackFanMode")
        self.SetPowerSupplyFanSpeed_SCHEMA = _load_schema("SetPowerSupplyFanSpeed")
        super().init_device()

    # ----------------------------------
    # Whether a command may run
    # ----------------------------------
    def is_board_command_allowed(
        self: SubrackCommands, request_type: Optional[LRCReqType] = None
    ) -> bool:
        """
        Return whether a command that reaches the board may run now.

        Only ``ONLINE`` and ``ENGINEERING`` let the device contact the subrack.
        Every other ``adminMode`` asks it to make no contact, so a command is
        refused there.

        ``adminMode`` is read rather than the state, because the device
        reaches ``DISABLE`` only after the last poll reports back. A command
        sent in that gap would otherwise start after the device went offline.

        :param request_type: whether the command is being queued or executed.
            Both are refused on the same grounds, so this is not read.

        :return: whether the command may run.
        """
        return self._admin_mode in (AdminMode.ONLINE, AdminMode.ENGINEERING)

    # ----------------------------------
    # Stopping the board commands
    # ----------------------------------
    def abort_board_commands(self: SubrackCommands) -> None:
        """Abort the running board command and every queued one."""
        self.task_executor.abort()

    # ----------------------------------
    # TPM power commands
    # ----------------------------------
    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    def PowerOnTpm(
        self: SubrackCommands, tpm_number: int
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power up one TPM.

        :param tpm_number: the one-based number of the TPM bay to power up.

        :return: the task that runs the board command.
        """
        return self._board_command_task(ClientCommand.TURN_ON_TPM, str(tpm_number))

    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    def PowerOffTpm(
        self: SubrackCommands, tpm_number: int
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power down one TPM.

        :param tpm_number: the one-based number of the TPM bay to power down.

        :return: the task that runs the board command.
        """
        return self._board_command_task(ClientCommand.TURN_OFF_TPM, str(tpm_number))

    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    def PowerUpTpms(
        self: SubrackCommands,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power up every TPM.

        :return: the task that runs the board command.
        """
        return self._board_command_task(ClientCommand.TURN_ON_TPMS)

    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    def PowerDownTpms(
        self: SubrackCommands,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Power down every TPM.

        :return: the task that runs the board command.
        """
        return self._board_command_task(ClientCommand.TURN_OFF_TPMS)

    # ----------------------------------
    # Fan commands
    # ----------------------------------
    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    @stb.validators.validate_json_args(schema="SetSubrackFanSpeed_SCHEMA")
    def SetSubrackFanSpeed(
        self: SubrackCommands,
        subrack_fan_id: int,
        speed_percent: int,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the speed of one subrack backplane fan.

        The argument is a JSON string with both keywords.

        :param subrack_fan_id: the one-based fan number, from 1 to 4.
        :param speed_percent: the fan speed, as a percentage.

        :return: the task that runs the board command.
        """
        return self._board_command_task(
            ClientCommand.SET_SUBRACK_FAN_SPEED,
            f"{int(subrack_fan_id)},{int(speed_percent)}",
        )

    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    @stb.validators.validate_json_args(schema="SetSubrackFanMode_SCHEMA")
    def SetSubrackFanMode(
        self: SubrackCommands,
        fan_id: int,
        mode: int,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the speed mode of one subrack backplane fan.

        The argument is a JSON string with both keywords.

        :param fan_id: the one-based fan number, from 1 to 4.
        :param mode: 0 means MANUAL and 1 means AUTO.

        :return: the task that runs the board command.
        """
        return self._board_command_task(
            ClientCommand.SET_FAN_MODE,
            f"{int(fan_id)},{FanMode(mode).value}",
        )

    @stb.long_running_commands.long_running_command(
        fisallowed="is_board_command_allowed"
    )
    @stb.validators.validate_json_args(schema="SetPowerSupplyFanSpeed_SCHEMA")
    def SetPowerSupplyFanSpeed(
        self: SubrackCommands,
        power_supply_fan_id: int,
        speed_percent: int,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Set the speed of one power supply fan.

        The argument is a JSON string with both keywords.

        :param power_supply_fan_id: the one-based fan number, 1 or 2.
        :param speed_percent: the fan speed, as a percentage.

        :return: the task that runs the board command.
        """
        return self._board_command_task(
            ClientCommand.SET_POWER_SUPPLY_FAN_SPEED,
            f"{int(power_supply_fan_id)},{int(speed_percent)}",
        )

    # ----------------------------------
    # Commands this device refuses
    # ----------------------------------
    def execute_Standby(
        self: SubrackCommands,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Refuse to put the subrack into standby, because it has no such mode.

        Implemented so that the command answers rather than raising
        ``NotImplementedError`` from ``BaseInterface``.

        :return: a result code and a message.
        """
        return (
            [ResultCode.REJECTED],
            ["A subrack has no standby mode."],
        )

    def execute_Reset(
        self: SubrackCommands,
    ) -> stb.type_hints.DevVarLongStringArrayType:
        """
        Refuse to reset the subrack, because the board offers no reset.

        Implemented so that the command answers rather than raising
        ``NotImplementedError`` from ``BaseInterface``.

        :return: a result code and a message.
        """
        return (
            [ResultCode.REJECTED],
            ["A subrack management board cannot be reset."],
        )

    # ----------------------------------
    # Running a board command
    # ----------------------------------
    def _board_command_task(
        self: SubrackCommands, name: ClientCommand, args: str = ""
    ) -> stb.type_hints.TaskFunctionType:
        """
        Build the task that runs one board command and reports its outcome.

        The subrack is read here, in the task factory, which runs before the
        command is submitted. So a device that has no subrack rejects the
        command rather than accepting it and then failing it.

        :param name: the SMB command to run.
        :param args: the SMB command argument string.

        :return: the task that runs the board command.
        """
        subrack = self.subrack

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            task_callback(status=TaskStatus.IN_PROGRESS)
            (outcome, message, _) = subrack.run_board_command(
                name.value, args, abort_event=task_abort_event
            )
            self._report_outcome(task_callback, outcome, message)

        return task

    @staticmethod
    def _report_outcome(
        task_callback: stb.type_hints.TaskCallbackType,
        outcome: BoardCommandStatus,
        message: str,
    ) -> None:
        """
        Report what became of a board command to the task callback.

        Every outcome maps to a terminal task status, so no command is left in
        ``lrcExecuting``.

        :param task_callback: the callback to report to.
        :param outcome: what became of the board command.
        :param message: what the subrack client said about it.
        """
        (status, result_code) = _OUTCOMES[outcome]
        task_callback(status=status, result=(result_code, message))
