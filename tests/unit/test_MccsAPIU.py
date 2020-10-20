###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsStationBeam project
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

from tango import DevFailed, DevState

from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.base.commands import ResultCode
from ska.low.mccs.apiu import (
    AntennaHardwareSimulator,
    APIUHardwareManager,
    APIUHardwareSimulator,
)

device_to_load = {
    "path": "charts/ska-low-mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "apiu",
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
        assert not antenna_hardware_simulator.is_on
        assert antenna_hardware_simulator.voltage is None
        assert antenna_hardware_simulator.current is None
        assert antenna_hardware_simulator.temperature is None

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
        assert antenna_hardware_simulator.voltage is None
        assert antenna_hardware_simulator.current is None
        assert antenna_hardware_simulator.temperature is None


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
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert apiu_simulator.is_antenna_on(antenna_id + 1) is None

        assert apiu_simulator.voltage is None
        assert apiu_simulator.current is None
        assert apiu_simulator.temperature is None

        apiu_simulator.on()
        assert apiu_simulator.is_on
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)
        assert apiu_simulator.voltage == APIUHardwareSimulator.VOLTAGE
        assert apiu_simulator.current == APIUHardwareSimulator.CURRENT
        assert apiu_simulator.temperature == APIUHardwareSimulator.TEMPERATURE

        apiu_simulator.off()
        assert not apiu_simulator.is_on
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert apiu_simulator.is_antenna_on(antenna_id + 1) is None
        assert apiu_simulator.voltage is None
        assert apiu_simulator.current is None
        assert apiu_simulator.temperature is None

    def test_antenna_on_off(self, apiu_simulator):
        """
        Test that

        * when the APIU is off, the antennas are off, and we can't turn
          them on.
        * when the APIU is on, we can turn antennas on and off

        :param apiu_simulator: a simulator for APIU hardware
        :type apiu_simulator: :py:class:`~ska.low.mccs.apiu.APIUHardwareSimulator`
        """
        assert not apiu_simulator.is_on
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert apiu_simulator.is_antenna_on(antenna_id + 1) is None
            apiu_simulator.turn_on_antenna(antenna_id + 1)
            assert apiu_simulator.is_antenna_on(antenna_id + 1) is None

        apiu_simulator.on()
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not apiu_simulator.is_antenna_on(antenna_id + 1)
            apiu_simulator.turn_on_antenna(antenna_id + 1)
            assert apiu_simulator.is_antenna_on(antenna_id + 1)

        apiu_simulator.off()
        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert apiu_simulator.is_antenna_on(antenna_id + 1) is None


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
            NotImplementedError,
            match=(
                "APIUHardwareManager does not implement "
                "abstract _create_driver method."
            ),
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
            NotImplementedError,
            match=(
                "APIUHardwareManager does not implement "
                "abstract _create_driver method."
            ),
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

        hardware = hardware_manager._hardware

        assert not hardware_manager.is_on
        assert hardware_manager.current is None
        assert hardware_manager.voltage is None
        assert hardware_manager.temperature is None
        assert hardware_manager.humidity is None
        assert hardware_manager.health == HealthState.OK

        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        hardware._current = current
        hardware._voltage = voltage
        hardware._temperature = temperature
        hardware._humidity = humidity
        hardware_manager.poll_hardware()

        assert hardware_manager.is_on
        assert hardware_manager.current == current
        assert hardware_manager.voltage == voltage
        assert hardware_manager.temperature == temperature
        assert hardware_manager.humidity == humidity
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

        hardware_manager.off()

        assert not hardware_manager.is_on
        assert hardware_manager.current is None
        assert hardware_manager.voltage is None
        assert hardware_manager.temperature is None
        assert hardware_manager.humidity is None
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

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
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when APIU is off"
            ):
                _ = hardware_manager.is_antenna_on(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when APIU is off"
            ):
                _ = hardware_manager.get_antenna_current(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when APIU is off"
            ):
                _ = hardware_manager.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when APIU is off"
            ):
                _ = hardware_manager.get_antenna_temperature(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot act on antenna when APIU is off"
            ):
                _ = hardware_manager.turn_off_antenna(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot act on antenna when APIU is off"
            ):
                _ = hardware_manager.turn_on_antenna(antenna_id + 1)

        hardware_manager.on()

        for antenna_id in range(APIUHardwareSimulator.NUMBER_OF_ANTENNAS):
            assert not hardware_manager.is_antenna_on(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when antenna is off"
            ):
                _ = hardware_manager.get_antenna_current(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when antenna is off"
            ):
                _ = hardware_manager.get_antenna_voltage(antenna_id + 1)
            with pytest.raises(
                ValueError, match="Cannot monitor antenna when antenna is off"
            ):
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

        print(f"Init state is {device_under_test.state()}")
        assert device_under_test.state() == DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.TRUE
        assert device_under_test.testMode == TestMode.NONE

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

        # print(f'logicalAntennaId -> {repr(device_under_test.logicalAntennaId)}')
        # assert device_under_test.logicalAntennaId == [0]

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
        assert message == "APIU successfully powered up"

        [[result_code], [message]] = device_under_test.PowerUp()
        assert result_code == ResultCode.OK
        assert message == "APIU was already powered up"

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
        assert message == "APIU was already powered down"

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDown()
        assert result_code == ResultCode.OK
        assert message == "APIU successfully powered down"

    def test_PowerUpAntenna(self, device_under_test):
        """
        Test for PowerUpAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(DevFailed, match="Cannot act on antenna when APIU is off"):
            _ = device_under_test.PowerUpAntenna(0)

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerUpAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "Antenna 0 successfully powered up"

        [[result_code], [message]] = device_under_test.PowerUpAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "Antenna 0 was already powered up"

    def test_PowerDownAntenna(self, device_under_test):
        """
        Test for PowerDownAntenna

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """

        with pytest.raises(DevFailed, match="Cannot act on antenna when APIU is off"):
            _ = device_under_test.PowerUpAntenna(0)

        _ = device_under_test.PowerUp()

        [[result_code], [message]] = device_under_test.PowerDownAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "Antenna 0 was already powered down"

        _ = device_under_test.PowerUpAntenna(0)

        [[result_code], [message]] = device_under_test.PowerDownAntenna(0)
        assert result_code == ResultCode.OK
        assert message == "Antenna 0 successfully powered down"
