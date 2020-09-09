###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsGroupDevice.
"""

from tango import DevState
from ska.base.commands import ResultCode
from ska.base.control_model import HealthState, ControlMode, SimulationMode, TestMode


device_to_load = {
    "path": "charts/mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "groupdevice1",
}


class TestMccsGroupDevice(object):
    """
    Test class for MccsGroupDevice tests.
    """

    def test_InitDevice(self, device_under_test):
        """
           Test for Initial state.
           """
        assert device_under_test.State() == DevState.OFF
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

    def test_AddMember(self, device_under_test):
        """Test for AddMember"""
        [[result_code], [message]] = device_under_test.AddMember("")
        assert result_code == ResultCode.OK
        assert message == "AddMember command succeeded"

    def test_RemoveMember(self, device_under_test):
        """Test for RemoveMember"""
        [[result_code], [message]] = device_under_test.RemoveMember("")
        assert result_code == ResultCode.OK
        assert message == "RemoveMember command succeeded"

    def test_RunCommand(self, device_under_test):
        """Test for RunCommand"""
        [[result_code], [message]] = device_under_test.Run("")
        assert result_code == ResultCode.OK
        assert message == "Run command succeeded"

    def test_memberStates(self, device_under_test):
        """Test for memberStates"""
        assert device_under_test.memberStates == (DevState.UNKNOWN,)

    def test_memberList(self, device_under_test):
        """Test for memberList"""
        assert device_under_test.memberList == ("",)
