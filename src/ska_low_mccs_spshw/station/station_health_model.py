#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a station."""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from ska_control_model import HealthState
from ska_low_mccs_common.health import HealthModel

__all__ = ["SpsStationHealthModel"]


class SpsStationHealthModel(HealthModel):
    """A health model for a Sps station."""

    def __init__(
        self: SpsStationHealthModel,
        subrack_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param tile_fqdns: the FQDNs of this station's tiles
        :param subrack_fqdns: the FQDNs of this station's subracks
        :param component_state_changed_callback: callback to be called whenever
            there is a change to this component's state, including the health
            model's evaluated health state.
        """
        self._tile_health: dict[str, Optional[HealthState]] = {
            tile_fqdn: HealthState.UNKNOWN for tile_fqdn in tile_fqdns
        }
        self._subrack_health: dict[str, Optional[HealthState]] = {
            subrack_fqdn: HealthState.UNKNOWN for subrack_fqdn in subrack_fqdns
        }
        super().__init__(component_state_changed_callback)

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
    ) -> HealthState:
        """
        Compute overall health of the station.

        The overall health is based on the fault and communication
        status of the station overall, together with the health of the
        tiles that it manages.

        This implementation simply sets the health of the station to the
        health of its least healthy component.

        :return: an overall health of the station
        """
        station_health = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
        ]:
            if station_health == health:
                return health
            if health in self._tile_health.values():
                return health
        return HealthState.OK
