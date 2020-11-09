########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
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
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareManager,
    HardwareSimulator,
    OnOffHardwareManager,
    OnOffHardwareSimulator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)


@pytest.fixture()
def hardware_health_evaluator():
    """
    Return the hardware health evaluator under test

    :return: the hardware health evaluator under test
    :rtype: :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`
    """
    return HardwareHealthEvaluator()


@pytest.fixture()
def hardware_driver():
    """
    Return the hardware driver under test.

    Returns a HardwareSimulator, because we need to return a basic
    mock driver, and the HardwareSimulator is just that.

    :return: the hardware driver under test
    :rtype: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
    """
    return HardwareSimulator()


@pytest.fixture()
def hardware_factory(hardware_driver):
    """
    Fixture that provides a basic hardware factory that always returns
    a pre-defined hardware driver

    :param hardware_driver: the hardware driver for this factory to
        return
    :type hardware_driver:
        :py:class:`~ska.low.mccs.hardware.HardwareDriver`

    :return: a hardware factory that always returns the pre-defined
        hardware driver
    :rtype: :py:class:`~ska.low.mccs.hardware.HardwareFactory`
    """

    class BasicHardwareFactory(HardwareFactory):
        """
        A basic hardware factory that always returns the same hardware
        """

        def __init__(self, hardware):
            """
            Create a new instance

            :param hardware: the hardware that this factory will always
                return
            :type hardware:
                :py:class:`~ska.low.mccs.hardware.HardwareDriver`
            """
            self._hardware = hardware

        @property
        def hardware(self):
            """
            Return this factory's hardware

            :return: this factory's hardware
            :rtype:
                :py:class:`~ska.low.mccs.hardware.HardwareDriver`
            """
            return self._hardware

    return BasicHardwareFactory(hardware_driver)


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


class TestSimulableHardware:
    """
    Contains tests of the hardware classes that support simulation:
    * :py:class:`ska.low.mccs.hardware.HardwareSimulator`
    * :py:class:`ska.low.mccs.hardware.SimulableHardwareFactory`
    * :py:class:`ska.low.mccs.hardware.SimulableHardwareManager`
    """

    @pytest.fixture()
    def hardware_simulator(self, request):
        """
        Fixture that returns a hardware simulator for testing

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
        """
        parameter = getattr(request, "param", None)
        if parameter is None:
            return HardwareSimulator()
        return HardwareSimulator(fail_connect=not parameter)

    @pytest.fixture()
    def hardware_factory(self, request, hardware_driver, hardware_simulator):
        """
        Fixture that returns a hardware factory for simulable hardware

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :param hardware_driver: the hardware driver to be returned by
            by this hardware factory when not in simulation mode
        :type hardware_driver:
            :py:class:`~ska.low.mccs.hardware.HardwareDriver`
        :param hardware_simulator: the hardware simulator to be returned
            by this hardware factory when in simulation mode
        :type hardware_simulator:
            :py:class:`~ska.low.mccs.hardware.HardwareSimulator`

        :return: a hardware factory for simulable hardware
        :rtype:
            :py:class:`~ska.low.mccs.hardware.SimulableHardwareFactory`
        """
        return SimulableHardwareFactory(True, hardware_driver, hardware_simulator)

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, hardware_health_evaluator):
        """
        Fixture that returns a
        :py:class:`~ska.low.mccs.hardware.SimulableHardwareManager` for
        testing

        :param hardware_factory: the hardware factory used by this
            hardware manager
        :type hardware_factory:
            :py:class:`~ska.low.mccs.hardware.SimulableHardwareFactory`
        :param hardware_health_evaluator: the hardware health evaluator
            used by this hardware manager
        :type hardware_health_evaluator:
            :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator`

        :return: a simulable hardware manager
        :rtype:
            :py:class:`~ska.low.mccs.hardware.SimulableHardwareManager`
        """
        return SimulableHardwareManager(hardware_factory, hardware_health_evaluator)

    class TestHardwareSimulator:
        """
        This class contains the tests for the HardwareSimulator class.

        (The HardwareSimulator class is a software-only representation of a
        hardware driver.
        """

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

        def test_simulate_connection_failure(self, hardware_simulator):
            """
            Test that simulating connection failure causes the hardware
            simulator to think its connection has been lost

            :param hardware_simulator: the hardware simulator under test
            :type hardware_simulator:
                :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
            """
            assert hardware_simulator.is_connected
            hardware_simulator.simulate_connection_failure(True)
            assert not hardware_simulator.is_connected
            hardware_simulator.simulate_connection_failure(False)
            assert hardware_simulator.is_connected

    class TestSimulableHardwareFactory:
        """
        This class contains tests of the
        :py:class:`~ska.low.mccs.hardware.SimulableHardwareFactory`
        class.
        """

        def test_simulation_mode(
            self, hardware_driver, hardware_simulator, hardware_factory
        ):
            """
            Test that different hardware is returned depending on
            simulation mode

            :param hardware_driver: the hardware driver that the
                hardware factory returns when not in simulation mode
            :type hardware_driver:
                :py:class:`ska.low.mccs.hardware.HardwareDriver`
            :param hardware_simulator: the hardware simulator that the
                hardware factory returns when in simulation mode
            :type hardware_simulator:
                :py:class:`ska.low.mccs.hardware.HardwareSimulator`
            :param hardware_factory: a hardware factory that returns a
                driver or simulator depending on its simulation mode
            :type hardware_factory:
                :py:class:`ska.low.mccs.hardware.SimulableHardwareFactory`
            """
            # check precondition - the test doesn't make sense unless
            # these are unequal
            assert hardware_driver != hardware_simulator

            assert hardware_factory.simulation_mode
            assert hardware_factory.hardware == hardware_simulator

            hardware_factory.simulation_mode = False
            assert not hardware_factory.simulation_mode
            assert hardware_factory.hardware == hardware_driver

            hardware_factory.simulation_mode = True
            assert hardware_factory.simulation_mode
            assert hardware_factory.hardware == hardware_simulator

    class TestSimulableHardwareManager:
        """
        This class contains the tests for the SimulableHardwareManager
        class.

        (The SimulableHardwareManager class is a base class for classes
        that manage hardware, on behalf of a device, in circumstances
        where a simulator may be substituted for the hardware.
        """

        def test_simulation_mode(
            self, hardware_driver, hardware_simulator, hardware_manager
        ):
            """
            Test that changing simulation mode, where the simulator is
            simulating connection failure, causes changes in health

            :param hardware_driver: the hardware driver (simulated for
                testing purposes)
            :type hardware_driver:
                :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
            :param hardware_simulator: the hardware simulator
            :type hardware_simulator:
                :py:class:`~ska.low.mccs.hardware.HardwareSimulator`
            :param hardware_manager: the hardware manager under test
            :type hardware_manager:
                :py:class:`~ska.low.mccs.hardware.SimulableHardwareManager`
            """
            assert hardware_manager.simulation_mode
            assert hardware_manager.health == HealthState.OK

            hardware_simulator.simulate_connection_failure(True)
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.FAILED

            hardware_manager.simulation_mode = SimulationMode.FALSE
            assert hardware_manager.health == HealthState.OK

            hardware_manager.simulation_mode = SimulationMode.TRUE
            assert hardware_manager.health == HealthState.FAILED


