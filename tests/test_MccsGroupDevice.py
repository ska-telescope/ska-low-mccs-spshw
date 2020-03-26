###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsGroupDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contain the tests for the Grouping of MCCS devices."""

# Imports
import pytest

from tango import DevState
from ska.mccs import release


# Device test case
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsGroupDevice(object):
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
        # cls.numpy = MccsGroupDevice.numpy = MagicMock()

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

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        info = release.get_release_info("MccsDevice")
        assert tango_context.device.GetVersionInfo() == [info]

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is None

    def test_AddMember(self, tango_context):
        """Test for AddMember"""
        assert tango_context.device.AddMember("") is None

    def test_RemoveMember(self, tango_context):
        """Test for RemoveMember"""
        assert tango_context.device.RemoveMember("") is None

    def test_RunCommand(self, tango_context):
        """Test for RunCommand"""
        assert tango_context.device.RunCommand("") is None

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

    def test_loggingTargets(self, tango_context):
        """Test for loggingTargets"""
        assert tango_context.device.loggingTargets == ()

    def test_memberStates(self, tango_context):
        """Test for memberStates"""
        assert tango_context.device.memberStates == (DevState.UNKNOWN,)

    def test_memberList(self, tango_context):
        """Test for memberList"""
        assert tango_context.device.memberList == ("",)
