# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the subrack component manager."""
from __future__ import annotations

from typing import Any, Literal

import pytest
from ska_control_model import CommunicationStatus, PowerState, ResultCode, TaskStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.subrack import (
    FanMode,
    SubrackComponentManager,
    SubrackData,
    SubrackSimulator,
)


class TestNoSupply:
    """
    Tests of the no supply scenario.

    That is, tests of the subrack component manager where the upstream
    power supply proxy reports that it has no power supply. In this
    cases, not only is the subrack off, but it cannot be turned on.
    """

    @pytest.fixture()
    def initial_power_state(self: TestNoSupply) -> Literal[PowerState.NO_SUPPLY]:
        """
        Set the initial power state of the upstream power supply.

        :return: PowerState.NO_SUPPLY
        """
        return PowerState.NO_SUPPLY

    def test_communication(
        self: TestNoSupply,
        subrack_component_manager: SubrackComponentManager,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test communication.

        :param subrack_component_manager: the subrack component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.NO_SUPPLY)
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.on(task_callback=callbacks["task"])

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.FAILED,
            result=(
                ResultCode.FAILED,
                "Poll failed: This power supply simulator has no power supply.",
            ),
        )
        callbacks["task"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.off()
        # Can't be bothered asserting task status QUEUED, IN_PROGRESS, FAILED,
        # since we already went through all that in the on() case
        # but in short, the poll will fail, so the state won't change.
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.stop_communicating()
        callbacks["component_state"].assert_call(power=PowerState.UNKNOWN)
        callbacks["component_state"].assert_not_called()


class TestUnknown:
    """
    Tests of the "power state unknown" scenario.

    That is, tests of the subrack component manager where the upstream
    power supply proxy reports that it does not have established
    communication with the upstream power supply, so its power state is
    unknown.
    """

    @pytest.fixture()
    def initial_power_state(self: TestUnknown) -> Literal[PowerState.UNKNOWN]:
        """
        Set the initial power state of the upstream power supply.

        :return: PowerState.UNKNOWN
        """
        return PowerState.UNKNOWN

    def test_communication(
        self: TestUnknown,
        subrack_component_manager: SubrackComponentManager,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test communication.

        :param subrack_component_manager: the subrack component manager
            under test
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_not_called()

        # no component state change will be pushed here,
        # because UNKNOWN is the initial state,
        # so nothing has changed.
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.on(task_callback=callbacks["task"])

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)

        callbacks["task"].assert_call(
            status=TaskStatus.FAILED,
            result=(
                ResultCode.FAILED,
                "Poll failed: No communication with power supply.",
            ),
        )
        callbacks["task"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.off()
        # Can't be bothered asserting task status QUEUED, IN_PROGRESS, FAILED,
        # since we already went through all that in the on() case
        # but in short the poll will fail, so the state won't change.
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.stop_communicating()
        callbacks["component_state"].assert_not_called()


class TestOff:
    """
    Tests of the off scenario.

    That is, tests of the subrack component manager where the upstream
    power supply proxy reports that the subrack is turned off.
    """

    @pytest.fixture()
    def initial_power_state(self: TestOff) -> PowerState:
        """
        Set the initial power state of the upstream power supply.

        :return: PowerState.OFF
        """
        return PowerState.OFF

    def test_communication(
        self: TestOff,
        subrack_component_manager: SubrackComponentManager,
        subrack_simulator_attribute_values: dict[str, Any],
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test communication.

        :param subrack_component_manager: the subrack component manager
            under test
        :param subrack_simulator_attribute_values: key-value dictionary of
            the expected subrack simulator attribute values
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.OFF)
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.on(task_callback=callbacks["task"])

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command completed"),
        )
        callbacks["task"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False)

        callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
        callbacks["component_state"].assert_not_called()

        # Now that the subrack is on,
        # we could also perform various commands if we wanted,
        # but let's save all that for the `TestOn` class below.

        subrack_component_manager.off(task_callback=callbacks["task"])

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command completed"),
        )
        callbacks["task"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.OFF, lookahead=2)
        callbacks["component_state"].assert_call(
            fault=None,
            **{
                attribute_name: None
                for attribute_name in subrack_simulator_attribute_values
            },
        )

        callbacks["component_state"].assert_not_called()

        subrack_component_manager.stop_communicating()
        callbacks["component_state"].assert_call(power=PowerState.UNKNOWN)
        callbacks["component_state"].assert_not_called()


