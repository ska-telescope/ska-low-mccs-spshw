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

from tango import AttrQuality, DevFailed, DevState, EventType
from ska_tango_base.control_model import (
    ControlMode,
    LoggingLevel,
    HealthState,
    SimulationMode,
)
from ska_tango_base.commands import ResultCode

from ska.low.mccs.antenna.antenna_device import AntennaHardwareManager, MccsAntenna
from ska.low.mccs.apiu.apiu_simulator import AntennaHardwareSimulator
from ska.low.mccs.hardware import HardwareFactory, PowerMode


@pytest.fixture()
def device_to_load():
    """
    Fixture that specifies the device to be loaded for testing.

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
    that and drive an antenna simulator directly.

    :return: an antenna hardware driver
    :rtype:
        :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
    """
    return AntennaHardwareSimulator()


@pytest.fixture()
def hardware_factory(hardware_driver):
    """
    Return a hardware factory for antenna hardware.

    :param hardware_driver: the antenna hardware driver that the factory
        will return
    :type hardware_driver:
        :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`

    :return: a hardware factory for antenna hardware
    :rtype:
        :py:class:`~ska.low.mccs.antenna.antenna_device.AntennaHardwareFactory`
    """

    class BasicAntennaHardwareFactory(HardwareFactory):
        """
        A simple hardware factory that always returns the same, pre-
        created hardware driver.
        """

        def __init__(self):
            """
            Create a new instance.
            """
            self._hardware = hardware_driver

        @property
        def hardware(self):
            """
            Return a hardware driver created by this factory.

            :return: a hardware driver created by this factory
            :rtype:
                :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
            """
            return self._hardware

    return BasicAntennaHardwareFactory()


@pytest.fixture()
def hardware_manager(hardware_factory, logger, mock_callback):
    """
    Return a hardware manager for antenna hardware.

    :param hardware_factory: a factory that gives us control over, and
        access to, the hardware driver that it returns, for testing
        purposes
    :type:
        :py:class:`~ska.low.mccs.antenna.antenna_device.AntennaHardwareDriver`
    :param logger: a object that implements the standard logging interface of
        :py:class:`logging.Logger`
    :type logger: :py:class:`logging.Logger`
    :param mock_callback: a mock to pass as a callback
    :type mock_callback: :py:class:`unittest.Mock`

    :return: a hardware manager for antenna hardware
    :rtype: :py:class:`~ska.low.mccs.antenna.antenna_device.AntennaHardwareManager`
    """
    return AntennaHardwareManager(
        "low-mccs/apiu/001",
        1,
        # "low-mccs/tile/0001",
        None,
        1,
        mock_callback,
        logger,
        _factory=hardware_factory,
    )


class TestAntennaHardwareManager:
    """
    Contains the tests of the
    :py:class:`ska.low.mccs.antenna.antenna_device.AntennaHardwareManager`
    """

    def test_on_off(self, hardware_driver, hardware_manager, mocker):
        """
        Test that the hardware manager receives updated values, and re-
        evaluates device health, each time it polls the hardware.

        :param hardware_driver: the antenna hardware driver
        :type hardware_driver:
            :py:class:`~ska.low.mccs.apiu.apiu_simulator.AntennaHardwareSimulator`
        :param hardware_manager: a hardware manager for antenna hardware
        :type hardware_manager:
            :py:class:`~ska.low.mccs.antenna.antenna_device.AntennaHardwareManager`
        :param mocker: fixture that wraps the :py:mod:`unittest.mock`
            module
        :type mocker: wrapper for :py:mod:`unittest.mock`
        """
        voltage = 3.5
        current = 23.4
        temperature = 120

        assert hardware_manager.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.current

        assert hardware_manager.health == HealthState.OK
        mock_health_callback = mocker.Mock()
        hardware_manager.register_health_callback(mock_health_callback)
        mock_health_callback.assert_called_once_with(HealthState.OK)
        mock_health_callback.reset_mock()

        hardware_manager.on()
        assert hardware_manager.power_mode == PowerMode.ON
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
        assert hardware_manager.power_mode == PowerMode.OFF
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.temperature
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.voltage
        with pytest.raises(ValueError, match="Antenna hardware is not ON."):
            _ = hardware_manager.current
        assert hardware_manager.health == HealthState.OK
        mock_health_callback.assert_not_called()


