########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""contains the tests for the MccsSubarray"""
import itertools
import pytest
from tango import DevSource, DevState, DevFailed
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    ObsState,
    SimulationMode,
    TestMode,
)
from ska.mccs import release
from ska.mccs.utils import call_with_json


# pylint: disable=invalid-name
class TestMccsSubarray:
    """
    Test cases for MccsSubarray
    """

    # tests of general methods
    def test_InitDevice(self, tango_device):
        """
        Test for Initial state.

        :todo: Test for different memorized values of adminMode.
        """
        assert tango_device.adminMode == AdminMode.OFFLINE
        assert tango_device.state() == DevState.DISABLE

        assert tango_device.obsState == ObsState.IDLE
        assert tango_device.healthState == HealthState.OK
        assert tango_device.controlMode == ControlMode.REMOTE
        assert tango_device.simulationMode == SimulationMode.FALSE
        assert tango_device.testMode == TestMode.NONE
        assert tango_device.assignedResources is None

        # The following reads might not be allowed in this state once
        # properly implemented
        assert tango_device.scanId == -1
        assert list(tango_device.configuredCapabilities) == [
            "BAND1:0",
            "BAND2:0",
        ]
        assert tango_device.stationFQDNs == ()
        #         assert tango_device.tileFQDNs is None
        #         assert tango_device.stationBeamFQDNs is None
        assert tango_device.activationTime == 0

    # tests of overridden base class commands
    def test_GetVersionInfo(self, tango_device):
        """
        Test for GetVersionInfo
        """
        version_info = release.get_release_info(tango_device.info().dev_class)
        assert tango_device.GetVersionInfo() == [version_info]

    def test_AssignResources(self, tango_device):
        """
        Test for AssignResources
        """
        tango_device.set_source(DevSource.DEV)
        tango_device.adminMode = AdminMode.ONLINE

        call_with_json(
            tango_device.AssignResources, stations=["low/elt/station_1"]
        )
        assert list(tango_device.stationFQDNs) == ["low/elt/station_1"]

    # tests of MccsSubarray commands
    def test_sendTransientBuffer(self, tango_device):
        """
        Test for sendTransientBuffer
        """
        segment_spec = []
        returned = tango_device.sendTransientBuffer(segment_spec)
        assert list(returned) == ["OK", "sendTransientBuffer command completed"]

    # tests of overridden base class attributes
    def test_buildState(self, tango_device):
        """
        Test for buildState
        """
        build_info = release.get_release_info()
        assert tango_device.buildState == build_info

    def test_versionId(self, tango_device):
        """
        Test for versionId
        """
        assert tango_device.versionId == release.version

    # tests of MccsSubarray attributes
    def test_scanId(self, tango_device):
        """
        Test for scanID attribute
        """
        assert tango_device.scanId == -1

    def test_stationFQDNs(self, tango_device):
        """
        Test for stationFQDNs attribute
        """
        assert tango_device.stationFQDNs == ()

    # General device behaviour tests

    @pytest.mark.parametrize(
        "state_under_test, action_under_test",
        itertools.product(
            [
                "DISABLED (NOTFITTED)",
                "DISABLED (OFFLINE)",
                "OFF (ONLINE)",
                "OFF (MAINTENANCE)",
                "ON (ONLINE)",
                "ON (MAINTENANCE)",
                "READY (ONLINE)",
                "READY (MAINTENANCE)",
                "SCANNING (ONLINE)",
                "SCANNING (MAINTENANCE)",
                "ABORTED (ONLINE)",
                "ABORTED (MAINTENANCE)",
            ],
            [
                "notfitted",
                "offline",
                "online",
                "maintenance",
                "assign",
                "release",
                "release (all)",
                "releaseall",
                "configure",
                "deconfigure",
                "deconfigure (all)",
                "deconfigureall",
                "deconfigureall (all)",
                "scan",
                "endscan",
                "endsb",
                "abort",
                "reset",
            ],
        ),
    )
    def test_state_machine(self, tango_device,  # mock_device_proxy,
                           state_under_test, action_under_test):
        """
        Test the subarray state machine: for a given initial state and
        an action, does execution of that action, from that initial
        state, yield the expected results? If the action was not allowed
        from that initial state, does the device raise a DevFailed
        exception? If the action was allowed, does it result in the
        correct state transition?

        :todo: Need to refactor to better handle side-effects of
            transitions. At present, we are not testing that we stay in
            the right state when incrementally assigning resources i.e.
            multiple applications of different "assign"-like actions.
        """

        states = {
            "DISABLED (NOTFITTED)": (
                AdminMode.NOT_FITTED,
                DevState.DISABLE,
                ObsState.IDLE,
            ),
            "DISABLED (OFFLINE)": (AdminMode.OFFLINE, DevState.DISABLE, ObsState.IDLE),
            "OFF (ONLINE)": (AdminMode.ONLINE, DevState.OFF, ObsState.IDLE),
            "OFF (MAINTENANCE)": (AdminMode.MAINTENANCE, DevState.OFF, ObsState.IDLE),
            "ON (ONLINE)": (AdminMode.ONLINE, DevState.ON, ObsState.IDLE),
            "ON (MAINTENANCE)": (AdminMode.MAINTENANCE, DevState.ON, ObsState.IDLE),
            "READY (ONLINE)": (AdminMode.ONLINE, DevState.ON, ObsState.READY),
            "READY (MAINTENANCE)": (AdminMode.MAINTENANCE, DevState.ON, ObsState.READY),
            "SCANNING (ONLINE)": (AdminMode.ONLINE, DevState.ON, ObsState.SCANNING),
            "SCANNING (MAINTENANCE)": (
                AdminMode.MAINTENANCE,
                DevState.ON,
                ObsState.SCANNING,
            ),
            "ABORTED (ONLINE)": (AdminMode.ONLINE, DevState.ON, ObsState.ABORTED),
            "ABORTED (MAINTENANCE)": (
                AdminMode.MAINTENANCE,
                DevState.ON,
                ObsState.ABORTED,
            ),
        }

        def assert_state(state):
            assert states[state] == (
                tango_device.adminMode,
                tango_device.state(),
                tango_device.obsState,
            )

        actions = {
            "notfitted": lambda d: d.write_attribute("adminMode", AdminMode.NOT_FITTED),
            "offline": lambda d: d.write_attribute("adminMode", AdminMode.OFFLINE),
            "online": lambda d: d.write_attribute("adminMode", AdminMode.ONLINE),
            "maintenance": lambda d: d.write_attribute(
                "adminMode", AdminMode.MAINTENANCE
            ),
            "assign": lambda d: call_with_json(
                d.AssignResources,
                stations=["low/elt/station_1", "low/elt/station_2"]
            ),
            "release": lambda d: call_with_json(
                d.ReleaseResources, stations=["low/elt/station_1"],
            ),
            "release (all)": lambda d: call_with_json(
                d.ReleaseResources,
                stations=["low/elt/station_1", "low/elt/station_2"]
            ),
            "releaseall": lambda d: d.ReleaseAllResources(),
            "configure": lambda d: d.ConfigureCapability([[2, 2], ["BAND1", "BAND2"]]),
            "deconfigure": lambda d: d.DeconfigureCapability([[1], ["BAND1"]]),
            "deconfigure (all)": lambda d: d.DeconfigureCapability(
                [[2, 2], ["BAND1", "BAND2"]]
            ),
            "deconfigureall": lambda d: d.DeconfigureAllCapabilities("BAND1"),
            "deconfigureall (all)": lambda d: [
                d.DeconfigureAllCapabilities("BAND1"),
                d.DeconfigureAllCapabilities("BAND2"),
            ],
            "scan": lambda d: d.Scan(["Dummy scan id"]),
            "endscan": lambda d: d.EndScan(),
            "endsb": lambda d: d.EndSB(),
            "abort": lambda d: d.Abort(),
            "reset": lambda d: d.Reset(),
        }

        def perform_action(action):
            actions[action](tango_device)

        transitions = {
            ("DISABLED (NOTFITTED)", "notfitted"): "DISABLED (NOTFITTED)",
            ("DISABLED (NOTFITTED)", "offline"): "DISABLED (OFFLINE)",
            ("DISABLED (NOTFITTED)", "online"): "OFF (ONLINE)",
            ("DISABLED (NOTFITTED)", "maintenance"): "OFF (MAINTENANCE)",
            ("DISABLED (OFFLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("DISABLED (OFFLINE)", "offline"): "DISABLED (OFFLINE)",
            ("DISABLED (OFFLINE)", "online"): "OFF (ONLINE)",
            ("DISABLED (OFFLINE)", "maintenance"): "OFF (MAINTENANCE)",
            ("OFF (ONLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("OFF (ONLINE)", "offline"): "DISABLED (OFFLINE)",
            ("OFF (ONLINE)", "online"): "OFF (ONLINE)",
            ("OFF (ONLINE)", "maintenance"): "OFF (MAINTENANCE)",
            ("OFF (ONLINE)", "assign"): "ON (ONLINE)",
            ("OFF (MAINTENANCE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("OFF (MAINTENANCE)", "offline"): "DISABLED (OFFLINE)",
            ("OFF (MAINTENANCE)", "online"): "OFF (ONLINE)",
            ("OFF (MAINTENANCE)", "maintenance"): "OFF (MAINTENANCE)",
            ("OFF (MAINTENANCE)", "assign"): "ON (MAINTENANCE)",
            ("ON (ONLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("ON (ONLINE)", "offline"): "DISABLED (OFFLINE)",
            ("ON (ONLINE)", "online"): "ON (ONLINE)",
            ("ON (ONLINE)", "maintenance"): "ON (MAINTENANCE)",
            # ("ON (ONLINE)", "assign"): "ON (ONLINE)",
            ("ON (ONLINE)", "release"): "ON (ONLINE)",
            ("ON (ONLINE)", "release (all)"): "OFF (ONLINE)",
            ("ON (ONLINE)", "releaseall"): "OFF (ONLINE)",
            ("ON (ONLINE)", "configure"): "READY (ONLINE)",
            ("ON (MAINTENANCE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("ON (MAINTENANCE)", "offline"): "DISABLED (OFFLINE)",
            ("ON (MAINTENANCE)", "online"): "ON (ONLINE)",
            ("ON (MAINTENANCE)", "maintenance"): "ON (MAINTENANCE)",
            # ("ON (MAINTENANCE)", "assign"): "ON (MAINTENANCE)",
            ("ON (MAINTENANCE)", "release"): "ON (MAINTENANCE)",
            ("ON (MAINTENANCE)", "release (all)"): "OFF (MAINTENANCE)",
            ("ON (MAINTENANCE)", "releaseall"): "OFF (MAINTENANCE)",
            ("ON (MAINTENANCE)", "configure"): "READY (MAINTENANCE)",
            ("READY (ONLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("READY (ONLINE)", "offline"): "DISABLED (OFFLINE)",
            ("READY (ONLINE)", "online"): "READY (ONLINE)",
            ("READY (ONLINE)", "maintenance"): "READY (MAINTENANCE)",
            ("READY (ONLINE)", "endsb"): "ON (ONLINE)",
            ("READY (ONLINE)", "reset"): "ON (ONLINE)",
            ("READY (ONLINE)", "configure"): "READY (ONLINE)",
            ("READY (ONLINE)", "deconfigure"): "READY (ONLINE)",
            ("READY (ONLINE)", "deconfigure (all)"): "ON (ONLINE)",
            ("READY (ONLINE)", "deconfigureall"): "READY (ONLINE)",
            ("READY (ONLINE)", "deconfigureall (all)"): "ON (ONLINE)",
            ("READY (ONLINE)", "scan"): "SCANNING (ONLINE)",
            ("READY (ONLINE)", "abort"): "ABORTED (ONLINE)",
            ("READY (MAINTENANCE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("READY (MAINTENANCE)", "offline"): "DISABLED (OFFLINE)",
            ("READY (MAINTENANCE)", "online"): "READY (ONLINE)",
            ("READY (MAINTENANCE)", "maintenance"): "READY (MAINTENANCE)",
            ("READY (MAINTENANCE)", "endsb"): "ON (MAINTENANCE)",
            ("READY (MAINTENANCE)", "reset"): "ON (MAINTENANCE)",
            ("READY (MAINTENANCE)", "configure"): "READY (MAINTENANCE)",
            ("READY (MAINTENANCE)", "deconfigure"): "READY (MAINTENANCE)",
            ("READY (MAINTENANCE)", "deconfigure (all)"): "ON (MAINTENANCE)",
            ("READY (MAINTENANCE)", "deconfigureall"): "READY (MAINTENANCE)",
            ("READY (MAINTENANCE)", "deconfigureall (all)"): "ON (MAINTENANCE)",
            ("READY (MAINTENANCE)", "scan"): "SCANNING (MAINTENANCE)",
            ("READY (MAINTENANCE)", "abort"): "ABORTED (MAINTENANCE)",
            ("SCANNING (ONLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("SCANNING (ONLINE)", "offline"): "DISABLED (OFFLINE)",
            ("SCANNING (ONLINE)", "online"): "SCANNING (ONLINE)",
            ("SCANNING (ONLINE)", "maintenance"): "SCANNING (MAINTENANCE)",
            ("SCANNING (ONLINE)", "endscan"): "READY (ONLINE)",
            ("SCANNING (ONLINE)", "abort"): "ABORTED (ONLINE)",
            ("SCANNING (ONLINE)", "reset"): "ON (ONLINE)",
            ("SCANNING (MAINTENANCE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("SCANNING (MAINTENANCE)", "offline"): "DISABLED (OFFLINE)",
            ("SCANNING (MAINTENANCE)", "online"): "SCANNING (ONLINE)",
            ("SCANNING (MAINTENANCE)", "maintenance"): "SCANNING (MAINTENANCE)",
            ("SCANNING (MAINTENANCE)", "endscan"): "READY (MAINTENANCE)",
            ("SCANNING (MAINTENANCE)", "abort"): "ABORTED (MAINTENANCE)",
            ("SCANNING (MAINTENANCE)", "reset"): "ON (MAINTENANCE)",
            ("ABORTED (ONLINE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("ABORTED (ONLINE)", "offline"): "DISABLED (OFFLINE)",
            ("ABORTED (ONLINE)", "online"): "ABORTED (ONLINE)",
            ("ABORTED (ONLINE)", "maintenance"): "ABORTED (MAINTENANCE)",
            ("ABORTED (ONLINE)", "reset"): "ON (ONLINE)",
            ("ABORTED (MAINTENANCE)", "notfitted"): "DISABLED (NOTFITTED)",
            ("ABORTED (MAINTENANCE)", "offline"): "DISABLED (OFFLINE)",
            ("ABORTED (MAINTENANCE)", "online"): "ABORTED (ONLINE)",
            ("ABORTED (MAINTENANCE)", "maintenance"): "ABORTED (MAINTENANCE)",
            ("ABORTED (MAINTENANCE)", "reset"): "ON (MAINTENANCE)",
        }

        setups = {
            "DISABLED (NOTFITTED)": ["notfitted"],
            "DISABLED (OFFLINE)": ["offline"],
            "OFF (ONLINE)": ["online"],
            "OFF (MAINTENANCE)": ["maintenance"],
            "ON (ONLINE)": ["online", "assign"],
            "ON (MAINTENANCE)": ["maintenance", "assign"],
            "READY (ONLINE)": ["online", "assign", "configure"],
            "READY (MAINTENANCE)": ["maintenance", "assign", "configure"],
            "SCANNING (ONLINE)": ["online", "assign", "configure", "scan"],
            "SCANNING (MAINTENANCE)": ["maintenance", "assign", "configure", "scan"],
            "ABORTED (ONLINE)": ["online", "assign", "configure", "abort"],
            "ABORTED (MAINTENANCE)": ["maintenance", "assign", "configure", "abort"],
        }

        # bypass cache for this test because we are testing for a change
        # in the polled attribute obsState
        tango_device.set_source(DevSource.DEV)

        # Put the device into the state under test
        for action in setups[state_under_test]:
            perform_action(action)

        # Check that we are in the state under test
        assert_state(state_under_test)

        # Test that the action under test does what we expect it to
        if (state_under_test, action_under_test) in transitions:
            # Action should succeed
            perform_action(action_under_test)
            assert_state(transitions[(state_under_test, action_under_test)])
        else:
            # Action should fail
            with pytest.raises(DevFailed):
                perform_action(action_under_test)
