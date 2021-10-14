# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for station beams."""
from __future__ import annotations

import logging
from typing import Callable, Optional, cast
from typing_extensions import Literal

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, PowerMode

from ska_low_mccs.component import (
    CommunicationStatus,
    DeviceComponentManager,
    MccsComponentManager,
    MessageQueue,
    check_communicating,
    check_on,
    enqueue,
)


__all__ = ["StationBeamComponentManager"]


class _StationProxy(DeviceComponentManager):
    """A station beam's proxy to its station."""

    @check_communicating
    @check_on
    @enqueue
    def apply_pointing(self: _StationProxy, pointing_args: list[float]) -> ResultCode:
        """
        Apply the provided pointing arguments to the station.

        :param pointing_args: the pointing arguments to be applied.

        :return: a result code.
        """
        assert self._proxy is not None
        (result_code, _) = self._proxy.ApplyPointing(pointing_args)
        return result_code


class StationBeamComponentManager(MccsComponentManager):
    """A component manager for a station beam."""

    def __init__(
        self: StationBeamComponentManager,
        beam_id: int,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        message_queue_size_callback: Callable[[int], None],
        is_beam_locked_changed_callback: Callable[[bool], None],
        station_health_changed_callback: Callable[[Optional[HealthState]], None],
        station_fault_changed_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param beam_id: the beam id of this station beam
        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param message_queue_size_callback: callback to be called when
            the size of the message queue changes
        :param is_beam_locked_changed_callback: a callback to be called
            when whether the beam is locked changes
        :param station_health_changed_callback: a callback to be called
            when the health of this station beam's station changes.
        :param station_fault_changed_callback: a callback to be called
            when the fault state of this station beam's station changes.
        """
        self._subarray_id = 0
        self._beam_id = beam_id
        self._station_id = 0
        self._logical_beam_id = 0
        self._update_rate = 0.0
        self._is_beam_locked = False

        self._channels: list[list[int]] = []
        self._desired_pointing: list[float] = []
        self._pointing_delay: list[float] = []
        self._pointing_delay_rate: list[float] = []
        self._antenna_weights: list[float] = []
        self._phase_centre: list[float] = []

        self._station_fqdn: Optional[str] = None
        self._station_proxy: Optional[_StationProxy] = None

        self._is_beam_locked_changed_callback = is_beam_locked_changed_callback
        self._station_health_changed_callback = station_health_changed_callback
        self._station_fault_changed_callback = station_fault_changed_callback

        self._message_queue = MessageQueue(
            logger,
            queue_size_callback=message_queue_size_callback,
        )

        super().__init__(
            logger,
            communication_status_changed_callback,
            None,
            None,
        )

    def start_communicating(self: StationBeamComponentManager) -> None:
        """Establish communication with the component."""
        super().start_communicating()

        if self._station_proxy is None:
            self.update_communication_status(CommunicationStatus.ESTABLISHED)
        else:
            self._station_proxy.start_communicating()

    def stop_communicating(self: StationBeamComponentManager) -> None:
        """Cease monitoring the component, and break off all communication with it."""
        super().stop_communicating()

        if self._station_proxy is not None:
            self._station_proxy.stop_communicating()

    def power_mode(self: StationBeamComponentManager) -> Literal[PowerMode.ON]:
        """
        Return the power mode to the station beam.

        The station beam is an always-on device, so this method always
        return ON.

        :return: the power mode of the station beam.
        """
        return PowerMode.ON

    def off(self: StationBeamComponentManager) -> None:
        """
        Turn off the station beam.

        :raises NotImplementedError: because station beam is an
            always-on device.
        """
        raise NotImplementedError("MccsStationBeam is an always-on device.")

    def standby(self: StationBeamComponentManager) -> None:
        """
        Put the station beam into standby mode.

        :raises NotImplementedError: because station beam is an
            always-on device.
        """
        raise NotImplementedError("MccsStationBeam is an always-on device.")

    def on(self: StationBeamComponentManager) -> None:
        """
        Turn on the station beam.

        :raises NotImplementedError: because station beam is an
            always-on device.
        """
        raise NotImplementedError("MccsStationBeam is an always-on device.")

    def _device_communication_status_changed(
        self: StationBeamComponentManager,
        communication_status: CommunicationStatus,
    ) -> None:
        if communication_status == CommunicationStatus.ESTABLISHED:
            self.update_communication_status(CommunicationStatus.ESTABLISHED)
        else:
            self.update_communication_status(CommunicationStatus.NOT_ESTABLISHED)

    @property
    def station_fqdn(self: StationBeamComponentManager) -> Optional[str]:
        """
        Return the station FQDN.

        If the station FQDN is not set, return the empty string.

        :return: the station FQDN
        """
        return self._station_fqdn

    @station_fqdn.setter
    def station_fqdn(self: StationBeamComponentManager, value: Optional[str]) -> None:
        """
        Set the station FQDN.

        The string must be either a valid FQDN for a station, or the empty string.

        :param value: the new station FQDN, or the empty string
        """
        communicating = self.communication_status != CommunicationStatus.DISABLED

        if self._station_fqdn != value:
            self._station_fqdn = value

            if communicating and self._station_proxy is not None:
                self._station_proxy.stop_communicating()
                self._station_proxy = None
                if self._station_fqdn is None:
                    self.update_communication_status(CommunicationStatus.ESTABLISHED)
            if self._station_fqdn is not None:
                self._station_proxy = _StationProxy(
                    self._station_fqdn,
                    self._message_queue,
                    self.logger,
                    self._device_communication_status_changed,
                    None,
                    self._station_fault_changed_callback,
                    self._station_health_changed_callback,
                )
                if communicating:
                    self._station_proxy.start_communicating()

    @property
    def beam_id(self: StationBeamComponentManager) -> int:
        """
        Return the station beam id.

        :return: the station beam id
        """
        return self._beam_id

    @property
    def subarray_id(self: StationBeamComponentManager) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self._subarray_id

    @subarray_id.setter
    def subarray_id(self: StationBeamComponentManager, value: int) -> None:
        """
        Set the Subarray ID.

        :param value: the new subarray id
        """
        self._subarray_id = value

    @property
    def station_id(self: StationBeamComponentManager) -> int:
        """
        Return the station id.

        :return: the station ids
        """
        return self._station_id

    @station_id.setter
    def station_id(self: StationBeamComponentManager, value: int) -> None:
        """
        Set the station id.

        :param value: the new station id
        """
        self._station_id = value

    @property
    def logical_beam_id(self: StationBeamComponentManager) -> int:
        """
        Return the logical beam id.

        :return: the logical beam id
        """
        return self._logical_beam_id

    @logical_beam_id.setter
    def logical_beam_id(self: StationBeamComponentManager, value: int) -> None:
        """
        Set the logical beam id.

        :param value: the new logical beam id
        """
        self._logical_beam_id = value

    @property
    def update_rate(self: StationBeamComponentManager) -> float:
        """
        Return the update rate.

        :return: the update rate
        """
        return self._update_rate

    @property
    def is_beam_locked(self: StationBeamComponentManager) -> bool:
        """
        Return whether the beam is locked.

        :return: whether the beam is locked
        """
        return self._is_beam_locked

    @is_beam_locked.setter
    def is_beam_locked(self: StationBeamComponentManager, value: bool) -> None:
        """
        Set whether the beam is locked.

        :param value: new value for whether the beam is locked
        """
        if self._is_beam_locked != value:
            self._is_beam_locked = value
            if self._is_beam_locked_changed_callback is not None:
                self._is_beam_locked_changed_callback(value)

    @property
    def channels(self: StationBeamComponentManager) -> list[list[int]]:
        """
        Return the ids of the channels configured for this station beam.

        :return: the ids of the channels configured for this subarray
            beam.
        """
        return [list(i) for i in self._channels]  # deep copy

    @property
    def antenna_weights(self: StationBeamComponentManager) -> list[float]:
        """
        Return the antenna weights.

        :return: the antenna weights
        """
        return list(self._antenna_weights)

    @property
    def desired_pointing(self: StationBeamComponentManager) -> list[float]:
        """
        Return the desired pointing.

        :return: the desired pointing
        """
        return self._desired_pointing

    @desired_pointing.setter
    def desired_pointing(self: StationBeamComponentManager, value: list[float]) -> None:
        """
        Set the desired pointing.

        :param value: the new desired pointing
        """
        self._desired_pointing = value

    @property
    def pointing_delay(self: StationBeamComponentManager) -> list[float]:
        """
        Return the pointing delay.

        :return: the pointing delay
        """
        return self._pointing_delay

    @pointing_delay.setter
    def pointing_delay(self: StationBeamComponentManager, value: list[float]) -> None:
        """
        Set the pointing delay.

        :param value: the new pointing delay
        """
        self._pointing_delay = value

    @property
    def pointing_delay_rate(self: StationBeamComponentManager) -> list[float]:
        """
        Return the pointing delay rate.

        :return: the pointing delay rate
        """
        return self._pointing_delay_rate

    @pointing_delay_rate.setter
    def pointing_delay_rate(
        self: StationBeamComponentManager, value: list[float]
    ) -> None:
        """
        Set the pointing delay rate.

        :param value: the new pointing delay rate
        """
        self._pointing_delay_rate = value

    @property
    def phase_centre(self: StationBeamComponentManager) -> list[float]:
        """
        Return the phase centre.

        :return: the phase centre
        """
        return self._phase_centre

    def configure(
        self: StationBeamComponentManager,
        beam_id: int,
        station_id: int,
        update_rate: float,
        channels: list[list[int]],
        desired_pointing: list[float],
        antenna_weights: list[float],
        phase_centre: list[float],
    ) -> ResultCode:
        """
        Configure this station beam for scanning.

        :param beam_id: the id of this station beam
        :param station_id: the ids of participating stations
        :param update_rate: the update rate of the scan
        :param channels: ids of channels configured for this station beam
        :param desired_pointing: sky coordinates for this beam to point at
        :param antenna_weights: weights to use for the antennas
        :param phase_centre: the phase centre

        :return: a result code
        """
        self._beam_id = beam_id
        self._station_id = station_id
        self._channels = list(list(i) for i in channels)  # deep copy
        self._update_rate = update_rate
        self._desired_pointing = list(desired_pointing)
        self._antenna_weights = list(antenna_weights)
        self._phase_centre = list(phase_centre)
        # TODO: forward relevant configuration to participating stations
        return ResultCode.OK

    @check_communicating
    def apply_pointing(self: StationBeamComponentManager) -> ResultCode:
        """
        Apply the configured pointing to this station beam's station.

        :return: a result code
        """
        zipped_delays_and_rates = [
            item
            for pair in zip(self.pointing_delay, self.pointing_delay_rate + [0])
            for item in pair
        ]
        station_pointing_args = [
            cast(float, self.logical_beam_id)
        ] + zipped_delays_and_rates

        assert self._station_proxy is not None
        return self._station_proxy.apply_pointing(station_pointing_args)
