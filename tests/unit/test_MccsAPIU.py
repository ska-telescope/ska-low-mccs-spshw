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
import pytest

from tango import DevFailed, DevState, AttrQuality, EventType

from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.base.commands import ResultCode
from ska.low.mccs.apiu import APIUHardwareManager
from ska.low.mccs.apiu_simulator import AntennaHardwareSimulator, APIUHardwareSimulator


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska.low.mccs",
        "device": "apiu_001",
    }


class TestAntennaHardwareSimulator:
    """
    Contains tests of the AntennaHardwareSimulator
    """

    @pytest.fixture()
    def antenna_hardware_simulator(self):
        """
        Return a simulator for antenna hardware

        :return: a simulator for antenna hardware
        :rtype: :py:class:`~ska.low.mccs.apiu.AntennaHardwareSimulator`
        """
        return AntennaHardwareSimulator()

    def test_off_on(self, antenna_hardware_simulator):
        """
        Test that we can turn the antenna hardware off and on

        :param antenna_hardware_simulator: a simulator for antenna
            hardware
        :type antenna_hardware_simulator:
            :py:class:`~ska.low.mccs.apiu.AntennaHardwareSimulator`
        """
        assert not antenna_hardware_simulator.is_on
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.voltage
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.current
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.temperature

        antenna_hardware_simulator.on()
        assert antenna_hardware_simulator.is_on
        assert antenna_hardware_simulator.voltage == AntennaHardwareSimulator.VOLTAGE
        assert antenna_hardware_simulator.current == AntennaHardwareSimulator.CURRENT
        assert (
            antenna_hardware_simulator.temperature
            == AntennaHardwareSimulator.TEMPERATURE
        )

        antenna_hardware_simulator.off()
        assert not antenna_hardware_simulator.is_on
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.voltage
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.current
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = antenna_hardware_simulator.temperature


