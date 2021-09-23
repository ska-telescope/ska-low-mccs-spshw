########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for ska_low_mccs.apiu.demo_apiu_device module."""
from __future__ import annotations

import time

import pytest

from ska_tango_base.control_model import AdminMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.apiu.demo_apiu_device import DemoAPIU

from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_to_load() -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "apiu_001",
        "patch": DemoAPIU,
        "proxy": MccsDeviceProxy,
    }


class TestDemoAPIU:
    """This class contains the tests for the DemoAPIU device class."""

    @pytest.fixture()
    def device_under_test(
        self: TestDemoAPIU,
        tango_harness: TangoHarness,
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/apiu/001")

    def test(
        self: TestDemoAPIU,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test.

        * the `isAntenna1Powered`, `isAntenna2Powered` etc attributes.
        * the `PowerUpAntenna1`, `PowerDownAntenna2` etc commands.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """

        def assert_powered(expected: list[bool]) -> None:
            """
            Assert the power mode of each TPM.

            :param expected: the expected power mode of each TPM
            """
            assert [
                device_under_test.read_attribute(f"isAntenna{antenna_id}Powered").value
                for antenna_id in range(1, 5)
            ] == expected

        device_under_test.adminMode = AdminMode.ONLINE
        device_under_test.On()

        time.sleep(0.1)

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
