#########################################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsGroupDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################################
"""Contain the tests for the Grouping of MCCS devices."""

# Path
import sys
import os

path = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.abspath(path))

# Imports
import pytest
from mock import MagicMock

from tango import DevState
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    LoggingLevel,
    SimulationMode,
    TestMode,
)


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
        assert tango_context.device.Status() == "The device is in UNKNOWN state."

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        assert tango_context.device.GetVersionInfo() == [
            "MccsGroupDevice, lmcbaseclasses, 0.5.1, A set of generic base devices for SKA Telescope."
        ]

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() == None

    def test_AddMember(self, tango_context):
        """Test for AddMember"""
        assert tango_context.device.AddMember("") == None

    def test_RemoveMember(self, tango_context):
        """Test for RemoveMember"""
        assert tango_context.device.RemoveMember("") == None

    def test_RunCommand(self, tango_context):
        """Test for RunCommand"""
        assert tango_context.device.RunCommand("") == None

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
