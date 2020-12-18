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
:py:mod:`ska.low.mccs.hardware.simulable_hardware` module.
"""
import pytest

from ska.base.control_model import HealthState, SimulationMode
from ska.low.mccs.hardware import (
    HardwareSimulator,
    SimulableHardwareFactory,
    SimulableHardwareManager,
)


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
        Fixture that returns a hardware simulator for testing.

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
        Fixture that returns a hardware factory for simulable hardware.

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

        (The HardwareSimulator class is a software-only representation
        of a hardware driver.
        """

        @pytest.mark.parametrize(
            ("hardware_simulator", "is_connected"),
            [(False, False), (True, True)],
            indirect=("hardware_simulator",),
        )
        def test_init(self, hardware_simulator, is_connected):
            """
            Test initialisation of this hardware simulator.

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
            simulator to think its connection has been lost.

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
            simulation mode.

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
            simulating connection failure, causes changes in health.

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
