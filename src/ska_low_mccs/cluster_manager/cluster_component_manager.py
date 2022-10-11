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
import threading
from typing import Any, Callable, Optional, cast

from ska_control_model import (
    CommunicationStatus,
    HealthState,
    ResultCode,
    SimulationMode,
    TaskStatus,
)
from ska_low_mccs_common.component import (
    DriverSimulatorSwitchingComponentManager,
    ObjectComponentManager,
    check_communicating,
)

from ska_low_mccs.cluster_manager import ClusterSimulator

__all__ = ["ClusterComponentManager"]


class ClusterSimulatorComponentManager(ObjectComponentManager):
    def __init__(
        self: ClusterSimulatorComponentManager,
        logger: logging.Logger,
        max_workers: int,
        communication_state_changed_callback: Optional[
            Callable[[CommunicationStatus], None]
        ],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        self._component_state_changed_callback = component_state_changed_callback

        self.cluster_simulator = ClusterSimulator()
        super().__init__(
            self.cluster_simulator,
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )

    def update_component_shadow_master_pool_node_health(
        self: ClusterSimulatorComponentManager, health: list[HealthState]
    ) -> None:
        """
        Update the shadow master pool node health, calling callbacks as required.

        :param health: the healths of each node in the shadow master pool.
        """
        if self._component_state_changed_callback is not None:
            self._component_state_changed_callback(
                {"shadow_master_pool_node_healths": health}
            )

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
        max_workers: int,
        initial_simulation_mode: SimulationMode,
        communication_state_changed_callback: Callable[[CommunicationStatus], None],
        component_state_changed_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Initialise a new instance.

        :param logger: a logger for this object to use
        :param max_workers: the maximum number of workers
        :param initial_simulation_mode: the simulation mode that the
            component should start in
        :param communication_state_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_state_changed_callback: callback to be called when the
            component state changes
        """
        self.cluster_simulator = ClusterSimulatorComponentManager(
            logger,
            max_workers,
            communication_state_changed_callback,
            component_state_changed_callback,
        )
        super().__init__(None, self.cluster_simulator, initial_simulation_mode)

    def start_job(
        self: ClusterComponentManager,
        job_id: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the start job slow task.

        This method returns immediately after it is submitted for execution.

        :param job_id: The id of the job to be started
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._start_job, args=[job_id], task_callback=task_callback
        )

    def _start_job(
        self: ClusterComponentManager,
        job_id: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Start job command using slow command.

        :param job_id: The id of the job to be started
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self.cluster_simulator.start_job(job_id)
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The start job task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="The start job task has completed"
            )

    def stop_job(
        self: ClusterComponentManager,
        job_id: str,
        task_callback: Optional[Callable] = None,
    ) -> tuple[TaskStatus, str]:
        """
        Submit the stop job slow task.

        This method returns immediately after it is submitted for execution.

        :param job_id: The id of the job to be stopped
        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._stop_job, args=[job_id], task_callback=task_callback
        )

    def _stop_job(
        self: ClusterComponentManager,
        job_id: str,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Stop job command using slow command.

        :param job_id: The id of the job to be stopped
        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self.cluster_simulator.stop_job(job_id)
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The stop job task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED, result="The stop job task has completed"
            )

    # def submit_job(
    #     self: ClusterComponentManager,
    #     job_config: str,
    #     task_callback: Optional[Callable] = None,
    # ) -> tuple[TaskStatus, str]:
    #     """
    #     Submit the submit_job slow task.

    #     This method returns immediately after it is submitted for execution.

    #     :todo: currently the JobConfig class is unimplemented. This task should
    #         include the job specification

    #     :param job_config: The configuration of the job to be submitted
    #     :param task_callback: Update task state, defaults to None

    #     :return: A tuple containing a ResultCode and a response message
    #     """
    #     return self.submit_task(
    #         self._submit_job, args=[job_config], task_callback=task_callback
    #     )

    # def _submit_job(
    #     self: ClusterComponentManager,
    #     job_config: str,
    #     task_callback: Optional[Callable] = None,
    #     task_abort_event: Optional[threading.Event] = None,
    # ) -> None:
    #     """
    #     Submit job command using slow cammand.

    #     :param job_config: The configuration of the job to be submitted
    #     :param task_callback: Update task state, defaults to None
    #     :param task_abort_event: Check for abort, defaults to None
    #     """
    #     if task_callback:
    #         task_callback(status=TaskStatus.IN_PROGRESS)
    #     try:
    #         self.cluster_simulator.submit_job(job_config)
    #     except Exception as ex:
    #         if task_callback:
    #             task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
    #         return

    #     if task_abort_event and task_abort_event.is_set():
    #         if task_callback:
    #             task_callback(
    #                 status=TaskStatus.ABORTED, result="The submit job task aborted"
    #             )
    #         return

    #     if task_callback:
    #         task_callback(
    #             status=TaskStatus.COMPLETED, result="The submit job task has completed"
    #         )

    # def get_job_status(
    #     self: ClusterComponentManager,
    #     job_id: str,
    #     task_callback: Optional[Callable] = None,
    # ) -> tuple[ResultCode, str]:  # tuple[TaskStatus, str]:
    #     """
    #     Submit the get_job_status slow task.

    #     This method returns immediately after it is submitted for execution.

    #     :param job_id: The id of the job for which the status is to be checked
    #     :param task_callback: Update task state, defaults to None

    #     :return: A tuple containing a ResultCode and a response message
    #     """
    #     return self.submit_task(
    #         self._get_job_status, args=[job_id], task_callback=task_callback
    #     )

    # def get_job_status(
    #     self: ClusterComponentManager,
    #     job_id: str,
    #     #task_callback: Optional[Callable] = None,
    #     #task_abort_event: Optional[threading.Event] = None,
    # ) -> JobStatus:
    #     """
    #     Get job status command using slow cammand.

    #     :param job_id: The id of the job for which the status is to be checked
    #     :param task_callback: Update task state, defaults to None
    #     :param task_abort_event: Check for abort, defaults to None
    #     """
    #     # if task_callback:
    #     #     task_callback(status=TaskStatus.IN_PROGRESS)
    #     try:
    #         self.cluster_simulator.get_job_status(job_id)
    #     except Exception as ex:
    #         # if task_callback:
    #         #     task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
    #         return

    #     if task_abort_event and task_abort_event.is_set():
    #         if task_callback:
    #             task_callback(
    #                 status=TaskStatus.ABORTED, result="The get job status task aborted"
    #             )
    #         return

    #     if task_callback:
    #         task_callback(
    #             status=TaskStatus.COMPLETED,
    #             result="The get job status task has completed",
    #         )

    def clear_job_stats(
        self: ClusterComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[ResultCode, str]:  # tuple[TaskStatus, str]:
        """
        Submit the clear_job_stats slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._clear_job_stats, args=[], task_callback=task_callback
        )

    def _clear_job_stats(
        self: ClusterComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Clear the job stats using slow cammand.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self.cluster_simulator.clear_job_stats()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED, result="The clear job stats task aborted"
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The clear job stats task has completed",
            )

    def ping_master_pool(
        self: ClusterComponentManager,
        task_callback: Optional[Callable] = None,
    ) -> tuple[ResultCode, str]:  # tuple[TaskStatus, str]:
        """
        Submit the ping_master_pool slow task.

        This method returns immediately after it is submitted for execution.

        :param task_callback: Update task state, defaults to None

        :return: A tuple containing a ResultCode and a response message
        """
        return self.submit_task(
            self._ping_master_pool, args=[], task_callback=task_callback
        )

    def _ping_master_pool(
        self: ClusterComponentManager,
        task_callback: Optional[Callable] = None,
        task_abort_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Ping the master pool using slow cammand.

        :param task_callback: Update task state, defaults to None
        :param task_abort_event: Check for abort, defaults to None
        """
        if task_callback:
            task_callback(status=TaskStatus.IN_PROGRESS)
        try:
            self.cluster_simulator.ping_master_pool()
        except Exception as ex:
            if task_callback:
                task_callback(status=TaskStatus.FAILED, result=f"Exception: {ex}")
            return

        if task_abort_event and task_abort_event.is_set():
            if task_callback:
                task_callback(
                    status=TaskStatus.ABORTED,
                    result="The ping master pool task aborted",
                )
            return

        if task_callback:
            task_callback(
                status=TaskStatus.COMPLETED,
                result="The ping master pool task has completed",
            )
