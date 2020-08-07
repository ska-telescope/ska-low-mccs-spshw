###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contains the tests for the MccsMaster Tango device_under_test prototype."""

import json
import pytest
import tango

from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.low.mccs import MccsMaster, release
from ska.low.mccs.utils import call_with_json, tango_raise
from ska.base.commands import ResultCode

device_info = {
    "class": MccsMaster,
    "properties": {
        "MccsSubarrays": ["low/elt/subarray_1", "low/elt/subarray_2"],
        "MccsStations": ["low/elt/station_1", "low/elt/station_2"],
        "MccsTiles": [
            "low/elt/tile_1",
            "low/elt/tile_2",
            "low/elt/tile_3",
            "low/elt/tile_4",
        ],
    },
}


# pylint: disable=invalid-name
class TestMccsMaster:
    """Test case for packet generation."""

    @pytest.mark.skip(reason="Not implemented")
    def test_properties(self, device_under_test):
        """ Test the properties """

    def test_State(self, device_under_test):
        """Test for State"""
        assert device_under_test.State() == tango.DevState.OFF

    def test_Status(self, device_under_test):
        """Test for Status"""
        assert device_under_test.Status() == "The device is in OFF state."

    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        vinfo = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [vinfo]

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, device_under_test):
        """Test for isCapabilityAchievable"""
        assert device_under_test.isCapabilityAchievable([[0], [""]]) is not False

    @pytest.mark.skip(reason="too weak a test to count")
    def test_Reset(self, device_under_test):
        """Test for Reset"""

        with pytest.raises(Exception):
            device_under_test.Reset()

    def test_On(self, device_under_test):
        """Test for On"""
        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

    def test_Off(self, device_under_test):
        """Test for Off"""
        # Need to turn it on before we can turn it off
        device_under_test.On()
        [[result_code], [message]] = device_under_test.Off()
        assert result_code == ResultCode.OK
        assert message == "Off command completed OK"

    def test_StandbyLow(self, device_under_test):
        """Test for StandbyLow"""
        [[result_code], [message]] = device_under_test.StandbyLow()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyLowCommand(), does nothing"

    def test_StandbyFull(self, device_under_test):
        """Test for StandbyFull"""
        [[result_code], [message]] = device_under_test.StandbyFull()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of StandbyFullCommand(), does nothing"

    def test_Operate(self, device_under_test):
        """Test for Operate"""
        # assert device_under_test.Operate() == 0
        [[result_code], [message]] = device_under_test.Operate()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of OperateCommand(), does nothing"

    def test_Maintenance(self, device_under_test):
        """Test for Maintenance"""
        # assert device_under_test.Maintenance() is None
        [[result_code], [message]] = device_under_test.Maintenance()
        assert result_code == ResultCode.OK
        assert message == "Stub implementation of Maintenance(), does nothing"

    @pytest.mark.mock_device_proxy
    def test_EnableSubarray(self, device_under_test):
        master = device_under_test  # to make test clearer to read
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")

        master.On()

        mock_subarray_1.On.side_effect = ((ResultCode.OK, "Subarray is on."),)
        mock_subarray_2.On.side_effect = ((ResultCode.OK, "Subarray is on."),)

        # Tell master to enable subarray 1
        (result_code, message) = master.EnableSubarray(1)
        assert result_code == ResultCode.OK

        # Check that subarray 1 was turned on, and subarray 2 was not
        mock_subarray_1.On.assert_called_once_with()
        mock_subarray_2.On.assert_not_called()

        mock_subarray_1.reset_mock()
        mock_subarray_1.On.side_effect = ((ResultCode.FAILED, "Subarray already on."),)

        # Telling master to enable an enabled subarray should fail
        (result_code, message) = master.EnableSubarray(1)
        assert result_code == ResultCode.FAILED

        # Check no side-effect of failed call
        mock_subarray_1.On.assert_not_called()
        mock_subarray_2.On.assert_not_called()

        # Tell master to enable subarray 2
        (result_code, message) = master.EnableSubarray(2)
        assert result_code == ResultCode.OK

        # Check that the subarray 2 was turned on and subarray 1 wasn't.
        mock_subarray_1.On.assert_not_called()
        mock_subarray_2.On.assert_called_once_with()

    @pytest.mark.mock_device_proxy
    def test_DisableSubarray(self, device_under_test):
        master = device_under_test  # to make test clearer to read
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")

        master.On()

        mock_subarray_1.On.side_effect = ((ResultCode.OK, "Subarray is on."),)
        mock_subarray_2.On.side_effect = ((ResultCode.OK, "Subarray is on."),)

        # setup by telling master to enable subarrays 1 and 2
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        mock_subarray_1.ReleaseAllResources.side_effect = (
            (ResultCode.FAILED, "No resources to release"),
        )
        mock_subarray_1.Off.side_effect = ((ResultCode.OK, "Subarray is off."),)

        # now tell master to disable subarray 1
        (result_code, message) = master.DisableSubarray(1)
        assert result_code == ResultCode.OK

        # Check that the subarray 1 only was turned off.
        mock_subarray_1.Off.assert_called_once_with()
        mock_subarray_2.Off.assert_not_called()

        mock_subarray_1.reset_mock()

        # Disabling a subarray that is already disabled should fail
        (result_code, message) = master.DisableSubarray(1)
        assert result_code == ResultCode.FAILED

        # check no side-effect of failed command.
        mock_subarray_1.Off.assert_not_called()
        mock_subarray_2.Off.assert_not_called()

    @pytest.mark.mock_device_proxy
    def test_Allocate(self, device_under_test):
        """
        Test the Allocate command.
        """
        master = device_under_test  # for readability
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")
        mock_station_1 = tango.DeviceProxy("low/elt/station_1")
        mock_station_2 = tango.DeviceProxy("low/elt/station_2")

        # Subarrays and stations are mock devices so we have to manually
        # set any relevant initial state
        mock_station_1.subarrayId = 0
        mock_station_2.subarrayId = 0

        master.On()

        # Can't allocate to an array that hasn't been enabled
        (result_code, message) = call_with_json(
            master.Allocate, subarray_id=1, stations=["low/elt/station_1"]
        )
        assert result_code == ResultCode.FAILED

        # check no side-effect to failure
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.On.side_effect = ((ResultCode.OK, "Subarray is on."),)
        mock_subarray_2.On.side_effect = ((ResultCode.OK, "Subarray is on."),)

        # now enable subarrays
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )

        # allocate station_1 to subarray_1
        (result_code, message) = call_with_json(
            master.Allocate, subarray_id=1, stations=["low/elt/station_1"]
        )
        assert result_code == ResultCode.OK

        # check that the mock subarray_1 was told to assign that resource
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low/elt/station_1"]})
        )
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        (result_code, message) = call_with_json(
            master.Allocate, subarray_id=2, stations=["low/elt/station_1"]
        )
        assert result_code == ResultCode.FAILED

        # check no side-effects
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray
        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )

        (result_code, message) = call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low/elt/station_2"]})
        )
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 1

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        mock_subarray_1.ReleaseResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )

        # allocating station 2 to subarray 1 should succeed, because the
        # it only requires resource release
        (result_code, message) = call_with_json(
            master.Allocate, subarray_id=1, stations=["low/elt/station_2"]
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.ReleaseResources.assert_called_once_with(
            json.dumps({"stations": ["low/elt/station_1"]})
        )
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 1

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        mock_subarray_1.ReleaseAllResources.side_effect = (
            (ResultCode.FAILED, "No resources to release"),
        )
        mock_subarray_1.Off.side_effect = ((ResultCode.OK, "Resources assigned"),)

        # now disable subarray 1
        master.DisableSubarray(1)

        # check
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

        # now that subarray 1 has been disabled, its resources should
        # have been released so we should be able to allocate them to
        # subarray 2

        mock_subarray_2.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        (result_code, message) = call_with_json(
            master.Allocate,
            subarray_id=2,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low/elt/station_1", "low/elt/station_2"]})
        )
        assert mock_station_1.subarrayId == 2
        assert mock_station_2.subarrayId == 2

    @pytest.mark.mock_device_proxy
    def test_Release(self, device_under_test):
        """
        Test Release command.
        """
        master = device_under_test  # for readability
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")
        mock_station_1 = tango.DeviceProxy("low/elt/station_1")
        mock_station_2 = tango.DeviceProxy("low/elt/station_2")

        master.On()

        # enable subarrays
        mock_subarray_1.On.side_effect = ((ResultCode.OK, "Subarray is on"),)
        master.EnableSubarray(1)
        mock_subarray_2.On.side_effect = ((ResultCode.OK, "Subarray is on"),)
        master.EnableSubarray(2)

        # allocate stations 1 to subarray 1
        mock_subarray_1.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        call_with_json(master.Allocate, subarray_id=1, stations=["low/elt/station_1"])

        # allocate station 2 to subarray 2
        mock_subarray_2.AssignResources.side_effect = (
            (ResultCode.OK, "Resources assigned"),
        )
        call_with_json(master.Allocate, subarray_id=2, stations=["low/elt/station_2"])

        # check initial state
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 2

        # release resources of subarray_2
        mock_subarray_2.ReleaseAllResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )
        (result_code, message) = master.Release(2)
        assert result_code == ResultCode.OK

        # check
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_called_once_with()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # tell mock_subarray_2 that it is an empty subarray that should
        # raise an exception if ReleaseAllResources is called on it.
        mock_subarray_2.ReleaseAllResources.side_effect = lambda: tango_raise(
            "Command disallowed when obsState==IDLE",
            _origin="Subarray.ReleaseAllResources()",
            reason="MockException",
        )

        # releasing resources of unresourced subarray_2 should fail
        (result_code, message) = master.Release(2)
        assert result_code == ResultCode.FAILED

        # check no side-effect to failed release
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_called_once_with()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # release resources of subarray_1
        mock_subarray_1.ReleaseAllResources.side_effect = (
            (ResultCode.OK, "Resources released"),
        )
        (result_code, message) = master.Release(1)
        assert result_code == ResultCode.OK

        # check all released
        mock_subarray_1.ReleaseAllResources.assert_called_once_with()
        mock_subarray_2.ReleaseAllResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

    def test_buildState(self, device_under_test):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert device_under_test.buildState == binfo

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version

    def test_healthState(self, device_under_test):
        """Test for healthState"""
        assert device_under_test.healthState == HealthState.OK

    def test_controlMode(self, device_under_test):
        """Test for controlMode"""
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """Test for simulationMode"""
        assert device_under_test.simulationMode == SimulationMode.FALSE

    def test_testMode(self, device_under_test):
        """Test for testMode"""
        assert device_under_test.testMode == TestMode.NONE

    def test_commandProgress(self, device_under_test):
        """Test for commandProgress"""
        assert device_under_test.commandProgress == 0

    def test_commandDelayExpected(self, device_under_test):
        """Test for commandDelayExpected"""
        assert device_under_test.commandDelayExpected == 0

    def test_maxCapabilities(self, device_under_test):
        """Test for maxCapabilities"""
        assert device_under_test.maxCapabilities is None

    def test_availableCapabilities(self, device_under_test):
        """Test for availableCapabilities"""
        assert device_under_test.availableCapabilities is None
