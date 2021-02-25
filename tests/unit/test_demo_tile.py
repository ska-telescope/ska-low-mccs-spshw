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
:py:mod:`ska.low.mccs.tile.demo_tile_device` module.
"""
import pytest

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState, SimulationMode
from ska.low.mccs.tile.demo_tile_device import DemoTile


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
        "device": "tile_0001",
        "patch": DemoTile,
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
    :type request: :py:class:`_pytest.fixtures.SubRequest`
    :return: a dictionary of mocks, keyed by FQDN
    :rtype: dict
    """

    def _subrack_mock(is_on=False, result_code=ResultCode.OK):
        """
        Sets up a mock for a :py:class:`tango.DeviceProxy` that
        connects to an :py:class:`~ska.low.mccs.MccsSubrack`
        device. The returned mock will respond suitably to
        actions taken on it by the TilePowerManager as part of the
        controller's
        :py:meth:`~ska.low.mccs.MccsController.Allocate` and
        :py:meth:`~ska.low.mccs.MccsController.Release`
        commands.

        :param is_on: whether this mock subrack device should report
            that its TPMs are turned on
        :type is_on: bool
        :param result_code: the result code this mock subrack device
            should return when told to turn a TPM on or off
        :type result_code: :py:class:`ska_tango_base.commands.ResultCode`
        :return: a mock for a :py:class:`tango.DeviceProxy` that
            connects to an
            :py:class:`~ska.low.mccs.MccsSubarray` device.
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mock_factory()
        mock.IsTpmOn.return_value = is_on
        mock.PowerOffTpm.return_value = [
            [result_code],
            ["Mock information_only message"],
        ]
        mock.PowerOnTpm.return_value = [
            [result_code],
            ["Mock information_only message"],
        ]
        return mock

    kwargs = getattr(request, "param", {})
    return {"low-mccs/subrack/01": _subrack_mock(**kwargs)}


@pytest.fixture()
def mock_factory(mocker, request):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: wrapper for :py:mod:`unittest.mock`
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`_pytest.fixtures.SubRequest`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an
        instance)
    """
    kwargs = getattr(request, "param", {})
    is_on = kwargs.get("is_on", False)
    _values = {"areTpmsOn": [is_on, True, False, True]}

    def _mock_attribute(name, *args, **kwargs):
        """
        Returns a mock of a :py:class:`tango.DeviceAttribute` instance,
        for a given attribute name.

        :param name: name of the attribute
        :type name: str
        :param args: positional args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type args: list
        :param kwargs: named args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type kwargs: dict

        :return: a basic mock for a :py:class:`tango.DeviceAttribute`
            instance, with name, value and quality values
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.name = name
        mock.value = _values.get(name, "MockValue")
        mock.quality = "MockQuality"
        return mock

    def _mock_device():
        """
        Returns a mock for a :py:class:`tango.DeviceProxy` instance,
        with its :py:meth:`tango.DeviceProxy.read_attribute` method
        mocked to return :py:class:`tango.DeviceAttribute` mocks.

        :return: a basic mock for a :py:class:`tango.DeviceProxy`
            instance,
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.read_attribute.side_effect = _mock_attribute
        return mock

    return _mock_device


class TestDemoTile:
    """
    This class contains the tests for the DemoTile device class.
    """

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
        assert device_under_test.healthState == HealthState.OK

        device_under_test.SimulateConnectionFailure(True)
        assert device_under_test.healthState == HealthState.FAILED

        device_under_test.SimulateConnectionFailure(False)
        assert device_under_test.healthState == HealthState.OK
