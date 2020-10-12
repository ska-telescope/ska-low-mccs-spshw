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
from ska.base.commands import ResultCode
from tango import DevState

device_to_load = {
    "path": "charts/mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "clustermanager",
}


class TestMccsClusterManager(object):
    """
    Test class for MccsClusterManager tests.
    """

    def test_jobsError(self, device_under_test):
        """
        Test for jobsError

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsError == 0

    def test_jobsFailed(self, device_under_test):
        """
        Test for jobsFailed

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsFailed == 0

    def test_jobsFinished(self, device_under_test):
        """
        Test for jobsFinished

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsFinished == 0

    def test_jobsKilled(self, device_under_test):
        """
        Test for test_jobsKilled

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsKilled == 0

    def test_jobsKilling(self, device_under_test):
        """
        Test for jobsKilling

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsKilling == 0

    def test_jobsLost(self, device_under_test):
        """
        Test for jobsLost

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsLost == 0

    def test_jobsRunning(self, device_under_test):
        """
        Test for jobsRunning

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsRunning == 0

    def test_jobsStaging(self, device_under_test):
        """
        Test for jobsStaging

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsStaging == 0

    def test_jobsUnreachable(self, device_under_test):
        """
        Test for jobsUnreachable

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.jobsUnreachable == 0

    def test_memoryTotal(self, device_under_test):
        """
        Test for memoryTotal

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.memoryTotal == 0.0

    def test_memoryAvail(self, device_under_test):
        """
        Test for memoryAvail

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.memoryAvail == 0.0

    def test_memoryUsed(self, device_under_test):
        """
        Test for memoryUsed

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.memoryUsed == 0.0

    def test_nodesInUse(self, device_under_test):
        """
        Test for nodesInUse

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.nodesInUse == 0

    def test_nodesTotal(self, device_under_test):
        """
        Test for nodesTotal

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.nodesTotal == 0

    def test_masterNodeId(self, device_under_test):
        """
        Test for masterNodeId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterNodeId == 0

    def test_masterCpusAllocatedPercent(self, device_under_test):
        """
        Test for masterCpusAllocatedPercent

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterCpusAllocatedPercent == 0.0

    def test_masterCpusUsed(self, device_under_test):
        """
        Test for masterCpusUsed

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterCpusUsed == 0

    def test_masterCpusTotal(self, device_under_test):
        """
        Test for masterCpusTotal

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterCpusTotal == 0

    def test_masterDiskPercent(self, device_under_test):
        """
        Test for masterDiskPercent

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterDiskPercent == 0.0

    def test_masterDiskUsed(self, device_under_test):
        """
        Test for masterDiskUsed

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterDiskUsed == 0.0

    def test_masterDiskTotal(self, device_under_test):
        """
        Test for masterDiskTotal

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterDiskTotal == 0.0

    def test_masterMemPercent(self, device_under_test):
        """
        Test for masterMemPercent

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterMemPercent == 0.0

    def test_masterMemUsed(self, device_under_test):
        """
        Test for masterMemUsed

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterMemUsed == 0.0

    def test_masterMemTotal(self, device_under_test):
        """
        Test for masterMemTotal

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.masterMemTotal == 0.0

    def test_shadowMasterPoolNodeIds(self, device_under_test):
        """
        Test for shadowMasterPoolNodeIds

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.shadowMasterPoolNodeIds == (0,)

    def test_shadowMasterPoolStatus(self, device_under_test):
        """
        Test for shadowMasterPoolStatus

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.shadowMasterPoolStatus == (DevState.UNKNOWN,)

    def test_StartJob(self, device_under_test):
        """
        Test for StartJob

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StartJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StartJobCommand(), does nothing"

    def test_StopJob(self, device_under_test):
        """
        Test for StopJob

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.StopJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StopJobCommand(), does nothing"

    def test_SubmitJob(self, device_under_test):
        """
        Test for SubmitJob

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.SubmitJob(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of SubmitJobCommand(), does nothing"

    def test_GetJobStatus(self, device_under_test):
        """
        Test for GetJobStatus

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.GetJobStatus(0)
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of GetJobStatusCommand(), does nothing"

    def test_ClearJobStats(self, device_under_test):
        """
        Test for ClearJobStats

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.ClearJobStats()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of ClearJobStatsCommand(), does nothing"

    def test_PingMasterPool(self, device_under_test):
        """
        Test for PingMasterPool

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.PingMasterPool()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of PingMasterPoolCommand(), does nothing"