@pytest.fixture()
def initial_mocks(mock_factory, request):
    """
    Fixture that registers device proxy mocks prior to patching. The
    default fixture is overridden here to ensure that a mock subrack
    responds suitably to actions taken on it by the AntennaApiuProxy.

    :param mock_factory: a factory for
        :py:class:`tango.DeviceProxy` mocks
    :type mock_factory: object
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`_pytest.fixtures.SubRequest`
    :return: a dictionary of mocks, keyed by FQDN
    :rtype: dict
    """

    def _apiu_mock(state=DevState.ON, is_on=False, result_code=ResultCode.OK):
        """
        Sets up a mock for a :py:class:`tango.DeviceProxy` that connects
        to an :py:class:`~ska.low.mccs.MccsAPIU` device. The returned
        mock will respond suitably to actions taken on it by the
        AntennaApiuProxy.

        :param state: the device state that this mock APIU device
            should report
        :type state: :py:class:`tango.DevState`
        :param is_on: whether this mock APIU device should report
            that its Antennas are turned on
        :type is_on: bool
        :param result_code: the result code this mock APIU device
            should return when told to turn an Antenna on or off
        :type result_code: :py:class:`~ska_tango_base.commands.ResultCode`
        :return: a mock for a :py:class:`tango.DeviceProxy` that
            connects to an
            :py:class:`~ska.low.mccs.MccsAPIU` device.
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mock_factory()
        mock.state.return_value = state
        mock.IsAntennaOn.return_value = is_on
        mock.PowerDownAntenna.return_value = [
            [result_code],
            ["Mock information_only message"],
        ]
        mock.PowerUpAntenna.return_value = [
            [result_code],
            ["Mock information_only message"],
        ]
        return mock

    kwargs = getattr(request, "param", {})
    return {"low-mccs/apiu/001": _apiu_mock(**kwargs)}


@pytest.fixture()
def mock_factory(mocker, request):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: wrapper for :py:mod:`unittest.mock`
    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`_pytest.fixtures.SubRequest`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an
        instance)
    """
    kwargs = getattr(request, "param", {})
    is_on = kwargs.get("is_on", False)
    _values = {"areAntennasOn": [is_on, True, False, True]}

    def _mock_attribute(name, *args, **kwargs):
        """
        Returns a mock of a :py:class:`tango.DeviceAttribute` instance,
        for a given attribute name.

        :param name: name of the attribute
        :type name: str
        :param args: positional args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type args: list
        :param kwargs: named args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type kwargs: dict

        :return: a basic mock for a :py:class:`tango.DeviceAttribute`
            instance, with name, value and quality values
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.name = name
        mock.value = _values.get(name, "MockValue")
        mock.quality = "MockQuality"
        return mock

    def _mock_device():
        """
        Returns a mock for a :py:class:`tango.DeviceProxy` instance,
        with its :py:meth:`tango.DeviceProxy.read_attribute` method
        mocked to return :py:class:`tango.DeviceAttribute` mocks.

        :return: a basic mock for a :py:class:`tango.DeviceProxy`
            instance,
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.read_attribute.side_effect = _mock_attribute
        return mock

    return _mock_device


