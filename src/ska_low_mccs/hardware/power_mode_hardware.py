# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements MCCS hardware for which the power mode can be managed."""
import enum

from ska_low_mccs.hardware import HardwareDriver, HardwareManager, HardwareSimulator


__all__ = [
    "BasePowerModeHardwareDriver",
    "BasePowerModeHardwareSimulator",
    "BasePowerModeHardwareManager",
    "OnOffHardwareDriver",
    "OnOffHardwareManager",
    "OnOffHardwareSimulator",
    "OnStandbyHardwareDriver",
    "OnStandbyHardwareSimulator",
    "OnStandbyHardwareManager",
    "OnStandbyOffHardwareDriver",
    "OnStandbyOffHardwareSimulator",
    "OnStandbyOffHardwareManager",
    "PowerMode",
]


class PowerMode(enum.IntEnum):
    """Enumerated type for hardware power mode."""

    UNKNOWN = 0
    """
    The power mode of the hardware is unknown.
    """

    OFF = 1
    """
    The hardware is turned off.
    """

    STANDBY = 2
    """
    The hardware is in a low-power standby mode.
    """

    ON = 3
    """
    The hardware is turned on. This does not imply that the hardware is
    currently in use.
    """


class BasePowerModeHardwareDriver(HardwareDriver):
    """
    A mixin that adds an abstract :py:meth:`.on` method and an abstract
    :py:attr:`.power_mode` property to the abstract
    :py:class:`.HardwareDriver` class.
    """

    def on(self):
        """
        Turn me on.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    @property
    def power_mode(self):
        """
        Return the power mode of the hardware.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def check_power_mode(self, power_mode, error=None):
        """
        Helper method to check that the hardware power mode is what it is expected to
        be, and raise a suitable error if it is not.

        :param power_mode: the expected power mode
        :type power_mode: :py:class:`PowerMode`
        :param error: the error message for the exception to be raise if
            not connected
        :type error: str

        :raises ValueError: if the power mode is not what it is expected
            to be
        """
        self.check_connected()
        if self.power_mode != power_mode:
            raise ValueError(error or f"Hardware is not {power_mode.name}.")


class OnOffHardwareDriver(BasePowerModeHardwareDriver):
    """A mixin that adds an abstract :py:meth:`.off` method to a hardware driver."""

    def off(self):
        """
        Turn the hardware off.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError


class OnStandbyHardwareDriver(BasePowerModeHardwareDriver):
    """A mixin that adds an abstract :py:meth:`.standby` method to a hardware driver."""

    def standby(self):
        """
        Put the hardware into low-power standby mode.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError


class OnStandbyOffHardwareDriver(OnOffHardwareDriver, OnStandbyHardwareDriver):
    """
    A syntactic-sugar mixin that combines the
    :py:class:`OnOffHardwareDriver` mixin with the
    :py:class:`OnStandbyHardwareDriver` mixin, thus yielding a mixin
    that adds both :py:meth:`~.OnOffHardwareDriver.off` and
    :py:meth:`~.OnStandbyHardwareDriver.standby` abstract methods to a
    hardware driver.
    """

    pass


class BasePowerModeHardwareSimulator(HardwareSimulator, BasePowerModeHardwareDriver):
    """
    A mixin that add an :py:meth:`.on` method and :py:attr:`.power_mode` property to a
    :py:class:`.HardwareSimulator`.
    """

    def __init__(
        self, is_connectible=True, fail_connect=False, power_mode=PowerMode.UNKNOWN
    ):
        """
        Initialise a new instance.

        :param is_connectible: whether it ought to be possible,
            initially, to connect to the hardware being simulated. For
            example, if the hardware we are simulating is not yet
            powered on, then we would not expect to be able to connect
            to it, and failure to do so would not be an error.
        :type is_connectible: bool
        :param fail_connect: whether this simulator should initially
            simulate failure to connect to the hardware
        :type fail_connect: bool
        :param power_mode: the initial power_mode of the simulated
            hardware. For example, if set to ON, then
            this simulator will simulate connecting to hardware and
            finding it to be already powered on.
        :type power_mode: :py:class:`.PowerMode`
        """
        super().__init__(is_connectible, fail_connect)
        self._power_mode = power_mode

    def on(self):
        """Turn me on."""
        self.check_connected()
        self._power_mode = PowerMode.ON

    @property
    def power_mode(self):
        """
        Return the power mode of the simulated hardware.

        :return: the power mode of the simulated hardware
        :rtype: bool
        """
        self.check_connected()
        return self._power_mode


