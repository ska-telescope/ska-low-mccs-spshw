# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements classes for MCCS hardware for which the power
mode can be managed; i.e. we can turn it on and off.
"""
__all__ = ["OnOffHardwareDriver", "OnOffHardwareManager", "OnOffHardwareSimulator"]


from ska.low.mccs.hardware import HardwareDriver, HardwareManager, HardwareSimulator


class OnOffHardwareDriver(HardwareDriver):
    """
    A mixin that adds on() and off() commands to the abstract
    :py:class:`.HardwareDriver` class.
    """

    def on(self):
        """
        Turn me on.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def off(self):
        """
        Turn the hardware off.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    @property
    def is_on(self):
        """
        Return whether I am on or off.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def _check_on(self, error=None):
        """
        Helper method to check that the hardware is turned on, and raise
        a suitable error if it is not.

        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ValueError: if the hardware is turned off
        """
        self._check_connected()
        if not self.is_on:
            raise ValueError(error or "Hardware is turned off")


class OnOffHardwareSimulator(HardwareSimulator, OnOffHardwareDriver):
    """
    Adds on() and off() commands to the :py:class:`.HardwareSimulator`
    base class.
    """

    def __init__(self, fail_connect=False, is_on=False):
        """
        Initialise a new OnOffHardwareSimulator instance.

        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        :param is_on: whether this simulator should simulate connecting
            to hardware that was already turned on
        :type is_on: bool
        """
        super().__init__(fail_connect)
        self._is_on = is_on

    def off(self):
        """
        Turn me off.
        """
        self._check_connected()
        self._is_on = False

    def on(self):
        """
        Turn me on.
        """
        self._check_connected()
        self._is_on = True

    @property
    def is_on(self):
        """
        Return whether I am on or off.

        :return: whether I am on or off
        :rtype: bool
        """
        self._check_connected()
        return self._is_on


class OnOffHardwareManager(HardwareManager):
    """
    A :py:class:`.HardwareManager` mixin that adds on() and off()
    commands.
    """

    def off(self):
        """
        Turn the hardware off.

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if not self._factory.hardware.is_on:
            return
        self._factory.hardware.off()

        self._update_health()
        return not self._factory.hardware.is_on

    def on(self):
        """
        Turn the hardware on.

        :return: whether successful, or None if there was nothing to do.
        :rtype: bool or None
        """
        if self._factory.hardware.is_on:
            return
        self._factory.hardware.on()

        self._update_health()
        return self._factory.hardware.is_on

    @property
    def is_on(self):
        """
        Whether the hardware is on or not.

        :return: whether the hardware is on or not
        :rtype: bool
        """
        return self._factory.hardware.is_on
