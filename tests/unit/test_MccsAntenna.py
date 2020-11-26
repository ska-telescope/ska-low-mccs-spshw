#########################################################################
# !/usr/bin/env python
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
This module contains the tests for the MccsAntenna.
"""
import threading

import pytest

from tango import AttrQuality, DevFailed, DevSource, EventType
from ska.base.control_model import (
    ControlMode,
    LoggingLevel,
    HealthState,
    SimulationMode,
)
from ska.base.commands import ResultCode

from ska.low.mccs.antenna import AntennaHardwareManager, MccsAntenna
from ska.low.mccs.apiu.apiu_simulator import AntennaHardwareSimulator
from ska.low.mccs.hardware import HardwareFactory


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
        "device": "antenna_000001",
    }


@pytest.fixture()
def hardware_driver():
    """
    Returns a hardware driver for antenna hardware. The antenna tango
    device is supposed to drive the APIU tango device, which drives the
    APIU hardware (driver or simulator), which drives the Antenna
    hardware (driver or simulator). But for unit testing, we bypass all
    that and drive an antenna simulator directly

    :return: an antenna hardware driver
    :rtype:
        :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
    """
    return AntennaHardwareSimulator()


@pytest.fixture()
def hardware_factory(hardware_driver):
    """
    Return a hardware factory for antenna hardware

    :param hardware_driver: the antenna hardware driver that the factory
        will return
    :type hardware_driver:
        :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`

    :return: a hardware factory for antenna hardware
    :rtype:
        :py:class:`~ska.low.mccs.antenna.AntennaHardwareFactory`
    """

    class BasicAntennaHardwareFactory(HardwareFactory):
        """
        A simple hardware factory that always returns the same,
        pre-created hardware driver
        """

        def __init__(self):
            """
            Create a new instance
            """
            self._hardware = hardware_driver

        @property
        def hardware(self):
            """
            Return a hardware driver created by this factory

            :return: a hardware driver created by this factory
            :rtype:
                :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
            """
            return self._hardware

    return BasicAntennaHardwareFactory()


@pytest.fixture()
def hardware_manager(hardware_factory):
    """
    Return a hardware manager for antenna hardware

    :param hardware_factory: a factory that gives us control over, and
        access to, the hardware driver that it returns, for testing
        purposes
    :type:
        :py:class:`~ska.low.mccs.antenna.AntennaHardwareDriver`

    :return: a hardware manager for antenna hardware
    :rtype: :py:class:`~ska.low.mccs.antenna.AntennaHardwareManager`
    """
    return AntennaHardwareManager(
        "low-mccs/apiu/001", 1, "low-mccs/tile/0001", 1, _factory=hardware_factory
    )


class TestAntennaHardwareManager:
    """
    Contains the tests of the
    :py:class:`ska.low.mccs.antenna.AntennaHardwareManager`
    """

    def test_on_off(self, hardware_driver, hardware_manager, mocker):
        """
        Test that the hardware manager receives updated values,
        and re-evaluates device health, each time it polls the hardware

        :param hardware_driver: the antenna hardware driver
        :type hardware_driver:
            :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
        :param hardware_manager: a hardware manager for antenna hardware
        :type hardware_manager:
            :py:class:`~ska.low.mccs.antenna.AntennaHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        voltage = 3.5
        current = 23.4
        temperature = 120

        assert not hardware_manager.is_on
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.current

        assert hardware_manager.health == HealthState.OK
        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert hardware_manager.is_on
        assert hardware_manager.voltage == AntennaHardwareSimulator.VOLTAGE
        assert hardware_manager.current == AntennaHardwareSimulator.CURRENT
        assert hardware_manager.temperature == AntennaHardwareSimulator.TEMPERATURE
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()

        hardware_driver.simulate_voltage(voltage)
        assert hardware_manager.voltage == voltage

        hardware_driver.simulate_current(current)
        assert hardware_manager.voltage == voltage

        hardware_driver.simulate_temperature(temperature)
        assert hardware_manager.temperature == temperature

        hardware_manager.off()
        assert not hardware_manager.is_on
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="Antenna hardware is turned off"):
            _ = hardware_manager.current
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()


