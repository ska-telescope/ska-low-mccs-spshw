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
from contextlib import nullcontext

import pytest

from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.hardware import (
    HardwareSimulator,
    HardwareManager,
    HardwareHealthEvaluator,
    OnOffHardwareSimulator,
    OnOffHardwareManager,
    OnOffHardwareHealthEvaluator,
)


class TestHardwareHealthEvaluator:
    """
    Contains tests of the
    :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator` class
    """

    @pytest.fixture()
    def hardware_health_evaluator(self):
        """
        Return the hardware health evaluator under test

        :return: the hardware health evaluator under test
        :rtype: :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
        """
        return HardwareHealthEvaluator()

    @pytest.mark.parametrize(
        ("is_connected", "expected_health"),
        [(True, HealthState.OK), (False, HealthState.FAILED)],
    )
    def test_evaluate(
        self, hardware_health_evaluator, mocker, is_connected, expected_health
    ):
        """
        Test the output of the health evaluation

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
            hardware_health_evaluator.evaluate_health(mock_hardware) == expected_health
        )


class TestOnOffHardwareHealthEvaluator:
    """
    Contains tests of the
    :py:class:`~ska.low.mccs.hardware.OnOffHardwareHealthEvaluator`
    class
    """

    @pytest.fixture()
    def hardware_health_evaluator(self):
        """
        Return the hardware health evaluator under test

        :return: the hardware health evaluator under test
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareHealthEvaluator`
        """
        return OnOffHardwareHealthEvaluator()

    @pytest.mark.parametrize(
        ("is_connected", "is_on", "expected_health"),
        [
            (False, False, HealthState.FAILED),
            (False, True, HealthState.FAILED),
            (True, False, HealthState.UNKNOWN),
            (True, True, HealthState.OK),
        ],
    )
    def test(
        self, hardware_health_evaluator, mocker, is_connected, is_on, expected_health
    ):
        """
        Test the output of the health evaluation

        :param hardware_health_evaluator: the hardware health evaluator
            under test
        :type hardware_health_evaluator:
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareHealthEvaluator`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param is_connected: whether or not this hardware_simulator is
            simulating having a connection to the hardware
        :type is_connected: bool
        :param is_on: whether or not this hardware_simulator is
            simulating being turned on
        :type is_on: bool
        :param expected_health: the health that this
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareHealthEvaluator`
            should report
        :type expected_health:
            :py:class:`~ska.base.control_model.HealthState`
        """
        mock_hardware = mocker.Mock()
        mock_hardware.is_connected = is_connected
        mock_hardware.is_on = is_on

        assert (
            hardware_health_evaluator.evaluate_health(mock_hardware) == expected_health
        )


class TestHardwareSimulator:
    """
    This class contains the tests for the HardwareSimulator class.

    (The HardwareSimulator class is a software-only representation of a
    hardware driver.
    """

    @pytest.fixture()
    def hardware_simulator(self, request):
        """
        Fixture that returns a hardware simulator for testing

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareSimulator`
        """
        parameter = getattr(request, "param", None)
        if parameter is None:
            return HardwareSimulator()
        return HardwareSimulator(fail_connect=not parameter)

    @pytest.mark.parametrize(
        ("hardware_simulator", "is_connected"),
        [(False, False), (True, True)],
        indirect=("hardware_simulator",),
    )
    def test_init(self, hardware_simulator, is_connected):
        """
        Test initialisation of this hardware simulator

        :param hardware_simulator: the hardware simulator under test
        :type hardware_simulator:
            :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
        :param is_connected: whether or not this hardware_simulator is
            simulating having a connection to the hardware
        :type is_connected: bool
        """
        assert hardware_simulator.is_connected == is_connected


class TestOnOffHardwareSimulator:
    """
    This class contains the tests for the OnOffHardwareSimulator class.

    (The OnOffHardwareSimulator class is a software representation of
    hardware that can be turned on and off.)
    """

    @pytest.fixture()
    def hardware_simulator(self, request):
        """
        Fixture that returns a hardware simulator for testing

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareSimulator`
        """
        parameters = getattr(request, "param", None)
        if parameters is None:
            return OnOffHardwareSimulator()

        return OnOffHardwareSimulator(
            fail_connect=not parameters[0], is_on=parameters[1]
        )

    @pytest.mark.parametrize(
        ("hardware_simulator", "is_connected", "is_on"),
        [
            ((False, False), False, False),
            ((False, True), False, True),
            ((True, False), True, False),
            ((True, True), True, True),
        ],
        indirect=("hardware_simulator",),
    )
    def test_init(self, hardware_simulator, is_connected, is_on):
        """
        Test initialisation of this hardware simulator

        :param hardware_simulator: the hardware simulator under test
        :type hardware_simulator:
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareSimulator`
        :param is_connected: whether or not this hardware_simulator is
            simulating having a connection to the hardware
        :type is_connected: bool
        :param is_on: whether or not this hardware_simulator is
            simulating being turned on
        :type is_on: bool
        """
        contexts = {
            False: pytest.raises(ConnectionError, match="No connection to hardware"),
            True: nullcontext(),
        }

        assert hardware_simulator.is_connected == is_connected
        with contexts[is_connected]:
            assert hardware_simulator.is_on == is_on

    def test_on_off(self, hardware_simulator):
        """
        Test that we can turn a hardware simulator off and on, as long
        as its connection to the hardware hasn't failed.

        :param hardware_simulator: the hardware simulator under
            test
        :type hardware_simulator:
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareSimulator`
        """
        assert hardware_simulator.is_connected
        assert not hardware_simulator.is_on
        hardware_simulator.off()
        assert not hardware_simulator.is_on
        hardware_simulator.on()
        assert hardware_simulator.is_on
        hardware_simulator.on()
        assert hardware_simulator.is_on
        hardware_simulator.off()
        assert not hardware_simulator.is_on

        hardware_simulator.simulate_connection_failure(True)

        assert not hardware_simulator.is_connected
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            hardware_simulator.on()
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            hardware_simulator.off()
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            _ = hardware_simulator.is_on


class TestHardwareManager:
    """
    This class contains the tests for the HardwareManager class.

    (The HardwareManager class is a base class for classes that
    manage, on behalf of a device, hardware (or software simulator of
    hardware).
    """

    @pytest.fixture()
    def hardware_manager(self):
        """
        Fixture that returns an
        :py:class:`~ska.low.mccs.hardware.HardwareManager` for testing

        :return: a hardware manager
        :rtype: :py:class:`~ska.low.mccs.hardware.HardwareManager`
        """

        return HardwareManager(
            simulation_mode=SimulationMode.TRUE,
            health_evaluator=HardwareHealthEvaluator(),
        )

    def test(self, hardware_manager, mocker):
        """
        Test that

        * the hardware can be turned off and on when not failed
        * when the hardware fails and cannot be turned off and on, the
          hardwareManager reports that failure
        * when the hardware fails, the healthState of the hardware
          manager is updates and any registered callback is called

        :param hardware_manager: the hardware_manager under test
        :type hardware_manager:
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
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

        # make this hardware fail. Check that health changes and
        # callback is called
        hardware.simulate_connection_failure(True)
        # because this is an external event, the hardware manager won't
        # know about it until it polls
        hardware_manager.poll()
        assert hardware_manager.health == HealthState.FAILED
        mock_callback.assert_called_once_with(HealthState.FAILED)
        mock_callback.reset_mock()

        # Check that we handle multiple callbacks correctly
        hardware_manager.register_health_callback(another_mock_callback)
        mock_callback.assert_not_called()
        another_mock_callback.assert_called_once_with(HealthState.FAILED)
        another_mock_callback.reset_mock()

        hardware.simulate_connection_failure(False)
        # because this is an external event, the hardware manager won't
        # know about it until it polls
        hardware_manager.poll()
        assert hardware_manager.health == HealthState.OK
        mock_callback.assert_called_once_with(HealthState.OK)
        another_mock_callback.assert_called_once_with(HealthState.OK)


class TestOnOffHardwareManager:
    """
    This class contains the tests for the OnOffHardwareManager class.

    (The OnOffHardwareManager class is a base class for classes that
    manage, on behalf of a device, hardware (or software simulator of
    hardware) that can be turned on and off.
    """

    @pytest.fixture()
    def hardware_manager(self):
        """
        Fixture that returns an
        :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager` for testing

        :return: a hardware manager
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
        """

        return OnOffHardwareManager(
            simulation_mode=SimulationMode.TRUE,
            health_evaluator=OnOffHardwareHealthEvaluator(),
        )

    def test(self, hardware_manager, mocker):
        """
        Test that

        * the hardware can be turned off and on when not failed
        * when the hardware fails and cannot be turned off and on, the
          hardwareManager reports that failure
        * when the hardware fails, the healthState of the hardware
          manager is updates and any registered callback is called

        :param hardware_manager: the hardware_manager under test
        :type hardware_manager:
            :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        hardware = hardware_manager._hardware

        mock_callback = mocker.Mock()
        another_mock_callback = mocker.Mock()

        assert hardware_manager.health == HealthState.UNKNOWN

        # Check that health callback gets called on registration
        hardware_manager.register_health_callback(mock_callback)
        mock_callback.assert_called_once_with(HealthState.UNKNOWN)
        mock_callback.reset_mock()

        # check turning this healthy hardware off and on
        assert not hardware_manager.is_on
        assert hardware_manager.off() is None  # nothing to do
        assert not hardware_manager.is_on

        assert hardware_manager.on()  # success
        assert hardware_manager.is_on

        assert hardware_manager.health == HealthState.OK
        mock_callback.assert_called_once_with(HealthState.OK)
        mock_callback.reset_mock()

        assert hardware_manager.on() is None  # nothing to do
        assert hardware_manager.is_on
        assert hardware_manager.off()  # success
        assert not hardware_manager.is_on

        assert hardware_manager.health == HealthState.UNKNOWN
        mock_callback.assert_called_once_with(HealthState.UNKNOWN)
        mock_callback.reset_mock()

        # make this hardware fail. Check that health changes and
        # callback is called
        hardware.simulate_connection_failure(True)
        # because this is an external event, the hardware manager won't
        # know about it until it polls
        hardware_manager.poll()
        assert hardware_manager.health == HealthState.FAILED
        mock_callback.assert_called_once_with(HealthState.FAILED)
        mock_callback.reset_mock()

        # check that when turning hardware on fails, the hardware
        # manager reports failure through its return codes
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            hardware_manager.on()
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            hardware_manager.off()
        with pytest.raises(ConnectionError, match="No connection to hardware"):
            _ = hardware_manager.is_on

        # Check that we handle multiple callbacks correctly
        hardware_manager.register_health_callback(another_mock_callback)
        mock_callback.assert_not_called()
        another_mock_callback.assert_called_once_with(HealthState.FAILED)
        another_mock_callback.reset_mock()

        hardware.simulate_connection_failure(False)
        # because this is an external event, the hardware manager won't
        # know about it until it polls
        hardware_manager.poll()
        mock_callback.assert_called_once_with(HealthState.UNKNOWN)
        another_mock_callback.assert_called_once_with(HealthState.UNKNOWN)
