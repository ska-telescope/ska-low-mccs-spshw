# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements base classes for hardware management in the MCCS
subsystem.
"""
__all__ = [
    "HardwareDriver",
    "HardwareFactory",
    "HardwareHealthEvaluator",
    "HardwareManager",
]

from ska.base.control_model import HealthState


class HardwareDriver:
    """
    An abstract base class for hardware drivers. A hardware driver
    provides a python interface to hardware, hiding details of the
    actual control interface of the hardware.

    The only functionality it mandates is the ability to check whether
    this driver is connected to hardware.
    """

    def __init__(self, is_connectible=True):
        self._is_connectible = is_connectible

    @property
    def is_connectible(self):
        """
        Returns whether the hardware to which this driver connects is
        currently connectible. For example, if the hardware is known to
        be powered off, then we would not expect it to be possible to
        connect to it, and failure to do so would not be an error.

        :return: whether the hardware that this driver will need to
            connect to is currentl connectible
        :rtype: bool
        """
        return self._is_connectible

    @is_connectible.setter
    def is_connectible(self, is_now_connectible):
        """
        Sets whether the hardware to which this driver connects is
        currently connectible.

        :param is_now_connectible: whether the hardware to which this
            driver connects is currently connectible.
        """
        self._is_connectible = is_now_connectible

    @property
    def is_connected(self):
        """
        Returns whether this driver is connected to the hardware. This
        should be implemented to return a bool.

        :raises NotImplementedError: if this method is not implemented
            by a subclass
        """
        raise NotImplementedError

    def check_connected(self, connectible_error=None, connection_error=None):
        """
        Helper method to check that a connection is in place, and raise
        a suitable error if it is not.

        :param connectible_error: the error message for the exception to
            be raised if the hardware is not currently connectible (e.g.
            it is turned off)
        :type connectible_error: str
        :param connection_error: the error message for the exception to
            be raised if the hardware should be connectible yet there is
            no connection to the hardware
        :type connection_error: str

        :raises ConnectionError: if there is no connection to the
            hardware
        """
        if not self.is_connectible:
            raise ConnectionError(
                connectible_error or "Hardware is not currently connectible."
            )

        if not self.is_connected:
            raise ConnectionError(connection_error or "No connection to hardware")


class HardwareHealthEvaluator:
    """
    An simple base class that implements a policy by which a hardware
    manager evaluates the health of its hardware.

    This evaluator treads the hardware as failed if the connection to
    the hardware is broken, and OK otherwise.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the hardware.

        :param hardware: the hardware driver for which health is being
            evaluated
        :type hardware: :py:class:`.HardwareDriver`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not hardware.is_connectible:
            return HealthState.UNKNOWN

        if not hardware.is_connected:
            return HealthState.FAILED

        return HealthState.OK


class HardwareFactory:
    """
    Abstract base class for a hardware factory.
    """

    @property
    def hardware(self):
        """
        Return the hardware.

        :raises NotImplementedError: because this method need to be
            implemented by a concrete subclass
        """
        raise NotImplementedError(
            f"{type(self).__name__}.hardware property not implemented."
        )


class HardwareManager:
    """
    A base class for a hardware manager. The hardware manager manages
    hardware on behalf of a device.

    This base class supports only monitoring and reporting on hardware
    health. To this end, it allows for:

    * registration of a HardwareHealthEvaluator to evaluate the health
      of hardware

    * a :py:meth:`poll` method that re-evaluates hardware health each
      time it is called.

    * a read-only health property

    * registration of callbacks to be called on health change
    """

    def __init__(self, hardware_factory, health_evaluator):
        """
        Initialise a new HardwareManager instance.

        :param hardware_factory: a factory that provides access to the
            hardware
        :type hardware_factory: :py:class:`.HardwareFactory`
        :param health_evaluator: a class that implements a policy for
            deciding on hardware health, defaults to
            :py:class:`.HardwareHealthEvaluator`
        :type health_evaluator: :py:class:`.HardwareHealthEvaluator`
        """
        self._factory = hardware_factory
        self._health = HealthState.UNKNOWN
        self._health_callbacks = []
        self._health_evaluator = health_evaluator
        self._update_health()

    def poll(self):
        """
        Poll the hardware and respond to external events/changes.
        """
        self._update_health()

    @property
    def health(self):
        """
        Getter for health property; returns the health of the hardware,
        as evaluated by this manager.

        :return: the health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self._health

    def _update_health(self):
        """
        Update the health of this hardware, ensuring that any registered
        callbacks are called.
        """
        health = self._health_evaluator.evaluate_health(self._factory.hardware)
        if self._health == health:
            return
        self._health = health
        for callback in self._health_callbacks:
            callback(health)

    def register_health_callback(self, callback):
        """
        Register a callback to be called when the health of the hardware
        changes.

        :param callback: function handle to be called when the health of
            the hardware changes
        :type callback: callable
        """
        self._health_callbacks.append(callback)
        callback(self._health)

    @property
    def is_connectible(self):
        """
        Returns whether the hardware managed by this hardware manager is
        currently connectible. For example, if the hardware is known to
        be powered off, then we would not expect it to be possible to
        connect to it, and failure to do so would not be an error.

        :return: whether the hardware that this driver will need to
            connect to is currentl connectible
        :rtype: bool
        """
        return self._is_connectible

    @is_connectible.setter
    def is_connectible(self, is_now_connectible):
        """
        Sets whether the hardware managed by this hardware manager is
        currently connectible.

        :param is_now_connectible: whether the hardware managed by this
            hardware manager is currently connectible.
        """
        self._is_connectible = is_now_connectible

    @property
    def is_connected(self):
        """
        Returns whether this driver is connected to the hardware.

        :return: whether this driver is connected to the hardware
        :rtype: bool
        """
        return self._factory.hardware.is_connected
