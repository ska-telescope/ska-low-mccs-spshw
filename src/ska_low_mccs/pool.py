# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for management of device pools.

It is useful for devices that handle commands by passing them to a pool
of subservient devices.

:todo: This is quite a basic class that allows for sending a command to
    all devices in a pool at once, and for sending a command to pools in
    sequence. In the long run, this might need to evolve into a class
    that send commands in a sequence that complies with a complex
    dependency graph.
"""

from __future__ import annotations  # allow forward references in type hints

import functools
import json
import logging
from typing import Union, Any

from ska_tango_base.commands import ResultCode
from ska_low_mccs.device_proxy import MccsDeviceProxy


class DevicePool:
    """
    A class for managing a static pool of devices.

    It allows execution of a command on all members of the pool at the
    same time. i.e. asynchronously.

    At this point it only explicitly supports the SKABaseDevice commands
    Disable(), Off(), Standby() and On(), but there is also a generic
    invoke_command method that allows execution of an arbitrary method
    by name.

    It is only capable of supporting commands that return OK or FAILED,
    not STARTED or QUEUED.
    """

    def __init__(
        self: DevicePool, fqdns: list[str], logger: logging.Logger, connect: bool = True
    ) -> None:
        """
        Initialise a new DevicePool object.

        :param fqdns: the FQDNs of the devices in this pool
        :param logger: the logger to be used by this object.
        :param connect: whether to establish connections immediately.
            Defaults to True. If False, the connections may be
            established by calling the :py:meth:`.connect` method, or by
            calling one of the supported commands.
        """
        self._fqdns = fqdns or []
        self._logger = logger
        self._devices: list[MccsDeviceProxy] = []
        self._responses: dict[str, bool] = {}
        self._results: list[ResultCode] = []

        if connect:
            self.connect()

    def connect(self: DevicePool) -> None:
        """Connect to the devices in the pool."""
        if not self._devices:
            # TODO: it would save some time if we were connecting asynchronously.
            self._devices = [
                MccsDeviceProxy(fqdn, self._logger) for fqdn in self._fqdns
            ]

    # TODO: Deprecate this call (once converted to messaging system)
    def invoke_command(self: DevicePool, command_name: str, arg: Any = None) -> bool:
        """
        A generic method for invoking a command on all devices in the pool.

        :param command_name: the name of the command to be invoked
        :param arg: optional argument to the command

        :return: Whether the command succeeded or not
        """
        if not self._devices:
            self.connect()

        async_ids = []
        for device in self._devices:
            asyncid = device.command_inout_asynch(command_name, arg)
            async_ids.append(asyncid)

        for (async_id, device) in zip(async_ids, self._devices):
            result = device.command_inout_reply(async_id, timeout=0)
            # TODO: added this to prevent TypeError: cannot unpack non-iterable Mock object
            # review when message queue implementation is complete
            if isinstance(result, list):
                (result_code, _) = result
                if result_code == ResultCode.FAILED:
                    return False

        return True

    def invoke_command_with_callback(
        self: DevicePool, command_name: str, fqdn: str, callback: str
    ) -> bool:
        """
        A generic method to send a message to the pool of devices.

        :param command_name: the name of the command to be invoked
        :param fqdn: FQDN to return message to
        :param callback: Callback command to call reply to

        :return: Whether the messages were sent or not
        """
        self._logger.debug(f"pool.py:invoke_command_with_callback({command_name})")
        if len(self._responses):
            self._logger.error(f"{len(self._responses)} pool messages in progress")
            return False

        if not self._devices:
            self.connect()

        self._results = []

        # Send a message to all of the registered devices in the pool
        for device in self._devices:
            self._logger.debug(f"cmd={command_name}, rtnfqdn={fqdn}, cb={callback}")

            # TODO: Need to expand this to include arguments passed to commands...
            args = {"respond_to_fqdn": fqdn, "callback": callback}
            json_string = json.dumps(args)
            self._logger.debug(f"Calling {device}:{command_name}({json_string})")
            [result_code], [status, message_uid] = device.command_inout(
                command_name, json_string
            )
            self._logger.debug(f"Pool({result_code}:{message_uid}:{status})")

            if result_code == ResultCode.FAILED:
                self._logger.debug(f"Early exit! uid={message_uid}")
                return False

            if result_code == ResultCode.QUEUED:
                self._logger.debug(f"Added response {message_uid}")
                self._responses[message_uid] = False
            else:
                self._logger.debug(f"Response NOT ADDED! rc={result_code}")

        return True

    def pool_stats(self: DevicePool) -> int:
        """
        Statistics on which pool command replies are pending.

        :return: Number of pending responses for this pool
        """
        return len(self._responses)

    def callback(self: DevicePool, argin: str) -> tuple[bool, ResultCode]:
        """
        A generic method to send a message to the pool of devices.

        :param argin: json string with the result of the command

        :return: Whether all of the messages were completed, return_code and message
        """
        # check that each received message is on message_object and mark off as recevied
        kwargs = json.loads(argin)
        message_object = kwargs.get("message_object")
        result_code = kwargs.get("result_code")
        self._results.append(result_code)
        key = message_object.get("message_uid")
        self._logger.debug(f"Got reply key {key}")
        if key in self._responses:
            self._responses[key] = True
        # else OK, this reply was not for this pool - exit as normal below

        # When all callbacks have been received, derive the result code
        if self._results.count(ResultCode.OK) == len(self._results):
            result_code = ResultCode.OK
        else:
            result_code = ResultCode.FAILED

        # and return to the caller (the device)
        if all(self._responses.values()):
            self._responses.clear()
            return (True, result_code)
        else:
            # We have some responses pending...
            return (False, result_code)

    def disable(self: DevicePool) -> bool:
        """
        Call Disable() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("Disable")

    def standby(self: DevicePool) -> bool:
        """
        Call Standby() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("Standby")

    def off(self: DevicePool) -> bool:
        """
        Call Off() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("Off")

    def on(self: DevicePool) -> bool:
        """
        Call On() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("On")

    def add_change_event_callback(self, attribute_name, callback):
        """
        Register a callback for change events being pushed by devices in this pool.

        :param attribute_name: the name of the attribute for which
            change events are subscribed.
        :param callback: the function to be called when a change event
            arrives.
        """
        if self._devices is None:
            self.connect()

        for device in self._devices:
            device.add_change_event_callback(
                attribute_name, functools.partial(callback, device.dev_name())
            )


class DevicePoolSequence:
    """
    A class for managing a sequence of device pools.

    It allows execution of a command on each pool in sequence.

    For example, if we need to turn subracks on before we can turn tiles
    on, then we can

    - create a pool of subracks
    - create a pool of tiles
    - pass these two pools to this class

    We can then call the on() command for this class, and it will

    - call the on() command for all subracks at the same time
    - wait for them to complete
    - call the on() command for all tiles at the same time.

    At this point it only explicitly supports the SKABaseDevice commands
    Disable(), Off(), Standby() and On(), but there is also a generic
    invoke_command method that allows execution of an arbitrary method
    by name.

    It is only capable of supporting commands that return OK or FAILED,
    not STARTED or QUEUED.
    """

    def __init__(
        self: DevicePoolSequence,
        pools: list[DevicePool],
        logger: logging.Logger,
        connect: bool = True,
    ) -> None:
        """
        Initialise a new DevicePoolSequence object.

        :param pools: a sequence of device pools
        :param logger: the logger to be used by this object.
        :param connect: whether to establish connections immediately.
            Defaults to True. If False, the connections may be
            established by calling the :py:meth:`.connect` method, or by
            calling one of the supported commands.
        """
        self._logger = logger
        self._pools = pools

        if connect:
            self.connect()

    def connect(self: DevicePoolSequence) -> None:
        """Connect to the devices in the pools."""
        for pool in self._pools:
            pool.connect()

    def invoke_command(
        self: DevicePoolSequence,
        command_name: str,
        arg: Any = None,
        reverse: bool = False,
    ) -> Union[bool, None]:
        """
        A generic method for sequential invoking a command on a list of device pools.

        :param command_name: the name of the command to be invoked
        :param arg: optional argument to the command
        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.)

        :return: Whether the command succeeded or not
        """
        did_nothing = True

        pools = reversed(self._pools) if reverse else self._pools
        for pool in pools:
            success = pool.invoke_command(command_name, arg)
            if success is False:
                return False
            if success is True:
                did_nothing = False
        else:
            return None if did_nothing else True

    def invoke_command_with_callback(
        self: DevicePoolSequence,
        command_name: str,
        fqdn: str,
        callback: str,
        reverse: bool = False,
    ) -> bool:
        """
        A generic method for sequential invoking a command on a list of device pools.

        :param command_name: the name of the command to be invoked
        :param fqdn: FQDN to return message to
        :param callback: Callback command to call reply to
        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.)

        :return: Whether the command succeeded or not
        """
        all_ok = True

        pools = reversed(self._pools) if reverse else self._pools
        for pool in pools:
            success = pool.invoke_command_with_callback(
                command_name=command_name, fqdn=fqdn, callback=callback
            )
            if success is False:
                all_ok = False
        return all_ok

    def disable(self: DevicePoolSequence, reverse: bool = False) -> Union[bool, None]:
        """
        Call Disable() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("Disable", reverse=reverse)

    def standby(self: DevicePoolSequence, reverse: bool = False) -> Union[bool, None]:
        """
        Call Standby() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False

        :return: Whether the command succeeded or not
        """
        return self.invoke_command("Standby", reverse=reverse)

    def off(self: DevicePoolSequence, reverse: bool = False) -> Union[bool, None]:
        """
        Call Off() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False

        :return: Whether the command succeeded or not
        """
        args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(args)
        return self.invoke_command(command_name="Off", arg=json_string, reverse=reverse)

    def on(self: DevicePoolSequence, reverse: bool = False) -> Union[bool, None]:
        """
        Call On() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False

        :return: Whether the command succeeded or not
        """
        args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(args)
        return self.invoke_command(command_name="On", arg=json_string, reverse=reverse)

    def pool_stats(self: DevicePoolSequence) -> str:
        """
        Stats on the pool.

        :return: The pool stats
        """
        status = ""
        for pool in self._pools:
            status += f"{str(pool.pool_stats())} "
        return status

    def callback(self: DevicePoolSequence, argin: str) -> tuple[bool, ResultCode, str]:
        """
        We need to check all pools have received their callbacks whenever we get a
        callback message.

        :param argin: results from executed command

        :return: A tuple containing a flag indicating whether pools are complete,
            an overall return code and an information status
        """
        responses_pending_message = "Message responses pending"
        all_responses_received_message = "All message responses received"

        pools_complete = 0
        results = []
        for pool in self._pools:
            (pool_done, result_code) = pool.callback(argin=argin)
            if pool_done:
                pools_complete += 1
            results.append(result_code)

        if results.count(ResultCode.OK) == len(results):
            result_code = ResultCode.OK
        else:
            result_code = ResultCode.FAILED

        if pools_complete == len(self._pools):
            return (True, result_code, all_responses_received_message)
        return (False, result_code, responses_pending_message)
