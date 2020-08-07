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
This module contains the tests for MccsClusterManager.
"""
from ska.base.control_model import LoggingLevel
from ska.low.mccs import MccsClusterManager
from ska.base.commands import ResultCode
from tango import DevState

device_info = {
    "class": MccsClusterManager,
    "properties": {"SkaLevel": "4", "LoggingLevelDefault": "4"},
}


class TestMccsClusterManager(object):
    """
    Test class for MccsClusterManager tests.
    """

    def test_properties(self, device_under_test):
        """Test the properties """
        assert device_under_test.loggingLevel == LoggingLevel.INFO

    def test_jobsError(self, device_under_test):
        """Test for jobsError"""
        assert device_under_test.jobsError == 0

    def test_jobsFailed(self, device_under_test):
        """Test for jobsFailed"""
        assert device_under_test.jobsFailed == 0

    def test_jobsFinished(self, device_under_test):
        """Test for jobsFinished"""
        assert device_under_test.jobsFinished == 0

    def test_jobsKilled(self, device_under_test):
        """Test for test_jobsKilled"""
        assert device_under_test.jobsKilled == 0

    def test_jobsKilling(self, device_under_test):
        """Test for jobsKilling"""
        assert device_under_test.jobsKilling == 0

    def test_jobsLost(self, device_under_test):
        """Test for jobsLost"""
        assert device_under_test.jobsLost == 0

    def test_jobsRunning(self, device_under_test):
        """Test for jobsRunning"""
        assert device_under_test.jobsRunning == 0

    def test_jobsStaging(self, device_under_test):
        """Test for jobsStaging"""
        assert device_under_test.jobsStaging == 0

    def test_jobsUnreachable(self, device_under_test):
        """Test for jobsUnreachable"""
        assert device_under_test.jobsUnreachable == 0

    def test_memoryTotal(self, device_under_test):
        """Test for memoryTotal"""
        assert device_under_test.memoryTotal == 0.0

    def test_memoryAvail(self, device_under_test):
        """Test for memoryAvail"""
        assert device_under_test.memoryAvail == 0.0

    def test_memoryUsed(self, device_under_test):
        """Test for memoryUsed"""
        assert device_under_test.memoryUsed == 0.0

    def test_nodesInUse(self, device_under_test):
        """Test for nodesInUse"""
        assert device_under_test.nodesInUse == 0

    def test_nodesTotal(self, device_under_test):
        """Test for nodesTotal"""
        assert device_under_test.nodesTotal == 0

    def test_masterNodeId(self, device_under_test):
        """Test for masterNodeId"""
        assert device_under_test.masterNodeId == 0

    def test_masterCpusAllocatedPercent(self, device_under_test):
        """Test for masterCpusAllocatedPercent"""
        assert device_under_test.masterCpusAllocatedPercent == 0.0

    def test_masterCpusUsed(self, device_under_test):
        """Test for masterCpusUsed"""
        assert device_under_test.masterCpusUsed == 0

    def test_masterCpusTotal(self, device_under_test):
        """Test for masterCpusTotal"""
        assert device_under_test.masterCpusTotal == 0

    def test_masterDiskPercent(self, device_under_test):
        """Test for masterDiskPercent"""
        assert device_under_test.masterDiskPercent == 0.0

    def test_masterDiskUsed(self, device_under_test):
        """Test for masterDiskUsed"""
        assert device_under_test.masterDiskUsed == 0.0

    def test_masterDiskTotal(self, device_under_test):
        """Test for masterDiskTotal"""
        assert device_under_test.masterDiskTotal == 0.0

    def test_masterMemPercent(self, device_under_test):
        """Test for masterMemPercent"""
        assert device_under_test.masterMemPercent == 0.0

    def test_masterMemUsed(self, device_under_test):
        """Test for masterMemUsed"""
        assert device_under_test.masterMemUsed == 0.0

    def test_masterMemTotal(self, device_under_test):
        """Test for masterMemTotal"""
        assert device_under_test.masterMemTotal == 0.0

    def test_shadowMasterPoolNodeIds(self, device_under_test):
        """Test for shadowMasterPoolNodeIds"""
        assert device_under_test.shadowMasterPoolNodeIds == (0,)

    def test_shadowMasterPoolStatus(self, device_under_test):
        """Test for shadowMasterPoolStatus"""
        assert device_under_test.shadowMasterPoolStatus == (DevState.UNKNOWN,)

    def test_StartJob(self, device_under_test):
        """Test for StartJob"""
        [[result_code], [message]] = device_under_test.StartJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StartJobCommand(), does nothing"

    def test_StopJob(self, device_under_test):
        """Test for StopJob"""
        [[result_code], [message]] = device_under_test.StopJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StopJobCommand(), does nothing"

    def test_SubmitJob(self, device_under_test):
        """Test for SubmitJob"""
        [[result_code], [message]] = device_under_test.SubmitJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of SubmitJobCommand(), does nothing"

    def test_GetJobStatus(self, device_under_test):
        """Test for GetJobStatus"""
        [[result_code], [message]] = device_under_test.GetJobStatus(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of GetJobStatusCommand(), does nothing"

    def test_ClearJobStats(self, device_under_test):
        """Test for ClearJobStats"""
        [[result_code], [message]] = device_under_test.ClearJobStats()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of ClearJobStatsCommand(), does nothing"

    def test_PingMasterPool(self, device_under_test):
        """Test for PingMasterPool"""
        [[result_code], [message]] = device_under_test.PingMasterPool()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of PingMasterPoolCommand(), does nothing"
