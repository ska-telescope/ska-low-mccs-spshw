###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsSubarray project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""contains the tests for the MccsSubarray"""
import pytest
import tango
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.mccs import release

# pylint: disable=invalid-name
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsSubarray:
    """
    Test cases for MccsSubarray
    """

    properties = {
        # SKASubarray properties
        "CapabilityTypes": [],
        "SubID": "",
        # SKABaseDevice properties
        "SkaLevel": "2",
        "GroupDefinitions": [],
        "LoggingLevelDefault": 4,
        "LoggingTargetsDefault": [],
    }

    def test_properties(self, tango_context):
        """ Test the properties """

    # general methods
    def test_InitDevice(self, tango_context):
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
        assert not tango_context.device.simulationMode
        assert tango_context.device.testMode == TestMode.NONE
        assert tango_context.device.assignedResources is None
        # The following reads might not be allowed in this state once properly
        # implemented
        assert tango_context.device.scanId == -1
        assert tango_context.device.configuredCapabilities is None
        assert tango_context.device.stationFQDNs is None
        assert tango_context.device.tileFQDNs is None
        assert tango_context.device.stationBeamFQDNs is None
        assert tango_context.device.activationTime == 0

    # overridden base class commands
    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(tango_context.class_name)
        assert tango_context.device.GetVersionInfo() == [version_info]

    # MccsSubarray commands
    def test_configureScan(self, tango_context):
        """ Test for configureScan """
        json_spec = "Dummy string"
        status_str = tango_context.device.configureScan(json_spec)
        assert status_str == (
            "Dummy ASCII string returned from "
            "MccsSubarray.configureScan() to indicate status, for "
            "information purposes only"
        )
    def test_sendTransientBuffer(self, tango_context):
        """ Test for sendTransientBuffer """
        segment_spec = []
        status_str = tango_context.device.sendTransientBuffer(segment_spec)
        assert status_str == (
            "Dummy ASCII string returned from "
            "MccsSubarray.sendTransientBuffer() to indicate status, for "
            "information purposes only"
        )

    # overridden base class attributes
    def test_buildState(self, tango_context):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert tango_context.device.buildState == build_info

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == release.version

    # MccsSubarray attributes
    def test_scanId(self, tango_context):
        """Test for scanID attribute"""
        assert tango_context.device.scanId == -1

    def test_stationFQDNs(self, tango_context):
        """Test for stationFQDNs attribute"""
        assert tango_context.device.stationFQDNs is None

    def test_tileFQDNs(self, tango_context):
        """Test for tileFQDNs attribute"""
        assert tango_context.device.tileFQDNs is None

    def test_stationBeamFQDNs(self, tango_context):
        """Test for stationBeamFQDNs attribute"""
        assert tango_context.device.stationBeamFQDNs is None

