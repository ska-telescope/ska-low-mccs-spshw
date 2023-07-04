#  -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for station calibrators."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Optional

import tango
from ska_control_model import CommunicationStatus, ResultCode
from ska_low_mccs_common.component import DeviceComponentManager
from ska_tango_base.base import check_communicating
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = ["StationCalibratorComponentManager"]

DevVarLongStringArrayType = tuple[list[ResultCode], list[str]]


class _FieldStationProxy(DeviceComponentManager):
    """A proxy to a subrack, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _FieldStationProxy,
        name: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
        outside_temperature_changed_callback: Callable[[str, Any, Any], None],
    ) -> None:
        """
        Initialise a new instance.

        :param name: the name of the device
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param component_state_callback: callback to be
            called when the component state changes
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        :param outside_temperature_changed_callback: callback to be called when a
            Field Station outsideTemperature change event is received
        """
        self._connecting = False
        self._outside_temperature_changed_callback = (
            outside_temperature_changed_callback
        )

        super().__init__(
            name,
            logger,
            max_workers,
            communication_state_callback,
            component_state_callback,
        )

    def start_communicating(self: _FieldStationProxy) -> None:
        """Establish communication with the station components."""
        self._connecting = True
        super().start_communicating()

    def _device_state_changed(
        self: _FieldStationProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if self._connecting and event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            self._connecting = False
        super()._device_state_changed(event_name, event_value, event_quality)

    def subscribe_to_attributes(self: _FieldStationProxy) -> None:
        """Subscribe to change events in field station attributes of interest."""
        assert self._proxy is not None
        if (
            "outsideTemperature"
            not in self._proxy._change_event_subscription_ids.keys()
        ):
            self._proxy.add_change_event_callback(
                "outsideTemperature", self._outside_temperature_changed_callback
            )


class _CalibrationStoreProxy(DeviceComponentManager):
    """A proxy to a subrack, for a station to use."""

    # pylint: disable=too-many-arguments
    def __init__(
        self: _CalibrationStoreProxy,
        name: str,
        logger: logging.Logger,
        max_workers: int,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param name: the name of the device
        :param logger: the logger to be used by this object.
        :param max_workers: the maximum worker threads for the slow commands
            associated with this component manager.
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_callback: callback to be
            called when the component state changes
        """
        self._connecting = False

        super().__init__(
            name,
            logger,
            max_workers,
            communication_state_callback,
            component_state_callback,
        )

    def start_communicating(self: _CalibrationStoreProxy) -> None:
        self._connecting = True
        super().start_communicating()

    def _device_state_changed(
        self: _CalibrationStoreProxy,
        event_name: str,
        event_value: tango.DevState,
        event_quality: tango.AttrQuality,
    ) -> None:
        if self._connecting and event_value == tango.DevState.ON:
            assert self._proxy is not None  # for the type checker
            self._connecting = False
        super()._device_state_changed(event_name, event_value, event_quality)


# pylint: disable=too-many-instance-attributes
class StationCalibratorComponentManager(TaskExecutorComponentManager):
    """A component manager for a station calibrator."""

    def __init__(  # pylint: disable=too-many-arguments
        self: StationCalibratorComponentManager,
        logger: logging.Logger,
        field_station_name: str,
        calibration_store_name: str,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param field_station_name: the name of this calibrator's field station
        :param calibration_store_name: the name of this calibrator's calibration store
        :param communication_state_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes.
        :param component_state_callback: callback to be called when the
            component state changes.
        """
        super().__init__(
            logger,
            communication_state_callback,
            component_state_callback,
            max_workers=1,
            power=None,
            fault=None,
        )
        self._device_communication_state_lock = threading.Lock()
        self._communication_states = {
            name: CommunicationStatus.DISABLED
            for name in [field_station_name, calibration_store_name]
        }

        self._component_state_callback: Callable[..., None] = component_state_callback

        self._field_station_name = field_station_name
        self._field_station_proxy = _FieldStationProxy(
            field_station_name,
            logger,
            1,
            self._field_station_communication_state_changed,
            self._field_station_state_changed,
            self._field_station_outside_temperature_changed,
        )

        self._calibration_store_name = calibration_store_name
        self._calibration_store_proxy = _CalibrationStoreProxy(
            calibration_store_name,
            logger,
            1,
            self._calibration_store_communication_state_changed,
            self._calibration_store_state_changed,
        )

        self._outside_temperature: Optional[float] = None
        self.logger = logger

    def start_communicating(self: StationCalibratorComponentManager) -> None:
        """Establish communication with the StationCalibrator components."""
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        self._field_station_proxy.start_communicating()
        self._calibration_store_proxy.start_communicating()

    def stop_communicating(self: StationCalibratorComponentManager) -> None:
        """Break off communication with the StationCalibrator components."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)

    def _field_station_state_changed(
        self: StationCalibratorComponentManager, **kwargs: Any
    ) -> None:
        self._component_state_callback(**kwargs, device_name=self._field_station_name)

    def _calibration_store_state_changed(
        self: StationCalibratorComponentManager, **kwargs: Any
    ) -> None:
        self._component_state_callback(
            **kwargs, device_name=self._calibration_store_name
        )

    def _field_station_communication_state_changed(
        self: StationCalibratorComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        if communication_state == CommunicationStatus.ESTABLISHED:
            self._field_station_proxy.subscribe_to_attributes()
        # Only update state on change.
        if communication_state != self._communication_state:
            self._device_communication_state_changed(
                self._field_station_name, communication_state
            )

    def _calibration_store_communication_state_changed(
        self: StationCalibratorComponentManager,
        communication_state: CommunicationStatus,
    ) -> None:
        if communication_state != self._communication_state:
            self._device_communication_state_changed(
                self._calibration_store_name, communication_state
            )

    def _device_communication_state_changed(
        self: StationCalibratorComponentManager,
        fqdn: str,
        communication_state: CommunicationStatus,
    ) -> None:
        # Many callback threads could be hitting this method at the same time, so it's
        # possible (likely) that the GIL will suspend a thread between checking if it
        # need to update, and actually updating. This leads to callbacks appearing out
        # of order, which breaks tests. Therefore we need to serialise access.
        with self._device_communication_state_lock:
            self._communication_states[fqdn] = communication_state

            if self.communication_state == CommunicationStatus.DISABLED:
                return

            if CommunicationStatus.DISABLED in self._communication_states.values():
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            elif (
                CommunicationStatus.NOT_ESTABLISHED
                in self._communication_states.values()
            ):
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            else:
                self._update_communication_state(CommunicationStatus.ESTABLISHED)

    def _field_station_outside_temperature_changed(
        self: StationCalibratorComponentManager,
        attr_name: str,
        attr_value: Any,
        attr_quality: tango.AttrQuality,
    ) -> None:
        self.logger.info(
            "Outside temperature changed from "
            f"{self._outside_temperature} to {attr_value}"
        )
        self._outside_temperature = attr_value

    @check_communicating
    def get_calibration(
        self: StationCalibratorComponentManager,
        channel: int,
    ) -> list[float]:
        """
        Get a calibration from the calibration store.

        :param channel: the frequency channel to calibrate for

        :raises ValueError: if the outside temperature has not been read yet
        :return: A list of calibration values
        """
        assert self._calibration_store_proxy._proxy is not None
        if self._outside_temperature is None:
            self.logger.error("GetCalibration failed - outside temperature is None")
            raise ValueError("Outside temperature has not been read yet")
        return self._calibration_store_proxy._proxy.GetSolution(
            json.dumps(
                {
                    "frequency_channel": channel,
                    "outside_temperature": self._outside_temperature,
                }
            )
        )
