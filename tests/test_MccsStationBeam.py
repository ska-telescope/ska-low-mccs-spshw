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
This module contains the tests for MccsStationBeam.
"""
import pytest
import tango
from tango import DevSource
from ska.base.control_model import (
    ControlMode,
    HealthState,
    SimulationMode,
    TestMode,
)
from ska.low.mccs import MccsStationBeam, release


device_info = {
    "class": MccsStationBeam,
    "properties": {
        "SkaLevel": "2",
        # "GroupDefinitions": [],
        "LoggingLevelDefault": 4,
        # "LoggingTargetsDefault": [],
    },
}


# pylint: disable=invalid-name
class TestMccsStationBeam:
    """
    Test class for MccsStationBeam tests
    """

    @pytest.mark.skip(reason="Not implemented.")
    def test_properties(self, device_under_test):
        """
        Test the properties. Not implemented.
        """
        pass

    # general methods
    def test_InitDevice(self, device_under_test):
        """
        Test for Initial state.
        """
        assert device_under_test.state() == tango.DevState.OFF
        assert device_under_test.status() == "The device is in OFF state."
        assert device_under_test.healthState == HealthState.OK
        assert device_under_test.controlMode == ControlMode.REMOTE
        assert device_under_test.simulationMode == SimulationMode.FALSE
        assert device_under_test.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert device_under_test.stationId == 0
        assert device_under_test.logicalBeamId == 0
        assert device_under_test.channels is None
        assert list(device_under_test.desiredPointing) == []
        assert device_under_test.pointingDelay is None
        assert device_under_test.pointingDelayRate is None
        assert device_under_test.updateRate == 0.0
        assert list(device_under_test.antennaWeights) == []
        assert not device_under_test.isLocked

    # overridden base class commands
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

    # MccsStationBeam attributes
    def test_stationId(self, device_under_test):
        """Test for stationId attribute"""
        assert device_under_test.stationId == 0

    def test_logicalBeamId(self, device_under_test):
        """Test for logicalId attribute"""
        assert device_under_test.logicalBeamId == 0

    def test_updateRate(self, device_under_test):
        """Test for updateRate attribute"""
        assert device_under_test.updateRate == 0.0

    def test_isLocked(self, device_under_test):
        """Test for isLocked attribute"""
        assert not device_under_test.isLocked

    def test_channels(self, device_under_test):
        """Test for channels"""
        assert device_under_test.channels is None

    def test_desiredPointing(self, device_under_test):
        dummy_sky_coordinate = [1585619550.0, 192.85948, 27.12825, 1.0]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            device_under_test, "desiredPointing", dummy_sky_coordinate, float_format
        )

    def test_pointingDelay(self, device_under_test):
        assert device_under_test.pointingDelay is None

    def test_pointingDelayRate(self, device_under_test):
        assert device_under_test.pointingDelayRate is None

    def test_antennaWeights(self, device_under_test):
        dummy_weights = [0.1, 0.2, 0.3, 0.4, 0.5]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            device_under_test, "antennaWeights", dummy_weights, float_format
        )

    def _test_readwrite_double_array(
        self, device_under_test, attribute_name, value_to_write, float_format
    ):
        """
        Test for a READ-WRITE double array attribute. This is a messy
        test because there can be some loss of floating-point precision
        during transfer, so you have to check approximate equality when
        reading back what you've written. This is done here by comparing
        the values by their string representation.
        """

        # SETUP
        device_under_test.set_source(DevSource.DEV)
        write_as_string = [float_format.format(x) for x in value_to_write]

        # RUN
        device_under_test.write_attribute(attribute_name, value_to_write)
        value_as_read = device_under_test.read_attribute(attribute_name).value

        # CHECK
        read_as_string = [float_format.format(x) for x in value_as_read]
        assert read_as_string == write_as_string