class TestMccsAntenna:
    """
    Test class for MccsAntenna tests.
    """

    def test_Reset(self, device_under_test):
        """
        Test for Reset. Expected to fail as can't reset in the Off
        state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(DevFailed):
            device_under_test.Reset()

    def test_antennaId(self, device_under_test):
        """
        Test for antennaId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.antennaId == 0

    def test_gain(self, device_under_test):
        """
        Test for gain.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.gain == 0.0

    def test_rms(self, device_under_test):
        """
        Test for rms.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.rms == 0.0

    @pytest.mark.parametrize("voltage", [19.0])
    def test_voltage(self, device_under_test, mock_device_proxies, voltage):
        """
        Test for voltage.

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

        assert device_under_test.voltage == voltage
        assert mock_apiu.get_antenna_voltage.called_once_with(1)

    @pytest.mark.parametrize("current", [4.5])
    def test_current(self, device_under_test, mock_device_proxies, current):
        """
        Test for current.

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

        assert device_under_test.current == current
        assert mock_apiu.get_antenna_current.called_once_with(1)

    @pytest.mark.parametrize("temperature", [37.4])
    def test_temperature(self, device_under_test, mock_device_proxies, temperature):
        """
        Test for temperature.

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

        assert device_under_test.temperature == temperature
        assert mock_apiu.get_antenna_temperature.called_once_with(1)

    def test_xPolarisationFaulty(self, device_under_test):
        """
        Test for xPolarisationFaulty.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, device_under_test):
        """
        Test for yPolarisationFaulty.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.yPolarisationFaulty is False

    def test_fieldNodeLongitude(self, device_under_test):
        """
        Test for fieldNodeLongitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fieldNodeLongitude == 0.0

    def test_fieldNodeLatitude(self, device_under_test):
        """
        Test for fieldNodeLatitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.fieldNodeLatitude == 0.0

    def test_altitude(self, device_under_test):
        """
        Test for altitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.altitude == 0.0

    def test_xDisplacement(self, device_under_test):
        """
        Test for xDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.xDisplacement == 0.0

    def test_yDisplacement(self, device_under_test):
        """
        Test for yDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.yDisplacement == 0.0

    def test_timestampOfLastSpectrum(self, device_under_test):
        """
        Test for timestampOfLastSpectrum.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.timestampOfLastSpectrum == ""

    def test_loggingLevel(self, device_under_test):
        """
        Test for loggingLevel.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.loggingLevel == LoggingLevel.WARNING

    def test_healthState(self, device_under_test, mock_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_callback: a mock to pass as a callback
        :type mock_callback: :py:class:`unittest.Mock`
        """
        assert device_under_test.healthState == HealthState.OK

        # Test that polling is turned on and subscription yields an
        # event as expected
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
        Test for controlMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, device_under_test):
        """
        Test for simulationMode.

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
        Test for logicalAntennaId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(self, device_under_test):
        """
        Test for xPolarisationScalingFactor.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(self, device_under_test):
        """
        Test for yPolarisationScalingFactor.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(self, device_under_test):
        """
        Test for calibrationCoefficient.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(self, device_under_test):
        """
        Test for pointingCoefficient.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.pointingCoefficient) == [0.0]

    def test_spectrumX(self, device_under_test):
        """
        Test for spectrumX.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.spectrumX) == [0.0]

    def test_spectrumY(self, device_under_test):
        """
        Test for spectrumY.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.spectrumY) == [0.0]

    def test_position(self, device_under_test):
        """
        Test for position.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.position) == [0.0]

    def test_loggingTargets(self, device_under_test):
        """
        Test for loggingTargets.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.loggingTargets == ("tango::logger",)

    def test_delays(self, device_under_test):
        """
        Test for delays.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delays) == [0.0]

    def test_delayRates(self, device_under_test):
        """
        Test for delayRates.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert list(device_under_test.delayRates) == [0.0]

    def test_bandpassCoefficient(self, device_under_test):
        """
        Test for bandpassCoefficient.

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
            Create a new HangableInitCommand instance.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska_tango_base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
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
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_hardware_management_called = True
            super()._initialise_hardware_management(device)
            with self._hang_lock:
                # hang until the hang lock is released
                pass

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device (overridden here
            to inject a call trace attribute).

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`ska_tango_base.SKABaseDevice`
            """
            self._initialise_health_monitoring_called = True
            super()._initialise_health_monitoring(device)

    def test_interrupt(self, mocker):
        """
        Test that the command's interrupt method will cause a running
        thread to stop prematurely.

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
