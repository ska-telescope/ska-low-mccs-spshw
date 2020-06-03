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

from tango import DevState
from ska.base.control_model import LoggingLevel
from ska.low.mccs import release


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

    def test_properties(self, tango_device):
        # Test the properties
        pass

    def test_State(self, tango_device):
        """Test for State"""
        assert tango_device.State() == DevState.UNKNOWN

    def test_Status(self, tango_device):
        """Test for Status"""
        status = "The device is in UNKNOWN state."
        assert tango_device.Status() == status

    def test_GetVersionInfo(self, tango_device):
        """Test for GetVersionInfo"""
        info = release.get_release_info(tango_device.info().dev_class)
        assert tango_device.GetVersionInfo() == [info]

    def test_Reset(self, tango_device):
        """Test for Reset"""
        assert tango_device.Reset() is None

    def test_ExceptionCallback(self, tango_device):
        """Test for ExceptionCallback"""
        assert tango_device.ExceptionCallback() is None

    def test_DefaultAlarmOnCallback(self, tango_device):
        """Test for DefaultAlarmOnCallback"""
        assert tango_device.DefaultAlarmOnCallback() is None

    def test_DefaultAlarmOffCallback(self, tango_device):
        """Test for DefaultAlarmOffCallback"""
        assert tango_device.DefaultAlarmOffCallback() is None

    def test_GetFullReport(self, tango_device):
        """Test for GetFullReport"""
        assert tango_device.GetFullReport() is None

    def test_GetCommandReport(self, tango_device):
        """Test for GetCommandReport"""
        assert tango_device.GetCommandReport() == [""]

    def test_GetAttributeReport(self, tango_device):
        """Test for GetAttributeReport"""
        assert tango_device.GetAttributeReport() == [""]

    def test_ConstructDeviceProxyAddress(self, tango_device):
        """Test for ConstructDeviceProxyAddress"""
        assert tango_device.ConstructDeviceProxyAddress("") is None

    def test_buildState(self, tango_device):
        """Test for buildState"""
        print(tango_device.buildState)
        assert tango_device.buildState == (
            ", ".join((release.name, release.version, release.description))
        )  # noqa: E501

    def test_loggingLevel(self, tango_device):
        """Test for loggingLevel"""
        assert tango_device.loggingLevel == LoggingLevel.INFO

    def test_healthState(self, tango_device):
        """Test for healthState"""
        assert tango_device.healthState == 0

    def test_adminMode(self, tango_device):
        """Test for adminMode"""
        assert tango_device.adminMode == 0

    def test_controlMode(self, tango_device):
        """Test for controlMode"""
        assert tango_device.controlMode == 0

    def test_simulationMode(self, tango_device):
        """Test for simulationMode"""
        assert tango_device.simulationMode == 0

    def test_testMode(self, tango_device):
        """Test for testMode"""
        assert tango_device.testMode == 0

    def test_isHardwareDevice(self, tango_device):
        """Test for isHardwareDevice"""
        assert tango_device.isHardwareDevice is False

    def test_diagMode(self, tango_device):
        """Test for diagMode"""
        assert tango_device.diagMode is False

    def test_calledUndefinedDevice(self, tango_device):
        """Test for calledUndefinedDevice"""
        assert tango_device.calledUndefinedDevice is False

    def test_calledDeadServer(self, tango_device):
        """Test for calledDeadServer"""
        assert tango_device.calledDeadServer is False

    def test_detectedDeadServer(self, tango_device):
        """Test for detectedDeadServer"""
        assert tango_device.detectedDeadServer is False

    def test_calledNonRunningDevice(self, tango_device):
        """Test for calledNonRunningDevice"""
        assert tango_device.calledNonRunningDevice is False

    def test_callTimeout(self, tango_device):
        """Test for callTimeout"""
        assert tango_device.callTimeout is False

    def test_callCommFailed(self, tango_device):
        """Test for callCommFailed"""
        assert tango_device.callCommFailed is False

    def test_invalidAsynId(self, tango_device):
        """Test for invalidAsynId"""
        assert tango_device.invalidAsynId is False

    def test_calledInexistentCallback(self, tango_device):
        """Test for calledInexistentCalback"""
        assert tango_device.calledInexistentCallback is False

    def test_requestIdMismatch(self, tango_device):
        """Test for requestIdMismatch"""
        assert tango_device.requestIdMismatch is False

    def test_expectedReplyNotReady(self, tango_device):
        """Test for expectedReplyNotReady"""
        assert tango_device.expectedReplyNotReady is False

    def test_experiencedSubscriptionFailure(self, tango_device):
        """Test for experiencedSubscriptionFailure"""
        assert tango_device.experiencedSubscriptionFailure is False

    def test_invalidEventId(self, tango_device):
        """Test for invalidEventId"""
        assert tango_device.invalidEventId is False

    def test_loggingTargets(self, tango_device):
        """Test for loggingTargets"""
        assert tango_device.loggingTargets == ('tango::logger',)
