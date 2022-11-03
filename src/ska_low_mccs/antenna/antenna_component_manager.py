#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements an component manager for an MCCS antenna Tango device."""
from __future__ import annotations

import functools
import logging
import threading
from typing import Any, Callable, Optional

import tango
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common.component import (
    DeviceComponentManager,
    MccsComponentManager,
    PowerSupplyProxyComponentManager,
    check_communicating,
    check_on,
)

__all__ = ["AntennaComponentManager"]


class _ApiuProxy(DeviceComponentManager, PowerSupplyProxyComponentManager):
    """A proxy to an antenna's APIU."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _ApiuProxy,
        fqdn: str,
        logical_antenna_id: int,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[
            [dict[str, Any], Optional[str]], None
        ],
    ) -> None:
        """
        Initialise a new APIU proxy instance.

        :param fqdn: the FQDN of the APIU
        :param logical_antenna_id: this antenna's id within the APIU
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes


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
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,  # type: ignore[arg-type]
        )

    def stop_communicating(self: _ApiuProxy) -> None:
        """Cease communicating with the APIU device."""
        super().stop_communicating()
        self._antenna_change_registered = False

    def reset(
        self: _ApiuProxy, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna's power state is
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
        if self.supplied_power_state == PowerState.ON:
            return None
        return self._power_up_antenna()

    def _power_up_antenna(self: _ApiuProxy) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], _) = self._proxy.PowerUpAntenna(self._logical_antenna_id)
        return result_code

    @check_communicating
    def power_off(self: _ApiuProxy) -> ResultCode | None:
        """
        Tell the APIU to power off this antenna.

        :return: a result code.
        """
        if self.supplied_power_state == PowerState.OFF:
            return None
        return self._power_down_antenna()

    def _power_down_antenna(self: _ApiuProxy) -> ResultCode:
        assert self._proxy is not None  # for the type checker
        ([result_code], _) = self._proxy.PowerDownAntenna(self._logical_antenna_id)
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
            self.update_supplied_power_state(PowerState.OFF)

    def _register_are_antennas_on_callback(self: _ApiuProxy) -> None:
        assert self._proxy is not None  # for the type checker
        self._proxy.add_change_event_callback(
            "areAntennasOn",
            self._antenna_power_state_changed,
            stateless=True,
        )
        self._antenna_change_registered = True

    def _antenna_power_state_changed(
        self: _ApiuProxy,
        event_name: str,
        event_value: list[bool],
        event_quality: tango.AttrQuality,
    ) -> None:
        """
        Handle change in antenna power state.

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
        power_state = (
            PowerState.ON
            if event_value[self._logical_antenna_id - 1]
            else PowerState.OFF
        )
        # self._component_state_changed_callback(
        #    {"power_state": power_state},
        #    fqdn=None
        # )
        # self.update_supplied_power_state(
        #     # PowerState.ON
        #     # if event_value[self._logical_antenna_id - 1]
        #     # else PowerState.OFF
        #     power_state
        # )
        if self._component_state_changed_callback is not None:
            self._component_state_changed_callback({"power_state": power_state})
        self.update_supplied_power_state(power_state)


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

    # pylint: disable=too-many-arguments
    def __init__(
        self: _TileProxy,
        fqdn: str,
        logical_antenna_id: int,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param fqdn: the FQDN of the Tile device
        :param logical_antenna_id: this antenna's id within the Tile
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        :raises AssertionError: if parameters are out of bounds
        """
        assert (
            logical_antenna_id > 0
        ), "An APIU's logical antenna id must be positive integer."
        self._logical_antenna_id = logical_antenna_id

        super().__init__(
            fqdn,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def off(
        self: _TileProxy, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the antenna off; this is not implemented.

        This raises NotImplementedError because the antenna's power state
        is not controlled via the Tile device; it is controlled via the
        APIU device.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna's power state is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power state is not controlled via Tile device."
        )

    def standby(
        self: _TileProxy, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the antenna into standby state; this is not implemented.

        This raises NotImplementedError because the antenna has no
        standby state; and because the antenna's power state is not
        controlled via the Tile device; it is controlled via the APIU
        device.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna's power state is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power state is not controlled via Tile device."
        )

    def on(
        self: _TileProxy, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Turn the antenna on; this is not implemented.

        This raises NotImplementedError because the antenna's power state
        is not controlled via the Tile device; it is controlled via the
        APIU device.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna's power state is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError(
            "Antenna power state is not controlled via Tile device."
        )

    def reset(
        self: _TileProxy, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :param task_callback: callback to be called when the status of
            the command changes

        :raises NotImplementedError: because the antenna's power state is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError("Antenna hardware is not resettable.")


# pylint: disable=too-many-instance-attributes
class AntennaComponentManager(MccsComponentManager):
    """
    A component manager for managing the component of an MCCS antenna Tango device.

    Since there is no way to monitor and control an antenna directly,
    this component manager simply proxies certain commands to the APIU
    and/or tile Tango device.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self: AntennaComponentManager,
        apiu_fqdn: str,
        apiu_antenna_id: int,
        tile_fqdn: str,
        tile_antenna_id: int,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
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
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be
            called when the component state changes
        """
        self._power_state_lock = threading.RLock()
        self._apiu_power_state = PowerState.UNKNOWN
        self._target_power_state: Optional[PowerState] = None

        self._apiu_communication_state: CommunicationStatus = (
            CommunicationStatus.DISABLED
        )
        self._tile_communication_state: CommunicationStatus = (
            CommunicationStatus.DISABLED
        )
        self._antenna_faulty_via_apiu = False
        self._antenna_faulty_via_tile = False

        self._apiu_fqdn = apiu_fqdn
        self._tile_fqdn = tile_fqdn

        self._apiu_proxy = _ApiuProxy(
            apiu_fqdn,
            apiu_antenna_id,
            logger,
            max_workers,
            self._apiu_communication_state_changed,
            functools.partial(component_state_changed_callback, fqdn=apiu_fqdn),
        )
        self._tile_proxy = _TileProxy(
            tile_fqdn,
            tile_antenna_id,
            logger,
            max_workers,
            self._tile_communication_state_changed,
            functools.partial(component_state_changed_callback, fqdn=tile_fqdn),
        )

        super().__init__(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
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

    def _apiu_communication_state_changed(
        self: AntennaComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the APIU.

        :param communication_state: the status of communication with
            the antenna via the APIU.
        """
        self._apiu_communication_state = communication_state
        self._update_joint_communication_state()

    def _tile_communication_state_changed(
        self: AntennaComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle a change in status of communication with the antenna via the tile.

        :param communication_state: the status of communication with
            the antenna via the tile.
        """
        self._tile_communication_state = communication_state
        self._update_joint_communication_state()

    def _update_joint_communication_state(
        self: AntennaComponentManager,
    ) -> None:
        """
        Update the status of communication with the antenna.

        The update takes into account communication via both tile and
        APIU.
        """
        for communication_state in [
            CommunicationStatus.DISABLED,
            CommunicationStatus.ESTABLISHED,
        ]:
            if (
                self._apiu_communication_state == communication_state
                and self._tile_communication_state == communication_state
            ):
                self.update_communication_state(communication_state)
                return
            self.update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

    def _apiu_power_state_changed(
        self: AntennaComponentManager,
        power_state: PowerState,
    ) -> None:
        with self._power_state_lock:
            self._apiu_power_state = power_state

            if power_state == PowerState.UNKNOWN:
                self.update_component_state({"power_state": PowerState.UNKNOWN})
            elif power_state in [PowerState.OFF, PowerState.STANDBY]:
                self.update_component_state({"power_state": PowerState.OFF})
            else:
                # power_state is ON, wait for antenna power change
                pass
        self._review_power()

    def _antenna_power_state_changed(
        self: AntennaComponentManager,
        antenna_power_state: PowerState,
    ) -> None:
        self.update_component_state({"power_state": antenna_power_state})
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
        self.update_component_state(
            {"fault": self._antenna_faulty_via_apiu or self._antenna_faulty_via_tile}
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
        self.update_component_state(
            {"fault": self._antenna_faulty_via_apiu or self._antenna_faulty_via_tile}
        )

    @property
    def power_state_lock(self: MccsComponentManager) -> threading.RLock:
        """
        Return the power state lock of this component manager.

        :return: the power state lock of this component manager.
        """
        return self._power_state_lock

    # TODO should the decorator be uncommented
    # @check_communicating
    def off(
        self: AntennaComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the off slow task.

        This method returns immediately after it submitted
        `self._off` for execution.

        :param task_callback: Update task state, defaults to None

        :returns: task status and message
        """
        return self.submit_task(self._off, task_callback=task_callback)

    def _off(
        self: AntennaComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn the antenna off.

        It does so by telling the APIU to turn the right antenna off.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        # Indicate that the task has started
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            with self._power_state_lock:
                self._target_power_state = PowerState.OFF
            # TODO should deal with the return code here
            self._review_power()
        # pylint: disable=broad-except
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")

        # Indicate that the task has completed
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="This slow task has completed"
            )

    def standby(
        self: AntennaComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Put the antenna into standby state; this is not implemented.

        This raises NotImplementedError because the antenna has no
        standby state.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna has no standby
            state.
        """
        raise NotImplementedError("Antenna has no standby state.")

    # TODO should the decorator be uncommented
    # @check_communicating
    def on(
        self: AntennaComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Submit the on slow task.

        This method returns immediately after it submitted
        `self._on` for execution.

        :param task_callback: Update task state, defaults to None

        :returns: task status and message
        """
        return self.submit_task(self._on, task_callback=task_callback)

    def _on(
        self: AntennaComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Turn the antenna on.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        # Indicate that the task has started
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            with self._power_state_lock:
                self._target_power_state = PowerState.ON
            # TODO should deal with the return code here
            self._review_power()
        # pylint: disable=broad-except
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")

        # Indicate that the task has completed
        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="This slow task has completed"
            )

    def _review_power(self: AntennaComponentManager) -> ResultCode | None:
        with self._power_state_lock:
            if self._target_power_state is None:
                return None
            if self.power_state == self._target_power_state:
                self._target_power_state = None  # attained without any action needed
                return None
            if self._apiu_power_state != PowerState.ON:
                return ResultCode.QUEUED
            if (
                self.power_state == PowerState.OFF
                and self._target_power_state == PowerState.ON
            ):
                result_code = self._apiu_proxy.power_on()
                self._target_power_state = None
                return result_code
            if (
                self.power_state == PowerState.ON
                and self._target_power_state == PowerState.OFF
            ):
                result_code = self._apiu_proxy.power_off()
                self._target_power_state = None
                return result_code
            return ResultCode.QUEUED

    def reset(
        self: AntennaComponentManager, task_callback: Optional[Callable] = None
    ) -> tuple[TaskStatus, str]:
        """
        Reset the antenna; this is not implemented.

        This raises NotImplementedError because the antenna is passive
        hardware and cannot meaningfully be reset.

        :param task_callback: Update task state, defaults to None

        :raises NotImplementedError: because the antenna's power state is
            not controlled via the Tile device; it is controlled via the
            APIU device.
        """
        raise NotImplementedError("Antenna cannot be reset.")

    def set_power_state(
        self: AntennaComponentManager,
        power_state: PowerState,
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Set the power state of the antenna.

        :param power_state: The desired power state
        :param fqdn: fqdn of the antenna

        :raises ValueError: unknown fqdn
        """
        with self._power_state_lock:
            if fqdn is None:
                self.power_state = power_state
            elif fqdn == self._tile_fqdn:
                self._tile_proxy.power_state = power_state
            elif fqdn == self._apiu_fqdn:
                self._apiu_proxy.power_state = power_state
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to tile or apiu"
                )

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
