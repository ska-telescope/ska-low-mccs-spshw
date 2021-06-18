# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for hardware management in the MCCS subsystem.

Conceptually, the model comprises:

* Hardware drivers. These wraps actual hardware. The hardware provides a
  software-controllable interface, but the possibilities for this are
  diverse: USB, bluetooth, serial line, ethernet, TCP / UDP / IP,
  encodings, encryption, session management, etc etc etc. A hardware
  driver encapsulates all that, and provides a python object interface
  to the hardware.

* Hardware simulators. These implement the interface of the
  corresponding hardware driver, but in software. That is, a hardware
  simulator pretends to be a hardware driver, but it does not wrap
  actual hardware. In addition to implementing the driver interface,
  a simulator may expose methods for external events that it can
  simulate. For example, actual hardware can fail, so a simulator might
  simulate failure via methods like `_simulate_cooling_failure` etc.

* Hardware factories. These create and provide access to hardware
  drivers / simulators. For example, in a device that can switch between
  hardware driver and hardware simulator, the hardware factory is
  responsible for the switching, and all other components of the system
  do not distinguish between the two.

* Hardware health evaluators. These interrogate the hardware, evaluate
  its health in accordance with some policy, and report that health to
  other components.

* Hardware managers. These manage hardware on behalf of a device.
  Specifically, they manage a device's simulation mode (if relevant),
  monitor hardware health, and provide access to the hardware interface.


The classes fall into three groups:

* The "base" classes comprise:

  * :py:class:`.HardwareDriver`: a base class for hardware drivers. The
    only functionality it specifies is an
    :py:meth:`~.HardwareDriver.connection_status` property, which
    captures the status of the driver's connection to the hardware.

  * :py:class:`.HardwareFactory`: a base class for hardware factories.

  * :py:class:`.HardwareHealthEvaluator`: a base class for hardware
    health evaluators. The policy implemented determines health solely
    on the basis of whether there is a connection to the hardware.

  * :py:class:`.HardwareManager`: a base class for hardware managers.
    Its main function is to ensure that the hardware health evaluator is
    regularly polled.

* The "simulator" group of classes extend the above to handle switching
  between an actual hardware driver and a hardware simulator. They
  comprise:

  * :py:class:`.HardwareSimulator`: a base class for hardware simulators.
    This implements the :py:meth:`~.HardwareDriver.connection_status`
    property, and provides a
    :py:meth:`~HardwareSimulator.simulate_connection_failure` method by
    which failure of the connection to the hardware can be simulated.

  * :py:class:`.SimulableHardwareFactory`: a hardware factory that can
    switch between returning a hardware driver or a hardware simulator,
    depending on its simulation mode

  * :py:class:`.SimulableHardwareManager`: a hardware manager that
    manages a device's
    :py:attr:`ska_tango_base.SKABaseDevice.simulationMode` attribute,
    allowing switching between hardware driver and hardware simulator

