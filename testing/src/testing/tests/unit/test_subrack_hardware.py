# type: ignore
#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests of the subrack hardware, including the
SubrackHardwareManager class and the SubrackBoardSimulator.

When we eventually have a SubrackDriver that drives real hardware, this
module could also be used to test that.
"""
import pytest

from ska_tango_base.control_model import SimulationMode
from ska_low_mccs.subrack import (
    SubrackHardwareManager,
    SubrackBoardSimulator,
    SubrackBaySimulator,
)


@pytest.fixture()
def subrack_simulator(logger):
    """
    Fixture that returns a TPM simulator.

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`
    :type logger: :py:class:`logging.Logger`

    :return: a subrack simulator
    :rtype:
        :py:class:`ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
    """
    return SubrackBoardSimulator()


@pytest.fixture()
def subrack_hardware_manager(logger, mock_callback):
    """
    Fixture that returns a hardware manager for the MCCS subrack device, in hardware
    simulation mode.

    :param logger: a object that implements the standard logging
        interface of :py:class:`logging.Logger`
    :type logger: :py:class:`logging.Logger`
    :param mock_callback: a mock to pass as a callback
    :type mock_callback: :py:class:`unittest.mock.Mock`

    :return: a hardware manager for the MCCS subrack device, in hardware
        simulation mode
    :rtype: :py:class:`ska_low_mccs.subrack.subrack_device.SubrackHardwareManager`
    """
    return SubrackHardwareManager(
        SimulationMode.TRUE,
        mock_callback,
        logger=logger,
        subrack_ip="0.0.0.0",
        subrack_port=8081,
    )


class TestSubrackHardwareManager:
    """Contains tests specific to SubrackHardwareManager."""

    def test_init_simulation_mode(self, logger, mock_callback):
        """
        Test that we cannot create an hardware manager that isn't in simulation mode.

        :param logger: a object that implements the standard logging
            interface of :py:class:`logging.Logger`
        :type logger: :py:class:`logging.Logger`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        _ = SubrackHardwareManager(
            SimulationMode.FALSE,
            mock_callback,
            logger=logger,
            subrack_ip="0.0.0.0",
            subrack_port=8081,
        )

    def test_simulation_mode(self, subrack_hardware_manager):
        """
        Test that we can't take the subrack hardware manager out of simulation mode.

        :param subrack_hardware_manager: a manager for subrack hardware
        :type subrack_hardware_manager:
            :py:class:`~ska_low_mccs.subrack.subrack_device.SubrackHardwareManager`
        """
        assert subrack_hardware_manager.simulation_mode == SimulationMode.TRUE
        subrack_hardware_manager.simulation_mode = SimulationMode.FALSE
        assert subrack_hardware_manager.simulation_mode == SimulationMode.FALSE


