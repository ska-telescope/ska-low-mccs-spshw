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
"""contains the tests for the MccsStationBeam"""
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
@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsStationBeam:
    """
    Test cases for MccsStationBeam
    """

    properties = {
        # SKABaseDevice properties
        "SkaLevel": "2",
        "GroupDefinitions": [],
        "LoggingLevelDefault": 4,
        "LoggingTargetsDefault": [],
    }

    def test_properties(self, tango_context):
        """ Test the properties """

    # general methods
    def test_InitDevice(self, tango_context):
        """
        Test for Initial state.
        A freshly initialised station device has no assigned resources
        and is therefore in OFF state.
        """
        assert tango_context.device.state() == tango.DevState.OFF
        assert tango_context.device.status() == "The device is in OFF state."
        assert tango_context.device.adminMode == AdminMode.ONLINE
        assert tango_context.device.healthState == HealthState.OK
        assert tango_context.device.controlMode == ControlMode.REMOTE
        assert tango_context.device.simulationMode == SimulationMode.FALSE
        assert tango_context.device.testMode == TestMode.NONE

        # The following reads might not be allowed in this state once properly
        # implemented
        assert tango_context.device.stationId == 0
        assert tango_context.device.logicalBeamId == 0
        assert tango_context.device.channels is None
        assert list(tango_context.device.desiredPointing) == []
        assert tango_context.device.pointingDelay is None
        assert tango_context.device.pointingDelayRate is None
        assert tango_context.device.updateRate == 0.0
        assert list(tango_context.device.antennaWeights) == []
        assert not tango_context.device.isLocked

    # overridden base class commands
    def test_GetVersionInfo(self, tango_context):
        """Test for GetVersionInfo"""
        version_info = release.get_release_info(tango_context.class_name)
        assert tango_context.device.GetVersionInfo() == [version_info]

    # overridden base class attributes
    def test_buildState(self, tango_context):
        """Test for buildState"""
        build_info = release.get_release_info()
        assert tango_context.device.buildState == build_info

    def test_versionId(self, tango_context):
        """Test for versionId"""
        assert tango_context.device.versionId == release.version

    # MccsStationBeam attributes
    def test_stationId(self, tango_context):
        """Test for stationId attribute"""
        assert tango_context.device.stationId == 0

    def test_logicalBeamId(self, tango_context):
        """Test for logicalId attribute"""
        assert tango_context.device.logicalBeamId == 0

    def test_updateRate(self, tango_context):
        """Test for updateRate attribute"""
        assert tango_context.device.updateRate == 0.0

    def test_isLocked(self, tango_context):
        """Test for isLocked attribute"""
        assert not tango_context.device.isLocked

    def test_channels(self, tango_context):
        """Test for channels"""
        assert tango_context.device.channels is None

    def test_desiredPointing(self, tango_context):
        dummy_sky_coordinate = [1585619550.0, 192.85948, 27.12825, 1.0]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            tango_context, "desiredPointing", dummy_sky_coordinate, float_format
        )

    def test_pointingDelay(self, tango_context):
        assert tango_context.device.pointingDelay is None

    def test_pointingDelayRate(self, tango_context):
        assert tango_context.device.pointingDelayRate is None

    def test_antennaWeights(self, tango_context):
        dummy_weights = [0.1, 0.2, 0.3, 0.4, 0.5]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            tango_context, "antennaWeights", dummy_weights, float_format
        )

    def _test_readwrite_double_array(
        self, tango_context, attribute_name, value_to_write, float_format
    ):
        """
        Test for a READ-WRITE double array attribute. This is a messy test
        because:
        (a) it is a READWRITE attribute, so we want to test that we can write
        to it AND read the value back;
        (b) in case it is a polled attribute, we have to wait a poll period in
        order to read back what we've written; else you just read
        back the cached value
        (c) there may be some loss of floating-point precision during transfer,
        so you have to check approximate equality when reading back what you've
        written.

        """

        # SETUP
        write_as_string = [float_format.format(x) for x in value_to_write]
        sleep_seconds = (
            tango_context.device.get_attribute_poll_period(attribute_name)
            / 1000.0
            * 1.2
        )

        # RUN
        tango_context.device.write_attribute(attribute_name, value_to_write)
        time.sleep(sleep_seconds)
        value_as_read = tango_context.device.read_attribute(attribute_name).value

        # CHECK
        read_as_string = [float_format.format(x) for x in value_as_read]
        assert read_as_string == write_as_string
