# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements component management for transient buffers."""
from __future__ import annotations

import logging
from typing import Any, Callable

from ska_low_mccs.transient_buffer import TransientBuffer
from ska_low_mccs.component import (
    check_communicating,
    CommunicationStatus,
    ObjectComponentManager,
)


__all__ = ["TransientBufferComponentManager"]


class TransientBufferComponentManager(ObjectComponentManager):
    """A component manager for a transient buffer."""

    def __init__(
        self: TransientBufferComponentManager,
        logger: logging.Logger,
        push_change_event,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        super().__init__(
            TransientBuffer(logger),
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            None,
        )

    def __getattr__(
        self: TransientBufferComponentManager,
        name: str,
        default_value: Any = None,
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the transient buffer component. The intent is to avoid having
        to implement a whole lot of methods that simply call the
        corresponding method on the simulator. The only reason this is
        possible is because the component has much the same interface as
        its component manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in [
            "station_id",
            "transient_buffer_job_id",
            "resampling_bits",
            "n_stations",
            "transient_frequency_window",
            "station_ids",
        ]:
            return self._get_from_component(name)
        return default_value

    @check_communicating
    def _get_from_component(
        self: TransientBufferComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)
