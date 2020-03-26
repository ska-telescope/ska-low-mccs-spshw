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
"""Contain the tests for the Mccs Base Device."""

# Imports
import pytest

from tango import DevState

# from ska.mccs import release
from ska.base.control_model import LoggingLevel
from ska.mccs import release


# Device test case
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsDevice(object):
    """Test case for packet generation."""

    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsDevice.numpy = MagicMock()

    def test_properties(self, tango_context):
        # Test the properties
        pass

    def test_State(self, tango_context):
        """Test for State"""
        assert tango_context.device.State() == DevState.UNKNOWN

    def test_Status(self, tango_context):
        """Test for Status"""
        status = "The device is in UNKNOWN state."
        assert tango_context.device.Status() == status

    #     def test_buildState(self, tango_context):
    #         """Test for buildState"""
    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        info = release.get_release_info(tango_context.class_name)
        assert tango_context.device.GetVersionInfo() == [info]

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is None

    def test_ExceptionCallback(self, tango_context):
        """Test for ExceptionCallback"""
        assert tango_context.device.ExceptionCallback() is None

    def test_DefaultAlarmOnCallback(self, tango_context):
        """Test for DefaultAlarmOnCallback"""
        assert tango_context.device.DefaultAlarmOnCallback() is None

    def test_DefaultAlarmOffCallback(self, tango_context):
        """Test for DefaultAlarmOffCallback"""
        assert tango_context.device.DefaultAlarmOffCallback() is None

    def test_GetFullReport(self, tango_context):
        """Test for GetFullReport"""
        assert tango_context.device.GetFullReport() is None

    def test_GetCommandReport(self, tango_context):
        """Test for GetCommandReport"""
        assert tango_context.device.GetCommandReport() == [""]

    def test_GetAttributeReport(self, tango_context):
        """Test for GetAttributeReport"""
        assert tango_context.device.GetAttributeReport() == [""]

    def test_ConstructDeviceProxyAddress(self, tango_context):
        """Test for ConstructDeviceProxyAddress"""
        assert tango_context.device.ConstructDeviceProxyAddress("") is None

    #     def test_buildState(self, tango_context):
    #         """Test for buildState"""
    #         print(tango_context.device.buildState)
    #         assert tango_context.device.buildState ==  (", ".join((release.name, release.version, release.description))) # noqa: E501

    def test_loggingLevel(self, tango_context):
        """Test for loggingLevel"""
        assert tango_context.device.loggingLevel == LoggingLevel.INFO

    def test_healthState(self, tango_context):
        """Test for healthState"""
        assert tango_context.device.healthState == 0

    def test_adminMode(self, tango_context):
        """Test for adminMode"""
        assert tango_context.device.adminMode == 0

    def test_controlMode(self, tango_context):
        """Test for controlMode"""
        assert tango_context.device.controlMode == 0

    def test_simulationMode(self, tango_context):
        """Test for simulationMode"""
        assert tango_context.device.simulationMode == 0

    def test_testMode(self, tango_context):
        """Test for testMode"""
        assert tango_context.device.testMode == 0

    def test_isHardwareDevice(self, tango_context):
        """Test for isHardwareDevice"""
        assert tango_context.device.isHardwareDevice is False

    def test_diagMode(self, tango_context):
        """Test for diagMode"""
        assert tango_context.device.diagMode is False

    def test_calledUndefinedDevice(self, tango_context):
        """Test for calledUndefinedDevice"""
        assert tango_context.device.calledUndefinedDevice is False

    def test_calledDeadServer(self, tango_context):
        """Test for calledDeadServer"""
        assert tango_context.device.calledDeadServer is False

    def test_detectedDeadServer(self, tango_context):
        """Test for detectedDeadServer"""
        assert tango_context.device.detectedDeadServer is False

    def test_calledNonRunningDevice(self, tango_context):
        """Test for calledNonRunningDevice"""
        assert tango_context.device.calledNonRunningDevice is False

    def test_callTimeout(self, tango_context):
        """Test for callTimeout"""
        assert tango_context.device.callTimeout is False

    def test_callCommFailed(self, tango_context):
        """Test for callCommFailed"""
        assert tango_context.device.callCommFailed is False

    def test_invalidAsynId(self, tango_context):
        """Test for invalidAsynId"""
        assert tango_context.device.invalidAsynId is False

    def test_calledInexistentCallback(self, tango_context):
        """Test for calledInexistentCalback"""
        assert tango_context.device.calledInexistentCallback is False

    def test_requestIdMismatch(self, tango_context):
        """Test for requestIdMismatch"""
        assert tango_context.device.requestIdMismatch is False

    def test_expectedReplyNotReady(self, tango_context):
        """Test for expectedReplyNotReady"""
        assert tango_context.device.expectedReplyNotReady is False

    def test_experiencedSubscriptionFailure(self, tango_context):
        """Test for experiencedSubscriptionFailure"""
        assert tango_context.device.experiencedSubscriptionFailure is False

    def test_invalidEventId(self, tango_context):
        """Test for invalidEventId"""
        assert tango_context.device.invalidEventId is False

    def test_loggingTargets(self, tango_context):
        """Test for loggingTargets"""
        assert tango_context.device.loggingTargets == ()
