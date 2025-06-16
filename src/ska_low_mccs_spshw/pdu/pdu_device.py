# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""This module implements the PDU device."""

from __future__ import annotations  # allow forward references in type hints

import importlib.resources
import sys
from typing import Any, cast

from ska_attribute_polling.attribute_polling_device import AttributePollingDevice
from ska_control_model import CommunicationStatus, HealthState, PowerState
from ska_low_mccs_common import MccsBaseDevice
from ska_snmp_device.definitions import load_device_definition, parse_device_definition
from tango import Attribute
from tango.server import attribute, command, device_property

from ska_low_mccs_spshw.pdu.pdu_health_model import PduHealthModel

from .pdu_component_manager import PduComponentManager

__all__ = ["MccsPdu", "main"]


# pylint: disable=too-many-instance-attributes
class MccsPdu(MccsBaseDevice, AttributePollingDevice):
    """An implementation of a PDU Tango device for MCCS."""

    Model = device_property(dtype=str, mandatory=True)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    V2Community = device_property(dtype=str)
    V3UserName = device_property(dtype=str)
    V3AuthKey = device_property(dtype=str)
    V3PrivKey = device_property(dtype=str)
    MaxObjectsPerSNMPCmd = device_property(dtype=int, default_value=24)
    UpdateRate = device_property(dtype=float, default_value=3.0)
    PowerMarshallerTrl = device_property(dtype=str, default_value="")
    PortDeviceTrls = device_property(dtype=(str,), default_value=[])

    DeviceModels: dict[str, str] = {
        "ENLOGIC": "enlogic.yaml",
        "RARITAN": "raritan.yaml",
    }

    # ---------------
    # Initialisation
    # ---------------
    def __init__(
        self: MccsPdu,
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
        self._health_model: PduHealthModel
        self._on_value: int
        self._off_value: int
        self.component_manager: PduComponentManager

        self._port_device_information: list[str] = [""] * 24

        if self.PortDeviceTrls:
            for i, trl in enumerate(self.PortDeviceTrls):
                self._port_device_information[i] = trl

    def init_device(self: MccsPdu) -> None:
        """Initialise the device."""
        try:
            super().init_device()
            self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
            device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
            version = f"{device_name} Software Version: {self._version_id}"
            properties = f"Initialised {device_name} on: {self.Host}:{self.Port}"
            version_info = f"{self.__class__.__name__}, {self._build_state}"
            self.logger.info("\n%s\n%s\n%s", version_info, version, properties)
            if self.Model == "RARITAN":
                self._off_value = 0
                self._on_value = 1
            elif self.Model == "ENLOGIC":
                self._off_value = 1
                self._on_value = 2
            else:
                self.logger.error(f"Invalid model {self.Model} specified")

        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Initialise failed: Incomplete server: %s", repr(ex))

    def delete_device(self: MccsPdu) -> None:
        """Delete the device."""
        try:
            self.logger.info("Deleting device")
            self.component_manager.stop_communicating()
        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Failed to delete device %s", repr(ex))
        self.component_manager.marshaller_proxy.cleanup()

    def _init_state_model(self: MccsPdu) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN
        self._health_model = PduHealthModel(self._health_changed, True)
        self.set_change_event("healthState", True, False)
        self.set_archive_event("healthState", True, False)

    def create_component_manager(self: MccsPdu) -> PduComponentManager:
        """
        Create and return a component manager.

        :return: SNMPComponent manager
        """
        filename = self.DeviceModels[self.Model]
        device_definition = importlib.resources.files(
            "ska_low_mccs_spshw.pdu.device_definitions"
        ).joinpath(filename)
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        dynamic_attrs = parse_device_definition(
            load_device_definition(str(device_definition))
        )
        self._dynamic_attrs = {attr.name: attr for attr in dynamic_attrs}

        assert (self.V2Community and not self.V3UserName) or (
            not self.V2Community and self.V3UserName
        ), "Can't be V2 & V3 simultaneously"

        if self.V2Community:
            authority = self.V2Community
        else:
            authority = {
                "auth": self.V3UserName,
                "authKey": self.V3AuthKey,
                "privKey": self.V3PrivKey,
            }

        return PduComponentManager(
            host=self.Host,
            port=self.Port,
            authority=authority,
            max_objects_per_pdu=self.MaxObjectsPerSNMPCmd,
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
            attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
            power_marshaller_trl=self.PowerMarshallerTrl,
        )

    def _communication_state_changed(
        self: MccsPdu,
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

        info_msg = f"Communication status is {communication_state}"
        self.logger.info(info_msg)
        self._health_model.update_state(
            communicating=communication_state == CommunicationStatus.ESTABLISHED
        )
        super()._communication_state_changed(communication_state)

    def _component_state_changed(
        self: MccsPdu,
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

    def _health_changed(self: MccsPdu, health: HealthState) -> None:
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
    def healthReport(self: MccsPdu) -> str:
        """
        Get the health report.

        :return: the health report.
        """
        return self._health_model.health_report

    @command(dtype_in=int)
    def pduPortOn(self: MccsPdu, port: int) -> None:
        """
        Set pdu port On.

        :param port: The pdu port to turn on
        """
        self.component_manager.enqueue_write(f"pduPort{port}OnOff", self._on_value)

    @command(dtype_in=int)
    def pduPortOff(self: MccsPdu, port: int) -> None:
        """
        Set pdu port OFF.

        :param port: The pdu port to turn off
        """
        self.component_manager.enqueue_write(f"pduPort{port}OnOff", self._off_value)

    @command(dtype_in=int)
    def SchedulePduPortOn(self: MccsPdu, port: int) -> None:
        """
        Schedule PDU port on with power marshaller.

        :param port: The pdu port to turn on
        """
        if not self._port_device_information or self._port_device_information[port]:
            self.logger.error("No information known about attached device")
            return
        attached_device_info = self._port_device_information[port]
        self.component_manager.schedule_power(
            attached_device_info, self.get_name(), "pduPortOn", str(port)
        )

    @command(dtype_in=int)
    def SchedulePduPortOff(self: MccsPdu, port: int) -> None:
        """
        Schedule PDU port off with power marshaller.

        :param port: The pdu port to turn off
        """
        if not self._port_device_information or self._port_device_information[port]:
            self.logger.error("No information known about attached device")
            return
        attached_device_info = self._port_device_information[port]
        self.component_manager.schedule_power(
            attached_device_info, self.get_name(), "pduPortOff", str(port)
        )


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
    return cast(int, MccsPdu.run_server(args=args or None, **kwargs))


if __name__ == "__main__":
    main()
