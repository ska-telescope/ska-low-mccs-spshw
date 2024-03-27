# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
# This is a temporary file until we release ska-low-mccs-common
"""This module implements a MccsCommandProxy."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import tango
from ska_control_model import ResultCode, TaskStatus
from ska_tango_testing.context import DeviceProxy


class LRCResultObserverThread(threading.Thread):
    """
    A Threading class to observer LRC result.

    LRC -> LongRunningCommand

    This will monitor for change events for LRCs on remote devices
    the join function has been overriden to reuturn the LRC result.
    """

    def __init__(
        self: LRCResultObserverThread,
        proxy: tango.DeviceProxy,
        command_id: str,
        timeout: int,
        logger: logging.Logger,
    ) -> None:
        """
        Initialise a new instance.

        :param proxy: the `tango.DeviceProxy` to subscribe to LRC result.
        :param command_id: the unique id of the command being observed on proxy.
        :param timeout: The max time to wait for a LRC result.
        :param logger: for information

        """
        super().__init__()
        self._stop_event = threading.Event()
        self.logger = logger
        self.proxy = proxy
        self.command_id = command_id
        self._timeout = timeout
        self._lrc_result: tuple[ResultCode, str] | None = None

    def stop(self) -> None:
        """Stop the thread."""
        self._stop_event.set()

    def on_change(self: LRCResultObserverThread, change_event: tango.EventData) -> None:
        """
        Handle LRC change events.

        :param change_event: the `tango.EventData` passed on change.
        """
        if self.is_lrc_valid(change_event):
            result_code, message = json.loads(change_event.attr_value.value[1])
            self.logger.info(
                f"LRC for {self.proxy.dev_name()} changed to "
                f"{ResultCode(result_code).name} : {message}"
            )
            self._lrc_result = (result_code, message)

            self.stop()

    def is_lrc_valid(
        self: LRCResultObserverThread, change_event: tango.EventData
    ) -> bool:
        """
        Validate a LRC change_event.

        :param change_event: the `tango.EventData` passed on change.

        :return: True is valid.
        """
        try:
            command_id = change_event.attr_value.value[0]
            result_code, message = json.loads(change_event.attr_value.value[1])
        except Exception:  # pylint: disable=broad-except
            return False
        if command_id != self.command_id:
            # The wrong command_id, ignore
            return False
        if not isinstance(command_id, str):
            self.logger.error(
                f"LRC not valid, Command_id '{command_id}' is not a string"
            )
            return False
        if not isinstance(message, str):
            self.logger.error(f"LRC not valid, message '{message}' is not a string")
            return False
        try:
            ResultCode(result_code)
        except ValueError:
            self.logger.error("LRC not valid, not a result code")
            return False
        return True

    def run(self: LRCResultObserverThread) -> None:
        """
        Run the thread.

        subscribe to the `longRunningCommandResult` change event.
        If we get no response in timeout period close thread and
        unsubscribe.
        """
        result_subscription_id = self.proxy.subscribe_event(
            "longRunningCommandResult",
            tango.EventType.CHANGE_EVENT,
            self.on_change,
        )
        self.logger.error(
            f"Waiting for LRC result for {self.proxy.dev_name()}/{self.command_id} ..."
        )
        # Wait for a callback
        self._stop_event.wait(timeout=self._timeout)

        self.proxy.unsubscribe_event(result_subscription_id)

    def join(  # type: ignore
        self: LRCResultObserverThread, timeout: int = 40
    ) -> tuple[ResultCode, str] | None:
        """
        Join the thread.

        NOTE: This is overriding the theading.Threading.join, and violating the
        `Liskov substitution principle`

        :param timeout: The max time to wait for a LRC result.

        :return: the long running command result
        """
        super().join(timeout=timeout)
        return self._lrc_result


class MccsCommandProxy:
    """
    A command proxy that understands the ska-low-mccs command variants.

    It hides the messy details of the device interface
    through which commands are monitored.

    The idea is that one can invoke a command on a device,
    and monitor its progress,
    simply by invoking a command on a proxy,
    and passing it a task_callback.
    The command proxy interacts with the device interface,
    hiding its details from the user,
    and calls the task_callback as appropriate.
    """

    def __init__(
        self: MccsCommandProxy,
        device_name: str,
        command_name: str,
        logger: logging.Logger,
        device_proxy_factory: Callable[[str], tango.DeviceProxy] | None = None,
    ) -> None:
        """
        Initialise a new instance.

        :param device_name: name of the device on which to invoke the command
        :param command_name: name of the command to invoke
        :param logger: a logger for this object to use
        :param device_proxy_factory: optional override for device proxy factory
        """
        self._device_name = device_name
        self._command_name = command_name
        self._logger = logger
        self._device_proxy_factory = device_proxy_factory or DeviceProxy

    def name(self) -> str:
        """
        Return the command proxy name.

        :return: the unique name of this command proxy
        """
        return self._device_name + self._command_name

    def __call__(  # noqa: C901
        self: MccsCommandProxy,
        arg: Any = None,
        *,
        task_callback: Callable | None = None,
        run_in_thread: bool = True,
        timeout: int = 40,
    ) -> tuple[ResultCode | TaskStatus, str]:
        """
        Manage execution of the command.

        If the command returns a DevVarLongStringArray,
        it is assumed to return a standard response of the form
        `[[ResultCode], ["human-readable message"]]`:

        * If that `ResultCode` is `ResultCode.QUEUED` or `ResultCode.STARTED`,
          the command is taken to be a long-running command,
          and its progress and completion is monitored via the
          `longRunningCommandProgress`, `longRunningCommandStatus` and
          `longRunningCommandResult` attributes.
        * Otherwise, the command is either a short-running command,
          or a long-running command that finished immediately
          (e.g. immediate failure).

        If the command returns anything other than a DevVarLongStringArray,
        it is assumed to be a fast command that has run to completion
        and yielded an immediate result.

        :param arg: argument to the name, or None if no argument
        :param task_callback: callback to update with task status
        :param run_in_thread: True if you want this command to run in a
            thread
        :param timeout: The maximum time to wait for a response.

        :return: the task status and a human-readable status message
        """
        # This lock prevents an unlikely but possible race condition
        # in which the response callback has already been called
        # before this method returns QUEUED.
        lock = threading.RLock()

        def _try_task_callback(**kwargs: Any) -> None:
            if task_callback is not None:
                try:
                    with lock:
                        task_callback(**kwargs)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.error(
                        f"Could not invoke task callback: exception {repr(e)}."
                    )

        def _execute_command() -> tuple[ResultCode, str]:
            try:
                # throwaway proxy so that we can isolate our event subscriptions
                proxy = self._device_proxy_factory(self._device_name)
                try:
                    args = [] if arg is None else [arg]
                    response = proxy.command_inout(self._command_name, *args)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.error(
                        f"Error invoking command on device: exception {repr(e)}."
                    )
                    _try_task_callback(status=TaskStatus.FAILED)
                    return (
                        ResultCode.FAILED,
                        f"Error invoking command on device: exception {repr(e)}.",
                    )

                try:
                    [task_status], [command_id] = response
                except:  # pylint: disable=bare-except  # noqa: E722
                    self._logger.debug(
                        "Response is not a (task_status, message) tuple."
                        "Command is interpreted as completed."
                    )
                    _try_task_callback(status=TaskStatus.COMPLETED, result=response)
                    return (
                        ResultCode.OK,
                        response,
                    )

                # respond depending upon the TaskStatus.
                # Return immediatly for task endpoints
                # i.e COMPLETED, FAILED, REJECTED, ABORTED, NOT_FOUND
                # Continue if not STAGING, QUEUED, IN_PROGRESS
                result = None
                match task_status:
                    case TaskStatus.COMPLETED:
                        result = (ResultCode.OK, command_id)
                    case TaskStatus.FAILED:
                        result = (ResultCode.FAILED, command_id)
                    case TaskStatus.ABORTED:
                        result = (ResultCode.ABORTED, command_id)
                    case TaskStatus.REJECTED:
                        result = (ResultCode.REJECTED, command_id)
                    case TaskStatus.NOT_FOUND:
                        result = (ResultCode.UNKNOWN, command_id)
                    case _:
                        _try_task_callback(status=TaskStatus(task_status))
                # If command already has a result call task_callback and return
                # result of command.
                if result is not None:
                    _try_task_callback(status=TaskStatus(task_status), result=result)
                    return result

                # Start the observer thread for the LRCResult
                thread = LRCResultObserverThread(
                    proxy, command_id, timeout, self._logger
                )
                thread.start()

                # wait up to timeout.
                lrc_result = thread.join(timeout=timeout)

                if lrc_result is None:
                    _try_task_callback(
                        status=TaskStatus.COMPLETED,
                        result=(
                            ResultCode.UNKNOWN,
                            "Command failed to complete in time",
                        ),
                    )
                    return (
                        ResultCode.FAILED,
                        f"Command failed to complete in time {timeout}",
                    )
                _try_task_callback(status=TaskStatus.COMPLETED, result=lrc_result)
                return lrc_result

            # Catch and report everything because otherwise the thread crashes silently
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error(f"Failed to track LRC on device {repr(e)}")
                _try_task_callback(status=TaskStatus.FAILED)
                return (ResultCode.FAILED, f"Exception raised : {e}")

        with lock:
            if not run_in_thread:
                self._logger.error("Command blocking on LRC result....")
                return _execute_command()

            self._logger.error("Command executed in thread....")
            thread = threading.Thread(target=_execute_command)
            thread.start()

            _try_task_callback(status=TaskStatus.QUEUED)

            return (
                TaskStatus.QUEUED,
                "Task command has been invoked on the remote device.",
            )
