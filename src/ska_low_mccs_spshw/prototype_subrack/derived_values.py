#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The subrack values that are computed rather than read from the board.

``subrack_max_fan_speeds`` estimates fan rpm at 100% pwm duty.
``tpm_currents``, ``tpm_powers`` and ``tpm_voltages`` pass through a noise
filter. Both keep state between polls.

This module holds no HTTP code and reads no status codes. It works on a
dictionary of poll values.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..subrack.subrack_attribute_filter import SubrackAttributeFilter
from ..subrack.subrack_data import SubrackData
from .constants import FILTERED_ATTRIBUTES, MIN_PWM_DUTY_FRACTION, DerivedKey, ReadKey

__all__ = ["DerivedValues"]


class DerivedValues:
    """
    The subrack values that are computed rather than read.

    One instance belongs to one poll loop. Every method must be called from the
    polling thread, because the instance keeps state between polls and takes no
    lock.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self: DerivedValues,
        logger: logging.Logger,
        max_fan_errors: int = 5,
        max_fan_rpm_delta: float = 25.0,
        attribute_filter_type: str | None = None,
        attribute_filter_max_samples: int = 5,
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this instance to use.
        :param max_fan_errors: how many consecutive bad fan rpm estimates to
            replace, per fan, before the estimate is reported as measured.
        :param max_fan_rpm_delta: the tolerance, as a percentage of the maximum
            fan speed, outside which a fan rpm estimate counts as bad.
        :param attribute_filter_type: the noise filter to apply to the TPM
            current, power and voltage readings.
        :param attribute_filter_max_samples: the filter sample window.
        """
        self._logger = logger
        self._max_fan_errors = int(max_fan_errors)
        self._max_fan_delta = max_fan_rpm_delta / 100
        self._fan_error_counts = [0] * SubrackData.FAN_COUNT

        # One filter per key, because each filter holds its own sample buffer.
        # Sharing one filter would average currents together with voltages.
        self._filters = {
            key: SubrackAttributeFilter(
                attribute_filter_type, attribute_filter_max_samples, logger
            )
            for key in FILTERED_ATTRIBUTES
        }

    @property
    def fan_error_counts(self: DerivedValues) -> list[int]:
        """
        Return how many consecutive bad estimates each fan has had.

        At ``max_fan_errors`` the estimate for that fan is reported as measured.

        :return: a copy of the per fan counters.
        """
        return list(self._fan_error_counts)

    def apply(self: DerivedValues, values: dict[str, Any]) -> None:
        """
        Add the derived values, and filter the noisy ones, in place.

        :param values: the poll values, modified in place.
        """
        values[DerivedKey.SUBRACK_MAX_FAN_SPEEDS.value] = self.estimate_max_fan_rpm(
            values.get(ReadKey.SUBRACK_FAN_SPEEDS.value),
            values.get(ReadKey.SUBRACK_FAN_SPEEDS_PERCENT.value),
        )
        for key, attribute_filter in self._filters.items():
            # An unknown value is passed in too, because that clears the
            # sample buffer.
            values[key] = attribute_filter(values.get(key))

    def clear(self: DerivedValues) -> None:
        """Drop the fan counters and the filter sample buffers."""
        self._fan_error_counts = [0] * SubrackData.FAN_COUNT
        for attribute_filter in self._filters.values():
            attribute_filter.clear()

    def estimate_max_fan_rpm(
        self: DerivedValues,
        fan_speeds: Optional[list[float]],
        fan_speeds_percent: Optional[list[float]],
    ) -> Optional[list[float]]:
        """
        Estimate the fan rpm at 100% pwm duty.

        The rpm reading lags a pwm change by about 5 to 10 seconds, because the
        fans have inertia, so the scaled value is wrong during that time. A
        scaled value further than ``max_fan_rpm_delta`` percent from
        ``SubrackData.MAX_SUBRACK_FAN_SPEED`` is replaced with that maximum, for
        at most ``max_fan_errors`` consecutive calls per fan.

        ``max_fan_errors=0`` switches the replacement off.

        :param fan_speeds: the fan speeds in rpm, as read from the board.
        :param fan_speeds_percent: the pwm duty cycle, as read from the board.

        :return: the estimated fan speeds at 100% pwm duty, or ``None`` when
            either input is unknown.
        """
        if fan_speeds is None or fan_speeds_percent is None:
            self._fan_error_counts = [0] * SubrackData.FAN_COUNT
            return None

        duty = [
            max(MIN_PWM_DUTY_FRACTION, percent / 100) for percent in fan_speeds_percent
        ]
        scaled = [rpm / duty[i] for i, rpm in enumerate(fan_speeds)]

        expected = SubrackData.MAX_SUBRACK_FAN_SPEED
        for i, value in enumerate(scaled):
            if abs(value - expected) / expected <= self._max_fan_delta:
                self._fan_error_counts[i] = 0
            elif self._fan_error_counts[i] < self._max_fan_errors:
                scaled[i] = expected
                self._fan_error_counts[i] += 1

        return scaled
