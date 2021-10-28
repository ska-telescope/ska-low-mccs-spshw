# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for subarray beams."""
from __future__ import annotations

import logging
from typing import Any, Callable, cast

from ska_low_mccs.subarray_beam import SubarrayBeam
from ska_low_mccs.component import (
    check_communicating,
    CommunicationStatus,
    ObjectComponentManager,
)


__all__ = ["SubarrayBeamComponentManager"]


class SubarrayBeamComponentManager(ObjectComponentManager):
    """A component manager for a subarray beam."""

    def __init__(
        self: SubarrayBeamComponentManager,
        logger: logging.Logger,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        is_beam_locked_changed_callback: Callable[[bool], None],
        is_configured_changed_callback: Callable[[bool], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param is_beam_locked_changed_callback: a callback to be called
            when whether the beam is locked changes
        :param is_configured_changed_callback: callback to be called
            when whether this component manager is configured changes
        """
        self._is_beam_locked_changed_callback = is_beam_locked_changed_callback
        self._is_configured_changed_callback = is_configured_changed_callback

        super().__init__(
            SubarrayBeam(logger),
            logger,
            communication_status_changed_callback,
            None,
            None,
        )

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
            self._is_beam_locked_changed_callback
        )
        cast(SubarrayBeam, self._component).set_is_configured_changed_callback(
            self._is_configured_changed_callback
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
