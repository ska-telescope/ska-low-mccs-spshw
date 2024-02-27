#  -*- coding: utf-8 -*
# pylint: disable=arguments-differ
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A file to store health transition rules for station."""
from __future__ import annotations

from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthRules

DEGRADED_STATES = frozenset({HealthState.DEGRADED, HealthState.FAILED, None})


class SpsStationHealthRules(HealthRules):
    """A class to handle transition rules for station."""

    def unknown_rule(  # type: ignore[override]
        self: SpsStationHealthRules,
        subrack_healths: dict[str, HealthState | None],
        tile_healths: dict[str, HealthState | None],
    ) -> bool:
        """
        Test whether UNKNOWN is valid for the station.

        :param subrack_healths: dictionary of subrack healths
        :param tile_healths: dictionary of tile healths
        :return: True if UNKNOWN is a valid state
        """
        return (
            HealthState.UNKNOWN in subrack_healths.values()
            or HealthState.UNKNOWN in tile_healths.values()
        )

    def failed_rule(  # type: ignore[override]
        self: SpsStationHealthRules,
        subrack_healths: dict[str, HealthState | None],
        tile_healths: dict[str, HealthState | None],
    ) -> bool:
        """
        Test whether FAILED is valid for the station.

        :param subrack_healths: dictionary of subrack healths
        :param tile_healths: dictionary of tile healths
        :return: True if FAILED is a valid state
        """
        return (
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES, default=0)
            >= self._thresholds["tile_failed"]
            or self.get_fraction_in_states(subrack_healths, DEGRADED_STATES, default=0)
            >= self._thresholds["subrack_failed"]
        )

    def degraded_rule(  # type: ignore[override]
        self: SpsStationHealthRules,
        subrack_healths: dict[str, HealthState | None],
        tile_healths: dict[str, HealthState | None],
    ) -> bool:
        """
        Test whether DEGRADED is valid for the station.

        :param subrack_healths: dictionary of subrack healths
        :param tile_healths: dictionary of tile healths
        :return: True if DEGRADED is a valid state
        """
        return (
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES, default=0)
            >= self._thresholds["tile_degraded"]
            or self.get_fraction_in_states(subrack_healths, DEGRADED_STATES, default=0)
            >= self._thresholds["subrack_degraded"]
        )

    def healthy_rule(  # type: ignore[override]
        self: SpsStationHealthRules,
        subrack_healths: dict[str, HealthState | None],
        tile_healths: dict[str, HealthState | None],
    ) -> bool:
        """
        Test whether OK is valid for the station.

        :param subrack_healths: dictionary of subrack healths
        :param tile_healths: dictionary of tile healths
        :return: True if OK is a valid state
        """
        return (
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES, default=0)
            < self._thresholds["tile_degraded"]
            and self.get_fraction_in_states(subrack_healths, DEGRADED_STATES, default=0)
            < self._thresholds["subrack_degraded"]
        )

    @property
    def default_thresholds(self: HealthRules) -> dict[str, float]:
        """
        Get the default thresholds for this device.

        :return: the default thresholds
        """
        return {
            "subrack_degraded": 0.05,
            "subrack_failed": 0.2,
            "tile_degraded": 0.05,
            "tile_failed": 0.2,
        }
