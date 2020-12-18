# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for power management in the MCCS
subsystem, separate from or common to all devices.

Each device will have its own implementation of power management, but
hopefully built on this infrastructure
"""
from ska.low.mccs.hardware import PowerMode
from ska.low.mccs.utils import backoff_connect


class PowerManagerError(ValueError):
    """
    Exception class for a ValueError thrown by the PowerManager, for
    example because the calling class has tried to turn it off when
    already off, or on when already on.
    """

    pass


class PowerManager:
    """
    A simple class for managing power state in a device. Currently
    supports only OFF and ON.

    A device is represented as (optionally) having its own hardware that
    must be powered off and on, and (optionally) a set of subservient
    devices that this device is responsible for turning off and on.
    """

    def __init__(self, hardware, device_fqdns, logger):
        """
        Initialise a new PowerManager object.

        :param hardware: an object encapsulating the device hardware,
            with on() and off() commands
        :type hardware: object
        :param device_fqdns: the FQDNs of the devices that are
            subservient, for power-management purposes, to this manager
        :type device_fqdns: list(str)
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        """
        self._logger = logger
        self._power_mode = PowerMode.OFF

        self.hardware = hardware
        if device_fqdns is None:
            self.devices = None
        else:
            self.devices = [backoff_connect(fqdn, logger) for fqdn in device_fqdns]

    def off(self):
        """
        Turn this device off, by first turning off own hardware, and
        then telling all subservient devices to turn off.

        :return: Whether the command succeeded or not, or None if there
            was nothing to do
        :rtype: bool or None
        """
        if self._power_mode == PowerMode.OFF:
            return
        if self.hardware is not None:
            self.hardware.off()
        if self.devices is not None:
            for device in self.devices:
                device.Off()
        self._power_mode = PowerMode.OFF
        return True

    def standby(self):
        """
        Put this device into low-power standby mode, by first do so to
        its own hardware, and then telling all subservient devices to do
        so.

        :return: Whether the command succeeded or not, or None if there
            was nothing to do
        :rtype: bool or None
        """
        if self._power_mode == PowerMode.STANDBY:
            return
        if self.hardware is not None:
            self.hardware.standby()
        if self.devices is not None:
            for device in self.devices:
                device.Standby()
        self._power_mode = PowerMode.STANDBY
        return True

    def on(self):
        """
        Turn this device on, by first telling all subservient devices to
        turn on, and then turning on own hardware.

        :return: Whether the command succeeded or not, or None if there
            was nothing to do
        :rtype: bool or None
        """
        if self._power_mode == PowerMode.ON:
            return
        if self.devices is not None:
            for device in self.devices:
                device.On()
        if self.hardware is not None:
            self.hardware.on()
        self._power_mode = PowerMode.ON
        return True

    @property
    def power_mode(self):
        """
        Return the power mode of this PowerManager object.

        :return: the power mode of thei PowerManager object
        :rtype: :py:class:`~ska.low.mccs.hardware.PowerMode`
        """
        return self._power_mode
