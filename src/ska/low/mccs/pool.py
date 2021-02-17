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
from ska.base.commands import ResultCode
from ska.low.mccs.utils import backoff_connect


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

    def __init__(self, fqdns, logger):
        """
        Initialise a new DevicePool object.

        :param fqdns: the FQDNs of the devices in this pool
        :type fqdns: list(str)
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        """
        self._logger = logger
        if fqdns is None:
            self._devices = None
        else:
            # TODO: it would save some time if we were connecting
            # asynchronously.
            self._devices = [backoff_connect(fqdn, logger) for fqdn in fqdns]

    def invoke_command(self, command_name, arg=None):
        """
        A generic method for invoking a command on all devices in the
        pool.

        :param command_name: the name of the command to be invoked
        :type command_name: str
        :param arg: optional argument to the command
        :type arg: object
        :return: Whether the command succeeded or not
        :rtype: bool
        """
        if self._devices is not None:
            async_ids = [
                device.command_inout_asynch(command_name, arg)
                for device in self._devices
            ]

            for (async_id, device) in zip(async_ids, self._devices):
                (result_code, _) = device.command_inout_reply(async_id, timeout=0)
                if result_code == ResultCode.FAILED:
                    return False
        return True

    def disable(self):
        """
        Call Disable() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Disable")

    def standby(self):
        """
        Call Standby() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Standby")

    def off(self):
        """
        Call Off() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Off")

    def on(self):
        """
        Call On() on all the devices in this device pool.

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("On")


class DevicePoolSequence(DevicePool):
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

    def __init__(self, pools, logger):
        """
        Initialise a new DevicePoolSequence object.

        :param pools: a sequence of device pools
        :type pools: list(:py:class:`.DevicePool`)
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        """
        self._logger = logger
        self._pools = pools

    def invoke_command(
        self,
        command_name,
        arg=None,
        reverse=False,
    ):
        """
        A generic method for sequential invoking a command on a list of
        device pools.

        :param command_name: the name of the command to be invoked
        :type command_name: str
        :param arg: optional argument to the command
        :type arg: object
        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.)
        :type reverse: bool

        :return: Whether the command succeeded or not
        :rtype: bool
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

    def disable(self, reverse=False):
        """
        Call Disable() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False
        :type reverse: bool

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Disable", reverse=reverse)

    def standby(self, reverse=False):
        """
        Call Standby() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False
        :type reverse: bool

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Standby", reverse=reverse)

    def off(self, reverse=False):
        """
        Call Off() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False
        :type reverse: bool

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("Off", reverse=reverse)

    def on(self, reverse=False):
        """
        Call On() on all the devices in this device pool.

        :param reverse: whether to call pools in reverse sequence. (You
            might turn everything on in a certain order, but need to
            turn them off again in reverse order.) Optional, defaults to
            False
        :type reverse: bool

        :return: Whether the command succeeded or not
        :rtype: bool
        """
        return self.invoke_command("On", reverse=reverse)
