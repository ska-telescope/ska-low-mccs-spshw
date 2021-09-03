# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""An implementation of a cluster simulator for SKA-Low-MCCS."""
from __future__ import annotations  # allow forward references in type hints

from enum import IntEnum
from itertools import count
from typing import Any, cast, Callable, Iterator, Optional, Tuple

from ska_tango_base.control_model import HealthState, PowerMode
from ska_low_mccs.component import ObjectComponent


__all__ = ["ClusterSimulator", "JobConfig", "JobStatus"]


class JobStatus(IntEnum):
    """
    An enumerated type for cluster job status.

    :todo: Once we start implementing a real cluster driver, this will
        need to be part of the shared interface
    """

    """
    The cluster is staging the job.
    """
    STAGING = 1

    """
    The cluster is starting the job.
    """
    STARTING = 2

    """
    The cluster is running the job.
    """
    RUNNING = 3

    """
    The cluster is killing the job.
    """
    KILLING = 4

    """
    The cluster cannot reach the job at present
    """
    UNREACHABLE = 5

    """
    The job finished in an error state.
    """
    ERRORED = 6

    """
    The job finished in an failure state.
    """
    FAILED = 7

    """
    The job finished successfully.
    """
    FINISHED = 8

    """
    The job was killed.
    """
    KILLED = 9

    """
    The job was lost; e.g. the node that the job was assigned to has
    crashed in such a way that the job is unrecoverable.
    """
    LOST = 10

    """
    The job is unknown to the cluster.
    """
    UNKNOWN = 11


class JobConfig:
    """
    Stub for a job configuration specification.

    This is unimplemented at present. Should eventually contain resource
    requirements (such as walltime, cpu, vmem, disk usage, etc) and a
    pointer to the job to be run.
    """

    def __init__(self: JobConfig, **kwargs: Any) -> None:
        """
        Create a new JobConfig instance.

        :param kwargs: dummy kwargs
        """
        self.kwargs = kwargs


class JobIdGenerator:
    """A generator of job ids."""

    def __init__(
        self: JobIdGenerator, id_format: str = "sim.{}", start: int = 1
    ) -> None:
        """
        Create a new instance.

        :param id_format: a format for the job id
        :param start: the initial job number
        """
        self._id_format = id_format
        self._counter = count(start=start)

    def __iter__(self: JobIdGenerator) -> Iterator:
        return self

    def __next__(self: JobIdGenerator) -> str:
        """
        Return the next job id.

        :return: the next job id
        """
        return self._id_format.format(next(self._counter))


