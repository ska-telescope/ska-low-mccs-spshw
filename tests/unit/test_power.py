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
from ska.low.mccs.hardware import PowerMode


class TestPowerManager:
    """
    This class contains the tests for the
    ska.low.mccs.power.PowerManager class.
    """

    class _OnStandbyOffMock:
        """
        Mock class that can be put into off, standby and on power modes.
        """

        def __init__(self, power_mode=PowerMode.UNKNOWN):
            """
            Initialise a new instance.

            :param power_mode: the initial power mode of this mock
                object
            :type power_mode: :py:class:`ska.low.mccs.hardware.PowerMode`
            """
            self._power_mode = power_mode

        def On(self):  # noqa: N802
            """
            Turn the mock object on.
            """
            self._power_mode = PowerMode.ON

        def on(self):
            """
            Turn the mock object on.
            """
            self._power_mode = PowerMode.ON

        def Off(self):  # noqa: N802
            """
            Turn the mock object off.
            """
            self._power_mode = PowerMode.OFF

        def off(self):
            """
            Turn the mock object off.
            """
            self._power_mode = PowerMode.OFF

        def Standby(self):  # noqa: N802
            """
            Put the mock object into standby mode.
            """
            self._power_mode = PowerMode.STANDBY

        def standby(self):
            """
            Turn the mock object off.
            """
            self._power_mode = PowerMode.STANDBY

        @property
        def power_mode(self):
            """
            Returns the power mode of this mock object.

            :return: the power mode of this mock object.
            :rtype: :py:class:`ska.low.mccs.hardware.PowerMode`
            """
            return self._power_mode

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
        return (
            self._OnStandbyOffMock(power_mode=PowerMode.OFF) if has_hardware else None
        )

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
            {
                f"mock/mock/{i+1}": self._OnStandbyOffMock(power_mode=PowerMode.OFF)
                for i in range(num_devices)
            }
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

        def assert_power_mode(power_mode):
            """
            Helper function that asserts the power mode of the power
            manager under test.

            :param power_mode: the power mode being asserted.
            :type power_mode: :py:class:`ska.low.mccs.hardware.PowerMode`
            """
            assert power_manager.power_mode == power_mode
            if power_manager.hardware is not None:
                assert power_manager.hardware.power_mode == power_mode
            if power_manager.devices is not None:
                for device in power_manager.devices:
                    assert device.power_mode == power_mode

        assert_power_mode(PowerMode.OFF)

        assert power_manager.on()
        assert_power_mode(PowerMode.ON)
        assert power_manager.on() is None
        assert_power_mode(PowerMode.ON)

        assert power_manager.off()
        assert_power_mode(PowerMode.OFF)
        assert power_manager.off() is None
        assert_power_mode(PowerMode.OFF)