class TestOn:
    """
    Tests of the on scenario.

    That is, tests of the subrack component manager where the upstream
    power supply proxy reports that the subrack is turned on.

    Most functionality is tested under this scenario, because most
    functionality only becomes available once the subrack is on.
    """

    @pytest.fixture()
    def initial_power_state(self: TestOn) -> PowerState:
        """
        Set the initial power state of the upstream power supply.

        :return: PowerState.ON
        """
        return PowerState.ON

    def test_attribute_updates(  # pylint: disable=too-many-locals
        self: TestOn,
        subrack_simulator: SubrackSimulator,
        subrack_component_manager: SubrackComponentManager,
        subrack_simulator_attribute_values: dict[str, Any],
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test that the subrack driver receives updated values.

        :param subrack_simulator: the subrack simulator backend that the
            subrack driver drives through its server interface.
        :param subrack_component_manager: the subrack component manager
            under test.
        :param subrack_simulator_attribute_values: key-value dictionary
            of the expected subrack simulator attribute values.
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        # Try to establish communication with the subrack's upstream power supply
        # (which is currently simulated).
        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )

        # Successful in establishing communication with the upstream power supply
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)

        callbacks["communication_status"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False)
        callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
        callbacks["component_state"].assert_not_called()

        subrack_simulator.simulate_attribute("board_current", 0.7)
        callbacks["component_state"].assert_call(
            board_current=pytest.approx(0.7),
        )

        for name, values in [
            ("backplane_temperatures", [45.0, 46.0]),
            ("board_temperatures", [47.0, 48.0]),
            # Not implemented on SMB
            # ("tpm_temperatures", [41.1, 41.2, 41.3, 41.4, 41.5, 41.6, 41.7, 41.8]),
        ]:
            subrack_simulator.simulate_attribute(name, values)
            callbacks["component_state"].assert_call(
                **{name: [pytest.approx(v) for v in values]},
            )

        new_power_supply_fan_speeds = [7500.0, 7600.0]
        subrack_simulator.simulate_attribute(
            "power_supply_fan_speeds", new_power_supply_fan_speeds
        )
        callbacks["component_state"].assert_call(
            power_supply_fan_speeds=[
                pytest.approx(s) for s in new_power_supply_fan_speeds
            ],
        )

        new_subrack_fan_speeds_percent = [73.0, 74.0, 75.0, 76.0]
        subrack_simulator.simulate_attribute(
            "subrack_fan_speeds_percent", new_subrack_fan_speeds_percent
        )
        callbacks["component_state"].assert_call(
            subrack_fan_speeds_percent=[
                pytest.approx(p) for p in new_subrack_fan_speeds_percent
            ],
            subrack_fan_speeds=[
                pytest.approx(p * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0)
                for p in new_subrack_fan_speeds_percent
            ],
        )

        power_supply_currents = subrack_simulator.get_attribute("power_supply_currents")
        new_power_supply_voltages = [13.1, 13.2]
        expected_power_supply_powers = [
            pytest.approx(i * v)
            for i, v in zip(power_supply_currents, new_power_supply_voltages)
        ]
        subrack_simulator.simulate_attribute(
            "power_supply_voltages", new_power_supply_voltages
        )
        callbacks["component_state"].assert_call(
            power_supply_voltages=[pytest.approx(v) for v in new_power_supply_voltages],
            power_supply_powers=expected_power_supply_powers,
        )

        new_power_supply_currents = [4.5, 4.6]
        expected_power_supply_powers = [
            pytest.approx(i * v)
            for i, v in zip(new_power_supply_currents, new_power_supply_voltages)
        ]
        subrack_simulator.simulate_attribute(
            "power_supply_currents", new_power_supply_currents
        )
        callbacks["component_state"].assert_call(
            power_supply_currents=[pytest.approx(i) for i in new_power_supply_currents],
            power_supply_powers=expected_power_supply_powers,
        )

        tpm_currents = subrack_simulator.get_attribute("tpm_currents")
        new_tpm_voltages = [12.2] * 8
        expected_tpm_powers = [
            pytest.approx(i * v) for i, v in zip(tpm_currents, new_tpm_voltages)
        ]
        subrack_simulator.simulate_attribute("tpm_voltages", new_tpm_voltages)
        callbacks["component_state"].assert_call(
            tpm_voltages=[pytest.approx(v) for v in new_tpm_voltages],
            tpm_powers=expected_tpm_powers,
        )

        new_tpm_currents = [0.45] * 8
        expected_tpm_powers = [
            pytest.approx(i * v) for i, v in zip(new_tpm_currents, new_tpm_voltages)
        ]
        subrack_simulator.simulate_attribute("tpm_currents", new_tpm_currents)
        callbacks["component_state"].assert_call(
            tpm_currents=[pytest.approx(i) for i in new_tpm_currents],
            tpm_powers=expected_tpm_powers,
        )

        subrack_component_manager.stop_communicating()

        callbacks["component_state"].assert_call(power=PowerState.UNKNOWN, lookahead=2)
        callbacks["component_state"].assert_call(
            fault=None,
            **{
                attribute_name: None
                for attribute_name in subrack_simulator_attribute_values
            },
        )
        callbacks["component_state"].assert_not_called()

    def test_tpm_power_commands(
        self: TestOn,
        subrack_simulator: SubrackSimulator,
        subrack_component_manager: SubrackComponentManager,
        subrack_simulator_attribute_values: dict[str, Any],
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test that the subrack driver pushes a full set of attribute values.

        :param subrack_simulator: the subrack simulator backend that the
            subrack driver drives through its server interface
        :param subrack_component_manager: the subrack component manager
            under test
        :param subrack_simulator_attribute_values: key-value dictionary of
            the expected subrack simulator attribute values
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False)
        callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
        callbacks["component_state"].assert_not_called()

        tpm_on_off = subrack_simulator.get_attribute("tpm_on_off")
        tpm_to_power = 3  # one-based

        assert not tpm_on_off[tpm_to_power - 1], "Test assumes TPM to be off."

        subrack_component_manager.turn_on_tpms(callbacks["task"])
        tpm_on_off = [True for _ in tpm_on_off]

        callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)
        callbacks["task"].assert_call(
            status=TaskStatus.COMPLETED,
            result=(ResultCode.OK, "Command completed."),
        )

        subrack_component_manager.turn_off_tpm(tpm_to_power)
        tpm_on_off[tpm_to_power - 1] = False
        callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

        subrack_component_manager.turn_off_tpms()
        tpm_on_off = [False for _ in tpm_on_off]
        callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

        subrack_component_manager.turn_on_tpm(tpm_to_power)
        tpm_on_off[tpm_to_power - 1] = True
        callbacks["component_state"].assert_call(tpm_on_off=tpm_on_off)

    def test_other_commands(
        self: TestOn,
        subrack_simulator: SubrackSimulator,
        subrack_component_manager: SubrackComponentManager,
        subrack_simulator_attribute_values: dict[str, Any],
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test that the subrack driver pushes a full set of attribute values.

        :param subrack_simulator: the subrack simulator backend that the
            subrack driver drives through its server interface
        :param subrack_component_manager: the subrack component manager
            under test
        :param subrack_simulator_attribute_values: key-value dictionary of
            the expected subrack simulator attribute values
        :param callbacks: dictionary of driver callbacks.
        """
        callbacks["communication_status"].assert_not_called()
        callbacks["component_state"].assert_not_called()

        subrack_component_manager.start_communicating()

        callbacks["communication_status"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_status"].assert_call(CommunicationStatus.ESTABLISHED)
        callbacks["communication_status"].assert_not_called()

        callbacks["component_state"].assert_call(power=PowerState.ON)
        callbacks["component_state"].assert_call(fault=False)
        callbacks["component_state"].assert_call(**subrack_simulator_attribute_values)
        callbacks["component_state"].assert_not_called()

        subrack_fan_speeds_percent = subrack_simulator.get_attribute(
            "subrack_fan_speeds_percent"
        )

        fan_to_set = 1  # one-based
        fan_speed_percent_setting = 78.0
        subrack_component_manager.set_subrack_fan_speed(
            fan_to_set, fan_speed_percent_setting
        )

        subrack_fan_speeds_percent[fan_to_set - 1] = fan_speed_percent_setting
        callbacks["component_state"].assert_call(
            subrack_fan_speeds_percent=[
                pytest.approx(p) for p in subrack_fan_speeds_percent
            ],
            subrack_fan_speeds=[
                pytest.approx(p * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0)
                for p in subrack_fan_speeds_percent
            ],
        )

        subrack_fan_mode = subrack_simulator.get_attribute("subrack_fan_mode")

        fan_to_set = 1  # one-based
        fan_speed_mode = (
            FanMode.AUTO
            if subrack_fan_mode[fan_to_set - 1] == FanMode.MANUAL
            else FanMode.MANUAL
        )
        subrack_component_manager.set_subrack_fan_mode(fan_to_set, fan_speed_mode)

        subrack_fan_mode[fan_to_set - 1] = fan_speed_mode
        callbacks["component_state"].assert_call(
            subrack_fan_mode=subrack_fan_mode,
        )

        power_supply_fan_speeds = subrack_simulator.get_attribute(
            "power_supply_fan_speeds"
        )

        fan_to_set = 2  # one-based
        fan_speed_setting = 7800.0
        subrack_component_manager.set_power_supply_fan_speed(
            fan_to_set, fan_speed_setting
        )

        power_supply_fan_speeds[fan_to_set - 1] = fan_speed_setting
        callbacks["component_state"].assert_call(
            power_supply_fan_speeds=[pytest.approx(s) for s in power_supply_fan_speeds],
        )
