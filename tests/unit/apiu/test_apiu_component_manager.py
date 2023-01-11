# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the APIU component manager and simulator."""
from __future__ import annotations

import threading
import time
from typing import Callable, Union, cast
from unittest.mock import patch

import pytest
from _pytest.fixtures import SubRequest
from ska_control_model import PowerState, TaskStatus
from ska_low_mccs_common.testing.mock import MockCallable, MockCallableDeque

from ska_low_mccs.apiu import (
    ApiuComponentManager,
    ApiuSimulator,
    ApiuSimulatorComponentManager,
    SwitchingApiuComponentManager,
)


class TestApiuCommon:
    """
    Common tests.

    Because the ApiuComponentManager is designed to pass commands through to the
    ApiuSimulator or (or actual APIU) that it is driving, many commands are common to.

    * the ApiuSimulator,
    * the ApiuSimulatorComponentManager,
    * the SwitchingApiuComponentManager (when in simulation mode)
    * the ApiuComponentManager (when in simulation mode and turned on)

    Therefore this class contains common tests, parametrised to test
    against each class.
    """

    @pytest.fixture()
    def initial_power_mode(self: TestApiuCommon) -> PowerState:
        """
        Return the initial power mode of the APIU's simulated power supply.

        :return: the initial power mode of the APIU's simulated power
            supply.
        """
        return PowerState.ON

    # pylint: disable=too-many-arguments
    @pytest.fixture(
        params=[
            "apiu_simulator",
            "apiu_simulator_component_manager",
            "switching_apiu_component_manager",
            "apiu_component_manager",
        ]
    )
    def apiu(
        self: TestApiuCommon,
        apiu_simulator: ApiuSimulator,
        apiu_simulator_component_manager: ApiuSimulatorComponentManager,
        switching_apiu_component_manager: SwitchingApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
        request: SubRequest,
    ) -> Union[
        ApiuSimulator,
        ApiuSimulatorComponentManager,
        SwitchingApiuComponentManager,
        ApiuComponentManager,
    ]:
        """
        Return the APIU class under test.

        This is parametrised to return

        * an APIU simulator,

        * an APIU simulator component manager,

        * a component manager that switches between APIU driver and
          simulator (in simulation mode), and

        * an APIU component manager (in simulation mode and turned on)

        So any test that relies on this fixture will be run four times:
        once for each of the above classes.

        :param apiu_simulator: the APIU simulator to return
        :param apiu_simulator_component_manager: the APIU simulator
            component manager to return
        :param switching_apiu_component_manager:
            a component manager that switches between APIU simulator and
            driver (in simulation mode)
        :param apiu_component_manager: the APIU component manager to
            return (in simulation mode and powered on)
        :param request: A pytest object giving access to the requesting
            test context.
        :param component_state_changed_callback: Callback to call when the
            component's state changes.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the APIU class object under test
        """
        if request.param == "apiu_simulator":
            return apiu_simulator
        if request.param == "apiu_simulator_component_manager":
            apiu_simulator_component_manager.start_communicating()
            return apiu_simulator_component_manager
        if request.param == "switching_apiu_component_manager":
            switching_apiu_component_manager.start_communicating()
            return switching_apiu_component_manager
        if request.param == "apiu_component_manager":
            apiu_component_manager.start_communicating()
            time.sleep(0.1)
            apiu_component_manager.on()
            time.sleep(0.1)
            expected_arguments = {"power_state": PowerState.ON}
            component_state_changed_callback.assert_in_deque(expected_arguments)
            apiu_component_manager.power_state = PowerState.ON
            return apiu_component_manager
        raise ValueError("apiu fixture parametrized with unrecognised option")

    def test_apiu_properties(
        self: TestApiuCommon,
        apiu: Union[
            ApiuSimulator,
            ApiuSimulatorComponentManager,
            SwitchingApiuComponentManager,
            ApiuComponentManager,
        ],
        random_current: Callable[[], float],
        random_humidity: Callable[[], float],
        random_temperature: Callable[[], float],
        random_voltage: Callable[[], float],
    ) -> None:
        """
        Test that the APIU properties.

        e.g. current, humidity, temperature and
        voltage, can be read, and that we can simulate changing values for them.

        :param apiu: the APIU component class object under test
        :param random_current: a random value within a reasonable range
            for a current measurement
        :param random_humidity: a random value within a reasonable range
            for a humidity measurement
        :param random_temperature: a random value within a reasonable
            range for a temperature measurement
        :param random_voltage: a random value within a reasonable range
            for a voltage measurement
        """
        assert apiu.current == ApiuSimulator.DEFAULT_CURRENT
        current = random_current()
        apiu.simulate_current(current)
        assert apiu.current == current

        assert apiu.humidity == ApiuSimulator.DEFAULT_HUMIDITY
        humidity = random_humidity()
        apiu.simulate_humidity(humidity)
        assert apiu.humidity == humidity

        assert apiu.temperature == ApiuSimulator.DEFAULT_TEMPERATURE
        temperature = random_temperature()
        apiu.simulate_temperature(temperature)
        assert apiu.temperature == temperature

        assert apiu.voltage == ApiuSimulator.DEFAULT_VOLTAGE
        voltage = random_voltage()
        apiu.simulate_voltage(voltage)
        assert apiu.voltage == voltage

    def test_antenna_on_off(
        self: TestApiuCommon,
        apiu_antenna_count: int,
        apiu: Union[ApiuSimulator, ApiuSimulatorComponentManager, ApiuComponentManager],
    ) -> None:
        """
        Test the APIU object.

        * can turn antennas on and off
        * can retrieve voltage, current and temperature values from the
          antennas when they are on
        * can simulate changed values of the above when the antennas are
          on.

        :param apiu_antenna_count: the number of antennas in the APIU
        :param apiu: the APIU component class object under test
        """
        assert apiu.antenna_count == apiu_antenna_count

        assert apiu.are_antennas_on() == [False] * apiu_antenna_count

        for antenna_id in range(1, apiu_antenna_count + 1):
            assert not apiu.is_antenna_on(antenna_id)
            with pytest.raises(ValueError, match="Antenna is not powered on."):
                _ = apiu.get_antenna_current(antenna_id)
            with pytest.raises(ValueError, match="Antenna is not powered on."):
                _ = apiu.get_antenna_voltage(antenna_id)
            with pytest.raises(ValueError, match="Antenna is not powered on."):
                _ = apiu.get_antenna_temperature(antenna_id)

            apiu.turn_on_antenna(antenna_id)

            # After turning on the antenna, it should be on, and all others should be
            # off.
            for _id in range(1, apiu_antenna_count + 1):
                assert apiu.is_antenna_on(_id) == (_id == antenna_id)

            assert (
                apiu.get_antenna_current(antenna_id)
                == ApiuSimulator.DEFAULT_ANTENNA_CURRENT
            )
            apiu.simulate_antenna_current(antenna_id, 3.2)
            assert apiu.get_antenna_current(antenna_id) == 3.2

            assert (
                apiu.get_antenna_voltage(antenna_id)
                == ApiuSimulator.DEFAULT_ANTENNA_VOLTAGE
            )
            apiu.simulate_antenna_voltage(antenna_id, 20.4)
            assert apiu.get_antenna_voltage(antenna_id) == 20.4

            assert (
                apiu.get_antenna_temperature(antenna_id)
                == ApiuSimulator.DEFAULT_ANTENNA_TEMPERATURE
            )
            apiu.simulate_antenna_temperature(antenna_id, 23.7)
            assert apiu.get_antenna_temperature(antenna_id) == 23.7

            apiu.turn_off_antenna(antenna_id)
            assert not apiu.is_antenna_on(antenna_id)
            assert apiu.are_antennas_on() == [False] * apiu_antenna_count

    def test_antennas_on_off(
        self: TestApiuCommon,
        apiu_antenna_count: int,
        apiu: Union[ApiuSimulator, ApiuSimulatorComponentManager, ApiuComponentManager],
    ) -> None:
        """
        Test that we can turn all the antennas on/off at once.

        :param apiu_antenna_count: the number of antennas in the APIU
        :param apiu: the APIU component class object under test
        """

        def check_all_antennas_on_off(mode: bool) -> None:
            """
            Check all antennas.

            Verify they are on, or that all antennas are off, depending on the mode.

            :param mode: whether all antennas are expected to be on or
                off. If true, all antennas are expected to be on. If
                false, all antennas are expected to be off.
            """
            are_antennas_on = apiu.are_antennas_on()
            if mode:
                assert all(are_antennas_on)
            else:
                assert not any(are_antennas_on)
            assert len(are_antennas_on) == apiu_antenna_count

            for antenna_id in range(1, apiu_antenna_count + 1):
                assert apiu.is_antenna_on(antenna_id) == mode

        check_all_antennas_on_off(False)
        apiu.turn_off_antennas()
        check_all_antennas_on_off(False)
        apiu.turn_on_antennas()
        check_all_antennas_on_off(True)
        apiu.turn_on_antennas()
        check_all_antennas_on_off(True)
        apiu.turn_off_antennas()
        check_all_antennas_on_off(False)


