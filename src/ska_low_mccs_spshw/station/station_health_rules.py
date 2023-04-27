#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A file to store health transition rules for station."""
from __future__ import annotations

from typing import Callable, FrozenSet

from ska_control_model import HealthState

DEGRADED_STATES = frozenset({HealthState.DEGRADED, HealthState.FAILED, None})


class SpsStationHealthRules:
    """A class to handle transition rules for station."""

    def __init__(
        self: SpsStationHealthRules,
        subrack_degraded_threshold: float = 0.05,
        subrack_failed_threshold: float = 0.2,
        tile_degraded_threshold: float = 0.05,
        tile_failed_threshold: float = 0.2,
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_degraded_threshold: the fraction of unhealthy subracks for
            the station to be DEGRADED
        :param subrack_failed_threshold: the fraction of unhealthy subracks for
            the station to be FAILED
        :param tile_degraded_threshold: the fraction of unhealthy tiles for
            the station to be DEGRADED
        :param tile_failed_threshold: the fraction of unhealthy tiles for
            the station to be FAILED
        """
        self._subrack_degraded_threshold = subrack_degraded_threshold
        self._subrack_failed_threshold = subrack_failed_threshold
        self._tile_degraded_threshold = tile_degraded_threshold
        self._tile_failed_threshold = tile_failed_threshold

    def get_fraction_in_states(
        self: SpsStationHealthRules,
        device_dict: dict[str, HealthState | None],
        states: FrozenSet[HealthState | None],
    ) -> float:
        """
        Get the fraction of devices in a given list of states.

        :param device_dict: dictionary of devices, key fqdn and value health
        :param states: the states to check
        :return: the fraction of the devices in the given states
        """
        return self.get_count_in_states(device_dict, states) / float(len(device_dict))

    def get_count_in_states(
        self: SpsStationHealthRules,
        device_dict: dict[str, HealthState | None],
        states: FrozenSet[HealthState | None],
    ) -> int:
        """
        Get the number of devices in a given list of state.

        :param device_dict: dictionary of devices, key fqdn and value health
        :param states: the states to check
        :return: the number of the devices in the given states
        """
        return sum(map(lambda s: s in states, device_dict.values()))

    def unknown_rule(
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

    def failed_rule(
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
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES)
            >= self._tile_failed_threshold
            or self.get_fraction_in_states(subrack_healths, DEGRADED_STATES)
            >= self._subrack_failed_threshold
        )

    def degraded_rule(
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
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES)
            >= self._tile_degraded_threshold
            or self.get_fraction_in_states(subrack_healths, DEGRADED_STATES)
            >= self._subrack_degraded_threshold
        )

    def healthy_rule(
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
            self.get_fraction_in_states(tile_healths, DEGRADED_STATES)
            < self._tile_degraded_threshold
            and self.get_fraction_in_states(subrack_healths, DEGRADED_STATES)
            < self._subrack_degraded_threshold
        )

    @property
    def rules(self: SpsStationHealthRules) -> dict[HealthState, Callable[..., bool]]:
        """
        Get the transition rules for the station.

        :return: the transition rules for the station
        """
        return {
            HealthState.FAILED: self.failed_rule,
            HealthState.DEGRADED: self.degraded_rule,
            HealthState.OK: self.healthy_rule,
            HealthState.UNKNOWN: self.unknown_rule,
        }
