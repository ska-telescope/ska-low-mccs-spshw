# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsStation."""
from __future__ import annotations

from typing import Any

import pytest
from ska_control_model import HealthState

from ska_low_mccs_spshw.station.station_health_model import SpsStationHealthModel


class TestSpsStationHealthModel:
    """A class for tests of the station health model."""

    @pytest.fixture
    def health_model(self: TestSpsStationHealthModel) -> SpsStationHealthModel:
        """
        Fixture to return the station health model.

        :return: Health model to be used.
        """

        def callback(arg: Any) -> None:
            pass

        health_model = SpsStationHealthModel(["subrack"], ["tile"], callback)
        health_model.is_communicating(True)

        return health_model

    @pytest.mark.parametrize(
        ("sub_devices", "thresholds", "expected_health"),
        [
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                None,
                HealthState.OK,
                id="All devices healthy, expect OK",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i > 0 else HealthState.FAILED
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                None,
                HealthState.DEGRADED,
                id="One subrack unhealthy, expect DEGRADED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i > 0 else HealthState.FAILED
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                {"subrack_degraded": 0.00001, "subrack_failed": 0.02},
                HealthState.FAILED,
                id="One subrack unhealthy, lowered thresholds, expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        if i != 0
                        else HealthState.FAILED
                        for i in range(16)
                    },
                },
                None,
                HealthState.DEGRADED,
                id="One tile unhealthy, expect DEGRADED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        if i != 0
                        else HealthState.FAILED
                        for i in range(16)
                    },
                },
                {"tile_degraded": 0.00001, "tile_failed": 0.02},
                HealthState.FAILED,
                id="One tile unhealthy, lowered thresholds, expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i > 3 else HealthState.FAILED
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                None,
                HealthState.FAILED,
                id="Many subracks unhealthy, expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": (
                            HealthState.OK if i > 4 else HealthState.FAILED
                        )
                        for i in range(16)
                    },
                },
                None,
                HealthState.FAILED,
                id="Five tiles unhealthy, expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i > 1 else HealthState.UNKNOWN
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                None,
                HealthState.UNKNOWN,
                id="Some subracks UNKNOWN, expect UNKNOWN",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs-spshw/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": (
                            HealthState.OK if i != 0 else HealthState.UNKNOWN
                        )
                        for i in range(16)
                    },
                },
                None,
                HealthState.UNKNOWN,
                id="One tile UNKNOWN, expect UNKNOWN",
            ),
        ],
    )
    def test_station_evaluate_health(
        self: TestSpsStationHealthModel,
        health_model: SpsStationHealthModel,
        sub_devices: dict,
        thresholds: dict[str, float],
        expected_health: HealthState,
    ) -> None:
        """
        Tests for evaluating station health.

        :param health_model: The station health model to use
        :param sub_devices: the devices for which the station cares about health,
            and their healths
        :param thresholds: A dictionary of thresholds with the param name as key
            and threshold as value
        :param expected_health: the expected health values
        """
        health_model._subrack_health = sub_devices["subrack"]
        health_model._tile_health = sub_devices["tile"]

        if thresholds is not None:
            health_model.thresholds = thresholds

        assert health_model.evaluate_health() == expected_health
