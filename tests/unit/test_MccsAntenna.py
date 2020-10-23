#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the SKA-Low MCCS project
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
import tango

from ska.base.control_model import ControlMode, SimulationMode, HealthState
from ska.base.commands import ResultCode

from ska.low.mccs.antenna import (
    AntennaHardwareManager,
    AntennaHardwareSimulator,
    MccsAntenna,
)

device_to_load = {
    "path": "charts/ska-low-mccs/data/configuration.json",
    "package": "ska.low.mccs",
    "device": "antenna_000001",
}


@pytest.fixture()
def hardware_manager():
    """
    Return a hardware manager for antenna hardware (in simulation mode)

    :return: a hardware manager for antenna hardware
    :rtype: :py:class:`~ska.low.mccs.antenna.AntennaHardwareManager`
    """
    return AntennaHardwareManager(SimulationMode.TRUE)


class TestAntennaHardwareManager:
    """
    Contains the tests of the
    :py:class:`ska.low.mccs.antenna.AntennaHardwareManager`
    """

    def test_init_simulation_mode(self):
        """
        Test that we can't create an hardware manager that isn't in
        simulation mode
        """
        with pytest.raises(
            NotImplementedError,
            match=("AntennaHardwareManager._create_driver method not implemented."),
        ):
            _ = AntennaHardwareManager(SimulationMode.FALSE)

    def test_simulation_mode(self, hardware_manager):
        """
        Test that we can't take the hardware manager out of simulation
        mode

        :param hardware_manager: a hardware manager for antenna hardware
        :type hardware_manager: :py:class:`~ska.low.mccs.antenna.AntennaHardwareManager`
        """
        with pytest.raises(
            NotImplementedError,
            match=("AntennaHardwareManager._create_driver method not implemented."),
        ):
            hardware_manager.simulation_mode = SimulationMode.FALSE

    def test_on_off(self, hardware_manager, mocker):
        """
        Test that the hardware manager receives updated values,
        and re-evaluates device health, each time it polls the hardware

        :param hardware_manager: a hardware manager for antenna hardware
        :type hardware_manager: :py:class:`~ska.low.mccs.antenna.AntennaHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        voltage = 3.5
        temperature = 120

        hardware = hardware_manager._hardware

        assert not hardware_manager.is_on
        assert hardware_manager.temperature is None
        assert hardware_manager.voltage is None
        assert hardware_manager.health == HealthState.UNKNOWN

        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.UNKNOWN)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert hardware_manager.is_on
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware._voltage = voltage
        assert hardware_manager.voltage == voltage

        hardware._temperature = temperature
        assert hardware_manager.temperature == temperature

        hardware_manager.off()
        assert not hardware_manager.is_on
        assert hardware_manager.voltage is None
        assert hardware_manager.temperature is None
        assert hardware_manager.health == HealthState.UNKNOWN
        mock_health_callback.assert_called_once_with(HealthState.UNKNOWN)


class TestMccsAntenna:
    """
    Test class for MccsAntenna tests.
    """

    def test_PowerOn(self, device_under_test):
        """
        Test for PowerOn

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        (result, info) = device_under_test.PowerOn()
        assert result == ResultCode.OK

    def test_PowerOff(self, device_under_test):
        """
        Test for PowerOff

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        (result, info) = device_under_test.PowerOff()
        assert result == ResultCode.OK

    def test_Reset(self, device_under_test):
        """
        Test for Reset.
        Expected to fail as can't reset in the Off state

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(tango.DevFailed):
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

    def test_logicalTpmAntenna_id(self, device_under_test):
        """
        Test for logicalTpmAntenna_id

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalTpmAntenna_id == 0

    def test_logicalApiuAntenna_id(self, device_under_test):
        """
        Test for logicalApiuAntenna_id

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalApiuAntenna_id == 0.0

    def test_tpmId(self, device_under_test):
        """
        Test for tpmId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.tpmId == 0.0

    def test_apiuId(self, device_under_test):
        """
        Test for apiuId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.apiuId == 0.0

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

    def test_voltage(self, device_under_test):
        """
        Test for voltage

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.PowerOn()
        assert device_under_test.voltage == AntennaHardwareSimulator.VOLTAGE

    def test_temperature(self, device_under_test):
        """
        Test for temperature

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        device_under_test.PowerOn()
        assert device_under_test.temperature == AntennaHardwareSimulator.TEMPERATURE

    def test_xPolarisationFaulty(self, device_under_test):
        """
        Test for xPolarisationFaulty

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, device_under_test):
        """
        Test for yPolarisationFaulty

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
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
        assert device_under_test.loggingLevel == 4

    def test_healthState(self, device_under_test):
        """
        Test for healthState

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.healthState == HealthState.OK

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
        assert device_under_test.simulationMode == SimulationMode.TRUE
        with pytest.raises(
            tango.DevFailed,
            match=("AntennaHardwareManager._create_driver method not implemented."),
        ):
            device_under_test.simulationMode = SimulationMode.FALSE
        assert device_under_test.simulationMode == SimulationMode.TRUE

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


class TestMccsAntenna_InitCommand:
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
            this device (overwridden here to inject a call trace
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
