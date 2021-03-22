########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska_low_mccs.pool module.
"""
import pytest

from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.pool import DevicePool

from testing.harness.mock import MockDeviceBuilder


class TestDevicePool:
    """
    This class contains the tests for the
    :py:class:`ska_low_mccs.pool.DevicePool` class.
    """

    @pytest.fixture()
    def mock_factory(self, mocker):
        """
        Fixture that provides a mock factory for device proxy mocks.
        This factory ensures that calls to a mock's command_inout method
        results in a (ResultCode.OK, message) return.

        :param mocker: a wrapper around the :py:mod:`unittest.mock` package
        :type mocker: :py:class:`pytest_mock.mocker`

        :return: a factory for device proxy mocks
        :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
        """
        builder = MockDeviceBuilder()
        builder.add_result_command("Foo", ResultCode.OK)
        builder.add_result_command("Disable", ResultCode.OK)
        builder.add_result_command("Off", ResultCode.OK)
        builder.add_result_command("Standby", ResultCode.OK)
        builder.add_result_command("On", ResultCode.OK)
        return builder

    @pytest.fixture()
    def fqdns(self):
        """
        Fixture that returns some FQDNs for testing against.

        :return: some FQDNs
        :rtype: list(str)
        """
        return ["test/test/1", "test/test/2", "test/test/3"]

    @pytest.fixture()
    def device_pool(self, fqdns, logger, mock_device_proxies):
        """
        Returns the device_pool under test.

        :param fqdns: FQDNs of the devices in the pool
        :type fqdns: list(str)
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)

        :return: a device_pool to test
        :rtype: :py:class:`ska_low_mccs.pool.DevicePool`
        """
        return DevicePool(fqdns, logger)

    @pytest.mark.parametrize("arg", ["Bah", None])
    def test_invoke_command(self, fqdns, device_pool, logger, arg):
        """
        Test of the
        :py:meth:`ska_low_mccs.pool.DevicePool.invoke_command`
        method.

        :param fqdns: FQDNs of the devices in the pool
        :type fqdns: list(str)
        :param device_pool: the device_pool under test
        :type device_pool: :py:class:`ska_low_mccs.pool.DevicePool`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        :param arg: a dummy argument to use in testing
        :type arg: str
        """
        if arg is None:
            device_pool.invoke_command("Foo")
        else:
            device_pool.invoke_command("Foo", arg)

        for fqdn in fqdns:
            MccsDeviceProxy(fqdn, logger).command_inout_asynch.assert_called_once_with(
                "Foo", arg
            )
            MccsDeviceProxy(fqdn, logger).command_inout_reply.assert_called_once()

    @pytest.mark.parametrize(
        ("method", "command"),
        [
            ("disable", "Disable"),
            ("off", "Off"),
            ("standby", "Standby"),
            ("on", "On"),
        ],
    )
    def test_commands(self, fqdns, device_pool, logger, method, command):
        """
        Test of command-specific methods.

        :param fqdns: FQDNs of the devices in the pool
        :type fqdns: list(str)
        :param device_pool: the device_pool under test
        :type device_pool: :py:class:`ska_low_mccs.pool.DevicePool`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        :param method: the command-specific method to test
        :type method: str
        :param command: the device command expected to be called on each
            device in the pool
        :type command: str
        """
        getattr(device_pool, method)()

        for fqdn in fqdns:
            MccsDeviceProxy(fqdn, logger).command_inout_asynch.assert_called_once_with(
                command, None
            )
            MccsDeviceProxy(fqdn, logger).command_inout_reply.assert_called_once()
