# type: ignore
#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests of the cluster simulator."""
from __future__ import annotations

from typing import Union

import pytest
from _pytest.fixtures import SubRequest  # for type hinting

from ska_tango_base.control_model import HealthState, SimulationMode

from ska_low_mccs.cluster_manager.cluster_simulator import JobConfig, JobStatus
from ska_low_mccs.cluster_manager import (
    ClusterComponentManager,
    ClusterSimulator,
    ClusterSimulatorComponentManager,
)

from ska_low_mccs.testing.mock import MockCallable


class TestClusterCommon:
    """
    Because the ClusterComponentManager is designed to pass commands through to the
    ClusterSimulator or ClusterDriver that it is driving, many commands are common to.

    * the ClusterSimulator,
    * the ClusterSimulatorComponentManager, and
    * the ClusterComponentManager

    Therefore this class contains common tests, parametrised to test
    against each class.
    """

    @pytest.fixture(params=["cluster_simulator", "cluster_component_manager"])
    def cluster(
        self,
        cluster_simulator: ClusterSimulator,
        cluster_simulator_component_manager: ClusterSimulatorComponentManager,
        cluster_component_manager: ClusterComponentManager,
        request: SubRequest,
    ) -> Union[
        ClusterSimulator, ClusterSimulatorComponentManager, ClusterComponentManager
    ]:
        """
        Return the hardware under test.

        This is parametrised to return

        * a cluster simulator,
        * a cluster simulator component manager, and
        * a cluster component manager

        so any test that relies on this fixture will be run twice: once
        for each hardware type.

        :param cluster_simulator: the cluster simulator to return
        :param cluster_simulator_component_manager: the cluster
            simulator component manager to return
        :param cluster_component_manager: the cluster component manager
            to return
        :param request: A pytest object giving access to the requesting
            test context.

        :return: the hardware under test: a cluster manager or simulator
        """
        if request.param == "cluster_simulator":
            return cluster_simulator
        elif request.param == "cluster_simulator_component_manager":
            cluster_simulator_component_manager.start_communicating()
            return cluster_simulator_component_manager
        elif request.param == "cluster_component_manager":
            cluster_component_manager.start_communicating()
            return cluster_component_manager

    @pytest.mark.parametrize(
        "resource",
        (
            "master_node_id",
            "shadow_master_pool_node_ids",
            "memory_total",
            "nodes_total",
            "master_cpus_total",
            "master_disk_total",
            "master_mem_total",
        ),
    )
    def test_configuration(
        self,
        cluster: Union[ClusterSimulator, ClusterComponentManager],
        resource: str,
    ) -> None:
        """
        Test of resources that are stored.

        :param cluster: the simulated cluster
        :param resource: the name of the configuration resource under
            test
        """
        assert getattr(cluster, resource) == ClusterSimulator.CONFIGURATION[resource]

    @pytest.mark.parametrize(
        "status", ["errored", "failed", "finished", "killed", "lost"]
    )
    def test_closed_jobs_stats(
        self,
        cluster: Union[ClusterSimulator, ClusterComponentManager],
        status: str,
    ):
        """
        Test the stats on closed jobs.

        For example, test that closed job stats are cleared by
        :py:meth:`~ska_low_mccs.cluster_manager.ClusterSimulator.clear_job_stats`.

        :param cluster: the simulated cluster
        :param status: the job status for which stats reporting is under
            test
        """
        job_status = JobStatus[status.upper()]
        assert (
            getattr(cluster, f"jobs_{status}") == ClusterSimulator.JOB_STATS[job_status]
        )
        cluster.clear_job_stats()
        assert getattr(cluster, f"jobs_{status}") == 0

    @pytest.mark.parametrize(
        "status", ("staging", "starting", "running", "killing", "unreachable")
    )
    def test_open_jobs_stats(
        self,
        cluster: Union[ClusterSimulator, ClusterComponentManager],
        status: str,
    ) -> None:
        """
        Test of the open job stats, including.

        * that it is consistent with the results of
          :py:meth:`~ska_low_mccs.cluster_manager.ClusterSimulator.clear_job_stats`

        * that the number of jobs of a given status decrements if an
          job with that status is killed; and

        * that it is NOT cleared by
          :py:meth:`~ska_low_mccs.cluster_manager.ClusterSimulator.clear_job_stats`.

        :param cluster: the simulated cluster
        :param status: the job status for which stats reporting is under
            test
        """
        jobs = ClusterSimulator.OPEN_JOBS.keys()
        job_status = JobStatus[status.upper()]
        jobs_of_status = [
            job for job in jobs if cluster.get_job_status(job) == job_status
        ]

        assert getattr(cluster, f"jobs_{status}") == len(jobs_of_status)

        cluster.stop_job(jobs_of_status.pop())
        assert getattr(cluster, f"jobs_{status}") == len(jobs_of_status)
        assert cluster.jobs_killed == ClusterSimulator.JOB_STATS[JobStatus.KILLED] + 1

        cluster.clear_job_stats()
        assert getattr(cluster, f"jobs_{status}") == len(jobs_of_status)

    @pytest.mark.parametrize(
        "resource",
        (
            "memory_used",
            "nodes_in_use",
            "master_cpus_used",
            "master_disk_used",
            "master_mem_used",
        ),
    )
    def test_resource_stats(
        self,
        cluster: Union[ClusterSimulator, ClusterComponentManager],
        resource: str,
    ) -> None:
        """
        Test of resources that are stored.

        :param cluster: the simulated cluster
        :param resource: the name of the resource for which stats
            reporting is under test
        :type resource: str
        """
        assert getattr(cluster, resource) == ClusterSimulator.RESOURCE_STATS[resource]

    @pytest.mark.parametrize(
        ("resource", "expected_value"),
        (
            (
                "memory_avail",
                ClusterSimulator.CONFIGURATION["memory_total"]
                - ClusterSimulator.RESOURCE_STATS["memory_used"],
            ),
            (
                "nodes_avail",
                ClusterSimulator.CONFIGURATION["nodes_total"]
                - ClusterSimulator.RESOURCE_STATS["nodes_in_use"],
            ),
            (
                "master_cpus_allocated_percent",
                ClusterSimulator.RESOURCE_STATS["master_cpus_used"]
                * 100.0
                / ClusterSimulator.CONFIGURATION["master_cpus_total"],
            ),
            (
                "master_disk_percent",
                ClusterSimulator.RESOURCE_STATS["master_disk_used"]
                * 100.0
                / ClusterSimulator.CONFIGURATION["master_disk_total"],
            ),
            (
                "master_mem_percent",
                ClusterSimulator.RESOURCE_STATS["master_mem_used"]
                * 100
                / ClusterSimulator.CONFIGURATION["master_mem_total"],
            ),
        ),
    )
    def test_computed_resources(
        self,
        cluster: Union[ClusterSimulator, ClusterComponentManager],
        resource: str,
        expected_value,
    ):
        """
        Test of resources that are computed.

        :param cluster: the simulated cluster
        :param resource: the name of the resource for which stats
            reporting is under test
        :param expected_value: the expected stat value for the resource
        :type expected_value: int or float
        """
        assert getattr(cluster, resource) == expected_value

    def test_resources_relate(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test that resources relate to each other as they should. For
        example:

        * used + available = total
        * 100 * used / total = percent

        :param cluster: the simulated cluster
        """
        assert cluster.memory_avail + cluster.memory_used == pytest.approx(
            cluster.memory_total
        )
        assert cluster.nodes_avail + cluster.nodes_in_use == pytest.approx(
            cluster.nodes_total
        )
        assert (
            100.0 * cluster.master_cpus_used / cluster.master_cpus_total
            == pytest.approx(cluster.master_cpus_allocated_percent)
        )
        assert (
            100.0 * cluster.master_disk_used / cluster.master_disk_total
            == pytest.approx(cluster.master_disk_percent)
        )
        assert (
            100.0 * cluster.master_mem_used / cluster.master_mem_total
            == pytest.approx(cluster.master_mem_percent)
        )

    def test_ping_master_pool(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test the ping master node command. This command has not been implemented, so the
        test is correspondingly weak.

        :param cluster: the simulated cluster
        """
        with pytest.raises(
            NotImplementedError,
            match="ClusterSimulator.ping_master_pool has not been implemented",
        ):
            assert cluster.ping_master_pool() is None

    def test_shadow_master_pool_status(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test that the shadow master pool status.

        :param cluster: the object under test: either a simulator or a
            component manager.
        """
        assert cluster.shadow_master_pool_status == (
            HealthState.OK,
            HealthState.OK,
            HealthState.OK,
            HealthState.OK,
        )

    def test_submit_job(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test that when we submit a job, we get a job id for it, and the status of the
        job is STAGING.

        :param cluster: the simulated cluster
        """
        job_config = JobConfig()
        job_id = cluster.submit_job(job_config)
        assert cluster.get_job_status(job_id) == JobStatus.STAGING

    def test_start_job(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test that when we start a job, that job starts running.

        :param cluster: the simulated cluster
        """
        with pytest.raises(ValueError, match="No such job"):
            cluster.start_job("no_such_job_id")

        for job_id in ClusterSimulator.OPEN_JOBS:
            if cluster.get_job_status(job_id) == JobStatus.STAGING:
                cluster.start_job(job_id)
                assert cluster.get_job_status(job_id) == JobStatus.RUNNING
            else:
                with pytest.raises(ValueError, match="Job cannot be started"):
                    cluster.start_job(job_id)

    def test_stop_job(
        self, cluster: Union[ClusterSimulator, ClusterComponentManager]
    ) -> None:
        """
        Test that we can stop a job.

        :param cluster: the simulated cluster
        """
        with pytest.raises(ValueError, match="No such job"):
            cluster.stop_job("no_such_job_id")

        for job_id in list(ClusterSimulator.OPEN_JOBS):
            cluster.stop_job(job_id)

            with pytest.raises(ValueError, match="No such job"):
                cluster.stop_job(job_id)


class TestClusterSimulator:
    """Contains tests specific to ClusterSimulator."""

    def test_node_failure(self, cluster_simulator: ClusterSimulator) -> None:
        """
        Test for the master node id is as expected, and that it changes if we simulate
        node failure.

        We're going to repeatedly make the master node fail, and watch
        the cluster choose a new master from the master pool, until
        every node in the master pool has failed, at which point the
        master node does not change any more.

        :param cluster_simulator: the simulated cluster
        """
        master_node_id = None
        assert (
            cluster_simulator.master_node_id
            == ClusterSimulator.CONFIGURATION["master_node_id"]
        )

        while any(
            status == HealthState.OK
            for status in cluster_simulator.shadow_master_pool_status
        ):
            assert cluster_simulator.master_node_id != master_node_id
            master_node_id = cluster_simulator.master_node_id
            assert cluster_simulator._node_statuses[master_node_id] == HealthState.OK
            assert (
                cluster_simulator.master_node_id
                in cluster_simulator.shadow_master_pool_node_ids
            )

            cluster_simulator.simulate_node_failure(master_node_id, True)
            assert (
                cluster_simulator._node_statuses[master_node_id] == HealthState.FAILED
            )

        assert cluster_simulator.master_node_id == master_node_id


class TestClusterComponentManager:
    """Contains tests specific to ClusterComponentManager."""

    def test_init_simulation_mode(self, logger) -> None:
        """
        Test that we can't create a cluster manager that's not in simulation mode.

        :param logger: a logger for the ClusterComponentManager instance
            that this test will try to initialise.
        """
        with pytest.raises(
            NotImplementedError,
            match=("Unimplemented switcher mode 'SimulationMode.FALSE'."),
        ):
            _ = ClusterComponentManager(
                logger,
                SimulationMode.FALSE,
                None,
                None,
                None,
                None,
            )

    def test_simulation_mode(
        self, cluster_component_manager: ClusterComponentManager
    ) -> None:
        """
        Test that we can't take the cluster manager out of simulation mode.

        :param cluster_component_manager: a manager for an external cluster
        """
        with pytest.raises(
            NotImplementedError,
            match=("Unimplemented switcher mode 'SimulationMode.FALSE'."),
        ):
            cluster_component_manager.simulation_mode = SimulationMode.FALSE

    def test_component_shadow_master_pool_node_health_changed_callback(
        self: TestClusterComponentManager,
        cluster_component_manager: ClusterComponentManager,
        component_shadow_master_pool_node_health_changed_callback: MockCallable,
    ) -> None:
        """
        Test that the callback is called when a shadow master pool node changes health.

        :param cluster_component_manager: a manager for an external cluster
        :param component_shadow_master_pool_node_health_changed_callback:
            callback to be called when the health of a node in the
            shadow pool changes
        """
        cluster_component_manager.start_communicating()
        component_shadow_master_pool_node_health_changed_callback.assert_next_call(
            (HealthState.OK, HealthState.OK, HealthState.OK, HealthState.OK)
        )

        cluster_component_manager._component.simulate_node_failure(1, True)
        component_shadow_master_pool_node_health_changed_callback.assert_next_call(
            (HealthState.FAILED, HealthState.OK, HealthState.OK, HealthState.OK)
        )