class TestApiuComponentManager:
    """Tests of the APIU component manager."""

    def test_component_fault_callback(
        self: TestApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that the callback is called when we simulate a fault.

        :param apiu_component_manager: the APIU component manager under
            test
        :param component_state_changed_callback: callback to be called when the
            component faults (or stops faulting)
        """
        apiu_component_manager.start_communicating()
        time.sleep(0.1)
        apiu_component_manager.on()
        time.sleep(0.1)
        expected_arguments = [{"fault": False}, {"power_state": PowerState.ON}]
        component_state_changed_callback.assert_all_in_deque(expected_arguments)
        cast(
            SwitchingApiuComponentManager, apiu_component_manager
        )._hardware_component_manager._component.simulate_fault(True)
        time.sleep(0.1)
        expected_arguments = [{"fault": True}, {"power_state": PowerState.OFF}]
        component_state_changed_callback.assert_all_in_deque(expected_arguments)

        cast(
            SwitchingApiuComponentManager, apiu_component_manager
        )._hardware_component_manager._component.simulate_fault(False)
        time.sleep(0.1)
        expected_arguments = [{"fault": False}]
        component_state_changed_callback.assert_in_deque(expected_arguments[0])

    def test_turn_on_off_antenna(
        self: TestApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that the callback is called when we change the power mode of an antenna.

        (i.e. turn it on or off).

        :param apiu_component_manager: the APIU component manager under
            test
        :param component_state_changed_callback: callback to be
            called when the power mode of an antenna changes
        """
        apiu_component_manager.start_communicating()
        time.sleep(0.1)
        apiu_component_manager.on()
        time.sleep(0.1)
        expected_arguments = {"power_state": PowerState.ON}
        component_state_changed_callback.assert_in_deque(expected_arguments)
        apiu_component_manager.power_state = PowerState.ON

        def mocked_failure() -> None:
            raise Exception("mocked exception")

        with patch(
            "ska_low_mccs.apiu.apiu_component_manager"
            + ".ComponentManagerWithUpstreamPowerSupply.on",
            side_effect=mocked_failure,
        ):

            task_callback_on = MockCallable()
            apiu_component_manager.on(task_callback_on)
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.QUEUED
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.IN_PROGRESS
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.FAILED
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.COMPLETED

        with patch(
            "ska_low_mccs.apiu.apiu_component_manager"
            + ".ApiuSimulatorComponentManager._get_from_component",
            side_effect=mocked_failure,
        ):

            task_callback_on = MockCallable()
            apiu_component_manager.off(task_callback_on)
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.QUEUED
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.IN_PROGRESS
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.FAILED
            time.sleep(0.1)
            _, kwargs = task_callback_on.get_next_call()
            assert kwargs["status"] == TaskStatus.COMPLETED

    def test_on_off_apiu_antenna_mockedfailure_task_callbacks(
        self: TestApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
    ) -> None:
        """
        Test task callbacks with mocked failure.

        :param apiu_component_manager: the APIU component manager under
            test
        """

        def mocked_failure() -> None:
            raise Exception("mocked exception")

        with patch(
            "ska_low_mccs.apiu.apiu_component_manager."
            + "ApiuSimulatorComponentManager._get_from_component",
            side_effect=mocked_failure,
        ):
            task_callback = MockCallable()
            commands = {
                "power_down": None,
                "power_up": None,
                "power_up_antenna": 1,
                "power_down_antenna": 1,
            }

            for command, parameter in commands.items():
                if parameter:
                    getattr(apiu_component_manager, command)(parameter, task_callback)
                else:
                    getattr(apiu_component_manager, command)(task_callback)
                time.sleep(0.1)
                _, kwargs = task_callback.get_next_call()
                assert kwargs["status"] == TaskStatus.QUEUED
                time.sleep(0.1)
                _, kwargs = task_callback.get_next_call()
                assert kwargs["status"] == TaskStatus.IN_PROGRESS
                time.sleep(0.1)
                _, kwargs = task_callback.get_next_call()
                assert kwargs["status"] == TaskStatus.FAILED

    def test_power_commands_with_abort(
        self: TestApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test task callbacks with mocked failure.

        :param apiu_component_manager: the APIU component manager under
            test
        :param component_state_changed_callback: a mocked callable for state
            change
        """
        apiu_component_manager.start_communicating()
        time.sleep(0.1)
        apiu_component_manager.on()
        time.sleep(0.1)
        expected_arguments = {"power_state": PowerState.ON}
        component_state_changed_callback.assert_in_deque(expected_arguments)
        apiu_component_manager.power_state = PowerState.ON
        task_callback = MockCallable()
        commands = {
            "_on": None,
            "_off": None,
            "_turn_on_antenna": 1,
            "_turn_off_antenna": 1,
        }
        abort_event = threading.Event()
        abort_event.set()

        for command, parameter in commands.items():
            if parameter:
                getattr(apiu_component_manager, command)(
                    parameter, task_callback, abort_event
                )
            else:
                getattr(apiu_component_manager, command)(task_callback, abort_event)

            time.sleep(0.1)
            _, kwargs = task_callback.get_next_call()
            assert kwargs["status"] == TaskStatus.IN_PROGRESS
            time.sleep(0.1)
            _, kwargs = task_callback.get_next_call()
            assert kwargs["status"] == TaskStatus.ABORTED

    def test_turn_on_off_apiu_antenna_task_callbacks(
        self: TestApiuComponentManager,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
    ) -> None:
        """
        Test that the callback is called when we change the power mode of an antenna.

        (i.e. turn it on or off).

        :param apiu_component_manager: the APIU component manager under
            test
        :param component_state_changed_callback: callback to be
            called when the power mode of an antenna changes
        """
        apiu_component_manager.start_communicating()
        time.sleep(0.1)
        apiu_component_manager.on()
        time.sleep(0.1)
        expected_arguments = {"power_state": PowerState.ON}
        component_state_changed_callback.assert_in_deque(expected_arguments)
        apiu_component_manager.power_state = PowerState.ON

        commands = {
            "on": "On command has completed",
            "off": "Off command has completed",
            "power_up": "The antenna all on task has completed",
            "power_down": "The antenna all off task has completed",
        }

        for command, expected_result in commands.items():
            getattr(apiu_component_manager, command)(component_state_changed_callback)
            component_state_changed_callback.assert_last_call(status=TaskStatus.QUEUED)
            time.sleep(0.1)
            component_state_changed_callback.assert_last_call(
                status=TaskStatus.COMPLETED, result=expected_result
            )

        # Turns off antenna
        apiu_component_manager.power_up_antenna(1, component_state_changed_callback)
        component_state_changed_callback.assert_last_call(status=TaskStatus.QUEUED)
        # wait to give time for process to complete
        time.sleep(0.1)
        component_state_changed_callback.assert_last_call(
            status=TaskStatus.COMPLETED, result="The antenna on task has completed"
        )

        # Turns off antennas
        apiu_component_manager.power_down_antenna(1, component_state_changed_callback)
        component_state_changed_callback.assert_last_call(status=TaskStatus.QUEUED)
        # wait to give time for process to complete
        time.sleep(0.1)
        component_state_changed_callback.assert_last_call(
            status=TaskStatus.COMPLETED, result="The antenna off task has completed"
        )

    @pytest.mark.parametrize("antenna_id", [1, 2])
    def test_component_antenna_power_changed_callback(
        self: TestApiuComponentManager,
        apiu_antenna_count: int,
        apiu_component_manager: ApiuComponentManager,
        component_state_changed_callback: MockCallableDeque,
        antenna_id: int,
    ) -> None:
        """
        Test that the callback is called when we change the power mode of an antenna.

        (i.e. turn it on or off).

        :param apiu_antenna_count: number of antennas managed by the
            APIU
        :param apiu_component_manager: the APIU component manager under
            test
        :param component_state_changed_callback: callback to be
            called when the power mode of an antenna changes
        :param antenna_id: the number of the antenna to use in the test
        """
        apiu_component_manager.start_communicating()
        time.sleep(0.1)
        apiu_component_manager.on()
        time.sleep(0.1)
        expected_power_arguments = {"power_state": PowerState.ON}
        component_state_changed_callback.assert_in_deque(expected_power_arguments)
        apiu_component_manager.power_state = PowerState.ON

        expected_are_antennas_on = [False] * apiu_antenna_count
        # expected_arguments = {"are_antennas_on": expected_are_antennas_on}
        assert apiu_component_manager.are_antennas_on() == expected_are_antennas_on
        # component_state_changed_callback.assert_in_deque(expected_arguments)
        # time.sleep(0.1)
        # assert component_state_changed_callback.assert_in_deque(expected_arguments)

        apiu_component_manager.turn_on_antenna(antenna_id)
        expected_are_antennas_on[antenna_id - 1] = True
        # expected_arguments = {"are_antennas_on": expected_are_antennas_on}
        assert apiu_component_manager.are_antennas_on() == expected_are_antennas_on
        # component_state_changed_callback.assert_in_deque(expected_arguments)

        #         apiu_component_manager.turn_on_antenna(antenna_id)
        #         component_state_changed_callback.assert_not_called()

        apiu_component_manager.turn_off_antenna(antenna_id)
        expected_are_antennas_on[antenna_id - 1] = False
        # expected_arguments = {"are_antennas_on": expected_are_antennas_on}
        assert apiu_component_manager.are_antennas_on() == expected_are_antennas_on
        # component_state_changed_callback.assert_next_call(expected_are_antennas_on)


#         apiu_component_manager.turn_off_antenna(antenna_id)
#         component_state_changed_callback.assert_not_called()
