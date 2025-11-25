# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""This module implements the PowerMarshaller device."""

from __future__ import annotations  # allow forward references in type hints

import json
import sys
from typing import Any, Callable, cast

import tango
from ska_control_model import CommunicationStatus, HealthState, PowerState
from ska_low_mccs_common import MccsBaseDevice
from tango import Attribute
from tango.server import attribute, command

from ska_low_mccs_spshw.power_marshaller.power_marshaller_health_model import (
    PowerMarshallerHealthModel,
)

from .power_marshaller_component_manager import PowerMarshallerComponentManager

__all__ = ["PowerMarshaller", "main"]


class PowerMarshaller(MccsBaseDevice):
    """An implementation of a PowerMarshaller Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def __init__(
        self: PowerMarshaller,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param args: positional arguments.
        :param kwargs: keyword arguments.
        """
        # This __init__ method is created for type-hinting purposes only.
        # Tango devices are not supposed to have __init__ methods,
        # And they have a strange __new__ method,
        # that calls __init__ when you least expect it.
        # So don't put anything executable in here
        # (other than the super() call).
        super().__init__(*args, **kwargs)
        self._dynamic_attrs: dict[str, Attribute]
        self._health_state: HealthState
        self._health_model: PowerMarshallerHealthModel
        self.component_manager: PowerMarshallerComponentManager

        self.command_queue: list[Callable] = []

    def init_device(self: PowerMarshaller) -> None:
        """Initialise the device."""
        try:
            super().init_device()
            self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
            device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
            version = f"{device_name} Software Version: {self._version_id}"
            properties = f"Initialised {device_name}"
            version_info = f"{self.__class__.__name__}, {self._build_state}"
            self.logger.info("\n%s\n%s\n%s", version_info, version, properties)

        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Initialise failed: Incomplete server: %s", repr(ex))

    def delete_device(self: PowerMarshaller) -> None:
        """Delete the device."""
        try:
            self.logger.info("Deleting device")
            self.component_manager.stop_communicating()
        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Failed to delete device %s", repr(ex))
        super().delete_device()

    def _init_state_model(self: PowerMarshaller) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN
        self._health_model = PowerMarshallerHealthModel(self._health_changed, True)
        self.set_change_event("healthState", True, False)
        self.set_archive_event("healthState", True, False)

    def create_component_manager(
        self: PowerMarshaller,
    ) -> PowerMarshallerComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return PowerMarshallerComponentManager(
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
        )

    def _communication_state_changed(
        self: PowerMarshaller,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications between
            the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: "component_on",
        }
        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        info_msg = f"Communication status is {communication_state.name}"
        self.logger.info(info_msg)
        self._health_model.update_state(
            communicating=communication_state == CommunicationStatus.ESTABLISHED,
        )
        super()._communication_state_changed(communication_state)

    def _component_state_changed(
        self: PowerMarshaller,
        fault: bool | None = None,
        power: PowerState | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param fault: whether the component has faulted or not
        :param power: unused in this implementation
        :param kwargs: state change parameters.
        """
        if "health" in kwargs:
            health = kwargs.pop("health")
            if self._health_state != health:
                # update health_state which is an attribute in the base class
                # change and archive events are pushed there
                self._update_health_state(health)
        # update base class for power and/or fault
        super()._component_state_changed(**kwargs)

        for attribute_name, value in kwargs.items():
            info_msg = f"Updating {attribute_name}, {value}"
            self.logger.info(info_msg)

    def _health_changed(self: PowerMarshaller, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state != health:
            self._health_state = health
            self.push_change_event("healthState", health)

    @attribute(dtype="DevString")
    def healthReport(self: PowerMarshaller) -> str:
        """
        Get the health report.

        :return: the health report.
        """
        return self._health_model.health_report

    @command(dtype_in=str)
    def SchedulePower(
        self: PowerMarshaller,
        args_in: str,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param args_in: args in.
        """
        args_expanded = json.loads(args_in)
        attached_device_info = args_expanded["attached_device_info"]
        command_args = args_expanded["command_args"]
        command_str = args_expanded["command_str"]
        device_trl = args_expanded["device_trl"]

        if attached_device_info is None:
            self.logger.info("No device info found")
            return

        device_proxy = tango.DeviceProxy(device_trl)
        device_proxy.command_inout(command_str, int(command_args))


# ----------
# Run server
# ----------


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments
    :return: exit code
    """
    return cast(int, PowerMarshaller.run_server(args=args or None, **kwargs))


if __name__ == "__main__":
    main()
