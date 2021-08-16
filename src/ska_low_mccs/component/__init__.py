# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements infrastructure for component management in MCCS."""

__all__ = [
    "CommunicationStatus",
    "ComponentManagerWithUpstreamPowerSupply",
    "ControlMode",
    "DeviceComponentManager",
    "DriverSimulatorSwitchingComponentManager",
    "HardwareClient",
    "PoolComponentManager",
    "PowerSupplyProxyComponentManager",
    "PowerSupplyProxySimulator",
    "MccsComponentManager",
    "MccsComponentManagerProtocol",
    "MessageQueueComponentManager",
    "ObjectComponent",
    "ObjectComponentManager",
    "ObsDeviceComponentManager",
    "SwitchingComponentManager",
    "WebHardwareClient",
    "check_communicating",
    "check_on",
    "enqueue",
]

from .component_manager import (
    CommunicationStatus,
    ControlMode,
    MccsComponentManager,
    MccsComponentManagerProtocol,
)
from .util import check_communicating, check_on
from .message_queue_component_manager import MessageQueueComponentManager, enqueue
from .object_component import ObjectComponent
from .object_component_manager import ObjectComponentManager
from .device_component_manager import DeviceComponentManager, ObsDeviceComponentManager

from .switching_component_manager import (
    SwitchingComponentManager,
    DriverSimulatorSwitchingComponentManager,
)
from .upstream_component_manager import (
    PowerSupplyProxyComponentManager,
    PowerSupplyProxySimulator,
    ComponentManagerWithUpstreamPowerSupply,
)

from .hardware_client import (  # type: ignore[attr-defined]
    HardwareClient,
    WebHardwareClient,
)
