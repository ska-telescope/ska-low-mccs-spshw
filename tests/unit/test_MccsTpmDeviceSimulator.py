#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsTpmDeviceSimulator.
"""

device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "tpmsimulator",
}


class TestMccsTpmDeviceSimulator(object):
    """
    Test class for MccsTpmDeviceSimulator tests.

    The TpmDeviceSimulator device simulates te H/W TPM unit allowing changes
    to the values of key attributes.
    """

    def test_simulate(self, device_under_test):
        """
        Test for the simulate attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulate is False
        device_under_test.simulate = True
        assert device_under_test.simulate is True

    def test_voltage(self, device_under_test):
        """
        Test for the voltage attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.voltage == 4.7
        device_under_test.voltage = 4.6
        assert device_under_test.voltage == 4.6
        device_under_test.simulate = True
        assert device_under_test.voltage != 4.6

    def test_current(self, device_under_test):
        """
        Test for the current attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.current == 0.4
        device_under_test.current = 0.2
        assert device_under_test.current == 0.2
        device_under_test.simulate = True
        assert device_under_test.current != 0.2

    def test_temperature(self, device_under_test):
        """
        Test for the board_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.temperature == 36.0
        device_under_test.temperature = 37.0
        assert device_under_test.temperature == 37.0
        device_under_test.simulate = True
        assert device_under_test.temperature != 37.0

    def test_fpga1_temperature(self, device_under_test):
        """
        Test for the fpga1_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fpga1_temperature == 38.0
        device_under_test.fpga1_temperature = 39.0
        assert device_under_test.fpga1_temperature == 39.0
        device_under_test.simulate = True
        assert device_under_test.fpga1_temperature != 39.0

    def test_fpga2_temperature(self, device_under_test):
        """
        Test for the fpga2_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fpga2_temperature == 37.5
        device_under_test.fpga2_temperature = 40.0
        assert device_under_test.fpga2_temperature == 40.0
        device_under_test.simulate = True
        assert device_under_test.fpga2_temperature != 40.0
