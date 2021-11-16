# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements an component manager for an MCCS antenna Tango device."""
from __future__ import annotations

import logging
from typing import Callable, Optional

import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    DeviceComponentManager,
    MccsComponentManager,
    PowerSupplyProxyComponentManager,
    check_communicating,
    check_on,
)


__all__ = ["AntennaComponentManager"]


class _ApiuProxy(PowerSupplyProxyComponentManager, DeviceComponentManager):
    """A proxy to an antenna's APIU."""

    def __init__(
        self: _ApiuProxy,
        fqdn: str,
        logical_antenna_id: int,
        logger: logging.Logger,
        push_change_event,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Callable[[bool], None],
        antenna_power_mode_changed_callback: Callable[[PowerMode], None],
    ) -> None:
        """
        Initialise a new APIU proxy instance.

        :param fqdn: the FQDN of the APIU
        :param logical_antenna_id: this antenna's id within the APIU
        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param antenna_power_mode_changed_callback: callback to be
            called when the power mode of the antenna changes.

        :raises AssertionError: if parameters are out of bounds
        """
        assert (
            logical_antenna_id > 0
        ), "An APIU's logical antenna id must be positive integer."
        self._logical_antenna_id = logical_antenna_id

        self._antenna_change_registered = False

        super().__init__(
            fqdn,
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            supplied_power_mode_changed_callback=antenna_power_mode_changed_callback,
        )

    def stop_communicating(self: _ApiuProxy) -> None:
        """Cease communicating with the APIU device."""
        super().stop_communicating()
        self._antenna_change_registered = False

    def reset(self: _ApiuProxy) -> None:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError("Antenna cannot be reset.")

    @check_communicating
    def power_on(self: _ApiuProxy) -> ResultCode | None:
        """
        Tell the APIU to power on this antenna.

        :return: a result code.
        """
        if self.supplied_power_mode == PowerMode.ON:
            return None
        rc = self._power_up_antenna()
        return rc

    def _power_up_antenna(self: _ApiuProxy) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.PowerUpAntenna(
            self._logical_antenna_id
        )
        return result_code

    @check_communicating
    def power_off(self: _ApiuProxy) -> ResultCode | None:
        """
        Tell the APIU to power off this antenna.

        :return: a result code.
        """
        if self.supplied_power_mode == PowerMode.OFF:
            return None
        return self._power_down_antenna()

    def _power_down_antenna(self: _ApiuProxy) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], [message]) = self._proxy.PowerDownAntenna(
            self._logical_antenna_id
        )
        return result_code

    @property  # type: ignore[misc]
    @check_communicating
    @check_on
    def current(self: _ApiuProxy) -> float:
        """
        Return the antenna's current.

        :return: the current of this antenna
        """
        assert self._proxy is not None  # for the type checker
        return self._proxy.get_antenna_current(self._logical_antenna_id)

    @property  # type: ignore[misc]
    @check_communicating
    @check_on
    def voltage(self: _ApiuProxy) -> float:
        """
        Return the antenna's voltage.

        :return: the voltage of this antenna
        """
        assert self._proxy is not None  # for the type checker
        return self._proxy.get_antenna_voltage(self._logical_antenna_id)

    @property  # type: ignore[misc]
    @check_communicating
    @check_on
    def temperature(self: _ApiuProxy) -> float:
        """
        Return the antenna's temperature.

        :return: the temperature of this antenna
        """
        assert self._proxy is not None  # for the type checker
        return self._proxy.get_antenna_temperature(self._logical_antenna_id)

    def _device_state_changed(
        self: _ApiuProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        assert (
            event_name.lower() == "state"
        ), "state changed callback called but event_name is {event_name}."

        super()._device_state_changed(event_name, event_value, event_quality)
        if event_value == tango.DevState.ON and not self._antenna_change_registered:
            self._register_are_antennas_on_callback()
        elif event_value == tango.DevState.OFF:
            self.update_supplied_power_mode(PowerMode.OFF)

    def _register_are_antennas_on_callback(self: _ApiuProxy) -> None:
        assert self._proxy is not None  # for the type checker
        self._proxy.add_change_event_callback(
            "areAntennasOn",
            self._antenna_power_mode_changed,
            stateless=True,
        )
        self._antenna_change_registered = True

    def _antenna_power_mode_changed(
        self: _ApiuProxy,
        event_name: str,
        event_value: list[bool],
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in antenna power mode.

        This is a callback that is triggered by an event subscription
        on the APIU device.

        :param event_name: name of the event; will always be
            "areAntennasOn" for this callback
        :param event_value: the new attribute value
        :param event_quality: the quality of the change event
        """
        assert event_name.lower() == "areAntennasOn".lower(), (
            "APIU 'areAntennasOn' attribute changed callback called but "
            f"event_name is {event_name}."
        )
        self.update_supplied_power_mode(
            PowerMode.ON if event_value[self._logical_antenna_id - 1] else PowerMode.OFF
        )


class _TileProxy(DeviceComponentManager):
    """
    A component manager for an antenna, that proxies through a Tile Tango device.

    Note the semantics: the end goal is the antenna, not the Tile that
    it proxies through.

    For example, the communication status of this component manager
    reflects whether communication has been established all the way to
    the antenna. If we have established communication with the Tile
    Tango device, but the Tile Tango device reports that the Tile is
    turned off, then we have NOT establihed communication to the
    antenna.

    At present it is an unused, unimplemented placeholder.
    """

    def __init__(
        self: _TileProxy,
        fqdn: str,
        logical_antenna_id: int,
        logger: logging.Logger,
        push_change_event,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the Tile device
        :param logical_antenna_id: this antenna's id within the Tile
        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :raises AssertionError: if parameters are out of bounds
        """
        assert (
            logical_antenna_id > 0
        ), "An APIU's logical antenna id must be positive integer."
        self._logical_antenna_id = logical_antenna_id

        super().__init__(
            fqdn,
            logger,
            push_change_event,
            communication_status_changed_callback,
            lambda power_mode: None,  # tile doesn't manage antenna power
            component_fault_callback,
        )

    def off(self: _TileProxy) -> None:
        """
        Turn the antenna off; this is not implemented.

        This raises NotImplementedError because the antenna's power mode
        is not controlled via the Tile device; it is controlled via the
        APIU device.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power mode is not controlled via Tile device."
        )

    def standby(self: _TileProxy) -> None:
        """
        Put the antenna into standby mode; this is not implemented.

        This raises NotImplementedError because the antenna has no
        standby mode; and because the antenna's power mode is not
        controlled via the Tile device; it is controlled via the APIU
        device.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power mode is not controlled via Tile device."
        )

    def on(self: _TileProxy) -> None:
        """
        Turn the antenna on; this is not implemented.

        This raises NotImplementedError because the antenna's power mode
        is not controlled via the Tile device; it is controlled via the
        APIU device.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power mode is not controlled via Tile device."
        )

    def reset(self: _TileProxy) -> None:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError("Antenna hardware is not resettable.")


class AntennaComponentManager(MccsComponentManager):
    """
    A component manager for managing the component of an MCCS antenna Tango device.

    Since there is no way to monitor and control an antenna directly,
    this component manager simply proxies certain commands to the APIU
    and/or tile Tango device.
    """

    def __init__(
        self: AntennaComponentManager,
        apiu_fqdn: str,
        apiu_antenna_id: int,
        tile_fqdn: str,
        tile_antenna_id: int,
        logger: logging.Logger,
        push_change_event,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_power_mode_changed_callback: Callable[[PowerMode], None],
        component_fault_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param apiu_fqdn: the FQDN of the Tango device for this
            antenna's APIU.
        :param apiu_antenna_id: the id of the antenna in the APIU.
        :param tile_fqdn: the FQDN of the Tango device for this
            antenna's tile.
        :param tile_antenna_id: the id of the antenna in the tile.
        :param logger: a logger for this object to use
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        """
        self._apiu_power_mode = PowerMode.UNKNOWN
        self._target_power_mode: Optional[PowerMode] = None

        self._apiu_communication_status: CommunicationStatus = (
            CommunicationStatus.DISABLED
        )
        self._tile_communication_status: CommunicationStatus = (
            CommunicationStatus.DISABLED
        )
        self._antenna_faulty_via_apiu = False
        self._antenna_faulty_via_tile = False

        self._apiu_proxy = _ApiuProxy(
            apiu_fqdn,
            apiu_antenna_id,
            logger,
            push_change_event,
            self._apiu_communication_status_changed,
            self._apiu_power_mode_changed,
            self._apiu_component_fault_changed,
            self._antenna_power_mode_changed,
        )
        self._tile_proxy = _TileProxy(
            tile_fqdn,
            tile_antenna_id,
            logger,
            push_change_event,
            self._tile_communication_status_changed,
            self._tile_component_fault_changed,
        )

        super().__init__(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
        )

    def start_communicating(self: AntennaComponentManager) -> None:
        """Establish communication with the component, then start monitoring."""
        super().start_communicating()
        self._apiu_proxy.start_communicating()
        self._tile_proxy.start_communicating()

    def stop_communicating(self: AntennaComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()
        self._apiu_proxy.stop_communicating()
        self._tile_proxy.stop_communicating()

    def _apiu_communication_status_changed(
        self: AntennaComponentManager, communication_status: CommunicationStatus
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the APIU.

        :param communication_status: the status of communication with
            the antenna via the APIU.
        """
        self._apiu_communication_status = communication_status
        self._update_joint_communication_status()

    def _tile_communication_status_changed(
        self: AntennaComponentManager, communication_status: CommunicationStatus
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the tile.

        :param communication_status: the status of communication with
            the antenna via the tile.
        """
        self._tile_communication_status = communication_status
        self._update_joint_communication_status()

    def _update_joint_communication_status(self: AntennaComponentManager) -> None:
        """
        Update the status of communication with the antenna.

        The update takes into account communication via both tile and
        APIU.
        """
        for communication_status in [
            CommunicationStatus.DISABLED,
            CommunicationStatus.ESTABLISHED,
        ]:
            if (
                self._apiu_communication_status == communication_status
                and self._tile_communication_status == communication_status
            ):
                self.update_communication_status(communication_status)
                return
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)

    def _apiu_power_mode_changed(
        self: AntennaComponentManager,
        apiu_power_mode: PowerMode,
    ) -> None:
        with self._power_mode_lock:
            self._apiu_power_mode = apiu_power_mode

            if apiu_power_mode == PowerMode.UNKNOWN:
                self.update_component_power_mode(PowerMode.UNKNOWN)
            elif apiu_power_mode in [PowerMode.OFF, PowerMode.STANDBY]:
                self.update_component_power_mode(PowerMode.OFF)
            else:
                # power_mode is ON, wait for antenna power change
                pass
        self._review_power()

    def _antenna_power_mode_changed(
        self: AntennaComponentManager,
        antenna_power_mode: PowerMode,
    ) -> None:
        with self._power_mode_lock:
            self.update_component_power_mode(antenna_power_mode)
        self._review_power()

    def _apiu_component_fault_changed(
        self: AntennaComponentManager,
        faulty: bool,
    ) -> None:
        """
        Handle a change in antenna fault status as reported via the APIU.

        :param faulty: whether the antenna is faulting.
        """
        self._antenna_faulty_via_apiu = faulty
        self.update_component_fault(
            self._antenna_faulty_via_apiu or self._antenna_faulty_via_tile
        )

    def _tile_component_fault_changed(
        self: AntennaComponentManager,
        faulty: bool,
    ) -> None:
        """
        Handle a change in antenna fault status as reported via the tile.

        :param faulty: whether the antenna is faulting.
        """
        self._antenna_faulty_via_tile = faulty
        self.update_component_fault(
            self._antenna_faulty_via_apiu or self._antenna_faulty_via_tile
        )

    # @check_communicating
    def off(self: AntennaComponentManager) -> ResultCode | None:
        """
        Turn the antenna off.

        It does so by telling the APIU to turn the right antenna off.

        :return: a ResultCode, or None if there was nothing to do
        """
        with self._power_mode_lock:
            self._target_power_mode = PowerMode.OFF
        return self._review_power()

    def standby(self: AntennaComponentManager) -> None:
        """
        Put the antenna into standby mode; this is not implemented.

        This raises NotImplementedError because the antenna has no
        standby mode.

        :raises NotImplementedError: because the antenna has no standby
            mode.
        """
        raise NotImplementedError("Antenna has no standby mode.")

    # @check_communicating
    def on(self: AntennaComponentManager) -> ResultCode | None:
        """
        Turn the antenna on.

        :return: whether successful, or None if there was nothing to do.
        """
        with self._power_mode_lock:
            self._target_power_mode = PowerMode.ON
        return self._review_power()

    def _review_power(self: AntennaComponentManager) -> ResultCode | None:
        with self._power_mode_lock:
            if self._target_power_mode is None:
                return None
            if self.power_mode == self._target_power_mode:
                self._target_power_mode = None  # attained without any action needed
                return None

            if self._apiu_power_mode != PowerMode.ON:
                return ResultCode.QUEUED
            if self.power_mode == PowerMode.OFF and self._target_power_mode == PowerMode.ON:
                result_code = self._apiu_proxy.power_on()
                self._target_power_mode = None
                return result_code
            if self.power_mode == PowerMode.ON and self._target_power_mode == PowerMode.OFF:
                result_code = self._apiu_proxy.power_off()
                self._target_power_mode = None
                return result_code
            return ResultCode.QUEUED

    def reset(self: AntennaComponentManager) -> None:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :raises NotImplementedError: because the antenna's power mode is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError("Antenna cannot be reset.")

    @property
    def current(self: AntennaComponentManager) -> float:
        """
        Return the antenna's current.

        :return: the current of this antenna
        """
        return self._apiu_proxy.current

    @property
    def voltage(self: AntennaComponentManager) -> float:
        """
        Return the antenna's voltage.

        :return: the voltage of this antenna
        """
        return self._apiu_proxy.voltage

    @property
    def temperature(self: AntennaComponentManager) -> float:
        """
        Return the antenna's temperature.

        :return: the temperature of this antenna
        """
        return self._apiu_proxy.temperature
