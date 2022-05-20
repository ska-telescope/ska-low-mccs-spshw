# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the MCCS cluster manager device."""
from __future__ import annotations

import json
from typing import Any, cast
import time

import pytest
import tango
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import AdminMode, HealthState
from tango import DevFailed

from ska_low_mccs import MccsClusterManagerDevice, MccsDeviceProxy
from ska_low_mccs.cluster_manager.cluster_simulator import ClusterSimulator, JobStatus
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/extra.json",
        "package": "ska_low_mccs",
        "device": "clustermanager",
        "proxy": MccsDeviceProxy,
    }


class TestMccsClusterManagerDevice:
    """Test class for MccsClusterManagerDevice tests."""

    @pytest.fixture()
    def device_under_test(
        self: TestMccsClusterManagerDevice, tango_harness: TangoHarness
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/clustermanager/clustermanager")

    def test_healthState(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

    @pytest.mark.parametrize(
        ("attribute_name", "attribute_value"),
        [
            ("jobsErrored", ClusterSimulator.JOB_STATS[JobStatus.ERRORED]),
            ("jobsFailed", ClusterSimulator.JOB_STATS[JobStatus.FAILED]),
            ("jobsFinished", ClusterSimulator.JOB_STATS[JobStatus.FINISHED]),
            ("jobsKilled", ClusterSimulator.JOB_STATS[JobStatus.KILLED]),
            (
                "jobsKilling",
                list(ClusterSimulator.OPEN_JOBS.values()).count(JobStatus.KILLING),
            ),
            ("jobsLost", ClusterSimulator.JOB_STATS[JobStatus.LOST]),
            (
                "jobsRunning",
                list(ClusterSimulator.OPEN_JOBS.values()).count(JobStatus.RUNNING),
            ),
            (
                "jobsStaging",
                list(ClusterSimulator.OPEN_JOBS.values()).count(JobStatus.STAGING),
            ),
            (
                "jobsStarting",
                list(ClusterSimulator.OPEN_JOBS.values()).count(JobStatus.STARTING),
            ),
            (
                "jobsUnreachable",
                list(ClusterSimulator.OPEN_JOBS.values()).count(JobStatus.UNREACHABLE),
            ),
            ("memoryTotal", ClusterSimulator.CONFIGURATION["memory_total"]),
            ("memoryUsed", ClusterSimulator.RESOURCE_STATS["memory_used"]),
            ("nodesInUse", ClusterSimulator.RESOURCE_STATS["nodes_in_use"]),
            ("nodesTotal", ClusterSimulator.CONFIGURATION["nodes_total"]),
            ("masterNodeId", ClusterSimulator.CONFIGURATION["master_node_id"]),
            (
                "masterCpusUsed",
                ClusterSimulator.RESOURCE_STATS["master_cpus_used"],
            ),
            (
                "masterCpusTotal",
                ClusterSimulator.CONFIGURATION["master_cpus_total"],
            ),
            (
                "masterDiskUsed",
                ClusterSimulator.RESOURCE_STATS["master_disk_used"],
            ),
            (
                "masterDiskTotal",
                ClusterSimulator.CONFIGURATION["master_disk_total"],
            ),
            (
                "masterMemUsed",
                ClusterSimulator.RESOURCE_STATS["master_mem_used"],
            ),
            (
                "masterMemTotal",
                ClusterSimulator.CONFIGURATION["master_mem_total"],
            ),
        ],
    )
    def test_attribute_constant_values(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        attribute_name: str,
        attribute_value: Any,
    ) -> None:
        """
        Test those attributes that take a constant initial value.

        (That is, test attributes whose initial value can be calculated
        using only class variables. i.e. in the parametrize decorator.)

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param attribute_name: name of the attribute under test.
        :param attribute_value: expected value of the attribute under
            test.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = getattr(device_under_test, attribute_name)

        device_under_test.adminMode = AdminMode.ONLINE

        assert getattr(device_under_test, attribute_name) == attribute_value

    def test_memoryAvail(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for memoryAvail.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.memoryAvail
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.memoryAvail == pytest.approx(
            device_under_test.memoryTotal - device_under_test.memoryUsed
        )

    def test_nodesAvail(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for nodesAvail.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.nodesAvail
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.nodesAvail == pytest.approx(
            device_under_test.nodesTotal - device_under_test.nodesInUse
        )

    def test_masterCpusAllocatedPercent(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for masterCpusAllocatedPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.masterCpusAllocatedPercent
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.masterCpusAllocatedPercent == pytest.approx(
            100.0 * device_under_test.masterCpusUsed / device_under_test.masterCpusTotal
        )

    def test_masterDiskPercent(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for masterDiskPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.masterDiskPercent
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.masterDiskPercent == pytest.approx(
            100.0 * device_under_test.masterDiskUsed / device_under_test.masterDiskTotal
        )

    def test_masterMemPercent(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for masterMemPercent.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.masterMemPercent
        device_under_test.adminMode = AdminMode.ONLINE
        assert device_under_test.masterMemPercent == pytest.approx(
            100.0 * device_under_test.masterMemUsed / device_under_test.masterMemTotal
        )

    def test_shadowMasterPoolNodeIds(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for shadowMasterPoolNodeIds.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.shadowMasterPoolNodeIds
        device_under_test.adminMode = AdminMode.ONLINE
        assert (
            tuple(device_under_test.shadowMasterPoolNodeIds)
            == ClusterSimulator.CONFIGURATION["shadow_master_pool_node_ids"]
        )

    def test_shadowMasterPoolStatus(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for shadowMasterPoolStatus.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(
            DevFailed, match="Communication with component is not established"
        ):
            _ = device_under_test.shadowMasterPoolStatus
        device_under_test.adminMode = AdminMode.ONLINE
        assert tuple(device_under_test.shadowMasterPoolStatus) == (
            HealthState.OK,
        ) * len(device_under_test.shadowMasterPoolNodeIds)

    def test_StartJob(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for StartJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_status_changed_callback: callback which reports the
            status of the submitted slow command.
        """
        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        assert (
            "longRunningCommandStatus".casefold()
            in device_under_test._change_event_subscription_ids
        )

        # Initialisation event.
        lrc_status_changed_callback.assert_next_change_event(
            None, tango._tango.AttrQuality.ATTR_VALID
        )

        ([result_code], [message]) = device_under_test.StartJob(
            next(iter(ClusterSimulator.OPEN_JOBS))
        )
        # Even when comms are not ESTABLISHED we can still queue the command.
        assert result_code == ResultCode.QUEUED
        assert "StartJob" in message.split("/")[-1]

        # lrc_status[0][1] contains the status and ID of all commands submitted.
        # We expect a "QUEUED" event...
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert message, "QUEUED" in lrc_status[0][1]
        # Followed by "IN_PROGRESS" when a worker thread picks it up...
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert message, "IN_PROGRESS" in lrc_status[0][1]
        # But then we expect "FAILED" due to comms not being ESTABLISHED.
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert message, "FAILED" in lrc_status[0][1]

        device_under_test.adminMode = AdminMode.ONLINE

        for (job_id, status) in list(ClusterSimulator.OPEN_JOBS.items()):
            print(f"Current job id: {job_id}")
            ([result_code], [message]) = device_under_test.StartJob(job_id)
            assert result_code == ResultCode.QUEUED
            assert "StartJob" in message.split("/")[-1]

            # We'll always expect these two events first whether the command
            # is expected to succeed or fail.
            lrc_status = lrc_status_changed_callback.get_next_call()
            assert message, "QUEUED" in lrc_status[0][1]
            lrc_status = lrc_status_changed_callback.get_next_call()
            assert message, "IN_PROGRESS" in lrc_status[0][1]

            if status == JobStatus.STAGING:
                lrc_status = lrc_status_changed_callback.get_next_call()
                assert message, "COMPLETED" in lrc_status[0][1]
                assert device_under_test.GetJobStatus(job_id) == JobStatus.RUNNING
            else:
                lrc_status = lrc_status_changed_callback.get_next_call()
                assert message, "FAILED" in lrc_status[0][1]

    def test_StopJob(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for StopJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        # ([result_code], [message]) = device_under_test.StopJob(
        #     next(iter(ClusterSimulator.OPEN_JOBS))
        # )
        # assert result_code == ResultCode.FAILED
        # assert "Communication with component is not established" in message
        ([result_code], [message]) = device_under_test.StopJob(
            next(iter(ClusterSimulator.OPEN_JOBS))
        )
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "StopJob"

        print(lrc_status_changed_callback.get_next_call())
        print(lrc_status_changed_callback.get_next_call())
        print(lrc_status_changed_callback.get_next_call())
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert "FAILED" in lrc_status[0][1]
        print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert (
            "\"Exception: Cannot execute 'ClusterSimulatorComponentManager._get_from_component'. Communication with component is not established.\""
            in lrc_result[0][1]
        )

        device_under_test.adminMode = AdminMode.ONLINE

        for job_id in list(ClusterSimulator.OPEN_JOBS):

            # job_id = device_under_test.SubmitJob(job_config)
            # assert device_under_test.GetJobStatus(job_id) == JobStatus.STAGING
            ([result_code], [message]) = device_under_test.StopJob(job_id)
            assert result_code == ResultCode.QUEUED
            assert message.split("_")[-1] == "StopJob"
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")

            lrc_result = lrc_result_changed_callback.get_next_call()
            assert '"The stop job task has completed"' in lrc_result[0][1]

            ([result_code], [message]) = device_under_test.StopJob(job_id)
            assert result_code == ResultCode.QUEUED
            assert message.split("_")[-1] == "StopJob"
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
            print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")

        # device_under_test.adminMode = AdminMode.ONLINE

        # for job_id in list(ClusterSimulator.OPEN_JOBS):
        #     [[result_code], [message]] = device_under_test.StopJob(job_id)
        #     assert result_code == ResultCode.OK
        #     assert message == MccsClusterManagerDevice.StopJobCommand.SUCCEEDED_MESSAGE

        #     [[result_code], [message]] = device_under_test.StopJob(job_id)
        #     assert result_code == ResultCode.FAILED
        #     assert message == ClusterSimulator.NONEXISTENT_JOB_MESSAGE

    def test_SubmitJob(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for SubmitJob.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        job_config = json.dumps({"mock_key": "mock_value"})
        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )

        ([result_code], [message]) = device_under_test.SubmitJob(job_config)
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "SubmitJob"

        print(lrc_status_changed_callback.get_next_call())
        print(lrc_status_changed_callback.get_next_call())
        print(lrc_status_changed_callback.get_next_call())
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert "FAILED" in lrc_status[0][1]
        print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert (
            "\"Exception: Cannot execute 'ClusterSimulatorComponentManager._get_from_component'. Communication with component is not established.\""
            in lrc_result[0][1]
        )

        device_under_test.adminMode = AdminMode.ONLINE
        # job_id = device_under_test.SubmitJob(job_config)
        # assert device_under_test.GetJobStatus(job_id) == JobStatus.STAGING
        ([result_code], [message]) = device_under_test.SubmitJob(job_config)

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert '"The submit job task has completed"' in lrc_result[0][1]

        # TODO: need to assert JobStatus is JobStatus.STAGING

    def test_GetJobStatus(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for GetJobStatus.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )

        ([result_code], [message]) = device_under_test.GetJobStatus(
            next(iter(ClusterSimulator.OPEN_JOBS))
        )
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "GetJobStatus"

        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert "FAILED" in lrc_status[0][1]
        print(f"!!LRC result: {lrc_result_changed_callback.get_next_call()}")

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert (
            "\"Exception: Cannot execute 'ClusterSimulatorComponentManager._get_from_component'. Communication with component is not established.\""
            in lrc_result[0][1]
        )

        device_under_test.adminMode = AdminMode.ONLINE

        for (job_id, status) in ClusterSimulator.OPEN_JOBS.items():
            ([result_code], [message]) = device_under_test.GetJobStatus(job_id)
            print([result_code], [message])
            lrc_result = lrc_result_changed_callback.get_next_call()
            assert '"The get job status task has completed"' in lrc_result[0][1]

            ##TODO: how do we check the status is correct now??

    def test_ClearJobStats(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for ClearJobStats.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )
        # with pytest.raises(
        #     DevFailed,
        #     match="Communication with component is not established",
        # ):
        #     ([result_code], [message]) = device_under_test.ClearJobStats()
        # assert result_code == ResultCode.FAILED
        # assert "Communication with component is not established" in message

        ([result_code], [message]) = device_under_test.ClearJobStats()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "ClearJobStats"

        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")

        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")
        # print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")
        # device_under_test.adminMode = AdminMode.ONLINE
        lrc_result = lrc_result_changed_callback.get_next_call()
        assert lrc_result.contains(
            "Exception: Cannot execute 'ClusterSimulatorComponentManager._get_from_component'. Communication with component is not established."
        )

        device_under_test.adminMode = AdminMode.ONLINE

        ([result_code], [message]) = device_under_test.ClearJobStats()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "ClearJobStats"

        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")

        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        # print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        # print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")
        lrc_status = lrc_status_changed_callback.get_next_call()
        assert "COMPLETED" in lrc_status[0][1]

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert '"The clear job stats task has completed"' in lrc_result[0][1]
        # ([result_code], [message]) = device_under_test.ClearJobStats()
        # assert result_code == ResultCode.OK
        # assert (
        #     message == MccsClusterManagerDevice.ClearJobStatsCommand.SUCCEEDED_MESSAGE
        # )

    def test_PingMasterPool(
        self: TestMccsClusterManagerDevice,
        device_under_test: MccsDeviceProxy,
        lrc_status_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for PingMasterPool.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        # with pytest.raises(
        #     DevFailed,
        #     match="Communication with component is not established",
        # ):

        device_under_test.add_change_event_callback(
            "longRunningCommandStatus",
            lrc_status_changed_callback,
        )
        assert (
            "longRunningCommandStatus".casefold()
            in device_under_test._change_event_subscription_ids
        )
        device_under_test.add_change_event_callback(
            "longRunningCommandResult",
            lrc_result_changed_callback,
        )

        ([result_code], [message]) = device_under_test.PingMasterPool()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PingMasterPool"

        time.sleep(0.1)
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")
        print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")

        # But we expect it to have failed when a worker thread picks it up.
        lrc_id, lrc_status = device_under_test.longRunningCommandStatus
        print(lrc_id, lrc_status)
        assert lrc_id == message
        assert lrc_status == "FAILED"

        device_under_test.adminMode = AdminMode.ONLINE

        ([result_code], [message]) = device_under_test.PingMasterPool()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "PingMasterPool"

        # print(f"LRC result: {lrc_result_changed_callback.get_next_call()}")
        print(f"LRC status: {lrc_status_changed_callback.get_next_call()}")
        print(f"lrcStatus: {device_under_test.longRunningCommandStatus}")

        # lrc_id, lrc_status = device_under_test.longRunningCommandStatus
        # print(lrc_id, lrc_status)
        # assert lrc_id == message
        # assert lrc_status == "FAILED"

        lrc_result = lrc_result_changed_callback.get_next_call()
        assert (
            '"Exception: ClusterSimulator.ping_master_pool has not been implemented"'
            in lrc_result[0][1]
        )
