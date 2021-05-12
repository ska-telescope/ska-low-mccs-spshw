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
    "ConnectionStatus",
    "ControlMode",
    "HardwareDriver",
    "HardwareFactory",
    "HardwareHealthEvaluator",
    "HardwareManager",
]

from enum import Enum

from ska_tango_base.control_model import HealthState


class ControlMode(Enum):
    """
    The control modes for hardware.

    Currently only MANUAL and AUTO modes are provided. In future we
    might need to support CASCADE mode.
    """

    MANUAL = 1
    """
    The control element is controlled by an external operator, such as
    a human or a TANGO device
    """

    AUTO = 2
    """
    The control element is controlled by an internal controller.
    """


class ConnectionStatus(Enum):
    """
    Represents the status of a hardware driver's connection to its
    hardware.
    """

    NOT_CONNECTIBLE = 1
    """
    It is not possible to connect to the hardware. There's no point even
    trying. For example, the hardware is not currently supplied with
    power.
    """

    NOT_CONNECTED = 2
    """
    It should be possible for the driver to connect to the hardware but
    it is not currently connected.
    """

    CONNECTED = 3
    """
    The driver has a connection to the hardware.
    """


class HardwareDriver:
    """
    An abstract base class for hardware drivers. A hardware driver
    provides a python interface to hardware, hiding details of the
    actual control interface of the hardware.

    The only functionality it mandates is the ability to check whether
    this driver is connected to hardware.
    """

    def __init__(self, is_connectible):
        """
        Initialise a new instance.

        This initialiser should construct the driver object and return
        ASAP. It therefore should not attempt anything that may suffer
        latency; for example, it should not try to establish a network
        connection to the hardware. Save that for the `connect` method.

        :param is_connectible: whether we expect the driver to be able
            to connect to the hardware. For example, if we know that the
            hardware is currently powered off, we wouldn't even try to
            connect to it.
        :type is_connectible: bool
        """
        self._connection_status = (
            ConnectionStatus.NOT_CONNECTED
            if is_connectible
            else ConnectionStatus.NOT_CONNECTIBLE
        )

    def connect(self):
        """
        Connect to the hardware.

        :return: whether successful or not; or None if the hardware was
            already connected.
        :rtype: bool
        """
        if self._connection_status == ConnectionStatus.CONNECTED:
            return None

        if (
            self._connection_status == ConnectionStatus.NOT_CONNECTED
            and self._connect()
        ):
            self._connection_status = ConnectionStatus.CONNECTED
            return True

        return False

    def _connect(self):
        """
        Try to connect to the hardware, and returns whether successful
        or not.

        :raises NotImplementedError: because this method needs to be
            implemented by a subclass
        """
        raise NotImplementedError(
            "HardwareDriver is abstract. Method '_connect' must "
            "be implemented by a subclass."
        )

    @property
    def connection_status(self):
        """
        Returns the status of the driver-hardware connection.

        :return: the status of the driver-hardware connection.
        :rtype: py:class:`.ConnectionStatus`
        """
        return self._connection_status

    @connection_status.setter
    def connection_status(self, status):
        """
        Sets the status of the driver-hardware connection.

        :param status: new status of the driver-hardware connection.
        """
        self._connection_status = status

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
        connection_status = self._connection_status
        if connection_status == ConnectionStatus.NOT_CONNECTIBLE:
            raise ConnectionError(
                connectible_error or "Hardware is not currently connectible."
            )

        if connection_status == ConnectionStatus.NOT_CONNECTED:
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
        :rtype: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        connection_status = hardware.connection_status
        if connection_status == ConnectionStatus.NOT_CONNECTIBLE:
            return HealthState.UNKNOWN

        if connection_status == ConnectionStatus.NOT_CONNECTED:
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
        # self._update_health()  # don't update health until after first connect attempt

    def poll(self):
        """
        Poll the hardware and respond to external events/changes.
        """
        if self._factory.hardware.connection_status == ConnectionStatus.NOT_CONNECTED:
            _ = self._factory.hardware.connect()  # attempt re-connection
        self._update_health()

    @property
    def health(self):
        """
        Getter for health property; returns the health of the hardware,
        as evaluated by this manager.

        :return: the health of the hardware
        :rtype: :py:class:`~ska_tango_base.control_model.HealthState`
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

    def connect(self):
        """
        Connect to the hardware.

        :return: whether successful or not; or None if the hardware was
            already connected.
        :rtype: bool
        """
        success = self._factory.hardware.connect()
        self._update_health()
        return success

    @property
    def connection_status(self):
        """
        Returns the status of the software-hardware connection.

        :return: the status of the software-hardware connection
        :rtype: :py:class:`.ConnectionStatus`
        """
        return self._factory.hardware.connection_status

    def set_connectible(self, is_connectible):
        """
        Sets whether it should be possible to establish a software-
        hardware connection.

        This is used to signal to the software whether there is any
        point in trying to connect to the hardware. For example, if
        power supply turns off power to the hardware, we would use this
        method to tell the software driver that it should not expect to
        be able to connect to the hardware, and therefore should not
        treat the loss of a connection as a hardware failure.

        :param is_connectible: whether the hardware managed by this
            hardware manager is currently connectible.
        :type is_connectible: bool
        """
        if is_connectible:
            if (
                self._factory.hardware.connection_status
                == ConnectionStatus.NOT_CONNECTIBLE
            ):
                self._factory.hardware.connection_status = (
                    ConnectionStatus.NOT_CONNECTED
                )
                if self._factory.hardware._connect():
                    self._factory.hardware.connection_status = (
                        ConnectionStatus.CONNECTED
                    )
        else:
            self._factory.hardware.connection_status = ConnectionStatus.NOT_CONNECTIBLE
        self._update_health()
