########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the
:py:mod:`ska_low_mccs.apiu.demo_apiu_device` module.
"""
import pytest

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.apiu.demo_apiu_device import DemoAPIU


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "apiu_001",
        "patch": DemoAPIU,
        "proxy": MccsDeviceProxy,
    }


class TestDemoAPIU:
    """
    This class contains the tests for the DemoAPIU device class.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/apiu/001")

    def test(self, device_under_test, dummy_json_args):
        """
        Test:

        * the `isAntenna1Powered`, `isAntenna2Powered` etc attributes.
        * the `PowerUpAntenna1`, `PowerDownAntenna2` etc commands.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param dummy_json_args: dummy json encoded arguments
        :type dummy_json_args: str
        """

        def assert_powered(expected):
            """
            Helper function to assert the power mode of each TPM.

            :param expected: the expected power mode of each TPM
            :type expected: list(bool)
            """
            assert [
                device_under_test.read_attribute(f"isAntenna{antenna_id}Powered").value
                for antenna_id in range(1, 5)
            ] == expected

        device_under_test.Off()
        device_under_test.On(dummy_json_args)

        assert_powered([False, False, False, False])

        device_under_test.PowerUpAntenna1()
        assert_powered([True, False, False, False])

        device_under_test.PowerUpAntenna2()
        assert_powered([True, True, False, False])

        device_under_test.PowerDownAntenna1()
        assert_powered([False, True, False, False])

        device_under_test.PowerUpAntenna3()
        assert_powered([False, True, True, False])

        device_under_test.PowerDownAntenna2()
        assert_powered([False, False, True, False])

        device_under_test.PowerUpAntenna4()
        assert_powered([False, False, True, True])

        device_under_test.PowerDownAntenna3()
        assert_powered([False, False, False, True])

        device_under_test.PowerUpAntenna1()
        assert_powered([True, False, False, True])

        device_under_test.PowerDownAntenna4()
        assert_powered([True, False, False, False])