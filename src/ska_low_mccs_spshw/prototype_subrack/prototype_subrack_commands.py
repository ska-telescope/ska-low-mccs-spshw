#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The Tango commands of the prototype subrack device.

:py:class:`SubrackCommands` declares every Tango command the device has. The
device mixes it in and supplies the subrack client that the board commands run
through, and the PDU link that ``On`` and ``Off`` run through.

Each board command is a long running command, because the SMB runs these
asynchronously. The task runs on a task executor thread, and
:py:meth:`~.subrack_client.Subrack.run_board_command` runs the whole handshake
on that thread. So a command never waits for a poll slot. A poll that lands
part way through a command gets ``BUSY`` from the board, and changes nothing.

``On`` and ``Off`` are long running commands too. Each task switches every PDU
port that feeds the subrack, then waits until the PDU reports every port in the
target state. Before ``Off`` switches the ports, it shuts the SMM down with
``poweroff_subrack``, unless the ports are already off. The device state
follows on the next poll, because the device state changes only on a poll.

The mixin inherits :py:class:`~ska_tango_base.long_running_commands.LRCMixin`,
because the ``long_running_command`` decorator needs the task executor and the
command tracker that mixin supplies. Stating that here rather than in the
device is what lets the device inherit the command surface and its machinery
together.
"""
from __future__ import annotations

import importlib.resources
import json
import socket
import threading
import time
from typing import Any, Final, Optional

import ska_tango_base as stb
from ska_control_model import AdminMode, PowerState, ResultCode, TaskStatus
from ska_tango_base.long_running_commands import LRCMixin, LRCReqType
from tango import DevState, Except

from ..subrack.subrack_data import FanMode, SubrackData
from .constants import (
    PDU_COMMAND_TIMEOUT,
    SMM_LEAVE_NETWORK_TIMEOUT,
    SMM_PROBE_INTERVAL,
    SMM_SHUTDOWN_TIME,
    ClientCommand,
    CommandOutcome,
)
from .pdu_link import PduLink
from .subrack_client import Subrack

__all__ = ["SubrackCommands"]


# The task callback status each command outcome ends on, and the result code
# that goes with it. Every outcome is terminal, so a command never stays in
# lrcExecuting.
_OUTCOMES: Final[dict[CommandOutcome, tuple[TaskStatus, ResultCode]]] = {
    CommandOutcome.COMPLETED: (TaskStatus.COMPLETED, ResultCode.OK),
    CommandOutcome.ABORTED: (TaskStatus.ABORTED, ResultCode.ABORTED),
    CommandOutcome.FAILED: (TaskStatus.FAILED, ResultCode.FAILED),
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
    The Tango commands of the prototype subrack device.

    Mixed into the device, which supplies the subrack and the PDU link below.
    The only state the mixin holds is the command schemas, which it loads in
    :py:meth:`init_device`. A command reads the subrack or the PDU link the
    device assembled rather than one it keeps.

    Every board command runs one SMB command through
    :py:meth:`~.subrack_client.Subrack.run_board_command`. What that returns
    maps onto a task status through ``_OUTCOMES``, so an abort reports
    ``ABORTED`` and a board that refused reports ``FAILED``. ``On`` and ``Off``
    report what their PDU wait returns in the same way.
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

    @property
    def pdu_link(self: SubrackCommands) -> PduLink:
        """
        Return the link to the PDU that feeds the subrack.

        :raises NotImplementedError: always, because the device supplies it.
        """
        raise NotImplementedError(
            f"'pdu_link' property must be implemented by '{type(self).__name__}'."
        )

    def wake_poller(self: SubrackCommands) -> None:
        """
        Make the next poll run now, rather than at the update rate.

        :raises NotImplementedError: always, because the device supplies it.
        """
        raise NotImplementedError(
            f"'wake_poller' must be implemented by '{type(self).__name__}'."
        )

    _admin_mode: AdminMode
    """The admin mode, which ``BaseInterface`` stores as it is written."""

    _commanded_state: Optional[DevState]
    """The commanded state, which ``BaseInterface`` declares as a signal."""

    SubrackIp: str
    """The address of the SMM, which the device declares as a property."""

    SubrackPort: int
    """The port of the SMM web server, which the device declares as a property."""

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
        Return whether a board command may run now.

        Only ``ONLINE`` and ``ENGINEERING`` let the device contact the subrack.
        Every other ``adminMode`` asks it to make no contact, so a command is
        refused there. ``On`` and ``Off`` do not use this. The base class
        refuses them in ``DISABLE``.

        ``adminMode`` is read rather than the state, because the device
        reaches ``DISABLE`` only after the last poll reports back. A command
        sent in that gap would otherwise start after the device went offline.

        :param request_type: whether the command is being queued or executed.
            Both are refused on the same grounds, so this is not read.

        :return: whether the command may run.
        """
        return self._admin_mode in (AdminMode.ONLINE, AdminMode.ENGINEERING)

    def is_SetPowerSupplyFanSpeed_allowed(  # pylint: disable=invalid-name
        self: SubrackCommands, request_type: Optional[LRCReqType] = None
    ) -> bool:
        """
        Return whether the power supply fan speed may be set now.

        API 1.8.0 has no ``set_power_supply_fan_speed`` command, so the command
        is refused with a reason, the same as on ``MccsSubrack``. Until the
        board info has been read the API version is unknown, so the command is
        let through and the board decides.

        :param request_type: whether the command is being queued or executed.
            Both are refused on the same grounds, so this is not read.

        :return: whether the command may run.
        """
        if not self.is_board_command_allowed(request_type):
            return False
        board_info = self.subrack.board_info
        if board_info is not None and not SubrackData.supports_power_supply_fan_speed(
            board_info
        ):
            Except.throw_exception(
                "CommandNotAllowed",
                "SetPowerSupplyFanSpeed is not supported by subrack "
                f"API {board_info['SMM']['bios']}.",
                self.get_name(),
            )
        return True

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
        fisallowed="is_SetPowerSupplyFanSpeed_allowed"
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
    # Power commands
    # ----------------------------------
    @stb.long_running_commands.submit_lrc_task
    def execute_On(
        self: SubrackCommands,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Switch on every PDU port that feeds the subrack.

        :return: the task that switches the ports.
        """
        return self._power_task(PowerState.ON)

    @stb.long_running_commands.submit_lrc_task
    def execute_Off(
        self: SubrackCommands,
    ) -> stb.type_hints.TaskFunctionType:
        """
        Shut the SMM down, then switch off every PDU port that feeds the subrack.

        :return: the task that shuts the SMM down and switches the ports.
        """
        return self._power_task(PowerState.OFF)

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
            self.logger.info(
                f"Running board command {name.value} with args '{args}'..."
            )
            (outcome, message, _) = subrack.run_board_command(
                name.value, args, abort_event=task_abort_event
            )
            # The command can change what the board reports, such as the TPM
            # power states, so the device reads it now.
            self.wake_poller()
            self._report_outcome(task_callback, outcome, message)
            self.logger.info(
                f"Board command {name.value} with args '{args}' finished with "
                f"outcome {outcome.name} and message '{message}'."
            )

        return task

    @staticmethod
    def _report_outcome(
        task_callback: stb.type_hints.TaskCallbackType,
        outcome: CommandOutcome,
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

    # ----------------------------------
    # Switching the PDU ports
    # ----------------------------------
    def _power_task(
        self: SubrackCommands, target: PowerState
    ) -> stb.type_hints.TaskFunctionType:
        """
        Build the task that switches the PDU ports and waits for them.

        The link is read here, in the task factory, which runs before the
        command is submitted. So a device with no PDU rejects the command
        rather than accepting it and then failing it.

        :param target: the power state to switch the ports to.

        :return: the task that switches the ports.
        """
        pdu_link = self.pdu_link
        on = target == PowerState.ON
        # Off shuts the SMM down first, so the PDU does not cut power to a
        # running board.
        subrack = None if on else self.subrack

        def task(
            task_callback: stb.type_hints.TaskCallbackType,
            task_abort_event: threading.Event,
        ) -> None:
            task_callback(status=TaskStatus.IN_PROGRESS)
            self._commanded_state = DevState.ON if on else DevState.OFF
            if subrack is not None and pdu_link.power_state != PowerState.OFF:
                if not self._shut_down_smm(subrack, task_abort_event):
                    self._report_outcome(
                        task_callback,
                        CommandOutcome.ABORTED,
                        "The command was aborted before the PDU ports switched off.",
                    )
                    return
            self.logger.info(f"Switching the PDU ports {target.name}...")
            (result_code, message) = pdu_link.set_ports(on)
            if result_code != ResultCode.OK:
                message = f"Could not switch the PDU ports {target.name}. {message}"
                self.logger.error(message)
                task_callback(
                    status=TaskStatus.FAILED, result=(ResultCode.FAILED, message)
                )
                return

            (outcome, message) = pdu_link.wait_for(
                target, PDU_COMMAND_TIMEOUT, abort_event=task_abort_event
            )
            self._report_outcome(task_callback, outcome, message)
            self.logger.info(message)

        return task

    def _shut_down_smm(
        self: SubrackCommands, subrack: Subrack, abort_event: threading.Event
    ) -> bool:
        """
        Shut the SMM down, then wait for the shutdown to finish.

        ``poweroff_subrack`` switches off the TPMs, the backplane and the fans,
        and then shuts down the SMM. The PSUs stay on, because the PDU ports
        switch off next, and a PSU that the SMM switched off needs a slow power
        cycle to come back. The board answers before it shuts down. This then
        waits for the SMM to leave the network, and then waits
        ``SMM_SHUTDOWN_TIME`` more for the rest of the shutdown.

        A board that does not accept the command is logged, and the ports
        still switch off. So ``Off`` removes power from a board that has
        stopped answering.

        :param subrack: the client to send the command through.
        :param abort_event: an event that requests an abort when set.

        :return: false if the command was aborted, otherwise true.
        """
        self.logger.info("Shutting the SMM down before the PDU ports switch off...")
        (outcome, message, _) = subrack.run_board_command(
            ClientCommand.POWEROFF_SUBRACK.value, "false", abort_event=abort_event
        )
        if outcome == CommandOutcome.ABORTED:
            return False
        if outcome == CommandOutcome.FAILED:
            self.logger.warning(
                "The SMM did not accept poweroff_subrack, so the PDU ports switch "
                f"off without a shutdown. {message}"
            )
            return True
        if not self._wait_for_smm_to_leave_network(abort_event):
            return False
        return not abort_event.wait(SMM_SHUTDOWN_TIME)

    def _wait_for_smm_to_leave_network(
        self: SubrackCommands, abort_event: threading.Event
    ) -> bool:
        """
        Wait until the SMM stops answering on the network.

        Each probe opens a TCP connection to the SMM web server. A refused
        connection means that the web server has stopped but the SMM network is
        still up, so the wait goes on. Any other error, such as a timeout or no
        route to the SMM, means that the SMM network is down.

        An SMM that still answers after ``SMM_LEAVE_NETWORK_TIMEOUT`` is logged,
        and the ports still switch off.

        :param abort_event: an event that requests an abort when set.

        :return: false if the command was aborted, otherwise true.
        """
        address = (self.SubrackIp, self.SubrackPort)
        deadline = time.monotonic() + SMM_LEAVE_NETWORK_TIMEOUT
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(address, timeout=SMM_PROBE_INTERVAL):
                    pass
            except ConnectionRefusedError:
                pass
            except OSError as error:
                self.logger.info(f"The SMM has left the network. {error!r}")
                return True
            if abort_event.wait(SMM_PROBE_INTERVAL):
                return False
        self.logger.warning(
            f"The SMM still answers after {SMM_LEAVE_NETWORK_TIMEOUT}s, so the PDU "
            "ports switch off anyway."
        )
        return True
