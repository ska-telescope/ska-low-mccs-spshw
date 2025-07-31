#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for PDUs."""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional, Sequence

from ska_control_model import CommunicationStatus
from ska_low_mccs_common.component import DeviceComponentManager
from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.snmp_types import SNMPAttrInfo
from ska_tango_base.base import CommunicationStatusCallbackType

__all__ = ["PduComponentManager"]


class _PowerMarshallerProxy(DeviceComponentManager):
    """A proxy to the power marshaller."""

    def __init__(
        self: _PowerMarshallerProxy,
        trl: str,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param trl: the trl of the device
        :param logger: the logger to be used by this object.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        self.trl = trl
        super().__init__(
            trl,
            logger,
            communication_state_callback,
            component_state_callback,
        )

    def schedule_power(
        self: _PowerMarshallerProxy,
        attached_device_info: str,
        device_trl: str,
        command_str: str,
        on_off: str,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param attached_device_info: details about the attached device.
        :param device_trl: trl of this device.
        :param command_str: name of the command being called.
        :param on_off: args to be called for the command.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        input_dict = {
            "attached_device_info": attached_device_info,
            "device_trl": device_trl,
            "command_str": command_str,
            "command_args": on_off,
        }
        input_str = json.dumps(input_dict)
        self._proxy._device.SchedulePower(input_str)


class PduComponentManager(SNMPComponentManager):
    """A component manager for a PDU."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: PduComponentManager,
        host: str,
        port: int,
        authority: str | dict[str, str],
        max_objects_per_pdu: int,
        logger: logging.Logger,
        communication_state_callback: CommunicationStatusCallbackType,
        component_state_callback: Callable[..., None],
        attributes: Sequence[SNMPAttrInfo],
        poll_rate: float,
        power_marshaller_trl: Optional[str],
    ) -> None:
        """
        Initialise a new instance.

        :param host: the hostname of the pdu
        :param port: port of the pdu
        :param authority: the snmp authority of the pdu
        :param max_objects_per_pdu: max objects per pdu
        :param logger: logger
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        :param attributes: pdu attributes
        :param poll_rate: how often the pdu polls
        :param power_marshaller_trl: trl of power marhsaller
        """
        super().__init__(
            host=host,
            port=port,
            authority=authority,
            max_objects_per_pdu=max_objects_per_pdu,
            logger=logger,
            communication_state_callback=communication_state_callback,
            component_state_callback=component_state_callback,
            attributes=attributes,
            poll_rate=poll_rate,
        )
        self.marshaller_proxy: _PowerMarshallerProxy
        if power_marshaller_trl:
            self._power_marshaller_trl = power_marshaller_trl
            self.marshaller_proxy = _PowerMarshallerProxy(
                power_marshaller_trl,
                logger,
                communication_state_callback,
                component_state_callback,
            )
        else:
            self._power_marshaller_trl = ""

    def start_communicating(self: PduComponentManager) -> None:
        """Establish communication with the station components."""
        if self._power_marshaller_trl:
            self.marshaller_proxy.start_communicating()

    def stop_communicating(self: PduComponentManager) -> None:
        """Break off communication with the station components."""
        if self._power_marshaller_trl:
            self.marshaller_proxy.stop_communicating()

    def schedule_power(
        self: PduComponentManager,
        attached_device_info: str,
        device_trl: str,
        command_str: str,
        on_off: str,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param attached_device_info: details about the attached device.
        :param device_trl: trl of this device.
        :param command_str: name of the command being called.
        :param on_off: args to be called for the command.
        """
        if self._power_marshaller_trl:
            self.marshaller_proxy.schedule_power(
                attached_device_info, device_trl, command_str, on_off
            )
            return

        self.logger.warning("No power marshaller established, skipping...")
