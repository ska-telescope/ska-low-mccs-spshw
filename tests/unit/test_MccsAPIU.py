###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsStationBeam project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsAPIU.
"""
from tango import DevState

from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.base.commands import ResultCode

device_to_load = {
    "path": "charts/ska-low-mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "apiu",
}


class TestMccsAPIU(object):
    """
    Test class for MccsAPIU tests.
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        print(f"Init state is {device_under_test.state()}")
        assert device_under_test.state() == DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

    def test_attributes(self, device_under_test):
        """
        Test of attributes

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        # Start-up values are zero - N.B. subject to change
        assert device_under_test.temperature == 0.0
        assert device_under_test.humidity == 0.0
        assert device_under_test.voltage == 0.0
        assert device_under_test.current == 0.0
        assert device_under_test.isAlive
        assert device_under_test.overCurrentThreshold == 0.0
        assert device_under_test.overVoltageThreshold == 0.0
        assert device_under_test.humidityThreshold == 0.0

        # print(f'logicalAntennaId -> {repr(device_under_test.logicalAntennaId)}')
        # assert device_under_test.logicalAntennaId == [0]

        device_under_test.overCurrentThreshold = 22.0
        assert device_under_test.overCurrentThreshold == 22.0
        device_under_test.overVoltageThreshold = 6.0
        assert device_under_test.overVoltageThreshold == 6.0
        device_under_test.humidityThreshold = 60.0
        assert device_under_test.humidityThreshold == 60.0

    def test_PowerUp(self, device_under_test):
        """
        Test for PowerUp

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        # assert message == "On command completed OK"

    def test_PowerDown(self, device_under_test):
        """
        Test for PowerDown

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # Need to turn it on before we can turn it off
        device_under_test.PowerUp()
        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        # assert message == "Off command completed OK"

    def test_PowerUpAntenna(self, device_under_test):
        """
        Test for PowerUpAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.PowerUpAntenna(0)
        assert result_code == ResultCode.OK
        # assert message == "On command completed OK"

    def test_PowerDownAntenna(self, device_under_test):
        """
        Test for PowerDownAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        # Need to turn it on before we can turn it off
        device_under_test.PowerUpAntenna(0)
        [[result_code], [message]] = device_under_test.PowerDownAntenna(0)
        assert result_code == ResultCode.OK
        # assert message == "Off command completed OK"
