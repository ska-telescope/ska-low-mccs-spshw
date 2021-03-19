###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsGroupDevice.
"""

import pytest
from tango import DevState

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    HealthState,
    ControlMode,
    SimulationMode,
    TestMode,
)

from ska_low_mccs import MccsDeviceProxy, MccsGroupDevice


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/extra.json",
        "package": "ska_low_mccs",
        "device": "groupdevice",
        "proxy": MccsDeviceProxy,
    }


class TestMccsGroupDevice(object):
    """
    Test class for MccsGroupDevice tests.
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.State() == DevState.OFF
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

    def test_AddMember(self, device_under_test):
        """
        Test for AddMember.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.AddMember("")
        assert result_code == ResultCode.OK
        assert message == MccsGroupDevice.AddMemberCommand.SUCCEEDED_MESSAGE

    def test_RemoveMember(self, device_under_test):
        """
        Test for RemoveMember.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.RemoveMember("")
        assert result_code == ResultCode.OK
        assert message == MccsGroupDevice.RemoveMemberCommand.SUCCEEDED_MESSAGE

    def test_RunCommand(self, device_under_test):
        """
        Test for RunCommand.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.Run("")
        assert result_code == ResultCode.OK
        assert message == MccsGroupDevice.RunCommand.SUCCEEDED_MESSAGE

    def test_memberStates(self, device_under_test):
        """
        Test for memberStates.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.memberStates == (DevState.UNKNOWN,)

    def test_memberList(self, device_under_test):
        """
        Test for memberList.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.memberList == ("",)
