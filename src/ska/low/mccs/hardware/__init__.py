# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements infrastructure for hardware management in the
MCCS subsystem.

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
    :py:meth:`~HardwareDriver.is_connected` property, which captures
    whether or not the hardware driver has established a connection to
    the hardware.

  * :py:class:`.HardwareFactory`: a base class for hardware factories.

  * :py:class:`.HardwareHealthEvaluator`: a base class for hardware
    health evaluators. The policy implemented determines health solely
    on the basis of whether there is a connection to the hardware.

  * :py:class:`.HardwareManager`: a base class for hardware managers. Its
    main function is to ensure that the hardware health evaluator is
    regularly polled.

* The "simulator" group of classes extend the above to handle switching
  between an actual hardware driver and a hardware simulator. They
  comprise:

  * :py:class:`.HardwareSimulator`: a base class for hardware simulators.
    This implements the :py:meth:`~HardwareSimulator.is_connected`
    property, and provides a
    :py:meth:`~HardwareSimulator.simulate_connection_failure` method by
    which failure of the connection to the hardware can be simulated.

  * :py:class:`.SimulableHardwareFactory`: a hardware factory that can
    switch between returning a hardware driver or a hardware simulator,
    depending on its simulation mode

  * :py:class:`.SimulableHardwareManager`: a hardware manager that
    manages a device's
    :py:attr:`~ska.base.SKABaseDevice.simulationMode` attribute,
    allowing switching between hardware driver and hardware simulator

* The "on/off" group of classes extend the base classes to handle the
  common case of hardware that can be turned off and on. They comprise

  * :py:class:`.OnOffHardwareDriver`: extends the hardware driver
    interface with :py:meth:`~OnOffHardwareDriver.off` and
    :py:meth:`~OnOffHardwareDriver.on` methods, and an
    :py:meth:`~OnOffHardwareDriver.is_on` property.

  * :py:class:`.OnOffHardwareSimulator`: provides
    a software implementation of the
    :py:meth:`~.OnOffHardwareSimulator.off` and
    :py:meth:`~.OnOffHardwareSimulator.on` methods, and the
    :py:meth:`~.OnOffHardwareSimulator.is_on` property

  * :py:class:`.OnOffHardwareManager`: extends the hardware manager to
    allow access to the :py:meth:`~.OnOffHardwareManager.off` and
    :py:meth:`~.OnOffHardwareManager.on` methods, and the
    :py:meth:`~.OnOffHardwareManager.is_on` property.
"""

__all__ = [
    "HardwareDriver",
    "HardwareFactory",
    "HardwareHealthEvaluator",
    "HardwareSimulator",
    "HardwareManager",
    "OnOffHardwareDriver",
    "OnOffHardwareManager",
    "OnOffHardwareSimulator",
    "SimulableHardwareFactory",
    "SimulableHardwareManager",
]

from .base_hardware import (
    HardwareDriver,
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareManager,
)

from .simulable_hardware import (
    HardwareSimulator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)

from .power_mode_hardware import (
    OnOffHardwareDriver,
    OnOffHardwareManager,
    OnOffHardwareSimulator,
)
