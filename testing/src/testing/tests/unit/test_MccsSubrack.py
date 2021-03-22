###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsSubrack.
"""
import random
import pytest
from tango import DevState, AttrQuality, EventType

from ska_tango_base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.hardware import PowerMode, SimulableHardwareFactory
from ska_low_mccs.subrack.subrack_device import SubrackHardwareManager
from ska_low_mccs.subrack.subrack_simulator import (
    SubrackBaySimulator,
    SubrackBoardSimulator,
)


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "subrack_01",
        "proxy": MccsDeviceProxy,
    }


@pytest.fixture()
def random_current():
    """
    Return a callable that returns a random current value.

    :return: a callable that returns a random current value
    :rtype: callable
    """
    return lambda: random.uniform(0.5, 1.0)


@pytest.fixture()
def random_temperature():
    """
    Return a callable that returns a random temperature.

    :return: a callable that returns a random temperature
    :rtype: float
    """
    return lambda: random.uniform(42.0, 47.0)


@pytest.fixture()
def random_voltage():
    """
    Return a callable that returns a random voltage.

    :return: a callable that returns a random voltage
    :rtype: float
    """
    return lambda: random.uniform(11.5, 12.5)


@pytest.fixture()
def random_fan_speed():
    """
    Return a callable that returns a random fan speed (in RPMs)

    :return: a callable that returns a random fan speed
    :rtype: float
    """
    return lambda: random.uniform(4500.0, 5500.0)


class TestSubrackBaySimulator:
    """
    Contains tests of the SubrackBaySimulator.
    """

    @pytest.fixture()
    def subrack_bay(self):
        """
        Return a simulator for a subrack bay.

        :return: a simulator for a subrack bay
        :rtype:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`
        """
        return SubrackBaySimulator()

    def test_subrack_bay_on_off(self, subrack_bay):
        """
        Test that:

        * we can turn the module in the subrack bay on and off.
        * we can monitor its temperature, current, voltage and power irrespective of
          whether it is on or off.

        :param subrack_bay: a simulator for a subrack bay housing an
            electronic module
        :type subrack_bay:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`
        """
        subrack_bay.connect()

        assert subrack_bay.power_mode == PowerMode.OFF
        assert subrack_bay.temperature == SubrackBaySimulator.DEFAULT_TEMPERATURE
        assert subrack_bay.current == 0.0
        assert subrack_bay.voltage == 0.0
        assert subrack_bay.power == 0.0

        subrack_bay.on()

        assert subrack_bay.power_mode == PowerMode.ON
        assert subrack_bay.temperature == SubrackBaySimulator.DEFAULT_TEMPERATURE
        assert subrack_bay.current == SubrackBaySimulator.DEFAULT_CURRENT
        assert subrack_bay.voltage == SubrackBaySimulator.DEFAULT_VOLTAGE
        assert subrack_bay.power == SubrackBaySimulator.DEFAULT_POWER

        subrack_bay.off()

        assert subrack_bay.power_mode == PowerMode.OFF
        assert subrack_bay.temperature == SubrackBaySimulator.DEFAULT_TEMPERATURE
        assert subrack_bay.current == 0.0
        assert subrack_bay.voltage == 0.0
        assert subrack_bay.power == 0.0

    def test_subrack_bay_monitoring(
        self,
        subrack_bay,
        random_current,
        random_temperature,
        random_voltage,
    ):
        """
        Test that we can simulate changes to the current and temperature
        values reported by the bay.

        :param subrack_bay: a simulator for a subrack bay housing an
            electronic module
        :type subrack_bay:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`
        :param random_current: a random value within a reasonable range
            for a current measurement
        :type random_current: float
        :param random_voltage: a random value within a reasonable range
            for a voltage measurement
        :type random_voltage: float
        :param random_temperature: a random value within a reasonable
            range for a temperature measurement
        :type random_temperature: float
        """
        subrack_bay.connect()

        assert subrack_bay.power_mode == PowerMode.OFF
        assert subrack_bay.temperature == SubrackBaySimulator.DEFAULT_TEMPERATURE
        assert subrack_bay.current == 0.0
        assert subrack_bay.voltage == 0.0
        assert subrack_bay.power == 0.0

        temperature = random_temperature()
        subrack_bay.simulate_temperature(temperature)
        assert subrack_bay.temperature == temperature

        current = random_current()
        subrack_bay.simulate_current(current)
        assert subrack_bay.current == 0.0

        voltage = random_voltage()
        subrack_bay.simulate_voltage(voltage)
        assert subrack_bay.voltage == 0.0

        assert subrack_bay.power == 0.0

        subrack_bay.on()
        assert subrack_bay.temperature == temperature
        assert subrack_bay.current == current
        assert subrack_bay.voltage == voltage
        assert subrack_bay.power == current * voltage


@pytest.fixture()
def subrack_bays(random_temperature, random_current, random_voltage):
    """
    Return a list of subrack bay simulators for management by a subrack
    management board simulator.

    :param random_temperature: a random value within a reasonable
        range for a temperature measurement
    :type random_temperature: float
    :param random_current: a random value within a reasonable range
        for a current measurement
    :type random_current: float
    :param random_voltage: a random value within a reasonable range
        for a voltage measurement
    :type random_voltage: float

    :return: a list of subrack bay simulators
    :rtype:
        list of :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`
    """
    return [
        SubrackBaySimulator(
            temperature=random_temperature(),
            current=random_current(),
            voltage=random_voltage(),
        )
        for bay in range(4)
    ]


class TestSubrackBoardSimulator:
    """
    Contains tests of the SubrackBoardSimulator.
    """

    @pytest.fixture()
    def subrack_board(self, subrack_bays):
        """
        Return a simulator for a subrack management board.

        :param subrack_bays: list of subrack bay simulators for
            management by this subrack management board simulator
        :type subrack_bays: list of
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`

        :return: a simulator for a subrack management board
        :rtype:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """
        return SubrackBoardSimulator(_bays=subrack_bays)

    def test_subrack_on_off(self, subrack_board):
        """
        Test that we can change the subrack power mode, and that when
        on, we can read attributes, and that when off or standby, we
        can't.

        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """

        def assert_off_behaviour():
            """
            Helper function to assert the behaviour expected when this
            hardware manager is turned off.
            """
            assert subrack_board.power_mode == PowerMode.OFF
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.backplane_temperatures
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.board_temperatures
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.board_current
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.subrack_fan_speeds
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.power_supply_fan_speeds
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.power_supply_currents
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.power_supply_voltages
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = subrack_board.power_supply_powers

            assert subrack_board.are_tpms_on() is None
            for tpm_id in range(1, subrack_board.tpm_count + 1):
                assert subrack_board.is_tpm_on(tpm_id) is None

        def assert_on_behaviour():
            """
            Helper function to assert the behaviour expected when this
            hardware manager is turned on.
            """
            assert subrack_board.power_mode == PowerMode.ON
            assert (
                subrack_board.backplane_temperatures
                == SubrackBoardSimulator.DEFAULT_BACKPLANE_TEMPERATURE
            )
            assert (
                subrack_board.board_temperatures
                == SubrackBoardSimulator.DEFAULT_BOARD_TEMPERATURE
            )
            assert (
                subrack_board.board_current
                == SubrackBoardSimulator.DEFAULT_BOARD_CURRENT
            )
            assert (
                subrack_board.subrack_fan_speeds
                == SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_SPEED
            )
            assert (
                subrack_board.power_supply_fan_speeds
                == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEED
            )
            assert (
                subrack_board.power_supply_currents
                == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_CURRENT
            )
            assert (
                subrack_board.power_supply_voltages
                == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE
            )
            assert (
                subrack_board.power_supply_powers
                == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_POWER
            )

            are_tpms_on = subrack_board.are_tpms_on()
            assert not any(are_tpms_on)
            assert len(are_tpms_on) == subrack_board.tpm_count

            for tpm_id in range(1, subrack_board.tpm_count + 1):
                assert not subrack_board.is_tpm_on(tpm_id)

        subrack_board.connect()
        assert_off_behaviour()
        subrack_board.on()
        assert_on_behaviour()
        subrack_board.off()
        assert_off_behaviour()

    def test_tpm_on_off(self, subrack_board):
        """
        Test that:

        * when the subrack is on, we can turn TPMs on and off
        * when we turn the subrack off, the TPMs get turned off too

        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """
        subrack_board.connect()
        subrack_board.on()
        for tpm_id in range(1, subrack_board.tpm_count + 1):
            assert not subrack_board.is_tpm_on(tpm_id)

            subrack_board.turn_on_tpm(tpm_id)
            assert subrack_board.is_tpm_on(tpm_id)

        subrack_board.off()

        subrack_board.on()
        for tpm_id in range(1, subrack_board.tpm_count + 1):
            assert not subrack_board.is_tpm_on(tpm_id)

    def test_tpms_on_off(self, subrack_board):
        """
        Test that we can turn all the TPMs on and off at once.

        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """

        def assert_tpms_on(is_on):
            """
            Helper method that asserts TPMs to be either all off or all
            on, depending on the argument.

            :param is_on: whether to assert that all TPMs are on or off
            :type is_on: bool
            """
            for tpm_id in range(1, subrack_board.tpm_count + 1):
                assert subrack_board.is_tpm_on(tpm_id) == is_on

        subrack_board.connect()
        subrack_board.on()
        assert_tpms_on(False)
        subrack_board.turn_on_tpms()
        assert_tpms_on(True)
        subrack_board.turn_off_tpms()
        assert_tpms_on(False)
        subrack_board.turn_on_tpm(1)
        subrack_board.turn_on_tpms()
        assert_tpms_on(True)
        subrack_board.turn_off_tpm(2)
        subrack_board.turn_off_tpms()
        assert_tpms_on(False)

    def test_monitoring(
        self,
        subrack_bays,
        subrack_board,
        random_current,
        random_temperature,
        random_fan_speed,
        random_voltage,
    ):
        """
        Test that the monitoring attributes of this simulator return
        expected values.

        :param subrack_bays: list of subrack bay simulators for
            management by this subrack management board simulator
        :type subrack_bays: list of
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`
        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        :param random_temperature: a random value within a reasonable
            range for a temperature measurement
        :type random_temperature: float
        :param random_current: a random value within a reasonable range
            for a current measurement
        :type random_current: float
        :param random_fan_speed: a random value within a reasonable
            range for a fan speed measurement
        :type random_fan_speed: float
        :param random_voltage: a random value within a reasonable
            range for a voltage measurement
        :type random_voltage: float
        """
        subrack_board.connect()
        subrack_board.on()

        assert (
            subrack_board.backplane_temperatures
            == SubrackBoardSimulator.DEFAULT_BACKPLANE_TEMPERATURE
        )
        assert (
            subrack_board.board_temperatures
            == SubrackBoardSimulator.DEFAULT_BOARD_TEMPERATURE
        )
        assert (
            subrack_board.board_current == SubrackBoardSimulator.DEFAULT_BOARD_CURRENT
        )
        assert (
            subrack_board.subrack_fan_speeds
            == SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_SPEED
        )
        assert (
            subrack_board.power_supply_fan_speeds
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEED
        )
        assert (
            subrack_board.power_supply_currents
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_CURRENT
        )
        assert (
            subrack_board.power_supply_voltages
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE
        )
        assert (
            subrack_board.power_supply_powers
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_POWER
        )

        backplane_temperatures = [random_temperature() for i in range(2)]
        board_temperatures = [random_temperature() for i in range(2)]
        board_current = random_current()
        subrack_fan_speeds = [random_fan_speed() for i in range(4)]
        power_supply_fan_speeds = [random_fan_speed() for i in range(2)]
        power_supply_currents = [random_current() for i in range(2)]
        power_supply_voltages = [random_voltage() for i in range(2)]
        power_supply_powers = [
            current * voltage
            for (current, voltage) in zip(power_supply_currents, power_supply_voltages)
        ]

        subrack_board.simulate_backplane_temperatures(backplane_temperatures)
        subrack_board.simulate_board_temperatures(board_temperatures)
        subrack_board.simulate_board_current(board_current)
        subrack_board.simulate_subrack_fan_speeds(subrack_fan_speeds)
        subrack_board.simulate_power_supply_fan_speeds(power_supply_fan_speeds)
        subrack_board.simulate_power_supply_currents(power_supply_currents)
        subrack_board.simulate_power_supply_voltages(power_supply_voltages)
        subrack_board.simulate_power_supply_powers(power_supply_powers)

        assert subrack_board.backplane_temperatures == backplane_temperatures
        assert subrack_board.board_temperatures == board_temperatures
        assert subrack_board.board_current == board_current
        assert subrack_board.subrack_fan_speeds == subrack_fan_speeds
        assert subrack_board.power_supply_fan_speeds == power_supply_fan_speeds
        assert subrack_board.power_supply_currents == pytest.approx(
            power_supply_currents
        )
        assert subrack_board.power_supply_voltages == pytest.approx(
            power_supply_voltages
        )
        assert subrack_board.power_supply_powers == power_supply_powers

        assert subrack_board.tpm_temperatures == [
            bay.temperature for bay in subrack_bays
        ]
        assert subrack_board.tpm_currents == [0.0 for bay in subrack_bays]
        assert subrack_board.tpm_voltages == [0.0 for bay in subrack_bays]
        assert subrack_board.tpm_powers == [0.0 for bay in subrack_bays]

        subrack_board.turn_on_tpms()

        assert subrack_board.tpm_temperatures == [
            bay.temperature for bay in subrack_bays
        ]
        assert subrack_board.tpm_currents == [bay.current for bay in subrack_bays]
        assert subrack_board.tpm_voltages == [bay.voltage for bay in subrack_bays]
        assert subrack_board.tpm_powers == [bay.power for bay in subrack_bays]

        bay_temperatures = [
            random_temperature() for i in range(subrack_board.tpm_count)
        ]
        bay_currents = [random_current() for i in range(subrack_board.tpm_count)]
        bay_voltages = [random_voltage() for i in range(subrack_board.tpm_count)]
        bay_powers = [
            bay_currents[i] * bay_voltages[i] for i in range(subrack_board.tpm_count)
        ]

        subrack_board.simulate_tpm_temperatures(bay_temperatures)
        subrack_board.simulate_tpm_currents(bay_currents)
        subrack_board.simulate_tpm_voltages(bay_voltages)
        subrack_board.simulate_tpm_powers(bay_powers)

        assert subrack_board.tpm_temperatures == bay_temperatures
        assert subrack_board.tpm_currents == bay_currents
        assert subrack_board.tpm_voltages == bay_voltages
        assert subrack_board.tpm_powers == bay_powers

        subrack_board.turn_off_tpms()

        assert subrack_board.tpm_temperatures == bay_temperatures
        assert subrack_board.tpm_currents == [0.0 for bay in subrack_bays]
        assert subrack_board.tpm_voltages == [0.0 for bay in subrack_bays]
        assert subrack_board.tpm_powers == [0.0 for bay in subrack_bays]


class TestSubrackHardwareManager:
    """
    Contains tests of the SubrackHardwareManager.
    """

    @pytest.fixture()
    def subrack_board(
        self,
        random_temperature,
        random_current,
        random_fan_speed,
        random_voltage,
        subrack_bays,
    ):
        """
        Return a simulator for a subrack management board.

        :param random_temperature: a random value within a reasonable
            range for a temperature measurement
        :type random_temperature: float
        :param random_current: a random value within a reasonable range
            for a current measurement
        :type random_current: float
        :param random_fan_speed: a random value within a reasonable
            range for a fan speed measurement
        :type random_fan_speed: float
        :param random_voltage: a random value within a reasonable
            range for a voltage measurement
        :type random_voltage: float
        :param subrack_bays: list of subrack bay simulators for
            management by this subrack management board simulator
        :type subrack_bays: list of
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBaySimulator`

        :return: a simulator for a subrack management board
        :rtype:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """
        return SubrackBoardSimulator(
            backplane_temperatures=[random_temperature() for i in range(2)],
            board_temperatures=[random_temperature() for i in range(2)],
            board_current=random_current(),
            subrack_fan_speeds=[random_fan_speed() for i in range(4)],
            power_supply_fan_speeds=[random_fan_speed() for i in range(2)],
            power_supply_currents=[random_current() for i in range(2)],
            power_supply_voltages=[random_voltage() for i in range(2)],
            _bays=subrack_bays,
        )

    @pytest.fixture()
    def hardware_factory(self, subrack_board):
        """
        Return a subrack hardware factory.

        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`

        :return: a subrack hardware factory. This would normally be a
            :py:class:`ska_low_mccs.subrack.subrack_device.SubrackHardwareFactory`,
            but for testing purposes we want to be able to access the
            underlying simulator, so we return a bespoke
            :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
            that uses the simulator provided via the `subrack_board`
            fixture.
        :rtype: :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
        """
        return SimulableHardwareFactory(True, _static_simulator=subrack_board)

    @pytest.fixture()
    def hardware_manager(self, hardware_factory, mock_callback):
        """
        Return a manager for Subrack hardware.

        :param hardware_factory: a factory that returns a subrack
            hardware simulator/driver
        :type hardware_factory:
            :py:class:`ska_low_mccs.hardware.simulable_hardware.SimulableHardwareFactory`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`

        :return: a manager for Subrack hardware
        :rtype:
            :py:class:`~ska_low_mccs.subrack.subrack_device.SubrackHardwareManager`
        """
        return SubrackHardwareManager(
            SimulationMode.TRUE, mock_callback, _factory=hardware_factory
        )

    def test_init_simulation_mode(self, mock_callback):
        """
        Test that we can't create an hardware manager that isn't in
        simulation mode.

        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            _ = SubrackHardwareManager(SimulationMode.FALSE, mock_callback)

    def test_simulation_mode(self, hardware_manager):
        """
        Test that we can't take the hardware manager out of simulation
        mode.

        :param hardware_manager: a hardware manager for subrack hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.subrack.subrack_device.SubrackHardwareManager`
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            hardware_manager.simulation_mode = SimulationMode.FALSE

    def test_on_off(self, subrack_board, hardware_manager, mocker):
        """
        Test that:

        * we can use the hardware manager to turn the hardware
          on and off
        * when on, we can monitor the subrack and its bays.
        * the hardware manager receives updated values, and re-
          evaluates device health, each time it polls the hardware.

        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        :param hardware_manager: a hardware manager for subrack hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.subrack.subrack_device.SubrackHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: :py:class:`pytest_mock.mocker`
        """

        def assert_off_behaviour():
            """
            Helper function to assert the behaviour expected when this
            hardware manager is turned off.
            """
            assert hardware_manager.power_mode == PowerMode.OFF
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.backplane_temperatures
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.board_temperatures
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.board_current
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.subrack_fan_speeds
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.power_supply_fan_speeds
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.power_supply_currents
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.power_supply_voltages
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.power_supply_powers
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.tpm_temperatures
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.tpm_currents
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.tpm_powers
            with pytest.raises(ValueError, match="Subrack is not ON."):
                _ = hardware_manager.tpm_voltages
            assert hardware_manager.health == HealthState.OK

        def assert_on_behaviour():
            """
            Helper function to assert the behaviour expected when this
            hardware manager is turned on.
            """
            assert hardware_manager.power_mode == PowerMode.ON
            assert hardware_manager.health == HealthState.OK

            assert (
                hardware_manager.backplane_temperatures
                == subrack_board.backplane_temperatures
            )
            assert (
                hardware_manager.board_temperatures == subrack_board.board_temperatures
            )
            assert hardware_manager.board_current == subrack_board.board_current
            assert (
                hardware_manager.subrack_fan_speeds == subrack_board.subrack_fan_speeds
            )
            assert (
                hardware_manager.power_supply_fan_speeds
                == subrack_board.power_supply_fan_speeds
            )
            assert (
                hardware_manager.power_supply_currents
                == subrack_board.power_supply_currents
            )
            assert (
                hardware_manager.power_supply_voltages
                == subrack_board.power_supply_voltages
            )
            assert (
                hardware_manager.power_supply_powers
                == subrack_board.power_supply_powers
            )
            assert hardware_manager.tpm_temperatures == subrack_board.tpm_temperatures
            assert hardware_manager.tpm_currents == subrack_board.tpm_currents
            assert hardware_manager.tpm_powers == subrack_board.tpm_powers
            assert hardware_manager.tpm_voltages == subrack_board.tpm_voltages

        hardware_manager.poll()
        assert_off_behaviour()

        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert_on_behaviour()
        mock_health_callback.assert_not_called()

        hardware_manager.off()
        assert_off_behaviour()
        mock_health_callback.assert_not_called()

    def test_tpm_on_off(self, hardware_manager, subrack_board):
        """
        Test that:

        * when the subrack is on, we can turn TPMs on and off
        * when we turn the subrack off, the TPMs get turned off too

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        :param subrack_board: a simulator for a subrack management board
        :type subrack_board:
            :py:class:`~ska_low_mccs.subrack.subrack_simulator.SubrackBoardSimulator`
        """
        hardware_manager.poll()
        hardware_manager.on()
        for tpm_id in range(1, hardware_manager.tpm_count + 1):
            assert not hardware_manager.is_tpm_on(tpm_id)

            hardware_manager.turn_on_tpm(tpm_id)
            assert hardware_manager.is_tpm_on(tpm_id)
            assert subrack_board.is_tpm_on(tpm_id)

        hardware_manager.off()

        hardware_manager.on()
        for tpm_id in range(1, hardware_manager.tpm_count + 1):
            assert not hardware_manager.is_tpm_on(tpm_id)

    def test_tpms_on_off(self, hardware_manager):
        """
        Test that we can turn all the TPMs on and off at once.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        """

        def assert_tpms_on(is_on):
            """
            Helper method that asserts TPMs to be either all off or all
            on, depending on the argument.

            :param is_on: whether to assert that all TPMs are on or off
            :type is_on: bool
            """
            for tpm_id in range(1, hardware_manager.tpm_count + 1):
                assert hardware_manager.is_tpm_on(tpm_id) == is_on

        hardware_manager.poll()
        hardware_manager.on()
        assert_tpms_on(False)
        hardware_manager.turn_on_tpms()
        assert_tpms_on(True)
        hardware_manager.turn_off_tpms()
        assert_tpms_on(False)
        hardware_manager.turn_on_tpm(1)
        hardware_manager.turn_on_tpms()
        assert_tpms_on(True)
        hardware_manager.turn_off_tpm(2)
        hardware_manager.turn_off_tpms()
        assert_tpms_on(False)


