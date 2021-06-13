# type: ignore
########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for the ska_low_mccs.pool module."""
import pytest
import json
from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.pool import DevicePool

from testing.harness.mock import MockDeviceBuilder
from testing.harness.tango_harness import TangoHarness


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing. In this case we mock all
    devices, so there is no need to stand any up.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return None


class TestDevicePool:
    """
    This class contains the tests for the
    :py:class:`ska_low_mccs.pool.DevicePool` class.
    """

    @pytest.fixture()
    def mock_factory(self, mocker, test_string):
        """
        Fixture that provides a mock factory for device proxy mocks. This factory
        ensures that calls to a mock's command_inout method results in a (ResultCode.OK,
        message) return.

        :param mocker: a wrapper around the :py:mod:`unittest.mock` package
        :type mocker: :py:class:`pytest_mock.mocker`
        :param test_string: a test string that we'll use as a UID
        :type test_string: str

        :return: a factory for device proxy mocks
        :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an instance)
        """
        builder = MockDeviceBuilder()
        builder.add_result_command("Foo", ResultCode.QUEUED, message_uid=test_string)
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
    def device_pool(self, tango_harness: TangoHarness, fqdns, logger):
        """
        Returns the device_pool under test.

        :param tango_harness: a test harness for tango devices
        :param fqdns: FQDNs of the devices in the pool
        :type fqdns: list(str)
        :param logger: the logger to be used by this object.
        :type logger: :py:class:`logging.Logger`

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

    def test_invoke_command_with_callback(
        self, fqdns, device_pool, logger, test_string
    ):
        """
        Test of the
        :py:meth:`ska_low_mccs.pool.DevicePool.invoke_command_with_callback`
        method.

        :param fqdns: FQDNs of the devices in the pool
        :type fqdns: list(str)
        :param device_pool: the device_pool under test
        :type device_pool: :py:class:`ska_low_mccs.pool.DevicePool`
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        :param test_string: a test string that we'll use as a UID
        :type test_string: str
        """
        requestor_fqdn = "test"
        requester_callback = "callback"
        assert device_pool.invoke_command_with_callback(
            "Foo", requestor_fqdn, requester_callback
        )
        assert device_pool._responses.get(test_string) is False
        args = {"respond_to_fqdn": requestor_fqdn, "callback": requester_callback}
        json_string = json.dumps(args)
        for fqdn in fqdns:
            MccsDeviceProxy(fqdn, logger).command_inout.assert_called_once_with(
                "Foo", json_string
            )

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
