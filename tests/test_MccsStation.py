###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsStation project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This module contains the tests for MccsStation.
"""
import pytest
import time
import tango

from tango import DevState
from ska.base.control_model import ControlMode, HealthState, SimulationMode, TestMode
from ska.low.mccs import MccsStation, release


device_info = {
    "class": MccsStation,
    "properties": {"TileFQDNs": ["low/elt/tile_1", "low/elt/tile_2"]},
}


# pylint: disable=invalid-name
class TestMccsStation:
    """
    Test class for MccsStation tests
    """

    @pytest.mark.skip(reason="Not implemented")
    def test_properties(self, device_under_test):
        """
        Test the properties. Not implemented.
        """
        pass

    @pytest.mark.mock_device_proxy
    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        A freshly initialised station device has no assigned resources
        and is therefore in OFF state.
        """
        assert device_under_test.State() == DevState.OFF
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.subarrayId == 0
        assert device_under_test.transientBufferFQDN == ""
        assert not device_under_test.isCalibrated
        assert not device_under_test.isConfigured
        assert device_under_test.calibrationJobId == 0
        assert device_under_test.daqJobId == 0
        assert device_under_test.dataDirectory == ""
        assert list(device_under_test.tileFQDNs) == ["low/elt/tile_1", "low/elt/tile_2"]
        assert device_under_test.beamFQDNs is None
        assert list(device_under_test.delayCentre) == []
        assert device_under_test.calibrationCoefficients is None

    # overridden base class commands
    @pytest.mark.mock_device_proxy
    def test_GetVersionInfo(self, device_under_test):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(device_under_test.info().dev_class)
        assert device_under_test.GetVersionInfo() == [version_info]

    # overridden base class attributes
    def test_buildState(self, device_under_test):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert device_under_test.buildState == build_info

    def test_versionId(self, device_under_test):
        """Test for versionId"""
        assert device_under_test.versionId == release.version

    # MccsStation attributes
    @pytest.mark.mock_device_proxy
    def test_subarrayId(self, device_under_test):
        """
        Test for subarrayId attribute
        """
        station = device_under_test  # to make test easier to read
        mock_tile_1 = tango.DeviceProxy("low/elt/tile_1")
        mock_tile_2 = tango.DeviceProxy("low/elt/tile_2")

        # These tiles are mock devices so we have to manually set their
        # initial states
        mock_tile_1.subarrayId = 0
        mock_tile_2.subarrayId = 0

        # check initial state
        assert station.subarrayId == 0
        assert mock_tile_1.subarrayId == 0
        assert mock_tile_2.subarrayId == 0

        # action under test
        station.subarrayId = 1

        # check
        assert station.subarrayId == 1
        assert mock_tile_1.subarrayId == 1
        assert mock_tile_2.subarrayId == 1

    def test_tileFQDNs(self, device_under_test):
        """Test for tileFQDNs attribute"""
        assert list(device_under_test.tileFQDNs) == ["low/elt/tile_1", "low/elt/tile_2"]

    def test_beamFQDNs(self, device_under_test):
        """Test for beamFQDNs attribute"""
        assert device_under_test.beamFQDNs is None

    def test_transientBufferFQDN(self, device_under_test):
        """Test for transientBufferFQDN attribute"""
        assert device_under_test.transientBufferFQDN == ""

    def test_delayCentre(self, device_under_test):
        """
        Test for delayCentre attribute. This is a messy test because:
        (a) it is a READWRITE attribute, so we want to test that we can write
        to it AND read the value back;
        (b) delayCentre is a polled attribute, so you have to wait a poll
        period in order to read back what you've written; else you just read
        back the cached value
        (c) there is some loss of floating-point precision during transfer, so
        you have to check approximate equality when reading back what you've
        written.

        """
        assert list(device_under_test.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]
        sleep_seconds = (
            device_under_test.get_attribute_poll_period("delayCentre") / 1000.0 * 1.2
        )

        # RUN
        device_under_test.delayCentre = dummy_location
        time.sleep(sleep_seconds)
        delay_centre = device_under_test.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(self, device_under_test):
        """Test for calibrationCoefficients attribute"""
        assert device_under_test.calibrationCoefficients is None

    def test_isCalibrated(self, device_under_test):
        """Test for isCalibrated attribute"""
        assert not device_under_test.isCalibrated

    def test_isConfigured(self, device_under_test):
        """Test for isConfigured attribute"""
        assert not device_under_test.isConfigured

    def test_calibrationJobId(self, device_under_test):
        """Teset for calibrationJobId attribute"""
        assert device_under_test.calibrationJobId == 0

    def test_daqJobId(self, device_under_test):
        """Test for daqJobId attributes"""
        assert device_under_test.daqJobId == 0

    def test_dataDirectory(self, device_under_test):
        """Test for dataDirectory attribute"""
        assert device_under_test.dataDirectory == ""
