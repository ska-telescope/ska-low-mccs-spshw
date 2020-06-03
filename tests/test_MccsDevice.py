###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsDevice.
"""

import pytest
from tango import DevState
from ska.base.control_model import LoggingLevel
from ska.low.mccs import MccsDevice, release


device_info = {
    "class": MccsDevice,
    "properties": {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        # "LoggingTargetsDefault": "",
    }
}


class TestMccsDevice(object):
    """
    Test class for MccsDevice tests.
    """

    @pytest.mark.skip(reason="Not implemented")
    def test_properties(self, device_under_test):
        """
        Test for device properties. Not implemented.
        """
        pass

    def test_State(self, device_under_test):
        """Test for State"""
        assert device_under_test.State() == DevState.UNKNOWN

    def test_Status(self, device_under_test):
        """Test for Status"""
        status = "The device is in UNKNOWN state."
        assert device_under_test.Status() == status

    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [info]

    def test_Reset(self, device_under_test):
        """Test for Reset"""
        assert device_under_test.Reset() is None

    def test_ExceptionCallback(self, device_under_test):
        """Test for ExceptionCallback"""
        assert device_under_test.ExceptionCallback() is None

    def test_DefaultAlarmOnCallback(self, device_under_test):
        """Test for DefaultAlarmOnCallback"""
        assert device_under_test.DefaultAlarmOnCallback() is None

    def test_DefaultAlarmOffCallback(self, device_under_test):
        """Test for DefaultAlarmOffCallback"""
        assert device_under_test.DefaultAlarmOffCallback() is None

    def test_GetFullReport(self, device_under_test):
        """Test for GetFullReport"""
        assert device_under_test.GetFullReport() is None

    def test_GetCommandReport(self, device_under_test):
        """Test for GetCommandReport"""
        assert device_under_test.GetCommandReport() == [""]

    def test_GetAttributeReport(self, device_under_test):
        """Test for GetAttributeReport"""
        assert device_under_test.GetAttributeReport() == [""]

    def test_ConstructDeviceProxyAddress(self, device_under_test):
        """Test for ConstructDeviceProxyAddress"""
        assert device_under_test.ConstructDeviceProxyAddress("") is None

    def test_buildState(self, device_under_test):
        """Test for buildState"""
        print(device_under_test.buildState)
        assert device_under_test.buildState == (
            ", ".join((release.name, release.version, release.description))
        )  # noqa: E501

    def test_loggingLevel(self, device_under_test):
        """Test for loggingLevel"""
        assert device_under_test.loggingLevel == LoggingLevel.INFO

    def test_healthState(self, device_under_test):
        """Test for healthState"""
        assert device_under_test.healthState == 0

    def test_adminMode(self, device_under_test):
        """Test for adminMode"""
        assert device_under_test.adminMode == 0

    def test_controlMode(self, device_under_test):
        """Test for controlMode"""
        assert device_under_test.controlMode == 0

    def test_simulationMode(self, device_under_test):
        """Test for simulationMode"""
        assert device_under_test.simulationMode == 0

    def test_testMode(self, device_under_test):
        """Test for testMode"""
        assert device_under_test.testMode == 0

    def test_isHardwareDevice(self, device_under_test):
        """Test for isHardwareDevice"""
        assert device_under_test.isHardwareDevice is False

    def test_diagMode(self, device_under_test):
        """Test for diagMode"""
        assert device_under_test.diagMode is False

    def test_calledUndefinedDevice(self, device_under_test):
        """Test for calledUndefinedDevice"""
        assert device_under_test.calledUndefinedDevice is False

    def test_calledDeadServer(self, device_under_test):
        """Test for calledDeadServer"""
        assert device_under_test.calledDeadServer is False

    def test_detectedDeadServer(self, device_under_test):
        """Test for detectedDeadServer"""
        assert device_under_test.detectedDeadServer is False

    def test_calledNonRunningDevice(self, device_under_test):
        """Test for calledNonRunningDevice"""
        assert device_under_test.calledNonRunningDevice is False

    def test_callTimeout(self, device_under_test):
        """Test for callTimeout"""
        assert device_under_test.callTimeout is False

    def test_callCommFailed(self, device_under_test):
        """Test for callCommFailed"""
        assert device_under_test.callCommFailed is False

    def test_invalidAsynId(self, device_under_test):
        """Test for invalidAsynId"""
        assert device_under_test.invalidAsynId is False

    def test_calledInexistentCallback(self, device_under_test):
        """Test for calledInexistentCalback"""
        assert device_under_test.calledInexistentCallback is False

    def test_requestIdMismatch(self, device_under_test):
        """Test for requestIdMismatch"""
        assert device_under_test.requestIdMismatch is False

    def test_expectedReplyNotReady(self, device_under_test):
        """Test for expectedReplyNotReady"""
        assert device_under_test.expectedReplyNotReady is False

    def test_experiencedSubscriptionFailure(self, device_under_test):
        """Test for experiencedSubscriptionFailure"""
        assert device_under_test.experiencedSubscriptionFailure is False

    def test_invalidEventId(self, device_under_test):
        """Test for invalidEventId"""
        assert device_under_test.invalidEventId is False

    def test_loggingTargets(self, device_under_test):
        """Test for loggingTargets"""
        assert device_under_test.loggingTargets == ('tango::logger',)
