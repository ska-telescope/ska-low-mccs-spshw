# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Tests for converting tpm-api values containing ``None`` for Tango."""
from __future__ import annotations

from typing import Any, Callable

import pytest

from ska_low_mccs_spshw.tile.attribute_converters import (
    adc_pll_to_list,
    adc_to_list,
    clock_managers_count,
    clock_managers_status,
    clocks_to_list,
    find_missing_values,
    lane_error_to_array,
    udp_error_count_to_list,
)

ADCS = [f"ADC{i}" for i in range(16)]
MMCMS = ["C2C_MMCM", "JESD_MMCM", "DSP_MMCM"]
LANES = {f"lane{i}": 0 for i in range(8)}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({adc: True for adc in ADCS}, []),
        (
            {**{adc: True for adc in ADCS}, "ADC9": None, "ADC12": None},
            ["ADC9", "ADC12"],
        ),
        ({"ADC0": (True, None)}, ["ADC0[1]"]),
        ({"ADC0": None}, ["ADC0"]),
        (
            {"Core0": {"lane0": 0, "lane3": None}, "Core1": None},
            ["Core0.lane3", "Core1"],
        ),
        ({"JESD": False, "DDR": 0}, []),
    ],
)
def test_find_missing_values(value: Any, expected: list[str]) -> None:
    """
    Test that ``None`` entries are located, while falsy values are not.

    :param value: the raw value to search.
    :param expected: the paths of the expected missing entries.
    """
    assert find_missing_values(value) == expected


@pytest.mark.parametrize(
    ("converter", "complete", "incomplete"),
    [
        (
            adc_to_list,
            {adc: True for adc in ADCS},
            # The value from the original bug report.
            {adc: (None if adc in ("ADC9", "ADC12") else True) for adc in ADCS},
        ),
        (
            adc_pll_to_list,
            {adc: (True, True) for adc in ADCS},
            {adc: ((True, None) if adc == "ADC3" else (True, True)) for adc in ADCS},
        ),
        (
            udp_error_count_to_list,
            {f"lane{i}": 0 for i in range(4)},
            {"lane0": 0, "lane1": None, "lane2": 0, "lane3": 0},
        ),
        (
            lane_error_to_array,
            {"Core0": dict(LANES), "Core1": dict(LANES)},
            {"Core0": dict(LANES), "Core1": {**LANES, "lane5": None}},
        ),
        (
            clock_managers_count,
            {mmcm: (True, 0) for mmcm in MMCMS},
            {**{mmcm: (True, 0) for mmcm in MMCMS}, "DSP_MMCM": (True, None)},
        ),
        (
            clock_managers_status,
            {mmcm: (True, 0) for mmcm in MMCMS},
            {**{mmcm: (True, 0) for mmcm in MMCMS}, "C2C_MMCM": None},
        ),
        (
            clocks_to_list,
            {"JESD": True, "DDR": True, "UDP": True},
            {"JESD": True, "DDR": None, "UDP": True},
        ),
    ],
)
def test_converter_returns_none_for_missing_values(
    converter: Callable[[Any], Any],
    complete: Any,
    incomplete: Any,
) -> None:
    """
    Test that a value with ``None`` entries converts to ``None``.

    ``None`` is published by the signal bus with ``ATTR_INVALID`` quality,
    rather than the converter raising inside the signal bus thread.

    :param converter: the converter under test.
    :param complete: a raw value with every entry present.
    :param incomplete: a raw value with at least one ``None`` entry.
    """
    assert converter(complete) is not None
    assert converter(incomplete) is None
