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
:py:mod:`ska.low.mccs.hardware.base_hardware` module.
"""

import pytest

from ska.base.control_model import HealthState
from ska.low.mccs.hardware import HardwareManager


class TestBaseHardware:
    """
    Contains tests of the hardware base classes:

    * :py:class:`ska.low.mccs.hardware.HardwareDriver`
    * :py:class:`ska.low.mccs.hardware.HardwareFactory`
    * :py:class:`ska.low.mccs.hardware.HardwareHealthEvaluator`
    * :py:class:`ska.low.mccs.hardware.HardwareManager`
    """

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, hardware_health_evaluator):
        """
        Fixture that returns an
        :py:class:`~ska.low.mccs.hardware.HardwareManager` for
        testing

        :param hardware_factory: the hardware factory used by this
            hardware manager
        :type hardware_factory:
            :py:class:`~ska.low.mccs.hardware.HardwareFactory`
        :param hardware_health_evaluator: the hardware health evaluator
            used by this hardware manager
        :type hardware_health_evaluator:
            :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`

        :return: a hardware manager
        :rtype:
            :py:class:`~ska.low.mccs.hardware.HardwareManager`
        """
        return HardwareManager(hardware_factory, hardware_health_evaluator)

    class TestHardwareHealthEvaluator:
        """
        Contains tests of the
        :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator` class
        """

        @pytest.mark.parametrize(
            ("is_connected", "expected_health"),
            [(True, HealthState.OK), (False, HealthState.FAILED)],
        )
        def test_evaluate(
            self, hardware_health_evaluator, mocker, is_connected, expected_health
        ):
            """
            Test the output of the health evaluation.

            :param hardware_health_evaluator: the hardware health evaluator
                under test
            :type hardware_health_evaluator:
                :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
            :param mocker: fixture that wraps unittest.Mock
            :type mocker: wrapper for :py:mod:`unittest.mock`
            :param is_connected: whether or not this hardware_simulator is
                simulating having a connection to the hardware
            :type is_connected: bool
            :param expected_health: the health that this
                :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
                should report
            :type expected_health:
                :py:class:`~ska.base.control_model.HealthState`
            """
            mock_hardware = mocker.Mock()
            mock_hardware.is_connected = is_connected

            assert (
                hardware_health_evaluator.evaluate_health(mock_hardware)
                == expected_health
            )

    class TestHardwareManager:
        """
        This class contains the tests for the
        :py:class:`~ska.low.mccs.hardware.HardwareManager` class

        (The HardwareManager class is a base class for classes that
        manage hardware on behalf of a device.
        """

        def test_health_reporting(self, hardware_manager, hardware_driver, mocker):
            """
            Test the hardware_manager's health reporting.

            :param hardware_manager: the hardware_manager under test
            :type hardware_manager:
                :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
            :param hardware_driver: the hardware driver (but for testing
                purposes we use a hardware simulator)
            :type hardware_driver:
                :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
            :param mocker: fixture that wraps unittest.Mock
            :type mocker: wrapper for :py:mod:`unittest.mock`
            """
            mock_callback = mocker.Mock()
            another_mock_callback = mocker.Mock()

            assert hardware_manager.health == HealthState.OK

            # Check that health callback gets called on registration
            hardware_manager.register_health_callback(mock_callback)
            mock_callback.assert_called_once_with(HealthState.OK)
            mock_callback.reset_mock()

            # make this hardware fail. Check that health changes and
            # callback is called
            hardware_driver.simulate_connection_failure(True)
            # because this is an external event, the hardware manager
            # won't know about it until it polls
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.FAILED
            mock_callback.assert_called_once_with(HealthState.FAILED)
            mock_callback.reset_mock()

            # Check that we handle multiple callbacks correctly
            hardware_manager.register_health_callback(another_mock_callback)
            mock_callback.assert_not_called()
            another_mock_callback.assert_called_once_with(HealthState.FAILED)
            another_mock_callback.reset_mock()

            hardware_driver.simulate_connection_failure(False)
            # because this is an external event, the hardware manager won't
            # know about it until it polls
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK
            mock_callback.assert_called_once_with(HealthState.OK)
            another_mock_callback.assert_called_once_with(HealthState.OK)
