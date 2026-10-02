#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
The subrack values that are computed rather than read from the board.

``subrack_max_fan_speeds`` estimates fan rpm at 100% pwm duty, and
``tpm_currents``, ``tpm_powers`` and ``tpm_voltages`` pass through a noise
filter. Both keep state between polls. ``psu_dead_count`` counts the power
supplies that are fed but supplying nothing, ``tpm_count`` counts the occupied
bays, and ``psu1_load`` and ``psu2_load`` give the load on each power supply.
These keep no state.

This module holds no HTTP code and reads no status codes. It works on a
dictionary of poll values.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

from utils import walk

from ..subrack.subrack_attribute_filter import SubrackAttributeFilter
from ..subrack.subrack_data import SubrackData
from .constants import (
    FILTERED_ATTRIBUTES,
    HEALTH_STATUS_KEY,
    MIN_PWM_DUTY_FRACTION,
    PSU_DEAD_VOLTAGE_THRESHOLD,
    PSU_MAX_POWER,
    PSU_NAMES,
    DerivedKey,
    ReadKey,
)

__all__ = ["DerivedValues"]

# The key for the load on each power supply, in ``PSU_NAMES`` order.
_PSU_LOAD_KEYS = (DerivedKey.PSU1_LOAD.value, DerivedKey.PSU2_LOAD.value)


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

    def apply(
        self: DerivedValues,
        values: dict[str, Any],
    ) -> None:
        """
        Add the derived values, and filter the noisy ones, in place.

        A key is absent from ``values`` when the board was too busy to read it.
        A derived value that needs an absent key is left out too, and the state
        that spans polls is kept, so a busy board changes nothing.

        :param values: the poll values, modified in place. The health status
            is under ``HEALTH_STATUS_KEY``.
        """
        fan_speeds = ReadKey.SUBRACK_FAN_SPEEDS.value
        fan_speeds_percent = ReadKey.SUBRACK_FAN_SPEEDS_PERCENT.value
        if fan_speeds in values and fan_speeds_percent in values:
            values[DerivedKey.SUBRACK_MAX_FAN_SPEEDS.value] = self.estimate_max_fan_rpm(
                values[fan_speeds], values[fan_speeds_percent]
            )
        if HEALTH_STATUS_KEY in values:
            values[DerivedKey.PSU_DEAD_COUNT.value] = self.count_dead_psus(
                values[HEALTH_STATUS_KEY]
            )
        tpm_present = ReadKey.TPM_PRESENT.value
        if tpm_present in values:
            values[DerivedKey.TPM_COUNT.value] = self.count_tpms(values[tpm_present])
        power_supply_powers = ReadKey.POWER_SUPPLY_POWERS.value
        if power_supply_powers in values:
            loads = self.psu_loads(
                values[power_supply_powers], values.get(HEALTH_STATUS_KEY)
            )
            values.update(zip(_PSU_LOAD_KEYS, loads))
        for key, attribute_filter in self._filters.items():
            if key not in values:
                continue
            # An unknown value is passed in too, because that clears the
            # sample buffer.
            values[key] = attribute_filter(self.known_bays(values.get(key)))

    def clear(self: DerivedValues) -> None:
        """Drop the fan counters and the filter sample buffers."""
        self._fan_error_counts = [0] * SubrackData.FAN_COUNT
        for attribute_filter in self._filters.values():
            attribute_filter.clear()

    @staticmethod
    def known_bays(value: Any) -> Any:
        """
        Replace an unknown per bay reading with ``nan``.

        The board reports ``None`` for a bay whose TPM is powered off, so a
        subrack with nothing switched on reads every bay as ``None``. Tango
        cannot push ``None`` inside a float spectrum, and the noise filter
        cannot average it either, so each unknown bay becomes ``nan``.

        ``nan`` is what the filter skips, so a bay that is off does not drag
        down the average of the bays that are on. It is also what the subrack
        device this one replaces reports for the same reading.

        :param value: the reading as the board gave it.

        :return: the reading, with each unknown bay as ``nan``.
        """
        if not isinstance(value, list):
            return value
        return [math.nan if reading is None else reading for reading in value]

    @staticmethod
    def count_tpms(tpm_present: Optional[list[bool]]) -> Optional[int]:
        """
        Count the bays that hold a TPM.

        :param tpm_present: whether each bay holds a TPM, or ``None`` when the
            board could not say.

        :return: the number of occupied bays, or ``None`` when the board could
            not say.
        """
        return None if tpm_present is None else tpm_present.count(True)

    @staticmethod
    def psu_loads(
        power_supply_powers: Optional[list[Optional[float]]],
        health_status: Optional[dict],
    ) -> list[Optional[float]]:
        """
        Give the load on each power supply, as a fraction of its maximum power.

        The load comes from ``power_supply_powers``. A supply that this reading
        does not report takes its output power from the health status instead.

        :param power_supply_powers: the output power of each supply in Watts,
            or ``None`` when the board could not say.
        :param health_status: the polled health status, or ``None`` when this
            poll did not read it.

        :return: the load on each supply in ``PSU_NAMES`` order, with ``None``
            for a supply that neither source reports.
        """
        loads: list[Optional[float]] = []
        for index, psu in enumerate(PSU_NAMES):
            power = None
            if isinstance(power_supply_powers, list) and index < len(
                power_supply_powers
            ):
                power = power_supply_powers[index]
            if power is None:
                power = walk(health_status, ("psus", "power_out", psu))
            loads.append(None if power is None else float(power) / PSU_MAX_POWER)
        return loads

    @staticmethod
    def count_dead_psus(health_status: Optional[dict]) -> Optional[int]:
        """
        Count the power supplies that are present and fed but supplying nothing.

        A supply counts as dead when it is fitted, its input voltage is above
        the threshold, and its output voltage is below it.

        :param health_status: the polled health status, or ``None`` when this
            poll did not read it.

        :return: the number of dead power supplies, or ``None`` when the health
            status does not say enough to tell.
        """
        # The board does not always answer with a mapping. A failed read gives
        # a string, so the type alone cannot be relied on.
        if not isinstance(health_status, dict):
            return None

        psus = health_status.get("psus")
        if not isinstance(psus, dict):
            return None

        def field(name: str, psu: str) -> Any:
            """
            Read one field of one power supply.

            :param name: the health status field to read.
            :param psu: the power supply to read it for.

            :return: the value, or ``None`` when it is not reported.
            """
            values = psus.get(name)
            return values.get(psu) if isinstance(values, dict) else None

        dead_count = 0
        for psu in PSU_NAMES:
            present = field("present", psu)
            voltage_in = field("voltage_in", psu)
            voltage_out = field("voltage_out", psu)
            if present is None or voltage_in is None or voltage_out is None:
                return None
            if present and voltage_out < PSU_DEAD_VOLTAGE_THRESHOLD < voltage_in:
                dead_count += 1
        return dead_count

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
