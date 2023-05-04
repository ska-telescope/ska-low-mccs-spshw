# -*- coding: utf-8 -*
# pylint: disable=too-many-arguments
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsStation."""
from __future__ import annotations

import pytest
from ska_control_model import HealthState, PowerState

from ska_low_mccs_spshw.station.station_health_model import SpsStationHealthModel


class TestSpsStationHealthModel:
    """A class for tests of the station health model."""

    @pytest.fixture
    def health_model(self: TestSpsStationHealthModel) -> SpsStationHealthModel:
        """
        Fixture to return the station health model.

        :return: Health model to be used.
        """

        def callback(health: HealthState) -> None:
            pass

        health_model = SpsStationHealthModel(["subrack"], ["tile"], callback)
        health_model.update_state(communicating=True, power=PowerState.ON)

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
            health_model.health_params = thresholds

        assert health_model.evaluate_health() == expected_health

    @pytest.mark.parametrize(
        (
            "sub_devices",
            "health_change",
            "expected_init_health",
            "expected_final_health",
        ),
        [
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.FAILED
                        for i in range(3)
                    },
                },
                HealthState.OK,
                HealthState.FAILED,
                id="All devices healthy, expect OK, then 3 subracks FAILED, "
                "expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.FAILED
                        for i in range(1)
                    },
                },
                HealthState.OK,
                HealthState.DEGRADED,
                id="All devices healthy, expect OK, then 1 subrack FAILED, expect DEGRADED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        if i != 0
                        else HealthState.FAILED
                        for i in range(16)
                    },
                },
                {
                    "tile": {"low-mccs-spshw/tile/0000": HealthState.OK},
                },
                HealthState.DEGRADED,
                HealthState.OK,
                id="One tile unhealthy, expect DEGRADED, then tile becomes OK, "
                "expect OK",
            ),
        ],
    )
    def test_station_evaluate_changed_health(
        self: TestSpsStationHealthModel,
        health_model: SpsStationHealthModel,
        sub_devices: dict,
        health_change: dict[str, dict[str, HealthState]],
        expected_init_health: HealthState,
        expected_final_health: HealthState,
    ) -> None:
        """
        Tests of the station health model for a changed health.

        The properties of the health model are set and checked, then the health states
        of subservient devices are updated and the health is checked against the new
        expected value.

        :param health_model: The station health model to use
        :param sub_devices: the devices for which the station cares about health,
            and their healths
        :param health_change: a dictionary of the health changes, key device and value
            dictionary of fqdn:HealthState
        :param expected_init_health: the expected initial health
        :param expected_final_health: the expected final health
        """
        health_model._subrack_health = sub_devices["subrack"]
        health_model._tile_health = sub_devices["tile"]

        assert health_model.evaluate_health() == expected_init_health

        health_update = {
            "subrack": health_model.subrack_health_changed,
            "tile": health_model.tile_health_changed,
        }

        for device in health_change:
            changes = health_change[device]
            for change in changes:
                health_update[device](change, changes[change])

        assert health_model.evaluate_health() == expected_final_health

    @pytest.mark.parametrize(
        (
            "sub_devices",
            "init_thresholds",
            "expected_init_health",
            "final_thresholds",
            "expected_final_health",
        ),
        [
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": HealthState.OK
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        if i != 0
                        else HealthState.FAILED
                        for i in range(16)
                    },
                },
                {"tile_degraded": 0.05, "tile_failed": 0.2},
                HealthState.DEGRADED,
                {"tile_degraded": 0.15, "tile_failed": 0.3},
                HealthState.OK,
                id="One tile unhealthy, expect DEGRADED, then raise DEGRADED threshold"
                ", expect OK",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i != 0 else HealthState.FAILED
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                {"subrack_degraded": 0.05, "subrack_failed": 0.2},
                HealthState.DEGRADED,
                {"subrack_degraded": 0.0004, "subrack_failed": 0.008},
                HealthState.FAILED,
                id="One subrack unhealthy, expect DEGRADED, then lower DEGRADED and "
                "FAILED threshold, expect FAILED",
            ),
            pytest.param(
                {
                    "subrack": {
                        f"low-mccs/subrack/{str(i).zfill(2)}": (
                            HealthState.OK if i > 3 else HealthState.FAILED
                        )
                        for i in range(10)
                    },
                    "tile": {
                        f"low-mccs-spshw/tile/{str(i).zfill(4)}": HealthState.OK
                        for i in range(16)
                    },
                },
                {"subrack_degraded": 0.6, "subrack_failed": 0.8},
                HealthState.OK,
                {"subrack_degraded": 0.45, "subrack_failed": 0.6},
                HealthState.OK,
                id="Few subracks unhealthy with high thresholds, expect OK, then lower"
                "DEGRADED and FAILED threshold but not by much, expect OK",
            ),
        ],
    )
    def test_station_evaluate_health_changed_thresholds(
        self: TestSpsStationHealthModel,
        health_model: SpsStationHealthModel,
        sub_devices: dict,
        init_thresholds: dict[str, float],
        expected_init_health: HealthState,
        final_thresholds: dict[str, float],
        expected_final_health: HealthState,
    ) -> None:
        """
        Tests of the station health model for changed thresholds.

        The properties of the health model are set and checked, then the thresholds for
        the health rules are changed and the new health is checked against the expected
        value

        :param health_model: The station health model to use
        :param sub_devices: the devices for which the station cares about health,
            and their healths
        :param init_thresholds: the initial thresholds of the health rules
        :param expected_init_health: the expected initial health
        :param final_thresholds: the final thresholds of the health rules
        :param expected_final_health: the expected final health
        """
        health_model._subrack_health = sub_devices["subrack"]
        health_model._tile_health = sub_devices["tile"]

        health_model.health_params = init_thresholds
        assert health_model.evaluate_health() == expected_init_health

        health_model.health_params = final_thresholds
        print(health_model._health_rules._thresholds)
        assert health_model.evaluate_health() == expected_final_health
