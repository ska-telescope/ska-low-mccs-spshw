#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for PDUs."""
from __future__ import annotations

import logging
from typing import Callable, Optional, Sequence

from ska_control_model import CommunicationStatus
from ska_low_mccs_common.component import DeviceComponentManager
from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.snmp_types import SNMPAttrInfo
from ska_tango_base.base import CommunicationStatusCallbackType, check_communicating

__all__ = ["PduComponentManager"]


class _PowerMarshallerProxy(DeviceComponentManager):
    """A proxy to the power marshaller."""

    def __init__(
        self: _PowerMarshallerProxy,
        fqdn: str,
        logger: logging.Logger,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the device
        :param logger: the logger to be used by this object.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        self.fqdn = fqdn
        super().__init__(
            fqdn,
            logger,
            communication_state_callback,
            component_state_callback,
        )

    def schedule_power(
        self: _PowerMarshallerProxy,
        attached_device_info: str,
        on_off: str,
        power_command: Callable,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param attached_device_info: details about the attached device.
        :param on_off: if the device is being turned on or off.
        :param power_command: Callable to power on/off a port.
        """
        assert self._proxy is not None  # for the type checker
        assert self._proxy._device is not None  # for the type checker

        self._proxy._device.SchedulePower(attached_device_info, on_off, power_command)


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
        power_marshaller_fqdn: Optional[str],
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
        :param power_marshaller_fqdn: fqdn of power marhsaller
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
        if power_marshaller_fqdn:
            self._power_marshaller_fqdn = power_marshaller_fqdn
            self.marshaller_proxy = _PowerMarshallerProxy(
                power_marshaller_fqdn,
                logger,
                communication_state_callback,
                component_state_callback,
            )
        else:
            self._power_marshaller_fqdn = ""

    @check_communicating
    def schedule_power(
        self: PduComponentManager,
        attached_device_info: str,
        on_off: str,
        power_command: Callable,
    ) -> None:
        """
        Request a power schedule from the marshaller.

        :param attached_device_info: details about the attached device.
        :param on_off: if the device is being turned on or off.
        :param power_command: Callable to power on/off a port.
        """
        if self._power_marshaller_fqdn:
            self.marshaller_proxy.schedule_power(
                attached_device_info, on_off, power_command
            )

        self.logger.warning("No power marshaller established, skipping...")
