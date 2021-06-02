# type: ignore
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
:py:mod:`ska_low_mccs.hardware.simulable_hardware` module.
"""
from random import seed

import pytest

from ska_tango_base.control_model import HealthState, SimulationMode
from ska_low_mccs.hardware import (
    ConnectionStatus,
    HardwareSimulator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)
from ska_low_mccs.hardware.simulable_hardware import DynamicValuesGenerator


@pytest.fixture()
def zero_seed():
    """Sets the random seed to zero, so that we get some determinism in our stochastic
    tests."""
    seed(0)


class TestDynamicValuesGenerator:
    """Contains tests of the dynamic values generator."""

    def test_collapse(self):
        """
        Test that we get the fixed value we expect with in_range_rate set to 1.

        (If you set the in_range_rate to 1, the model variance collapses
        to zero, and all your values end up being the mean of soft_min
        and soft_max, regardless of window size. This isn't a good thing
        but it is useful for testing.)
        """
        generator = DynamicValuesGenerator(
            soft_min=30,
            soft_max=40,
            window_size=10,
            in_range_rate=1.0,
        )
        assert next(generator) == 35.0

    def test_rate(self, zero_seed):
        """
        Test that the attained rate is reasonably close to the set rate.

        :param zero_seed: fixture that sets the random seed to 0 so that
            we get the same random values each time. This is necessary
            because we are testing a stochastic process, which won't
            pass for all possible sets of values. Therefore we "freeze"
            the values that we pass in, so that we can guarantee that it
            won't fail for purely random reasons.
        :type zero_seed: None
        """
        soft_min, soft_max = 30, 40
        generator = DynamicValuesGenerator(
            soft_min=30,
            soft_max=40,
            window_size=10,
            in_range_rate=0.9,
        )
        values = [next(generator) for i in range(1000)]
        in_range = [soft_min <= value <= soft_max for value in values]
        assert 850 <= sum(in_range) <= 950


class TestSimulableHardware:
    """
    Contains tests of the hardware classes that support simulation:

    * :py:class:`ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
    * :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
    * :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareManager`
    """

    @pytest.fixture()
    def static_hardware_simulator(self, request):
        """
        Fixture that returns a static hardware simulator for testing. Actually there is
        nothing particularly static about this simulator, but our test only requires
        that our static and dynamic hardware simulators be distinct objects.

        :param request: A pytest object giving access to the requesting
            test context.
        :type request: :py:class:`pytest.FixtureRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
        """
        kwargs = getattr(request, "param", {"is_connectible": True})
        return HardwareSimulator(**kwargs)

    @pytest.fixture()
    def dynamic_hardware_simulator(self, request):
        """
        Fixture that returns a dynamic hardware simulator for testing. Actually there is
        nothing particularly dynamic about this simulator, but our test only requires
        that our static and dynamic hardware simulators be distinct objects.

        :param request: A pytest object giving access to the requesting
            test context.
        :type request: :py:class:`pytest.FixtureRequest`
        :return: a hardware simulator
        :rtype: :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
        """
        kwargs = getattr(request, "param", {"is_connectible": True})
        return HardwareSimulator(**kwargs)

    @pytest.fixture()
    def hardware_factory(
        self,
        request,
        hardware_driver,
        static_hardware_simulator,
        dynamic_hardware_simulator,
    ):
        """
        Fixture that returns a hardware factory for simulable hardware.

        :param request: A pytest object giving access to the requesting
            test context.
        :type request: :py:class:`pytest.FixtureRequest`
        :param hardware_driver: the hardware driver to be returned by
            by this hardware factory when not in simulation mode
        :type hardware_driver:
            :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareDriver`
        :param static_hardware_simulator: the hardware simulator to be
            returned by this hardware factory when in simulation mode
            and test mode
        :type static_hardware_simulator:
            :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
        :param dynamic_hardware_simulator: the hardware simulator to be
            returned by this hardware factory when in simulation mode
            but not in test mode
        :type dynamic_hardware_simulator:
            :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`

        :return: a hardware factory for simulable hardware
        :rtype:
            :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
        """
        return SimulableHardwareFactory(
            True,
            _driver=hardware_driver,
            _static_simulator=static_hardware_simulator,
            _dynamic_simulator=dynamic_hardware_simulator,
        )

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, hardware_health_evaluator):
        """
        Fixture that returns a
        :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareManager` for
        testing

        :param hardware_factory: the hardware factory used by this
            hardware manager
        :type hardware_factory:
            :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
        :param hardware_health_evaluator: the hardware health evaluator
            used by this hardware manager
        :type hardware_health_evaluator:
            :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareHealthEvaluator`

        :return: a simulable hardware manager
        :rtype:
            :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareManager`
        """
        return SimulableHardwareManager(hardware_factory, hardware_health_evaluator)

    class TestHardwareSimulator:
        """
        This class contains the tests for the HardwareSimulator class.

        (The HardwareSimulator class is a software-only representation
        of a hardware driver.
        """

        @pytest.mark.parametrize(
            ("static_hardware_simulator", "connection_status"),
            [
                (
                    {"is_connectible": True, "fail_connect": False},
                    ConnectionStatus.CONNECTED,
                ),
                (
                    {"is_connectible": True, "fail_connect": True},
                    ConnectionStatus.NOT_CONNECTED,
                ),
            ],
            indirect=("static_hardware_simulator",),
        )
        def test_init(self, static_hardware_simulator, connection_status):
            """
            Test initialisation of this hardware simulator.

            :param static_hardware_simulator: the hardware simulator under test
            :type static_hardware_simulator:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param connection_status: the status of the simulated
                software-hardware connection
            :type connection_status:
                :py:class:`ska_low_mccs.hardware.base_hardware.ConnectionStatus`
            """
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.NOT_CONNECTED
            )
            _ = static_hardware_simulator.connect()
            assert static_hardware_simulator.connection_status == connection_status

        def test_simulate_connection_failure(self, static_hardware_simulator):
            """
            Test that simulating connection failure causes the hardware simulator to
            think its connection has been lost.

            :param static_hardware_simulator: the hardware simulator under test
            :type static_hardware_simulator:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            """
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.NOT_CONNECTED
            )
            assert static_hardware_simulator.connect()
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.CONNECTED
            )
            static_hardware_simulator.simulate_connection_failure(True)
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.NOT_CONNECTED
            )
            assert not static_hardware_simulator.connect()
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.NOT_CONNECTED
            )
            static_hardware_simulator.simulate_connection_failure(False)
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.NOT_CONNECTED
            )
            assert static_hardware_simulator.connect()
            assert (
                static_hardware_simulator.connection_status
                == ConnectionStatus.CONNECTED
            )

    class TestSimulableHardwareFactory:
        """
        This class contains tests of the
        :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
        class.
        """

        def test_simulation_mode(
            self, hardware_driver, static_hardware_simulator, hardware_factory
        ):
            """
            Test that different hardware is returned depending on simulation mode.

            :param hardware_driver: the hardware driver that the
                hardware factory returns when not in simulation mode
            :type hardware_driver:
                :py:class:`ska_low_mccs.hardware.base_hardware.HardwareDriver`
            :param static_hardware_simulator: the hardware simulator that the
                hardware factory returns when in simulation mode
            :type static_hardware_simulator:
                :py:class:`ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param hardware_factory: a hardware factory that returns a
                driver or simulator depending on its simulation mode
            :type hardware_factory:
                :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
            """
            # check precondition - the test doesn't make sense unless
            # these are unequal
            assert hardware_driver != static_hardware_simulator

            assert hardware_factory.simulation_mode
            assert hardware_factory.hardware == static_hardware_simulator

            hardware_factory.simulation_mode = False
            assert not hardware_factory.simulation_mode
            assert hardware_factory.hardware == hardware_driver

            hardware_factory.simulation_mode = True
            assert hardware_factory.simulation_mode
            assert hardware_factory.hardware == static_hardware_simulator

        def test_test_mode(
            self,
            hardware_driver,
            static_hardware_simulator,
            dynamic_hardware_simulator,
            hardware_factory,
        ):
            """
            Test that, when in simulation mode, a different simulator is returned
            depending on test mode.

            :param hardware_driver: the hardware driver that the
                hardware factory returns when not in simulation mode
            :type hardware_driver:
                :py:class:`ska_low_mccs.hardware.base_hardware.HardwareDriver`
            :param static_hardware_simulator: the hardware simulator
                that the hardware factory returns when in simulation
                mode and test mode
            :type static_hardware_simulator:
                :py:class:`ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param dynamic_hardware_simulator: the hardware simulator
                that the hardware factory returns when in simulation
                mode but not in test mode
            :type dynamic_hardware_simulator:
                :py:class:`ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param hardware_factory: a hardware factory that returns a
                driver or simulator depending on its simulation mode
            :type hardware_factory:
                :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
            """
            # check precondition - the test doesn't make sense unless
            # these are unequal
            assert static_hardware_simulator != dynamic_hardware_simulator

            assert hardware_factory.simulation_mode
            assert hardware_factory.test_mode
            assert hardware_factory.hardware == static_hardware_simulator

            hardware_factory.test_mode = False
            assert not hardware_factory.test_mode
            assert hardware_factory.hardware == dynamic_hardware_simulator

            hardware_factory.test_mode = True
            assert hardware_factory.test_mode
            assert hardware_factory.hardware == static_hardware_simulator

    class TestSimulableHardwareManager:
        """
        This class contains the tests for the SimulableHardwareManager class.

        (The SimulableHardwareManager class is a base class for classes
        that manage hardware, on behalf of a device, in circumstances
        where a simulator may be substituted for the hardware.
        """

        def test_simulation_mode(
            self, hardware_driver, static_hardware_simulator, hardware_manager
        ):
            """
            Test that changing simulation mode, where the simulator is simulating
            connection failure, causes changes in health.

            :param hardware_driver: the hardware driver (simulated for
                testing purposes)
            :type hardware_driver:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param static_hardware_simulator: the hardware simulator
            :type static_hardware_simulator:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.HardwareSimulator`
            :param hardware_manager: the hardware manager under test
            :type hardware_manager:
                :py:class:`~ska_low_mccs.hardware.simulable_hardware.SimulableHardwareManager`
            """
            assert hardware_manager.simulation_mode
            assert hardware_manager.health == HealthState.UNKNOWN

            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK

            static_hardware_simulator.simulate_connection_failure(True)
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.FAILED

            hardware_manager.simulation_mode = SimulationMode.FALSE
            hardware_manager.poll()
            assert hardware_manager.health == HealthState.OK

            hardware_manager.simulation_mode = SimulationMode.TRUE
            assert hardware_manager.health == HealthState.FAILED