class TestMccsSubrack(object):
    """
    Test class for MccsSubrack tests.
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        assert device_under_test.state() == DevState.DISABLE
        assert device_under_test.status() == "The device is in DISABLE state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.testMode == TestMode.TEST

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`
        """
        assert device_under_test.healthState == HealthState.OK

        _ = device_under_test.subscribe_event(
            "healthState", EventType.CHANGE_EVENT, mock_callback
        )
        mock_callback.assert_called_once()

        event_data = mock_callback.call_args[0][0].attr_value
        assert event_data.name == "healthState"
        assert event_data.value == HealthState.OK
        assert event_data.quality == AttrQuality.ATTR_VALID

    def test_attributes(self, device_under_test):
        """
        Test of attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        device_under_test.On()
        assert (
            list(device_under_test.backplaneTemperatures)
            == SubrackBoardSimulator.DEFAULT_BACKPLANE_TEMPERATURE
        )
        assert (
            list(device_under_test.boardTemperatures)
            == SubrackBoardSimulator.DEFAULT_BOARD_TEMPERATURE
        )
        assert (
            device_under_test.boardCurrent
            == SubrackBoardSimulator.DEFAULT_BOARD_CURRENT
        )
        assert (
            list(device_under_test.subrackFanSpeeds)
            == SubrackBoardSimulator.DEFAULT_SUBRACK_FAN_SPEED
        )
        assert (
            list(device_under_test.powerSupplyFanSpeeds)
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_FAN_SPEED
        )
        assert device_under_test.powerSupplyCurrents == pytest.approx(
            SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_CURRENT
        )
        assert device_under_test.powerSupplyVoltages == pytest.approx(
            SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_VOLTAGE
        )

        assert (
            list(device_under_test.powerSupplyPowers)
            == SubrackBoardSimulator.DEFAULT_POWER_SUPPLY_POWER
        )
        assert (
            list(device_under_test.tpmTemperatures)
            == [SubrackBaySimulator.DEFAULT_TEMPERATURE] * 4
        )
        assert list(device_under_test.tpmCurrents) == [0.0, 0.0, 0.0, 0.0]
        assert list(device_under_test.tpmPowers) == [0.0, 0.0, 0.0, 0.0]
        assert list(device_under_test.tpmVoltages) == [0.0, 0.0, 0.0, 0.0]

    def test_PowerOnTpm(self, device_under_test):
        """
        Test for PowerOnTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        _ = device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on successful"

        [[result_code], [message]] = device_under_test.PowerOnTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-on is redundant"

    def test_PowerOffTpm(self, device_under_test):
        """
        Test for PowerOffTpm.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        _ = device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off is redundant"

        _ = device_under_test.PowerOnTpm(1)

        [[result_code], [message]] = device_under_test.PowerOffTpm(1)
        assert result_code == ResultCode.OK
        assert message == "Subrack TPM 1 power-off successful"
