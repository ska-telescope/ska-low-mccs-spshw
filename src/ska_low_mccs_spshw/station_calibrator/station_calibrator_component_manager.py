#  -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for station calibrators."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import tango
from ska_control_model import CommunicationStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.component import check_communicating
from ska_tango_base.executor import TaskExecutorComponentManager

__all__ = ["StationCalibratorComponentManager"]


class StationCalibratorComponentManager(TaskExecutorComponentManager):
    """A component manager for a station calibrator."""

    def __init__(  # pylint: disable=too-many-arguments
        self: StationCalibratorComponentManager,
        logger: logging.Logger,
        field_station_fqdn: str,
        calibration_store_fqdn: str,
        communication_state_callback: Callable[[CommunicationStatus], None],
        component_state_callback: Callable[..., None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param field_station_fqdn: the fqdn of this calibrator's field station
        :param calibration_store_fqdn: the fqdn of this calibrator's calibration store
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
        self._component_state_callback = component_state_callback
        self._field_station_fqdn = field_station_fqdn
        self._field_station_proxy: Optional[MccsDeviceProxy] = None
        self._calibration_store_fqdn = calibration_store_fqdn
        self._calibration_store_proxy: Optional[MccsDeviceProxy] = None
        self._outside_temperature: float = 25
        self.logger = logger

    def start_communicating(self: StationCalibratorComponentManager) -> None:
        """Establish communication with the StationCalibrator components."""
        if self.communication_state == CommunicationStatus.ESTABLISHED:
            return
        if self.communication_state == CommunicationStatus.DISABLED:
            self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)

        if self._field_station_proxy is None:
            try:
                self.logger.info(
                    f"attempting to form proxy with {self._field_station_fqdn}"
                )

                self._field_station_proxy = MccsDeviceProxy(
                    self._field_station_fqdn, self.logger, connect=True
                )
            except Exception as e:  # pylint: disable=broad-except
                self._update_component_state(fault=True)
                self.logger.error("Caught exception in forming proxy: %s", e)
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
                return

        try:
            self._field_station_proxy.add_change_event_callback(
                "outsideTemperature", self._field_station_outside_temperature_changed
            )
        except Exception as e:  # pylint: disable=broad-except
            self._update_component_state(fault=True)
            self.logger.error("Caught exception in attribute subscriptions: %s", e)
            self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
            return

        if self._calibration_store_proxy is None:
            try:
                self.logger.info(
                    f"attempting to form proxy with {self._calibration_store_fqdn}"
                )

                self._calibration_store_proxy = MccsDeviceProxy(
                    self._calibration_store_fqdn, self.logger, connect=True
                )
            except Exception as e:  # pylint: disable=broad-except
                self._update_component_state(fault=True)
                self.logger.error("Caught exception in forming proxy: %s", e)
                self._update_communication_state(CommunicationStatus.NOT_ESTABLISHED)
                return

        self._update_communication_state(CommunicationStatus.ESTABLISHED)

    def stop_communicating(self: StationCalibratorComponentManager) -> None:
        """Break off communication with the StationCalibrator components."""
        if self.communication_state == CommunicationStatus.DISABLED:
            return

        self._update_communication_state(CommunicationStatus.DISABLED)
        self._update_component_state(power=None, fault=None)

    def _field_station_outside_temperature_changed(
        self: StationCalibratorComponentManager,
        attr_name: str,
        attr_value: Any,
        attr_quality: tango.AttrQuality,
    ) -> None:
        self._outside_temperature = attr_value

    @check_communicating
    def get_calibration(
        self: StationCalibratorComponentManager,
        channel: int,
    ) -> list[float]:
        """
        Get a calibration from the calibration store.

        :param channel: the frequency channel to calibrate for

        :return: A list of calibration values
        """
        assert self._calibration_store_proxy is not None
        return self._calibration_store_proxy.GetSolution(
            channel, self._outside_temperature
        )
