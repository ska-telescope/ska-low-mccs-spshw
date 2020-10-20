########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA ska-low-mccs project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.hardware module
"""
import pytest

from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.hardware import HardwareSimulator, HardwareManager


@pytest.fixture()
def hardware_simulator():
    """
    Fixture that returns a hardware simulator for testing

    :return: a hardware simulator
    :rtype: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
    """
    return HardwareSimulator()


@pytest.fixture()
def hardware_manager():
    """
    Fixture that returns a hardware manager for testing

    :return: a hardware manager
    :rtype: :py:class:`~ska.low.mccs.hardware.HardwareManager`
    """

    class TestHardwareManager(HardwareManager):
        """
        A :py:class:`~ska.low.mccs.hardware.HardwareManager` subclass
        for testing superclass functionality. This class just implements
        the :py:class:`~ska.low.mccs.hardware.HardwareManager._create_simulator`
        method.

        :param HardwareManager: the superclass
        :type HardwareManager: :py:class:`~ska.low.mccs.hardware.HardwareManager`
        """

        def _create_simulator(self):
            """
            Create and return the simulator to be used by this
            :py:class:`~ska.low.mccs.hardware.HardwareManager`

            :return: the simulator, just created, to be used by this
                :py:class:`~ska.low.mccs.hardware.HardwareManager`
            :rtype: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
            """
            return HardwareSimulator()

    return TestHardwareManager(simulation_mode=SimulationMode.TRUE)


class TestHardwareSimulator:
    """
    This class contains the tests for the HardwareSimulator class.

    (The HardwareSimulator class is a software representation of
    hardware.)
    """

    def test_off_on(self, hardware_simulator):
        """
        Test that this hardware simulator can be turned off and on

        :param hardware_simulator: the hardware simulator under test
        :type hardware_simulator: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
        """
        assert not hardware_simulator.failed
        assert not hardware_simulator.is_on
        hardware_simulator.off()
        assert not hardware_simulator.is_on
        hardware_simulator.on()
        assert hardware_simulator.is_on
        hardware_simulator.on()
        assert hardware_simulator.is_on
        hardware_simulator.off()
        assert not hardware_simulator.is_on

        hardware_simulator.failed = True

        assert hardware_simulator.failed
        hardware_simulator.on()
        assert not hardware_simulator.is_on  # didn't work because hardware has failed


class TestHardwareManager:
    """
    This class contains the tests for the HardwareManager class.

    (The HardwareManager class is a base class for classes that manage
    device hardware (or software simulator of hardware) on behalf of a
    device.)
    """

    def test(self, hardware_manager, mocker):
        """
        Test that

        * the hardware can be turned off and on when not failed
        * when the hardware fails and cannot be turned off and on, the
          hardwareManager reports that failure
        * when the hardware fails, the healthState of the hardware
          manager is updates and any registered callback is called

        :param hardware_manager: the hardware_manager under test
        :type hardware_manager: :py:class:`HardwareManager`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        hardware = hardware_manager._hardware

        mock_callback = mocker.Mock()
        another_mock_callback = mocker.Mock()

        assert hardware_manager.health == HealthState.OK

        # Check that health callback gets called on registration
        hardware_manager.register_health_callback(mock_callback)
        mock_callback.assert_called_once_with(HealthState.OK)
        mock_callback.reset_mock()

        # check turning this healthy hardware off and on
        assert not hardware_manager.is_on
        assert hardware_manager.off() is None  # nothing to do
        assert not hardware_manager.is_on
        assert hardware_manager.on()  # success
        assert hardware_manager.is_on
        assert hardware_manager.on() is None  # nothing to do
        assert hardware_manager.is_on
        assert hardware_manager.off()  # success
        assert not hardware_manager.is_on
        mock_callback.assert_not_called()

        # make this hardware fail. Check that health changes and
        # callback is called
        hardware.failed = True
        hardware_manager.poll_hardware()
        mock_callback.assert_called_once_with(HealthState.FAILED)
        mock_callback.reset_mock()

        # check that when turning hardware on fails, the hardware
        # manager reports failure through its return codes
        assert not hardware_manager.is_on
        assert hardware_manager.off() is None  # nothing to do
        assert not hardware_manager.is_on
        assert not hardware_manager.on()  # failed
        assert not hardware_manager.is_on
        mock_callback.assert_not_called()

        # Check that we handle multiple callbacks correctly
        hardware_manager.register_health_callback(another_mock_callback)
        mock_callback.assert_not_called()
        another_mock_callback.assert_called_once_with(HealthState.FAILED)
        another_mock_callback.reset_mock()

        hardware.failed = False
        hardware_manager.poll_hardware()
        mock_callback.assert_called_once_with(HealthState.OK)
        another_mock_callback.assert_called_once_with(HealthState.OK)