class TestAPIUHardwareSimulator:
    """
    Contains tests of the APIUHardwareSimulator
    """

    @pytest.fixture()
    def apiu_simulator(self):
        """
        Return a simulator for APIU hardware

        :return: a simulator for APIU hardware
        :rtype: :py:class:`~ska.low.mccs.apiu.APIUHardwareSimulator`
        """
        return APIUHardwareSimulator()

    def test_apiu_on_off(self, apiu_simulator):
        """
        Test that we can turn the APIU on and off, that when on, we can
        read APIU attributes, and that turning the APIU on doesn't mean
        the antennas get turned on.

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator: :py:class:`~ska.low.mccs.apiu.APIUHardwareSimulator`
        """
        assert not apiu_simulator.is_on
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.voltage
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.current
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.temperature
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                assert apiu_simulator.is_antenna_on(antenna_id + 1) is None

        apiu_simulator.on()
        assert apiu_simulator.is_on
        assert apiu_simulator.voltage == APIUHardwareSimulator.VOLTAGE
        assert apiu_simulator.current == APIUHardwareSimulator.CURRENT
        assert apiu_simulator.temperature == APIUHardwareSimulator.TEMPERATURE
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)

        apiu_simulator.off()
        assert not apiu_simulator.is_on
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.voltage
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.current
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = apiu_simulator.temperature
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                assert apiu_simulator.is_antenna_on(antenna_id + 1) is None

    def test_antenna_on_off(self, apiu_simulator):
        """
        Test that

        * when the APIU is on, we can turn antennas on and off
        * when the APIO is on, but an antenna is off, we can't read
          antenna attributes
        * when we turn the APIU off, the antennas get turned off too

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator: :py:class:`~ska.low.mccs.apiu.APIUHardwareSimulator`
        """
        apiu_simulator.on()
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_current(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_temperature(antenna_id + 1)

            apiu_simulator.turn_on_antenna(antenna_id + 1)
            assert apiu_simulator.is_antenna_on(antenna_id + 1)

            assert (
                apiu_simulator.get_antenna_current(antenna_id + 1)
                == AntennaHardwareSimulator.CURRENT
            )
            assert (
                apiu_simulator.get_antenna_voltage(antenna_id + 1)
                == AntennaHardwareSimulator.VOLTAGE
            )
            assert (
                apiu_simulator.get_antenna_temperature(antenna_id + 1)
                == AntennaHardwareSimulator.TEMPERATURE
            )

            apiu_simulator.turn_off_antenna(antenna_id + 1)
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)

        apiu_simulator.off()
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                apiu_simulator.turn_on_antenna(antenna_id + 1)

        apiu_simulator.on()
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_current(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = apiu_simulator.get_antenna_temperature(antenna_id + 1)


class TestAPIUHardwareManager:
    """
    Contains tests of the APIUHardwareManager
    """

    @pytest.fixture()
    def hardware_manager(self):
        """
        Return a manager for APIU hardware

        :return: a manager for APIU hardware
        :rtype: :py:class:`~ska.low.mccs.apiu.APIUHardwareManager`
        """
        return APIUHardwareManager(SimulationMode.TRUE)

    def test_init_simulation_mode(self):
        """
        Test that we can't create an hardware manager that isn't in
        simulation mode
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            _ = APIUHardwareManager(SimulationMode.FALSE)

    def test_simulation_mode(self, hardware_manager):
        """
        Test that we can't take the hardware manager out of simulation
        mode

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager: :py:class:`~ska.low.mccs.apiu.APIUHardwareManager`
        """
        with pytest.raises(
            NotImplementedError, match=("._create_driver method not implemented.")
        ):
            hardware_manager.simulation_mode = SimulationMode.FALSE

    def test_on_off(self, hardware_manager, mocker):
        """
        Test that the hardware manager receives updated values,
        and re-evaluates device health, each time it polls the hardware

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager: :py:class:`~ska.low.mccs.apiu.APIUHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        voltage = 3.5
        temperature = 120
        current = 4.7
        humidity = 23.4

        hardware = hardware_manager._factory.hardware

        assert not hardware_manager.is_on
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.current
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.humidity
        assert hardware_manager.health == HealthState.OK

        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert hardware_manager.is_on
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
        assert not hardware_manager.is_on
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.current
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="APIU hardware is turned off"):
            _ = hardware_manager.humidity

    def test_antenna_on_off(self, hardware_manager, mocker):
        """
        Test that the hardware manager supports monitoring antennas and
        turning them on and off.

        :param hardware_manager: a hardware manager for APIU hardware
        :type hardware_manager: :py:class:`~ska.low.mccs.apiu.APIUHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert not hardware_manager.is_on

        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.is_antenna_on(antenna_id + 1)
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.get_antenna_current(antenna_id + 1)
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.get_antenna_temperature(antenna_id + 1)
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.turn_off_antenna(antenna_id + 1)
            with pytest.raises(ValueError, match="APIU hardware is turned off"):
                _ = hardware_manager.turn_on_antenna(antenna_id + 1)

        hardware_manager.on()

        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not hardware_manager.is_antenna_on(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = hardware_manager.get_antenna_current(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = hardware_manager.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(ValueError, match="Antenna hardware is turned off"):
                _ = hardware_manager.get_antenna_temperature(antenna_id + 1)

            assert hardware_manager.turn_off_antenna(antenna_id + 1) is None
            assert hardware_manager.turn_on_antenna(antenna_id + 1)
            assert hardware_manager.is_antenna_on(antenna_id + 1)
            assert (
                hardware_manager.get_antenna_current(antenna_id + 1)
                == AntennaHardwareSimulator.CURRENT
            )
            assert (
                hardware_manager.get_antenna_voltage(antenna_id + 1)
                == AntennaHardwareSimulator.VOLTAGE
            )
            assert (
                hardware_manager.get_antenna_temperature(antenna_id + 1)
                == AntennaHardwareSimulator.TEMPERATURE
            )

            assert hardware_manager.turn_on_antenna(antenna_id + 1) is None
            assert hardware_manager.turn_off_antenna(antenna_id + 1)
            assert not hardware_manager.is_antenna_on(antenna_id + 1)


class TestMccsAPIU(object):
    """
    Test class for MccsAPIU tests.
    """

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        assert device_under_test.state() == DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.testMode == TestMode.NONE

    def test_healthState(self, device_under_test, mocker):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
        mock_callback = mocker.Mock()
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
        Test of attributes

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.PowerUp()
        assert device_under_test.temperature == APIUHardwareSimulator.TEMPERATURE
        assert device_under_test.humidity == APIUHardwareSimulator.HUMIDITY
        assert device_under_test.voltage == APIUHardwareSimulator.VOLTAGE
        assert device_under_test.current == APIUHardwareSimulator.CURRENT
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
        Test for PowerUp

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up successful"

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU power-up is redundant"

    def test_PowerDown(self, device_under_test):
        """
        Test for PowerDown

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down is redundant"

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU power-down successful"

    def test_PowerUpAntenna(self, device_under_test):
        """
        Test for PowerUpAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(DevFailed, match="APIU hardware is turned off"):
            _ = device_under_test.PowerUpAntenna(0)

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerUpAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 0 power-up successful"

        [[result_code], [message]] = device_under_test.PowerUpAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 0 power-up is redundant"

    def test_PowerDownAntenna(self, device_under_test):
        """
        Test for PowerDownAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        with pytest.raises(DevFailed, match="APIU hardware is turned off"):
            _ = device_under_test.PowerDownAntenna(0)

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDownAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 0 power-down is redundant"

        _ = device_under_test.PowerUpAntenna(0)

        [[result_code], [message]] = device_under_test.PowerDownAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "APIU antenna 0 power-down successful"
