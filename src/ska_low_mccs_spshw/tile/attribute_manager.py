#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Attribute objects with TANGO specific information."""
from __future__ import annotations

import time
from typing import Any, Callable

import tango

__all__ = ["Attribute", "LimitAttribute", "BoolAttribute"]


class Attribute:
    """An attribute to serve as the source of truth for the TANGO attribute."""

    def __init__(
        self: Attribute,
        initial_value: Any,
        value_time_quality_callback: Callable,
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        """
        self._value = initial_value
        self._quality = (
            tango.AttrQuality.ATTR_INVALID
            if initial_value is None
            else tango.AttrQuality.ATTR_VALID
        )
        self._last_update = time.time()
        self._value_time_quality_callback = value_time_quality_callback

    def update(self: Attribute, value: Any) -> None:
        """
        Update attribute.

        :param value: the value we want to update attribute with.
        """
        self._value = value
        self._last_update = time.time()
        self.update_quality()
        self.notify()

    def update_quality(self: Attribute) -> None:
        """
        Must Override to define quality.

        :raises NotImplementedError: if not overriden.
        """
        raise NotImplementedError("This method must be defined in subclass.")

    def read(self: Attribute) -> tuple[Any, float, tango.AttrQuality]:
        """
        Return the attribute value, time, quality.

        :return: the attribute value, time, quality.
        """
        return self._value, self._last_update, self._quality

    def notify(self: Attribute) -> None:
        """Notify callback with value."""
        self._value_time_quality_callback(self.read())


class LimitAttribute(Attribute):
    """An attribute that Alarms upon exceeding limits."""

    def __init__(
        self: LimitAttribute,
        initial_value: int | float | None,
        alarm_min: int | float | None,
        alarm_max: int | float | None,
        value_time_quality_callback: Callable,
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param alarm_min: The minimum limit for this attribute.
        :param alarm_max: The maximimum limit for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        """
        super().__init__(initial_value, value_time_quality_callback)
        self._value = initial_value
        self._quality = tango.AttrQuality.ATTR_INVALID
        self._last_update = time.time()
        self.alarm_min = alarm_min
        self.alarm_max = alarm_max

    def update_quality(self: LimitAttribute) -> None:
        """Update the attribute quality."""
        if self.alarm_min is not None and self.alarm_max is not None:
            if not self.alarm_min < self._value < self.alarm_max:
                self._quality = tango.AttrQuality.ATTR_ALARM
            else:
                self._quality = tango.AttrQuality.ATTR_VALID
        else:
            self._quality = tango.AttrQuality.ATTR_VALID

    def update_thresholds(
        self: LimitAttribute, min_limit: float | int, max_limit: float | int
    ) -> None:
        """
        Update the attribute limit values.

        :param min_limit: A attribute with this value or below is in Alarm
        :param max_limit: A attribute with this value or anove is in Alarm
        """
        if min_limit:
            self.alarm_min = min_limit
        if max_limit:
            self.alarm_max = max_limit

        self.update_quality()
        self.notify()


class ShutdownOnLimitAttribute(LimitAttribute):
    """An attribute that calls a shutdown hook upon exceeding limits."""

    def __init__(  # pylint: disable=too-many-arguments
        self: ShutdownOnLimitAttribute,
        initial_value: int | float | None,
        alarm_min: int | float | None,
        alarm_max: int | float | None,
        value_time_quality_callback: Callable,
        shutdown_hook: Callable,
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param alarm_min: The minimum limit for this attribute.
        :param alarm_max: The maximimum limit for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        :param shutdown_hook: A hook to call upon exceeding limits
        """
        self.shutdown_hook = shutdown_hook

        super().__init__(
            initial_value, alarm_min, alarm_max, value_time_quality_callback
        )

    def notify(self: ShutdownOnLimitAttribute) -> None:
        """Nofify the callbacks."""
        super().notify()
        if self._quality == tango.AttrQuality.ATTR_ALARM:
            self.shutdown_hook()


class BoolAttribute(Attribute):
    """An Boolean attribute with optional alarm on HIGH."""

    def __init__(
        self: BoolAttribute,
        initial_value: bool | None,
        alarm_flag: str | None,
        value_time_quality_callback: Callable,
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param alarm_flag: A flag to represent if this attribute alarms
            on `HIGH` or `LOW`.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        """
        super().__init__(initial_value, value_time_quality_callback)

        self._alarm_on_true: bool | None = None

        if alarm_flag:
            self._alarm_on_true = bool(alarm_flag == "HIGH")

    def update_quality(self: BoolAttribute) -> None:
        """Update attribute quality."""
        if self._alarm_on_true is not None:
            if self._alarm_on_true == self._value:
                self._quality = tango.AttrQuality.ATTR_ALARM
            else:
                self._quality = tango.AttrQuality.ATTR_VALID
        else:
            self._quality = tango.AttrQuality.ATTR_VALID


class StringAttribute(Attribute):
    """An String attribute."""

    def __init__(
        self: StringAttribute, initial_value: str, value_time_quality_callback: Callable
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        """
        super().__init__(initial_value, value_time_quality_callback)

    def update_quality(self: StringAttribute) -> None:
        """Update attribute quality."""
        self._quality = tango.AttrQuality.ATTR_VALID


class ListAttribute(Attribute):
    """An String attribute."""

    def __init__(
        self: ListAttribute,
        initial_value: list[Any] | None,
        value_time_quality_callback: Callable,
    ) -> None:
        """
        Initialise a new attribute.

        :param initial_value: The initial value for this attribute.
        :param value_time_quality_callback: A hook to call with the attribute
            value, timestamp, and quality factor.
        """
        super().__init__(initial_value, value_time_quality_callback)

    def update_quality(self: ListAttribute) -> None:
        """Update attribute quality."""
        self._quality = tango.AttrQuality.ATTR_VALID
