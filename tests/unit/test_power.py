########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.power module.
"""
import pytest
from tango import DevState

from ska.low.mccs.power import PowerManager


class TestPowerManager:
    """
    This class contains the tests for the
    ska.low.mccs.power.PowerManager class.
    """

    class _OnOffMock:
        """
        Mock class that can be turned off and on.
        """

        def __init__(self):
            """
            Initialise a new _OnOffMock object.
            """
            self._is_on = False

        def On(self):  # noqa: N802
            """
            Turn the mock object on.
            """
            self._is_on = True

        def on(self):
            """
            Turn the mock object on.
            """
            self._is_on = True

        def Off(self):  # noqa: N802
            """
            Turn the mock object off.
            """
            self._is_on = False

        def off(self):
            """
            Turn the mock object off.
            """
            self._is_on = False

        def is_on(self):
            """
            Returns whether this mock object is on or not.

            :return: whether this mock object is on or not
            :rtype: bool
            """
            return self._is_on

        def ping(self):
            """
            Report that I am responsive.

            :return: nominally the time taken; here we just return 0
            :rtype: int
            """
            return 0

        def state(self):
            """
            Report my state.

            :return: OFF
            :rtype: :py:class:`tango.DevState`
            """
            return DevState.OFF

    @pytest.fixture(params=[False, True])
    def hardware_manager(self, request):
        """
        Fixture that returns the hardware manager to be used by the
        power manager under test. This fixture is parametrised to return
        two results: None, and a mock object that can be turned off and
        on. Thus it covers the cases of a power manager for a device
        with or without hardware.

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`

        :return: a mock that can be treated for power management
            purposes as a hardware manager i.e. something that can be
            turned on and off
        :rtype: object, or None
        """
        has_hardware = request.param
        return self._OnOffMock() if has_hardware else None

    @pytest.fixture(params=[None, 0, 2])
    def devices(self, request, mock_device_proxies):
        """
        Fixture that returns a list of devices to be provided to the
        power manager under test as its subservient devices. It is
        paramerised to return three results: None, 0 and 2. Thus it
        covers the cases of a power manager with or without subservient
        devices.

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :param mock_device_proxies: fixture that mocks out tango.DeviceProxy.
        :type mock_device_proxies: dict

        :return: a list of devices that can be turned on and off, or
            None if no devices are provided
        :rtype: list or None
        """
        num_devices = request.param
        if num_devices is None:
            return None

        mock_device_proxies.update(
            {f"mock/mock/{i+1}": self._OnOffMock() for i in range(num_devices)}
        )
        return mock_device_proxies.keys()

    @pytest.fixture()
    def power_manager(self, hardware_manager, devices, logger):
        """
        Fixture that returns a power manager.

        :param hardware_manager: fixture that returns a hardware manager:
            something that can be turned off and on.
        :param devices: fixture that returns a list of devices that are
            subservient to the device under test.
        :param logger: a logger for this power manager to use
        :type logger: an instance of :py:class:`logging.Logger`, or
            an object that implements the same interface

        :return: a power manager instance
        :rtype: :py:class:`ska.low.mccs.power.PowerManager`
        """
        return PowerManager(hardware_manager, devices, logger)

    def test_power_manager(self, power_manager):
        """
        Test the PowerManager class.

        :param power_manager: fixture that returns the power manager
            under test
        :type power_manager: :py:class:`ska.low.mccs.power.PowerManager`
        """

        def assert_on(is_on):
            """
            Helper function that asserts the off/on status of the power
            manager under test.

            :param is_on: the off/on status being asserted. If true, we
                are asserting that the power manager is on; if false, we
                are asserting that it is off
            :type is_on: bool
            """
            assert power_manager.is_on() == is_on
            if power_manager.hardware is not None:
                assert power_manager.hardware.is_on() == is_on
            if power_manager.devices is not None:
                for device in power_manager.devices:
                    assert device.is_on() == is_on

        assert_on(False)

        assert power_manager.on()
        assert_on(True)
        assert power_manager.on() is None
        assert_on(True)

        assert power_manager.off()
        assert_on(False)
        assert power_manager.off() is None
        assert_on(False)
