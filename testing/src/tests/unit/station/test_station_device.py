# type: ignore
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
"""This module contains the tests for MccsStation."""
import json
import unittest.mock

import pytest

from ska_tango_base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska_low_mccs import MccsDeviceProxy, release


@pytest.fixture()
def device_under_test(tango_harness):
    """
    Fixture that returns the device under test.

    :param tango_harness: a test harness for Tango devices

    :return: the device under test
    """
    return tango_harness.get_device("low-mccs/station/001")


class TestMccsStation:
    """Test class for MccsStation tests."""

    @pytest.fixture()
    def device_to_load(self):
        """
        Fixture that specifies the device to be loaded for testing.

        :return: specification of the device to be loaded
        :rtype: dict
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration.json",
            "package": "ska_low_mccs",
            "device": "station_001",
            "proxy": MccsDeviceProxy,
        }

    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state. A freshly initialised station device has no assigned
        resources.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.healthState == HealthState.UNKNOWN
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.TEST

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.subarrayId == 0
        assert device_under_test.transientBufferFQDN == ""
        assert not device_under_test.isCalibrated
        assert not device_under_test.isConfigured
        assert device_under_test.calibrationJobId == 0
        assert device_under_test.daqJobId == 0
        assert device_under_test.dataDirectory == ""
        assert device_under_test.beamFQDNs is None
        assert list(device_under_test.delayCentre) == []
        assert device_under_test.calibrationCoefficients is None

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

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """
        Test for buildState.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    # overridden base class commands
    def test_GetVersionInfo(self, device_under_test):
        """
        Test for GetVersionInfo.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    def test_versionId(self, device_under_test):
        """
        Test for versionId.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    def test_refLongitude(self, device_under_test):
        """
        Test for refLongitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.refLongitude == 0.0

    def test_refLatitude(self, device_under_test):
        """
        Test for refLatitude.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.refLatitude == 0.0

    def test_refHeight(self, device_under_test):
        """
        Test for refHeight.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.refHeight == 0.0

    def test_subarrayId(self, device_under_test):
        """
        Test for subarrayId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.subarrayId == 0
        device_under_test.subarrayId = 1
        assert device_under_test.subarrayId == 1

    def test_beamFQDNs(self, device_under_test):
        """
        Test for beamFQDNs attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(self, device_under_test):
        """
        Test for transientBufferFQDN attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(self, device_under_test):
        """
        Test for delayCentre attribute. This is a messy test because there is some loss
        of floating-point precision during transfer, so you have to check approximate
        equality when reading back what you've written.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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

    def test_calibrationCoefficients(self, device_under_test):
        """
        Test for calibrationCoefficients attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(self, device_under_test):
        """
        Test for isCalibrated attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isCalibrated

    def test_isConfigured(self, device_under_test):
        """
        Test for isConfigured attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert not device_under_test.isConfigured

    def test_calibrationJobId(self, device_under_test):
        """
        Test for calibrationJobId attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(self, device_under_test):
        """
        Test for daqJobId attributes.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(self, device_under_test):
        """
        Test for dataDirectory attribute.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.dataDirectory == ""


class TestPatchedStation:
    """
    Test class for MccsStation tests that patches the component manager.

    These are thin tests that simply test that commands invoked on the
    device are passed through to the component manager
    """

    @pytest.fixture()
    def device_to_load(self, patched_station_class):
        """
        Fixture that specifies the device to be loaded for testing.

        :param patched_station_class: a subclass of MccsStation that has
            been patched for testing
        :return: specification of the device to be loaded
        :rtype: dict
        """
        return {
            "path": "charts/ska-low-mccs/data/configuration.json",
            "package": "ska_low_mccs",
            "device": "station_001",
            "proxy": MccsDeviceProxy,
            "patch": patched_station_class,
        }

    def test_configure(
        self,
        device_under_test,
        mock_component_manager: unittest.mock.Mock,
    ):
        """
        Test for configure command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        :param mock_component_manager: the mock component manage to patch
            into this station.
        """
        config_dict = {"station_id": 1}
        json_str = json.dumps(config_dict)

        [[result_code], [message]] = device_under_test.Configure(json_str)
        mock_component_manager.configure.assert_next_call(1)

    def test_applyPointing(
        self,
        device_under_test,
        mock_component_manager: unittest.mock.Mock,
    ):
        """
        Test for ApplyPointing command.

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
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
        assert len(args) == 1
        assert list(args[0]) == argin
