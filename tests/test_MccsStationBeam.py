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
        assert tango_device.stationId == 0
        assert tango_device.logicalBeamId == 0
        assert tango_device.channels is None
        assert list(tango_device.desiredPointing) == []
        assert tango_device.pointingDelay is None
        assert tango_device.pointingDelayRate is None
        assert tango_device.updateRate == 0.0
        assert list(tango_device.antennaWeights) == []
        assert not tango_device.isLocked

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

    # MccsStationBeam attributes
    def test_stationId(self, tango_device):
        """Test for stationId attribute"""
        assert tango_device.stationId == 0

    def test_logicalBeamId(self, tango_device):
        """Test for logicalId attribute"""
        assert tango_device.logicalBeamId == 0

    def test_updateRate(self, tango_device):
        """Test for updateRate attribute"""
        assert tango_device.updateRate == 0.0

    def test_isLocked(self, tango_device):
        """Test for isLocked attribute"""
        assert not tango_device.isLocked

    def test_channels(self, tango_device):
        """Test for channels"""
        assert tango_device.channels is None

    def test_desiredPointing(self, tango_device):
        dummy_sky_coordinate = [1585619550.0, 192.85948, 27.12825, 1.0]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            tango_device, "desiredPointing", dummy_sky_coordinate, float_format
        )

    def test_pointingDelay(self, tango_device):
        assert tango_device.pointingDelay is None

    def test_pointingDelayRate(self, tango_device):
        assert tango_device.pointingDelayRate is None

    def test_antennaWeights(self, tango_device):
        dummy_weights = [0.1, 0.2, 0.3, 0.4, 0.5]
        float_format = "{:3.4f}"
        self._test_readwrite_double_array(
            tango_device, "antennaWeights", dummy_weights, float_format
        )

    def _test_readwrite_double_array(
        self, tango_device, attribute_name, value_to_write, float_format
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
            tango_device.get_attribute_poll_period(attribute_name)
            / 1000.0
            * 1.2
        )

        # RUN
        tango_device.write_attribute(attribute_name, value_to_write)
        time.sleep(sleep_seconds)
        value_as_read = tango_device.read_attribute(attribute_name).value

        # CHECK
        read_as_string = [float_format.format(x) for x in value_as_read]
        assert read_as_string == write_as_string
