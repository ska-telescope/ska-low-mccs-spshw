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
    "AlarmAttributeManager",
]


class AttributeManager:
    """The Base AttributeManager."""

    def __init__(
        self: AttributeManager,
        value_time_quality_callback: Callable,
        initial_value: Any = None,
        alarm_handler: None | Callable = None,
        converter: Callable | None = None,
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
        :param converter: a optional function to conver the value coming in.
        """
        self._converter = converter
        self.alarm_handler = alarm_handler
        self._initial_value = initial_value
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
        value_changed = value != self._value
        self._last_update = time.time()
        if value is None:
            self._quality = tango.AttrQuality.ATTR_INVALID
        else:
            self._value = self._converter(value) if self._converter else value
            self.update_quality()
        if post:
            self.notify(value_changed)

    def mark_stale(self: AttributeManager) -> None:
        """Mark attribute as stale."""
        if (
            self._initial_value == self._value
            or self._quality == tango.AttrQuality.ATTR_INVALID
        ):
            return
        self._last_update = time.time()
        self._quality = tango.AttrQuality.ATTR_INVALID
        if self._value is not None:
            self.notify(True)

    def update_quality(self: AttributeManager) -> None:
        """Update the attribute quality factor."""
        self._quality = tango.AttrQuality.ATTR_VALID

    def read(self: AttributeManager) -> Any:
        """
        Return the attribute value.

        :return: A tuple with value, last_updated and quaility.
            Or None if attribute has not had an update yet.
        """
        if self._value is not None:
            return self._value, self._last_update, self._quality
        return self._value

    def notify(self: AttributeManager, value_changed: bool) -> None:
        """
        Notify callback with value.

        :param value_changed: a flag representing if the value changed
            from the previous value.
        """
        if value_changed:
            self._value_time_quality_callback(
                self._value, self._last_update, self._quality
            )
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


class AlarmAttributeManager(AttributeManager):
    """
    An AttributeManager for alarm attribute.

    The quality of the alarm attribute is specific to custom
    values. This manager will evaluate the attribute quality
    against these values.
    """

    def __init__(
        self: AlarmAttributeManager,
        value_time_quality_callback: Callable,
        initial_value: bool | None = None,
        alarm_handler: None | Callable = None,
    ) -> None:
        """
        Initialise a new AlarmAttributeManager.

        :param initial_value: The initial value for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        :param alarm_handler: A hook to call upon alarming.
        """
        super().__init__(
            value_time_quality_callback,
            initial_value=initial_value,
            alarm_handler=alarm_handler,
        )

    def _is_valid(self: AlarmAttributeManager, value: dict[str, int]) -> bool:
        """
        Is the value a valid input.

        :param value: the value to check if valid.

        :returns: True is the value is valid.
        """
        return isinstance(value, dict)

    def update_quality(self: AlarmAttributeManager) -> None:
        """Update attribute quality."""
        if not self._is_valid(self._value):
            self._quality = tango.AttrQuality.ATTR_INVALID
            return
        if any(alarm_value == 2 for alarm_value in self._value.values()):
            self._quality = tango.AttrQuality.ATTR_ALARM
        elif any(alarm_value == 1 for alarm_value in self._value.values()):
            self._quality = tango.AttrQuality.ATTR_WARNING
        else:
            self._quality = tango.AttrQuality.ATTR_VALID
