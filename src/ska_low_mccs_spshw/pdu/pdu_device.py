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
import time
from typing import Any, cast

from ska_attribute_polling.attribute_polling_device import AttributePollingDevice
from ska_control_model import CommunicationStatus, HealthState, PowerState, ResultCode
from ska_low_mccs_common import MccsBaseDevice
from ska_snmp_device.definitions import load_device_definition, parse_device_definition
from tango import AttrDataFormat, Attribute, AttrQuality, CmdArgType
from tango.server import attribute, command, device_property

from ska_low_mccs_spshw.pdu.pdu_health_model import PduHealthModel

from .pdu_component_manager import PduComponentManager

__all__ = ["MccsPdu", "main"]


# pylint: disable=too-many-instance-attributes, too-many-ancestors
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

    def init_device(self: MccsPdu) -> None:
        """Initialise the device."""
        try:
            super().init_device()
            self._build_state = sys.modules["ska_low_mccs_spshw"].__version_info__
            self._version_id = sys.modules["ska_low_mccs_spshw"].__version__
            device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
            version = f"{device_name} Software Version: {self._version_id}"
            properties = (
                f"Initialised {device_name} device with properties:\n"
                f"\tHost: {self.Host}\n"
                f"\tModel: {self.Model}\n"
                f"\tPowerMarshallerTrl: {self.PowerMarshallerTrl}\n"
            )
            self.logger.info(
                "\n%s\n%s\n%s", str(self.GetVersionInfo()), version, properties
            )

            if self.Model == "RARITAN":
                self._off_value = 0
                self._on_value = 1
            elif self.Model == "ENLOGIC":
                self._off_value = 1
                self._on_value = 2
            else:
                self.logger.error(f"Invalid model {self.Model} specified")

        except Exception as ex:  # pylint: disable=broad-exception-caught
            self.logger.error("Initialise failed: Incomplete server: %s", repr(ex))

    def delete_device(self: MccsPdu) -> None:
        """Delete the device."""
        try:
            self.logger.info("Deleting device")
            self.component_manager.stop_communicating()
            # TODO: marshaller_proxy is conditional.
            # Should this just be component_manager.cleanup() ?
            if self.component_manager._power_marshaller_trl:
                self.component_manager.marshaller_proxy.cleanup()
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to delete device %s", repr(ex))
        super().delete_device()

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

        A value of ``None`` means the component manager has no value for that
        attribute, because it lost contact with the PDU. It is pushed with
        ``ATTR_INVALID`` quality, so a subscriber gets no value.

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
        lost = [name for name, value in kwargs.items() if value is None]
        for name in lost:
            del kwargs[name]
        # update base class for power and/or fault
        super()._component_state_changed(**kwargs)

        for attribute_name, value in kwargs.items():
            info_msg = f"Updating {attribute_name}, {value}"
            self.logger.info(info_msg)

        if lost:
            timestamp = time.time()
            for name in lost:
                placeholder = self._invalid_placeholder(name)
                for push in (self.push_change_event, self.push_archive_event):
                    push(name, placeholder, timestamp, AttrQuality.ATTR_INVALID)
            self.logger.info(f"No values for {', '.join(lost)}")

    def _invalid_placeholder(self: MccsPdu, name: str) -> Any:
        """
        Return a value that an invalid push of one attribute can carry.

        Tango drops the value of an ``ATTR_INVALID`` push, but pytango still
        converts it to the attribute type first, so it must fit that type.

        :param name: the attribute to push.

        :return: a value of the attribute's type.
        """
        attr = self.get_device_attr().get_attr_by_name(name)
        if attr.get_data_format() != AttrDataFormat.SCALAR:
            return []
        if attr.get_data_type() == CmdArgType.DevString:
            return ""
        return 0

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

    @attribute(
        dtype="DevString", label="Health Report", doc="Return the health report."
    )
    def healthReport(self: MccsPdu) -> str:
        """
        Get the health report.

        :return: the health report.
        """
        return self._health_model.health_report

    @command(dtype_in=int, dtype_out="DevVarLongStringArray")
    def pduPortOn(self: MccsPdu, port: int) -> tuple[list[ResultCode], list[str]]:
        """
        Set pdu port On.

        The write is queued for the next poll, so the port switches later.

        :param port: The pdu port to turn on

        :return: a result code and a message.
        """
        self.component_manager.enqueue_write(f"pduPort{port}OnOff", self._on_value)
        return ([ResultCode.OK], [f"Queued the write to switch port {port} on."])

    @command(dtype_in=int, dtype_out="DevVarLongStringArray")
    def pduPortOff(self: MccsPdu, port: int) -> tuple[list[ResultCode], list[str]]:
        """
        Set pdu port OFF.

        The write is queued for the next poll, so the port switches later.

        :param port: The pdu port to turn off

        :return: a result code and a message.
        """
        self.component_manager.enqueue_write(f"pduPort{port}OnOff", self._off_value)
        return ([ResultCode.OK], [f"Queued the write to switch port {port} off."])


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
