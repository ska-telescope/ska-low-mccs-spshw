# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the subrack component manager."""
from __future__ import annotations

import time
import unittest
from typing import Any, Union

import pytest
from _pytest.fixtures import SubRequest
from ska_control_model import (
    CommunicationStatus,
    PowerState,
    SimulationMode,
    TaskStatus,
)
from ska_low_mccs_common.testing.mock import MockCallable, MockCallableDeque

from ska_low_mccs_spshw.subrack import (
    SubrackComponentManager,
    SubrackData,
    SubrackDriver,
    SubrackSimulatorComponentManager,
    SwitchingSubrackComponentManager,
)
from ska_low_mccs_spshw.subrack.internal_subrack_simulator import (
    InternalSubrackSimulator as SubrackSimulator,
)


class TestSubrackSimulatorCommon:
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

    @pytest.fixture()
    def initial_power_mode(self: TestSubrackSimulatorCommon) -> PowerState:
        """
        Return the initial power mode of the subrack's simulated power supply.

        :return: the initial power mode of the subrack's simulated power
            supply.
        """
        return PowerState.ON

    @pytest.fixture(
        params=[
            "switching_subrack_component_manager",
            "subrack_component_manager",
        ]
    )
    def subrack(
        self: TestSubrackSimulatorCommon,
        switching_subrack_component_manager: SwitchingSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        component_state_changed_callback,
        request: SubRequest,
    ) -> Union[SwitchingSubrackComponentManager, SubrackComponentManager]:
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

        :param switching_subrack_component_manager:
            a component manager that switches between subrack simulator
            and driver (in simulation mode)
        :param subrack_component_manager: the subrack component manager
            to return (in simulation mode and powered on)
        :param request: A pytest object giving access to the requesting
            test context.
        :param component_state_changed_callback: Callback to call when the
            component's state changes.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the subrack class object under test
        """
        if request.param == "switching_subrack_component_manager":
            switching_subrack_component_manager.start_communicating()
            return switching_subrack_component_manager
        elif request.param == "subrack_component_manager":
            subrack_component_manager.start_communicating()
            time.sleep(0.1)
            subrack_component_manager.on()
            time.sleep(0.1)
            expected_arguments = {"power_state": PowerState.ON}
            component_state_changed_callback.assert_in_deque(expected_arguments)
            subrack_component_manager.power_state = PowerState.ON
            return subrack_component_manager
        raise ValueError("subrack fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            (
                "backplane_temperatures",
                SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURES,
            ),
            (
                "board_temperatures",
                SubrackSimulator.DEFAULT_BOARD_TEMPERATURES,
            ),
            ("board_current", SubrackSimulator.DEFAULT_BOARD_CURRENT),
            (
                "subrack_fan_speeds",
                SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS,
            ),
            (
                "subrack_fan_speeds_percent",
                [
                    speed * 100.0 / SubrackData.MAX_SUBRACK_FAN_SPEED
                    for speed in SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
                ],
            ),
            ("subrack_fan_modes", SubrackSimulator.DEFAULT_SUBRACK_FAN_MODES),
            ("tpm_count", SubrackData.TPM_BAY_COUNT),
            (
                "tpm_temperatures",
                [SubrackSimulator.DEFAULT_TPM_TEMPERATURE] * SubrackData.TPM_BAY_COUNT,
            ),
            (
                "tpm_powers",
                [
                    SubrackSimulator.DEFAULT_TPM_VOLTAGE
                    * SubrackSimulator.DEFAULT_TPM_CURRENT
                ]
                * SubrackData.TPM_BAY_COUNT,
            ),
            (
                "tpm_voltages",
                [SubrackSimulator.DEFAULT_TPM_VOLTAGE] * SubrackData.TPM_BAY_COUNT,
            ),
            (
                "power_supply_fan_speeds",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
            ),
            (
                "power_supply_currents",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENTS,
            ),
            (
                "power_supply_powers",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_POWERS,
            ),
            (
                "power_supply_voltages",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGES,
            ),
            ("tpm_present", SubrackSimulator.DEFAULT_TPM_PRESENT),
            (
                "tpm_currents",
                [SubrackSimulator.DEFAULT_TPM_CURRENT] * SubrackData.TPM_BAY_COUNT,
            ),
        ),
    )
    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_read_attribute(
        self: TestSubrackSimulatorCommon,
        subrack: Union[
            SubrackSimulator,
            SubrackSimulatorComponentManager,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a
        weak test; over time we should find ways to more thoroughly test each of these
        independently.

        :param subrack: the subrack class object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        subrack.turn_on_tpms()
        assert getattr(subrack, attribute_name) == expected_value

    @pytest.mark.parametrize(
        "command_name",
        (
            "turn_on_tpms",
            "turn_off_tpms",
        ),
    )
    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_command(
        self: TestSubrackSimulatorCommon,
        subrack: Union[
            SubrackSimulator,
            SubrackSimulatorComponentManager,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        command_name: str,
    ) -> None:
        """
        Test of commands that require no parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        """
        _ = getattr(subrack, command_name)()

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("is_tpm_on", 1),
            ("turn_on_tpm", 1),
            ("turn_off_tpm", 1),
            ("set_subrack_fan_speed", 2),
            ("set_subrack_fan_modes", 2),
            ("set_power_supply_fan_speed", 2),
        ),
    )
    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_command_numeric(
        self: TestSubrackSimulatorCommon,
        subrack: Union[
            SubrackSimulator,
            SubrackSimulatorComponentManager,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        command_name: str,
        num_args: int,
    ) -> None:
        """
        Test of commands that require numeric parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        :param num_args: the number of args the command takes
        """
        if num_args == 1:
            _ = getattr(subrack, command_name)(1)
        elif num_args == 2:
            _ = getattr(subrack, command_name)(1, 1)

    @pytest.mark.parametrize(
        ("command_name", "args"),
        (
            ("simulate_power_supply_voltages", [0.1, 0.2]),
            ("simulate_backplane_temperatures", [0.3, 0.4]),
            ("simulate_board_temperatures", [0.5, 0.6]),
            ("simulate_board_current", [0.7, 0.8]),
            ("simulate_subrack_fan_speeds", [0.9, 1.0]),
            (
                "simulate_tpm_temperatures",
                [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8],
            ),
            (
                "simulate_tpm_currents",
                [2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8],
            ),
            ("simulate_tpm_powers", [3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8]),
            (
                "simulate_tpm_voltages",
                [4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8],
            ),
            ("simulate_power_supply_fan_speeds", [1.7, 1.8]),
            ("simulate_power_supply_currents", [1.9, 2.0]),
            ("simulate_power_supply_powers", [2.1, 2.2]),
        ),
    )
    def test_commands_with_lists(
        self: TestSubrackSimulatorCommon,
        subrack: Union[
            SubrackSimulator,
            SubrackSimulatorComponentManager,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        command_name: str,
        args: Any,
    ) -> None:
        """
        Test of commands that require list parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        :param args: the args the command takes
        """
        _ = getattr(subrack, command_name)(args)


class TestSubrackDriverCommon:
    """
    This class contains tests common to several subrack component manager classes.

    Because the subrack component manager is designed to pass commands
    through to the subrack simulator or driver, many commands are common
    to:

    * the SubrackDriver,
    * the SwitchingSubrackComponentManager (when in driver mode)
    * the SubrackComponentManager (when in driver mode and turned on)

    Therefore this class contains common tests, parametrised to test
    against each class.
    """

    @pytest.fixture()
    def initial_power_mode(self: TestSubrackSimulatorCommon) -> PowerState:
        """
        Return the initial power mode of the subrack's simulated power supply.

        :return: the initial power mode of the subrack's simulated power
            supply.
        """
        return PowerState.ON

    @pytest.fixture(
        params=[
            "subrack_driver",
            "switching_subrack_component_manager",
            "subrack_component_manager",
        ]
    )
    def subrack(
        self: TestSubrackDriverCommon,
        subrack_driver: SubrackDriver,
        switching_subrack_component_manager: SwitchingSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        component_state_changed_callback,
        request: SubRequest,
    ) -> Union[
        SubrackDriver,
        SwitchingSubrackComponentManager,
        SubrackComponentManager,
    ]:
        """
        Return the subrack class under test.

        This is parametrised to return:

        * a subrack driver,

        * a component manager that switches between subrack driver and
          simulator (in driver mode), and

        * a subrack component manager (in driver mode and turned on)

        So any test that relies on this fixture will be run three times:
        once for each of the above classes.

        :param subrack_driver: the subrack driver to return
        :param switching_subrack_component_manager:
            a component manager that switches between subrack simulators
            and driver (in driver mode)
        :param subrack_component_manager: the subrack component manager
            to return (in driver mode and powered on)
        :param request: A pytest object giving access to the requesting
            test context.
        :param component_state_changed_callback: Callback to call when the
            component's state changes.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the subrack class object under test
        """
        if request.param == "subrack_driver":
            return subrack_driver
        elif request.param == "switching_subrack_component_manager":
            switching_subrack_component_manager.simulation_mode = SimulationMode.FALSE
            switching_subrack_component_manager.start_communicating()
            return switching_subrack_component_manager
        elif request.param == "subrack_component_manager":
            subrack_component_manager.simulation_mode = SimulationMode.FALSE
            subrack_component_manager.start_communicating()
            time.sleep(0.1)
            subrack_component_manager.on()
            time.sleep(0.2)
            expected_arguments = {"power_state": PowerState.ON}
            component_state_changed_callback.assert_in_deque(expected_arguments)
            subrack_component_manager.power_state = PowerState.ON
            return subrack_component_manager
        raise ValueError("subrack fixture parametrized with unrecognised option")

    @pytest.fixture()
    def web_hardware_client_mock(
        self: TestSubrackDriverCommon,
    ) -> unittest.mock.Mock:
        """
        Provide a mock for the web hardware client.

        :return: A web hardware client mock
        """
        return unittest.mock.Mock()

    def test_communication(
        self: TestSubrackDriverCommon,
        subrack_driver: SubrackDriver,
        web_hardware_client_mock: unittest.mock.Mock,
    ) -> None:
        """
        Create the subrack driver and start communication with the component.

        :param subrack_driver: the subrack driver under test.
        :param web_hardware_client_mock: a mock provided for the
            web hardare client member of the subrack driver.
        """
        setattr(subrack_driver, "_client", web_hardware_client_mock)
        web_hardware_client_mock.connect.return_value = True
        assert subrack_driver.communication_state == CommunicationStatus.DISABLED
        subrack_driver.start_communicating()
        assert subrack_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED

        # Wait for the message to execute
        time.sleep(0.1)
        web_hardware_client_mock.connect.assert_called_once()
        # assert "_ConnectToSubrack" in subrack_driver._queue_manager._task_result[0]
        # assert subrack_driver._queue_manager._task_result[1] ==
        # str(ResultCode.OK.value)
        # assert "Connected to " in subrack_driver._queue_manager._task_result[2]
        assert subrack_driver.communication_state == CommunicationStatus.ESTABLISHED

    def test_communication_fails(
        self: TestSubrackDriverCommon,
        subrack_driver: SubrackDriver,
        web_hardware_client_mock: unittest.mock.Mock,
    ) -> None:
        """
        Create the subrack driver and start communication with the component.

        Failure to communicate with the underlying client must be handled correctly.

        :param subrack_driver: the subrack driver under test.
        :param web_hardware_client_mock: a mock provided for the
            web hardare client member of the subrack driver.
        """
        setattr(subrack_driver, "_client", web_hardware_client_mock)
        web_hardware_client_mock.connect.return_value = False
        assert subrack_driver.communication_state == CommunicationStatus.DISABLED
        subrack_driver.start_communicating()
        assert subrack_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED

        # Wait for the message to execute
        time.sleep(0.1)
        web_hardware_client_mock.connect.assert_called_once()
        # assert "_ConnectToSubrack" in subrack_driver._queue_manager._task_result[0]
        # assert subrack_driver._queue_manager._task_result[1] == str(
        #    ResultCode.FAILED.value
        # )
        # assert "Failed to connect to " in
        # subrack_driver._queue_manager._task_result[2]
        assert subrack_driver.communication_state == CommunicationStatus.NOT_ESTABLISHED

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            (
                "backplane_temperatures",
                SubrackSimulator.DEFAULT_BACKPLANE_TEMPERATURES,
            ),
            (
                "board_temperatures",
                SubrackSimulator.DEFAULT_BOARD_TEMPERATURES,
            ),
            ("board_current", SubrackSimulator.DEFAULT_BOARD_CURRENT),
            (
                "subrack_fan_speeds",
                SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS,
            ),
            (
                "subrack_fan_speeds_percent",
                [
                    speed * 100.0 / SubrackData.MAX_SUBRACK_FAN_SPEED
                    for speed in SubrackSimulator.DEFAULT_SUBRACK_FAN_SPEEDS
                ],
            ),
            ("subrack_fan_modes", SubrackSimulator.DEFAULT_SUBRACK_FAN_MODES),
            ("tpm_count", SubrackData.TPM_BAY_COUNT),
            ("tpm_temperatures", [0.0] * SubrackData.TPM_BAY_COUNT),
            (
                "tpm_powers",
                [
                    SubrackSimulator.DEFAULT_TPM_VOLTAGE
                    * SubrackSimulator.DEFAULT_TPM_CURRENT
                ]
                * SubrackData.TPM_BAY_COUNT,
            ),
            (
                "tpm_voltages",
                [SubrackSimulator.DEFAULT_TPM_VOLTAGE] * SubrackData.TPM_BAY_COUNT,
            ),
            (
                "power_supply_fan_speeds",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEEDS,
            ),
            (
                "power_supply_currents",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_CURRENTS,
            ),
            (
                "power_supply_powers",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_POWERS,
            ),
            (
                "power_supply_voltages",
                SubrackSimulator.DEFAULT_POWER_SUPPLY_VOLTAGES,
            ),
            ("tpm_present", SubrackSimulator.DEFAULT_TPM_PRESENT),
            (
                "tpm_currents",
                [SubrackSimulator.DEFAULT_TPM_CURRENT] * SubrackData.TPM_BAY_COUNT,
            ),
        ),
    )
    # @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_read_attribute(
        self: TestSubrackDriverCommon,
        subrack: Union[
            SubrackDriver,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a
        weak test; over time we should find ways to more thoroughly test each of these
        independently.

        :param subrack: the subrack class object under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        subrack.turn_on_tpms()
        assert getattr(subrack, attribute_name) == expected_value

    @pytest.mark.parametrize(
        "command_name",
        (
            "turn_on_tpms",
            "turn_off_tpms",
        ),
    )
    #  @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_command(
        self: TestSubrackDriverCommon,
        subrack: Union[
            SubrackDriver,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        command_name: str,
    ) -> None:
        """
        Test of commands that require no parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        """
        _ = getattr(subrack, command_name)()

    @pytest.mark.parametrize(
        ("command_name", "num_args"),
        (
            ("is_tpm_on", 1),
            ("turn_on_tpm", 1),
            ("turn_off_tpm", 1),
            ("set_subrack_fan_speed", 2),
            ("set_subrack_fan_modes", 2),
            ("set_power_supply_fan_speed", 2),
        ),
    )
    #  @pytest.mark.skip(reason="needs fixing for base class version 0.12.0")
    def test_command_numeric(
        self: TestSubrackDriverCommon,
        subrack: Union[
            SubrackDriver,
            SwitchingSubrackComponentManager,
            SubrackComponentManager,
        ],
        command_name: str,
        num_args: int,
    ) -> None:
        """
        Test of commands that require numeric parameters.

        These tests don't really do anything, they simply check that the
        command can be called.

        :param subrack: the subrack class object under test.
        :param command_name: the name of the command under test
        :param num_args: the number of args the command takes
        """
        if num_args == 1:
            _ = getattr(subrack, command_name)(1)
        elif num_args == 2:
            _ = getattr(subrack, command_name)(1, 1)


class TestSubrackComponentManager:
    """Tests of the subrack component manager."""

    @pytest.mark.parametrize("tpm_id", [1, 2])
    def test_tpm_power_states(
        self: TestSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        component_state_changed_callback: MockCallableDeque,
        tpm_id: int,
    ) -> None:
        """
        Test that the callback is called when we change the power mode of an tpm.

        (i.e. turn it on or off).

        :param subrack_component_manager: the subrack component manager under
            test
        :param component_state_changed_callback: callback to be
            called when the component power mode changes
        :param tpm_id: the number of the tpm to use in the test
        """
        subrack_component_manager.start_communicating()
        time.sleep(0.2)
        component_state_changed_callback.assert_in_deque(
            {"power_state": PowerState.OFF}
        )
        subrack_component_manager.power_state = PowerState.OFF
        assert subrack_component_manager.power_state == PowerState.OFF
        time.sleep(0.2)

        expected_tpm_power_states = [PowerState.NO_SUPPLY] * SubrackData.TPM_BAY_COUNT
        component_state_changed_callback.assert_next_call_with_keys(
            {"tpm_power_states": expected_tpm_power_states}
        )
        time.sleep(0.2)

        subrack_component_manager._on()
        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.ON}
        )
        subrack_component_manager.power_state = PowerState.ON
        assert subrack_component_manager.power_state == PowerState.ON

        expected_tpm_power_states = [PowerState.OFF] * SubrackData.TPM_BAY_COUNT
        component_state_changed_callback.assert_next_call_with_keys(
            {"tpm_power_states": expected_tpm_power_states}
        )
        subrack_component_manager._tpm_power_states = expected_tpm_power_states
        assert subrack_component_manager.tpm_power_states == expected_tpm_power_states

        assert subrack_component_manager.turn_on_tpm(tpm_id)
        time.sleep(0.2)
        expected_tpm_power_states[tpm_id - 1] = PowerState.ON
        component_state_changed_callback.assert_in_deque(
            {"tpm_power_states": expected_tpm_power_states}
        )
        assert subrack_component_manager.tpm_power_states == expected_tpm_power_states

        assert subrack_component_manager.turn_off_tpm(tpm_id)
        time.sleep(0.2)
        expected_tpm_power_states[tpm_id - 1] = PowerState.OFF
        component_state_changed_callback.assert_next_call_with_keys(
            {"tpm_power_states": expected_tpm_power_states}
        )
        assert subrack_component_manager.tpm_power_states == expected_tpm_power_states

        subrack_component_manager._off()
        time.sleep(0.2)
        component_state_changed_callback.assert_next_call_with_keys(
            {"power_state": PowerState.OFF}
        )
        subrack_component_manager.power_state = PowerState.OFF
        assert subrack_component_manager.power_state == PowerState.OFF
        time.sleep(0.3)
        expected_tpm_power_states = [PowerState.NO_SUPPLY] * SubrackData.TPM_BAY_COUNT
        component_state_changed_callback.assert_in_deque(
            {"tpm_power_states": expected_tpm_power_states}
        )

        expected_tpm_power_states = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT
        subrack_component_manager.stop_communicating()
        time.sleep(0.2)
        component_state_changed_callback.assert_in_deque(
            {"tpm_power_states": expected_tpm_power_states}
        )

    def test_component_progress_changed_callback(
        self: TestSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that the callback is called when we change the progress.

        Reported by the subrack simulator when using the 'turn_on_tpm' method.

        :param subrack_component_manager: the subrack component manager under
            test
        :param component_state_changed_callback: callback to be
            called when the progress value of a tpm command changes
        """
        subrack_component_manager.start_communicating()
        time.sleep(0.1)
        subrack_component_manager.on()
        time.sleep(0.1)

        expected_arguments = {"power_state": PowerState.ON}
        component_state_changed_callback.assert_in_deque(expected_arguments)
        subrack_component_manager.power_state = PowerState.ON
        subrack_component_manager.turn_on_tpm(1)
        time.sleep(0.3)
        component_state_changed_callback.assert_next_call_with_keys({"progress": 0})
        component_state_changed_callback.assert_next_call_with_keys({"progress": 100})

    def test_component_upstream_power_state_task_callback(
        self: TestSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
    ) -> None:
        """
        Test the task callbacks during on and off commands.

        :param subrack_component_manager: the subrack component manager under
            test
        """
        subrack_component_manager.start_communicating()
        time.sleep(0.1)
        task_callback_on = MockCallable()

        subrack_component_manager.on(task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "On command has completed"

        subrack_component_manager.off(task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "Off command completed"

    def test_component_subservient_power_state_task_callback(
        self: TestSubrackComponentManager,
        subrack_component_manager: SubrackComponentManager,
    ) -> None:
        """
        Test the task callbacks during power commands to subservient device.

        :param subrack_component_manager: the subrack component manager under
            test
        """
        subrack_component_manager.start_communicating()
        time.sleep(0.1)
        task_callback_on = MockCallable()
        tpm_id = 2
        subrack_component_manager.turn_on_tpm(tpm_id, task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert (
            kwargs["result"] == f"Subrack TPM {tpm_id} turn on tpm task has completed"
        )

        subrack_component_manager.power_state = PowerState.ON

        subrack_component_manager.turn_off_tpm(tpm_id, task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert (
            kwargs["result"] == f"Subrack TPM {tpm_id} turn off tpm task has completed"
        )

        subrack_component_manager.turn_on_tpms(task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "The turn tpms on task has completed"

        subrack_component_manager.power_state = PowerState.ON

        subrack_component_manager.turn_off_tpms(task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.IN_PROGRESS

        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.COMPLETED
        assert kwargs["result"] == "The turn tpms off task has completed"

        subrack_component_manager.power_state = PowerState.OFF

        subrack_component_manager.turn_off_tpm(tpm_id, task_callback=task_callback_on)
        time.sleep(0.1)
        _, kwargs = task_callback_on.get_next_call()
        assert kwargs["status"] == TaskStatus.QUEUED

        # This should be put in a queue for when the power next comes on
        task_callback_on.assert_not_called()
