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
"""This module contains the tests of the subrack component manager."""
from __future__ import annotations

from typing import Union

import pytest
from _pytest.fixtures import SubRequest  # type: ignore[import]

from ska_tango_base.control_model import PowerMode

from ska_low_mccs.subrack import (
    SubrackComponentManager,
    SubrackSimulator,
    SubrackSimulatorComponentManager,
    SwitchingSubrackComponentManager,
)

from ska_low_mccs.testing.mock import MockCallable


class TestSubrackCommon:
    """
    This class contains tests common to several subrack component manager classes.

    Because the subrack component manager is designed to pass commands
    through to the subrack simulator or driver, many commands are common
    to:

    * the SubrackSimulator,
    * the SubrackSimulatorComponentManager,
    * the SwitchingSubrackComponentManager (when in simulation mode)
    * the SubrackComponentManager (when in simulation mode and turned on)

    Therefore this class contains common tests, parametrised to test
    against each class.
    """

    @pytest.fixture(
        params=[
            "subrack_simulator",
            "subrack_simulator_component_manager",
            "switching_subrack_component_manager",
            "subrack_component_manager",
        ]
    )
    def subrack(
        self: TestSubrackCommon,
        subrack_simulator: SubrackSimulator,
        subrack_simulator_component_manager: SubrackSimulatorComponentManager,
        switching_subrack_component_manager: SwitchingSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        request: SubRequest,
    ) -> Union[
        SubrackSimulator,
        SubrackSimulatorComponentManager,
        SwitchingSubrackComponentManager,
        SubrackComponentManager,
    ]:
        """
        Return the subrack class under test.

        This is parametrised to return:

        * a subrack simulator,

        * a subrack simulator component manager,

        * a component manager that switches between subrack driver and
          simulator (in simulation mode), and

        * a subrack component manager (in simulation mode and turned on)

        So any test that relies on this fixture will be run four times:
        once for each of the above classes.

        :param subrack_simulator: the subrack simulator to return
        :param subrack_simulator_component_manager: the subrack
            simulator component manager to return
        :param switching_subrack_component_manager:
            a component manager that switches between subrack simulator
            and driver (in simulation mode)
        :param subrack_component_manager: the subrack component manager
            to return (in simulation mode and powered on)
        :param request: A pytest object giving access to the requesting
            test context.

        :raises AssertionError: if parametrized with an unrecognised option

        :return: the subrack class object under test
        """
        if request.param == "subrack_simulator":
            return subrack_simulator
        elif request.param == "subrack_simulator_component_manager":
            subrack_simulator_component_manager.start_communicating()
            return subrack_simulator_component_manager
        elif request.param == "switching_subrack_component_manager":
            switching_subrack_component_manager.start_communicating()
            return switching_subrack_component_manager
        elif request.param == "subrack_component_manager":
            subrack_component_manager.start_communicating()
            subrack_component_manager.on()
            return subrack_component_manager
        raise AssertionError("subrack fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            (
                "backplane_temperatures",
                SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURE,
            ),
            ("board_temperatures", SubrackSimulator.DEFAULT_BOARD_TEMPERATURE),
            ("board_current", SubrackSimulator.DEFAULT_BOARD_CURRENT),
            ("subrack_fan_speeds", SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS),
            (
                "subrack_fan_speeds_percent",
                [
                    speed * 100.0 / SubrackSimulator.MAX_SUBRACK_FAN_SPEED
                    for speed in SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
                ],
            ),
            ("subrack_fan_mode", SubrackSimulator.DEFAULT_SUBRACK_FAN_MODE),
            ("tpm_count", 8),
            ("tpm_temperatures", [SubrackSimulator.DEFAULT_TPM_TEMPERATURE] * 8),
            (
                "tpm_powers",
                [
                    SubrackSimulator.DEFAULT_TPM_VOLTAGE
                    * SubrackSimulator.DEFAULT_TPM_CURRENT
                ]
                * 8,
            ),
            ("tpm_voltages", [SubrackSimulator.DEFAULT_TPM_VOLTAGE] * 8),
            (
                "power_supply_fan_speeds",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
            ),
            (
                "power_supply_currents",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENT,
            ),
            (
                "power_supply_powers",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_POWER,
            ),
            (
                "power_supply_voltages",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE,
            ),
            ("tpm_present", SubrackSimulator.DEFAULT_TPM_PRESENT),
            ("tpm_currents", [SubrackSimulator.DEFAULT_TPM_CURRENT] * 8),
        ),
    )
    def test_read_attribute(
        self, subrack: Union[SubrackSimulator], attribute_name, expected_value
    ):
        """
        Tests that read-only attributes take certain known initial values. This is a
        weak test; over time we should find ways to more thoroughly test each of these
        independently.

        :param subrack: the subrack class object under test.
        :param attribute_name: the name of the attribute under test
        :type attribute_name: str
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :type expected_value: object
        """
        subrack.turn_on_tpms()
        assert getattr(subrack, attribute_name) == expected_value

    @pytest.mark.parametrize(
        "command_name",
        (
            "are_tpms_on",
            "turn_on_tpms",
            "turn_off_tpms",
        ),
    )
    def test_command(self, subrack: Union[SubrackSimulator], command_name):
        """
        Test of commands that require no parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        :type command_name: str
        """
        _ = getattr(subrack, command_name)()

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
    def test_command_numeric(
        self, subrack: Union[SubrackSimulator], command_name, num_args
    ):
        """
        Test of commands that require numeric parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        :type command_name: str
        :param num_args: the number of args the command takes
        :type num_args: int
        """
        if num_args == 1:
            _ = getattr(subrack, command_name)(1)
        elif num_args == 2:
            _ = getattr(subrack, command_name)(1, 1)


class TestSubrackComponentManager:
    """Tests of the subrack component manager."""

    @pytest.mark.parametrize("tpm_id", [1, 2])
    def test_component_tpm_power_changed_callback(
        self: TestSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        component_tpm_power_changed_callback: MockCallable,
        tpm_id: int,
    ) -> None:
        """
        Test that the callback is called when we change the power mode of an tpm (i.e.
        turn it on or off).

        :param subrack_component_manager: the subrack component manager under
            test
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of an tpm changes
        :param tpm_id: the number of the tpm to use in the test
        """
        subrack_component_manager.start_communicating()
        subrack_component_manager.on()
        assert subrack_component_manager.power_mode == PowerMode.ON

        expected_are_tpms_on = [False] * subrack_component_manager.tpm_count
        component_tpm_power_changed_callback.assert_next_call(expected_are_tpms_on)
        assert subrack_component_manager.are_tpms_on() == expected_are_tpms_on

        subrack_component_manager.turn_on_tpm(tpm_id)
        expected_are_tpms_on[tpm_id - 1] = True
        component_tpm_power_changed_callback.assert_next_call(expected_are_tpms_on)
        assert subrack_component_manager.are_tpms_on() == expected_are_tpms_on

        subrack_component_manager.turn_on_tpm(tpm_id)
        component_tpm_power_changed_callback.assert_not_called()

        subrack_component_manager.turn_off_tpm(tpm_id)
        expected_are_tpms_on[tpm_id - 1] = False
        component_tpm_power_changed_callback.assert_next_call(expected_are_tpms_on)
        assert subrack_component_manager.are_tpms_on() == expected_are_tpms_on

        subrack_component_manager.turn_off_tpm(tpm_id)
        component_tpm_power_changed_callback.assert_not_called()
