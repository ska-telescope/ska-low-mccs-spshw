# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for management of device pools.

It is useful for devices that manage a pool of subservient devices.
"""
from ska.base.commands import ResultCode
from ska.low.mccs.utils import backoff_connect


class DevicePoolManager:
    """
    A simple base class for managing a static pool of devices.

    At this point is only supports the SKABaseDevice commands Disable(),
    Off(), Standby() and On(). And it is only capable of supporting
    commands that return OK or FAILED, not STARTED or QUEUED.
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
            for device in self._devices:
                (result_code, _) = device.command_inout(command_name, arg)
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
