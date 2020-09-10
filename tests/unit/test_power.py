########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.power module
"""
import pytest

from ska.low.mccs.power import PowerManager, PowerManagerError


class TestPowerManager:
    """
    This class contains the tests for the ska.low.mccs.power.PowerManager
    class
    """

    class _OnOffMock:
        """
        Mock class that can be turned off and on
        """

        def __init__(self):
            """
            Initialise a new _OnOffMock object
            """
            self._is_on = False

        def On(self):
            """
            Turn the mock object on
            """
            self._is_on = True

        def Off(self):
            """
            Turn the mock object off
            """
            self._is_on = False

        def is_on(self):
            """
            Returns whether this mock object is on or not

            :return: whether this mock object is on or not
            :rtype: boolean
            """
            return self._is_on

    @pytest.fixture(params=[False, True])
    def hardware_manager(self, request):
        """
        Fixture that returns the hardware manager to be used by the
        power manager under test. This fixture is parametrised to return
        two results: None, and a mock object that can be turned off and
        on. Thus it covers the cases of a power manager for a device
        with or without hardware.
        """
        has_hardware = request.param
        return self._OnOffMock() if has_hardware else None

    @pytest.fixture(params=[None, 0, 2])
    def devices(self, request):
        """
        Fixture that returns a list of devices to be provided to the
        power manager under test as its subservient devices. It is
        paramerised to return three results: None, 0 and 2. Thus it
        covers the cases of a power manager with or without subservient
        devices
        """
        num_devices = request.param
        return None if num_devices is None else [self._OnOffMock()] * num_devices

    @pytest.fixture()
    def power_manager(self, hardware_manager, devices):
        """
        Fixture that returns a power manager

        :param hardware_manager: fixture that returns a hardware manager:
            something that can be turned off and on.
        :param devices: fixture that returns a list of devices that are
            subservient to the device under test.
        """
        return PowerManager(hardware_manager, devices)

    def test_power_manager(self, power_manager):
        """
        Test the PowerManager class

        :param power_manager: fixture that returns the power manager under
            test
        """

        def assert_on(is_on):
            """
            Helper function that asserts the off/on status of the power
            manager under test

            :param is_on: the off/on status being asserted. If true, we
                are asserting that the power manager is on; if false, we
                are asserting that it is off
            :ptype is_on: boolean
            """
            assert power_manager.is_on() == is_on
            if power_manager.hardware is not None:
                assert power_manager.hardware.is_on() == is_on
            if power_manager.devices is not None:
                for device in power_manager.devices:
                    assert device.is_on() == is_on

        assert_on(False)

        with pytest.raises(PowerManagerError):
            power_manager.off()
        assert_on(False)

        assert power_manager.on()
        assert_on(True)

        with pytest.raises(PowerManagerError):
            power_manager.on()
        assert_on(True)

        assert power_manager.off()
        assert_on(False)
