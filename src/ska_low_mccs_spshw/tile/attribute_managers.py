#  -*- coding: utf-8 -*
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A collection of AttributeManagers to serve the TANGO attribute."""
from __future__ import annotations

import time
from typing import Any, Callable

import tango

__all__ = [
    "AttributeManager",
    "BoolAttributeManager",
]


class AttributeManager:
    """The Base AttributeManager."""

    def __init__(
        self: AttributeManager,
        value_time_quality_callback: Callable,
        initial_value: Any = None,
        alarm_handler: None | Callable = None,
    ) -> None:
        """
        Initialise a new AttributeManager.

        The AttributeManager will:
         - Hold a cached value of the last update.
         - Calculate a quality factor from the value.
         - post the attribute cache to listeners upon an update.

        :param initial_value: The initial value for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor upon update.
        :param alarm_handler: A hook to call when in ALARM.
        """
        self.alarm_handler = alarm_handler
        self._value = initial_value
        self._quality = (
            tango.AttrQuality.ATTR_INVALID
            if initial_value is None
            else tango.AttrQuality.ATTR_VALID
        )
        self._last_update = time.time()
        self._value_time_quality_callback = value_time_quality_callback

    def update(self: AttributeManager, value: Any, post: bool = True) -> None:
        """
        Update attribute manager with a new value.

        :param value: the value we want to update attribute with.
        :param post: Optional flag to post an update.
        """
        self._value = value
        self._last_update = time.time()
        if self._value is None:
            self._quality = tango.AttrQuality.ATTR_INVALID
        else:
            self.update_quality()
        if post:
            self.notify()

    def update_quality(self: AttributeManager) -> None:
        """Update the attribute quality factor."""
        self._quality = tango.AttrQuality.ATTR_VALID

    def read(self: AttributeManager) -> Any:
        """
        Return the attribute value.

        :return: the attribute value.
        """
        return self._value, self._last_update, self._quality

    def notify(self: AttributeManager) -> None:
        """Notify callback with value."""
        self._value_time_quality_callback(*self.read())
        if self.alarm_handler is not None:
            self.alarm_handler()


class BoolAttributeManager(AttributeManager):
    """An AttributeManager for Booleans."""

    def __init__(
        self: BoolAttributeManager,
        value_time_quality_callback: Callable,
        initial_value: bool | None = None,
        alarm_flag: str | None = None,
        alarm_handler: None | Callable = None,
    ) -> None:
        """
        Initialise a new BoolAttributeManager.

        :param initial_value: The initial value for this attribute.
        :param alarm_flag: A flag to represent if this attribute alarms
            on `HIGH` or `LOW`.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        :param alarm_handler: A hook to call upon alarming.
        """
        super().__init__(
            value_time_quality_callback,
            initial_value=initial_value,
            alarm_handler=alarm_handler,
        )

        self._alarm_on_true: bool | None
        flag = None if alarm_flag is None else alarm_flag.lower()
        match flag:
            case "high":
                self._alarm_on_true = True
            case "low":
                self._alarm_on_true = False
            case _:
                self._alarm_on_true = None

    def update_quality(self: BoolAttributeManager) -> None:
        """Update attribute quality."""
        self._quality = (
            tango.AttrQuality.ATTR_ALARM
            if self._alarm_on_true is self._value
            else tango.AttrQuality.ATTR_VALID
        )
