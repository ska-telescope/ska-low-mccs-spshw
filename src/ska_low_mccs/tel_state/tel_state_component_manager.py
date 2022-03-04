# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for telescope state."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from ska_low_mccs.component import (
    CommunicationStatus,
    ObjectComponentManager,
    check_communicating,
)
from ska_low_mccs.tel_state import TelState

__all__ = ["TelStateComponentManager"]


class TelStateComponentManager(ObjectComponentManager):
    """A component manager for a transient buffer."""

    def __init__(
        self: TelStateComponentManager,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: the logger to be used by this object.
        :param push_change_event: method to call when the base classes
            want to send an event
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        """
        super().__init__(
            TelState(logger),
            logger,
            push_change_event,
            communication_status_changed_callback,
            None,
            None,
        )

    __PASSTHROUGH = [
        "elements_states",
        "observations_states",
        "algorithms",
        "algorithms_version",
    ]

    def __getattr__(
        self: TelStateComponentManager,
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
        self: TelStateComponentManager,
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
        self: TelStateComponentManager,
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
        self: TelStateComponentManager, name: str, value: Any
    ) -> None:
        """
        Set an attribute in the component (if we are communicating with it).

        :param name: name of the attribute to set.
        :param value: new value for the attribute
        """
        # This one-liner is only a method so that we can decorate it.
        setattr(self._component, name, value)
