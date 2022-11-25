# type: ignore
#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains a placeholder for a subarray beam component."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from ska_control_model import CommunicationStatus, ResultCode
from ska_low_mccs_common.component import ObjectComponent

__all__ = ["SubarrayBeam"]


# pylint: disable=too-many-instance-attributes
class SubarrayBeam(ObjectComponent):
    """A placeholder for a subarray beam component."""

    def __init__(
        self: SubarrayBeam,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this component to use
        :param max_workers: no of worker threads
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        self._logger = logger

        self._is_beam_locked_changed_callback = component_state_changed_callback
        self._is_configured = False
        self._is_configured_changed_callback = component_state_changed_callback

        self._subarray_id = 0
        self._subarray_beam_id = 0
        self._station_ids: list[int] = []
        self._logical_beam_id = 0
        self._update_rate = 0.0
        self._is_beam_locked = False

        self._channels: list[list[int]] = []
        self._desired_pointing: list[float] = []
        self._antenna_weights: list[float] = []
        self._phase_centre: list[float] = []
        self._scan_id: int = 0
        self._scan_time: int = 0

    def set_is_beam_locked_changed_callback(
        self: SubarrayBeam,
        is_beam_locked_changed_callback: Optional[Callable] = None,
    ) -> None:
        """
        Set a callback to be called if whether this subarray beam is locked changes.

        :param is_beam_locked_changed_callback: the callback to be
            called if whether this subarray beam is locked changes, or
            None to remove the callback
        """
        self._is_beam_locked_changed_callback = is_beam_locked_changed_callback

    def set_is_configured_changed_callback(
        self: SubarrayBeam,
        is_configured_changed_callback: Optional[Callable] = None,
    ) -> None:
        """
        Set a callback to be called if whether this subarray beam is configured changes.

        :param is_configured_changed_callback: the callback to be called
            if whether this subarray beam is configured changes, or None
            to remove the callback
        """
        self._is_configured_changed_callback = is_configured_changed_callback
        if self._is_configured_changed_callback is not None:
            self._is_configured_changed_callback(
                {"configured_changed": self._is_configured}
            )

    @property
    def subarray_id(self: SubarrayBeam) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self._subarray_id

    @property
    def subarray_beam_id(self: SubarrayBeam) -> int:
        """
        Return the subarray beam id.

        :return: the subarray beam id
        """
        return self._subarray_beam_id

    @property
    def station_ids(self: SubarrayBeam) -> list[int]:
        """
        Return the station ids.

        :return: the station ids
        """
        return list(self._station_ids)

    @station_ids.setter
    def station_ids(self: SubarrayBeam, value: list[int]) -> None:
        """
        Set the station ids.

        :param value: the new station ids
        """
        self._station_ids = value

    @property
    def logical_beam_id(self: SubarrayBeam) -> int:
        """
        Return the logical beam id.

        :return: the logical beam id
        """
        return self._logical_beam_id

    @logical_beam_id.setter
    def logical_beam_id(self: SubarrayBeam, value: int) -> None:
        """
        Set the logical beam id.

        :param value: the new logical beam id
        """
        self._logical_beam_id = value

    @property
    def update_rate(self: SubarrayBeam) -> float:
        """
        Return the update rate.

        :return: the update rate
        """
        return self._update_rate

    @property
    def is_beam_locked(self: SubarrayBeam) -> bool:
        """
        Return whether the beam is locked.

        :return: whether the beam is locked
        """
        return self._is_beam_locked

    @is_beam_locked.setter
    def is_beam_locked(self: SubarrayBeam, value: bool) -> None:
        """
        Set whether the beam is locked.

        :param value: new value for whether the beam is locked
        """
        if self._is_beam_locked != value:
            self._is_beam_locked = value
            if self._is_beam_locked_changed_callback is not None:
                self._is_beam_locked_changed_callback({"beam_locked": value})

    @property
    def channels(self: SubarrayBeam) -> list[list[int]]:
        """
        Return the ids of the channels configured for this subarray beam.

        :return: the ids of the channels configured for this subarray
            beam.
        """
        return [list(i) for i in self._channels]  # deep copy

    @property
    def antenna_weights(self: SubarrayBeam) -> list[float]:
        """
        Return the antenna weights.

        :return: the antenna weights
        """
        return list(self._antenna_weights)

    @property
    def desired_pointing(self: SubarrayBeam) -> list[float]:
        """
        Return the desired pointing.

        :return: the desired pointing
        """
        return self._desired_pointing

    @desired_pointing.setter
    def desired_pointing(self: SubarrayBeam, value: list[float]) -> None:
        """
        Set the desired pointing.

        :param value: the new desired pointing
        """
        self._desired_pointing = value

    @property
    def phase_centre(self: SubarrayBeam) -> list[float]:
        """
        Return the phase centre.

        :return: the phase centre
        """
        return self._phase_centre

    # pylint: disable=too-many-arguments
    def configure(
        self: SubarrayBeam,
        subarray_beam_id: int,
        station_ids: list[int],
        update_rate: float,
        channels: list[list[int]],
        desired_pointing: list[float],
        antenna_weights: list[float],
        phase_centre: list[float],
    ) -> ResultCode:
        """
        Configure this subarray beam for scanning.

        :param subarray_beam_id: the id of this subarray beam
        :param station_ids: the ids of participating stations
        :param update_rate: the update rate of the scan
        :param channels: ids of channels configured for this subarray beam
        :param desired_pointing: sky coordinates for this beam to point at
        :param antenna_weights: weights to use for the antennas
        :param phase_centre: the phase centre

        :return: a result code
        """
        self._subarray_beam_id = subarray_beam_id
        self._station_ids = list(station_ids)

        self._channels = list(list(i) for i in channels)  # deep copy
        self._update_rate = update_rate
        self._desired_pointing = list(desired_pointing)
        self._antenna_weights = list(antenna_weights)
        self._phase_centre = list(phase_centre)
        # TODO: forward relevant configuration to participating stations

        self._update_is_configured(True)
        return ResultCode.OK

    def _update_is_configured(
        self: SubarrayBeam,
        is_configured: bool,
    ) -> None:
        if self._is_configured != is_configured:
            self._is_configured = is_configured
            if self._is_configured_changed_callback is not None:
                self._is_configured_changed_callback(
                    {"configured_changed": is_configured}
                )

    def scan(
        self: SubarrayBeam,
        scan_id: int,
        scan_time: float,
    ) -> ResultCode:
        """
        Start scanning.

        :param scan_id: the id of the scan
        :param scan_time: the start time, or the duration, of the scan?

        :todo: clarify meaning of "scan_time" argument

        :return: a result code
        """
        self._scan_id = scan_id
        self._scan_time = scan_time
        # TODO: Forward scan command and parameters to all the subservient Stations
        return ResultCode.OK