class OnOffHardwareSimulator(BasePowerModeHardwareSimulator, OnOffHardwareDriver):
    """
    A mixin that provides a software-simulation implementation of the
    :py:meth:`~.OnOffHardwareDriver.off` method.
    """

    def off(self):
        """Turn me off."""
        self.check_connected()
        self._power_mode = PowerMode.OFF


class OnStandbyHardwareSimulator(
    BasePowerModeHardwareSimulator, OnStandbyHardwareDriver
):
    """
    A mixin that provides a software-simulation implementation of the
    :py:meth:`~.OnStandbyHardwareDriver.standby`
    method.
    """

    def standby(self):
        """Put me into low-power standby mode."""
        self.check_connected()
        self._power_mode = PowerMode.STANDBY


class OnStandbyOffHardwareSimulator(
    OnOffHardwareSimulator, OnStandbyHardwareSimulator, OnStandbyOffHardwareDriver
):
    """
    A syntactic-sugar mixin that combines the
    :py:class:`.OnOffHardwareSimulator` mixin with the
    :py:class:`.OnStandbyHardwareSimulator` mixin, thus yielding a mixin
    that implements both :py:meth:`~.OnStandbyHardwareDriver.standby`
    and :py:meth:`~.OnOffHardwareDriver.off` methods of the
    :py:class:`~.OnStandbyOffHardwareDriver` class.
    """

    pass


class BasePowerModeHardwareManager(HardwareManager):
    """
    A base class for :py:class:`.HardwareManager` mixins.

    Add an
    :py:meth:`.on` method and a :py:attr:`.power_mode` property.
    """

    def __init__(self, hardware_factory, health_evaluator):
        """
        Initialise a new instance.

        :param hardware_factory: a factory that provides access to the
            hardware
        :type hardware_factory: :py:class:`.HardwareFactory`
        :param health_evaluator: a class that implements a policy for
            deciding on hardware health, defaults to
            :py:class:`.HardwareHealthEvaluator`
        :type health_evaluator: :py:class:`.HardwareHealthEvaluator`
        """
        self._power_mode = PowerMode.UNKNOWN
        self._power_mode_callbacks = []
        super().__init__(hardware_factory, health_evaluator)

    def on(self):
        """
        Turn the hardware on.

        :return: whether successful, or None if there was nothing to do.
        :rtype: bool or None
        """
        if self._factory.hardware.power_mode == PowerMode.ON:
            return
        self._factory.hardware.on()

        self._update_health()
        return self._factory.hardware.power_mode == PowerMode.ON

    @property
    def power_mode(self):
        """
        Whether the hardware is on or not.

        :return: whether the hardware is on or not
        :rtype: bool
        """
        return self._factory.hardware.power_mode


class OnOffHardwareManager(BasePowerModeHardwareManager):
    """A :py:class:`.HardwareManager` mixin that adds an :py:meth:`.off` method."""

    def off(self):
        """
        Turn the hardware off.

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if self._factory.hardware.power_mode == PowerMode.OFF:
            return
        self._factory.hardware.off()

        self._update_health()
        return self._factory.hardware.power_mode == PowerMode.OFF


class OnStandbyHardwareManager(BasePowerModeHardwareManager):
    """
    A :py:class:`.HardwareManager` mixin that adds an
    :py:meth:`.standby` method.
    """

    def standby(self):
        """
        Put the hardware into low-power standby mode.

        :return: whether successful, or None if there was nothing to do
        :rtype: bool or None
        """
        if self._factory.hardware.power_mode == PowerMode.STANDBY:
            return
        self._factory.hardware.standby()

        self._update_health()
        return self._factory.hardware.power_mode == PowerMode.STANDBY


class OnStandbyOffHardwareManager(OnOffHardwareManager, OnStandbyHardwareManager):
    """
    A syntactic sugar :py:class:`.HardwareManager` mixin that combines
    both :py:class:`.OnOffHardwareManager` and
    :py:class:`.OnStandbyHardwareManager`, thus providing both
    :py:meth:`~.OnOffHardwareManager.off` and
    :py:meth:`~.OnStandbyHardwareManager.standby` methods.
    """

    pass
