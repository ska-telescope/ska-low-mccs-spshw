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
"""Contains the tests for the MccsMaster Tango tango_device prototype."""

import json
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
from ska.mccs.utils import call_with_json


# pylint: disable=invalid-name
class TestMccsMaster:
    """Test case for packet generation."""

    properties = {
        "SkaLevel": "4",
        "CentralLoggingTarget": "",
        "ElementLoggingTarget": "",
        "StorageLoggingTarget": "localhost",
        "GroupDefinitions": "",
        "NrSubarrays": "16",
        "CapabilityTypes": "",
        "MaxCapabilities": "",
        "MccsSubarrays": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
        "MccsStations": "",
    }

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsMaster.numpy = MagicMock()

    def test_properties(self, tango_device):
        """ Test the properties """

    def test_State(self, tango_device):
        """Test for State"""
        assert tango_device.State() == tango.DevState.ON

    def test_Status(self, tango_device):
        """Test for Status"""
        assert tango_device.Status() == "The device is in ON state."

    def test_GetVersionInfo(self, tango_device):
        """Test for GetVersionInfo"""
        vinfo = release.get_release_info(tango_device.info().dev_class)
        assert tango_device.GetVersionInfo() == [vinfo]

    @pytest.mark.skip(reason="have to work out how this works")
    def test_isCapabilityAchievable(self, tango_device):
        """Test for isCapabilityAchievable"""
        assert tango_device.isCapabilityAchievable([[0], [""]]) is not False

    def test_Reset(self, tango_device):
        """Test for Reset"""
        assert tango_device.Reset() is None

    def test_On(self, tango_device):
        """Test for On"""
        with pytest.raises(tango.DevFailed):
            assert tango_device.On()

    def test_Off(self, tango_device):
        """Test for Off"""
        assert tango_device.Off() is None

    def test_StandbyLow(self, tango_device):
        """Test for StandbyLow"""
        assert tango_device.StandbyLow() == 0

    def test_StandbyFull(self, tango_device):
        """Test for StandbyFull"""
        assert tango_device.StandbyFull() == 0

    def test_Operate(self, tango_device):
        """Test for Operate"""
        assert tango_device.Operate() == 0

    def test_Maintenance(self, tango_device):
        """Test for Maintenance"""
        assert tango_device.Maintenance() is None

    def test_EnableSubarray(self, tango_device, mock_device_proxy):
        master = tango_device  # to make test clearer to read
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")

        # These subarrays are mock devices so we have to manually
        # set their initial states
        mock_subarray_1.adminMode = AdminMode.OFFLINE
        mock_subarray_2.adminMode = AdminMode.OFFLINE

        # Tell master to enable subarray 1
        master.EnableSubarray(1)

        # Check that the ONLINE adminMode attribute was written on the
        # mock subarray_1, and that subarray_2 remains OFFLINE
        assert mock_subarray_1.adminMode == AdminMode.ONLINE
        assert mock_subarray_2.adminMode == AdminMode.OFFLINE

        # Telling master to enable an enabled subarray should fail
        with pytest.raises(tango.DevFailed):
            master.EnableSubarray(1)

        # Check no side-effect of failed call
        assert mock_subarray_1.adminMode == AdminMode.ONLINE
        assert mock_subarray_2.adminMode == AdminMode.OFFLINE

        # Tell master to enable subarray 2
        master.EnableSubarray(2)

        # Check that the ONLINE adminMode attribute was written on the
        # mock subarray_2 and that the mock subarray_1 remains
        # unaffected.
        assert mock_subarray_1.adminMode == AdminMode.ONLINE
        assert mock_subarray_2.adminMode == AdminMode.ONLINE

    def test_DisableSubarray(self, tango_device, mock_device_proxy):
        master = tango_device  # to make test clearer to read
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")

        # setup by telling master to enable subarrays 1 and 2
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # check that the ONLINE adminMode attribute was written on both
        # mock subarrays
        assert mock_subarray_1.adminMode == AdminMode.ONLINE
        assert mock_subarray_2.adminMode == AdminMode.ONLINE

        # now tell master to disable subarray 1
        master.DisableSubarray(1)

        # Check that the OFFLINE adminMode attribute was written on the
        # mock subarray_1 and that the mock subarray_2 remains
        # unaffected.
        assert mock_subarray_1.adminMode == AdminMode.OFFLINE
        assert mock_subarray_2.adminMode == AdminMode.ONLINE

        # Disabling a subarray that is already disabled should fail
        with pytest.raises(tango.DevFailed):
            master.DisableSubarray(1)

        # check no side-effect of failed command.
        assert mock_subarray_1.adminMode == AdminMode.OFFLINE
        assert mock_subarray_2.adminMode == AdminMode.ONLINE

    def test_Allocate(self, tango_device, mock_device_proxy):
        """
        Test the Allocate command.
        """
        master = tango_device  # for readability
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")
        mock_station_1 = tango.DeviceProxy("low/elt/station_1")
        mock_station_2 = tango.DeviceProxy("low/elt/station_2")

        # Subarrays and stations are mock devices so we have to manually
        # set any relevant initial state
        mock_station_1.subarrayId = 0
        mock_station_2.subarrayId = 0

        # Can't allocate to an array that hasn't been enabled
        with pytest.raises(tango.DevFailed):
            call_with_json(
                master.Allocate,
                subarray_id=1,
                stations=["low/elt/station_1"],
            )

        # check no side-effect to failure
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

        # now enable subarrays
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # allocate station_1 to subarray_1
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1"],
        )

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
        with pytest.raises(tango.DevFailed):
            call_with_json(
                master.Allocate,
                subarray_id=2,
                stations=["low/elt/station_1"],
            )

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
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )

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

        # allocating station 2 to subarray 1 should succeed, because the
        # it only requires resource release
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_2"],
        )

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

        # now disable subarray 1
        master.DisableSubarray(1)

        # check
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

        # now that subarray 1 has been disabled, its resources should
        # have been released so we should be able to allocate them to
        # subarray 2
        call_with_json(
            master.Allocate,
            subarray_id=2,
            stations=["low/elt/station_1", "low/elt/station_2"],
        )

        # check
        mock_subarray_1.ReleaseResources.assert_not_called()
        mock_subarray_1.AssignResources.assert_not_called()
        mock_subarray_2.ReleaseResources.assert_not_called()
        mock_subarray_2.AssignResources.assert_called_once_with(
            json.dumps({"stations": ["low/elt/station_1", "low/elt/station_2"]})
        )
        assert mock_station_1.subarrayId == 2
        assert mock_station_2.subarrayId == 2

    def test_Release(self, tango_device, mock_device_proxy):
        """
        Test Release command.
        """
        master = tango_device  # for readability
        mock_subarray_1 = tango.DeviceProxy("low/elt/subarray_1")
        mock_subarray_2 = tango.DeviceProxy("low/elt/subarray_2")
        mock_station_1 = tango.DeviceProxy("low/elt/station_1")
        mock_station_2 = tango.DeviceProxy("low/elt/station_2")

        # enable subarrays
        master.EnableSubarray(1)
        master.EnableSubarray(2)

        # allocate stations 1 to subarray 1
        call_with_json(
            master.Allocate,
            subarray_id=1,
            stations=["low/elt/station_1"]
        )

        # allocate station 2 to subarray 2
        call_with_json(
            master.Allocate,
            subarray_id=2,
            stations=["low/elt/station_2"]
        )

        # check initial state
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 2

        # release resources of subarray_2
        master.Release(2)

        # check
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_called_once_with()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # tell mock_subarray_2 that it is an empty subarray that should
        # raise an exception if ReleaseAllResources is called on it.
        mock_subarray_2.ReleaseAllResources.side_effect = \
            lambda: tango.Except.throw_exception(
                "MockException",
                "Command disallowed when obsState==IDLE",
                "Subarray.ReleaseAllResources()",
                tango.ErrSeverity.ERR
            )

        # releasing resources of unresourced subarray_2 should fail
        with pytest.raises(tango.DevFailed):
            master.Release(2)

        # check no side-effect to failed release
        mock_subarray_1.ReleaseAllResources.assert_not_called()
        mock_subarray_2.ReleaseAllResources.assert_called_once_with()
        assert mock_station_1.subarrayId == 1
        assert mock_station_2.subarrayId == 0

        mock_subarray_1.reset_mock()
        mock_subarray_2.reset_mock()

        # release resources of subarray_1
        master.Release(1)

        # check all released
        mock_subarray_1.ReleaseAllResources.assert_called_once_with()
        mock_subarray_2.ReleaseAllResources.assert_not_called()
        assert mock_station_1.subarrayId == 0
        assert mock_station_2.subarrayId == 0

    def test_buildState(self, tango_device):
        """Test for buildState"""
        binfo = ", ".join((release.name, release.version, release.description))
        assert tango_device.buildState == binfo

    def test_versionId(self, tango_device):
        """Test for versionId"""
        assert tango_device.versionId == release.version

    def test_healthState(self, tango_device):
        """Test for healthState"""
        assert tango_device.healthState == HealthState.OK

    def test_adminMode(self, tango_device):
        """Test for adminMode"""
        assert tango_device.adminMode == AdminMode.ONLINE
        tango_device.adminMode = AdminMode.OFFLINE
        assert tango_device.adminMode == AdminMode.OFFLINE

    def test_controlMode(self, tango_device):
        """Test for controlMode"""
        assert tango_device.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, tango_device):
        """Test for simulationMode"""
        assert tango_device.simulationMode == SimulationMode.FALSE

    def test_testMode(self, tango_device):
        """Test for testMode"""
        assert tango_device.testMode == TestMode.NONE

    def test_commandProgress(self, tango_device):
        """Test for commandProgress"""
        assert tango_device.commandProgress == 0

    def test_commandDelayExpected(self, tango_device):
        """Test for commandDelayExpected"""
        assert tango_device.commandDelayExpected == 0

    def test_opState(self, tango_device):
        """Test for opState"""
        assert tango_device.opState == tango.DevState.UNKNOWN

    def test_maxCapabilities(self, tango_device):
        """Test for maxCapabilities"""
        assert tango_device.maxCapabilities is None

    def test_availableCapabilities(self, tango_device):
        """Test for availableCapabilities"""
        assert tango_device.availableCapabilities is None
