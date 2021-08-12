# type: ignore
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
"""This module contains the tests for the MccsAntenna."""
import pytest
import time

import tango

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import (
    AdminMode,
    ControlMode,
    LoggingLevel,
    HealthState,
    SimulationMode,
)

from ska_low_mccs import MccsDeviceProxy

from ska_low_mccs.testing import TangoHarness


@pytest.fixture()
def device_to_load(patched_antenna_device_class):
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_antenna_device_class: the antenna device class to
        patch in, in place of MccsAntenna.

    :return: specification of the device to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "device": "antenna_000001",
        "patch": patched_antenna_device_class,
        "proxy": MccsDeviceProxy,
    }


class TestMccsAntenna:
    """Test class for MccsAntenna tests."""

    @pytest.fixture()
    def device_under_test(self, tango_harness):
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/antenna/000001")

    def test_Reset(self, device_under_test):
        """
        Test for Reset. Expected to fail as can't reset in the Off state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        with pytest.raises(tango.DevFailed):
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
    def test_voltage(
        self,
        tango_harness: TangoHarness,
        device_under_test,
        device_admin_mode_changed_callback,
        voltage,
    ):
        """
        Test for voltage.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param voltage: a voltage value to use for testing
        :type voltage: float
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_voltage.return_value = voltage

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        with pytest.raises(tango.DevFailed, match="Not connected"):
            _ = device_under_test.voltage

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.MockApiuOn()
        time.sleep(0.1)

        assert device_under_test.voltage == voltage
        assert mock_apiu.get_antenna_voltage.called_once_with(1)

    @pytest.mark.parametrize("current", [4.5])
    def test_current(
        self,
        tango_harness: TangoHarness,
        device_under_test,
        device_admin_mode_changed_callback,
        current,
    ):
        """
        Test for current.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param current: a current value to use for testing
        :type current: float
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_current.return_value = current

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        with pytest.raises(tango.DevFailed, match="Not connected"):
            _ = device_under_test.current

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.MockApiuOn()

        assert device_under_test.current == current
        assert mock_apiu.get_antenna_current.called_once_with(1)

    @pytest.mark.parametrize("temperature", [37.4])
    def test_temperature(
        self,
        tango_harness: TangoHarness,
        device_under_test,
        device_admin_mode_changed_callback,
        temperature,
    ):
        """
        Test for temperature.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param temperature: a temperature value to use for testing
        :type temperature: float
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_temperature.return_value = temperature

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        with pytest.raises(tango.DevFailed, match="Not connected"):
            _ = device_under_test.temperature

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.MockApiuOn()

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

    def test_zDisplacement(self, device_under_test):
        """
        Test for zDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.zDisplacement == 0.0

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

    def test_healthState(self, device_under_test, device_health_state_changed_callback):
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_health_state_changed_callback: a callback that we
            can use to subscribe to health state changes on the device
        """
        device_under_test.add_change_event_callback(
            "healthState",
            device_health_state_changed_callback,
        )
        device_health_state_changed_callback.assert_next_change_event(
            HealthState.UNKNOWN
        )
        assert device_under_test.healthState == HealthState.UNKNOWN

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
            tango.DevFailed,
            match="MccsAntenna cannot be put into simulation mode.",
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

    def test_On(
        self,
        device_under_test,
        device_admin_mode_changed_callback,
        mock_apiu_device_proxy,
        apiu_antenna_id,
    ):
        """
        Test for On.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the tile
            device
        :param mock_apiu_device_proxy: a proxy to the APIU device for
            the APIU of the antenna under test.
        :param apiu_antenna_id: the position of the antenna in its APIU
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        assert device_under_test.state() == tango.DevState.DISABLE
        with pytest.raises(
            tango.DevFailed,
            match="Command On not allowed when the device is in DISABLE state",
        ):
            _ = device_under_test.On()

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.MockApiuOn()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.OK
        assert message == "On command completed OK"

        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)
        # At this point the APIU should turn the antenna on, then fire a change event.
        # so let's fake that.
        device_under_test.MockAntennaPoweredOn()
        assert device_under_test.state() == tango.DevState.ON
