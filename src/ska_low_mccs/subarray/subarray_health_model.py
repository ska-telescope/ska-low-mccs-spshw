# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for subarrays."""
from __future__ import annotations

from typing import Any, Callable

from ska_tango_base.control_model import HealthState

from ska_low_mccs.health import HealthModel

__all__ = ["SubarrayHealthModel"]


class SubarrayHealthModel(HealthModel):
    """A health model for subarrays."""

    def __init__(
        self: SubarrayHealthModel,
        health_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: a callback to be called when the
            health of the subarray (as evaluated by this model) changes
        """
        self._station_healths: dict[str, HealthState | None] = {}
        self._subarray_beam_healths: dict[str, HealthState | None] = {}
        self._station_beam_healths: dict[str, HealthState | None] = {}
        super().__init__(health_changed_callback)

    def evaluate_health(
        self: SubarrayHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the subarray.

        The overall health is based on the fault and communication
        status of the subarray overall, together with the health of its
        stations and subarray beams.

        This implementation simply sets the health of the station to the
        health of its least healthy component.

        :return: an overall health of the subarray
        """
        subarray_health = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
        ]:
            if subarray_health == health:
                return health
            if health in self._station_healths.values():
                return health
            if health in self._subarray_beam_healths.values():
                return health
        return HealthState.OK

    def resources_changed(
        self: SubarrayHealthModel,
        station_fqdns: set[str],
        subarray_beam_fqdns: set[str],
        station_beam_fqdns: set[str],
    ) -> None:
        """
        Handle change in subarray resources.

        This is a callback hook, called by the component manager when
        the resources of the subarray changes.

        :param station_fqdns: the FQDNs of stations assigned to this
            subarray
        :param subarray_beam_fqdns: the FQDNs of subarray beams assigned
            to this subarray
        :param station_beam_fqdns: the FQDNs of station beams assigned
            to this subarray
        """
        self._station_healths = {
            fqdn: self._station_healths.get(fqdn, HealthState.UNKNOWN)
            for fqdn in station_fqdns
        }
        self._subarray_beam_fqdns = {
            fqdn: self._subarray_beam_healths.get(fqdn, HealthState.UNKNOWN)
            for fqdn in subarray_beam_fqdns
        }
        self._station_beam_fqdns = {
            fqdn: self._station_beam_healths.get(fqdn, HealthState.UNKNOWN)
            for fqdn in station_beam_fqdns
        }
        self.update_health()

    def station_health_changed(
        self: SubarrayHealthModel,
        fqdn: str,
        health_state: HealthState | None,
    ) -> None:
        """
        Handle change in station health.

        This is a callback hook, called by the component manager when
        the health of a station changes.

        :param fqdn: the FQDN of the station whose health has
            changed
        :param health_state: the new health state of the station, or
            None if the subarray beam's health should not be taken into
            account.
        """
        self._station_healths[fqdn] = health_state
        self.update_health()

    def subarray_beam_health_changed(
        self: SubarrayHealthModel,
        fqdn: str,
        health_state: HealthState | None,
    ) -> None:
        """
        Handle change in subarray beam health.

        This is a callback hook, called by the component manager when
        the health of a subarray beam changes.

        :param fqdn: the FQDN of the subarray beam whose health has
            changed
        :param health_state: the new health state of the subarray beam,
            or None if the subarray beam's health should not be taken
            into account.
        """
        self._subarray_beam_healths[fqdn] = health_state
        self.update_health()

    def station_beam_health_changed(
        self: SubarrayHealthModel,
        fqdn: str,
        health_state: HealthState | None,
    ) -> None:
        """
        Handle change in station beam health.

        This is a callback hook, called by the component manager when
        the health of a station beam changes.

        :param fqdn: the FQDN of the station beam whose health has
            changed
        :param health_state: the new health state of the station beam,
            or None if the station beam's health should not be taken
            into account.
        """
        self._station_beam_healths[fqdn] = health_state
        self.update_health()
