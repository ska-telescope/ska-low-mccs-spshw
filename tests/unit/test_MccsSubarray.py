########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for MccsSubarray.
"""
import pytest
import tango
from tango import DevSource
from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.base.commands import ResultCode
from ska.low.mccs import release
from ska.low.mccs.utils import call_with_json


device_to_load = {
    "path": "charts/mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "subarray_01",
}


# pylint: disable=invalid-name
class TestMccsSubarray:
    """
    Test class for MccsSubarray tests
    """

    # tests of general methods
    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :todo: Test for different memorized values of adminMode.
        """
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE
        assert device_under_test.assignedResources is None

        # The following reads might not be allowed in this state once
        # properly implemented
        assert device_under_test.scanId == -1
        assert list(device_under_test.configuredCapabilities) == ["BAND1:0", "BAND2:0"]
        assert device_under_test.stationFQDNs is None
        #         assert device_under_test.tileFQDNs is None
        #         assert device_under_test.stationBeamFQDNs is None
        assert device_under_test.activationTime == 0

    # tests of overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo
        """
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    @pytest.mark.mock_device_proxy
    def test_AssignResources(self, device_under_test):
        """
        Test for AssignResources
        """
        device_under_test.set_source(DevSource.DEV)

        station_fqdn = "low-mccs/station/001"
        mock_station = tango.DeviceProxy(station_fqdn)

        device_under_test.On()
        [[result_code], [message]] = call_with_json(
            device_under_test.AssignResources, stations=[station_fqdn]
        )
        assert result_code == ResultCode.OK
        assert message == "AssignResources command completed successfully"
        assert list(device_under_test.stationFQDNs) == [station_fqdn]

        mock_station.Configure.assert_called_once_with()

    # tests of MccsSubarray commands
    def test_sendTransientBuffer(self, device_under_test):
        """
        Test for sendTransientBuffer
        """
        segment_spec = []
        returned = device_under_test.sendTransientBuffer(segment_spec)
        assert returned == [
            [ResultCode.OK],
            ["SendTransientBuffer command completed successfully"],
        ]

    # tests of overridden base class attributes
    def test_buildState(self, device_under_test):
        """
        Test for buildState
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    def test_versionId(self, device_under_test):
        """
        Test for versionId
        """
        assert device_under_test.versionId == release.version

    # tests of MccsSubarray attributes
    def test_scanId(self, device_under_test):
        """
        Test for scanID attribute
        """
        assert device_under_test.scanId == -1

    def test_stationFQDNs(self, device_under_test):
        """
        Test for stationFQDNs attribute
        """
        assert device_under_test.stationFQDNs is None
