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
This module contains the tests for MccsAPIU.
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
from ska_low_mccs.apiu.apiu_device import APIUHardwareManager
from ska_low_mccs.apiu.apiu_simulator import AntennaHardwareSimulator, APIUSimulator
from ska_low_mccs.hardware import PowerMode


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
        "device": "apiu_001",
        "proxy": MccsDeviceProxy,
    }


class TestAntennaHardwareSimulator:
    """
    Contains tests of the AntennaHardwareSimulator.
    """

    @pytest.fixture()
    def antenna_hardware_simulator(self):
        """
        Return a simulator for antenna hardware.

        :return: a simulator for antenna hardware
        :rtype:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
        """
        return AntennaHardwareSimulator()

    def test_off_on(self, antenna_hardware_simulator):
        """
        Test that we can turn the antenna hardware off and on.

        :param antenna_hardware_simulator: a simulator for antenna
            hardware
        :type antenna_hardware_simulator:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
        """
        assert antenna_hardware_simulator.connect()
        assert antenna_hardware_simulator.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.voltage
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.current
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.temperature

        antenna_hardware_simulator.on()
        assert antenna_hardware_simulator.power_mode == PowerMode.ON
        assert antenna_hardware_simulator.voltage == AntennaHardwareSimulator.VOLTAGE
        assert antenna_hardware_simulator.current == AntennaHardwareSimulator.CURRENT
        assert (
            antenna_hardware_simulator.temperature
            == AntennaHardwareSimulator.TEMPERATURE
        )

        antenna_hardware_simulator.off()
        assert antenna_hardware_simulator.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.voltage
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.current
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = antenna_hardware_simulator.temperature


