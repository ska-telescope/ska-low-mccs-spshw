#
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements dispatch and failure-handling helpers for tango.Group."""

from __future__ import annotations

from typing import Any, Optional

import tango
from tango import DevFailed

# Default client-side timeout, in seconds, for tile group calls. Callers
# set this explicitly on every call via group_write_attribute/group_command,
# rather than relying on whatever a previous call last left it as --
# tango.Group's timeout is a mutable property of the shared group object,
# not a per-call argument, so it does not reset itself.
_DEFAULT_GROUP_TIMEOUT_SECONDS = 1  # TODO: tmp for testing

__all__ = ["raise_for_group_failures", "group_write_attribute", "group_command"]


def raise_for_group_failures(
    action: str,
    replies: list[Any],
) -> list[Any]:
    """
    Raise DevFailed if any reply from a group operation failed.

    Calling this at all is the caller's explicit choice to raise on
    failure; callers that just want to inspect or log failures should
    check ``reply.has_failed()`` themselves instead of calling this.

    :param action: Human-readable description of the operation that was
        attempted, for the error message, e.g. ``"write
        channeliserRounding"`` or ``"run SetLmcDownload"``.
    :param replies: Group replies, one per device.

    :return: ``replies``, unchanged.

    :raises DevFailed: if one or more replies failed. The exception's
        error stack contains one ``tango.DevError`` per failed device.
    """
    failures = [reply for reply in replies if reply.has_failed()]

    if not failures:
        return replies

    errors: list[tango.DevError] = []

    for reply in failures:
        err_stack = reply.get_err_stack()

        if err_stack:
            errors.extend(err_stack)
            continue

        error = tango.DevError()
        error.reason = "GroupOperationFailed"
        error.desc = (
            f"Failed to {action} on {reply.dev_name()}: unknown error. "
            "No error stack was provided. This may indicate a PyTango bug."
        )
        error.origin = "raise_for_group_failures"
        error.severity = tango.ErrSeverity.ERR
        errors.append(error)

    raise DevFailed(*errors)


def group_write_attribute(
    group: Any,
    attr_name: str,
    value: Any,
    *,
    multi: bool = False,
    timeout: float = _DEFAULT_GROUP_TIMEOUT_SECONDS,
) -> list[Any]:
    """
    Write an attribute to every device in ``group``, in parallel.

    This should always attempt execution on every device in the group.
    It is purely a dispatcher: it does not inspect the replies for
    failures. Callers that care whether the write succeeded should pass
    the returned replies to :py:func:`raise_for_group_failures`, or
    inspect ``reply.has_failed()`` themselves.

    :param group: the ``tango.Group`` (or compatible test double) to
        dispatch the write on.
    :param attr_name: name of the attribute to write.
    :param value: value to broadcast to every device, or (if ``multi``)
        a list of one value per device, ordered as ``group``'s device
        list.
    :param multi: whether ``value`` is a per-device list rather than a
        single value to broadcast to every device.
    :param timeout: client-side timeout, in seconds, defaulting to
        ``_DEFAULT_GROUP_TIMEOUT_SECONDS``.

    :return: one ``GroupReply`` per device, in the same order as
        ``group``'s device list.
    """
    group.set_timeout_millis(timeout * 1000)
    return group.write_attribute(attr_name, value, multi=multi)


def group_command(
    group: Any,
    command_name: str,
    arg: Any = None,
    *,
    multi: bool = False,
    arg_type: Optional[tango.CmdArgType] = None,
    timeout: float = _DEFAULT_GROUP_TIMEOUT_SECONDS,
) -> list[Any]:
    """
    Run a command on every device in ``group``, in parallel.

    Purely a dispatcher: it does not inspect the replies for failures.
    Callers that care whether the command succeeded should pass the
    returned replies to :py:func:`raise_for_group_failures`, or inspect
    ``reply.has_failed()`` themselves.

    :param group: the ``tango.Group`` (or compatible test double) to
        dispatch the command on.
    :param command_name: name of the command to run.
    :param arg: single argument to broadcast to every device, or (if
        ``multi``) a list of one argument per device, ordered as
        ``group``'s device list.
    :param multi: whether ``arg`` is a per-device list rather than a
        single value to broadcast to every device.
    :param arg_type: the Tango argument type of ``command_name``'s
        input, required when ``multi`` is True (used to build the
        per-device ``tango.DeviceDataList``); ignored otherwise.
    :param timeout: client-side timeout, in seconds, defaulting to
        ``_DEFAULT_GROUP_TIMEOUT_SECONDS``.

    :return: one ``GroupCmdReply`` per device, in the same order as
        ``group``'s device list.

    :raises ValueError: if ``multi`` is True and ``arg_type`` is None.
    """
    group.set_timeout_millis(timeout * 1000)

    if not multi:
        return group.command_inout(command_name, arg)

    if arg_type is None:
        raise ValueError("arg_type is required when multi is True")

    device_data_list = tango.DeviceDataList()

    for device_arg in arg:
        device_data = tango.DeviceData()
        device_data.insert(arg_type, device_arg)
        device_data_list.append(device_data)

    return group.command_inout(command_name, device_data_list)
