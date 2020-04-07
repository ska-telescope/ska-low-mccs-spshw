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
from tango import DevSource, DevState
from ska.base.control_model import (AdminMode, ControlMode, HealthState,
                                    ObsState, TestMode)
from ska.mccs import release

# pylint: disable=invalid-name
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsSubarray:
    """
    Test cases for MccsSubarray
    """

    # properties = {
    #     # SKASubarray properties
    #     "CapabilityTypes": [],
    #     "SubID": "",
    #     # SKABaseDevice properties
    #     "SkaLevel": "2",
    #     "GroupDefinitions": [],
    #     "LoggingLevelDefault": 4,
    #     "LoggingTargetsDefault": [],
    # }

    # def test_properties(self, tango_context):
    #     """ Test the properties """

    # tests of general methods
    def test_InitDevice(self, tango_context):
        """
        Test for Initial state.

        Per https://confluence.skatelescope.org/display/SE/Subarray+State+Model,
        a freshly initialised subarray device is DISABLED, offline and idle,
        until TM puts it online, and which time it transitions to OFF until
        assigned resources.
        """
        state = tango_context.device.state()
        admin_mode = tango_context.device.adminMode
        admin_mode_is_disabled = (admin_mode in [AdminMode.OFFLINE,
                                                 AdminMode.NOT_FITTED])
        assert admin_mode_is_disabled == (state == DevState.DISABLE)

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

    # tests of overridden base class commands
    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(tango_context.class_name)
        assert tango_context.device.GetVersionInfo() == [version_info]

    def test_ReleaseAllResources(self, tango_context):
        """Test for ReleaseAllResources"""
        # SETUP
        tango_context.device.adminMode = AdminMode.ONLINE
        tango_context.device.AssignResources("foo")
        assert tango_context.device.state() == DevState.ON

        # TEST
        tango_context.device.ReleaseAllResources()
        assert tango_context.device.state() == DevState.OFF

    def test_Scan(self, tango_context):
        """Test for ReleaseAllResources"""
        # bypass cache for this test because we are testing for a change in the
        # polled attribute obsState
        tango_context.device.set_source(DevSource.DEV)  # bypass cache

        # SETUP
        tango_context.device.adminMode = AdminMode.ONLINE
        tango_context.device.AssignResources("foo")

        # CHECK INITIAL STATE
        assert tango_context.device.state() == DevState.ON
        assert tango_context.device.obsState == ObsState.IDLE

        # TEST
        tango_context.device.Scan([""])
        assert tango_context.device.state() == DevState.ON
        assert tango_context.device.obsState == ObsState.SCANNING

    # tests of MccsSubarray commands
    def test_configureScan(self, tango_context):
        """ Test for configureScan """
        json_spec = "Dummy string"
        before_state = tango_context.device.state()
        status_str = tango_context.device.configureScan(json_spec)
        assert status_str == (
            "Dummy ASCII string returned from "
            "MccsSubarray.configureScan() to indicate status, for "
            "information purposes only"
        )
        assert before_state == tango_context.device.state()

    def test_sendTransientBuffer(self, tango_context):
        """ Test for sendTransientBuffer """
        segment_spec = []
        status_str = tango_context.device.sendTransientBuffer(segment_spec)
        assert status_str == (
            "Dummy ASCII string returned from "
            "MccsSubarray.sendTransientBuffer() to indicate status, for "
            "information purposes only"
        )

    # tests of overridden base class attributes
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

    # General device behaviour tests

    def test_state_machine(self, tango_context):
        """
        Test the subarray state machine.

        This test executes sequences of actions and checks that the required
        state transition occur.

        :todo: add tests for illegal actions
        """

        state_check = {
            "NOTFITTED":
                lambda d: (d.adminMode == AdminMode.NOT_FITTED
                           and d.state() == DevState.DISABLE
                           and d.obsState == ObsState.IDLE),
            "OFFLINE":
                lambda d: (d.adminMode == AdminMode.OFFLINE
                           and d.state() == DevState.DISABLE
                           and d.obsState == ObsState.IDLE),
            "OFF (ONLINE)":
                lambda d: (d.adminMode == AdminMode.ONLINE
                           and d.state() == DevState.OFF
                           and d.obsState == ObsState.IDLE),
            "OFF (MAINTENANCE)":
                lambda d: (d.adminMode == AdminMode.MAINTENANCE
                           and d.state() == DevState.OFF
                           and d.obsState == ObsState.IDLE),
            "READY (ONLINE)":
                lambda d: (d.adminMode == AdminMode.ONLINE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.IDLE),
            "READY (MAINTENANCE)":
                lambda d: (d.adminMode == AdminMode.MAINTENANCE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.IDLE),
            "SCANNING (ONLINE)":
                lambda d: (d.adminMode == AdminMode.ONLINE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.SCANNING),
            "SCANNING (MAINTENANCE)":
                lambda d: (d.adminMode == AdminMode.MAINTENANCE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.SCANNING),
            "ABORTED (ONLINE)":
                lambda d: (d.adminMode == AdminMode.ONLINE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.ABORTED),
            "ABORTED (MAINTENANCE)":
                lambda d: (d.adminMode == AdminMode.MAINTENANCE
                           and d.state() == DevState.ON
                           and d.obsState == ObsState.ABORTED),
        }

        def write_admin(d, mode):
            d.adminMode = mode

        actions = {
            "online": lambda d: write_admin(d, AdminMode.ONLINE),
            "offline": lambda d: write_admin(d, AdminMode.OFFLINE),
            "maintenance": lambda d: write_admin(d, AdminMode.MAINTENANCE),
            "notfitted": lambda d: write_admin(d, AdminMode.NOT_FITTED),
            "assign": lambda d: d.AssignResources("foo"),
            "release": lambda d: d.ReleaseAllResources(),
            "configure": lambda d: d.configureScan("foo"),
            "scan": lambda d: d.Scan(["foo"]),
            "endscan": lambda d: d.EndScan(),
            "abort": lambda d: d.Abort(),
            "reset": lambda d: d.Reset()
        }
        transitions = {
            ("NOTFITTED", "offline"): "OFFLINE",
            ("NOTFITTED", "online"): "OFF (ONLINE)",
            ("NOTFITTED", "maintenance"): "OFF (MAINTENANCE)",
            ("OFFLINE", "online"): "OFF (ONLINE)",
            ("OFFLINE", "maintenance"): "OFF (MAINTENANCE)",
            ("OFFLINE", "notfitted"): "NOTFITTED",
            ("OFF (ONLINE)", "offline"): "OFFLINE",
            ("OFF (ONLINE)", "maintenance"): "OFF (MAINTENANCE)",
            ("OFF (ONLINE)", "notfitted"): "NOTFITTED",
            ("OFF (ONLINE)", "assign"): "READY (ONLINE)",
            ("OFF (MAINTENANCE)", "offline"): "OFFLINE",
            ("OFF (MAINTENANCE)", "online"): "OFF (ONLINE)",
            ("OFF (MAINTENANCE)", "notfitted"): "NOTFITTED",
            ("OFF (MAINTENANCE)", "assign"): "READY (MAINTENANCE)",
            ("READY (ONLINE)", "offline"): "OFFLINE",
            ("READY (ONLINE)", "maintenance"): "READY (MAINTENANCE)",
            ("READY (ONLINE)", "notfitted"): "NOTFITTED",
            ("READY (ONLINE)", "release"): "OFF (ONLINE)",
            ("READY (ONLINE)", "configure"): "READY (ONLINE)",
            ("READY (ONLINE)", "scan"): "SCANNING (ONLINE)",
            ("READY (MAINTENANCE)", "offline"): "OFFLINE",
            ("READY (MAINTENANCE)", "online"): "READY (ONLINE)",
            ("READY (MAINTENANCE)", "notfitted"): "NOTFITTED",
            ("READY (MAINTENANCE)", "release"): "OFF (MAINTENANCE)",
            ("READY (MAINTENANCE)", "configure"): "READY (MAINTENANCE)",
            ("READY (MAINTENANCE)", "scan"): "SCANNING (MAINTENANCE)",
            ("SCANNING (ONLINE)", "offline"): "OFFLINE",
            ("SCANNING (ONLINE)", "maintenance"): "SCANNING (MAINTENANCE)",
            ("SCANNING (ONLINE)", "notfitted"): "NOTFITTED",
            ("SCANNING (ONLINE)", "endscan"): "READY (ONLINE)",
            ("SCANNING (ONLINE)", "configure"): "SCANNING (ONLINE)",
            ("SCANNING (ONLINE)", "abort"): "ABORTED (ONLINE)",
            ("SCANNING (MAINTENANCE)", "offline"): "OFFLINE",
            ("SCANNING (MAINTENANCE)", "online"): "SCANNING (ONLINE)",
            ("SCANNING (MAINTENANCE)", "notfitted"): "NOTFITTED",
            ("SCANNING (MAINTENANCE)", "endscan"): "READY (MAINTENANCE)",
            ("SCANNING (MAINTENANCE)", "configure"): "SCANNING (MAINTENANCE)",
            ("SCANNING (MAINTENANCE)", "abort"): "ABORTED (MAINTENANCE)",
            ("ABORTED (ONLINE)", "offline"): "OFFLINE",
            ("ABORTED (ONLINE)", "maintenance"): "ABORTED (MAINTENANCE)",
            ("ABORTED (ONLINE)", "notfitted"): "NOTFITTED",
            ("ABORTED (ONLINE)", "reset"): "OFF (ONLINE)",
            ("ABORTED (MAINTENANCE)", "offline"): "OFFLINE",
            ("ABORTED (MAINTENANCE)", "online"): "ABORTED (ONLINE)",
            ("ABORTED (MAINTENANCE)", "notfitted"): "NOTFITTED",
            ("ABORTED (MAINTENANCE)", "reset"): "OFF (MAINTENANCE)",
        }

        def perform_action(tango_context, action):
            actions[action](tango_context.device)

        def check_state(tango_context, state):
            assert state_check[state](tango_context.device)

        action_sequence = [
            # Test all transitions between disabled and off states
            "notfitted", "offline", "maintenance", "online", "offline",
            "notfitted", "online", "maintenance", "notfitted", "maintenance",
            "offline", "online",
            # Extend to ready states
            "assign", "maintenance", "release", "assign", "online", "release",
            "assign", "notfitted", "online", "assign", "offline", "maintenance",
            "assign", "notfitted", "maintenance", "assign", "offline", "online",
            # Extend to scanning states
            "assign", "scan", "maintenance", "endscan", "scan", "online",
            "endscan", "scan", "notfitted", "online", "assign", "scan",
            "offline", "maintenance", "assign", "scan", "notfitted",
            "maintenance", "assign", "scan", "offline", "online",
            # Extend to abort states
            "assign", "scan", "abort", "notfitted", "maintenance",
            "assign", "scan", "abort", "notfitted", "online",
            "assign", "scan", "abort", "offline", "maintenance",
            "assign", "scan", "abort", "offline", "online",
            "assign", "scan", "abort", "maintenance", "reset",
            "assign", "scan", "abort", "online", "reset",
        ]

        # bypass cache for this test because we are testing for a change in the
        # polled attribute obsState
        tango_context.device.set_source(DevSource.DEV)  # bypass cache

        # CHECK INITIAL STATE
        state = "OFF (ONLINE)"
        check_state(tango_context, state)

        # TEST ACTION SEQUENCE
        for action in action_sequence:
            perform_action(tango_context, action)
            check_state(tango_context, transitions[(state, action)])
            state = transitions[(state, action)]