class TestAPIUSimulator:
    """
    Contains tests of the APIUSimulator.
    """

    @pytest.fixture()
    def apiu_simulator(self):
        """
        Return a simulator for APIU hardware.

        :return: a simulator for APIU hardware
        :rtype:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.APIUSimulator`
        """
        return APIUSimulator(16)

    def test_apiu_on_off(self, apiu_simulator):
        """
        Test that we can turn the APIU on and off, that when on, we can
        read APIU attributes, and that turning the APIU on doesn't mean
        the antennas get turned on.

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.APIUSimulator`
        """
        assert apiu_simulator.connect()
        assert apiu_simulator.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.voltage
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.current
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.temperature

        assert apiu_simulator.are_antennas_on() is None
        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            assert apiu_simulator.is_antenna_on(antenna_id) is None

        apiu_simulator.on()
        assert apiu_simulator.power_mode == PowerMode.ON
        assert apiu_simulator.voltage == APIUSimulator.VOLTAGE
        assert apiu_simulator.current == APIUSimulator.CURRENT
        assert apiu_simulator.temperature == APIUSimulator.TEMPERATURE

        are_antennas_on = apiu_simulator.are_antennas_on()
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == apiu_simulator.antenna_count

        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            assert not apiu_simulator.is_antenna_on(antenna_id)

        apiu_simulator.off()
        assert apiu_simulator.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.voltage
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.current
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = apiu_simulator.temperature

        assert apiu_simulator.are_antennas_on() is None
        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            assert apiu_simulator.is_antenna_on(antenna_id) is None

    def test_antenna_on_off(self, apiu_simulator):
        """
        Test that:

        * when the APIU is on, we can turn antennas on and off
        * when the APIU is on, but an antenna is off, we can't read
          antenna attributes
        * when we turn the APIU off, the antennas get turned off too

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.APIUSimulator`
        """
        assert apiu_simulator.connect()
        apiu_simulator.on()
        are_antennas_on = apiu_simulator.are_antennas_on()
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == apiu_simulator.antenna_count

        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            assert not apiu_simulator.is_antenna_on(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_current(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_voltage(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_temperature(antenna_id)

            apiu_simulator.turn_on_antenna(antenna_id)

            # After turning on the antenna, it should be on, and all others should be
            # off.
            for _id in range(1, apiu_simulator.antenna_count + 1):
                assert apiu_simulator.is_antenna_on(_id) == (_id == antenna_id)

            assert (
                apiu_simulator.get_antenna_current(antenna_id)
                == AntennaHardwareSimulator.CURRENT
            )
            assert (
                apiu_simulator.get_antenna_voltage(antenna_id)
                == AntennaHardwareSimulator.VOLTAGE
            )
            assert (
                apiu_simulator.get_antenna_temperature(antenna_id)
                == AntennaHardwareSimulator.TEMPERATURE
            )

            apiu_simulator.turn_off_antenna(antenna_id)
            are_antennas_on = apiu_simulator.are_antennas_on()
            assert not any(are_antennas_on)
            assert len(are_antennas_on) == apiu_simulator.antenna_count

            assert not apiu_simulator.is_antenna_on(antenna_id)

        apiu_simulator.off()
        assert apiu_simulator.are_antennas_on() is None
        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            with pytest.raises(ValueError, match="APIU hardware is not ON."):
                apiu_simulator.turn_on_antenna(antenna_id)

        apiu_simulator.on()
        are_antennas_on = apiu_simulator.are_antennas_on()
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == apiu_simulator.antenna_count

        for antenna_id in range(1, apiu_simulator.antenna_count + 1):
            assert not apiu_simulator.is_antenna_on(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_current(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_voltage(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = apiu_simulator.get_antenna_temperature(antenna_id)

    def test_antennas_on_off(self, apiu_simulator):
        """
        Test that we can turn all the antennas on/off at once.

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator:
            :py:class:`~ska_low_mccs.apiu.apiu_simulator.APIUSimulator`
        """

        def check_all_antennas_on_off(mode):
            """
            Helper function to check that all antennas are on, or that
            all antennas are off, depending on the mode.

            :param mode: whether all antennas are expected to be on or
                off. If true, all antennas are expected to be on. If
                false, all antennas are expected to be off.
            :type mode: bool
            """
            are_antennas_on = apiu_simulator.are_antennas_on()
            if mode:
                assert all(are_antennas_on)
            else:
                assert not any(are_antennas_on)
            assert len(are_antennas_on) == apiu_simulator.antenna_count

            for antenna_id in range(1, apiu_simulator.antenna_count + 1):
                assert apiu_simulator.is_antenna_on(antenna_id) == mode

        assert apiu_simulator.connect()
        apiu_simulator.on()

        # check all antennas are off
        check_all_antennas_on_off(False)

        # now turn them all off at once (nothing to do)
        apiu_simulator.turn_off_antennas()

        # check all antennas are off
        check_all_antennas_on_off(False)

        # now turn them all on at once
        apiu_simulator.turn_on_antennas()

        # check all antennas are on
        check_all_antennas_on_off(True)

        # now turn them all on at once (nothing to do)
        apiu_simulator.turn_on_antennas()

        # check all antennas are on
        check_all_antennas_on_off(True)

        # now turn them all off at once
        apiu_simulator.turn_off_antennas()

        # check all antennas are off
        check_all_antennas_on_off(False)


class TestAPIUHardwareManager:
    """
    Contains tests of the APIUHardwareManager.
    """

    @pytest.fixture()
    def hardware_manager(self, mock_callback):
        """
        Return a manager for APIU hardware.

        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.mock.Mock`

        :return: a manager for APIU hardware
        :rtype:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        """
        return APIUHardwareManager(SimulationMode.TRUE, 2, mock_callback)

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
            _ = APIUHardwareManager(SimulationMode.FALSE, 2, mock_callback)

    def test_simulation_mode(self, hardware_manager):
        """
        Test that we can't take the hardware manager out of simulation
        mode.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            hardware_manager.simulation_mode = SimulationMode.FALSE

    def test_on_off(self, hardware_manager, mocker):
        """
        Test that the hardware manager receives updated values, and re-
        evaluates device health, each time it polls the hardware.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: :py:class:`pytest_mock.mocker`
        """
        voltage = 3.5
        temperature = 120
        current = 4.7
        humidity = 23.4

        hardware = hardware_manager._factory.hardware

        hardware_manager.poll()
        assert hardware_manager.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.current
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.humidity
        assert hardware_manager.health == HealthState.OK

        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert hardware_manager.power_mode == PowerMode.ON
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

        hardware._current = current
        assert hardware_manager.current == current

        hardware._voltage = voltage
        assert hardware_manager.voltage == voltage

        hardware._temperature = temperature
        assert hardware_manager.temperature == temperature

        hardware._humidity = humidity
        assert hardware_manager.humidity == humidity

        hardware_manager.off()
        assert hardware_manager.power_mode == PowerMode.OFF
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.current
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="APIU hardware is not ON."):
            _ = hardware_manager.humidity

    def test_antenna_on_off(self, hardware_manager):
        """
        Test that the hardware manager supports monitoring antennas and
        turning them on and off.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        """
        hardware_manager.poll()
        assert hardware_manager.power_mode == PowerMode.OFF

        are_antennas_on = hardware_manager.are_antennas_on()
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == hardware_manager.antenna_count

        for antenna_id in range(1, hardware_manager.antenna_count + 1):
            assert not hardware_manager.is_antenna_on(antenna_id)
            with pytest.raises(ValueError, match="APIU hardware is not ON."):
                _ = hardware_manager.get_antenna_current(antenna_id)
            with pytest.raises(ValueError, match="APIU hardware is not ON."):
                _ = hardware_manager.get_antenna_voltage(antenna_id)
            with pytest.raises(ValueError, match="APIU hardware is not ON."):
                _ = hardware_manager.get_antenna_temperature(antenna_id)
            assert hardware_manager.turn_off_antenna(antenna_id) is None
            with pytest.raises(ValueError, match="APIU hardware is not ON."):
                _ = hardware_manager.turn_on_antenna(antenna_id)

        hardware_manager.on()

        are_antennas_on = hardware_manager.are_antennas_on()
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == hardware_manager.antenna_count

        for antenna_id in range(1, hardware_manager.antenna_count + 1):
            assert not hardware_manager.is_antenna_on(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = hardware_manager.get_antenna_current(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = hardware_manager.get_antenna_voltage(antenna_id)
            with pytest.raises(ValueError, match="Antenna hardware is not ON."):
                _ = hardware_manager.get_antenna_temperature(antenna_id)

            assert hardware_manager.turn_off_antenna(antenna_id) is None
            assert hardware_manager.turn_on_antenna(antenna_id)

            # After turning on the antenna, it should be on, and all others should be
            # off.
            assert hardware_manager.are_antennas_on() == [
                antenna_id == i for i in range(1, hardware_manager.antenna_count + 1)
            ]
            for _id in range(1, hardware_manager.antenna_count + 1):
                assert hardware_manager.is_antenna_on(_id) == (_id == antenna_id)

            assert (
                hardware_manager.get_antenna_current(antenna_id)
                == AntennaHardwareSimulator.CURRENT
            )
            assert (
                hardware_manager.get_antenna_voltage(antenna_id)
                == AntennaHardwareSimulator.VOLTAGE
            )
            assert (
                hardware_manager.get_antenna_temperature(antenna_id)
                == AntennaHardwareSimulator.TEMPERATURE
            )

            assert hardware_manager.turn_on_antenna(antenna_id) is None
            assert hardware_manager.turn_off_antenna(antenna_id)

            are_antennas_on = hardware_manager.are_antennas_on()
            assert not any(are_antennas_on)
            assert len(are_antennas_on) == hardware_manager.antenna_count

            assert not hardware_manager.is_antenna_on(antenna_id)

    def test_antennas_on_off(self, hardware_manager):
        """
        Test that the hardware manager supports monitoring turning all
        antennas on and off at once.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager:
            :py:class:`~ska_low_mccs.apiu.apiu_device.APIUHardwareManager`
        """

        def check_all_antennas_on_off(mode):
            """
            Helper function to check that all antennas are on, or that
            all antennas are off, depending on the mode.

            :param mode: whether all antennas are expected to be on or
                off. If true, all antennas are expected to be on. If
                false, all antennas are expected to be off.
            :type mode: bool
            """
            are_antennas_on = hardware_manager.are_antennas_on()
            if mode:
                assert all(are_antennas_on)
            else:
                assert not any(are_antennas_on)
            assert len(are_antennas_on) == hardware_manager.antenna_count

            for antenna_id in range(1, hardware_manager.antenna_count + 1):
                assert hardware_manager.is_antenna_on(antenna_id) == mode

        hardware_manager.poll()
        assert hardware_manager.power_mode == PowerMode.OFF

        hardware_manager.on()

        # check all antennas are off
        check_all_antennas_on_off(False)

        # now turn them all off at once (nothing to do)
        assert hardware_manager.turn_off_antennas() is None

        # check all antennas are off
        check_all_antennas_on_off(False)

        # now turn them all on at once
        assert hardware_manager.turn_on_antennas()

        # check all antennas are on
        check_all_antennas_on_off(True)

        # now turn them all on at once
        assert hardware_manager.turn_on_antennas() is None

        # now turn them all off at once
        assert hardware_manager.turn_off_antennas()

        # check all antennas are off
        check_all_antennas_on_off(False)

        # turn on a random antenna
        antenna_id = random.randint(1, hardware_manager.antenna_count)
        assert hardware_manager.turn_on_antenna(antenna_id)

        # now turn them all on at once (even though one is already on)
        assert hardware_manager.turn_on_antennas()

        # check all antennas are on
        check_all_antennas_on_off(True)

        # turn off a random antenna
        antenna_id = random.randint(1, hardware_manager.antenna_count)
        assert hardware_manager.turn_off_antenna(antenna_id)

        # now turn them all off at once (even though one is already off)
        assert hardware_manager.turn_off_antennas()


class TestMccsAPIU(object):
    """
    Test class for MccsAPIU tests.
    """

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/apiu/001")

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
        assert device_under_test.temperature == APIUSimulator.TEMPERATURE
        assert device_under_test.humidity == APIUSimulator.HUMIDITY
        assert device_under_test.voltage == APIUSimulator.VOLTAGE
        assert device_under_test.current == APIUSimulator.CURRENT
        assert device_under_test.isAlive
        assert device_under_test.overCurrentThreshold == 0.0
        assert device_under_test.overVoltageThreshold == 0.0
        assert device_under_test.humidityThreshold == 0.0

        device_under_test.overCurrentThreshold = 22.0
        assert device_under_test.overCurrentThreshold == 22.0
        device_under_test.overVoltageThreshold = 6.0
        assert device_under_test.overVoltageThreshold == 6.0
        device_under_test.humidityThreshold = 60.0
        assert device_under_test.humidityThreshold == 60.0

    def test_PowerUp(self, device_under_test):
        """
        Test for PowerUp.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up successful"

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up is redundant"

    def test_PowerDown(self, device_under_test):
        """
        Test for PowerDown.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        device_under_test.On()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down is redundant"

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down successful"

    def test_PowerUpAntenna(self, device_under_test):
        """
        Test for PowerUpAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        _ = device_under_test.On()

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-up successful"

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerUpAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-up is redundant"

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

    def test_PowerDownAntenna(self, device_under_test):
        """
        Test for PowerDownAntenna.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.Off()
        _ = device_under_test.On()

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-down is redundant"

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount

        _ = device_under_test.PowerUpAntenna(1)

        are_antennas_on = list(device_under_test.areAntennasOn)
        assert are_antennas_on[0]
        assert not any(are_antennas_on[1:])
        assert len(are_antennas_on) == device_under_test.antennaCount

        [[result_code], [message]] = device_under_test.PowerDownAntenna(1)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 1 power-down successful"

        are_antennas_on = device_under_test.areAntennasOn
        assert not any(are_antennas_on)
        assert len(are_antennas_on) == device_under_test.antennaCount
