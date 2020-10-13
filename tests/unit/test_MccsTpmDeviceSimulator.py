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

from tango import AttrQuality, DevSource, EventType
from ska.base.control_model import HealthState

from ska.low.mccs.tpm_device_simulator import TpmHardware

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

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
        mock_callback = mocker.Mock()
        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

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
        device_under_test.set_source(DevSource.DEV)

        assert device_under_test.voltage == TpmHardware.VOLTAGE
        device_under_test.simulate = True
        assert device_under_test.voltage != TpmHardware.VOLTAGE

    def test_current(self, device_under_test):
        """
        Test for the current attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)

        device_under_test.current == TpmHardware.CURRENT
        device_under_test.simulate = True
        assert device_under_test.current != TpmHardware.CURRENT

    def test_temperature(self, device_under_test):
        """
        Test for the temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)

        assert device_under_test.temperature == TpmHardware.TEMPERATURE
        device_under_test.simulate = True
        assert device_under_test.temperature != TpmHardware.TEMPERATURE

    def test_fpga1_temperature(self, device_under_test):
        """
        Test for the fpga1_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)

        assert device_under_test.fpga1_temperature == TpmHardware.FPGA1_TEMPERATURE
        device_under_test.simulate = True
        assert device_under_test.fpga1_temperature != TpmHardware.FPGA1_TEMPERATURE

    def test_fpga2_temperature(self, device_under_test):
        """
        Test for the fpga2_temperature attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)

        assert device_under_test.fpga2_temperature == TpmHardware.FPGA2_TEMPERATURE
        device_under_test.simulate = True
        assert device_under_test.fpga2_temperature != TpmHardware.FPGA2_TEMPERATURE
