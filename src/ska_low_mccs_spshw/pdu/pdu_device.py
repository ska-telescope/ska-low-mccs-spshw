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

from ska_control_model import CommunicationStatus, HealthState, PowerState
from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.snmp_device import AttributePollingDevice
from tango.server import device_property

from ska_low_mccs_spshw.pdu.pdu_health_model import PduHealthModel

__all__ = ["MccsPdu", "main"]


class MccsPdu(AttributePollingDevice):
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

    DeviceModels: dict[str, str] = {
        "PDU": "pdu.yaml",
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
        self._health_state: HealthState
        self._health_model: PduHealthModel
        self._dynamic_attrs: dict
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__

        super().__init__(*args, **kwargs)

    def init_device(self: MccsPdu) -> None:
        """Initialise the device."""
        try:
            super().init_device()

            device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
            version = f"{device_name} Software Version: {self._version_id}"
            properties = f"Initialised {device_name} on: {self.Host}:{self.Port}"
            version_info = f"{self.__class__.__name__}, {self._build_state}"
            self.logger.info("\n%s\n%s\n%s", version_info, version, properties)

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

    def _init_state_model(self: MccsPdu) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN
        self._health_model = PduHealthModel(self._component_state_changed)
        self.set_change_event("healthState", True, False)
        self.set_archive_event("healthState", True, False)

    def create_component_manager(self) -> SNMPComponentManager:
        """
        Create and return a component manager.

        :return: SNMPComponent manager
        """
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        filename = self.DeviceModels[self.Model]
        device_definition = importlib.resources.files(
            "ska_low_mccs_spshw.pdu.pdu"
        ).joinpath(filename)
        dynamic_attrs = self.parse_device_definition(
            self.load_device_definition(str(device_definition), None)
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

        return SNMPComponentManager(
            host=self.Host,
            port=self.Port,
            authority=authority,
            max_objects_per_pdu=self.MaxObjectsPerSNMPCmd,
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
            attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
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
            CommunicationStatus.NOT_ESTABLISHED: "component_disconnected",
            CommunicationStatus.ESTABLISHED: "component_on",
        }
        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        info_msg = f"Communication status is {communication_state}"
        self.logger.info(info_msg)
        self._health_model.update_state(communicating=True)

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
                self._health_state = cast(HealthState, health)
                self.push_change_event("healthState", health)
                self.push_archive_event("healthState", health)
        super()._component_state_changed(**kwargs)

        for attribute_name, value in kwargs.items():
            info_msg = f"Updating {attribute_name}, {value}"
            self.logger.info(info_msg)


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
