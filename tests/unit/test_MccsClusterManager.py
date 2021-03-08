#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTransientBuffer project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsClusterManagerDevice.
"""
import json

import pytest
from tango import AttrQuality, DevFailed, EventType

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState

from ska.low.mccs import MccsClusterManagerDevice, MccsDeviceProxy
from ska.low.mccs.cluster_manager.cluster_simulator import ClusterSimulator, JobStatus


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/extra.json",
        "package": "ska.low.mccs",
        "device": "clustermanager",
        "proxy": MccsDeviceProxy,
    }


class TestMccsClusterManagerDevice:
    """
    Test class for MccsClusterManagerDevice tests.
    """

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

    def test_jobsErrored(self, device_under_test):
        """
        Test for jobsErrored.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.jobsErrored
            == ClusterSimulator.JOB_STATS[JobStatus.ERRORED]
        )

    def test_jobsFailed(self, device_under_test):
        """
        Test for jobsFailed.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.jobsFailed == ClusterSimulator.JOB_STATS[JobStatus.FAILED]
        )

    def test_jobsFinished(self, device_under_test):
        """
        Test for jobsFinished.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.jobsFinished
            == ClusterSimulator.JOB_STATS[JobStatus.FINISHED]
        )

    def test_jobsKilled(self, device_under_test):
        """
        Test for test_jobsKilled.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.jobsKilled == ClusterSimulator.JOB_STATS[JobStatus.KILLED]
        )

    def test_jobsKilling(self, device_under_test):
        """
        Test for jobsKilling.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsKilling == list(
            ClusterSimulator.OPEN_JOBS.values()
        ).count(JobStatus.KILLING)

    def test_jobsLost(self, device_under_test):
        """
        Test for jobsLost.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsLost == ClusterSimulator.JOB_STATS[JobStatus.LOST]

    def test_jobsRunning(self, device_under_test):
        """
        Test for jobsRunning.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsRunning == list(
            ClusterSimulator.OPEN_JOBS.values()
        ).count(JobStatus.RUNNING)

    def test_jobsStaging(self, device_under_test):
        """
        Test for jobsStaging.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsStaging == list(
            ClusterSimulator.OPEN_JOBS.values()
        ).count(JobStatus.STAGING)

    def test_jobsStarting(self, device_under_test):
        """
        Test for jobsStarting.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsStarting == list(
            ClusterSimulator.OPEN_JOBS.values()
        ).count(JobStatus.STARTING)

    def test_jobsUnreachable(self, device_under_test):
        """
        Test for jobsUnreachable.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsUnreachable == list(
            ClusterSimulator.OPEN_JOBS.values()
        ).count(JobStatus.UNREACHABLE)

    def test_memoryTotal(self, device_under_test):
        """
        Test for memoryTotal.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.memoryTotal
            == ClusterSimulator.CONFIGURATION["memory_total"]
        )

    def test_memoryAvail(self, device_under_test):
        """
        Test for memoryAvail.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            pytest.approx(device_under_test.memoryAvail)
            == device_under_test.memoryTotal - device_under_test.memoryUsed
        )

    def test_memoryUsed(self, device_under_test):
        """
        Test for memoryUsed.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.memoryUsed
            == ClusterSimulator.RESOURCE_STATS["memory_used"]
        )

    def test_nodesInUse(self, device_under_test):
        """
        Test for nodesInUse.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.nodesInUse
            == ClusterSimulator.RESOURCE_STATS["nodes_in_use"]
        )

    def test_nodesAvail(self, device_under_test):
        """
        Test for nodesAvail.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            pytest.approx(device_under_test.nodesAvail)
            == device_under_test.nodesTotal - device_under_test.nodesInUse
        )

    def test_nodesTotal(self, device_under_test):
        """
        Test for nodesTotal.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.nodesTotal
            == ClusterSimulator.CONFIGURATION["nodes_total"]
        )

    def test_masterNodeId(self, device_under_test):
        """
        Test for masterNodeId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterNodeId
            == ClusterSimulator.CONFIGURATION["master_node_id"]
        )

    def test_masterCpusAllocatedPercent(self, device_under_test):
        """
        Test for masterCpusAllocatedPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            pytest.approx(device_under_test.masterCpusAllocatedPercent)
            == 100.0
            * device_under_test.masterCpusUsed
            / device_under_test.masterCpusTotal
        )

    def test_masterCpusUsed(self, device_under_test):
        """
        Test for masterCpusUsed.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterCpusUsed
            == ClusterSimulator.RESOURCE_STATS["master_cpus_used"]
        )

    def test_masterCpusTotal(self, device_under_test):
        """
        Test for masterCpusTotal.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterCpusTotal
            == ClusterSimulator.CONFIGURATION["master_cpus_total"]
        )

    def test_masterDiskPercent(self, device_under_test):
        """
        Test for masterDiskPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            pytest.approx(device_under_test.masterDiskPercent)
            == 100.0
            * device_under_test.masterDiskUsed
            / device_under_test.masterDiskTotal
        )

    def test_masterDiskUsed(self, device_under_test):
        """
        Test for masterDiskUsed.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterDiskUsed
            == ClusterSimulator.RESOURCE_STATS["master_disk_used"]
        )

    def test_masterDiskTotal(self, device_under_test):
        """
        Test for masterDiskTotal.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterDiskTotal
            == ClusterSimulator.CONFIGURATION["master_disk_total"]
        )

    def test_masterMemPercent(self, device_under_test):
        """
        Test for masterMemPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            pytest.approx(device_under_test.masterMemPercent)
            == 100.0
            * device_under_test.masterMemUsed
            / device_under_test.masterMemTotal
        )

    def test_masterMemUsed(self, device_under_test):
        """
        Test for masterMemUsed.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterMemUsed
            == ClusterSimulator.RESOURCE_STATS["master_mem_used"]
        )

    def test_masterMemTotal(self, device_under_test):
        """
        Test for masterMemTotal.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            device_under_test.masterMemTotal
            == ClusterSimulator.CONFIGURATION["master_mem_total"]
        )

    def test_shadowMasterPoolNodeIds(self, device_under_test):
        """
        Test for shadowMasterPoolNodeIds.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert (
            tuple(device_under_test.shadowMasterPoolNodeIds)
            == ClusterSimulator.CONFIGURATION["shadow_master_pool_node_ids"]
        )

    def test_shadowMasterPoolStatus(self, device_under_test):
        """
        Test for shadowMasterPoolStatus.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert tuple(device_under_test.shadowMasterPoolStatus) == (
            HealthState.OK,
        ) * len(device_under_test.shadowMasterPoolNodeIds)

    def test_StartJob(self, device_under_test):
        """
        Test for StartJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        for (job_id, status) in list(ClusterSimulator.OPEN_JOBS.items()):
            [[result_code], [message]] = device_under_test.StartJob(job_id)
            if status == JobStatus.STAGING:
                assert result_code == ResultCode.OK
                assert (
                    message
                    == MccsClusterManagerDevice.StartJobCommand.SUCCEEDED_MESSAGE
                )

                assert device_under_test.GetJobStatus(job_id) == JobStatus.RUNNING
            else:
                assert result_code == ResultCode.FAILED
                assert (
                    message
                    == ClusterSimulator.JOB_CANNOT_START_BECAUSE_NOT_STAGING_MESSAGE
                )

    def test_StopJob(self, device_under_test):
        """
        Test for StopJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        for job_id in list(ClusterSimulator.OPEN_JOBS):
            [[result_code], [message]] = device_under_test.StopJob(job_id)
            assert result_code == ResultCode.OK
            assert message == MccsClusterManagerDevice.StopJobCommand.SUCCEEDED_MESSAGE

            [[result_code], [message]] = device_under_test.StopJob(job_id)
            assert result_code == ResultCode.FAILED
            assert message == ClusterSimulator.NONEXISTENT_JOB_MESSAGE

    def test_SubmitJob(self, device_under_test):
        """
        Test for SubmitJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        job_config = json.dumps({"mock_key": "mock_value"})

        job_id = device_under_test.SubmitJob(job_config)
        assert device_under_test.GetJobStatus(job_id) == JobStatus.STAGING

    def test_GetJobStatus(self, device_under_test):
        """
        Test for GetJobStatus.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        for (job_id, status) in ClusterSimulator.OPEN_JOBS.items():
            assert status == device_under_test.GetJobStatus(job_id)

    def test_ClearJobStats(self, device_under_test):
        """
        Test for ClearJobStats.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.ClearJobStats()
        assert result_code == ResultCode.OK
        assert (
            message == MccsClusterManagerDevice.ClearJobStatsCommand.SUCCEEDED_MESSAGE
        )

    def test_PingMasterPool(self, device_under_test):
        """
        Test for PingMasterPool.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(
            DevFailed,
            match="ClusterSimulator.ping_master_pool has not been implemented",
        ):
            _ = device_under_test.PingMasterPool()