class TestCommon:
    """
    Because the SubrackHardwareManager is designed to pass commands through to the
    SubrackBoardSimulator or SubrackDriver that it is driving, many commands are common
    to SubrackHardwareManager and SubrackBoardSimulator, and they will also be common to
    the SubrackDriver when we eventually implement it.

    Therefore this class contains common tests, parametrised to test
    against each class
    """

    @pytest.fixture(params=["subrack_simulator", "subrack_hardware_manager"])
    def hardware_under_test(self, subrack_simulator, subrack_hardware_manager, request):
        """
        Return the hardware under test. This is parametrised to return both a TPM
        simulator and a subrack hardware manager, so any test that relies on this
        fixture will be run twice: once for each hardware type.

        :param subrack_simulator: an instance of the simulator
        :param subrack_hardware_manager: an instance of the subrack hardware manager
        :param request: which one to choose

        :return: the simulator or the driver
        """
        if request.param == "subrack_simulator":
            return subrack_simulator
        elif request.param == "subrack_hardware_manager":
            return subrack_hardware_manager

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            (
                "backplane_temperatures",
                SubrackBoardSimulator.DEFAULT_BACKPLANE_TEMPERATURE,
            ),
            ("board_temperatures", SubrackBoardSimulator.DEFAULT_BOARD_TEMPERATURE),
            ("board_current", SubrackBoardSimulator.DEFAULT_BOARD_CURRENT),
            ("subrack_fan_speeds", SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_SPEED),
            (
                "subrack_fan_speeds_percent",
                [
                    speed * 100.0 / SubrackBoardSimulator.MAX_SUBRACK_FAN_SPEED
                    for speed in SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_SPEED
                ],
            ),
            ("subrack_fan_mode", SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_MODE),
            ("tpm_count", 8),
            ("tpm_temperatures", [SubrackBaySimulator.DEFAULT_TEMPERATURE] * 8),
            (
                "tpm_powers",
                [
                    SubrackBaySimulator.DEFAULT_VOLTAGE
                    * SubrackBaySimulator.DEFAULT_CURRENT
                ]
                * 8,
            ),
            ("tpm_voltages", [SubrackBaySimulator.DEFAULT_VOLTAGE] * 8),
            (
                "power_supply_fan_speeds",
                SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEED,
            ),
            (
                "power_supply_currents",
                SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_CURRENT,
            ),
            (
                "power_supply_powers",
                SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_POWER,
            ),
            (
                "power_supply_voltages",
                SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE,
            ),
            ("tpm_present", SubrackBoardSimulator.DEFAULT_TPM_PRESENT),
            ("tpm_currents", [SubrackBaySimulator.DEFAULT_CURRENT] * 8),
        ),
    )
    def test_read_attribute(self, hardware_under_test, attribute_name, expected_value):
        """
        Tests that read-only attributes take certain known initial values. This is a
        weak test; over time we should find ways to more thoroughly test each of these
        independently.

        :param hardware_under_test: the hardware object under test. This
            could be a SubrackBoardSimulator, or a SubrackHardwareManager, or, when
            we eventually write it, a SubrackDriver of an actual hardware
            TPM
        :type hardware_under_test: object
        :param attribute_name: the name of the attribute under test
        :type attribute_name: str
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :type expected_value: object
        """
        hardware_under_test.connect()
        hardware_under_test.on()
        hardware_under_test.turn_on_tpms()
        assert getattr(hardware_under_test, attribute_name) == expected_value

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("are_tpms_on", 0),
            ("turn_on_tpms", 0),
            ("turn_off_tpms", 0),
        ),
    )
    def test_command(self, hardware_under_test, command_name, num_args):
        """
        Test of commands that require no parameters don't really do anything, these
        tests simply check that the command can be called.

        :param hardware_under_test: the hardware object under test. This
            could be a SubrackBoardSimulator, or a SubrackHardwareManager, or, when
            we eventually write it, a SubrackDriver of an actual hardware
            subrack
        :type hardware_under_test: object
        :param command_name: the name of the command under test
        :type command_name: str
        :param num_args: the number of args the command takes
        :type num_args: int
        """
        hardware_under_test.connect()
        hardware_under_test.on()
        _ = getattr(hardware_under_test, command_name)()

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("is_tpm_on", 1),
            ("turn_on_tpm", 1),
            ("turn_off_tpm", 1),
            ("set_subrack_fan_speed", 2),
            ("set_subrack_fan_mode", 2),
            ("set_subrack_fan_speed", 2),
            ("set_power_supply_fan_speed", 2),
        ),
    )
    def test_command_numeric(self, hardware_under_test, command_name, num_args):
        """
        Test of commands that require numeric parameters don't really do anything, these
        tests simply check that the command can be called.

        :param hardware_under_test: the hardware object under test. This
            could be a SubrackBoardSimulator, or a SubrackHardwareManager, or, when
            we eventually write it, a SubrackDriver of an actual hardware
            subrack
        :type hardware_under_test: object
        :param command_name: the name of the command under test
        :type command_name: str
        :param num_args: the number of args the command takes
        :type num_args: int
        """
        hardware_under_test.connect()
        hardware_under_test.on()
        if num_args == 1:
            _ = getattr(hardware_under_test, command_name)(1)
        elif num_args == 2:
            _ = getattr(hardware_under_test, command_name)(1, 1)
