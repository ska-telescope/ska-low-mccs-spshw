# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains pytest fixtures other test setups.

These are common to all ska-low-mccs tests: unit, integration and
functional (BDD).
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, Union

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import EventType


@contextmanager
def tango_event_subscription(
    device_proxy: tango.DeviceProxy,
    attr_name: str,
    event_type: tango.EventType,
    callback: Callable[[tango.EventData], None],
) -> Generator[int, None, None]:
    """
    Context manager to handle Tango event subscription.

    :param device_proxy: The Tango device proxy.
    :param attr_name: The name of the attribute to subscribe to.
    :param event_type: The type of Tango event (e.g., CHANGE_EVENT).
    :param callback: The callback function to handle the event.
    :yield: The subscription ID.
    """
    sub_id = device_proxy.subscribe_event(attr_name, event_type, callback)
    try:
        yield sub_id
    finally:
        device_proxy.unsubscribe_event(sub_id)


def wait_for_completed_command_to_clear_from_queue(
    device_proxy: tango.DeviceProxy,
) -> None:
    """
    Wait for Long Running Commands to clear from queue.

    A completed command is expected to clear after 10 seconds.

    :param device_proxy: device proxy for use in the test.
    """
    # base class clears after 10 seconds
    count = 0
    timeout = 20

    while device_proxy.longRunningCommandsInQueue != ():
        time.sleep(0.5)
        count += 1
        if count == timeout:
            if device_proxy.longRunningCommandsInQueue != ():
                pytest.fail(
                    f"LRCs still in queue after {timeout} seconds: "
                    f"{device_proxy.dev_name()} : "
                    f"{device_proxy.longRunningCommandsInQueue}"
                )


def wait_for_lrc_result(
    device: tango.DeviceProxy, uid: str, expected_result: ResultCode, timeout: float
) -> None:
    """
    Wait for a specific result from a LRC.

    :param device: The tango device to listen to.
    :param uid: The uid used to identify the task under question.
    :param expected_result: The expected ResultCode from execution.
    :param timeout: A time to wait in seconds.

    :raises TimeoutError: When the commands failed to exit the queue in time.
    :raises ValueError: When the Result is incorrect or the result not found.
    """
    count: int = 0
    increment: int = 1

    while device.lrcQueue != () or device.lrcExecuting != ():
        time.sleep(increment)
        count += increment
        if count == timeout:
            raise TimeoutError(
                f"LRCs still running after {timeout} seconds: "
                f"{device.dev_name()} : {device.lrcQueue=} "
                f"{device.lrcExecuting=}"
            )

    for finished_result in device.lrcfinished:
        loaded_result = json.loads(finished_result)
        if loaded_result["uid"] == uid:
            actual_result = ResultCode(loaded_result["result"][0])
            if actual_result == expected_result:
                return
            raise ValueError(
                f"Result for {uid} = {ResultCode(actual_result).name}. "
                f"Expected {ResultCode(expected_result).name}!"
            )
    raise ValueError(f"uid '{uid}' not found in LrcFinished")


def execute_lrc_to_completion(
    device_proxy: tango.DeviceProxy,
    command_name: str,
    command_arguments: Any,
    timeout: int = 5,
) -> None:
    """
    Execute a LRC to completion.

    :param device_proxy: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.
    :param timeout: A timeout to wait for a change event.
        Defaults to 5 seconds.
    :param command_name: the name of the device command under test
    :param command_arguments: argument to the command (optional)
    """
    _lrc_tracker = MockTangoEventCallbackGroup("track_lrc_command", timeout=timeout)

    subscription_id = device_proxy.subscribe_event(
        "longrunningcommandstatus",
        EventType.CHANGE_EVENT,
        _lrc_tracker["track_lrc_command"],
    )
    _lrc_tracker["track_lrc_command"].assert_change_event(Anything)
    [[task_status], [command_id]] = getattr(device_proxy, command_name)(
        command_arguments
    )

    assert task_status == ResultCode.QUEUED
    assert command_name in command_id.split("_")[-1]
    _lrc_tracker["track_lrc_command"].assert_change_event((command_id, "STAGING"))
    _lrc_tracker["track_lrc_command"].assert_change_event((command_id, "QUEUED"))
    _lrc_tracker["track_lrc_command"].assert_change_event((command_id, "IN_PROGRESS"))
    _lrc_tracker["track_lrc_command"].assert_change_event((command_id, "COMPLETED"))
    device_proxy.unsubscribe_event(subscription_id)


def retry_communication(device_proxy: tango.Deviceproxy, timeout: int = 30) -> None:
    """
    Retry communication with the backend.

    NOTE: This is to be used for devices that do not know if the backend is available
    at the time of the call. For example the daq_handler backend gRPC server
    may not be ready when we try to start communicating.
    In this case we will retry connection.

    :param device_proxy: A 'tango.DeviceProxy' to the backend device.
    :param timeout: A max time in seconds before we give up trying
    """
    tick = 2
    if device_proxy.adminMode != AdminMode.ONLINE:
        terminate_time = time.time() + timeout
        while time.time() < terminate_time:
            try:
                device_proxy.adminMode = AdminMode.ONLINE
                break
            except tango.DevFailed:
                print(f"{device_proxy.dev_name()} failed to communicate with backend.")
                time.sleep(tick)
        assert device_proxy.adminMode == AdminMode.ONLINE
    else:
        print(f"Device {device_proxy.dev_name()} is already ONLINE nothing to do.")


class AttributeWaiter:  # pylint: disable=too-few-public-methods
    """A AttributeWaiter class."""

    def __init__(self: AttributeWaiter, timeout: float = 2.0) -> None:
        """
        Initialise a new AttributeWaiter with a timeout.

        :param timeout: the timeout to wait.
        """
        self._timeout = timeout
        self._attr_callback = MockTangoEventCallbackGroup(
            "attr_callback", timeout=timeout
        )

    def wait_for_value(
        self: AttributeWaiter,
        device_proxy: tango.DeviceProxy,
        attr_name: str,
        attr_value: Optional[Union[str, int, bool, list[Any], np.ndarray]] = None,
        lookahead: int = 1,
    ) -> None:
        """
        Wait for the value in alloted time.

        :param device_proxy: the device proxy
        :param attr_name: the name of the attribute.
            use None for Any change event.
        :param attr_value: the value of the attribute
        :param lookahead: the lookahead.
        """
        with tango_event_subscription(
            device_proxy,
            attr_name,
            tango.EventType.CHANGE_EVENT,
            self._attr_callback["attr_callback"],
        ):
            self._attr_callback["attr_callback"].assert_change_event(
                Anything,
            )
            read_attr_value = getattr(device_proxy, attr_name)
            if not self._values_equal(read_attr_value, attr_value):
                self._attr_callback["attr_callback"].assert_change_event(
                    attr_value if attr_value is not None else Anything,
                    lookahead=lookahead,
                    consume_nonmatches=True,
                )

    def _values_equal(
        self: AttributeWaiter, read_value: Any, expected_value: Any
    ) -> bool:
        """
        Return whether values are equal.

        :param read_value: The value read from backend.
        :param expected_value: The value expected from backend.

        :raises ValueError: when the values are not comparable.

        :return: True if the values are equal.
        """
        if isinstance(read_value, np.ndarray):
            if not isinstance(expected_value, np.ndarray):
                raise ValueError(
                    f"Expected np.ndarray for comparison with attribute value, "
                    f"but got {type(expected_value).__name__}"
                )
            return np.array_equal(read_value, expected_value)

        return read_value == expected_value
