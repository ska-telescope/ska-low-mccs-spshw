# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsStation."""
from __future__ import annotations

import json
import unittest.mock

import pytest
from ska_tango_base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)

from ska_low_mccs import MccsDeviceProxy, MccsStation, release
from ska_low_mccs.testing.mock import MockChangeEventCallback
from ska_low_mccs.testing.tango_harness import DeviceToLoadType, TangoHarness


@pytest.fixture()
def device_under_test(tango_harness: TangoHarness) -> MccsDeviceProxy:
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/station/001")


class TestMccsStation:
    """Test class for MccsStation tests."""

    @pytest.fixture()
    def device_to_load(self: TestMccsStation) -> DeviceToLoadType:
        """
        Fixture that specifies the device to be loaded for testing.

        :return: specification of the device to be loaded
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration.json",
            "package": "ska_low_mccs",
            "device": "station_001",
            "proxy": MccsDeviceProxy,
        }

    def test_InitDevice(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for Initial state.

        A freshly initialised station device has no assigned
        resources.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.transientBufferFQDN == ""
        assert not device_under_test.isCalibrated
        assert not device_under_test.isConfigured
        assert device_under_test.calibrationJobId == 0
        assert device_under_test.daqJobId == 0
        assert device_under_test.dataDirectory == ""
        assert device_under_test.beamFQDNs is None
        assert list(device_under_test.delayCentre) == []
        assert device_under_test.calibrationCoefficients is None

    def test_healthState(
        self: TestMccsStation,
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

    # overridden base class attributes
    def test_buildState(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    # overridden base class commands
    def test_GetVersionInfo(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
        lrc_result_changed_callback: MockChangeEventCallback,
    ) -> None:
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param lrc_result_changed_callback: a callback to
            be used to subscribe to device LRC result changes
        """
        vinfo = [release.get_release_info(device_under_test.info().dev_class)]
        assert device_under_test.GetVersionInfo() == vinfo

    def test_versionId(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    def test_refLongitude(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for refLongitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.refLongitude == 0.0

    def test_refLatitude(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for refLatitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.refLatitude == 0.0

    def test_refHeight(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for refHeight.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.refHeight == 0.0

    def test_beamFQDNs(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for beamFQDNs attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for transientBufferFQDN attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for delayCentre attribute.

        This is a messy test because there is some loss
        of floating-point precision during transfer, so you have to check approximate
        equality when reading back what you've written.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert list(device_under_test.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]

        # RUN
        device_under_test.delayCentre = dummy_location
        delay_centre = device_under_test.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for calibrationCoefficients attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for isCalibrated attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert not device_under_test.isCalibrated

    def test_isConfigured(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for isConfigured attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert not device_under_test.isConfigured

    def test_calibrationJobId(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for calibrationJobId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for daqJobId attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(
        self: TestMccsStation,
        device_under_test: MccsDeviceProxy,
    ) -> None:
        """
        Test for dataDirectory attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert device_under_test.dataDirectory == ""


class TestPatchedStation:
    """
    Test class for MccsStation tests that patches the component manager.

    These are thin tests that simply test that commands invoked on the
    device are passed through to the component manager
    """

    @pytest.fixture()
    def device_to_load(
        self: TestPatchedStation, patched_station_class: type[MccsStation]
    ) -> DeviceToLoadType:
        """
        Fixture that specifies the device to be loaded for testing.

        :param patched_station_class: a subclass of MccsStation that has
            been patched for testing
        :return: specification of the device to be loaded
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration.json",
            "package": "ska_low_mccs",
            "device": "station_001",
            "proxy": MccsDeviceProxy,
            "patch": patched_station_class,
        }

    def test_configure(
        self: TestPatchedStation,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
    ) -> None:
        """
        Test for configure command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: the mock component manage to patch
            into this station.
        """
        config_dict = {"station_id": 1}
        json_str = json.dumps(config_dict)

        device_under_test.Configure(json_str)
        mock_component_manager.configure.assert_next_call(json_str, unittest.mock.ANY)

    def test_applyPointing(
        self: TestPatchedStation,
        device_under_test: MccsDeviceProxy,
        mock_component_manager: unittest.mock.Mock,
    ) -> None:
        """
        Test for ApplyPointing command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param mock_component_manager: the mock component manage to patch
            into this station.
        """
        beam_index = 1.0
        delay_array = [1.0e-9] * 512
        argin = [beam_index] + delay_array

        [[result_code], [message]] = device_under_test.ApplyPointing(argin)

        # we need to do this the long way because if Tango is numpy-enabled, then the
        # component manager will be called with an array not a list.
        (args, kwargs) = mock_component_manager.apply_pointing.get_next_call()
        assert not kwargs
        # since v0.13 of the base classes, a second argument will be passed which is
        # the task status callback
        assert len(args) == 2
        assert list(args[0]) == argin