* The "power mode" group of classes extend the base classes to handle
  the common case of hardware for which power mode can be managed e.g.
  they can be turned off and on. To be precise, such devices have an
  "on" power mode, in which they are fully powered, and an
  :py:meth:`~.BasePowerModeHardwareDriver.on`
  command.

  In addition they must have at least one other power mode that serves
  as a counterpoint to the "on" power mode: "off" (powered off) or
  "standby" (in a low-power standby mode) or both. These classes are
  therefore mostly implemented as mixins:

  * A private
    :py:class:`~.BasePowerModeHardwareDriver`
    base class provides for an
    :py:meth:`~.BasePowerModeHardwareDriver.on`
    method and a
    :py:attr:`~.BasePowerModeHardwareDriver.power_mode`
    property

  * :py:class:`.OnOffHardwareDriver` adds an
    :py:meth:`~OnOffHardwareDriver.off` method.

  * :py:class:`.OnStandbyHardwareDriver` add a
    :py:meth:`~OnStandbyHardwareDriver.standby` method.

  * :py:class:`.OnStandbyOffHardwareDriver` combines the two and thus
    supports both :py:meth:`~OnOffHardwareDriver.off` and
    :py:meth:`~OnStandbyHardwareDriver.standby` methods. (It is really
    just syntactic sugar.)

  * A private
    :py:class:`~.BasePowerModeHardwareSimulator`
    base class provides a software implementation of the
    :py:meth:`~.BasePowerModeHardwareSimulator.on`
    method and
    :py:attr:`~.BasePowerModeHardwareSimulator.power_mode`
    property.

  * :py:class:`.OnOffHardwareSimulator`: adds a software implementation
    of the :py:meth:`~.OnOffHardwareSimulator.off` method

  * :py:class:`.OnStandbyHardwareSimulator`: adds a software
    implementation of the :py:meth:`~.OnStandbyHardwareSimulator.standby`
    method

  * :py:class:`.OnStandbyOffHardwareSimulator` combines the two and thus
    supports both :py:meth:`~OnOffHardwareSimulator.off` and
    :py:meth:`~OnStandbyHardwareSimulator.standby` methods. (It is
    really just syntactic sugar.)

  * A private
    :py:class:`~.BasePowerModeHardwareManager`
    base class extends the hardware manager with an
    :py:meth:`~.BasePowerModeHardwareManager.on`
    method and a
    :py:attr:`~ska_low_mccs.hardware.power_mode_hardware.BasePowerModeHardwareManager.power_mode`
    property.

  * :py:class:`.OnOffHardwareManager`: add an
    :py:meth:`~.OnOffHardwareManager.off` method.

  * :py:class:`.OnStandbyHardwareManager`: add an
    :py:meth:`~.OnStandbyHardwareManager.standby` method.

  * :py:class:`.OnStandbyOffHardwareManager` combines the two and thus
    supports both :py:meth:`~OnOffHardwareManager.off` and
    :py:meth:`~OnStandbyHardwareManager.standby` methods. (It is
    really just syntactic sugar.)
"""

__all__ = [
    "BasePowerModeHardwareDriver",
    "BasePowerModeHardwareSimulator",
    "BasePowerModeHardwareManager",
    "ConnectionStatus",
    "ControlMode",
    "HardwareDriver",
    "HardwareFactory",
    "HardwareHealthEvaluator",
    "HardwareSimulator",
    "HardwareManager",
    "OnOffHardwareDriver",
    "OnOffHardwareManager",
    "OnOffHardwareSimulator",
    "OnStandbyHardwareDriver",
    "OnStandbyHardwareManager",
    "OnStandbyHardwareSimulator",
    "OnStandbyOffHardwareDriver",
    "OnStandbyOffHardwareManager",
    "OnStandbyOffHardwareSimulator",
    "PowerMode",
    "SimulableHardwareFactory",
    "SimulableHardwareManager",
    "power_mode_hardware",
    "HardwareClient",
    "WebHardwareClient",
]

from .base_hardware import (  # type: ignore[attr-defined]
    ConnectionStatus,
    ControlMode,
    HardwareDriver,
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareManager,
)

from .simulable_hardware import (  # type: ignore[attr-defined]
    HardwareSimulator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)

from .power_mode_hardware import (  # type: ignore[attr-defined]
    BasePowerModeHardwareDriver,
    BasePowerModeHardwareSimulator,
    BasePowerModeHardwareManager,
    OnOffHardwareDriver,
    OnOffHardwareManager,
    OnOffHardwareSimulator,
    OnStandbyHardwareDriver,
    OnStandbyHardwareManager,
    OnStandbyHardwareSimulator,
    OnStandbyOffHardwareDriver,
    OnStandbyOffHardwareManager,
    OnStandbyOffHardwareSimulator,
    PowerMode,
)

from .hardware_client import (  # type: ignore[attr-defined]
    HardwareClient,
    WebHardwareClient,
)
