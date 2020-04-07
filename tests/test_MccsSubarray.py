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
import time
import pytest
import tango
from ska.base.control_model import (AdminMode, ControlMode, HealthState,
                                    ObsState, TestMode)
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

        Per https://confluence.skatelescope.org/display/SE/Subarray+State+Model,
        a freshly initialised subarray device is DISABLED, offline and idle,
        until TM puts it online, and which time it transitions to OFF until
        assigned resources.
        """
        assert tango_context.device.state() == tango.DevState.DISABLE
        assert tango_context.device.status() == "The device is in DISABLE state."
        assert tango_context.device.adminMode == AdminMode.OFFLINE
        assert tango_context.device.obsState == ObsState.IDLE

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

    def test_adminMode(self, tango_context):
        """
        Test for adminMode. This test executes the following sequence of
        mode transitions, checking after each transition that the subarray is
        in the expected state. Thus all twelve possible mode transitions are
        tested:

        OFFLINE -> ONLINE -> OFFLINE -> MAINTENANCE -> ONLINE -> NOT_FITTED
        -> MAINTENANCE -> OFFLINE -> NOT_FITTED -> ONLINE -> MAINTENANCE
        -> NOT_FITTED -> OFFLINE

        :todo: test taking offline after resources have been allocated
        :todo: test taking offline while scan is configuring
        :todo: test taking offline while scan is ready
        :todo: test taking offline while scannning
        """
        # SETUP
        sleep_seconds = tango_context.device.get_attribute_poll_period(
            "adminMode"
        ) / 1000.0 * 1.2

        checks = {
            AdminMode.OFFLINE: {
                "permitted_states": [tango.DevState.DISABLE],
                "permitted_obs_states": [ObsState.IDLE]
            },
            AdminMode.ONLINE: {
                "permitted_states": [tango.DevState.OFF],
                "permitted_obs_states": [ObsState.IDLE]
            },
            AdminMode.MAINTENANCE: {
                "permitted_states": [tango.DevState.OFF],
                "permitted_obs_states": [ObsState.IDLE]
            },
            AdminMode.NOT_FITTED: {
                "permitted_states": [tango.DevState.DISABLE, tango.DevState.OFF],
                "permitted_obs_states": [ObsState.IDLE]
            }
        }

        def check_state(tango_context, adminMode):
            assert tango_context.device.adminMode == adminMode
            if "permitted_states" in checks[adminMode]:
                state = tango_context.device.state()
                assert state in checks[adminMode]["permitted_states"]
            if "permitted_obs_states" in checks[adminMode]:
                obs_state = tango_context.device.obsState
                assert obs_state in checks[adminMode]["permitted_obs_states"]

        mode_sequence = [AdminMode.ONLINE, AdminMode.OFFLINE,
                         AdminMode.MAINTENANCE, AdminMode.ONLINE,
                         AdminMode.NOT_FITTED, AdminMode.MAINTENANCE,
                         AdminMode.OFFLINE, AdminMode.NOT_FITTED,
                         AdminMode.ONLINE, AdminMode.MAINTENANCE,
                         AdminMode.NOT_FITTED, AdminMode.OFFLINE]

        # CHECK INITIAL CONDITIONS
        check_state(tango_context, AdminMode.OFFLINE)

        # Test
        for mode in mode_sequence:
            tango_context.device.adminMode = mode
            time.sleep(sleep_seconds)
            check_state(tango_context, mode)

    # MccsSubarray attributes

    def test_scanId(self, tango_context):
        """Test for scanID attribute"""
        assert tango_context.device.scanId == -1

    def test_stationFQDNs(self, tango_context):
        """
        Test for stationFQDNs attribute
        """
        assert tango_context.device.stationFQDNs is None

    def test_tileFQDNs(self, tango_context):
        """Test for tileFQDNs attribute"""
        assert tango_context.device.tileFQDNs is None

    def test_stationBeamFQDNs(self, tango_context):
        """Test for stationBeamFQDNs attribute"""
        assert tango_context.device.stationBeamFQDNs is None
