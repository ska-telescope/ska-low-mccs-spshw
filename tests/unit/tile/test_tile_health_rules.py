# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the TileHealthRules."""
from __future__ import annotations

from typing import Any

import pytest
from ska_control_model import HealthState

from ska_low_mccs_spshw.tile import TileData
from ska_low_mccs_spshw.tile.tile_health_rules import TileHealthRules


class TestTileHealthRules:
    """A class for tests of the tile health rules."""

    @pytest.fixture
    def health_rules(self: TestTileHealthRules) -> TileHealthRules:
        """
        Fixture to return the tile health rules.

        :return: Health rules to be used.
        """
        return TileHealthRules()

    @pytest.mark.parametrize(
        ("min_max", "monitoring_points", "expected_state", "expected_report"),
        [
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS["temperatures"],
                TileData.get_tile_defaults().get("temperatures"),
                HealthState.OK,
                "",
                id="Default values used, health is OK",
            ),
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS["voltages"],
                TileData.TILE_MONITORING_POINTS["voltages"],
                HealthState.UNKNOWN,
                "not yet read",
                id="Monitoring points are None, health is UNKNOWN",
            ),
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS["currents"],
                {"FE0_mVA": None, "FE1_mVA": 50},
                HealthState.FAILED,
                'Monitoring point "/FE1_mVA": 50 not in range 2.02 - 2.38',
                id="One monitoring point failed, one out of range, health is FAILED",
            ),
        ],
    )
    def test_compute_intermediate_state(
        self: TestTileHealthRules,
        health_rules: TileHealthRules,
        min_max: dict[str, Any],
        monitoring_points: dict[str, Any],
        expected_state: HealthState,
        expected_report: str,
    ) -> None:
        """
        Test the computing of intermediate health states.

        :param health_rules: the health rules object to use
        :param min_max: the min and max values that the monitoring points can take
        :param monitoring_points: the input monitoring point values
        :param expected_state: the expected health state
        """
        if expected_state == HealthState.UNKNOWN:
            state, report = health_rules.compute_intermediate_state(
                monitoring_points, min_max
            )
            assert state == expected_state
            assert report.count(expected_report) == 36
        else:
            assert health_rules.compute_intermediate_state(
                monitoring_points, min_max
            ) == (expected_state, expected_report)
