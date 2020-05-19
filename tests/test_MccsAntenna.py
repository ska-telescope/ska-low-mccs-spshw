#########################################################################
# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""Contain the tests for the SKA MCCS Antenna Device Server."""

# Imports
import pytest

from PyTango import DevState
from ska.base.control_model import AdminMode, ControlMode, HealthState, LoggingLevel


@pytest.mark.usefixtures("tango_context", "initialize_device")
class TestMccsAntenna(object):
    """Test case for Antenna DS."""

    properties = {
        "SkaLevel": "4",
        "GroupDefinitions": "",
        "LoggingLevelDefault": "4",
        "LoggingTargetsDefault": "",
    }

    def test_properties(self, tango_context):
        """Test the properties """
        assert tango_context.device.loggingLevel == LoggingLevel.INFO

    def test_State(self, tango_context):
        """Test for State"""
        assert tango_context.device.state() == DevState.ON

    #    def test_Status(self, tango_context):
    #        """Test for Status"""
    #        assert tango_context.device.status() == "This device is On"

    def test_PowerOn(self, tango_context):
        """Test for PowerOn"""
        assert tango_context.device.PowerOn() is None

    def test_PowerOff(self, tango_context):
        """Test for PowerOff"""
        assert tango_context.device.PowerOff() is None

    def test_Reset(self, tango_context):
        """Test for Reset"""
        assert tango_context.device.Reset() is None

    def test_antennaId(self, tango_context):
        """Test for antennaId"""
        assert tango_context.device.antennaId == 0

    def test_logicalTpmAntenna_id(self, tango_context):
        """Test for logicalTpmAntenna_id"""
        assert tango_context.device.logicalTpmAntenna_id == 0

    def test_logicalApiuAntenna_id(self, tango_context):
        """Test for logicalApiuAntenna_id"""
        assert tango_context.device.logicalApiuAntenna_id == 0.0

    def test_tpmId(self, tango_context):
        """Test for tpmId"""
        assert tango_context.device.tpmId == 0.0

    def test_apiuId(self, tango_context):
        """Test for apiuId"""
        assert tango_context.device.apiuId == 0.0

    def test_gain(self, tango_context):
        """Test for gain"""
        assert tango_context.device.gain == 0.0

    def test_rms(self, tango_context):
        """Test for rms"""
        assert tango_context.device.rms == 0.0

    def test_voltage(self, tango_context):
        """Test for voltage"""
        assert tango_context.device.voltage == 0.0

    def test_temperature(self, tango_context):
        """Test for temperature"""
        assert tango_context.device.temperature == 0.0

    def test_xPolarisationFaulty(self, tango_context):
        """Test for xPolarisationFaulty"""
        assert tango_context.device.xPolarisationFaulty is False

    def test_yPolarisationFaulty(self, tango_context):
        """Test for yPolarisationFaulty"""
        assert tango_context.device.yPolarisationFaulty is False

    def test_fieldNodeLongitude(self, tango_context):
        """Test for fieldNodeLongitude"""
        assert tango_context.device.fieldNodeLongitude == 0.0

    def test_fieldNodeLatitude(self, tango_context):
        """Test for fieldNodeLatitude"""
        assert tango_context.device.fieldNodeLatitude == 0.0

    def test_altitude(self, tango_context):
        """Test for altitude"""
        assert tango_context.device.altitude == 0.0

    def test_xDisplacement(self, tango_context):
        """Test for xDisplacement"""
        assert tango_context.device.xDisplacement == 0.0

    def test_yDisplacement(self, tango_context):
        """Test for yDisplacement"""
        assert tango_context.device.yDisplacement == 0.0

    def test_timestampOfLastSpectrum(self, tango_context):
        """Test for timestampOfLastSpectrum"""
        assert tango_context.device.timestampOfLastSpectrum == ""

    def test_loggingLevel(self, tango_context):
        """Test for loggingLevel"""
        assert tango_context.device.loggingLevel == 4

    def test_healthState(self, tango_context):
        """Test for healthState"""
        assert tango_context.device.healthState == HealthState.OK

    def test_adminMode(self, tango_context):
        """Test for adminMode"""
        assert tango_context.device.adminMode == AdminMode.ONLINE

    def test_controlMode(self, tango_context):
        """Test for controlMode"""
        assert tango_context.device.controlMode == ControlMode.REMOTE

    def test_simulationMode(self, tango_context):
        """Test for simulationMode"""
        assert tango_context.device.SimulationMode == 0  # Equates to False

    def test_logicalAntennaId(self, tango_context):
        """Test for logicalAntennaId"""
        assert tango_context.device.logicalAntennaId == 0

    def test_xPolarisationScalingFactor(self, tango_context):
        """Test for xPolarisationScalingFactor"""
        assert list(tango_context.device.xPolarisationScalingFactor) == [0]

    def test_yPolarisationScalingFactor(self, tango_context):
        """Test for yPolarisationScalingFactor"""
        assert list(tango_context.device.yPolarisationScalingFactor) == [0]

    def test_calibrationCoefficient(self, tango_context):
        """Test for calibrationCoefficient"""
        assert list(tango_context.device.calibrationCoefficient) == [0.0]

    def test_pointingCoefficient(self, tango_context):
        """Test for pointingCoefficient"""
        assert list(tango_context.device.pointingCoefficient) == [0.0]

    def test_spectrumX(self, tango_context):
        """Test for spectrumX"""
        assert list(tango_context.device.spectrumX) == [0.0]

    def test_spectrumY(self, tango_context):
        """Test for spectrumY"""
        assert list(tango_context.device.spectrumY) == [0.0]

    def test_position(self, tango_context):
        """Test for position"""
        assert list(tango_context.device.position) == [0.0]

    def test_loggingTargets(self, tango_context):
        """Test for loggingTargets"""
        assert tango_context.device.loggingTargets == ('tango::logger',)

    def test_delays(self, tango_context):
        """Test for delays"""
        assert list(tango_context.device.delays) == [0.0]

    def test_delayRates(self, tango_context):
        """Test for delayRates"""
        assert list(tango_context.device.delayRates) == [0.0]

    def test_bandpassCoefficient(self, tango_context):
        """Test for bandpassCoefficient"""
        assert list(tango_context.device.bandpassCoefficient) == [0.0]