class ClusterSimulator(ObjectComponent):
    """
    A rudimentary cluster simulator.

    The cluster is assumed to be an always-on resource (in the sense
    that any downtime is managed externally to this control system).

    Cluster configuration is hard-coded and cannot be changed

    Some initial job stats for closed jobs are hard-coded. These are
    modified by commands like :py:meth:`stop_job` and can be cleared by
    :py:meth:`clear_job_stats`.

    Stats on resources in use are hard-coded and cannot be changed.
    They are kept coherent e.g. "available" will always be "total" minus
    "in use".

    A small set of initial open jobs are hard-coded. These are modified
    by commands like :py:meth:`stop_job`. Stats on open jobs, such as
    :py:meth:`jobs_running` are calculated from this set.

    Node status start off healthy, but failure can be simulated. There
    is no notion of job assignment to nodes, so node failure does not
    affect running jobs. (Note deviation from SAD: node status is
    documented as a tango state, but it seemed much more sensible to
    implement as a SKA healthState.)
    """

    CONFIGURATION = {
        "master_node_id": 1,
        "shadow_master_pool_node_ids": (1, 2, 3, 4),
        "memory_total": 10000000.0,
        "nodes_total": 256,
        "master_cpus_total": 16,
        "master_disk_total": 10000000.0,
        "master_mem_total": 500.0,
    }

    JOB_STATS = {
        JobStatus.ERRORED: 20,
        JobStatus.FAILED: 21,
        JobStatus.FINISHED: 22,
        JobStatus.KILLED: 23,
        JobStatus.LOST: 24,
    }

    RESOURCE_STATS = {
        "memory_used": 8000000.0,
        "nodes_in_use": 201,
        "master_cpus_used": 15,
        "master_disk_used": 3450000.0,
        "master_mem_used": 401.0,
    }

    OPEN_JOBS = {
        "sim.1000": JobStatus.UNREACHABLE,
        "sim.1001": JobStatus.STAGING,
        "sim.1002": JobStatus.STARTING,
        "sim.1003": JobStatus.RUNNING,
        "sim.1004": JobStatus.KILLING,
    }

    NODE_STATUSES = {
        node_id: HealthState.OK
        for node_id in range(1, cast(int, CONFIGURATION["nodes_total"]) + 1)
    }

    JOB_CANNOT_START_BECAUSE_NOT_STAGING_MESSAGE = "Job cannot be started: not staging."
    NONEXISTENT_JOB_MESSAGE = "No such job"

    def __init__(
        self: ClusterSimulator,
    ) -> None:
        """Initialise a new ClusterSimulator instance."""
        self._faulty = False

        self._configuration = dict(self.CONFIGURATION)
        self._job_stats = dict(self.JOB_STATS)
        self._resource_stats = dict(self.RESOURCE_STATS)
        self._open_jobs = dict(self.OPEN_JOBS)
        self._node_statuses = dict(self.NODE_STATUSES)
        self._job_id_generator = JobIdGenerator(start=2000)

        self._fault_callback: Optional[Callable[[bool], None]] = None
        self._shadow_master_pool_node_health_changed_callback: Optional[
            Callable[[list[HealthState]], None]
        ] = None
        super().__init__()

    def set_fault_callback(
        self: ClusterSimulator, fault_callback: Optional[Callable[[bool], None]]
    ) -> None:
        """
        Set the callback to be called when the component faults.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param fault_callback: the callback to be called when a fault
            occurs
        """
        self._fault_callback = fault_callback
        if fault_callback is not None:
            fault_callback(self._faulty)

    def set_shadow_master_pool_node_health_changed_callback(
        self: ClusterSimulator,
        shadow_master_pool_node_health_changed_callback: Optional[
            Callable[[list[HealthState]], None]
        ],
    ) -> None:
        """
        Set the callback to be called when a shadow master pool node changes health.

        If a callback is provided (i.e. not None), then this method
        registers it, then calls it immediately.

        If the value provided is None, then any set callback is removed.

        :param shadow_master_pool_node_health_changed_callback: the
            callback to be called when the health of a node in the
            shadow master pool changes
        """
        self._shadow_master_pool_node_health_changed_callback = (
            shadow_master_pool_node_health_changed_callback
        )
        if shadow_master_pool_node_health_changed_callback is not None:
            shadow_master_pool_node_health_changed_callback(
                self.shadow_master_pool_status
            )

    def update_shadow_master_pool_node_health(self: ClusterSimulator) -> None:
        """Update the shadow master pool node health, calling callbacks as required."""
        if self._shadow_master_pool_node_health_changed_callback is not None:
            self._shadow_master_pool_node_health_changed_callback(
                self.shadow_master_pool_status
            )

    @property
    def faulty(self: ClusterSimulator) -> bool:
        """
        Return whether this component is faulty.

        The component will self-report as faulty if none of the node in
        its shadow master pool report good health.

        :return: whether or not this component is faulty.
        """
        return self._faulty

    @property
    def power_mode(self: ObjectComponent) -> PowerMode:
        """
        Return the power mode of the component.

        This is assumed to be an always-on service, so this property
        will always be ``PowerMode.ON``.

        :return: the power mode of the component. i.e. PowerMode.ON
        """
        return PowerMode.ON

    def off(self: ObjectComponent) -> None:
        """
        Turn the component off.

        :raises NotImplementedError: because this simulator is modelled
            as an always-on device, so this method has not been
            implemented.
        """
        raise NotImplementedError("ClusterSimulator is an always-on component.")

    def standby(self: ObjectComponent) -> None:
        """
        Put the component into low-power standby mode.

        :raises NotImplementedError: because this simulator is modelled
            as an always-on device, so this method has not been
            implemented.
        """
        raise NotImplementedError("ClusterSimulator is an always-on component.")

    def on(self: ObjectComponent) -> None:
        """Turn the component on."""
        pass

    def reset(self: ObjectComponent) -> None:
        """
        Reset the component (from fault state).

        :raises NotImplementedError: because this method has not been
            implemented.
        """
        raise NotImplementedError("ClusterSimulator reset not implemented.")

    @property
    def jobs_errored(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that have errored.

        :return: the number of jobs that have errored
        """
        return self._job_stats[JobStatus.ERRORED]

    @property
    def jobs_failed(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that have failed.

        :return: the number of jobs that have failed
        """
        return self._job_stats[JobStatus.FAILED]

    @property
    def jobs_finished(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that have finished.

        :return: the number of jobs that have finished
        """
        return self._job_stats[JobStatus.FINISHED]

    @property
    def jobs_killed(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that have been killed.

        :return: the number of jobs that have been killed
        """
        return self._job_stats[JobStatus.KILLED]

    @property
    def jobs_lost(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that have been lost.

        :return: the number of jobs that have been lost
        """
        return self._job_stats[JobStatus.LOST]

    def _num_open_jobs_by_status(self: ClusterSimulator, status: JobStatus) -> int:
        """
        Return the number of open jobs with a given status.

        :param status: the job status for which the number of open jobs
            are sought

        :return: the number of open jobs with a given status
        """
        return sum(value == status for value in self._open_jobs.values())

    @property
    def jobs_staging(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that are currently staging.

        :return: the number of jobs that are currently staging
        """
        return self._num_open_jobs_by_status(JobStatus.STAGING)

    @property
    def jobs_starting(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that are currently starting.

        :return: the number of jobs that are currently starting
        """
        return self._num_open_jobs_by_status(JobStatus.STARTING)

    @property
    def jobs_running(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that are currently running.

        :return: the number of jobs that are currently running
        """
        return self._num_open_jobs_by_status(JobStatus.RUNNING)

    @property
    def jobs_killing(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that are currently being killed.

        :return: the number of jobs that are currently being killed
        """
        return self._num_open_jobs_by_status(JobStatus.KILLING)

    @property
    def jobs_unreachable(self: ClusterSimulator) -> int:
        """
        Return the number of jobs that are currently unreachable.

        :return: the number of jobs that are currently unreachable
        """
        return self._num_open_jobs_by_status(JobStatus.UNREACHABLE)

    @property
    def memory_total(self: ClusterSimulator) -> float:
        """
        Return the total memory of the cluster.

        :return: the total memory of the cluster
        """
        return cast(float, self._configuration["memory_total"])

    @property
    def memory_used(self: ClusterSimulator) -> float:
        """
        Return the used memory of the cluster.

        :return: the used memory of the cluster
        """
        return cast(float, self._resource_stats["memory_used"])

    @property
    def memory_avail(self: ClusterSimulator) -> float:
        """
        Return the available memory of the cluster.

        :return: the available memory of the cluster
        """
        return self.memory_total - self.memory_used

    @property
    def nodes_total(self: ClusterSimulator) -> int:
        """
        Return the total number of nodes in the cluster.

        :return: the total number of nodes in the cluster
        """
        return cast(int, self._configuration["nodes_total"])

    @property
    def nodes_in_use(self: ClusterSimulator) -> int:
        """
        Return the number of nodes in use in the cluster.

        :return: the number of nodes in use in the cluster
        """
        return cast(int, self._resource_stats["nodes_in_use"])

    @property
    def nodes_avail(self: ClusterSimulator) -> int:
        """
        Return the number of available nodes in the cluster.

        :return: the number of available nodes in the cluster
        """
        return self.nodes_total - self.nodes_in_use

    @property
    def master_cpus_total(self: ClusterSimulator) -> int:
        """
        Return the total number of CPUs on the master node.

        :return: the total number of CPUs on the master node
        """
        return cast(int, self._configuration["master_cpus_total"])

    @property
    def master_cpus_used(self: ClusterSimulator) -> int:
        """
        Return the total number of CPUs in use on the master node.

        :return: the total number of CPUs in use on the master node
        """
        return cast(int, self._resource_stats["master_cpus_used"])

    @property
    def master_cpus_allocated_percent(self: ClusterSimulator) -> float:
        """
        Return the percent of CPUs allocated on master.

        :return: the percent of CPUs allocated on master
        """
        return self.master_cpus_used * 100.0 / self.master_cpus_total

    @property
    def master_disk_total(self: ClusterSimulator) -> float:
        """
        Return the total disk size on the master node.

        :return: the total disk size on the master node
        """
        return cast(float, self._configuration["master_disk_total"])

    @property
    def master_disk_used(self: ClusterSimulator) -> float:
        """
        Return the total disk usage on the master node.

        :return: the total disk usage on the master node
        """
        return self._resource_stats["master_disk_used"]

    @property
    def master_disk_percent(self: ClusterSimulator) -> float:
        """
        Return the percent of disk used on master.

        :return: the percent of disk used on master
        """
        return self.master_disk_used * 100.0 / self.master_disk_total

    @property
    def master_mem_total(self: ClusterSimulator) -> float:
        """
        Return the total memory size on the master node.

        :return: the total memory size on the master node
        """
        return cast(float, self._configuration["master_mem_total"])

    @property
    def master_mem_used(self: ClusterSimulator) -> float:
        """
        Return the total memory usage on the master node.

        :return: the total memory usage on the master node
        """
        return self._resource_stats["master_mem_used"]

    @property
    def master_mem_percent(self: ClusterSimulator) -> float:
        """
        Return the percent of memory used on master.

        :return: the percent of memory used on master
        """
        return self.master_mem_used * 100.0 / self.master_mem_total

    @property
    def master_node_id(self: ClusterSimulator) -> int:
        """
        Return the id of the master node.

        :return: the id of the master node
        """
        return cast(int, self._configuration["master_node_id"])

    @property
    def shadow_master_pool_node_ids(self: ClusterSimulator) -> tuple[int]:
        """
        Return the ids of nodes in the shadow master pool.

        :return: the ids of nodes in the shadow master pool
        """
        return cast(Tuple[int], self._configuration["shadow_master_pool_node_ids"])

    @property
    def shadow_master_pool_status(
        self: ClusterSimulator,
    ) -> list[HealthState]:
        """
        Return the statuses of nodes in the shadow master pool.

        :return: the statuses of nodes in the shadow master pool
        """
        return [
            self._node_statuses[node_id] for node_id in self.shadow_master_pool_node_ids
        ]

    def ping_master_pool(self: ClusterSimulator) -> None:
        """
        Ping the master pool nodes to make sure they are ok.

        This has not been implemented.

        :raises NotImplementedError: because this method is not yet
            meaningfully implemented
        """
        raise NotImplementedError(
            "ClusterSimulator.ping_master_pool has not been implemented"
        )

    def clear_job_stats(self: ClusterSimulator) -> None:
        """Clear stats for closed jobs."""
        for status in JobStatus:
            self._job_stats[status] = 0

    def get_job_status(self: ClusterSimulator, job_id: str) -> JobStatus:
        """
        Return the status of an open job.

        :param job_id: the id of the job

        :raises ValueError: if the job id does not match a current job

        :return: the status of the job
        """
        try:
            return self._open_jobs[job_id]
        except KeyError as key_error:
            raise ValueError(self.NONEXISTENT_JOB_MESSAGE) from key_error

    def submit_job(self: ClusterSimulator, job_config: JobConfig) -> str:
        """
        Submit a job to the cluster.

        Since the JobConfig class is not yet implemented, this simply
        creates a unique job id for the job, registers it as a STAGING
        job, and returns the job id.

        :param job_config: specification of the submitted job

        :return: the job_id
        """
        job_id = next(self._job_id_generator)
        self._open_jobs[job_id] = JobStatus.STAGING
        return job_id

    def start_job(self: ClusterSimulator, job_id: str) -> None:
        """
        Start a specified job.

        :param job_id: The id of the job to be started

        :raises ValueError: If the job does not exist
        """
        if self.get_job_status(job_id) == JobStatus.STAGING:
            self._open_jobs[job_id] = JobStatus.RUNNING
        else:
            raise ValueError(self.JOB_CANNOT_START_BECAUSE_NOT_STAGING_MESSAGE)

    def stop_job(self: ClusterSimulator, job_id: str) -> None:
        """
        Stop a specified job.

        :param job_id: The id of the job to be stopped

        :raises ValueError: If the job does not exist
        """
        try:
            del self._open_jobs[job_id]
        except KeyError as key_error:
            raise ValueError("No such job") from key_error
        else:
            self._job_stats[JobStatus.KILLED] += 1

    def simulate_node_failure(
        self: ClusterSimulator, node_id: int, failed: bool
    ) -> None:
        """
        Tells this simulator to simulate the failure of one of its nodes.

        :param node_id: id of the node whose failure status is to be
            changed
        :param failed: Whether the node should fail; pass False to
            simulate restoration of a previously failed node
        """
        if failed:
            self._node_statuses[node_id] = HealthState.FAILED
        else:
            self._node_statuses[node_id] = HealthState.OK

        if node_id in self.shadow_master_pool_node_ids:
            self.update_shadow_master_pool_node_health()
        self._update_master_node()

    def _update_master_node(self: ClusterSimulator) -> None:
        """Update the master node when the current master fails."""
        if self._node_statuses[self.master_node_id] != HealthState.OK:
            try:
                healthy_index = self.shadow_master_pool_status.index(HealthState.OK)
            except ValueError:
                self._faulty = True
                self.component_fault(True)
            else:
                self._configuration[
                    "master_node_id"
                ] = self.shadow_master_pool_node_ids[healthy_index]
                self._faulty = False
                self.component_fault(False)

    def component_fault(self: ClusterSimulator, faulty: bool) -> None:
        """
        Handle notification that the component has faulted.

        This is a callback hook.

        :param faulty: whether the component is in a fault state (if
            False, then this is a notification that the component has
            *recovered* from a fault).
        """
        if self._fault_callback is not None:
            self._fault_callback(faulty)
