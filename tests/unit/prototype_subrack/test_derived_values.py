#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
Tests of the subrack values that are computed rather than read.

``DerivedValues`` needs no hardware client, so every test here builds one with
nothing but a logger. ``TestDerivedValuesWiring``, in the client tests, covers
whether the client applies them.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from ska_low_mccs_spshw.prototype_subrack import DerivedValues
from ska_low_mccs_spshw.subrack.subrack_data import SubrackData

MAX_SPEED = SubrackData.MAX_SUBRACK_FAN_SPEED


class TestDerivedValues:
    """
    Tests of the values that are computed rather than read.

    The mean and median arithmetic has its own tests, in
    ``tests/unit/subrack/test_subrack_attribute_filter.py``.
    """

    @staticmethod
    def _derived(logger: logging.Logger, **kwargs: Any) -> DerivedValues:
        """
        Return a derived values object.

        :param logger: a logger.
        :param kwargs: overrides passed to the constructor.

        :return: a derived values object.
        """
        return DerivedValues(logger, **kwargs)

    # ----------------
    # The fan rpm estimate
    # ----------------
    def test_estimate_scales_by_pwm_duty(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        A fan at half duty must estimate to twice its measured rpm.

        ``max_fan_errors`` is zero and the expected answer is not the maximum
        fan speed, so the replacement rule cannot supply the asserted value.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=0)

        estimates = derived.estimate_max_fan_rpm([2600.0] * 4, [50.0] * 4)

        assert estimates == pytest.approx([5200.0] * 4)

    def test_unknown_input_gives_unknown_estimate(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        An unknown input must give an unknown estimate.

        :param logger: a logger.
        """
        derived = self._derived(logger)

        assert derived.estimate_max_fan_rpm(None, [50.0] * 4) is None
        assert derived.estimate_max_fan_rpm([100.0] * 4, None) is None

    def test_duty_is_floored(self: TestDerivedValues, logger: logging.Logger) -> None:
        """
        A zero pwm duty must not divide by zero.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=0)

        estimates = derived.estimate_max_fan_rpm([1200.0] * 4, [0.0] * 4)

        assert estimates is not None
        # Floored at 10% duty, so 1200 rpm scales to 12000 rpm.
        assert estimates == pytest.approx([12000.0] * 4)

    def test_bad_value_is_replaced_then_reported(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        A bad estimate must be replaced, but only for a bounded number of calls.

        A fan that is genuinely slow must eventually be reported as measured.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=3)
        stalled = [0.0] * SubrackData.FAN_COUNT
        full_duty = [100.0] * SubrackData.FAN_COUNT

        for _ in range(3):
            assert derived.estimate_max_fan_rpm(stalled, full_duty) == pytest.approx(
                [MAX_SPEED] * 4
            )

        assert derived.estimate_max_fan_rpm(stalled, full_duty) == pytest.approx(
            [0.0] * 4
        )

    def test_a_good_value_resets_the_counter(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        A good estimate must reset the counter for that fan.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=2)
        full_duty = [100.0] * 4

        derived.estimate_max_fan_rpm([0.0] * 4, full_duty)
        assert derived.fan_error_counts == [1, 1, 1, 1]

        derived.estimate_max_fan_rpm([MAX_SPEED] * 4, full_duty)
        assert derived.fan_error_counts == [0, 0, 0, 0]

    def test_the_counter_is_per_fan(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        One bad fan must not use up the allowance of the others.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=5)

        derived.estimate_max_fan_rpm(
            [0.0, MAX_SPEED, MAX_SPEED, MAX_SPEED], [100.0] * 4
        )

        assert derived.fan_error_counts == [1, 0, 0, 0]

    def test_tolerance_comes_from_max_fan_rpm_delta(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        A value inside the tolerance must pass through unchanged.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_rpm_delta=25.0)
        # 20% below the maximum, so inside the 25% tolerance.
        inside = [MAX_SPEED * 0.8] * 4

        estimates = derived.estimate_max_fan_rpm(inside, [100.0] * 4)

        assert estimates == pytest.approx(inside)
        assert derived.fan_error_counts == [0, 0, 0, 0]

    def test_unknown_input_clears_the_counters(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        An unknown reading must reset the fan counters.

        :param logger: a logger.
        """
        derived = self._derived(logger, max_fan_errors=5)
        derived.estimate_max_fan_rpm([0.0] * 4, [100.0] * 4)
        assert derived.fan_error_counts == [1, 1, 1, 1]

        derived.estimate_max_fan_rpm(None, None)

        assert derived.fan_error_counts == [0, 0, 0, 0]

    # ----------------
    # The noise filter
    # ----------------
    def test_every_filtered_key_is_filtered_on_its_own_samples(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        Each filtered key must be averaged, and only against its own samples.

        Two samples per key make the mean observable, and the three keys use
        different magnitudes, so a key that shares a buffer with another or
        skips filtering altogether gives the wrong answer.

        :param logger: a logger.
        """
        derived = self._derived(
            logger, attribute_filter_type="mean", attribute_filter_max_samples=5
        )

        derived.apply(
            {"tpm_currents": [0.0], "tpm_powers": [0.0], "tpm_voltages": [0.0]}
        )
        values: dict[str, Any] = {
            "tpm_currents": [10.0],
            "tpm_powers": [200.0],
            "tpm_voltages": [24.0],
        }
        derived.apply(values)

        assert values["tpm_currents"] == pytest.approx([5.0])
        assert values["tpm_powers"] == pytest.approx([100.0])
        assert values["tpm_voltages"] == pytest.approx([12.0])

    def test_unknown_value_clears_the_filter(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        An unknown value must clear the sample window and stay unknown.

        Otherwise a fresh reading averages against samples from before it.

        :param logger: a logger.
        """
        derived = self._derived(
            logger, attribute_filter_type="mean", attribute_filter_max_samples=5
        )

        derived.apply({"tpm_currents": [10.0]})

        unknown: dict[str, Any] = {"tpm_currents": None}
        derived.apply(unknown)
        assert unknown["tpm_currents"] is None

        fresh: dict[str, Any] = {"tpm_currents": [20.0]}
        derived.apply(fresh)

        assert fresh["tpm_currents"] == pytest.approx([20.0])

    def test_clear_forgets_everything(
        self: TestDerivedValues, logger: logging.Logger
    ) -> None:
        """
        ``clear`` must drop the fan counters and the filter samples.

        The client calls this when a poll fails.

        :param logger: a logger.
        """
        derived = self._derived(
            logger,
            max_fan_errors=5,
            attribute_filter_type="mean",
            attribute_filter_max_samples=5,
        )
        derived.apply({"tpm_currents": [10.0]})
        derived.estimate_max_fan_rpm([0.0] * 4, [100.0] * 4)
        assert derived.fan_error_counts == [1, 1, 1, 1]

        derived.clear()

        assert derived.fan_error_counts == [0, 0, 0, 0]
        fresh: dict[str, Any] = {"tpm_currents": [20.0]}
        derived.apply(fresh)
        assert fresh["tpm_currents"] == pytest.approx([20.0])
