#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a station."""
from __future__ import annotations

from typing import Optional, Sequence

from ska_control_model import HealthState
from ska_low_mccs_common.health import BaseHealthModel, HealthChangedCallbackProtocol

from .station_health_rules import SpsStationHealthRules

__all__ = ["SpsStationHealthModel"]


class SpsStationHealthModel(BaseHealthModel):
    """A health model for a Sps station."""

    def __init__(
        self: SpsStationHealthModel,
        subrack_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        health_changed_callback: HealthChangedCallbackProtocol,
        thresholds: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Initialise a new instance.

        :param subrack_fqdns: the FQDNs of this station's subracks
        :param tile_fqdns: the FQDNs of this station's tiles
        :param health_changed_callback: callback to be called whenever
            there is a change to this this health model's evaluated
            health state.
        :param thresholds: the threshold parameters for the health rules
        """
        self._tile_health: dict[str, Optional[HealthState]] = {
            tile_fqdn: HealthState.UNKNOWN for tile_fqdn in tile_fqdns
        }
        self._subrack_health: dict[str, Optional[HealthState]] = {
            subrack_fqdn: HealthState.UNKNOWN for subrack_fqdn in subrack_fqdns
        }
        self._health_rules = SpsStationHealthRules(thresholds)
        super().__init__(health_changed_callback)

    def subrack_health_changed(
        self: SpsStationHealthModel,
        subrack_fqdn: str,
        subrack_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in subrack health.

        :param subrack_fqdn: the FQDN of the tile whose health has changed
        :param subrack_health: the health state of the specified tile, or
            None if the subrack's admin mode indicates that its health
            should not be rolled up.
        """
        if self._subrack_health.get(subrack_fqdn) != subrack_health:
            self._subrack_health[subrack_fqdn] = subrack_health
            self.update_health()

    def tile_health_changed(
        self: SpsStationHealthModel,
        tile_fqdn: str,
        tile_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in tile health.

        :param tile_fqdn: the FQDN of the tile whose health has changed
        :param tile_health: the health state of the specified tile, or
            None if the tile's admin mode indicates that its health
            should not be rolled up.
        """
        if self._tile_health.get(tile_fqdn) != tile_health:
            self._tile_health[tile_fqdn] = tile_health
            self.update_health()

    def evaluate_health(
        self: SpsStationHealthModel,
    ) -> tuple[HealthState, str]:
        """
        Compute overall health of the station.

        The overall health is based on the fault and communication
        status of the station overall, together with the health of the
        tiles that it manages.

        This implementation simply sets the health of the station to the
        health of its least healthy component.

        :return: an overall health of the station
        """
        station_health, station_report = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
            HealthState.OK,
        ]:
            if health == station_health:
                return station_health, station_report
            result, report = self._health_rules.rules[health](
                self._subrack_health, self._tile_health
            )
            if result:
                return health, report
        return HealthState.UNKNOWN, "No rules matched"
