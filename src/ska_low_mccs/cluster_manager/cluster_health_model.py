# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""An implementation of a health model for a cluster."""
from __future__ import annotations

from typing import Callable

from ska_low_mccs_common.health import HealthModel
from ska_tango_base.control_model import HealthState

__all__ = ["ClusterHealthModel"]


class ClusterHealthModel(HealthModel):
    """A health model for a cluster manager."""

    def __init__(
        self: ClusterHealthModel,
        health_changed_callback: Callable[[HealthState], None],
    ) -> None:
        """
        Initialise a new instance.

        :param health_changed_callback: a callback to be called when the
            health of the cluster (as evaluated by this model) changes
        """
        self._node_health = HealthState.UNKNOWN
        super().__init__(health_changed_callback)

    def evaluate_health(
        self: ClusterHealthModel,
    ) -> HealthState:
        """
        Compute overall health of the cluster.

        The overall health is based on the fault and communication
        status of the overall cluster, and the health of nodes in the
        shadow master pool.

        :return: an overall health of the cluster
        """
        cluster_health = super().evaluate_health()

        for health in [
            HealthState.FAILED,
            HealthState.UNKNOWN,
            HealthState.DEGRADED,
        ]:
            if self._node_health == health:
                return health
            if cluster_health == health:
                return health
        return HealthState.OK

    def shadow_master_pool_node_health_changed(
        self: ClusterHealthModel,
        shadow_master_pool_node_healths: list[HealthState],
    ) -> None:
        """
        Handle a change in health of a node in the shadow master pool.

        This is a callback hook that is called when a node that belongs
        to the shadow master pool experiences a change in health.

        :param shadow_master_pool_node_healths: whether the health
            of each node in the shadow master pool is okay
        """
        shadow_master_pool_node_health_ok = [
            (health == HealthState.OK) for health in shadow_master_pool_node_healths
        ]
        if all(shadow_master_pool_node_health_ok):
            self._node_health = HealthState.OK
        elif any(shadow_master_pool_node_health_ok):
            self._node_health = HealthState.DEGRADED
        else:
            self._node_health = HealthState.FAILED
        self.update_health()
