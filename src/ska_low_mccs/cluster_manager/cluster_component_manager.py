# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements component management for cluster managers."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, cast

from ska_tango_base.control_model import HealthState, PowerState, SimulationMode

from ska_low_mccs.cluster_manager import ClusterSimulator
from ska_low_mccs.component import (
    CommunicationStatus,
    DriverSimulatorSwitchingComponentManager,
    ObjectComponentManager,
    check_communicating,
)

__all__ = ["ClusterComponentManager"]


class ClusterSimulatorComponentManager(ObjectComponentManager):
    def __init__(
        self: ClusterSimulatorComponentManager,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        communication_status_changed_callback: Optional[
            Callable[[CommunicationStatus], None]
        ],
        power_mode_changed_callback: Optional[Callable[[PowerState], None]],
        fault_callback: Optional[Callable[[bool], None]],
        shadow_master_pool_node_health_changed_callback: Optional[
            Callable[[list[HealthState]], None]
        ],
    ) -> None:
        self._fault_callback = fault_callback
        self._shadow_master_pool_node_health_changed_callback = (
            shadow_master_pool_node_health_changed_callback
        )

        cluster_simulator = ClusterSimulator()
        super().__init__(
            cluster_simulator,
            logger,
            push_change_event,
            communication_status_changed_callback,
            power_mode_changed_callback,
            fault_callback,
        )

    def update_component_shadow_master_pool_node_health(
        self: ClusterSimulatorComponentManager, health: list[HealthState]
    ) -> None:
        """
        Update the shadow master pool node health, calling callbacks as required.

        :param health: the healths of each node in the shadow master pool.
        """
        if self._shadow_master_pool_node_health_changed_callback is not None:
            self._shadow_master_pool_node_health_changed_callback(health)

    def component_shadow_master_pool_node_health_changed(
        self: ClusterSimulatorComponentManager, health: list[HealthState]
    ) -> None:
        """
        Handle a change of health in a shadow master pool node.

        This is a callback hook, to be passed to the component.

        :param health: the healths of each node in the shadow master pool.
        """
        self.update_component_shadow_master_pool_node_health(health)

    def start_communicating(self: ClusterSimulatorComponentManager) -> None:
        super().start_communicating()
        cast(
            ClusterSimulator, self._component
        ).set_shadow_master_pool_node_health_changed_callback(
            self.component_shadow_master_pool_node_health_changed
        )

    def stop_communicating(self: ClusterSimulatorComponentManager) -> None:
        super().stop_communicating()
        cast(
            ClusterSimulator, self._component
        ).set_shadow_master_pool_node_health_changed_callback(None)

    def __getattr__(
        self: ClusterSimulatorComponentManager,
        name: str,
        default_value: Any = None,
    ) -> Any:
        """
        Get value for an attribute not found in the usual way.

        Implemented to check against a list of attributes to pass down
        to the simulator. The intent is to avoid having to implement a
        whole lot of methods that simply call the corresponding method
        on the simulator. The only reason this is possible is because
        the simulator has much the same interface as its component
        manager.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :return: the requested attribute
        """
        if name in [
            "clear_job_stats",
            "get_job_status",
            "jobs_errored",
            "jobs_failed",
            "jobs_finished",
            "jobs_killed",
            "jobs_killing",
            "jobs_lost",
            "jobs_running",
            "jobs_staging",
            "jobs_starting",
            "jobs_unreachable",
            "master_cpus_allocated_percent",
            "master_cpus_total",
            "master_cpus_used",
            "master_disk_percent",
            "master_disk_total",
            "master_disk_used",
            "master_mem_percent",
            "master_mem_total",
            "master_mem_used",
            "master_node_id",
            "memory_avail",
            "memory_total",
            "memory_used",
            "nodes_avail",
            "nodes_in_use",
            "nodes_total",
            "ping_master_pool",
            "shadow_master_pool_node_ids",
            "shadow_master_pool_status",
            "start_job",
            "stop_job",
            "submit_job",
        ]:
            return self._get_from_component(name)
        return default_value

    @check_communicating
    def _get_from_component(
        self: ClusterSimulatorComponentManager,
        name: str,
    ) -> Any:
        """
        Get an attribute from the component (if we are communicating with it).

        :param name: name of the attribute to get.

        :return: the attribute value
        """
        # This one-liner is only a method so that we can decorate it.
        return getattr(self._component, name)


class ClusterComponentManager(DriverSimulatorSwitchingComponentManager):
    """A component manager for a cluster manager device."""

    def __init__(
        self: ClusterComponentManager,
        logger: logging.Logger,
        push_change_event: Optional[Callable],
        initial_simulation_mode: SimulationMode,
        communication_status_changed_callback: Optional[
            Callable[[CommunicationStatus], None]
        ],
        component_power_mode_changed_callback: Optional[Callable[[PowerState], None]],
        component_fault_callback: Optional[Callable[[bool], None]],
        component_shadow_master_pool_node_health_changed_callback: Optional[
            Callable[[list[HealthState]], None]
        ],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param push_change_event: mechanism to inform the base classes
            what method to call; typically device.push_change_event.
        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_power_mode_changed_callback: callback to be
            called when the component power mode changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_shadow_master_pool_node_health_changed_callback:
            callback to be called when the health of a node in the
            shadow pool changes
        """
        cluster_simulator = ClusterSimulatorComponentManager(
            logger,
            push_change_event,
            communication_status_changed_callback,
            component_power_mode_changed_callback,
            component_fault_callback,
            component_shadow_master_pool_node_health_changed_callback,
        )
        super().__init__(None, cluster_simulator, initial_simulation_mode)
