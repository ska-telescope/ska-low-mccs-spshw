#  -*- coding: utf-8 -*
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A collection of AttributeManagers to serve the TANGO attribute."""
from __future__ import annotations

import math
import time
from typing import Any, Callable

import numpy as np
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

    def _value_changed(self: AttributeManager, value: Any) -> bool:
        """
        Check if value has changed since last poll.

        :param value: the value we want to update attribute with.

        :returns: whether or not the value has changed.
        """
        if isinstance(value, np.ndarray):
            return not np.array_equal(value, self._value)
        return value != self._value

    def update(self: AttributeManager, value: Any, post: bool = True) -> None:
        """
        Update attribute manager with a new value.

        :param value: the value we want to update attribute with.
        :param post: Optional flag to post an update.
        """

        def _is_none_type(val: Any) -> bool:
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return True
            return False

        is_event_required = False
        self._last_update = time.time()

        try:
            new_value = (
                self._converter(value)
                if self._converter and not _is_none_type(value)
                else value
            )
        except Exception:  # pylint: disable=broad-except
            new_value = None

        if _is_none_type(val=new_value):
            # Move to invalid and require event!
            if self._quality != tango.AttrQuality.ATTR_INVALID:
                self._quality = tango.AttrQuality.ATTR_INVALID
                is_event_required = True
        else:
            # Check for quality or value changes!
            if self._update_quality(value) or self._value_changed(new_value):
                is_event_required = True

            self._value = new_value

        if post and is_event_required:
            self.__notify()

    def mark_stale(self: AttributeManager) -> None:
        """Mark attribute as stale."""
        # Update with None and push
        if self._value is None:
            # Not updated or already INVALID
            return
        if self._initial_value is None:
            self.update(None, True)

    def _update_quality(self: AttributeManager, new_value: Any) -> bool:
        """
        Update the attribute quality factor.

        :param new_value: the value we are checking.

        :return: True if there was a change in quality.
            False if there was no change.
        """
        evaluated_quality = (
            tango.AttrQuality.ATTR_VALID
            if new_value is not None
            else tango.AttrQuality.ATTR_INVALID
        )
        if self._quality != evaluated_quality:
            self._quality = evaluated_quality
            return True
        return False

    def read(self: AttributeManager) -> Any:
        """
        Return the attribute value.

        :return: A tuple with value, last_updated and quaility.
            Or None if attribute has not had an update yet.
        """
        if self._value is not None:
            return self._value, time.time(), self._quality
        return self._value

    def __notify(self: AttributeManager) -> None:
        """Notify callback with value."""
        self._value_time_quality_callback(self._value, self._last_update, self._quality)
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

    def _update_quality(self: BoolAttributeManager, new_value: Any) -> bool:
        """
        Update the attribute quality factor.

        :param new_value: the new value we are checking

        :return: True if there was a change in quality.
            False if there was no change
        """
        if new_value is None:
            evaluated_quality = tango.AttrQuality.ATTR_INVALID
        else:
            evaluated_quality = (
                tango.AttrQuality.ATTR_ALARM
                if self._alarm_on_true is new_value
                else tango.AttrQuality.ATTR_VALID
            )
        if self._quality != evaluated_quality:
            self._quality = evaluated_quality
            return True
        return False


class NpArrayAttributeManager(AttributeManager):
    """An AttributeManager for a np.ndarray attribute."""

    def _value_changed(self: NpArrayAttributeManager, value: np.ndarray) -> bool:
        """
        Check if value has changed since last poll.

        :param value: the value we want to update attribute with.

        :returns: whether or not the value has changed.
        """
        return not np.array_equal(value, self._value)
