# -*- coding: utf-8 -*-
#
# This file is part of the ska.low.mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for power management in the MCCS
subsystem, separate from or common to all devices.

Each device will have its own implementation of power management, but
hopefully built on this infrastructure
"""


class PowerManagerError(ValueError):
    """
    Exception class for a ValueError thrown by the PowerManager, for
    example because the calling class has tried to turn it off when
    already off, or on when already on
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

    def __init__(self, hardware, devices):
        """
        Initialise a new PowerManager object

        :param hardware: an object encapsulating the device hardware,
            with on() and off() commands
        :type hardware: object
        :param devices: the devices that are subservient,
            for power-management purposes, to this manager
        :type devices: a collection of DeviceProxy
        """
        self._is_on = False

        self.hardware = hardware
        self.devices = devices

    def off(self):
        """
        Turn this device off, by first turning off own hardware, and
        then telling all subservient devices to turn off

        :raises PowerManagerError: if trying to turn off when already
            off
        :return: Whether the command succeeded or not
        :rtype: boolean
        """
        if not self._is_on:
            raise PowerManagerError("Off() called when already Off")
        if self.hardware is not None:
            self.hardware.Off()
        if self.devices is not None:
            for device in self.devices:
                device.Off()
        self._is_on = False
        return True

    def on(self):
        """
        Turn this device on, by first telling all subservient devices to
        turn on, and then turning on own hardware

        :raises PowerManagerError: if trying to turn on when already
            on
        :return: Whether the command succeeded or not
        :rtype: boolean
        """
        if self._is_on:
            raise PowerManagerError("On() called when already On")
        if self.devices is not None:
            for device in self.devices:
                device.On()
        if self.hardware is not None:
            self.hardware.On()
        self._is_on = True
        return True

    def is_on(self):
        """
        Whether this PowerManager object is currently on or not

        :return: whether currently on
        :rtype: bool
        """
        return self._is_on