class TestOnOffHardware:
    """
    Contains tests of the hardware classes that support `off` and `on`
    modes:
    * :py:class:`ska.low.mccs.hardware.OnOffHardwareSimulator`
    * :py:class:`ska.low.mccs.hardware.OnOffHardwareManager`
    """

    @pytest.fixture()
    def hardware_driver(self, request):
        """
        Fixture that returns a hardware driver (actually a simulator for
        testing purposes)

        :param request: A pytest object giving access to the requesting test
            context.
        :type request: :py:class:`_pytest.fixtures.SubRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareSimulator`
        """
        return OnOffHardwareSimulator()

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

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, hardware_health_evaluator):
        """
        Fixture that returns an
        :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager` for testing

        :param hardware_factory: the hardware driver factory used by
            this hardware manager
        :type hardware_factory: :py:class:`HardwareFactory`
        :param hardware_health_evaluator: the hardware health evaluator
            used by this hardware manager
        :type hardware_health_evaluator:
            :py:class:`HardwareHealthEvaluator`

        :return: a hardware manager
        :rtype: :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
        """

        return OnOffHardwareManager(hardware_factory, hardware_health_evaluator)

    class TestOnOffHardwareSimulator:
        """
        This class contains the tests for the OnOffHardwareSimulator class.

        (The OnOffHardwareSimulator class is a software representation of
        hardware that can be turned on and off.)
        """

        @pytest.mark.parametrize(
            ("hardware_simulator", "is_connected", "is_on"),
            [
                # We pass the test a hardware simulator that has been
                # initialised with the first element of this triple, and
                # test that its connection status is that of the second
                # element, and its power mode is that of the third.
                #
                # For example, "((True, False), True, False)" means:
                # * take a hardware simulator that has been initialised
                #   as connected but not turned on;
                # * test that it behaves as though connected, but not
                #   turned on
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
                False: pytest.raises(
                    ConnectionError, match="No connection to hardware"
                ),
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

    class TestOnOffHardwareManager:
        """
        This class contains the tests for the OnOffHardwareManager class.

        (The OnOffHardwareManager class is a base class for classes that
        manage, on behalf of a device, hardware (or software simulator of
        hardware) that can be turned on and off.
        """

        def test(self, hardware_driver, hardware_manager):
            """
            Test that

            * the hardware can be turned off and on when not failed
            * when the hardware fails and cannot be turned off and on, the
              hardwareManager reports that failure

            :param hardware_driver: the hardware driver
            :type hardware_driver:
                :py:class:`~ska.low.mccs.hardware.HardwareDriver`
            :param hardware_manager: the hardware_manager under test
            :type hardware_manager:
                :py:class:`~ska.low.mccs.hardware.OnOffHardwareManager`
            """
            assert hardware_manager.health == HealthState.OK

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

            # make this hardware fail. Check that health changes and
            # callback is called
            hardware_driver.simulate_connection_failure(True)
            # because this is an external event, the hardware manager won't
            # know about it until it polls
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.FAILED

            # check that when turning hardware on fails, the hardware
            # manager reports failure through its return codes
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                hardware_manager.on()
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                hardware_manager.off()
            with pytest.raises(ConnectionError, match="No connection to hardware"):
                _ = hardware_manager.is_on

            hardware_driver.simulate_connection_failure(False)
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK
            assert not hardware_manager.is_on
