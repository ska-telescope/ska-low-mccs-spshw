# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for subarray beams."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Optional, cast

from ska_tango_base.control_model import CommunicationStatus
from ska_tango_base.executor import TaskStatus

from ska_low_mccs.component import ObjectComponentManager, check_communicating
from ska_low_mccs.subarray_beam import SubarrayBeam

__all__ = ["SubarrayBeamComponentManager"]


class SubarrayBeamComponentManager(ObjectComponentManager):
    """A component manager for a subarray beam."""

    def __init__(
        self: SubarrayBeamComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param max_workers: no. of worker threads
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called
            when the component state changes
        """
        self._is_beam_locked_changed_callback = component_state_changed_callback
        self._is_configured_changed_callback = component_state_changed_callback

        super().__init__(
            SubarrayBeam(logger),
            logger,
            max_workers,
            communication_status_changed_callback,
            component_state_changed_callback,
        )
        self._component_state_changed_callback = component_state_changed_callback

    __PASSTHROUGH = [
        "subarray_id",
        "subarray_beam_id",
        "station_beam_ids",
        "station_ids",
        "logical_beam_id",
        "update_rate",
        "is_beam_locked",
        "channels",
        "antenna_weights",
        "desired_pointing",
        "phase_centre",
        "configure",
        "scan",
    ]

    def start_communicating(self: SubarrayBeamComponentManager) -> None:
        """Establish communication with the subarray beam."""
        super().start_communicating()
        cast(SubarrayBeam, self._component).set_is_beam_locked_changed_callback(
            self._component_state_changed_callback
        )
        cast(SubarrayBeam, self._component).set_is_configured_changed_callback(
            self._component_state_changed_callback
        )

    def stop_communicating(self: SubarrayBeamComponentManager) -> None:
        """Break off communication with the subarray beam."""
        super().stop_communicating()
        cast(SubarrayBeam, self._component).set_is_beam_locked_changed_callback(None)
        cast(SubarrayBeam, self._component).set_is_configured_changed_callback(None)

    def __getattr__(
        self: SubarrayBeamComponentManager,
        name: str,
        default_value: Any = None,
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in self.__PASSTHROUGH:
            return self._get_from_component(name)
        return default_value

    @check_communicating
    def _get_from_component(
        self: SubarrayBeamComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)

    def __setattr__(
        self: SubarrayBeamComponentManager,
        name: str,
        value: Any,
    ) -> Any:
        """
        Set an attribute on this tel state component manager.

        This is implemented to pass writes to certain attributes to the
        underlying component.

        :param name: name of the attribute for which the value is to be
            set
        :param value: new value of the attribute
        """
        if name in self.__PASSTHROUGH:
            self._set_in_component(name, value)
        else:
            super().__setattr__(name, value)

    @check_communicating
    def _set_in_component(
        self: SubarrayBeamComponentManager, name: str, value: Any
    ) -> None:
        """
        Set an attribute in the component (if we are communicating with it).

        :param name: name of the attribute to set.
        :param value: new value for the attribute
        """
        # This one-liner is only a method so that we can decorate it.
        setattr(self._component, name, value)

    def configure(
        self: SubarrayBeamComponentManager,
        argin: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the configure slow task.

        This method returns immediately after it is submitted for execution.

        :param argin: Json string containing args
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        config_dict = json.loads(argin)

        return self.submit_task(
            self._configure,
            args=[
                config_dict.get("subarray_beam_id"),
                config_dict.get("station_ids", []),
                config_dict.get("update_rate"),
                config_dict.get("channels", []),
                config_dict.get("sky_coordinates", []),
                config_dict.get("antenna_weights", []),
                config_dict.get("phase_centre", []),
            ],
            task_callback=task_callback,
        )

    def _configure(
        self,
        subarray_beam_id: int,
        station_ids: list[list[int]],
        update_rate: float,
        channels: list[list[int]],
        sky_coordinates: list[float],
        antenna_weights: list[float],
        phase_centre: list[float],
        task_callback: Callable,
        task_abort_event: threading.Event,
    ) -> None:
        """
        Implement :py:meth:`.MccsSubarrayBeam.Configure` command.

        :param subarray_beam_id: id of this subarray beam.
        :param station_ids: ids of stations in this subarray beam.
        :param update_rate: update rate of the scan.
        :param channels: ids of channels configured for this subarray beam.
        :param sky_coordinates: sky coordinates for this subarray beam to point at.
        :param antenna_weights: weights to use for the antennas.
        :param phase_centre: the phase centre of this subarray beam.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Task abort, defaults to None
        """
        task_callback(status=TaskStatus.IN_PROGRESS)

        # TODO Ben add config stuff here
        task_abort_event.wait(20)  # for testing purposes only

        if task_abort_event.is_set():
            task_callback(status=TaskStatus.ABORTED, result="This task aborted")
            return

        task_callback(
            status=TaskStatus.COMPLETED, result="Configure command completed OK"
        )

    def scan(self, task_callback: Optional[Callable] = None) -> tuple[TaskStatus, str]:
        """
        Submit the scan slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a task status and a unique id string to identify the command
        """
        return self.submit_task(self._scan, task_callback=task_callback)

    def _scan(
        self,
        scan_id: int,
        scan_time: float,
        task_callback: Callable,
        task_abort_event: threading.Event,
    ) -> None:
        """
        Implement :py:meth:`.MccsSubarrayBeam.Scan` command.

        :param scan_id: Scan ID to associte with the data.
        :param scan_time: Start time/ duration of the scan.
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Task abort, defaults to None
        """
        task_callback(status=TaskStatus.IN_PROGRESS)

        # TODO Ben add scan_id and scan_time here
        task_abort_event.wait(20)  # for testing purposes only

        if task_abort_event.is_set():
            task_callback(status=TaskStatus.ABORTED, result="This task aborted")
            return

        task_callback(
            status=TaskStatus.COMPLETED, result="Configure command completed OK"
        )
