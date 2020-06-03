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
from ska.low.mccs import MccsGroupDevice


device_info = {
    "class": MccsGroupDevice,
    "properties": {}
}


class TestMccsGroupDevice(object):
    """
    Test class for MccsGroupDevice tests.
    """

    def test_AddMember(self, device_under_test):
        """Test for AddMember"""
        assert device_under_test.AddMember("") is None

    def test_RemoveMember(self, device_under_test):
        """Test for RemoveMember"""
        assert device_under_test.RemoveMember("") is None

    def test_RunCommand(self, device_under_test):
        """Test for RunCommand"""
        assert device_under_test.RunCommand("") is None

    def test_memberStates(self, device_under_test):
        """Test for memberStates"""
        assert device_under_test.memberStates == (DevState.UNKNOWN,)

    def test_memberList(self, device_under_test):
        """Test for memberList"""
        assert device_under_test.memberList == ("",)
