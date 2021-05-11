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
:py:mod:`ska_low_mccs.tile.demo_tile_device` module.
"""
import pytest

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, SimulationMode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.tile.demo_tile_device import DemoTile

from testing.harness.mock import MockDeviceBuilder


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
        "device": "tile_0001",
        "patch": DemoTile,
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def initial_mocks(mock_factory, request):
    """
    Fixture that registers device proxy mocks prior to patching. The
    default fixture is overridden here to ensure that a mock subrack
    responds suitably to actions taken on it by the TilePowerManager.

    :param mock_factory: a factory for
        :py:class:`tango.DeviceProxy` mocks
    :type mock_factory: object
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`
    :return: a dictionary of mocks, keyed by FQDN
    :rtype: dict
    """
    kwargs = getattr(request, "param", {})
    is_on = kwargs.get("is_on", False)
    result_code = kwargs.get("result_code", ResultCode.OK)

    mock_subrack_factory = MockDeviceBuilder(mock_factory)
    mock_subrack_factory.add_command("IsTpmOn", is_on)
    mock_subrack_factory.add_result_command("PowerOnTpm", result_code)
    mock_subrack_factory.add_result_command("PowerOffTpm", result_code)

    return {"low-mccs/subrack/01": mock_subrack_factory()}


@pytest.fixture()
def mock_factory(mocker, request):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: :py:class:`pytest_mock.mocker`
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
        instance)
    """
    kwargs = getattr(request, "param", {})
    is_on = kwargs.get("is_on", False)

    builder = MockDeviceBuilder()
    builder.add_attribute("areTpmsOn", [is_on, True, False, True])
    return builder


class TestDemoTile:
    """
    This class contains the tests for the DemoTile device class.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/tile/0001")

    def test_queue_debug(self, device_under_test, test_string):
        """
        Test that the queue debug attribute works correctly.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param test_string: a simple test string fixture
        :type test_string: str
        """
        assert device_under_test.aQueueDebug == "MessageQueueRunning\n"
        device_under_test.aQueueDebug = test_string
        assert device_under_test.aQueueDebug == test_string

    def test_health(self, device_under_test):
        """
        Test that device health changes to failed when we simulate
        connection failure.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.healthState == HealthState.UNKNOWN

        device_under_test.Off()

        assert device_under_test.healthState == HealthState.OK

        device_under_test.SimulateConnectionFailure(True)
        assert device_under_test.healthState == HealthState.FAILED

        device_under_test.SimulateConnectionFailure(False)
        assert device_under_test.healthState == HealthState.OK