class TestMccsAntenna:
    """
    Test class for MccsAntenna tests.
    """

    def test_PowerOn(self, device_under_test, mock_device_proxies):
        """
        Test for PowerOn

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict
        """
        mock_apiu = mock_device_proxies["low-mccs/apiu/001"]
        mock_apiu.is_antenna_on.side_effect = [False, True]

        [[result_code], [message]] = device_under_test.PowerOn()
        assert result_code == ResultCode.OK
        mock_apiu.is_antenna_on.assert_called_with(1)
        mock_apiu.turn_on_antenna.assert_called_once_with(1)

    def test_PowerOff(self, device_under_test, mock_device_proxies):
        """
        Test for PowerOff

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict
        """
        mock_apiu = mock_device_proxies["low-mccs/apiu/001"]
        mock_apiu.is_antenna_on.side_effect = [True, False]

        [[result_code], [message]] = device_under_test.PowerOff()
        assert result_code == ResultCode.OK
        mock_apiu.is_antenna_on.assert_called_with(1)
        mock_apiu.turn_off_antenna.assert_called_once_with(1)

    def test_Reset(self, device_under_test):
        """
        Test for Reset.
        Expected to fail as can't reset in the Off state

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(DevFailed):
            device_under_test.Reset()

    def test_antennaId(self, device_under_test):
        """
        Test for antennaId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.antennaId == 0

    def test_gain(self, device_under_test):
        """
        Test for gain

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.gain == 0.0

    def test_rms(self, device_under_test):
        """
        Test for rms

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.rms == 0.0

    @pytest.mark.parametrize("voltage", [19.0])
    def test_voltage(self, device_under_test, mock_device_proxies, voltage):
        """
        Test for voltage

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict
        :param voltage: a voltage value to use for testing
        :type voltage: float
        """
        mock_apiu = mock_device_proxies["low-mccs/apiu/001"]
        mock_apiu.get_antenna_voltage.return_value = voltage

        device_under_test.PowerOn()
        assert device_under_test.voltage == voltage
        assert mock_apiu.get_antenna_voltage.called_once_with(1)

    @pytest.mark.parametrize("current", [4.5])
    def test_current(self, device_under_test, mock_device_proxies, current):
        """
        Test for current

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict
        :param current: a current value to use for testing
        :type current: float
        """
        mock_apiu = mock_device_proxies["low-mccs/apiu/001"]
        mock_apiu.get_antenna_current.return_value = current

        device_under_test.PowerOn()
        assert device_under_test.current == current
        assert mock_apiu.get_antenna_current.called_once_with(1)

    @pytest.mark.parametrize("temperature", [37.4])
    def test_temperature(self, device_under_test, mock_device_proxies, temperature):
        """
        Test for temperature

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict
        :param temperature: a temperature value to use for testing
        :type temperature: float
        """
        mock_apiu = mock_device_proxies["low-mccs/apiu/001"]
        mock_apiu.get_antenna_temperature.return_value = temperature

        device_under_test.PowerOn()
        assert device_under_test.temperature == temperature
        assert mock_apiu.get_antenna_temperature.called_once_with(1)

    def test_xPolarisationFaulty(self, device_under_test):
        """
        Test for xPolarisationFaulty

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)
        assert device_under_test.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, device_under_test):
        """
        Test for yPolarisationFaulty

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.set_source(DevSource.DEV)
        assert device_under_test.yPolarisationFaulty is False

    def test_fieldNodeLongitude(self, device_under_test):
        """
        Test for fieldNodeLongitude

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fieldNodeLongitude == 0.0

    def test_fieldNodeLatitude(self, device_under_test):
        """
        Test for fieldNodeLatitude

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fieldNodeLatitude == 0.0

    def test_altitude(self, device_under_test):
        """
        Test for altitude

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.altitude == 0.0

    def test_xDisplacement(self, device_under_test):
        """
        Test for xDisplacement

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.xDisplacement == 0.0

    def test_yDisplacement(self, device_under_test):
        """
        Test for yDisplacement

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.yDisplacement == 0.0

    def test_timestampOfLastSpectrum(self, device_under_test):
        """
        Test for timestampOfLastSpectrum

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.timestampOfLastSpectrum == ""

    def test_loggingLevel(self, device_under_test):
        """
        Test for loggingLevel

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.loggingLevel == LoggingLevel.WARNING

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

    def test_controlMode(self, device_under_test):
        """
        Test for controlMode

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """
        Test for simulationMode

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.simulationMode == SimulationMode.FALSE
        with pytest.raises(
            DevFailed,
            match="Antennas cannot be put into simulation mode, but entire APIUs can.",
        ):
            device_under_test.simulationMode = SimulationMode.TRUE

    def test_logicalAntennaId(self, device_under_test):
        """
        Test for logicalAntennaId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(self, device_under_test):
        """
        Test for xPolarisationScalingFactor

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(self, device_under_test):
        """
        Test for yPolarisationScalingFactor

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(self, device_under_test):
        """
        Test for calibrationCoefficient

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(self, device_under_test):
        """
        Test for pointingCoefficient

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.pointingCoefficient) == [0.0]

    def test_spectrumX(self, device_under_test):
        """
        Test for spectrumX

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.spectrumX) == [0.0]

    def test_spectrumY(self, device_under_test):
        """
        Test for spectrumY

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.spectrumY) == [0.0]

    def test_position(self, device_under_test):
        """
        Test for position

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.position) == [0.0]

    def test_loggingTargets(self, device_under_test):
        """
        Test for loggingTargets

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.loggingTargets == ("tango::logger",)

    def test_delays(self, device_under_test):
        """
        Test for delays

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delays) == [0.0]

    def test_delayRates(self, device_under_test):
        """
        Test for delayRates

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delayRates) == [0.0]

    def test_bandpassCoefficient(self, device_under_test):
        """
        Test for bandpassCoefficient

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.bandpassCoefficient) == [0.0]


class TestInitCommand:
    """
    Contains the tests of :py:class:`~ska.low.mccs.MccsAntenna`'s
    :py:class:`~ska.low.mccs.MccsAntenna.InitCommand`.
    """

    class HangableInitCommand(MccsAntenna.InitCommand):
        """
        A subclass of InitCommand with the following properties that
        support testing:

        * A lock that, if acquired prior to calling the command, causes
          the command to hang until the lock is released
        * Call trace attributes that record which methods were called
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new HangableInitCommand instance

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model: :py:class:`DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: a logger that implements the standard library
                logger interface
            """
            super().__init__(target, state_model, logger)
            self._hang_lock = threading.Lock()
            self._initialise_hardware_management_called = False
            self._initialise_health_monitoring_called = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device (overridden here to inject a call trace
            attribute).

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            self._initialise_hardware_management_called = True
            super()._initialise_hardware_management(device)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device (overridden
            here to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device)

    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely

        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        mock_device = mocker.MagicMock()
        mock_state_model = mocker.Mock()

        init_command = self.HangableInitCommand(mock_device, mock_state_model)

        with init_command._hang_lock:
            init_command()
            # we got the hang lock first, so the initialisation thread
            # will hang in health initialisation until we release it
            init_command.interrupt()

        init_command._thread.join()

        # now that we've released the hang lock, the thread can exit
        # its _initialise_hardware_management, but before it enters its
        # _initialise_health_monitoring, it will detect that it has been
        # interrupted, and return
        assert init_command._initialise_hardware_management_called
        assert not init_command._initialise_health_monitoring_called
