###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsGroupDevice project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""Contain the tests for the Grouping of MCCS devices."""

# Imports
import pytest

from tango import DevState


# Device test case
@pytest.mark.usefixtures("tango_device", "initialize_device")
class TestMccsGroupDevice(object):
    """Test case for packet generation."""

    @classmethod
    def mocking(cls):
        """Mock external libraries."""
        # Example : Mock numpy
        # cls.numpy = MccsGroupDevice.numpy = MagicMock()

    def test_AddMember(self, tango_device):
        """Test for AddMember"""
        assert tango_device.AddMember("") is None

    def test_RemoveMember(self, tango_device):
        """Test for RemoveMember"""
        assert tango_device.RemoveMember("") is None

    def test_RunCommand(self, tango_device):
        """Test for RunCommand"""
        assert tango_device.RunCommand("") is None

    def test_memberStates(self, tango_device):
        """Test for memberStates"""
        assert tango_device.memberStates == (DevState.UNKNOWN,)

    def test_memberList(self, tango_device):
        """Test for memberList"""
        assert tango_device.memberList == ("",)
