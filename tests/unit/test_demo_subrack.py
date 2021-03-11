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
:py:mod:`ska.low.mccs.subrack.demo_subrack_device` module.
"""
import pytest

from ska_tango_base.commands import ResultCode

from ska.low.mccs import MccsDeviceProxy
from ska.low.mccs.subrack.demo_subrack_device import DemoSubrack


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska.low.mccs",
        "device": "subrack_01",
        "patch": DemoSubrack,
        "proxy": MccsDeviceProxy,
    }


class TestDemoSubrack:
    """
    This class contains the tests for the DemoSubrack device class.
    """

    @pytest.fixture()
    def mock_factory(self, mocker):
        """
        Fixture that provides a mock factory for device proxy mocks.
        This factory ensures that calls to a mock's command_inout method
        results in a (ResultCode.OK, message) return.

        :param mocker: a wrapper around the :py:mod:`unittest.mock` package
        :type mocker: obj

        :return: a factory for device proxy mocks
        :rtype: :py:class:`unittest.Mock` (the class itself, not an instance)
        """

        def custom_mock():
            """
            Return a mock that returns `(ResultCode.OK, message)` when
            its `command_inout` method is called.

            :return: a mock that returns `(ResultCode.OK, message)` when
                its `command_inout` method is called.
            :rtype: :py:class:`unittest.Mock`
            """
            mock_device_proxy = mocker.Mock()
            mock_device_proxy.command_inout.return_value = (
                (ResultCode.OK,),
                ("mock message",),
            )
            return mock_device_proxy

        return custom_mock

    def test(self, device_under_test):
        """
        Test:

        * the `isTpm1Powered`, `isTpm2Powered` etc attributes.
        * the `PowerOnTpm1`, `PowerOffTpm2` etc commands.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        def assert_powered(expected):
            """
            Helper function to assert the power mode of each TPM.

            :param expected: the expected power mode of each TPM
            :type expected: list(bool)
            """
            assert [
                device_under_test.read_attribute(f"isTpm{tpm_id}Powered").value
                for tpm_id in range(1, 5)
            ] == expected

        device_under_test.Off()
        device_under_test.On()

        assert_powered([False, False, False, False])

        device_under_test.PowerOnTpm1()
        assert_powered([True, False, False, False])

        device_under_test.PowerOnTpm2()
        assert_powered([True, True, False, False])

        device_under_test.PowerOffTpm1()
        assert_powered([False, True, False, False])

        device_under_test.PowerOnTpm3()
        assert_powered([False, True, True, False])

        device_under_test.PowerOffTpm2()
        assert_powered([False, False, True, False])

        device_under_test.PowerOnTpm4()
        assert_powered([False, False, True, True])

        device_under_test.PowerOffTpm3()
        assert_powered([False, False, False, True])

        device_under_test.PowerOnTpm1()
        assert_powered([True, False, False, True])

        device_under_test.PowerOffTpm4()
        assert_powered([True, False, False, False])
