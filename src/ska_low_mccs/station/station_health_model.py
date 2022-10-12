# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a station."""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from ska_low_mccs_common.health import HealthModel
from ska_tango_base.control_model import HealthState

__all__ = ["StationHealthModel"]


class StationHealthModel(HealthModel):
    """A health model for a station."""

    def __init__(
        self: StationHealthModel,
        apiu_fqdn: str,
        antenna_fqdns: Sequence[str],
        tile_fqdns: Sequence[str],
        component_state_changed_callback: Callable[[Any], None],
    ) -> None:
        """
        Initialise a new instance.

        :param apiu_fqdn: the FQDN of this station's APIU
        :param antenna_fqdns: the FQDNs of this station's antennas
        :param tile_fqdns: the FQDNs of this station's tiles
        :param component_state_changed_callback: callback to be called whenever
            there is a change to this component's state, including the health
            model's evaluated health state.
        """
        self._apiu_health: Optional[HealthState] = HealthState.UNKNOWN
        self._antenna_health: dict[str, Optional[HealthState]] = {
            antenna_fqdn: HealthState.UNKNOWN for antenna_fqdn in antenna_fqdns
        }
        self._tile_health: dict[str, Optional[HealthState]] = {
            tile_fqdn: HealthState.UNKNOWN for tile_fqdn in tile_fqdns
        }
        super().__init__(component_state_changed_callback)

    def apiu_health_changed(
        self: StationHealthModel,
        apiu_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in APIU health.

        :param apiu_health: the health state of the APIU, or None if the
            APIU's admin mode indicates that its health should not be
            rolled up.
        """
        if self._apiu_health != apiu_health:
            self._apiu_health = apiu_health
            self.update_health()

    def antenna_health_changed(
        self: StationHealthModel,
        antenna_fqdn: str,
        antenna_health: Optional[HealthState],
    ) -> None:
        """
        Handle a change in antenna health.

        :param antenna_fqdn: the FQDN of the antenna whose health has
            changed
        :param antenna_health: the health state of the specified
            antenna, or None if the antenna's admin mode indicates that
            its health should not be rolled up.
        """
        if self._antenna_health.get(antenna_fqdn) != antenna_health:
            self._antenna_health[antenna_fqdn] = antenna_health
            self.update_health()

    def tile_health_changed(
        self: StationHealthModel,
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
        self: StationHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the station.

        The overall health is based on the fault and communication
        status of the station overall, together with the health of the
        APIU, antennas and tiles that it manages.

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
            if self._apiu_health == health:
                return health
            if health in self._antenna_health.values():
                return health
            if health in self._tile_health.values():
                return health
        return HealthState.OK
