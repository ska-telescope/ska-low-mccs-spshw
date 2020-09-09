#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTile project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsTpmDeviceSimulator.
"""

from ska.low.mccs import MccsTpmDeviceSimulator

device_info = {"class": MccsTpmDeviceSimulator, "properties": {}}


class TestMccsTpmDeviceSimulator(object):
    """
    Test class for MccsTpmDeviceSimulator tests.

    The TpmDeviceSimulator device simulates te H/W TPM unit allowing changes
    to the values of key attributes.
    """

    def test_simulate(self, device_under_test):
        """Test for the simulate attribute."""
        assert device_under_test.simulate is False
        device_under_test.simulate = True
        assert device_under_test.simulate is True

    def test_voltage(self, device_under_test):
        """Test for the voltage attribute."""
        assert device_under_test.voltage == 4.7
        device_under_test.voltage = 4.6
        assert device_under_test.voltage == 4.6
        device_under_test.simulate = True
        assert device_under_test.voltage != 4.6

    def test_current(self, device_under_test):
        """Test for the current attribute."""
        device_under_test.current == 0.4
        device_under_test.current = 0.2
        assert device_under_test.current == 0.2
        device_under_test.simulate = True
        assert device_under_test.current != 0.2

    def test_temperature(self, device_under_test):
        """Test for the board_temperature attribute."""
        assert device_under_test.temperature == 36.0
        device_under_test.temperature = 37.0
        assert device_under_test.temperature == 37.0
        device_under_test.simulate = True
        assert device_under_test.temperature != 37.0

    def test_fpga1_temperature(self, device_under_test):
        """Test for the fpga1_temperature attribute."""
        assert device_under_test.fpga1_temperature == 38.0
        device_under_test.fpga1_temperature = 39.0
        assert device_under_test.fpga1_temperature == 39.0
        device_under_test.simulate = True
        assert device_under_test.fpga1_temperature != 39.0

    def test_fpga2_temperature(self, device_under_test):
        """Test for the fpga2_temperature attribute."""
        assert device_under_test.fpga2_temperature == 37.5
        device_under_test.fpga2_temperature = 40.0
        assert device_under_test.fpga2_temperature == 40.0
        device_under_test.simulate = True
        assert device_under_test.fpga2_temperature != 40.0
