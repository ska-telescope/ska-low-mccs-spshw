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
"""contains the tests for the MccsStation"""
import time
import pytest
import tango
from ska.base.control_model import (
    AdminMode,
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.mccs import release


# pylint: disable=invalid-name
@pytest.mark.usefixtures("tango_device", "initialize_device")
class TestMccsStation:
    """
    Test cases for MccsStation
    """

    properties = {
        # SKABaseDevice properties
        "SkaLevel": "2",
        "GroupDefinitions": [],
        "LoggingLevelDefault": 4,
        "LoggingTargetsDefault": [],
    }

    def test_properties(self, tango_device):
        """ Test the properties """

    # general methods
    def test_InitDevice(self, tango_device):
        """
        Test for Initial state.
        A freshly initialised station device has no assigned resources
        and is therefore in OFF state.
        """
        assert tango_device.state() == tango.DevState.OFF
        assert tango_device.status() == "The device is in OFF state."
        assert tango_device.adminMode == AdminMode.ONLINE
        assert tango_device.healthState == HealthState.OK
        assert tango_device.controlMode == ControlMode.REMOTE
        assert tango_device.simulationMode == SimulationMode.FALSE
        assert tango_device.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert tango_device.subarrayId == 0
        assert tango_device.transientBufferFQDN == ""
        assert not tango_device.isCalibrated
        assert not tango_device.isConfigured
        assert tango_device.calibrationJobId == 0
        assert tango_device.daqJobId == 0
        assert tango_device.dataDirectory == ""
        assert tango_device.tileFQDNs is None
        assert tango_device.beamFQDNs is None
        assert list(tango_device.delayCentre) == []
        assert tango_device.calibrationCoefficients is None

    # overridden base class commands
    def test_GetVersionInfo(self, tango_device):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(tango_device.info().dev_class)
        assert tango_device.GetVersionInfo() == [version_info]

    # overridden base class attributes
    def test_buildState(self, tango_device):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert tango_device.buildState == build_info

    def test_versionId(self, tango_device):
        """Test for versionId"""
        assert tango_device.versionId == release.version

    # MccsStation attributes
    def test_subarrayId(self, tango_device):
        """Test for subarrayId attribute"""
        assert tango_device.subarrayId == 0

    def test_tileFQDNs(self, tango_device):
        """Test for tileFQDNs attribute"""
        assert tango_device.tileFQDNs is None

    def test_beamFQDNs(self, tango_device):
        """Test for beamFQDNs attribute"""
        assert tango_device.beamFQDNs is None

    def test_transientBufferFQDN(self, tango_device):
        """Test for transientBufferFQDN attribute"""
        assert tango_device.transientBufferFQDN == ""

    def test_delayCentre(self, tango_device):
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
        assert list(tango_device.delayCentre) == []

        # SETUP
        dummy_location = (-30.72113, 21.411128)
        float_format = "{:3.4f}"
        dummy_location_str = [float_format.format(x) for x in dummy_location]
        sleep_seconds = (
            tango_device.get_attribute_poll_period("delayCentre") / 1000.0 * 1.2
        )

        # RUN
        tango_device.delayCentre = dummy_location
        time.sleep(sleep_seconds)
        delay_centre = tango_device.delayCentre

        # CHECK
        delay_centre_str = [float_format.format(x) for x in delay_centre]
        assert delay_centre_str == dummy_location_str

    def test_calibrationCoefficients(self, tango_device):
        """Test for calibrationCoefficients attribute"""
        assert tango_device.calibrationCoefficients is None

    def test_isCalibrated(self, tango_device):
        """Test for isCalibrated attribute"""
        assert not tango_device.isCalibrated

    def test_isConfigured(self, tango_device):
        """Test for isConfigured attribute"""
        assert not tango_device.isConfigured

    def test_calibrationJobId(self, tango_device):
        """Teset for calibrationJobId attribute"""
        assert tango_device.calibrationJobId == 0

    def test_daqJobId(self, tango_device):
        """Test for daqJobId attributes"""
        assert tango_device.daqJobId == 0

    def test_dataDirectory(self, tango_device):
        """Test for dataDirectory attribute"""
        assert tango_device.dataDirectory == ""
