# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides for monitoring and control of a PSI-Low subrack."""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Callable, Final, Optional

from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common.component import MccsBaseComponentManager, WebHardwareClient
from ska_tango_base.poller import PollingComponentManager

from .http_stack import HttpPollRequest, HttpPollResponse
from .subrack_data import FanMode, SubrackData


# pylint: disable-next=too-many-instance-attributes
class SubrackDriver(
    MccsBaseComponentManager, PollingComponentManager[HttpPollRequest, HttpPollResponse]
):
    """A component manager for the PSI-Low subrack."""

    # pylint: disable-next=too-many-arguments
    def __init__(
        self: SubrackDriver,
        host: str,
        port: int,
        logger: logging.Logger,
        communication_state_callback: Callable,
        component_state_callback: Callable,
        update_rate: float = 5.0,
    ) -> None:
        """
        Initialise a new instance.

        :param host: the host name or IP address of the subrack
            management board.
        :param port: the port of the subrack management board.
        :param logger: a logger for this component manager to use for
            logging
        :param communication_state_callback: callback to be called when
            the status of communications between the component manager
            and its component changes.
        :param component_state_callback: callback to be called when the
            state of the component changes.
        :param update_rate: how often updates to attribute values should
            be provided. This is not necessarily the same as the rate at
            which the instrument is polled. For example, the instrument
            may be polled every 0.1 seconds, thus ensuring that any
            invoked commands or writes will be executed promptly.
            However, if the `update_rate` is 5.0, then routine reads of
            instrument values will only occur every 50th poll (i.e.
            every 5 seconds).
        """
        self._client = WebHardwareClient(host, port)

        self._poll_rate: Final = 0.1
        self._max_tick: Final = int(update_rate / self._poll_rate)

        # We'll count ticks upwards, but start at the maximum so that
        # our initial update request occurs as soon as possible.
        self._tick = self._max_tick

        # Whether the board is busy running a command. Let's be
        # extremely conservative here and assume that it is until we
        # know that it isn't.
        self._board_is_busy: Optional[bool] = True
        self._active_callback: Optional[Callable] = None

        self._write_lock = threading.Lock()

        self._commands_to_execute: OrderedDict[
            str, tuple[str, str, Optional[Callable]]
        ] = OrderedDict()

        self._attributes_to_write: dict[str, Any] = {}

        super().__init__(
            logger,
            communication_state_callback,
            component_state_callback,
            self._poll_rate,
            tpm_present=None,
            tpm_on_off=None,
            backplane_temperatures=None,
            board_temperatures=None,
            board_current=None,
            power_supply_currents=None,
            power_supply_fan_speeds=None,
            power_supply_powers=None,
            power_supply_voltages=None,
            subrack_fan_speeds=None,
            subrack_fan_speeds_percent=None,
            subrack_fan_mode=None,
            tpm_currents=None,
            tpm_powers=None,
            # tpm_temperatures=None,  # Not implemented on SMB
            tpm_voltages=None,
        )

        self.logger.debug(
            f"Initialising PSI-Low subrack component manager: "
            f"Update rate is {update_rate}. "
            f"Poll rate is {self._poll_rate}. "
            f"Attributes will be updated roughly each {self._max_tick} polls."
        )

    def off(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component off.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this command is not yet
            implemented
        """
        raise NotImplementedError("The device cannot be turned off or on.")

    def standby(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the component into low-power standby mode.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this command is not yet
            implemented
        """
        raise NotImplementedError("The device cannot be put into standby mode.")

    def on(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the component on.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this command is not yet
            implemented
        """
        raise NotImplementedError("The device cannot be turned off or on.")

    def reset(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the component (from fault state).

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because this command is not yet
            implemented
        """
        raise NotImplementedError("The device cannot be reset.")

    def turn_off_tpm(
        self: SubrackDriver,
        tpm_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a TPM off.

        :param tpm_number: (one-based) number of the TPM to turn off.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self._turn_off_on_tpm(tpm_number, False, task_callback)

    def turn_on_tpm(
        self: SubrackDriver,
        tpm_number: int,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a TPM on.

        :param tpm_number: (one-based) number of the TPM to turn on.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self._turn_off_on_tpm(tpm_number, True, task_callback)

    def turn_off_tpms(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn all TPMs off.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self._turn_off_on_tpm(0, False, task_callback)

    def turn_on_tpms(
        self: SubrackDriver, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn all TPMs on.

        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        return self._turn_off_on_tpm(0, True, task_callback)

    def _turn_off_on_tpm(
        self: SubrackDriver,
        tpm_number: int,
        is_turn_on: bool,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Turn a TPM off or on.

        :param tpm_number: (one-based) number of the TPM to turn off or
            on. Zero means turn *all* TPMs off or on.
        :param is_turn_on: whether to turn the TPM off or on. If true,
            the TPM will be turned on. If false, it will be turned off.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        # TODO: Refuse to turn on a TPM that is not present.
        # TODO: Should we also refuse to turn on a TPM that is already on? In
        # that case, we should not refuse to turn on a TPM that is on, if we
        # have commanded it off and are waiting for that to come into effect.
        with self._write_lock:
            if tpm_number == 0:
                keys = [f"tpm_{i}_on_off" for i in range(SubrackData.TPM_BAY_COUNT + 1)]
                command_name = "turn_on_tpms" if is_turn_on else "turn_off_tpms"
                command_arg = ""
            else:
                keys = [f"tpm_{tpm_number}_on_off"]
                command_name = "turn_on_tpm" if is_turn_on else "turn_off_tpm"
                command_arg = str(tpm_number)

            for key in keys:
                if key in self._commands_to_execute:
                    # There is already a request to turn this TPM off or on,
                    # since the last poll. This request supersedes that previous
                    # request (because it is a request that acts upon the same
                    # TPM, either individually or as a group). So let's abort
                    # the earlier request, and insert this one in its place.
                    (_, _, prior_callback) = self._commands_to_execute[key]
                    if prior_callback is not None:
                        prior_callback(
                            status=TaskStatus.ABORTED,
                            # message="Superseded by later command.",
                        )

            self._commands_to_execute[f"tpm_{tpm_number}_on_off"] = (
                command_name,
                command_arg,
                task_callback,
            )

            off_on = "on" if is_turn_on else "off"

            if task_callback is not None:
                task_callback(status=TaskStatus.QUEUED)

            if tpm_number == 0:
                message = f"TPMs will be turned {off_on} at next poll."
            else:
                message = f"TPM {tpm_number} will be turned {off_on} at next poll."
            return (TaskStatus.QUEUED, message)

    def set_subrack_fan_speed(
        self: SubrackDriver,
        fan_number: int,
        speed: float,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed of a subrack fan.

        :param fan_number: one-based number of the fan to be set.
        :param speed: speed setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        key = f"subrack_fan_{fan_number}_speed"
        with self._write_lock:
            if key in self._commands_to_execute:
                # There is already a request to set the fan speed of this very
                # fan. This request supersedes that previous request, so let's
                # abort the earlier request, and insert this one in its place.
                (_, _, prior_callback) = self._commands_to_execute[key]
                if prior_callback is not None:
                    prior_callback(
                        status=TaskStatus.ABORTED,
                        # message="Superseded by later command.",
                    )
            self._commands_to_execute[key] = (
                "set_subrack_fan_speed",
                f"{fan_number},{speed}",
                task_callback,
            )
        if task_callback is not None:
            task_callback(status=TaskStatus.QUEUED)
        return (
            TaskStatus.QUEUED,
            f"Subrack fan {fan_number} will be set to speed {speed} at next poll.",
        )

    def set_subrack_fan_mode(
        self: SubrackDriver,
        fan_number: int,
        mode: FanMode,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed mode of a subrack fan.

        :param fan_number: one-based number of the fan to be set.
        :param mode: speed mode setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        key = f"subrack_fan_{fan_number}_mode"
        with self._write_lock:
            if key in self._commands_to_execute:
                # There is already a request to set the speed mode of this very
                # fan. This request supersedes that previous request, so let's
                # abort the earlier request, and insert this one in its place.
                (_, _, prior_callback) = self._commands_to_execute[key]
                if prior_callback is not None:
                    prior_callback(
                        status=TaskStatus.ABORTED,
                        # message="Superseded by later command.",
                    )
            self._commands_to_execute[key] = (
                "set_fan_mode",
                f"{fan_number},{mode.value}",
                task_callback,
            )
        if task_callback is not None:
            task_callback(status=TaskStatus.QUEUED)
        return (
            TaskStatus.QUEUED,
            f"Subrack fan {fan_number} will be set to speed mode {mode.AUTO} at next "
            "poll.",
        )

    def set_power_supply_fan_speed(
        self: SubrackDriver,
        fan_number: int,
        speed: float,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Set the target speed of a power supply fan.

        :param fan_number: one-based number of the fan to be set.
        :param speed: speed setting for the fan.
        :param task_callback: callback to be called when the status of
            the command changes

        :return: the task status and a human-readable status message
        """
        key = f"power_supply_fan_{fan_number}_speed"
        with self._write_lock:
            if key in self._commands_to_execute:
                # There is already a request to set the fan speed of this very
                # fan. This request supersedes that previous request, so let's
                # abort the earlier request, and insert this one in its place.
                (_, _, prior_callback) = self._commands_to_execute[key]
                if prior_callback is not None:
                    prior_callback(
                        status=TaskStatus.ABORTED,
                        # message="Superseded by later command.",
                    )
            self._commands_to_execute[key] = (
                "set_power_supply_fan_speed",
                f"{fan_number},{speed}",
                task_callback,
            )
        if task_callback is not None:
            task_callback(status=TaskStatus.QUEUED)
        return (
            TaskStatus.QUEUED,
            f"Power supply fan {fan_number} will be set to speed {speed} at next poll.",
        )

    def write_attribute(self: SubrackDriver, **kwargs: Any) -> None:
        """
        Update subrack attribute value(s).

        This doesn't actually immediately write to the subrack. It only
        stores the details of the requested write where it will be
        picked up by the next iteration of the polling loop.

        :param kwargs: keyword arguments specifying attributes to be
            written along with their corresponding value.
        """
        self.logger.debug(f"Registering attribute writes for next poll: {kwargs}")
        with self._write_lock:
            self._attributes_to_write.update(kwargs)

    def get_request(self: SubrackDriver) -> HttpPollRequest:
        """
        Return the reads, writes and commands to be executed in the next poll.

        :return: reads, writes and commands to be executed in the next
            poll.
        """
        self._tick += 1
        self.logger.debug(f"Constructing request for next poll (tick {self._tick}).")

        poll_request = HttpPollRequest()

        with self._write_lock:
            if self._board_is_busy:
                poll_request.add_command("command_completed")
                return poll_request

            if self._commands_to_execute:
                _, (
                    name,
                    args,
                    self._active_callback,
                ) = self._commands_to_execute.popitem(last=False)

                self.logger.debug(f"Adding command: {name}({args}).")
                poll_request.add_command(name, args)
                if self._active_callback is not None:
                    self._active_callback(status=TaskStatus.IN_PROGRESS)

            for name, value in self._attributes_to_write.items():
                self.logger.debug(f"Adding write request setop: {name}={value}.")
                poll_request.add_setattribute(name, value)
            self._attributes_to_write.clear()

        if self._tick > self._max_tick:
            self.logger.debug(f"Tick {self._tick} >= {self._max_tick}.")
            self.logger.debug("Adding queries.")
            poll_request.add_getattributes(
                "tpm_present",
                "tpm_on_off",
                "backplane_temperatures",
                "board_temperatures",
                "board_current",
                "power_supply_currents",
                "power_supply_fan_speeds",
                "power_supply_powers",
                "power_supply_voltages",
                "subrack_fan_speeds",
                "subrack_fan_speeds_percent",
                "subrack_fan_mode",
                "tpm_currents",
                "tpm_powers",
                # "tpm_temperatures",
                "tpm_voltages",
            )
            self._tick = 0
        self.logger.debug("Returning request for next poll.")
        return poll_request

    def poll(self: SubrackDriver, poll_request: HttpPollRequest) -> HttpPollResponse:
        """
        Poll the hardware.

        Connect to the hardware, write any values that are to be
        written, and then read all values.

        :param poll_request: specification of the reads and writes to be
            performed in this poll.

        :raises ConnectionError: if an error is raised from the lower
            layer

        :return: responses to queries in this poll
        """
        self.logger.info(
            "Poller is initiating next poll. "
            f"{len(poll_request.commands)} commands, "
            f"{len(poll_request.getattributes)} getattributes, "
            f"{len(poll_request.setattributes)} setattributes"
        )
        poll_response = HttpPollResponse()

        for command, args in poll_request.commands:
            command_response = self._client.execute_command(
                command, " ".join(str(arg) for arg in args)
            )
            self.logger.debug(f"Response: {command_response}")
            if command_response["status"] == "ERROR":
                # TODO: [MCCS-1329] Only raise connection errors
                # if the error indicates loss of communication.
                # Otherwise return error details through the query response.
                self.logger.error(
                    f"Command error for {command}: Info {command_response['info']}"
                )
                if self._active_callback is not None:
                    self._active_callback(status=TaskStatus.FAILED)
                    self._active_callback = None
                raise ConnectionError(f"Received ERROR response from command {command}")
            if command_response["status"] == "STARTED":
                self._board_is_busy = True
            elif command_response["status"] == "OK":
                # command has been completed,
                poll_response.add_command_response(
                    command, command_response["retvalue"]
                )
            else:
                if self._active_callback is not None:
                    self._active_callback(status=TaskStatus.FAILED)
                    self._active_callback = None

        for name, value in poll_request.setattributes:
            attribute_response = self._client.set_attribute(name, value)
            if attribute_response["status"] == "ERROR":
                # TODO: [MCCS-1329] Only raise connection errors
                # if the error indicates loss of communication.
                # Otherwise return error details through the query response.
                self.logger.error(
                    f"setattribute error for{name}: Info {attribute_response['info']}"
                )
                raise ConnectionError(
                    f"Received ERROR response from setattribute {name}"
                )
        for attribute in poll_request.getattributes:
            attribute_response = self._client.get_attribute(attribute)
            if attribute_response["status"] == "ERROR":
                # TODO: [MCCS-1329] Only raise connection errors
                # if the error indicates loss of communication.
                # Otherwise return error details through the query response.
                self.logger.error(
                    f"getattribute error for {attribute}: "
                    f"Info {attribute_response['info']}"
                )
                raise ConnectionError(
                    f"Received ERROR response from getattribute {attribute}"
                )
            if attribute_response["status"] == "OK":
                poll_response.add_query_response(attribute, attribute_response["value"])
        return poll_response

    def poll_succeeded(self: SubrackDriver, poll_response: HttpPollResponse) -> None:
        """
        Handle the receipt of new polling values.

        This is a hook called by the poller when values have been read
        during a poll.

        :param poll_response: response to the pool, including any values
            read.
        """
        self.logger.info(
            "Handing results of successful poll. "
            f"{len(poll_response.command_responses)} command responses, "
            f"{len(poll_response.query_responses)} query responses"
        )
        super().poll_succeeded(poll_response)

        # TODO: We should be deciding on the fault state of this device,
        # based on the values returned. For now, we just set it to
        # False.
        fault = False
        self.logger.debug(f"Calculated fault status is {fault}.")

        retvalues = poll_response.command_responses
        if "command_completed" in retvalues and not retvalues["command_completed"]:
            # A command that is asynchronous on the SMB is still running,
            # So there's nothing to do here.
            self.logger.debug("Command still running")
        elif retvalues:
            # The presence of any other retvalues indicate
            # that the active command has completed.
            # This is true also for normal completion of fast commands
            if self._board_is_busy:
                # This means that an attribute  poll is likely overdue and anyway
                # useful, as the hardware status could have been changed. Force it
                self._tick = self._max_tick + 1
            self._board_is_busy = False
            if self._active_callback is not None:
                self.logger.debug("Command completed")
                self._active_callback(
                    status=TaskStatus.COMPLETED,
                    result=(ResultCode.OK, "Command completed."),
                )
            self._active_callback = None

        values = poll_response.query_responses
        self.logger.debug("Pushing updates.")

        self._update_component_state(fault=fault, **values)

    def polling_stopped(self: SubrackDriver) -> None:
        """
        Respond to polling having stopped.

        This is a hook called by the poller when it stops polling.
        """
        self.logger.debug("Polling has stopped.")

        # Set to max here so that if/when polling restarts, an update is
        # requested as soon as possible.
        self._tick = self._max_tick

        self._update_component_state(
            fault=None,
            tpm_present=None,
            tpm_on_off=None,
            backplane_temperatures=None,
            board_temperatures=None,
            board_current=None,
            power_supply_currents=None,
            power_supply_fan_speeds=None,
            power_supply_powers=None,
            power_supply_voltages=None,
            subrack_fan_speeds=None,
            subrack_fan_speeds_percent=None,
            subrack_fan_mode=None,
            tpm_currents=None,
            tpm_powers=None,
            # tpm_temperatures=None,  # Not implemented on SMB
            tpm_voltages=None,
        )

        # Not calling super().polling_stopped() here,
        # because ska-tango-base inappropriately pushes power=UNKNOWN,
        # but polling may have stopped because we learned that power is OFF.
        self._update_communication_state(CommunicationStatus.DISABLED)

    def poll_failed(self: SubrackDriver, exception: Exception) -> None:
        """
        Override parent to set PowerState.UNKNOWN when polling fails.

        This is a bug fix that should be upstreamed to ska-tango-base - see MR
        https://gitlab.com/ska-telescope/ska-tango-base/-/merge_requests/133

        :param exception: the exception that was raised by a recent poll
            attempt.
        """
        self.logger.exception(f"Poll failed: {exception}")
        self._update_component_state(power=PowerState.UNKNOWN, fault=None)
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
