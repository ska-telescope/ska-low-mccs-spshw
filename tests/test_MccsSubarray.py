#########################################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsSubarray project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################################
"""contains the tests for the MccsSubarray"""
import pytest
import tango
from ska.base.control_model import AdminMode, ControlMode, HealthState, SimulationMode, TestMode
from ska.mccs import release

# pylint: disable=invalid-name
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsSubarray:
    """
    Test cases for MccsSubarray
    """

    properties = {
        'SkaLevel': '2',
    }

    def test_properties(self, tango_context):
        """ Test the properties """

    def test_InitialState(self, tango_context):
        """
        Test for Initial state.
        A freshly initialised subarray device has no assigned resources
        and is therefore in OFF state.
        """
        assert tango_context.device.state() == tango.DevState.OFF
        assert tango_context.device.status() == "The device is in OFF state."
        assert tango_context.device.adminMode == AdminMode.ONLINE
        assert tango_context.device.healthState == HealthState.OK
        assert tango_context.device.controlMode == ControlMode.REMOTE
        assert tango_context.device.simulationMode == False
        assert tango_context.device.testMode == TestMode.None

        print(tango_context.device.assignedResources)
        assert False

    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        info = [
            ", ".join(("MccsSubarray", release.name, release.version, release.description))
        ]
        assert tango_context.device.GetVersionInfo() == info

    def test_buildState(self, tango_context):
        """Test for buildState"""
        info = ", ".join((release.name, release.version, release.description))
        assert tango_context.device.buildState == info

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == release.version

    def test_configureScan(self, tango_context):
        """ Test for configureScan """

    def test_sendTransientBuffer(self, tango_context):
        """ Test for sendTransientBuffer """

