# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of the switching_component_manager module."""
from __future__ import annotations

import unittest.mock

import pytest
import pytest_mock
from ska_tango_base.control_model import SimulationMode

from ska_low_mccs.component import DriverSimulatorSwitchingComponentManager
from ska_low_mccs.component.switching_component_manager import Switcher


class TestSwitcher:
    """Tests of the switcher class."""

    @pytest.fixture()
    def option_a(
        self: TestSwitcher,
        mocker: pytest_mock.MockerFixture,
    ) -> unittest.mock.Mock:
        """
        Return a mock option to switch between.

        :param mocker: fixture that returns a mock.

        :return: a mock option to switch between.
        """
        return mocker.Mock()

    @pytest.fixture()
    def option_b(
        self: TestSwitcher,
        mocker: pytest_mock.MockerFixture,
    ) -> unittest.mock.Mock:
        """
        Return another mock option to switch between.

        :param mocker: fixture that returns a mock.

        :return: another mock option to switch between.
        """
        return mocker.Mock()

    @pytest.fixture()
    def switcher(
        self: TestSwitcher,
        option_a: unittest.mock.Mock,
        option_b: unittest.mock.Mock,
    ) -> Switcher:
        """
        Return a Switcher with two options to switch between.

        :param option_a: an option for the switcher
        :param option_b: another option for the switcher

        :return: a Switcher between option a and option b
        """
        return Switcher({"a": option_a, "b": option_b, "c": None}, "a")

    def test_switching(
        self: TestSwitcher,
        option_a: unittest.mock.Mock,
        option_b: unittest.mock.Mock,
        switcher: Switcher,
    ) -> None:
        """
        Test switching between options.

        :param option_a: an option for the switcher
        :param option_b: another option for the switcher
        :param switcher: a Switcher between option a and option b
        """
        assert switcher.switcher_mode == "a"
        switcher.foo()
        option_a.foo.assert_called_once_with()
        option_b.foo.assert_not_called()

        switcher.switcher_mode = "b"
        assert switcher.switcher_mode == "b"
        switcher.bah()
        option_a.bah.assert_not_called()
        option_b.bah.assert_called_once_with()

        with pytest.raises(NotImplementedError, match="Unimplemented switcher mode 'c'."):
            switcher.switcher_mode = "c"
        assert switcher.switcher_mode == "b"

        with pytest.raises(KeyError, match="Unrecognised switcher mode 'd'."):
            switcher.switcher_mode = "d"
        assert switcher.switcher_mode == "b"


class TestDriverSimulatorSwitchingComponentManager:
    """Tests of the switching component manager."""

    @pytest.fixture()
    def driver_component_manager(
        self: TestDriverSimulatorSwitchingComponentManager,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        Return a mock component manager that purports to drive a real component.

        :param mocker: pytest mocker fixture

        :return: a mock component manager that purports to drive a real
            component.
        """
        return mocker.Mock()

    @pytest.fixture()
    def simulator_component_manager(
        self: TestDriverSimulatorSwitchingComponentManager,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        Return a mock component manager that purports to drive a simulator component.

        :param mocker: pytest mocker fixture

        :return: a mock component manager that purports to drive a
            simulator component.
        """
        return mocker.Mock()

    class TestSwitching:
        """Tests of the switching component manager, for implemented drivers."""

        @pytest.fixture()
        def switching_component_manager(
            self: TestDriverSimulatorSwitchingComponentManager.TestSwitching,
            driver_component_manager: unittest.mock.Mock,
            simulator_component_manager: unittest.mock.Mock,
        ) -> DriverSimulatorSwitchingComponentManager:
            """
            Return a component manager that switches between driver and simulator mode.

            :param driver_component_manager: a mock component manager
                that purports to drive a real component.
            :param simulator_component_manager: a mock component manager
                that purports to drive a simulator component.

            :return: a component manager that can switch between driver
                and simulator mode.
            """
            return DriverSimulatorSwitchingComponentManager(
                driver_component_manager,
                simulator_component_manager,
                SimulationMode.FALSE,
            )

        def test_switching(
            self: TestDriverSimulatorSwitchingComponentManager.TestSwitching,
            driver_component_manager: unittest.mock.Mock,
            simulator_component_manager: unittest.mock.Mock,
            switching_component_manager: DriverSimulatorSwitchingComponentManager,
        ) -> None:
            """
            Test switching between simulator and driver.

            :param driver_component_manager: a mock component manager
                that purports to drive a real component.
            :param simulator_component_manager: a mock component manager
                that purports to drive a simulator component.
            :param switching_component_manager: the component manager
                under test: a component manager that can switch between
                underlying component managers for driver and simulator.
            """
            assert switching_component_manager.simulation_mode == SimulationMode.FALSE

            switching_component_manager.foo()
            driver_component_manager.foo.assert_called_once_with()
            simulator_component_manager.foo.assert_not_called()

            switching_component_manager.simulation_mode = SimulationMode.TRUE
            driver_component_manager.stop_communicating.assert_called_once_with()
            simulator_component_manager.start_communicating.assert_called_once_with()
            assert switching_component_manager.simulation_mode == SimulationMode.TRUE

            switching_component_manager.bah()
            driver_component_manager.bah.assert_not_called()
            simulator_component_manager.bah.assert_called_once_with()

    class TestSwitchingWithUnimplementedDriver:
        """Tests of the switching component manager, for unimplemented drivers."""

        @pytest.fixture()
        def switching_component_manager(
            self: TestDriverSimulatorSwitchingComponentManager.TestSwitchingWithUnimplementedDriver,
            simulator_component_manager: unittest.mock.Mock,
        ) -> DriverSimulatorSwitchingComponentManager:
            """
            Return a switching component manager with unimplemented driver mode.

            The switching component manager can purportedly switch
            between a simulator component manager and a driver component
            manager, but the driver component manager is unimplemented.

            :param simulator_component_manager: the component manager
                for the simulator

            :return: a component manager that can switch between
                simulator component manager, and an unimplemented driver
                component manager.
            """
            return DriverSimulatorSwitchingComponentManager(
                None,
                simulator_component_manager,
                SimulationMode.TRUE,
            )

        def test_switching_with_unimplemented_driver(
            self: TestDriverSimulatorSwitchingComponentManager.TestSwitchingWithUnimplementedDriver,
            simulator_component_manager: unittest.mock.Mock,
            switching_component_manager: DriverSimulatorSwitchingComponentManager,
        ) -> None:
            """
            Test that we can't switch to an unimplemented driver.

            :param simulator_component_manager: the component manager
                for the simulator
            :param switching_component_manager: a component manager
                that can switch between simulator component manager, and
                an unimplemented driver component manager.
            """
            assert switching_component_manager.simulation_mode == SimulationMode.TRUE

            switching_component_manager.foo()
            simulator_component_manager.foo.assert_called_once_with()

            with pytest.raises(
                NotImplementedError,
                match="Unimplemented switcher mode 'SimulationMode.FALSE'.",
            ):
                switching_component_manager.simulation_mode = SimulationMode.FALSE

            assert switching_component_manager.simulation_mode == SimulationMode.TRUE

            switching_component_manager.bah()
            simulator_component_manager.bah.assert_called_once_with()
