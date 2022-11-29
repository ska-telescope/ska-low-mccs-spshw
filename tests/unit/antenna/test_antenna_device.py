# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the MccsAntenna."""
from __future__ import annotations

import json
import time

import pytest
import tango
from ska_control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    LoggingLevel,
    ResultCode,
    SimulationMode,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback
from ska_low_mccs_common.testing.tango_harness import DeviceToLoadType, TangoHarness

from ska_low_mccs import MccsAntenna


@pytest.fixture()
def device_to_load(
    patched_antenna_device_class: MccsAntenna,
) -> DeviceToLoadType:
    """
    Fixture that specifies the device to be loaded for testing.

    :param patched_antenna_device_class: the antenna device class to
        patch in, in place of MccsAntenna.

    :return: specification of the device to be loaded
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
    def device_under_test(
        self: TestMccsAntenna,
        tango_harness: TangoHarness,
    ) -> MccsDeviceProxy:
        """
        Fixture that returns the device under test.

        :param tango_harness: a test harness for Tango devices

        :return: the device under test
        """
        return tango_harness.get_device("low-mccs/antenna/000001")

    @pytest.mark.parametrize(
        "config_in, expected_config",
        [
            pytest.param(
                {
                    "antennaId": 1,
                    "gain": 12.3,
                    "rms": 12.3,
                    "xPolarisationFaulty": True,
                    "yPolarisationFaulty": True,
                    "xDisplacement": 12.3,
                    "yDisplacement": 45.6,
                    "zDisplacement": 78.9,
                    "timestampOfLastSpectrum": "12.23.65",
                    "logicalAntennaId": 1,
                    "xPolarisationScalingFactor": [1, 2],
                    "yPolarisationScalingFactor": [1, 2],
                    "calibrationCoefficient": [0.5, 0.5],
                    "pointingCoefficient": [0.5, 0.5],
                    "spectrumX": [0.5, 0.5],
                    "spectrumY": [0.5, 0.5],
                    "position": [0.5, 0.5],
                    "delays": [0.5, 0.5],
                    "delayRates": [0.5, 0.5],
                    "bandpassCoefficient": [0.5, 0.5],
                    "first": True,
                    "altitude": 0.5,
                    "fieldNodeLatitude": 0.5,
                    "fieldNodeLongitude": 0.5,
                },
                {
                    "antennaId": 1,
                    "gain": 12.3,
                    "rms": 12.3,
                    "xPolarisationFaulty": True,
                    "yPolarisationFaulty": True,
                    "xDisplacement": 12.3,
                    "yDisplacement": 45.6,
                    "zDisplacement": 78.9,
                    "timestampOfLastSpectrum": "12.23.65",
                    "logicalAntennaId": 1,
                    "xPolarisationScalingFactor": [1, 2],
                    "yPolarisationScalingFactor": [1, 2],
                    "calibrationCoefficient": [0.5, 0.5],
                    "pointingCoefficient": [0.5, 0.5],
                    "spectrumX": [0.5, 0.5],
                    "spectrumY": [0.5, 0.5],
                    "position": [0.5, 0.5],
                    "delays": [0.5, 0.5],
                    "delayRates": [0.5, 0.5],
                    "bandpassCoefficient": [0.5, 0.5],
                    "first": True,
                    "altitude": 0.5,
                    "fieldNodeLatitude": 0.5,
                    "fieldNodeLongitude": 0.5,
                },
                id="valid config is entered correctly",
            ),
            pytest.param(
                {
                    "antennaId": 2,
                    "gain": 6.3,
                    "yDisplacement": 6.3,
                },
                {
                    "antennaId": 2,
                    "gain": 6.3,
                    "rms": 0.0,
                    "xPolarisationFaulty": False,
                    "yPolarisationFaulty": False,
                    "xDisplacement": 0.0,
                    "yDisplacement": 6.3,
                    "zDisplacement": 0.0,
                    "timestampOfLastSpectrum": "",
                    "logicalAntennaId": 0,
                    "xPolarisationScalingFactor": [0],
                    "yPolarisationScalingFactor": [0],
                    "calibrationCoefficient": [0],
                    "pointingCoefficient": [0],
                    "spectrumX": [0],
                    "spectrumY": [0],
                    "position": [0],
                    "delays": [0],
                    "delayRates": [0],
                    "bandpassCoefficient": [0],
                    "first": True,
                    "altitude": 0.0,
                    "fieldNodeLatitude": 0.0,
                    "fieldNodeLongitude": 0.0,
                },
                id="missing config data is valid",
            ),
            pytest.param(
                {"stupid_antennaId": 1},
                {
                    "antennaId": 0,
                    "gain": 0.0,
                    "rms": 0.0,
                    "xPolarisationFaulty": False,
                    "yPolarisationFaulty": False,
                    "xDisplacement": 0.0,
                    "yDisplacement": 0.0,
                    "zDisplacement": 0.0,
                    "timestampOfLastSpectrum": "",
                    "logicalAntennaId": 0,
                    "xPolarisationScalingFactor": [0],
                    "yPolarisationScalingFactor": [0],
                    "calibrationCoefficient": [0],
                    "pointingCoefficient": [0],
                    "spectrumX": [0],
                    "spectrumY": [0],
                    "position": [0],
                    "delays": [0],
                    "delayRates": [0],
                    "bandpassCoefficient": [0],
                    "first": True,
                    "altitude": 0.0,
                    "fieldNodeLatitude": 0.0,
                    "fieldNodeLongitude": 0.0,
                },
                id="invalid named configs are skipped",
            ),
            pytest.param(
                {"gain": "some string", "timestampOfLastSpectrum": [0, 2]},
                {
                    "antennaId": 0,
                    "gain": 0.0,
                    "rms": 0.0,
                    "xPolarisationFaulty": False,
                    "yPolarisationFaulty": False,
                    "xDisplacement": 0.0,
                    "yDisplacement": 0.0,
                    "zDisplacement": 0.0,
                    "timestampOfLastSpectrum": "",
                    "logicalAntennaId": 0,
                    "xPolarisationScalingFactor": [0],
                    "yPolarisationScalingFactor": [0],
                    "calibrationCoefficient": [0],
                    "pointingCoefficient": [0],
                    "spectrumX": [0],
                    "spectrumY": [0],
                    "position": [0],
                    "delays": [0],
                    "delayRates": [0],
                    "bandpassCoefficient": [0],
                    "first": True,
                    "altitude": 0.0,
                    "fieldNodeLatitude": 0.0,
                    "fieldNodeLongitude": 0.0,
                },
                id="invalid types dont apply",
            ),
            pytest.param(
                {},
                {
                    "antennaId": 0,
                    "gain": 0.0,
                    "rms": 0.0,
                    "xPolarisationFaulty": False,
                    "yPolarisationFaulty": False,
                    "xDisplacement": 0.0,
                    "yDisplacement": 0.0,
                    "zDisplacement": 0.0,
                    "timestampOfLastSpectrum": "",
                    "logicalAntennaId": 0,
                    "xPolarisationScalingFactor": [0],
                    "yPolarisationScalingFactor": [0],
                    "calibrationCoefficient": [0],
                    "pointingCoefficient": [0],
                    "spectrumX": [0],
                    "spectrumY": [0],
                    "position": [0],
                    "delays": [0],
                    "delayRates": [0],
                    "bandpassCoefficient": [0],
                    "first": True,
                    "altitude": 0.0,
                    "fieldNodeLatitude": 0.0,
                    "fieldNodeLongitude": 0.0,
                },
                id="empty dict is no op",
            ),
        ],
    )
    def test_Configure(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        config_in: dict,
        expected_config: dict,
    ) -> None:
        """
        Test for Configure.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        """
        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE

        device_under_test.Configure(json.dumps(config_in))

        assert device_under_test.antennaId == expected_config["antennaId"]
        assert device_under_test.gain == expected_config["gain"]
        assert device_under_test.rms == expected_config["rms"]
        assert (
            device_under_test.xPolarisationFaulty
            == expected_config["xPolarisationFaulty"]
        )
        assert (
            device_under_test.yPolarisationFaulty
            == expected_config["yPolarisationFaulty"]
        )
        assert device_under_test.xDisplacement == expected_config["xDisplacement"]
        assert device_under_test.yDisplacement == expected_config["yDisplacement"]
        assert device_under_test.zDisplacement == expected_config["zDisplacement"]
        assert (
            device_under_test.timestampOfLastSpectrum
            == expected_config["timestampOfLastSpectrum"]
        )
        assert device_under_test.logicalAntennaId == expected_config["logicalAntennaId"]
        assert (
            list(device_under_test.xPolarisationScalingFactor)
            == expected_config["xPolarisationScalingFactor"]
        )
        assert (
            list(device_under_test.yPolarisationScalingFactor)
            == expected_config["yPolarisationScalingFactor"]
        )
        assert (
            list(device_under_test.calibrationCoefficient)
            == expected_config["calibrationCoefficient"]
        )
        assert (
            list(device_under_test.pointingCoefficient)
            == expected_config["pointingCoefficient"]
        )
        assert list(device_under_test.spectrumX) == expected_config["spectrumX"]
        assert list(device_under_test.spectrumY) == expected_config["spectrumY"]
        assert list(device_under_test.position) == expected_config["position"]
        assert list(device_under_test.delays) == expected_config["delays"]
        assert list(device_under_test.delayRates) == expected_config["delayRates"]
        assert (
            list(device_under_test.bandpassCoefficient)
            == expected_config["bandpassCoefficient"]
        )
        assert device_under_test.first == expected_config["first"]
        assert device_under_test.altitude == expected_config["altitude"]
        assert (
            device_under_test.fieldNodeLatitude == expected_config["fieldNodeLatitude"]
        )
        assert (
            device_under_test.fieldNodeLongitude
            == expected_config["fieldNodeLongitude"]
        )

    def test_Reset(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Reset.

        Expected to fail as can't reset in the Off state.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        with pytest.raises(tango.DevFailed):
            device_under_test.Reset()

    def test_antennaId(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for antennaId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.antennaId == 0

    def test_gain(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for gain.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.gain == 0.0

    def test_rms(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for rms.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.rms == 0.0

    @pytest.mark.parametrize("voltage", [19.0])
    def test_voltage(
        self: TestMccsAntenna,
        tango_harness: TangoHarness,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_state_changed_callback: MockChangeEventCallback,
        voltage: float,
    ) -> None:
        """
        Test for voltage.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        :param voltage: a voltage value to use for testing
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_voltage.return_value = voltage

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )

        time.sleep(0.1)

        device_state_changed_callback.assert_last_change_event(tango.DevState.DISABLE)
        assert device_under_test.state() == tango.DevState.DISABLE

        with pytest.raises(
            tango.DevFailed,
            match="Communication with component is not established",
        ):
            _ = device_under_test.voltage

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)

        device_under_test.MockApiuOn()

        time.sleep(0.1)
        # TODO How do we check that the component_manager decorators are
        # satisfied here?
        # Decorators "check_communicating" & "check_on" need to be verified in
        # this test first.

        assert device_under_test.voltage == voltage
        assert mock_apiu.get_antenna_voltage.called_once_with(1)

    @pytest.mark.parametrize("current", [4.5])
    def test_current(
        self: TestMccsAntenna,
        tango_harness: TangoHarness,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_state_changed_callback: MockChangeEventCallback,
        current: float,
    ) -> None:
        """
        Test for current.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        :param current: a current value to use for testing
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_current.return_value = current

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )
        device_state_changed_callback.assert_last_change_event(tango.DevState.DISABLE)
        assert device_under_test.state() == tango.DevState.DISABLE

        with pytest.raises(
            tango.DevFailed,
            match="Communication with component is not established",
        ):
            _ = device_under_test.current

        time.sleep(0.1)

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        assert device_under_test.state() == tango.DevState.OFF

        device_under_test.MockApiuOn()

        time.sleep(0.1)
        # TODO How do we check that the component_manager decorators are
        # satisfied here?
        # Decorators "check_communicating" & "check_on" need to be verified
        # in this test first.

        assert device_under_test.current == current
        assert mock_apiu.get_antenna_current.called_once_with(1)

    @pytest.mark.parametrize("temperature", [37.4])
    def test_temperature(
        self: TestMccsAntenna,
        tango_harness: TangoHarness,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        device_state_changed_callback: MockChangeEventCallback,
        temperature: float,
    ) -> None:
        """
        Test for temperature.

        :param tango_harness: a test harness for tango devices
        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param device_admin_mode_changed_callback: a callback that
            we can use to subscribe to admin mode changes on the device
        :param device_state_changed_callback: a callback that we can use
            to subscribe to state changes on the tile device
        :param temperature: a temperature value to use for testing
        """
        mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
        mock_apiu.get_antenna_temperature.return_value = temperature

        device_under_test.add_change_event_callback(
            "adminMode",
            device_admin_mode_changed_callback,
        )
        device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        assert device_under_test.adminMode == AdminMode.OFFLINE

        device_under_test.add_change_event_callback(
            "state",
            device_state_changed_callback,
        )
        device_state_changed_callback.assert_last_change_event(tango.DevState.DISABLE)
        assert device_under_test.state() == tango.DevState.DISABLE

        with pytest.raises(
            tango.DevFailed,
            match="Communication with component is not established",
        ):
            _ = device_under_test.temperature

        device_under_test.adminMode = AdminMode.ONLINE
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        device_state_changed_callback.assert_last_change_event(tango.DevState.OFF)

        device_under_test.MockApiuOn()

        time.sleep(0.1)
        # TODO How do we check that the component_manager decorators are
        # satisfied here?
        # Decorators "check_communicating" & "check_on" need to be verified
        # in this test first.

        assert device_under_test.temperature == temperature
        assert mock_apiu.get_antenna_temperature.called_once_with(1)

    def test_xPolarisationFaulty(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for xPolarisationFaulty.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.xPolarisationFaulty is False

    def test_yPolarisationFaulty(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for yPolarisationFaulty.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.yPolarisationFaulty is False

    def test_xDisplacement(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for xDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.xDisplacement == 0.0

    def test_yDisplacement(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for yDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.yDisplacement == 0.0

    def test_zDisplacement(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for zDisplacement.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.zDisplacement == 0.0

    def test_timestampOfLastSpectrum(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for timestampOfLastSpectrum.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.timestampOfLastSpectrum == ""

    def test_loggingLevel(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for loggingLevel.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.loggingLevel == LoggingLevel.WARNING

    def test_healthState(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
        device_health_state_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for healthState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
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

    def test_controlMode(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for controlMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.controlMode == ControlMode.REMOTE

    def test_simulationMode(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for simulationMode.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.simulationMode == SimulationMode.FALSE
        with pytest.raises(
            tango.DevFailed,
            match="MccsAntenna cannot be put into simulation mode.",
        ):
            device_under_test.simulationMode = SimulationMode.TRUE

    def test_logicalAntennaId(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for logicalAntennaId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for xPolarisationScalingFactor.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for yPolarisationScalingFactor.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for calibrationCoefficient.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for pointingCoefficient.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.pointingCoefficient) == [0.0]

    def test_spectrumX(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for spectrumX.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.spectrumX) == [0.0]

    def test_spectrumY(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for spectrumY.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.spectrumY) == [0.0]

    def test_position(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for position.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.position) == [0.0]

    def test_loggingTargets(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for loggingTargets.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.loggingTargets == ("tango::logger",)

    def test_delays(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for delays.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.delays) == [0.0]

    def test_delayRates(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for delayRates.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.delayRates) == [0.0]

    def test_bandpassCoefficient(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for bandpassCoefficient.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.bandpassCoefficient) == [0.0]

    def test_On(
        self: TestMccsAntenna,
        device_under_test: MccsDeviceProxy,
        device_admin_mode_changed_callback: MockChangeEventCallback,
        mock_apiu_device_proxy: MccsDeviceProxy,
        apiu_antenna_id: int,
    ) -> None:
        """
        Test for On.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
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

        time.sleep(0.1)

        assert device_under_test.state() == tango.DevState.DISABLE
        with pytest.raises(
            tango.DevFailed,
            match="Command On not allowed when the device is in DISABLE state",
        ):
            _ = device_under_test.On()

        time.sleep(0.1)

        device_under_test.adminMode = AdminMode.ONLINE
        # device_admin_mode_changed_callback.assert_next_change_event(AdminMode.OFFLINE)
        device_admin_mode_changed_callback.assert_last_change_event(AdminMode.ONLINE)
        assert device_under_test.adminMode == AdminMode.ONLINE
        time.sleep(0.1)

        device_under_test.MockApiuOn()
        time.sleep(0.1)

        [[result_code], [message]] = device_under_test.On()
        assert result_code == ResultCode.QUEUED
        assert message.split("_")[-1] == "On"

        mock_apiu_device_proxy.PowerUpAntenna.assert_next_call(apiu_antenna_id)
        # At this point the APIU should turn the antenna on, then fire a change event.
        # so let's fake that.
        device_under_test.MockAntennaPoweredOn()
        time.sleep(0.1)
        assert device_under_test.state() == tango.DevState.ON
